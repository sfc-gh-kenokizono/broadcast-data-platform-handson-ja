# 第5章 視聴実績を日本語で質問する

この章では、視聴実績の指標をSemantic Viewに定義し、その定義だけを使うAgentをGUIで作ります。最後にPreviewとCoWorkで、直接SQLと同じ結果になることを確認します。

**このAgentは合成視聴実績専用です。第3章のF1在籍予測や文章検索は接続しません。**

## 完了までの流れ

| どこ | 操作 | 成功 |
|---|---|---|
| Git Workspace | `sql/05_01_semantic.sql` を順番に実行 | Semantic Viewと直接SQLの3指標が一致する |
| SnowsightのAgents | 現行UIの「一般・手順・ツール」に沿って`agent_texts.md`の値を入力 | `SV_VIEWING`だけを持つAgentが保存・公開される |
| Git Workspace | `sql/05_02_agent.sql`の`SHOW`、`DESCRIBE`、`GRANT`を実行 | 設定を確認でき、分析ロールへ共有される |
| AgentのPreview | 4つの検証質問を送る | 数値、生成SQL、対象外・データなしの応答が正しい |
| CoWork | 同じAgentで代表質問を送る | 共有先の利用者も同じ条件の回答を得られる |

```text
質問 → VIEWING_AGENT → Cortex Analyst（SV_VIEWING）
     → Semantic View → COMMON.VIEWING_DAILY
```

## 1. 質問前の前提を確認する

第2章の `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY` が完成していることが前提です。第3章の予測と第4章のアプリは前提ではありません。

| どこ | 操作 | 成功 |
|---|---|---|
| Snowsightの利用者設定 | 作成者と共有先利用者の`DEFAULT_ROLE`を確認 | Agent、Semantic View、参照データの権限を持つロール、または継承元ロールになっている |
| Snowsightの利用者設定 | `DEFAULT_WAREHOUSE`を確認 | 実在し、既定ロールから利用できる |
| Worksheets | `BCAST_PLATFORM_COMMON_WH`の利用可否を確認 | 作成者と共有先の必要ロールで利用できる |
| アカウント・リージョン | Cortex、Agent、必要なモデルの利用可否を講師・管理者が確認 | 利用可能と確認される |

確認が終わるまでPreviewやCoWorkへ質問を送信しません。第1章のSQLはユーザーの既定値を変更しません。権限不足を管理者ロールへの切替で回避せず、管理者に依頼します。本教材から`ALTER USER`は実行しません。

## 2. Semantic Viewを作り、直接SQLと比較する

Semantic Viewは、切り口と指標の計算ルールを定義します。元データは `COMMON.VIEWING_DAILY` だけです。

| 指標 | 定義 |
|---|---|
| `distinct_reach` | 対象範囲全体で`DEVICE_ID`の重複を除いた端末数。人数・世帯数ではない |
| `total_minutes` | `VIEW_MINUTES`の合計。単位は分 |
| `total_sessions` | `SESSION_COUNT`の合計。行数ではない |

日付、放送局、ジャンルが切り口です。教材期間は2026年5月1日から7月31日、局は`NW01`から`NW05`、ジャンルはNEWS、DRAMA、VARIETY、ANIME、SPORTS、MUSIC、MOVIE、INFOの8種類です。視聴時間は区間全体を開始日・開始時のジャンルへ計上するため、番組単位の正確な視聴時間ではありません。

| どこ | 操作 | 成功 |
|---|---|---|
| Git Workspace | [sql/05_01_semantic.sql](../sql/05_01_semantic.sql)を開く | 作成先が`BCAST_PLATFORM_HANDSON.MART.SV_VIEWING`である |
| 同SQL | `USE`、`CREATE SEMANTIC VIEW`、`GRANT`、`DESCRIBE`を順番に実行 | 3つの切り口、3指標、参照先を確認できる |
| 同SQL末尾 | Semantic ViewのSELECTを実行 | 全期間・全5局の3指標が1行で返る |
| 同SQL末尾 | 元テーブルの直接SQLを実行 | 対応する3指標がSemantic Viewの結果と一致する |

直接SQLの期待値は、リーチ20,000台、総視聴回数1,050,000回、総視聴時間約12,511,642.266667分です。小数の丸めだけで不一致と判断しません。結果と条件を、後のAgent検証の基準として残します。

同名ビューがある場合は停止し、`DROP`や`OR REPLACE`を追加せず講師へ確認します。不一致ならAgent作成へ進みません。

## 3. GUIでAgentを作る

`sql/05_02_agent.sql`はまだ全選択実行しません。先にGUIで作成・保存します。

### 3-1. Agentを作成する

| どこ | 操作 | 成功 |
|---|---|---|
| **AI & ML → Agents → Create agent** | 作成ロールを`BCAST_PLATFORM_ENGINEER_ROLE`にする | 教材用ロールが選択される |
| 作成画面 | Database=`BCAST_PLATFORM_HANDSON`、Schema=`MART`、Agent object name=`VIEWING_AGENT`を入力 | 作成先が`BCAST_PLATFORM_HANDSON.MART`になる |
| 作成画面 | Display name=`VIEWING_AGENT`を入力して作成 | `VIEWING_AGENT`の編集画面が開く |

同名Agentがある場合は上書きせず講師へ確認します。

### 3-2. Configuration → 一般

| どこ | 操作 | 成功 |
|---|---|---|
| 一般 → 表示名 | [agent_texts.md](agent_texts.md)の表示名を入力 | `VIEWING_AGENT`と表示される |
| 一般 → 説明 | 同ファイルの説明を貼り付け | 教材の対象と3指標が入力される |
| 一般 → 質問の例 | **質問を追加**を3回押し、質問例を1件ずつ入力 | 3件の質問が表示される |

### 3-3. Configuration → 手順

| どこ | 操作 | 成功 |
|---|---|---|
| 手順 → モデル | `Claude Opus 5`を選ぶ | 選択したモデル名が表示される |
| 手順 → オーケストレーション手順 | [agent_texts.md](agent_texts.md)の同名ブロックを全文コピー | 先頭から末尾まで入力される |
| 手順 → 応答手順 | 同ファイルの同名ブロックを全文コピー | 別の欄に全文が入力される |
| 手順 → 予算の構成 | 時間制限とトークン制限を変更しない | どちらも`制限なし`である |

### 3-4. Configuration → ツール

| どこ | 操作 | 成功 |
|---|---|---|
| ツール → 構造化データのクエリ | **セマンティックビューを追加**を押す | 追加画面が開く |
| 追加画面 | [agent_texts.md](agent_texts.md)の名前、Semantic view、Warehouse、Query timeout、説明を入力 | `SV_VIEWING`が追加される |
| ツール | ウェブ検索、分析検索、コード実行をオフにする | 3つともオフである |
| ツール | 検索サービス、カスタムツールを追加しない | `SV_VIEWING`以外のデータツールがない |
| スキル／MCP | 何も追加しない | 一覧が空である |

コード実行ツールが既定でオンの場合もオフにします。`ML.PREDICTIONS`、Cortex Search、カスタムツール、スキル、MCPは接続しません。120秒はSemantic Viewから生成された1つのSQLの待ち時間で、Agent全体の時間制限ではありません。

### 3-5. 保存・公開・Preview

| どこ | 操作 | 成功 |
|---|---|---|
| 右上 | **保存**を押す | 「保存されていない変更」が消える |
| 右上 | **公開**を押す | 設定した版が公開される |
| Preview | 第5節の検証質問を送る | `SV_VIEWING`が呼ばれ、回答とSQLを確認できる |

保存前に別タブへ移動しても入力が確定したとはみなしません。赤い「保存されていない変更」が消えたことを確認します。

## 4. 設定を確認し、共有する

| どこ | 操作 | 成功 |
|---|---|---|
| Git Workspace | [sql/05_02_agent.sql](../sql/05_02_agent.sql)を開く | GUI作成後であることを確認できる |
| 同SQL | `SHOW AGENTS`と`DESCRIBE AGENT`だけを実行 | `VIEWING_AGENT`が存在し、参照先と設定を確認できる |
| Agent画面 → Configuration | 一般・手順・ツールを再確認 | 質問3件、指示全文、`SV_VIEWING`、WH、120秒が保存されている |
| Agent画面 → Access | **ロールを追加**から`BCAST_PLATFORM_ANALYST_ROLE`を追加 | 所有者ロールと分析ロールが表示される |
| 同SQL | `GRANT USAGE ON AGENT ... TO ROLE BCAST_PLATFORM_ANALYST_ROLE`を実行 | GUIのAccess設定と同じ利用権限をSQLでも確認できる |

作成者は所有者として利用できるため、エンジニアロールへのUSAGE再付与は不要です。Semantic Viewへの`SELECT / REFERENCES`は `05_01_semantic.sql` で付与済みです。既定ロールが必要権限を直接持つか、ロール階層から継承する必要があります。

`sql/05_02_agent.sql`末尾のコメント内DDLは、GUIでまだAgentを一度も作成しておらず、講師から指示された場合だけ使う代替経路です。GUIと両方を実行しません。

## 5. Previewで検証する

各質問で、**回答文だけでなく生成SQLと実行結果を開いて確認**します。

| どこ | 操作 | 成功 |
|---|---|---|
| Preview | `2026年5月1日から7月31日の全5局のリーチ、総視聴時間、総視聴回数を教えてください`と質問 | 期間・局・単位が明示され、3指標が直接SQLの基準値と一致する |
| Preview | `2026年5月1日から7月31日の放送局別リーチを比較してください`と質問 | 局別リーチを足して全体リーチとしていない |
| Preview | `2026年5月1日から7月31日のF1在籍あり予測の端末数を教えてください`と質問 | F1在籍予測は対象外と説明し、視聴実績から推測しない |
| Preview | `2026年8月の全5局のリーチを教えてください`と質問 | 5月から7月へ置換せず、該当データなしと説明する。エラーを0件と扱わない |

生成SQLでは、日付条件と局条件、`COUNT(DISTINCT DEVICE_ID)`、`SUM(VIEW_MINUTES)`、`SUM(SESSION_COUNT)`に相当する集計を確認します。日別や局別のリーチを足して期間全体を作ってはいけません。

F1は20歳から34歳の女性です。ただしこのAgentは予測テーブルを持たないため、F1在籍確率、予測端末数、実際のF1視聴者数、モデル評価を答えません。

## 6. CoWorkで共有先を検証する

| どこ | 操作 | 成功 |
|---|---|---|
| CoWorkまたは[ai.snowflake.com](https://ai.snowflake.com/) | 共有先利用者で`VIEWING_AGENT`を選ぶ | Agentが表示される |
| 同画面 | 全体3指標の質問を送る | Previewと同じ条件・指標の回答になる |
| 共有先の設定 | 既定ロール、既定WH、Analyst用WHを再確認 | 権限エラーなくツールが実行される |

一覧に見えるだけではツール利用の確認になりません。見つからない、または権限エラーの場合は設定を推測して変えず、管理者へ確認します。既存のSnowflake Intelligenceオブジェクトを本教材から自動変更しません。

PreviewとCoWorkの両方で、共有先利用者が直接SQLと同条件の結果を確認できれば完了です。

## うまくいかないとき

| 状況 | 確認 |
|---|---|
| Semantic Viewを選べない | DB・スキーマ、作成結果、参照権限 |
| Agentが一覧にない | 配置先、表示名、保存／公開した版、AgentのUSAGE |
| Agentは見えるが質問に失敗 | 既定ロール・既定WH、Analyst用WH、Semantic Viewと元データの権限 |
| 回答値が直接SQLと違う | 期間・局、生成SQL、リーチの重複除去、`SESSION_COUNT`の合計 |
| 同名オブジェクトがある | 上書きせず、所有者と用途を講師・管理者へ確認 |

権限回避のために広い管理者権限を付けません。どの操作で止まったかを記録します。

## 補足と参考

Agent全体のorchestration budgetは明示設定していません。Semantic Viewクエリの120秒とは別です。GUIと代替SQLの動作が同じとは断定しないため、どちらの経路でもPreviewとCoWorkの検証を省略しません。

- [CREATE SEMANTIC VIEW](https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view)
- [AgentのGUI管理](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)
- [Agentのアクセス設定](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-setup)
- [補足教材](../supplemental/README.md)
- [後片付け](01_setup.md#後片付け)