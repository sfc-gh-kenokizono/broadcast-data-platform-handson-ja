# 第2章 dbtで視聴データを整え、5局をまとめる

第1章では、5局のファイルを局別のRAWテーブルへ取り込みました。
この章では、用意済みのdbtプロジェクトを使い、各局のデータを整形・集計・テストしてから5局分をまとめます。
入力は20,000台・2026年5月1日〜7月31日の再生成した合成データです。

> dbtの「モデル」は、テーブルを作るSQLです。第3章の「機械学習モデル」とは別の意味です。

## この章の操作は6ステップ

次の順番を変えずに進めます。

| 手順 | 操作 | 次へ進む条件 |
|---|---|---|
| 1 | 第1章で作ったGit Workspaceを開く | 教材の `dbt/` と `sql/` が見える |
| 2 | NW01の `ls` を実行する | **4モデル・15テストだけ**が表示される |
| 3 | NW01の `build` を実行する | ログ・件数・使用ウェアハウスの3点が正しい |
| 4 | NW02〜NW05を**1局ずつ** `build` する | 各局でログ・件数・使用ウェアハウスの3点が正しい |
| 5 | **5局すべての成功後だけ**commonを `build` する | 2モデル・6テストが成功する |
| 6 | [sql/02_check_common.sql](../sql/02_check_common.sql) を実行する | 期待値と一致し、照合がエラーなく終わる |

**1局でも失敗したらcommonへ進みません。** 対象局を直して同じ `build` を再実行します。
`--select +viewing_daily`、`--select +tag:common`、対象指定なしの全体buildには変更しないでください。

## 1. 作るテーブルを確認する

dbtは、SQLによる加工と結果のテストを依存順に実行します。この教材ではSQLとテストを用意済みです。

```text
RAW.VIEWING_LOG_NW01
  ↓ 完全重複・不正区間を除き、表記と分数を整える
NW01.CLEAN_VIEWING
  ├→ NW01.MART_DEVICE_DAILY       端末・日付・ジャンル別の日次実績
  └→ NW01.VIEWING_MINUTES
        ↓
      NW01.MART_MINUTE_AUDIENCE   局・日付・分別の重複なし端末数
```

同じ処理をNW01〜NW05で行います。各局が成功した後、完成済みのマートを `UNION ALL` して次の2表を作ります。

- `COMMON.VIEWING_DAILY`
- `COMMON.MINUTE_AUDIENCE`

RAWを先に全局結合して整形したり、commonで分展開をやり直したりはしません。局別の処理は局別ウェアハウス、統合はcommonウェアハウスで実行します。

### この章で使う言葉

| 言葉 | 意味 |
|---|---|
| RAW | 取り込んだ原本を残す場所。書き換えない |
| クレンジング | 空白や大文字・小文字などの違いを整える処理 |
| マート | グラフや分析に使いやすい形へまとめた表 |
| モデル | dbtで出力テーブルを作るSQLの定義 |
| テスト | NULL・重複・想定外の値・件数差などを調べる処理 |
| `build` | モデル作成とテストを依存順に実行するコマンド |
| `target` | 保存先・実行ロール・ウェアハウスの設定 |
| タグ | NW01など、実行する処理を選ぶ目印 |

## 2. Git Workspaceを開く

第1章で作ったGit Workspaceを開きます。Workspaceの作り直しや、ローカルPCへのdbtインストールは不要です。

開始前に次を確認します。

- 第1章のロードが終わり、[局別の期待件数](01_setup.md#5-件数を確認)と一致している。5局合計は1,050,648行。
- 講師が案内した教材データを使っている。既存環境では[第1章の注意](01_setup.md#実行前の確認)に従っている。
- `BCAST_PLATFORM_ENGINEER_ROLE` を選べる。
- dbtバージョン `1.9.4` と、第1章で作った6つのウェアハウスを使える。

局・target・タグ・保存先・ウェアハウスは、必ず同じ行の組み合わせで使います。

| 局・統合先 | `--target` | `--select` | 保存先 | ウェアハウス |
|---|---|---|---|---|
| NW01 | `nw01` | `tag:nw01` | `NW01` | `BCAST_PLATFORM_NW01_WH` |
| NW02 | `nw02` | `tag:nw02` | `NW02` | `BCAST_PLATFORM_NW02_WH` |
| NW03 | `nw03` | `tag:nw03` | `NW03` | `BCAST_PLATFORM_NW03_WH` |
| NW04 | `nw04` | `tag:nw04` | `NW04` | `BCAST_PLATFORM_NW04_WH` |
| NW05 | `nw05` | `tag:nw05` | `NW05` | `BCAST_PLATFORM_NW05_WH` |
| 5局統合 | `common` | `tag:common` | `COMMON` | `BCAST_PLATFORM_COMMON_WH` |

> SQLエディタでウェアハウスを選ぶだけでは、dbtの実行先は決まりません。各SQLの `--target` を省略しないでください。

Workspace名を変更している場合は、以降のSQLにある `"broadcast-data-platform-handson-ja"` を実際の名前へ変更します。`USER$` は実行者自身のWorkspaceを表します。

## 3. NW01の対象を確認する

Workspace内のSQLエディタで次のSQLを実行します。`ls` は対象一覧を表示するだけで、テーブルを作りません。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'ls --target nw01 --select tag:nw01 --indirect-selection cautious';
```

**成功の目印:** NW01の4モデルと15テストだけが表示されます。

他局やcommonが含まれる、または指定が受け付けられない場合は、全体実行へ置き換えず講師へ確認してください。

## 4. NW01を作成・テストする

次の1文を実行します。待機中に同じ `build` を重ねて実行しないでください。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw01 --select tag:nw01 --indirect-selection cautious';
```

### 4-1. ログを確認する

実行結果と `STDOUT` で、次のすべてを確認します。

- `Success = TRUE` で、`EXCEPTION` にエラーがない。
- `Completed successfully` が表示される。
- モデル4件とテスト15件がすべて成功する。
- `ERROR=0 SKIP=0` になっている。

固定のPASS合計ではなく、4モデル・15テストの内訳を見ます。補助処理（hook）がPASS合計に含まれる場合があるためです。
テーブルが見えても、以前の実行で作ったものかもしれません。必ず**今回のログ**を確認します。

### 4-2. 件数を確認する

NW01のbuild成功後、次のSQLを実行します。

```sql
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE WAREHOUSE BCAST_PLATFORM_NW01_WH;
SELECT
  (SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.RAW.VIEWING_LOG_NW01) AS RAW_ROWS,
  (SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.NW01.CLEAN_VIEWING) AS CLEAN_ROWS,
  (SELECT SUM(SESSION_COUNT) FROM BCAST_PLATFORM_HANDSON.NW01.MART_DEVICE_DAILY) AS MART_SESSIONS;
```

**成功の目印:** `RAW_ROWS = 195,938`、`CLEAN_ROWS = 195,808`、`MART_SESSIONS = 195,808` です。

### 4-3. ウェアハウスを確認する

Snowsightの **Monitoring → Query History（クエリ履歴）** を開き、自分のユーザーと実行時刻で絞ります。

1. 4表を作る `CREATE TABLE ... AS SELECT` を確認します。
2. `count(*) as failures` などのテストSQLを確認します。
3. どちらも `BCAST_PLATFORM_NW01_WH` で動いたことを確認します。

親の `EXECUTE DBT PROJECT` だけでなく、実際に表を作成・検査した子クエリを見ます。

## 5. NW02〜NW05を1局ずつ実行する

次のSQLは**1文ずつ**実行します。1局ごとにログ・件数・ウェアハウスを確認してから次へ進みます。

### NW02

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw02 --select tag:nw02 --indirect-selection cautious';
```

**成功の目印:** 4モデル・15テスト、`ERROR=0 SKIP=0`、RAW 184,465行、整形後と回数合計184,335、日次マート183,763行、`BCAST_PLATFORM_NW02_WH`。

### NW03

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw03 --select tag:nw03 --indirect-selection cautious';
```

**成功の目印:** 4モデル・15テスト、`ERROR=0 SKIP=0`、RAW 179,991行、整形後と回数合計179,861、日次マート179,103行、`BCAST_PLATFORM_NW03_WH`。

### NW04

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw04 --select tag:nw04 --indirect-selection cautious';
```

**成功の目印:** 4モデル・15テスト、`ERROR=0 SKIP=0`、RAW 234,324行、整形後と回数合計234,195、日次マート233,190行、`BCAST_PLATFORM_NW04_WH`。

### NW05

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target nw05 --select tag:nw05 --indirect-selection cautious';
```

**成功の目印:** 4モデル・15テスト、`ERROR=0 SKIP=0`、RAW 255,930行、整形後と回数合計255,801、日次マート254,212行、`BCAST_PLATFORM_NW05_WH`。

局別の期待値を一覧でも確認できます。

| 局 | RAW行数 | 整形後の行数＝日次マートの回数合計 | 日次マート行数 | `VIEWING_MINUTES` | `MART_MINUTE_AUDIENCE` |
|---|---:|---:|---:|---:|---:|
| NW01 | 195,938 | 195,808 | 194,852 | 2,520,553 | 109,630 |
| NW02 | 184,465 | 184,335 | 183,763 | 2,374,287 | 109,695 |
| NW03 | 179,991 | 179,861 | 179,103 | 2,324,082 | 109,463 |
| NW04 | 234,324 | 234,195 | 233,190 | 3,020,548 | 109,934 |
| NW05 | 255,930 | 255,801 | 254,212 | 3,293,457 | 109,813 |
| 合計 | 1,050,648 | 1,050,000 | 1,045,120 | 13,532,927 | 548,535 |

件数確認SQLは、NW01用SQLのWH・スキーマ・RAWテーブル名にある `NW01` を、対象局の番号へ**すべて同時に**変更して使います。

### 失敗した場合

- commonへ進まない。
- エラー文、局名、実行したSQLを控える。
- 原因を直し、対象局の同じ `build` を再実行する。
- 今回のログ・件数・ウェアハウスを再確認する。

この教材では、5局の成功を人が確認します。過去の成功ログと混ぜず、確認中に入力データやSQLを変更しないでください。
テスト失敗時も、途中まで作ったテーブルは残ることがあります。自動で元へ戻る仕組みではありません。

## 6. 5局すべての成功後にcommonを作る

NW01〜NW05の5局すべてで、ログ・件数・ウェアハウスの確認が終わってから、次の1文を実行します。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target common --select tag:common --indirect-selection cautious';
```

**成功の目印:** 2モデル・6テストが成功し、`ERROR=0 SKIP=0` です。作成SQLとテストSQLは `BCAST_PLATFORM_COMMON_WH` で動き、局別テーブルは作り直されていません。

> `--select +viewing_daily`、`--select +tag:common`、対象指定なしの全体buildには変更しないでください。
> `+` は前段も選ぶため、局別処理をcommonウェアハウスで動かす原因になります。

## 7. commonの結果を確認する

[sql/02_check_common.sql](../sql/02_check_common.sql) を開き、先頭から順に実行します。
`EXECUTE IMMEDIATE $$` から `$$;` までは、途中で区切らず一括実行してください。

| 順番 | 確認 | 成功の目印 |
|---|---|---|
| 1 | 日次表全体 | 行数・リーチ・回数・時間・期間・ジャンル数が下表と一致 |
| 2 | 毎分表全体 | `MINUTE_MART_ROWS` と `DEVICE_MINUTE_BUCKETS` が下表と一致 |
| 3 | commonと5局合計 | 日次・毎分の照合がエラーなく終了 |
| 4 | 局別のRAWから集計まで | NW01〜NW05の5行。件数差0、分数差は許容誤差内 |
| 5 | 局・日別の分単位集計 | 観測分数、最初と最後の分、ピーク台数、端末分数を確認 |
| 6 | ラベル表と観測端末 | 2つの不一致件数がともに0 |

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

件数の `*_DIFFERENCE` は0であることを確認します。
FLOATの分数差は **`max(0.000001分, 比較元の分数の絶対値 × 0.000000001)` 以内**なら通過です。
`INVALID_ROWS` と `VALID_DUPLICATE_ROWS` はRAWから除く対象件数なので、0でなくても異常ではありません。
この確認SQLは保存済みデータを作成・変更しません。不一致やエラーがあれば第3章へ進まず、講師へ確認してください。

ここまで成功したら、[第3章 MLOps](03_mlops.md)へ進みます。

## 補足：仕組みを詳しく知りたい方へ

ここからは任意です。本編の操作後に読めば十分です。

### 加工内容と数え方

`CLEAN_VIEWING` は入力6列が完全一致する重複を除き、開始・終了があり、終了が開始より後、24時間以内の区間だけを残します。
配布RAW 1,050,648行から、完全重複300行、時刻逆転200行、24時間超148行を除き、1,050,000行になります。
同じイベントIDで内容が違う行は勝手に統合せず、一意性テストで検出します。

ジャンルは空白と指定表記を整え、`NEWS`、`DRAMA`、`VARIETY`、`ANIME`、`SPORTS`、`MUSIC`、`MOVIE`、`INFO` の8種類にそろえます。知らない値は置換せず、許容値テストで検出します。
RAWは変更せず、整形結果を別テーブルへ保存します。

`MART_DEVICE_DAILY` は、同じ局・端末・開始日・開始時ジャンルの記録をまとめます。
たとえばNEWSを10分と20分、SPORTSを15分見た1台は、NEWS 1行（2回・30分）とSPORTS 1行（1回・15分）になります。
表は2行、視聴回数は3回、端末は1台です。
1,050,000件は1,045,120行になりますが、`SESSION_COUNT` の合計は1,050,000回です。
区間全体を開始日・開始時ジャンルへ帰属させるため、番組別の正確な視聴時間ではありません。

`VIEWING_MINUTES` は、視聴区間と少しでも重なる1分枠へ展開します。開始は含み、終了は含みません。
08:00:50〜08:01:10は08:00と08:01の2行、08:01:00ちょうどに終了する場合は08:01の行を作りません。
`MART_MINUTE_AUDIENCE` は、同じ局・分の `DEVICE_ID` を重複なく数えます。瞬間同時視聴台数や視聴者数ではありません。
局をまたぐ重複は除かれないため、局別値の合計を全局の重複なし台数にはできません。観測のない局・分の行は作られません。
13,532,927は実視聴分数や全期間リーチではなく、局・端末・分の組の延べ数です。

総経過時間750,698,536秒を60で割ると約12,511,642.266667分です。
視聴時間はナノ秒差をFLOATへ変換して60,000,000,000.0で割るため、浮動小数点の微小誤差を考慮します。
`TIMESTAMP_NTZ` にタイムゾーン変換は加えません。

### 出力テーブルの粒度

dbtが作る22出力（各局4 × 5局 + common 2）は、すべて `materialized: table` のテーブルです。

| 出力 | 1行が表すもの |
|---|---|
| 各局の `CLEAN_VIEWING` | その局の視聴記録1件 |
| 各局の `MART_DEVICE_DAILY` | 局・端末・日付・ジャンルごとの集計 |
| 各局の `VIEWING_MINUTES` | 局・イベント・交差する分ごとの記録 |
| 各局の `MART_MINUTE_AUDIENCE` | 局・日付・分ごとの重複なし端末数 |
| `COMMON.VIEWING_DAILY` | 局別日次マートと同じ粒度 |
| `COMMON.MINUTE_AUDIENCE` | 局別分単位マートと同じ粒度 |

日次マートは `NETWORK_ID`、`DEVICE_ID`、`VIEW_DATE`、`GENRE`、`SESSION_COUNT`、`VIEW_MINUTES` の6列です。
第3章は日次実績から特徴量を作るため、分展開の全行をPythonへ持ち出す必要はありません。機械学習の正解ラベル・予測値はこのdbt処理に含みません。

### 81テストの内訳

各局の15テストは次のとおりです。複数列をまとめて調べるものも1テストと数えます。

| 対象 | テスト内容 |
|---|---|
| 整形後 | 必須列のNULL、イベントIDの局内一意性 |
| 整形後 | 端末IDが `C000001`〜`C020000`、局番号が自局だけ、ジャンルが8種類 |
| 整形後 | 正の24時間以内の区間で、分数計算が一致 |
| 日次マート | 必須列のNULL、局・端末・日付・ジャンルの一意性 |
| RAW・整形後・日次 | 有効記録の件数・分数と日次集計が一致 |
| 分展開 | 必須列のNULL、局・イベント・分の一意性 |
| 分展開 | 区間ごとの分数・境界・端末が一致 |
| 分単位マート | 必須列のNULL、局・日付・分の一意性 |
| 分単位マート | 分展開から数えた重複なし台数と一致 |

commonは日次・分単位の各マートについて、必須列のNULL、集計キーの一意性、局別マートとの合計一致を各3件、合計6件検査します。
**各局15件 × 5局 + common 6件 = 81テスト**です。同じ検査を局ごとに適用するため、81種類の別ルールではありません。

テストはデータの正しさをすべて保証しません。たとえば許可済みの `NEWS` を誤って `SPORTS` に変えても、許容値テストだけでは検出できません。
そのため、本編では期待件数・回数・時間も確認します。

### `ref()`、タグ、選択範囲

`ref()` は参照先のテーブル名と処理順をdbtへ伝えます。commonは5局の既存マートを `ref()` で読みますが、commonだけを選ぶため局別モデルは再実行しません。
common targetでも参照先は `BCAST_PLATFORM_HANDSON.NW01.MART_DEVICE_DAILY` などの局別スキーマです。

`--target` は実行先、`--select tag:...` は処理対象を選びます。`cautious` は、依存先がすべて選ばれた関連テストだけを自動選択します。
commonの件数テストは `common` タグで明示選択されます。`--select viewing_daily` だけでは件数テストが外れるため、代替にしません。
`--selector nw01` は教材では `--select tag:nw01 --indirect-selection cautious` と同じ選択ですが、`--target nw01` は別途必要です。

### 主なファイルと認証情報の注意

| ファイル | 役割 |
|---|---|
| [clean_viewing.sql](../dbt/macros/clean_viewing.sql) | 重複・不正区間の除去、ジャンル表記、分数計算 |
| [device_daily.sql](../dbt/macros/device_daily.sql) | 端末・日付・ジャンルごとの集計 |
| [viewing_minutes.sql](../dbt/macros/viewing_minutes.sql) | 分単位への展開と端末数集計 |
| [viewing_daily.sql](../dbt/models/common/viewing_daily.sql) | 5局の日次マートを `UNION ALL` |
| [minute_audience.sql](../dbt/models/common/minute_audience.sql) | 5局の分単位マートを `UNION ALL` |
| [profiles.yml](../dbt/profiles.yml) | targetごとの保存先・ロール・ウェアハウス |
| [assert_execution_scope.sql](../dbt/macros/assert_execution_scope.sql) | target・ロール・WH・選択範囲の不一致を拒否 |
| [models/schema.yml](../dbt/models/schema.yml) | 列説明と共通テスト |
| [tests/](../dbt/tests/) | 局別とcommonのSQLテスト |

`profiles.yml` の `account: ''` と `user: ''` は、Snowflake内で実行するため意図的に空欄です。
**パスワード・鍵・トークンを追記しないでください。** ローカルdbt Core用の接続設定ではありません。外部パッケージを使わないため `dbt deps` も不要です。
この教材は1つのdbtプロジェクトと6つのtargetで構成し、dbt Meshではありません。

### テストだけを再実行する場合

次はNW03とcommonの例です。既存テーブルを作り直さず検査します。commonのテストはcommon build後だけ実行します。

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

他局では `target` とタグの局番号をそろえて変えます。
テストだけ、または `run` だけの成功は、本編で求める `build` 成功の代わりにはなりません。
補助macroは指定間違いを検出しますが、アクセス制御や過去5回の成功管理を行うものではありません。

## 参考

画面や実行結果が手順と異なる場合は、設定を推測して変えず講師へ確認してください。

- [EXECUTE DBT PROJECT](https://docs.snowflake.com/en/sql-reference/sql/execute-dbt-project)
- [対応dbt Coreバージョン](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions)
