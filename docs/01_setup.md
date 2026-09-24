# 第1章 視聴データを取り込む準備

この章では、5局の視聴記録をSnowflakeへ取り込みます。
ファイルは用意してあるので、自分でデータを作る必要はありません。

まず演習用の保存先と計算環境を作り、GitHubの教材をSnowsightへ取り込みます。
その後、各局のデータを別々のテーブルへ読み込みます。

**この章のゴールは、8ファイルを取り込み、5局のRAWが合計1,050,648行、ラベルが20,000台分になっていることです。**
期間は2026年5月1日〜7月31日です。局によって行数は異なります。

## この章の進め方

1. [実行前の確認](#実行前の確認)で、演習用アカウント・権限・既存環境を確認します。
2. [GitHubで最初のSQLを開き](#1-最初のセットアップsqlを開く)、Snowsightに貼り付けます。GitHubリポジトリの新規作成は不要です。
3. [SQL内の第1〜5節を実行](#2-専用環境とgit接続を作る)します。第5節がSnowflakeのGit Repositoryを作成します。
4. 第5節の `LIST` が成功し、8個のParquetが見えたら、[Git Workspaceを作ります](#受講用git-workspaceを作る)。
5. Workspaceで [sql/01_02_load_parquet.sql](../sql/01_02_load_parquet.sql)を開き、[ファイル準備・取込](#3-parquetをrawテーブルへ読み込む)と[件数確認](#動作確認)を行います。

## まず、登場するものを整理する

| 言葉 | 何に使うもの？ |
|---|---|
| データベース（DB） | 教材のテーブルなどをまとめる入れ物 |
| スキーマ | DBの中を用途別に分ける区画。RAW、NW01、MLなど |
| テーブル | 行と列でデータを保存する表 |
| ウェアハウス（WH） | SQLの計算を担当する場所。データの保存先ではありません |
| ロール | 「作る」「読む」など、利用できる操作をまとめた権限 |
| 内部ステージ | Snowflake内のファイル置き場。テーブルへ読み込む前のファイルを置く場所 |
| Parquet（パーケ） | 列ごとにデータを保存するファイル形式。今回は内部をZSTD方式で圧縮済み |
| RAW（ロー） | 取り込んだ原本を残す場所。表記の揺れは次章で整えます |

ファイルを置くことと、テーブルへ読み込むことは別の操作です。
この章では、次の順でデータを移します。

```text
GitHubのmain → FETCH：Snowflake側のGitコピーを更新
       ↓ COPY FILES：指定した8ファイルを初回だけコピー
内部ステージの /F1_SIGNAL_V2/ → LIST：8ファイルを確認
       ↓ COPY INTO：1ファイルずつ、8本のSQLで読み込む
RAWの8テーブル → COUNT(*)：各表の行数を確認
```

### Gitの接続とWorkspaceはどう違う？

| 対象 | いつ作る？ | 役割 |
|---|---|---|
| GitHubリポジトリ | 配布元として作成済み。受講者の新規作成は不要 | 教材コードとデータの配布元 |
| Git API統合 `BCAST_PLATFORM_GIT_API` | `sql/01_01_setup.sql` 第3節 | この教材のGitHub URLへの接続を許可 |
| SnowflakeのGit Repository `BCAST_PLATFORM_REPO` | `sql/01_01_setup.sql` 第5節 | SQLから配布ファイルを参照し、データを取り込むための接続先 |
| 自分用のGit Workspace | 第5節の `LIST` 成功後、Snowsightで作成 | SQL・dbt・Notebook・アプリのファイルを開く作業場所 |

**SQLで接続先を作っても、Git Workspaceは自動作成されません。** `LIST` で8ファイルを確認してから、下記の画面操作へ進みます。

## 実行前の確認

- 講師が案内する演習用アカウントを使います。業務用アカウントでは実行しません。
- 初期準備には `ACCOUNTADMIN` が必要です。権限がない場合は管理者に準備を依頼します。
- 教材の環境名は固定です。1アカウントに1組を想定しています。
- 同じアカウントを複数人で使う場合は、役割と環境の分け方を講師へ確認します。

> 同名のDBが既にあっても、そのまま実行してよいとは限りません。
> この教材のものか分からない場合は、変更せず講師へ確認してください。
> 参加者ごとに独立した環境を作る場合、DB名だけでなく教材全体の命名調整が必要です。

### 既存の環境がある場合

新しい演習アカウントでは移行作業は不要です。
同名のDB・表・モデルなどが既にある場合は、セットアップやロードを始める前に講師へ確認してください。既存データを削除したり、別の版を混ぜたり、`cleanup.sql` で初期化したりしません。

## 1. 最初のセットアップSQLを開く

**まだGit Workspaceは不要です。**
次のリンクから、ブラウザーでGitHubのSQLを開きます。

[sql/01_01_setup.sql を開く](https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja/blob/main/sql/01_01_setup.sql)

講師から、このリンクの教材で開始してよいという案内を受けてから進めます。

1. GitHub上でSQLの内容をコピーします。必要に応じて **Raw** 表示を使います。
2. SnowsightのSQLワークシート、または既存の個人用Workspaceで、新しいSQLファイルを開きます。
3. コピーしたSQLを貼り付けます。
4. 演習用アカウントであることを確認し、次の説明に沿って第1〜5節を順に実行します。

ここでいう「節」は、SQLファイル内の `-- 1. ...` などの区切りです。
エラーが出たら、その後のSQLへ進まず、エラー文を講師へ伝えてください。

## 2. 専用環境とGit接続を作る

`01_01_setup.sql` には、次の処理が入っています。

| SQL内の節 | 実行すると何ができる？ | 確認すること |
|---|---|---|
| 1. 専用環境の準備 | 2ロール、教材DB、10スキーマ、6WH | 教材DBと局別・共通WHが作られる |
| 2. 権限 | エンジニア用の作成権限、アナリスト用の参照権限 | 権限付与のSQLにエラーがない |
| 3. Git API統合 | 教材のGitHub URLへ接続する許可 | `BCAST_PLATFORM_GIT_API` が作られる |
| 4. RAWとステージ | 空のRAWテーブル8個、内部ステージ、Parquetの読込設定 | この時点ではテーブルは空でよい |
| 5. 公開リポジトリ接続 | SnowflakeのGit Repositoryを作り、`FETCH` で配布元を取得 | 最後の `LIST` で `main` の `data/` に8個のParquetが見える |

`LIST` はファイルの一覧を表示するだけです。8個が見えても、まだテーブルへデータを読み込んだことにはなりません。取込は、この章の第3節で行います。

第4節の冒頭で、実行ロールを `BCAST_PLATFORM_ENGINEER_ROLE` へ切り替えます。
以降の演習は、この作成用ロールを使います。

### ロールの使い分け

| ロール | 担当する操作 |
|---|---|
| `ACCOUNTADMIN` | 最初の環境・権限・Git API統合の準備 |
| `BCAST_PLATFORM_ENGINEER_ROLE` | データ取込、dbt、学習、アプリ・Agentの作成 |
| `BCAST_PLATFORM_ANALYST_ROLE` | 共通集計や、後の章で共有するアプリ・Agentの利用 |

アナリストへRAW・局別・MLスキーマの直接参照権限は付けません。
アプリやAgentそのものの利用権限は、それぞれを作る章で追加します。

**SQLの `CURRENT_USER()` は「今SQLを実行している本人」です。**
管理者がこのSQLを実行しても、別の受講者へ教材ロールが自動で付くわけではありません。
別ユーザーで受講する場合は、管理者から本人へ教材ロールを付与してもらってください。

### 作成と初期化は別

`CREATE ... IF NOT EXISTS` は、「なければ作る」という意味です。
既存の中身を消して初期化したり、既存の定義を今回の定義にそろえたりする処理ではありません。

再実行時も、同名オブジェクトの用途・所有者・設定が教材用であることを確認します。
このSQLはユーザーの既定ロール・既定WHを変更しません。

## 受講用Git Workspaceを作る

**`sql/01_01_setup.sql` 第5節の `LIST` が成功し、8個のParquetを確認してから**、教材を操作するWorkspaceを作ります。`LIST` が失敗した場合は、ここへ進まず講師へ確認してください。

1. Snowsightで `BCAST_PLATFORM_ENGINEER_ROLE` を選びます。
2. **Projects → Workspaces → From Git repository** を開きます。新規作成メニュー内にある場合もあります。
3. 次の値を指定して、自分用のWorkspaceを作ります。

| 項目 | 指定する値 |
|---|---|
| リポジトリURL | `https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja.git` |
| API統合 | `BCAST_PLATFORM_GIT_API` |
| ブランチ | `main` |
| Workspace名 | `broadcast-data-platform-handson-ja` |
| Git用シークレット | 公開リポジトリなので不要 |

Workspaceのファイル一覧で、次が見えることを確認します。

- `README.md`：教材の入口。
- `dbt/dbt_project.yml`：第2章で使う設定。
- `notebooks/03_mlops.ipynb`：第3章で実行するNotebook。
- `data/`：8個のParquet。

ここから先は、このWorkspace内で教材やSQLを開きます。
Workspaceでは `main` の教材コードを使います。SQLのデータ取込元も、公開リポジトリの `main` にある `data/` です。
Workspaceだけを編集しても、SQLの取込元ファイルは更新されません。

Workspace名を別の名前にした場合は、第2章のSQL内のWorkspace名も合わせます。
古い教材に接続したWorkspaceを開いている場合は、新教材のWorkspaceへ切り替えてください。
必要な項目が選べない場合は、講師に画面を見せて確認します。

## 3. ParquetをRAWテーブルへ読み込む

Workspaceで [sql/01_02_load_parquet.sql](../sql/01_02_load_parquet.sql) を開きます。
**接続設定 → 初回のファイル準備 → 8本の `COPY INTO` → 件数確認の順に、1文ずつ実行します。**

### ① 接続先を確認する

冒頭の `USE ...` を実行し、演習用DB・エンジニアロール・共通WHを使います。

### ② 初回だけファイルを準備する

`FETCH` でSnowflake側のGitコピーを更新し、`COPY FILES` を実行します。取込元の `/branches/main/data/` は、公開リポジトリの `main` ブランチにある `data` フォルダです。
`FILES` に指定された次の8ファイルだけを、内部ステージ `BCAST_PLATFORM_RAW_STAGE` の `/F1_SIGNAL_V2/` へコピーします。

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

続く内部ステージの `LIST` で、この8ファイルを確認します。セットアップ時のGit側の一覧とは、確認先が異なります。
`COPY FILES` のコピー結果にも8ファイルがあることを確認してください。存在しないファイルがスキップされる場合があるため、以前のファイルがステージに見えるだけでは、今回の準備成功とは判断しません。

`F1_SIGNAL_V2` は今回のデータ版とコピー先フォルダの名前です。**演習中は配布元・ステージのファイルを変更しません。** 取得失敗やファイル不足なら、別の取込元へ切り替えず講師へ確認します。再実行時には、この準備を繰り返さず[再実行手順](#もう一度実行するとき)へ進みます。

### ③ 8本のCOPY INTOで読み込む

最初の1文は、NW01のファイルをNW01のRAWテーブルへ読み込みます。

```sql
COPY INTO BCAST_PLATFORM_HANDSON.RAW.VIEWING_LOG_NW01
FROM @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/
FILES = ('viewing_log_nw01.parquet')
FILE_FORMAT = (FORMAT_NAME = 'BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_PARQUET')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = ABORT_STATEMENT;
```

`FILES` は読むファイル、`MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` は大文字・小文字を区別せず列名で対応付ける指定です。列の並び順に合わせて読み替える必要はありません。
`ON_ERROR = ABORT_STATEMENT` は、読込エラーがあれば**その1文の取込を中止**します。8文全体を一括で成功・取消する指定ではなく、先に成功した別の `COPY INTO` の結果は残ります。

SQLファイルには、上表の8組それぞれの `COPY INTO` が明示されています。NW01の初回結果で `STATUS` が `LOADED`、`ROWS_LOADED` が195,938であることを確認し、残り7文も1文ずつ実行します。エラーが出たら後続を止め、[再実行手順](#もう一度実行するとき)を確認してください。
日時はParquetの論理型と、セットアップで作った `TIMESTAMP_NTZ` 列を使って読み込みます。8文が成功したら、次の件数確認へ進みます。

## 動作確認

ロードSQL末尾のSELECTを実行すると、RAWの8表を直接数えた結果が8行表示されます。`TABLE_NAME`が表名、`ROW_COUNT`が実際の行数、`EXPECTED_ROWS`が期待する行数です。各行の2つの件数が一致することを確認してください。

| `TABLE_NAME` | `ROW_COUNT` の期待値 |
|---|---|
| `VIEWING_LOG_NW01` | 195,938行 |
| `VIEWING_LOG_NW02` | 184,465行 |
| `VIEWING_LOG_NW03` | 179,991行 |
| `VIEWING_LOG_NW04` | 234,324行 |
| `VIEWING_LOG_NW05` | 255,930行 |
| `PROGRAM_MASTER` | 60行 |
| `PROGRAM_SCHEDULE` | 8,747行 |
| `DEVICE_LABELS` | 20,000行 |

5局のRAW合計は1,050,648行です。件数の一致だけで、データ内容が完全に同じとは判断できません。ラベルの内訳・ID・NULLは第3章で確認します。正解あり2,000台の内訳は在籍なし1,656台・在籍あり344台です。

8本の `COPY INTO` の成功と、自分の件数結果が上表に一致することを確認してください。
この結果になれば、第2章へ渡すデータの準備は完了です。
**ジャンルに空白や小文字が残っていても、この時点では正常です。** 次章で整えます。

## 配布データについて

### どんな視聴記録？

すべて架空のデータです。実在の放送局・人物・世帯・視聴率調査とは関係ありません。

- テレビは `C000001`〜`C020000` の20,000台。1台につき1つの合成世帯を割り当て、局をまたいでも同じIDは同じテレビを表します。
- 期間は2026年5月1日〜7月31日の92日間。各テレビに52回または53回の有効な視聴区間があります。毎日視聴する設定ではありません。
- 1行は「視聴開始から終了まで」の1区間です。視聴していない時間の行はありません。
- 有効な区間は局をまたいでも同じテレビで重なりません。RAWには検査用の完全重複300行、時刻逆転200行、24時間超148行を別途含めています。
- 日時は日本の時計時刻を想定しています。タイムゾーンを持たない `TIMESTAMP_NTZ` で保存し、UTCへ変換しません。

番組マスタと放送予定をもとに、世帯構成を考慮して生成した視聴ログです。実際の視聴履歴ではありません。
RAWの視聴記録は `EVENT_ID`、`NETWORK_ID`、`DEVICE_ID`、`VIEW_FROM`、`VIEW_TO`、`GENRE` の6列です。
ジャンルは視聴開始時の番組に対応します。番組をまたいでも、次章の日次集計は番組境界で時間を分割しません。
全局を通じて20,000台すべてに観測がありますが、局ごとの到達台数は同じとは限りません。実際の視聴率や市場規模を表すものではありません。

### 正解ラベルは何に使う？

`device_labels.parquet` は、第3章の機械学習で使う「答え合わせ用の表」です。
列は `DEVICE_ID`、`LABEL_AVAILABLE`、`TARGET_F1` の3つです。
`TARGET_F1` は「対応する合成世帯にF1（20〜34歳の女性）が在籍する」なら1、在籍しないなら0です。
期間中に変わらない世帯の設定であり、その時間に誰が見ていたか、何人いたかを示しません。

2,000台は正解があり、そのうち344台が1、1,656台が0です。
残り18,000台は `LABEL_AVAILABLE = FALSE`、`TARGET_F1 = NULL` です。
**不明を「在籍なし」の0へ変えてはいけません。** 世帯構成の詳細や不明分の隠れた正解は配布しません。
第3章では1つの分類モデル `TV_F1_PRESENCE_MODEL` を使います。実在する人物の属性を確認する教材ではありません。
この章では読み込むだけで、学習や予測は行いません。

## 必須Notebookの実行準備

第3章では、SQL用WHとは別に、Pythonを動かすための **compute pool（コンピュートプール）** を使います。
これはNotebookの計算環境です。第1章のSQLは、その作成や利用権限の付与を行いません。

講師が案内するpool・runtime（実行環境の種類）・パッケージを使います。設定の基準と版の確認方法は[第3章の「接続する環境」](03_mlops.md#接続する環境)にまとめています。
Notebookの接続画面で選べない場合は、第3章を始める前に講師へ確認してください。

第4章の推奨Streamlit手順はWHで動かす方式です。
そこでcompute poolが不要でも、**第3章のNotebookには別途必要**です。

## もう一度実行するとき

Snowflakeはテーブルごとに、ファイルのロード履歴を内部で保持します。**同じ変更されていないファイルを同じテーブルへ `COPY INTO` すると、ロード済みと判定できる間はスキップされ、行は追加されません。** 表の内容を毎回置き換える処理ではありません。

### 同じCOPYをもう一度試す

1. 同じ演習中で、ステージのファイルとRAWテーブルを変更していないことを確認します。
2. 接続設定を確認し、**`COPY INTO` だけ**を再実行します。`FETCH`・`COPY FILES` に戻りません。
3. 再取込の対象がない旨の結果と、8表の件数が増えていないことを確認します。

`COPY FILES` は初回の準備です。ファイルを再配置すると更新日時などのメタデータが変わり得るため、同じ `COPY INTO` の再実行を試す際には繰り返しません。

重複ロード防止に使う内部メタデータには**64日の有効期限**があります。古いファイルではロード状態を判定できず、既定でスキップされる場合もあります。永久的な重複防止や、データ版・全行の内容一致を保証する仕組みではありません。長期間経過後やデータ変更後は、この再実行手順を使わず講師へ確認します。

### 途中で失敗した場合

先に成功した `COPY INTO` のデータは残ります。エラー文とクエリ履歴を確認し、ファイル・RAWを変更しない同じ演習中に原因を解消できた場合は、**失敗した1文だけ**を再実行します。成功を確認してから未実行の文へ進み、最後に8表の件数を確認します。
ファイルの修正・再配置が必要な場合や件数が合わない場合は、そのまま進めず講師へ相談します。再試行のために `FORCE = TRUE` を追加したり、`TRUNCATE`・`DELETE` で既存行を消したりしません。ほかの人と同時にロードやデータ変更をしないでください。

Notebook開始後に入力データが変わった場合は、学習・保存を続けず講師へ確認します。第2章のマートを更新・確認した後、Notebookのカーネルを再起動して先頭から実行します。登録済みモデル版があれば、第3章に従い未使用の `V3` などを選びます。

## 補足：Parquetの読込設定

`BCAST_PLATFORM_PARQUET` は、Parquetファイルそのものではなく、**読み方を決める設定**です。

| 設定 | 役割 |
|---|---|
| `TYPE = PARQUET` | ファイルの種類を指定 |
| `COMPRESSION = AUTO` | Parquet内部の圧縮を自動検出 |
| `USE_LOGICAL_TYPE = TRUE` | 日時などの型情報を解釈 |
| `USE_VECTORIZED_SCANNER = TRUE` | Parquet用の読み取り方式を指定 |

圧縮はParquet内部のZSTDです。外側にgzipなどは重ねません。
読込設定に `COMPRESSION = ZSTD` と書き換える必要もありません。

入力日時はマイクロ秒単位の `timestamp[us]` です。
ロードSQLでは `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` で列名を対応付け、セットアップで定義した型の列へ読み込みます。
変換失敗をNULLへ隠す処理や、エラー行を読み飛ばす設定へは変更しないでください。

## 後片付け

**第2章へ進むときは、まだ後片付けを実行しません。**
教材が不要になったときにだけ、次を行います。

1. [第3章の停止手順](03_mlops.md#8-notebookの実行サービスを停止する)で、自分のNotebookサービスを停止します。
2. 必要な成果物を残し、同じ教材環境を使う人がいないか確認します。
3. 講師の案内に従い、[sql/cleanup.sql](../sql/cleanup.sql) を実行します。

このSQLは教材DB全体、6WH、Git API統合、2ロールを削除します。
DB内のモデル、予測、公開済みStreamlit、Agentも削除対象です。旧教材DBとWHは対象外です。

**Notebookサービスは個人用DB側にあり、教材DB削除やブラウザー終了だけでは止まりません。**
また、第4章の補足・経路Aで起動したWorkspaceの開発アプリも、別途停止します。
不要な教材専用アプリやソースを整理し、他の作業があるWorkspaceは削除しません。

共有・既定・システム管理のcompute poolは停止・削除しません。
別途用意した教材専用poolがある場合も、管理者に他の利用がないことを確認してもらいます。

## 次の章へ

取り込んだ原本を、[第2章 dbt](02_dbt.md)で分析しやすい形へ整えましょう。

画面や結果が手順と異なる場合は、設定を推測して変更せず講師へ確認してください。

## 公式資料

- [CREATE FILE FORMAT：Parquetの設定](https://docs.snowflake.com/en/sql-reference/sql/create-file-format#type--parquet)
- [COPY FILES：ファイルのコピー](https://docs.snowflake.com/en/sql-reference/sql/copy-files)
- [COPY INTO：列名の対応付けとON_ERROR](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table#copy-options-copyoptions)
- [ロード履歴による重複防止と64日の有効期限](https://docs.snowflake.com/en/user-guide/data-load-considerations-load#load-metadata)