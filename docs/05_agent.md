# 第5章 セマンティックビューと Agent

数値の意味を `MART.SV_VIEWING` に定義し、それを唯一の Analyst ツールとして GUI で Agent を作ります。ML の予測テーブルと検索サービスは前提にしません。作成先はすべて **BCAST_PLATFORM_HANDSON** です。Semantic View集計とAgentのSQL作成はトライアルで確認済みですが、GUI操作・CoWorkへの公開と質問は未確認です。

## 1. 前提を確認

- 第2章の `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY` が完成していること。第3章の推論・第4章のアプリ作成は Agent の必須依存ではありません。
- `BCAST_PLATFORM_ENGINEER_ROLE` が MART に CREATE SEMANTIC VIEW と CREATE AGENT、共通マートに SELECT、対象 DB・スキーマと `BCAST_PLATFORM_COMMON_WH` に USAGE を持つこと。第1章で準備します。
- `BCAST_PLATFORM_ANALYST_ROLE` の DB・MART・COMMON の USAGE、共通マートの SELECT、共通 warehouse の USAGE を第1章で確認します。セマンティックビューの SELECT／REFERENCES と Agent の USAGE はこの章で対象オブジェクトだけに付与します。
- Cortex／Agent 利用に必要なアカウント側のロール・権限・モデル利用可否は、講師が [公式セットアップ](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup) と第1章で確認します。この章ではアカウント全体の設定変更・SNOWFLAKE データベースロール付与・ユーザーの既定値変更をしません。

### 初回呼び出し前の停止点（Playground／CoWork共通）

Agent を作成しても、以下を確認するまでは質問を送信しません。エラーが起きてから調べる項目ではなく、作成者・共有先の利用者それぞれの事前確認です。

1. 講師が利用者の **DEFAULT_ROLE と DEFAULT_WAREHOUSE** を確認します。画面の現在ロール／warehouse とユーザーの既定値を混同しません。第1章は既定値を設定しないため、準備SQLの完了だけではこの確認の代わりになりません。
2. 既定ロールが必要な教材ロールの権限を直接持つか、ロール階層を通じて継承することを確認します。ユーザーに教材ロールが付与されているだけでは、別の既定ロールがその権限を継承するとは限りません。Agent の USAGE、SV_VIEWING の SELECT／REFERENCES、参照データ・DB・スキーマ・Cortex の必要権限を、作成後の個別 GRANT も含めて確認します。管理者ロールの成功を閲覧者の権限確認の代わりにしません。
3. 既定 warehouse が設定され、存在し、既定ロールから USAGE を利用できることを確認します。あわせて Analyst ツールが使う `BCAST_PLATFORM_COMMON_WH` の USAGE も確認します。ツールに共通WHを指定したことだけでは、利用者の既定 warehouse の要件を満たしません。
4. いずれかが未確認・不足なら初回呼び出し前に停止し、アカウント管理者へ確認します。現在ロールの切替だけで解決したとはみなさず、ユーザーの既定値やロール階層を自動変更しません。本教材から `ALTER USER` は行いません。変更が必要な場合は、管理者が既存利用への影響を確認し、別の承認済み手順で対応してから再確認します。

## 2. セマンティックビューを作成

Snowsight の SQL エディタで `sql/04_semantic.sql` を開き、対象が新教材 DB であることを確認して実行します。既存の同名ビューは自動上書きしないため、再実行時の「既に存在」は定義確認のための停止です。勝手に DROP や OR REPLACE を足さないでください。

定義は論理テーブル `viewing` 1つ、ディメンション `view_date`・`network_id`・`genre`、メトリック `distinct_reach`・`total_minutes`・`total_sessions` です。物理参照先は COMMON.VIEWING_DAILY だけです。

- `distinct_reach`: `COUNT(DISTINCT DEVICE_ID)`。期間・局・ジャンルをまたいで重複を除いた端末数です。
- `total_minutes`: `SUM(VIEW_MINUTES)`。単位は分です。
- `total_sessions`: `SUM(SESSION_COUNT)`。マートの行数ではありません。

ビューの末尾の2つの読み取り SQL で、同期間の semantic query と元テーブル集計を比較します。リーチと回数は一致、FLOAT の分数は端数誤差を考慮して比較します。この比較を実施して初めて「確認済み」と記録してください。ローカルテストの合格を実環境での一致と呼びません。未検証の質問を VQR として登録していません。

## 3. GUIで Agentを作成

**ここがGUIチェックポイントです。`sql/05_agent.sql` を全選択実行せず、Agent の作成・設定・保存を終えてから SHOW／DESCRIBE／GRANT に進みます。**

1. Snowsight の AI & ML → Agents → Create agent を開きます。作成ロールを `BCAST_PLATFORM_ENGINEER_ROLE` にします。
2. Database `BCAST_PLATFORM_HANDSON`、Schema `MART`、Agent object name `VIEWING_AGENT`、Display name `5局共通の視聴データ分析` を指定して作成します。同名の既存 Agent があれば上書きせず確認します。
3. Edit／About で [貼り付け文章](agent_texts.md) の説明と3つの質問例を入力します。
4. Tools → Cortex Analyst → Add で Semantic view を選び、`BCAST_PLATFORM_HANDSON.MART.SV_VIEWING` を指定します。ツール名は **SV_VIEWING**、Warehouse は **BCAST_PLATFORM_COMMON_WH**、Query timeout (seconds) は **120**、説明は貼り付け文章の該当箇所です。名前がビュー名から自動設定される UI でも SV_VIEWING になっていることを確認します。
5. ツールはこの1つだけにします。Cortex Search、Analytical Search、Code execution、Data to Chart、Web search、Custom tools、MCP を追加・有効化しません。ML.PREDICTIONS も接続しません。
6. Orchestration model は **Auto** を選び、Planning／Orchestration instructions と Response instructions を貼り付けます。Auto は Snowflake によるモデル自動選択であり、特定モデルの固定・品質保証ではありません。
7. Save で保存します。UI に Publish／公開／バージョン選択がある場合は、意図した設定の版を確認して公開します。Save だけで公開済みとは断定しません。公開操作がない UI では、詳細画面を開き直して保存結果を確認します。質問の送信は、第4節の共有と第1節の初回呼び出し前チェックを終えてから第5節で行います。

Query timeout の120秒は **Analyst が実行する1つのクエリの待ち時間設定** です。Agent 全体の orchestration budget とは別です。本教材は budget の値を明示指定していません。UI の既定値がフォールバック SQL と同じとは限らないので、講師が記録して比較してください。ツール名、タイムアウト、Auto の表示・保存・公開・デフォルト機能は UI の展開状況による差分確認が必要です。

## 4. 作成後の確認と共有

`sql/05_agent.sql` の GUI チェックポイントより後の SHOW と DESCRIBE を実行し、`BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT` が存在することを確認します。詳細画面でも、ツールが SV_VIEWING だけで、指示・warehouse・timeout が保存されたことを確認します。その後、この新 Agent の USAGE を `BCAST_PLATFORM_ANALYST_ROLE` に付与する GRANT を実行します。ENGINEER は作成者として所有しているため、同じ役割への USAGE 再付与は不要です。

CoWork（Snowflake Intelligence と表示される環境もあります）で Agent の一覧・選択画面から表示名を探します。入口は [ai.snowflake.com](https://ai.snowflake.com/) またはアカウント内の CoWork です。利用者が必要なロールとツールへの権限を持ち、公開対象の版が反映されていることを確認します。

一覧に表示されても呼び出し成功の証明にはなりません。質問を送信する前に第1節の停止点を共有先の利用者でも確認します。現行の Agent 管理ドキュメントが説明する既定ロール・既定 warehouse の要件と、今回付与した権限の継承を照合してください。既存の Snowflake Intelligence オブジェクトへの登録が必要な旧構成もあり得ますが、既存設定を自動変更せず、アカウント管理者に確認します。

## 5. 動作を確認

1. 第1節の初回呼び出し前チェックと第4節の共有確認が完了していることを確認してから、貼り付け文章の全5局・全期間の質問を実行し、生成 SQL・実行結果を確認します。第2節の直接 SQL と、期間・局条件を合わせて比較します。
2. 局別リーチを聞いた後、全局合計のリーチを聞きます。局別の値を足さず、端末IDの DISTINCT を範囲全体で再計算することを確認します。
3. 日別推移と期間全体のリーチを別々に質問し、日別の合計を期間リーチにしないことを確認します。日付フィルターが semantic query の集計前に適用されていることも確認します。
4. 「2026年7月1日から30日のスポーツ関心あり予測の端末数」を質問し、予測は対象外と説明することを確認します。SPORTS の視聴実績を予測値の代わりに出してはいけません。
5. データ範囲外の2026年8月を指定し、7月に勝手に置換せず該当データなしと説明することを確認します。ツール実行エラーをゼロ件と説明しないことも確認します。

Playground と CoWork の両方を、共有先ロールの利用者でも確認してください。文章の指示はアクセス制御でも完全な挙動保証でもありません。実行された SQL と結果を確認するチェックが必要です。

## GUIが使えない場合のSQL

まだ Agent を作成していない場合だけ `sql/05_agent.sql` 末尾の `/* ... */` 内の CREATE AGENT 文を選択実行します。コメントの囲み自体は選択範囲に含めません。同名 Agent があると停止する新規作成用の文です。GUI の設定を上書きする手順ではありません。

名前・説明・指示・質問例・単一ツール・参照ビュー・共通 warehouse・query_timeout=120・Auto を GUI 用文章に合わせています。**同じ意図の設定を記述したもので、GUI経由とSQL経由の作成・保存・公開・実行結果の同等性を検証したものではありません。** SQL を実行した後も第4・5節の GUI 確認を省略しないでください。

## 未検証事項と参照

GUIの配置・保存・公開、CoWorkの一覧反映と質問結果は実施環境で確認してください。SQLで作成できることと、GUI経路や自然言語の回答まで確認できたことは別です。

- [CREATE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [CREATE AGENT](https://docs.snowflake.com/en/sql-reference/sql/create-agent)
- [AgentのGUI管理](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)
- [Agent仕様とExecutionEnvironment](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api)
- [Agentのアクセス設定](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup)