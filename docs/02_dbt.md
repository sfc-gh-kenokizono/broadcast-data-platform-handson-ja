# 第 2 章 局ごとの dbt 処理と最終統合

> 2026-09-15実機追記：トライアルのネイティブdbt 1.9.4／adapter 1.9.2で6 build・11モデル・38テストが成功しました。各局とCOMMONのモデル・テストのWH帰属も履歴で確認済みです。ステージから配置したdbt project objectでの検証であり、以下の参加者Workspace経路は未確認です。詳細は[検証記録](verification.md)。

## この章の到達点

5 局それぞれの生データを、その局のウェアハウスで整形・テスト・日次集計します。**5 局すべての build 成功を確認した後にだけ**、共通ウェアハウスで集計済みテーブルを `UNION ALL` します。生データを先にまとめる構成ではありません。

対象データベースは `BCAST_PLATFORM_HANDSON` です。前章のセットアップと Parquet ロードが完了し、`RAW.VIEWING_LOG_NW01` から `RAW.VIEWING_LOG_NW05` が存在することが前提です。この章の操作は参加者が Snowsight 上で行います。ローカル端末への dbt インストールや認証情報の登録は不要です。

## DAG と粒度

```text
RAW.VIEWING_LOG_NW01 -> NW01.CLEAN_VIEWING -> NW01.MART_DEVICE_DAILY --+
RAW.VIEWING_LOG_NW02 -> NW02.CLEAN_VIEWING -> NW02.MART_DEVICE_DAILY --+
RAW.VIEWING_LOG_NW03 -> NW03.CLEAN_VIEWING -> NW03.MART_DEVICE_DAILY --+-> COMMON.VIEWING_DAILY
RAW.VIEWING_LOG_NW04 -> NW04.CLEAN_VIEWING -> NW04.MART_DEVICE_DAILY --+   (UNION ALL)
RAW.VIEWING_LOG_NW05 -> NW05.CLEAN_VIEWING -> NW05.MART_DEVICE_DAILY --+
```

上図の RAW は入力テーブルで、dbt が作るのは **11 個すべて materialized table** です。各局の build は `CLEAN_VIEWING` の作成とテストを先に行い、上流テストが失敗すれば下流のマートをスキップします。ビューによる計算の先送りはありません。

| 出力 | 1 行の粒度 | 列 |
|---|---|---|
| `NWxx.CLEAN_VIEWING` | 局内の 1 イベント | `EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE, VIEW_MINUTES` |
| `NWxx.MART_DEVICE_DAILY` | 局 × 端末 × 日 × ジャンル | `NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES` |
| `COMMON.VIEWING_DAILY` | 局 × 端末 × 日 × ジャンル | 各局マートと同じ 6 列 |

`VIEW_DATE` は `TO_DATE(VIEW_FROM)` です。日付をまたぐ区間も開始日の実績として扱い、日ごとの区間分割は行いません。`SESSION_COUNT` はイベント件数、`VIEW_MINUTES` はミリ秒差を 60,000 で割った分数の合計です。表示用の丸めは集計時に行いません。`TIMESTAMP_NTZ` にタイムゾーン変換は加えません。

`EVENT_ID` の一意性は局内で検証します。共通マートでは `NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE` の **4 列の組**を検証します。端末は複数の局やジャンルに現れるため、`DEVICE_ID` 単独やジャンルを省いたキーを一意とはしません。ラベルや予測値は dbt の入力にも出力にも含めません。

## ファイルと設定

| ファイル | 役割 |
|---|---|
| `dbt/dbt_project.yml` | プロジェクト名 `bcast_platform_dbt`、局別スキーマ・タグ、table 指定 |
| `dbt/profiles.yml` | プロファイル `bcast_platform`、明示的な 6 targets と WH |
| `dbt/selectors.yml` | `nw01` から `nw05` と `common` の選択範囲 |
| `dbt/macros/generate_schema_name.sql` | `NW01_NW01` などに連結せず、指定スキーマ名をそのまま使用 |
| `dbt/macros/assert_execution_scope.sql` | build/run/test の target・WH・ロール・選択範囲の不一致を拒否 |
| `dbt/macros/clean_viewing.sql` | 全局で共通の整形ロジック。ただし各呼び出しの入力は 1 局のみ |
| `dbt/macros/device_daily.sql` | 全局で共通の日次集計ロジック |
| `dbt/models/nw01/` から `nw05/` | 局別のモデル 2 個ずつ。dbt モデル名には局の接尾辞を付け、実テーブル名は alias で統一 |
| `dbt/models/common/viewing_daily.sql` | 5 個の集計済みマートの UNION ALL |
| `dbt/models/schema.yml` | 全モデルの列定義と generic tests。YAML anchor で同じ検証を共有 |
| `dbt/tests/` | 局別の区間検査 5 個と common 件数検査 1 個 |

`profiles.yml` の `account: ''` と `user: ''` は意図した空文字です。旧教材と同じ Snowflake ネイティブ実行用であり、パスワード、トークン、鍵は記載しません。ローカル dbt Core から接続するためのプロファイルではありません。

外部パッケージは使用しません。`packages.yml`、`dbt deps`、パッケージ取得のための外部アクセス統合は不要です。**参加者の Snowsight dbt 1.9 系と、作成者のローカル dbt 1.11 系を区別します。** `require-dbt-version` は `>=1.9.0, <2.0.0` とし、generic tests の引数は `arguments:` で包まずテスト名の直下に置きます。1.10.5 以降専用の形式は使いません。ローカル 1.11 では旧形式の非推奨メッセージが出る場合がありますが、参加者の 1.9 との互換性を優先します。

以下は `DBT_VERSION = '1.9.4'` を明示した未実行の例です。開始前に講師が利用環境の対応バージョンを確認してください。1.9 の実機検証が済んだという意味ではなく、ローカル 1.11 の parse 成功を代用しません。

### GENRE の整形

半角・全角スペースを両端から除き、`UPPER` で大文字化した後、`ＮＥＷＳ`、`ＤＲＡＭＡ`、`ＶＡＲＩＥＴＹ`、`ＡＮＩＭＥ`、`ＳＰＯＲＴＳ` を対応する半角英字へ明示的に変換します。例は ` news ` → `NEWS`、`　ＳＰＯＲＴＳ　` → `SPORTS` です。

これは一般的な Unicode 正規化ではありません。任意の半角・全角混在や別名まで自動補正せず、未知値は残して accepted_values テストで検出します。不正区間、NULL、重複も黙って削除しません。

## 実行する target と WH

| target / selector / tag | 出力スキーマ | SQL とテストの WH |
|---|---|---|
| `nw01` | `NW01` | `BCAST_PLATFORM_NW01_WH` |
| `nw02` | `NW02` | `BCAST_PLATFORM_NW02_WH` |
| `nw03` | `NW03` | `BCAST_PLATFORM_NW03_WH` |
| `nw04` | `NW04` | `BCAST_PLATFORM_NW04_WH` |
| `nw05` | `NW05` | `BCAST_PLATFORM_NW05_WH` |
| `common` | `COMMON` | `BCAST_PLATFORM_COMMON_WH` |

**タグや selector は対象を選ぶだけで、WH を切り替えません。** 実行時の `--target` で接続先 WH を選びます。モデル固有の `snowflake_warehouse` は使わず、generic / singular tests を含む接続先を揃えます。SQL エディタの WH だけで局別 WH が設定されたとは判断せず、Snowsight 1.9 の子 SQL の実績で確認します。

共通 WH に帰属するのは、既存の局別マートを読み込む統合テーブル作成と common テストです。common 件数テストは 5 局のマートも読みますが、それらを作り直しません。テーブルをどのスキーマから読むかではなく、その SELECT/CTAS をどの WH で実行するかで計算負荷が決まります。dbt 実行基盤自体の消費と、変換・検査 SQL の消費を混同しないでください。

## Snowsight で 5 局を実行

1. 前章で取り込んだワークスペースの `dbt/dbt_project.yml` と `dbt/profiles.yml` を確認します。この章ではワークスペースや dbt project object を新規作成しません。
2. 自分が所有するワークスペースを使い、ロール `BCAST_PLATFORM_ENGINEER_ROLE` を選びます。RAW の読み取り、局別・COMMON スキーマのテーブル作成、6 WH の利用権限が必要です。
3. 下記は Snowsight の SQL エディタで実行する具体例です。ワークスペース表示名が異なる場合は `"broadcast-data-platform-handson-ja"` の部分を実際の名前に変更します。`PROJECT_ROOT = 'dbt'` はリポジトリ内の dbt フォルダです。SQL は一文ずつ実行し、結果を確認してから進めます。
4. 各結果で `Success = TRUE`、`EXCEPTION` なし、dbt 出力のモデル成功・全テスト pass・skip/error なしを確認します。今回の想定は各局 **2 models + 7 tests** です。出力アーカイブまたは実行履歴を残します。

**開始ゲート（実行者・講師が確認）:** 対応する 1.9 系の実行環境、ロール、6 WH、入力ロードを確認し、まず NW01 の `ls` で 2 models + 7 tests だけが選ばれることを確認します。NW01 build 後は CTAS とテスト SELECT の子クエリがともに `BCAST_PLATFORM_NW01_WH` を使ったことを確認してから残りの局へ進みます。target や選択範囲が保持されない環境では停止し、common WH での全体実行へ置き換えません。

最初に選択範囲だけを見る場合は次を使います。`ls` はローカルでの検証にも使用した、モデルを作成しないコマンドです。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'ls --target nw01 --select tag:nw01 --indirect-selection cautious';
```

続いて局別に実行します。**共通 build はこのブロックに含めません。**

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw01 --select tag:nw01 --indirect-selection cautious';

EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw02 --select tag:nw02 --indirect-selection cautious';

EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw03 --select tag:nw03 --indirect-selection cautious';

EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw04 --select tag:nw04 --indirect-selection cautious';

EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw05 --select tag:nw05 --indirect-selection cautious';
```

`--select tag:nw01 --indirect-selection cautious` は `--selector nw01` と同じ選択範囲です。selector 定義にも cautious を含めています。NW02 以降も同様です。

### Common 前の成功確認

- 同じコードと入力データに対する NW01 の最新 build が成功し、全 7 tests が pass。作成・検査の子 SQL は `BCAST_PLATFORM_NW01_WH`。
- 同条件で NW02 の最新 build が成功し、全 7 tests が pass。作成・検査の子 SQL は `BCAST_PLATFORM_NW02_WH`。
- 同条件で NW03 の最新 build が成功し、全 7 tests が pass。作成・検査の子 SQL は `BCAST_PLATFORM_NW03_WH`。
- 同条件で NW04 の最新 build が成功し、全 7 tests が pass。作成・検査の子 SQL は `BCAST_PLATFORM_NW04_WH`。
- 同条件で NW05 の最新 build が成功し、全 7 tests が pass。作成・検査の子 SQL は `BCAST_PLATFORM_NW05_WH`。

途中で 1 局でも失敗したら **common は実行せず**、原因を修正して該当局の同じ build を再実行します。古い成功結果や、古いテーブルが存在することを今回の成功の代わりにしません。確認期間中は入力・モデルを変更しないでください。

このゲートは **実行者による 5 回の成功確認**です。別々の dbt 呼び出し間で成功状態を永続管理する仕組みは本章にはありません。ガード macro が検査するのは target と選択範囲であり、過去 5 回の成功を証明するものではありません。将来の自動化では 5 回の成功をすべて条件にする必要があります。

## 最後に Common を作成

前節の 5 条件を満たした場合にだけ、この一文を実行します。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target common --select tag:common --indirect-selection cautious';
```

対象は **1 model + 3 tests** です。`--selector common` でも同じ範囲です。`ref()` は既存テーブルの場所を解決するためにも使われるため、上流が選択されていなくても 5 局のマートを参照できます。`generate_schema_name` により、common target でも参照先は `BCAST_PLATFORM_HANDSON.NW01.MART_DEVICE_DAILY` などのままです。

**`--select +viewing_daily`、`--select +tag:common`、無指定の全体 build は使いません。** 上流を含める `+` は各局モデルまで common WH で作り直す原因になります。本プロジェクトの on-run-start ガードはこの混在を拒否しますが、正しい選択を基本としてください。任意の SQL、変更されたプロファイル、ガードを削除したプロジェクトまで防ぐセキュリティ境界ではありません。

共通テーブルは再集計も重複排除もしない `UNION ALL` です。common build 後のテストが失敗した場合、テーブルが存在しても次章へ進みません。dbt build 全体は単一トランザクションではなく、テスト失敗で作成済みテーブルが自動的に取り消されるわけではありません。

**次章へのゲート（実行者が確認）:** common の 1 model と 3 tests がすべて成功し、skip/error なし、作成・検査の子 SQL が `BCAST_PLATFORM_COMMON_WH` を使い、局別モデルの再作成がないことを確認します。コードや入力を変更した場合は影響する局の build と common build をやり直します。`run` だけ、またはテストだけの成功は build 成功の代わりにしません。

## テストの範囲

| 検査 | 方法 | 実行スコープ |
|---|---|---|
| 必須列の NULL | 全出力列を `IS NULL ... OR ...` で調べる `not_null_columns`。モデルごとに 1 本 | 各局 clean / mart、common |
| イベント一意性 | `EVENT_ID` の `unique` | 局内のみ |
| 正しい局 | 局別 `NETWORK_ID` の accepted_values は自局 1 値 | 局内のみ |
| 正しいジャンル | `NEWS, DRAMA, VARIETY, ANIME, SPORTS` の accepted_values | 各局 clean |
| 区間の正当性 | `VIEW_TO > VIEW_FROM` と正の VIEW_MINUTES | 自局だけを ref する singular test |
| 複合キー一意性 | 4 列を GROUP BY し COUNT(*) > 1 を失敗行として返す | 各局 / common |
| 統合件数 | 5 局マートの件数と common の局別件数が一致 | common のみ |

**各局 7 本 = clean の必須列 NULL 1 + EVENT_ID 一意性 1 + 自局 accepted_values 1 + GENRE accepted_values 1 + 区間・正の分数 1 + mart の必須列 NULL 1 + mart の複合キー一意性 1。common は必須列 NULL・複合キー一意性・局別件数一致の 3 本。合計 38 tests（7 × 5 + 3）です。** 列ごとに同じ検査を繰り返す 127 本から、説明できる検査単位に絞っています。

区間テストは NULL の時刻・分数も失敗行として返します。集計値の正数検査を各層で繰り返すテストは省略しました。正の区間を通過したイベントを `COUNT` / `SUM` することを前提とし、任意に書き換えられた集計テーブルまで網羅的に検証する品質監視製品ではありません。

generic tests は選択されたモデルに付随します。区間の singular tests はそれぞれ `nw01` などのタグを持ち、他局を参照しません。件数テストは `common` タグのみを持ち、**5 局のマートと common の全 6 `ref()` を依存関係として保持**します。cautious は依存先がすべて選ばれたテストだけを間接選択するため、局だけの選択に件数テストが巻き込まれません。common の件数テストはタグで明示的に選ぶため、上流モデルを選択していなくても実行対象です。タグを外したり `--select viewing_daily` だけに変えたりすると、cautious では件数テストが落ちます。逆に `+` を足すと親モデルを選んでしまいます。いずれも本章の代替手順ではありません。

検査は同じ行の列比較、GROUP BY、および局別に 1 行へ集約した件数同士のキー結合です。端末列・局列・ジャンル列の値集合を CROSS JOIN して架空の組み合わせを作ることはありません。共通件数テストは局別の一致を検証するので、結果として合計件数も一致します。

### テストだけを再実行する場合

テストだけでも必ず対応する target を指定します。たとえば NW03 は次のとおりです。NW01、NW02、NW04、NW05 は数字を揃えて置き換えます。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'test --target nw03 --select tag:nw03 --indirect-selection cautious';

EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'test --target common --select tag:common --indirect-selection cautious';
```

common のテスト単独実行は共通 build 後に限ります。クエリ履歴で dbt が発行した CTAS とテスト SELECT の **WAREHOUSE_NAME** を確認してください。親の `EXECUTE DBT PROJECT` 一文の WH だけから判断せず、出力ログやクエリ ID から子 SQL を確認します。本教材作成時点で実際の WH 帰属を実測したわけではありません。

## ローカル検証と限界

再検証用の `dbt/verification/verify_local.py` は **教材の 38 tests とは別の作成者向けオフライン回帰検査**です。既存の dbt Core 1.11.7 / dbt-snowflake 1.11.3 を使い、ネットワーク接続を拒否します。6 targets の parse、selector と tag 選択の一致、テスト単独選択、DAG、スキーマ・alias、正確なテスト種類・件数・必須列・許容値、6 WH の分離、ガードの許可・拒否、テスト SQL の Jinja 展開と参照範囲を検査します。`build`、`run`、`test`、`compile`、`show`、`debug` は実行しません。新規パッケージのインストールも行いません。

common 件数テストの全 6 依存、明示タグでの選択、親モデルを選ばないこと、モデル名だけでは cautious により件数テストが落ちることも回帰検査します。各局のテストはその局のモデルだけを解決できる条件で展開し、他局未作成でも他局を参照しない構造を確認します。これは実テーブルでの SELECT 成功を意味しません。

オフラインのコマンド数は `parse` 6 回 + `ls` 26 回です。11 models と 38 tests の Jinja を展開し、ジャンルの明示変換、未知値の保持、ミリ秒の分換算、開始日への集計、4 列の粒度、5 局 UNION ALL も別途検査します。これらは文字列・依存関係の回帰検査であり、SQL の実行や実データの合否判定は行いません。

ガードは on-run-start の `execute` と `selected_resources` / `graph.nodes` / `target` を使います。実機デプロイ時の全体コンパイルもhookを評価するため、`flags.WHICH` がcompile/parse/ls/listの場合だけ除外します。フラグが取得できなければbuild扱いで検査します。build/run/testではtarget・WH・選択範囲の検査を維持し、トライアルでも誤った局のbuildを拒否しました。テストに明示タグがなければ親モデルから所属を判断し、common件数テストは明示commonタグを優先します。ローカル検査はフラグなしの保守的動作、実行コマンドの拒否、コンパイルの許可を含みます。

```bash
uv run --offline --no-project --no-config /opt/anaconda3/bin/python \
  /Users/kenokizono/Code/broadcast-data-platform-handson-ja/dbt/verification/verify_local.py
```

これは作成者の既存ローカル環境用のコマンドで、参加者の必須手順ではありません。生成される `dbt/target/` と `dbt/logs/` は検証用アーティファクトであり、教材のソースではありません。空の user に関するローカル adapter メッセージはネイティブ用プロファイルと dbt Core の違いです。認証情報を足して消す必要はありません。

**ローカル parse は Snowflake SQL のコンパイル、実データのテスト pass、Snowsight の画面操作、権限、実際の WH 帰属を保証しません。** 上記のネイティブ SQL 例は未実行です。Snowsight の操作パネルが同じオプションを保持するかも未検証のため、ボタン操作を同等の代替手順とは断言しません。

公式の構文とバージョン情報: [EXECUTE DBT PROJECT](https://docs.snowflake.com/en/sql-reference/sql/execute-dbt-project)、[対応 dbt Core バージョン](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions)。