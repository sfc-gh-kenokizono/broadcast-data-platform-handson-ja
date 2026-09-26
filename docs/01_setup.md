# 第1章 視聴データを取り込む

この章では、演習環境を作り、GitHubの8個のParquetをSnowflakeへ取り込みます。

**完了条件は、8本の `COPY INTO` が成功し、RAW 8表の件数が期待値と一致することです。** 5局のRAW合計は1,050,648行、ラベルは20,000台分です。値・重複・不正区間は後の章で検証します。

## 最初に全体を確認

| どこで開く？ | 何をする？ | 成功の目印 |
|---|---|---|
| GitHubの [sql/01_01_setup.sql](https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja/blob/main/sql/01_01_setup.sql) → Snowsight | SQLを貼り付け、第1〜5節を順に実行 | 第5節の `LIST` で8個のParquetが見える |
| Snowsightの **Projects → Workspaces → From Git repository** | `main` から自分用Git Workspaceを作る | `README.md`、`dbt/`、`notebooks/`、`data/` が見える |
| Workspaceの [sql/01_02_load_parquet.sql](../sql/01_02_load_parquet.sql) | `FETCH`、`COPY FILES`、内部ステージの `LIST` を実行 | コピー結果と `LIST` で指定した8ファイルを確認 |
| 同じSQLファイル | 8本の `COPY INTO` を1文ずつ実行 | 各文が成功。NW01は `STATUS = LOADED`、`ROWS_LOADED = 195,938` |
| 同じSQLファイル末尾 | 件数確認のSELECTを実行 | 8表すべてで `ROW_COUNT = EXPECTED_ROWS` |

```text
GitHubのmain → FETCH → COPY FILES → 内部ステージの8ファイル
                                      ↓ 8本のCOPY INTO
                                  RAWの8テーブル
                                      ↓ COUNT(*)
                                    件数確認
```

`FETCH` はSnowflake側のGitコピーを更新します。`COPY FILES` は8ファイルを内部ステージへ置き、`COPY INTO` は各ファイルをテーブルへ読み込みます。Git RepositoryはSQLから配布ファイルを参照する接続先、Git Workspaceは教材ファイルを開く自分用の作業場所です。

## 実行前の確認

- 講師が案内する演習用アカウントを使います。業務用アカウントでは実行しません。
- 初期準備には `ACCOUNTADMIN` が必要です。権限がない場合は管理者に依頼します。
- 教材の固定名環境は1アカウントに1組を想定しています。同じアカウントを複数人で使う場合は講師へ確認します。
- 同名のDB・表・モデルなどがある場合は、セットアップやロードを始める前に講師へ確認します。

同名オブジェクトがこの教材のものか分からない場合は変更しません。既存データの削除、別版との混在、`cleanup.sql` による初期化は行わないでください。参加者ごとに独立した環境を作るには、DB名だけでなく教材全体の命名調整が必要です。

## 1. セットアップSQLを実行

この時点ではGit Workspaceは不要です。

1. GitHubで [sql/01_01_setup.sql](https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja/blob/main/sql/01_01_setup.sql) を開き、必要に応じて **Raw** 表示から内容をコピーします。
2. SnowsightのSQLワークシート、または既存の個人用Workspaceで新しいSQLファイルを開き、貼り付けます。
3. 演習用アカウントであることを確認します。
4. SQL内の `-- 1. ...` から `-- 5. ...` まで、節ごとに順番に実行します。
5. エラーが出たら後続を実行せず、エラー文を講師へ伝えます。

| SQL内の節 | 作られるもの | 成功の目印 |
|---|---|---|
| 1. 専用環境の準備 | 2ロール、教材DB、10スキーマ、6WH | 教材DBと局別・共通WHが作られる |
| 2. 権限 | エンジニア用の作成権限、アナリスト用の参照権限 | 権限付与にエラーがない |
| 3. Git API統合 | `BCAST_PLATFORM_GIT_API` | 統合が作られる |
| 4. RAWとステージ | 空のRAWテーブル8個、内部ステージ、Parquet読込設定 | この時点でテーブルは空でよい |
| 5. 公開リポジトリ接続 | `BCAST_PLATFORM_REPO` と `FETCH` | 最後の `LIST` で `main` の `data/` に8個のParquetが見える |

第4節の冒頭で `BCAST_PLATFORM_ENGINEER_ROLE` へ切り替え、以降の演習でも使います。`ACCOUNTADMIN` は最初の環境・権限・Git API統合、`BCAST_PLATFORM_ANALYST_ROLE` は共通集計や後の章で共有するアプリ・Agentの利用に使います。アナリストへRAW・局別・MLスキーマの直接参照権限は付けません。

`CURRENT_USER()` はSQLを実行している本人です。管理者が実行しても、別の受講者へ教材ロールは自動付与されません。別ユーザーで受講する場合は、管理者から本人へ教材ロールを付与してもらいます。

`CREATE ... IF NOT EXISTS` は、同名オブジェクトがなければ作る指定です。既存の中身を消したり、定義を教材に合わせたりはしません。再実行前にも用途・所有者・設定が教材用であることを確認してください。このSQLはユーザーの既定ロール・既定WHを変更しません。

最後の `LIST` はGit側のファイル一覧を表示するだけです。8個が見えても、まだ内部ステージへのコピーやテーブルへのロードは終わっていません。

## 受講用Git Workspaceを作る

**セットアップSQL第5節の `LIST` が成功し、8個のParquetを確認してから進みます。** 失敗した場合は講師へ確認します。

1. Snowsightで `BCAST_PLATFORM_ENGINEER_ROLE` を選びます。
2. **Projects → Workspaces → From Git repository** を開きます。新規作成メニュー内にある場合もあります。
3. 次の値を指定して、自分用Workspaceを作ります。

| 項目 | 指定する値 |
|---|---|
| リポジトリURL | `https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja.git` |
| API統合 | `BCAST_PLATFORM_GIT_API` |
| ブランチ | `main` |
| Workspace名 | `broadcast-data-platform-handson-ja` |
| Git用シークレット | 公開リポジトリなので不要 |

ファイル一覧で `README.md`、`dbt/dbt_project.yml`、`notebooks/03_mlops.ipynb`、8個のParquetがある `data/` を確認します。ここから先は、このWorkspaceで教材とSQLを開きます。

Workspace名を変えた場合は、第2章のSQL内のWorkspace名も合わせます。古い教材に接続したWorkspaceではなく、新教材の `main` を使ってください。Workspace内のファイルを編集しても、SQLが参照するSnowflakeのGit Repositoryは自動更新されません。必要な項目が選べない場合は講師へ確認します。

## 3. COPY FILESで8ファイルを準備

Workspaceで [sql/01_02_load_parquet.sql](../sql/01_02_load_parquet.sql) を開き、**接続設定 → `FETCH` → `COPY FILES` → 内部ステージの `LIST`** の順に1文ずつ実行します。

冒頭の `USE ...` で、演習用DB、`BCAST_PLATFORM_ENGINEER_ROLE`、共通WHを選びます。`FETCH` の後、`COPY FILES` は `/branches/main/data/` の次の8ファイルだけを、`BCAST_PLATFORM_RAW_STAGE` の `/F1_SIGNAL_V2/` へコピーします。

| ファイル | 読み込むRAWテーブル |
|---|---|
| `viewing_log_nw01.parquet` | `VIEWING_LOG_NW01` |
| `viewing_log_nw02.parquet` | `VIEWING_LOG_NW02` |
| `viewing_log_nw03.parquet` | `VIEWING_LOG_NW03` |
| `viewing_log_nw04.parquet` | `VIEWING_LOG_NW04` |
| `viewing_log_nw05.parquet` | `VIEWING_LOG_NW05` |
| `program_master.parquet` | `PROGRAM_MASTER` |
| `program_schedule.parquet` | `PROGRAM_SCHEDULE` |
| `device_labels.parquet` | `DEVICE_LABELS` |

`COPY FILES` のコピー結果に8ファイルがあることと、続く内部ステージの `LIST` で同じ8ファイルが見えることを確認します。存在しないファイルはスキップされる場合があるため、以前のファイルがステージに見えるだけでは今回の準備成功とは判断しません。

`F1_SIGNAL_V2` はデータ版とコピー先フォルダの名前です。演習中は配布元・ステージのファイルを変更しません。取得失敗や不足があれば、別の取込元へ切り替えず講師へ確認します。再実行時は `FETCH`・`COPY FILES` に戻らず、[もう一度実行するとき](#もう一度実行するとき)へ進みます。

## 4. 8本のCOPY INTOを実行

SQLファイルの8本の `COPY INTO` を、上表の順に1文ずつ実行します。最初の文は次のNW01用です。

```sql
COPY INTO BCAST_PLATFORM_HANDSON.RAW.VIEWING_LOG_NW01
FROM @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/
FILES = ('viewing_log_nw01.parquet')
FILE_FORMAT = (FORMAT_NAME = 'BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_PARQUET')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = ABORT_STATEMENT;
```

NW01の初回結果で `STATUS` が `LOADED`、`ROWS_LOADED` が195,938であることを確認してから、残り7文を実行します。

- `FILES` は読み込む1ファイルを指定します。
- `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` は、大文字・小文字を区別せず列名で対応付けます。
- `ON_ERROR = ABORT_STATEMENT` は、エラーがあったその1文だけを中止します。先に成功した別の `COPY INTO` の結果は残ります。
- 日時はParquetの論理型と、セットアップで作った `TIMESTAMP_NTZ` 列を使います。

エラーが出たら後続を止め、[途中で失敗した場合](#途中で失敗した場合)に従います。8文が成功したら件数確認へ進みます。

## 5. 件数を確認

ロードSQL末尾のSELECTを実行します。8行の結果で、すべての `ROW_COUNT` が `EXPECTED_ROWS` と一致することを確認します。

| `TABLE_NAME` | `ROW_COUNT` の期待値 |
|---|---:|
| `VIEWING_LOG_NW01` | 195,938行 |
| `VIEWING_LOG_NW02` | 184,465行 |
| `VIEWING_LOG_NW03` | 179,991行 |
| `VIEWING_LOG_NW04` | 234,324行 |
| `VIEWING_LOG_NW05` | 255,930行 |
| `PROGRAM_MASTER` | 60行 |
| `PROGRAM_SCHEDULE` | 8,747行 |
| `DEVICE_LABELS` | 20,000行 |

5局のRAW合計は1,050,648行です。番組マスタ60行は、5局それぞれに12種類、合計60種類の番組タイプを定義したものです。放送予定8,747行は、その番組タイプを3か月の各放送枠へ繰り返し割り当てたものです。

**8本の `COPY INTO` が成功し、上の期待件数と一致すれば、この章のロードは完了です。** 第2章以降で値、重複、不正区間、ラベルの内訳を検証します。ジャンルに空白や小文字が残っていても、この時点では正常です。

正解あり2,000台の内訳は在籍あり344台、在籍なし1,656台です。残り18,000台は `LABEL_AVAILABLE = FALSE`、`TARGET_F1 = NULL` で、不明を0へ変更しません。

## 配布データの要点

すべて架空のデータで、実在の放送局・人物・世帯・視聴率調査とは関係ありません。

- 期間は2026年5月1日〜7月31日の92日間です。
- テレビは `C000001`〜`C020000` の20,000台です。同じIDは局をまたいでも同じテレビを表します。
- 1行は視聴開始から終了までの1区間です。各テレビに52回または53回の有効区間があり、毎日視聴する設定ではありません。
- RAWには検査用の完全重複300行、時刻逆転200行、24時間超148行を含みます。
- 日時は日本の時計時刻を想定し、`TIMESTAMP_NTZ` で保存します。UTCへ変換しません。
- 視聴記録は `EVENT_ID`、`NETWORK_ID`、`DEVICE_ID`、`VIEW_FROM`、`VIEW_TO`、`GENRE` の6列です。
- ジャンルは視聴開始時の番組です。次章の日次集計は番組境界で時間を分割しません。
- 全20,000台に観測がありますが、局ごとの到達台数は同じとは限りません。実際の視聴率や市場規模を表しません。

`device_labels.parquet` は第3章の答え合わせ用で、`DEVICE_ID`、`LABEL_AVAILABLE`、`TARGET_F1` の3列です。`TARGET_F1 = 1` は、対応する合成世帯にF1（20〜34歳の女性）が在籍する設定を表し、その時間に誰が見ていたかや人数は示しません。第3章では分類モデル `TV_F1_PRESENCE_MODEL` を使います。

## 第3章のNotebook準備

第3章のPython実行には、SQL用WHとは別にcompute poolが必要です。第1章のSQLはpoolの作成や権限付与を行いません。講師が案内するpool・runtime・パッケージを使い、選べない場合は第3章を始める前に確認してください。基準は[第3章の「1. Notebookを接続する」](03_mlops.md#1-notebookを接続する)にあります。

第4章の推奨Streamlit手順はWHで動きますが、第3章のNotebookにはcompute poolが必要です。

## もう一度実行するとき

Snowflakeはテーブルごとにファイルのロード履歴を保持します。同じ変更されていないファイルを同じテーブルへ `COPY INTO` すると、ロード済みと判定できる間はスキップされ、行は追加されません。表全体を置き換える処理ではありません。

### 同じCOPYをもう一度試す

1. 同じ演習中で、ステージのファイルとRAWテーブルを変更していないことを確認します。
2. 接続設定を確認し、**対象の `COPY INTO` だけ**を再実行します。`FETCH`・`COPY FILES` は繰り返しません。
3. 再取込対象がない結果と、8表の件数が増えていないことを確認します。

ロード履歴には**64日の有効期限**があります。古いファイルではロード状態を判定できず、既定でスキップされる場合もあります。永久的な重複防止や全行一致の保証ではないため、長期間経過後やデータ変更後は再実行せず講師へ確認します。

### 途中で失敗した場合

先に成功した `COPY INTO` のデータは残ります。エラー文とクエリ履歴を確認し、ファイル・RAWを変更していない同じ演習中に原因を解消できた場合は、**失敗した1文だけ**を再実行します。成功後に未実行の文へ進み、最後に8表の件数を確認します。

ファイルの修正・再配置が必要な場合や件数が合わない場合は、そのまま進めず講師へ相談します。`FORCE = TRUE` の追加、`TRUNCATE`、`DELETE` でのやり直しは行いません。ほかの人と同時にロードやデータ変更もしないでください。

Notebook開始後に入力データが変わった場合は学習・保存を止めます。第2章のマートを更新・確認し、Notebookのカーネルを再起動して先頭から実行します。登録済みモデル版がある場合は、第3章に従い未使用の `V4` などを選びます。

## 補足：Parquetの読込設定

`BCAST_PLATFORM_PARQUET` はファイルではなく、読み方の設定です。

| 設定 | 役割 |
|---|---|
| `TYPE = PARQUET` | ファイル形式を指定 |
| `COMPRESSION = AUTO` | Parquet内部の圧縮を自動検出 |
| `USE_LOGICAL_TYPE = TRUE` | 日時などの型情報を解釈 |
| `USE_VECTORIZED_SCANNER = TRUE` | Parquet用の読み取り方式を指定 |

圧縮はParquet内部のZSTDで、外側にgzipなどは重ねません。`COMPRESSION = ZSTD` への書き換えも不要です。入力日時はマイクロ秒単位の `timestamp[us]` です。変換失敗をNULLへ隠す処理や、エラー行を読み飛ばす設定へ変更しないでください。

## 後片付け

**第2章へ進むときは、まだ後片付けを実行しません。** 教材が不要になったときだけ、次を行います。

1. [第3章の停止手順](03_mlops.md#7-notebookサービスを停止する)で自分のNotebookサービスを停止します。
2. 必要な成果物を残し、同じ教材環境を使う人がいないか確認します。
3. 講師の案内に従い、[sql/cleanup.sql](../sql/cleanup.sql) を実行します。

`cleanup.sql` は教材DB全体、6WH、Git API統合、2ロールを削除し、DB内のモデル、予測、公開済みStreamlit、Agentも削除します。旧教材DBとWHは対象外です。

Notebookサービスは個人用DB側にあり、教材DB削除やブラウザー終了だけでは止まりません。第4章の補足・経路Aで起動したWorkspaceの開発アプリも別途停止します。不要な教材専用アプリやソースを整理し、他の作業があるWorkspaceは削除しません。共有・既定・システム管理のcompute poolは停止・削除しません。教材専用poolも、管理者が他の利用がないことを確認してから扱います。

## 次の章へ

取り込んだ原本を、[第2章 dbt](02_dbt.md)で分析しやすい形へ整えます。画面や結果が手順と異なる場合は、設定を推測して変更せず講師へ確認してください。

## 公式資料

- [CREATE FILE FORMAT：Parquetの設定](https://docs.snowflake.com/en/sql-reference/sql/create-file-format#type--parquet)
- [COPY FILES：ファイルのコピー](https://docs.snowflake.com/en/sql-reference/sql/copy-files)
- [COPY INTO：列名の対応付けとON_ERROR](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table#copy-options-copyoptions)
- [ロード履歴による重複防止と64日の有効期限](https://docs.snowflake.com/en/user-guide/data-load-considerations-load#load-metadata)