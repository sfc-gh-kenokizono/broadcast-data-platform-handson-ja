# 第2章 dbtで視聴データを整え、5局をまとめる

第1章では、5局のファイルを局別のRAWテーブルへ取り込みました。
この章では、Snowflake Workspacesのdbt実行パネルを使い、各局のデータを整形・集計・テストしてから5局分をまとめます。
入力は20,000台・2026年5月1日〜7月31日の再生成した合成データです。

dbtは、**SQLで書いたモデルファイルを読み、Jinja、`ref()`、`source()`、macroを実行可能なSnowflake SQLへコンパイルし、そのSQLでテーブルを作り、結果をテストする**仕組みです。

> dbtの「モデル」は、テーブルを作るSQLの定義です。第3章の「機械学習モデル」とは別の意味です。

## 1. 先に全体像をつかむ

### Compile、Run、Test、Buildの違い

| 操作 | 何をするか | テーブルを作るか |
|---|---|---|
| Compile（コンパイル） | プロジェクトやモデルの定義から実行可能なSQLを作り、WorkspaceでDAG（依存関係の図）を確認できる状態にする | 作らない |
| Run | モデルのテーブルやビューを作る。ただし、すべてのデータテストは実行しない | 作る |
| Test | すでにある出力だけをテストする | 作らない |
| Build | 選んだモデルとテストを依存順に実行する | 作る |

このハンズオンでは、最初に **Compileを1回**実行して仕組みを理解し、その後は **Build** で実際のテーブル作成とテストを行います。
**Compileの後にRunを実行する手順ではありません。** Buildは内部で必要なコンパイルも行うため、実処理ではBuildを選びます。

### この章のデータフロー

```text
RAW.VIEWING_LOG_NW01
  ↓ 完全重複・不正区間を除き、表記と分数を整える
NW01.CLEAN_VIEWING
  ├→ NW01.MART_DEVICE_DAILY       端末・日付・ジャンル別の日次実績
  └→ NW01.VIEWING_MINUTES
        ↓
      NW01.MART_MINUTE_AUDIENCE   局・日付・分別の重複なし端末数
```

同じ処理をNW01〜NW05で行います。5局すべてが成功した後、完成済みの局別マートを `UNION ALL` して次の2表を作ります。

- `COMMON.VIEWING_DAILY`
- `COMMON.MINUTE_AUDIENCE`

RAWを先に全局結合して整形したり、commonで分展開をやり直したりはしません。局別処理は局別ウェアハウス、統合はcommonウェアハウスで実行します。

### ファイル・フォルダの役割

| 場所 | 役割 |
|---|---|
| `dbt/dbt_project.yml` | プロジェクトのルール、モデル・macro・テストのパス、テーブル化、タグ、開始・終了時hook |
| `dbt/profiles.yml` | 6つのtarget。ロール・DB・基本スキーマ・ウェアハウスの組を定義 |
| `dbt/selectors.yml` | `nw01`〜`nw05` と `common` のモデル・テスト範囲を定義 |
| `dbt/models/sources.yml` | dbtが読み込む外部のRAW入力テーブルを宣言 |
| `dbt/models/nw01`〜`nw05` | 各局4モデル。整形、日次集計、分展開、分別集計 |
| `dbt/models/common` | 作成済みの5局マートを `UNION ALL` する2モデル |
| `dbt/models/schema.yml` | 列の説明と、NULL・一意性・許容値などの汎用テスト |
| `dbt/macros` | 局間で再利用するSQL処理と、実行範囲の安全確認 |
| `dbt/tests` | 件数・分展開・分別集計などを検査する22個のカスタムSQLテスト |

すべてのファイルを開いたり、1つずつ実行したりする必要はありません。
仕組みを理解するには、`dbt_project.yml`、`profiles.yml`、`selectors.yml`、NW01のモデル1つ、macro 1つを見れば十分です。

### モデルファイルとmacroの違い

例として [clean_viewing_nw01.sql](../dbt/models/nw01/clean_viewing_nw01.sql) を開きます。実質的な処理は次の2行です。

```sql
{{ config(alias='CLEAN_VIEWING') }}
{{ clean_viewing(source('raw', 'VIEWING_LOG_NW01')) }}
```

- モデルファイルは「どの入力へ、どの共通処理を使い、何を出力するか」を指定します。
- `source('raw', 'VIEWING_LOG_NW01')` は、dbtの外部にあるRAW入力を特定します。
- `clean_viewing(...)` は [macros/clean_viewing.sql](../dbt/macros/clean_viewing.sql) のmacroを呼びます。
- macroには、重複除去、不正区間の除外、ジャンル表記の統一、視聴分数の計算という実際の共通SQLがあります。
- `ref()` は別モデルへの依存を表し、正しいテーブル名と実行順をdbtへ伝えます。

このプロジェクトの22モデルは、`dbt_project.yml` の設定によりすべて **table** として保存されます。

## 2. Workspaceと実行パネルを確認する

第1章で作ったGit Workspaceを開きます。Workspaceの作り直しや、ローカルPCへのdbtインストールは不要です。

開始前に次を確認します。

- 第1章のロードが終わり、[局別の期待件数](01_setup.md#5-件数を確認)と一致している。5局合計は1,050,648行。
- `BCAST_PLATFORM_ENGINEER_ROLE` を利用できる。
- dbtバージョン `1.9.4` と、第1章で作った6つのウェアハウスを利用できる。

まず `dbt/dbt_project.yml` を開きます。これにより、Workspaceが `dbt` フォルダをdbtプロジェクトとして検出し、画面上部にdbt実行パネルが表示されます。

画面では次のコントロールを確認します。UI言語によってラベルが英語で表示される場合があります。

| 画面の項目 | 最初の設定 | 意味 |
|---|---|---|
| Project / プロジェクト | `dbt` | 実行するdbtプロジェクト |
| Profile / プロファイル | `nw01` | `profiles.yml` のtarget。ロール・DB・基本スキーマ・WHの組を選ぶ |
| Environment / 環境 | `環境なし` | この教材では `env.yml` を使わない。英語表示では `None` など |
| Command / コマンド | `コンパイル` または `Compile` | 最初にSQLとDAGを確認する操作 |
| Command / コマンド | `Build` | モデル作成とテストを行う本番操作 |
| 右端の実行ボタン | 三角形の実行ボタン | 選んだコマンドを開始 |

添付画面の実行結果領域には **Output、DAG、Performance** タブがあります。画面の版によって表示名やタブ構成が少し異なる場合があります。

- **Output**: 実行コマンド、標準出力、成功・失敗を確認します。
- **DAG**: source、モデル、テストの依存関係を図で確認します。
- **Performance**: 実行時間など、直近実行の性能情報を確認します。

Profileとselectorは役割が違います。

| 対象 | Profile | 追加引数 | 保存先 | ウェアハウス |
|---|---|---|---|---|
| NW01 | `nw01` | `--selector nw01` | `NW01` | `BCAST_PLATFORM_NW01_WH` |
| NW02 | `nw02` | `--selector nw02` | `NW02` | `BCAST_PLATFORM_NW02_WH` |
| NW03 | `nw03` | `--selector nw03` | `NW03` | `BCAST_PLATFORM_NW03_WH` |
| NW04 | `nw04` | `--selector nw04` | `NW04` | `BCAST_PLATFORM_NW04_WH` |
| NW05 | `nw05` | `--selector nw05` | `NW05` | `BCAST_PLATFORM_NW05_WH` |
| 5局統合 | `common` | `--selector common` | `COMMON` | `BCAST_PLATFORM_COMMON_WH` |

**selectorは実行するモデルとテストを選び、Profileはロール・DB・基本スキーマ・WHの組を選びます。必ず同じ名前の組み合わせにします。** 実際の出力スキーマは、モデルフォルダごとの設定も使って `NW01` などに固定されます。

## 3. NW01をCompileして中身を見る

1. Projectが `dbt` であることを確認します。
2. Profileで `nw01` を選びます。
3. Environmentは `環境なし` のままにします。
4. Commandで `コンパイル` / `Compile` を選びます。
5. `コンパイル` ボタン右側の▼を開き、追加引数に `--selector nw01` を入力します。
6. 右端の実行ボタンを押します。

### Compileの確認

- **Output** で成功を確認します。Compileなので出力テーブルはまだ作られません。
- **DAG** を開き、NW01の4モデルと、それらに関係する15テストを確認します。
- DAGまたはファイル一覧から `clean_viewing_nw01.sql` を開きます。
- エディタ右上の **View Compiled SQL** を選びます。
- 左側の短いmacro呼び出しと、右側の展開済みSQLを見比べます。

ここで、`source()` が実テーブル名へ、macroが実際の共通SQLへ展開されることを確認できます。

## 4. NW01をBuildする

Compileの後にRunへ切り替えず、次はBuildを実行します。

1. Projectを `dbt`、Profileを `nw01`、Environmentを `環境なし` にします。
2. Commandで `Build` を選びます。
3. 追加引数に `--selector nw01` を入力します。
4. 右端の実行ボタンを押します。

**成功の目印:** 実行が成功し、モデル4件・テスト15件がすべて成功、エラー0件・スキップ0件です。ログには `Completed successfully` や `ERROR=0 SKIP=0` と表示されます。

テーブルが見えるだけでは成功判定にしません。以前の実行で作られた可能性があるため、必ず今回のOutputを確認します。

NW01の期待値は次のとおりです。

- RAW: 195,938行
- 整形後: 195,808行
- 日次マートの `SESSION_COUNT` 合計: 195,808回
- 日次マート: 194,852行
- `VIEWING_MINUTES`: 2,520,553行
- `MART_MINUTE_AUDIENCE`: 109,630行

必要に応じて **Monitoring → Query History（クエリ履歴）** を開き、実際の作成SQLとテストSQLが `BCAST_PLATFORM_NW01_WH` で動いたことを確認します。

## 5. NW02〜NW05を1局ずつBuildする

NW01と同じ方法で、Profileとselectorを同じ局へ変更して **1局ずつ** Buildします。

1. Profile=`nw02`、追加引数=`--selector nw02` でBuildし、成功を確認します。
2. Profile=`nw03`、追加引数=`--selector nw03` でBuildし、成功を確認します。
3. Profile=`nw04`、追加引数=`--selector nw04` でBuildし、成功を確認します。
4. Profile=`nw05`、追加引数=`--selector nw05` でBuildし、成功を確認します。

各局で、モデル4件・テスト15件がすべて成功し、エラー0件・スキップ0件であることを確認してから次の局へ進みます。

| 局 | RAW行数 | 整形後の行数＝日次マートの回数合計 | 日次マート行数 | `VIEWING_MINUTES` | `MART_MINUTE_AUDIENCE` |
|---|---:|---:|---:|---:|---:|
| NW01 | 195,938 | 195,808 | 194,852 | 2,520,553 | 109,630 |
| NW02 | 184,465 | 184,335 | 183,763 | 2,374,287 | 109,695 |
| NW03 | 179,991 | 179,861 | 179,103 | 2,324,082 | 109,463 |
| NW04 | 234,324 | 234,195 | 233,190 | 3,020,548 | 109,934 |
| NW05 | 255,930 | 255,801 | 254,212 | 3,293,457 | 109,813 |
| 合計 | 1,050,648 | 1,050,000 | 1,045,120 | 13,532,927 | 548,535 |

### 失敗した場合

- commonへ進みません。
- エラー文、局名、Profile、追加引数を確認します。
- 原因を直し、その局と同じ組み合わせでBuildを再実行します。
- 今回のOutputと期待件数を再確認します。

Buildは1つの大きなトランザクションではありません。テストや後半のモデルが失敗しても、途中まで作成したテーブルが残ることがあります。残っているテーブルだけを見て成功と判断しないでください。

この教材では、5局の成功を人が確認します。**今回の一連のBuildログだけ**を使い、過去の成功ログや残っているテーブルを今回の成功とみなしません。5局を確認している途中で、入力データやdbtファイルを変更しないでください。

## 6. 5局すべての成功後にcommonをBuildする

NW01〜NW05の5局すべてが成功したことを確認してから実行します。これが **5局ゲート** です。

1. Profileを `common` に変更します。
2. Commandは `Build` を選びます。
3. 追加引数に `--selector common` を入力します。
4. 右端の実行ボタンを押します。

**成功の目印:** モデル2件・テスト6件がすべて成功し、エラー0件・スキップ0件です。ログには `Completed successfully` や `ERROR=0 SKIP=0` と表示されます。

`--selector +common` や `--select +tag:common` のように **`+` を付けないでください。**
`+` は依存する上流モデルまで選ぶため、5局の処理をcommonウェアハウスで再実行する原因になります。この手順では、作成済みの局別マートだけを `UNION ALL` します。

## 7. SQLファイルで最終確認する

[sql/02_check_common.sql](../sql/02_check_common.sql) をSQLファイルまたはSQLエディタで開き、上から順に実行します。
`EXECUTE IMMEDIATE $$` から `$$;` までは、途中で区切らず一括実行してください。

| 確認 | 期待する結果 |
|---|---|
| `COMMON.VIEWING_DAILY` の行数 | 1,045,120行 |
| 全期間・全5局のリーチ | 20,000台 |
| 総視聴回数 | 1,050,000回 |
| 総視聴時間 | 約12,511,642.266667分 |
| 最初・最後の視聴日 / ジャンル数 | 2026-05-01・2026-07-31 / 8種類 |
| `MINUTE_MART_ROWS` | 548,535行 |
| `DEVICE_MINUTE_BUCKETS` | 13,532,927 |
| `LABEL_DEVICES_WITHOUT_OBSERVATIONS` | 0 |
| `OBSERVED_DEVICES_WITHOUT_LABEL_ROW` | 0 |

局別照合では、件数の `*_DIFFERENCE` が0であることを確認します。
FLOATの分数差は **`max(0.000001分, 比較元の分数の絶対値 × 0.000000001)` 以内**なら正常です。
`INVALID_ROWS` と `VALID_DUPLICATE_ROWS` はRAWから除く対象件数なので、0でなくても異常ではありません。

不一致やエラーがあれば第3章へ進まず、該当局のBuild、5局ゲート、commonのBuildを順に見直します。

ここまで成功したら、[第3章 MLOps](03_mlops.md)へ進みます。

## 補足：処理内容と数え方

ここからは任意です。本編の操作後に読めば十分です。

`CLEAN_VIEWING` は入力6列が完全一致する重複を除き、開始・終了があり、終了が開始より後、24時間以内の区間だけを残します。
配布RAW 1,050,648行から、完全重複300行、時刻逆転200行、24時間超148行を除き、1,050,000行になります。
同じイベントIDで内容が違う行は勝手に統合せず、一意性テストで検出します。

ジャンルは空白と指定表記を整え、`NEWS`、`DRAMA`、`VARIETY`、`ANIME`、`SPORTS`、`MUSIC`、`MOVIE`、`INFO` の8種類にそろえます。RAWは変更せず、整形結果を別テーブルへ保存します。

`MART_DEVICE_DAILY` は、同じ局・端末・開始日・開始時ジャンルの記録をまとめます。
1,050,000件は1,045,120行になりますが、`SESSION_COUNT` の合計は1,050,000回です。

`VIEWING_MINUTES` は、視聴区間と少しでも重なる1分枠へ展開します。開始は含み、終了は含みません。
`MART_MINUTE_AUDIENCE` は、同じ局・分の `DEVICE_ID` を重複なく数えます。瞬間同時視聴台数や人数ではありません。
13,532,927は、局・端末・分の組の延べ数です。

総経過時間750,698,536秒を60で割ると約12,511,642.266667分です。
視聴時間はFLOATで計算するため、最終確認では微小な丸め誤差を許容します。

各局には汎用テストとカスタムSQLテストを合わせて15件、commonには6件あります。
**各局15件 × 5局 + common 6件 = 81テスト**です。`dbt/tests` のファイル数22とは、実行されるテストノード数が異なります。

## 補足：profiles.ymlと認証情報

`profiles.yml` の6つのtargetは、Profileドロップダウンの `nw01`〜`nw05`、`common` として表示されます。保存先スキーマは `dbt_project.yml` のフォルダ別設定と `generate_schema_name.sql` も使って、局別の `NW01`〜`NW05` と `COMMON` に固定します。
`account: ''` と `user: ''` は、Snowflake内の現在のアカウントとユーザーで実行するため意図的に空欄です。

**パスワード、秘密鍵、トークンなどの認証情報を `profiles.yml` に追記しないでください。**
このプロジェクトは外部パッケージを使わないため、`dbt deps` も不要です。

## 任意：SQLで実行する場合の参考

通常は、ここまで説明したWorkspaceのdbt実行パネルを使います。
次の `EXECUTE DBT PROJECT FROM WORKSPACE` は、UIが概念的に生成するSQLの参考、またはUIを利用できない場合のフォールバックです。
**UIで同じBuildを実行した場合、このSQLを追加で実行しないでください。** 同じテーブル作成とテストが重複します。

Workspace名を変更している場合は、`"broadcast-data-platform-handson-ja"` を実際の名前へ変更します。`USER$` は実行者自身のWorkspaceを表します。

### NW01のBuild例

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw01 --selector nw01';
```

### commonのBuild例

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target common --selector common';
```

SQLでは `--target` がUIのProfile、`--selector` がUIの追加引数に相当します。ここでも同じ名前を組み合わせ、commonにグラフ展開の `+` を付けません。

## 参考

画面や実行結果が手順と異なる場合は、全体Buildへ変更せず講師へ確認してください。

- [Workspaces for dbt Projects on Snowflake](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-using-workspaces)
- [EXECUTE DBT PROJECT](https://docs.snowflake.com/en/sql-reference/sql/execute-dbt-project)
- [対応dbt Coreバージョン](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions)