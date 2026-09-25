# 補足 Cortex Searchでジャンルの説明を探す

**任意の独立演習です。** 固定した5ジャンルの説明文から、「試合の結果や選手の活躍を知りたい」に近い説明を検索します。本編の `VIEWING_AGENT` は変更せず、別Agentも作りません。本編のツールは引き続き `SV_VIEWING` の1つだけです。

検索対象はNEWS、DRAMA、VARIETY、ANIME、SPORTSです。本編の8ジャンルのうちMUSIC、MOVIE、INFOは含みません。視聴実績集計、番組・CM検索、F1在籍予測も対象外です。

## 全体の流れ

| どこ | 操作 | 成功 |
|---|---|---|
| 管理者の権限確認 | 利用可否・既存サービス・停止担当を確認し、作成権限を付与 | 教材ロールで安全に作成できる |
| Git Workspace | `02_create_genre_search.sql`の確認とCREATEを実行 | `SVC_GENRE_GUIDE`が作成される |
| 同SQL | `SEARCH_PREVIEW`を1回実行 | SPORTSの説明を含む関連結果を確認できる |
| Git Workspace | 所有者を確認してSUSPEND、不要ならDROP | INDEXINGとSERVINGが停止、またはサービスが消える |

## 1. 実行前の安全確認

入力はSQL内の固定5行なので、dbt、共通マート、MLは不要です。第1章を完了した新教材のアカウントだけを使います。

| どこ | 操作 | 成功 |
|---|---|---|
| 講師・管理者 | 対象リージョンでCortex Searchと`snowflake-arctic-embed-l-v2.0`を利用できるか確認 | 利用可能と確認される |
| 管理者 | 教材ロールのDB、MART、共通WH、埋め込みモデルの利用権限を確認 | 必要権限が確認される |
| 管理者 | `SVC_GENRE_GUIDE`が既にないか、所有者を含め確認 | 同名サービスがない |
| 講師・管理者 | 終了時の停止・削除担当を決める | 担当者が明確になる |

利用できない、または同名サービスがある場合は停止します。削除・上書き、別モデルへの変更、アカウント全体設定の変更で回避しません。受講者が管理者ロールのまま作成する手順ではありません。

第1章に作成権限は含まれません。承認後、MARTの所有者など権限を付与できる管理者が実行します。

```sql
GRANT CREATE CORTEX SEARCH SERVICE
  ON SCHEMA BCAST_PLATFORM_HANDSON.MART
  TO ROLE BCAST_PLATFORM_ENGINEER_ROLE;
```

`SNOWFLAKE.CORTEX_USER`だけでは、この作成権限の代わりになりません。自分の一覧に見えないことも、サービスが存在しない証拠にはなりません。

## 2. CREATEを実行する

| どこ | 操作 | 成功 |
|---|---|---|
| Git Workspace | [02_create_genre_search.sql](02_create_genre_search.sql)を開く | 対象が`BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE`である |
| 同SQL冒頭 | `USE`と確認SELECTを実行 | アカウント、ロール、DB、WHが教材用である |
| 同SQL | `CREATE CORTEX SEARCH SERVICE`を1文として実行 | エラーなく作成される |

設定は、検索列=`GUIDE_TEXT`、属性列=`GENRE`、WH=`BCAST_PLATFORM_COMMON_WH`、入力=SQL内の5行です。`INITIALIZE = ON_CREATE`で最初の索引を準備し、固定5行のため`REFRESH_MODE = FULL`を使います。大規模データへの推奨構成ではありません。

## 3. SEARCH_PREVIEWで確認する

作成SQL末尾の `SEARCH_PREVIEW` を1回だけ実行します。

```text
試合の結果や選手の活躍を知りたい
```

| どこ | 操作 | 成功 |
|---|---|---|
| SQL結果 | `GENRE`と`GUIDE_TEXT`を読む | SPORTSの説明が含まれ、検索文と内容が合う |
| 結果件数 | 最大3件の結果を確認 | 件数や順位を固定の正解とはみなさない |

空結果、初期化未完了、権限エラーの場合は再試行を繰り返さず、初期化状態とモデル利用可否を講師へ確認します。`SEARCH_PREVIEW`は試験用で、アプリ性能の測定には使いません。

## 4. 必ず停止し、不要なら削除する

**共通WHの自動停止ではSearchサービスは止まりません。** 共同利用者への影響を確認し、作成時の所有者ロールで対象と所有者を確認します。

```sql
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

自分が作成した `SVC_GENRE_GUIDE` で、停止してよいことを確認してから実行します。

```sql
ALTER CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE SUSPEND;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

| どこ | 操作 | 成功 |
|---|---|---|
| SHOW結果 | INDEXINGとSERVINGの状態を確認 | 両方が停止している |
| 権限 | 作成時の所有者ロールで実行 | `OPERATE`不足がない。所有者変更済みなら所有者へ依頼する |

`SUSPEND`後も索引の保存は残ります。今後使わず、利用者や処理がないことを確認した場合だけ、所有者が削除します。

```sql
DROP CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

削除には`OWNERSHIP`が必要です。一覧から消えたことを確認します。共通WH、MART、本編Agent、既存テーブルは削除しません。追加した作成権限を取り消すかは、他用途を確認した管理者が判断します。

## 費用と更新

作成・更新用WH、埋め込み、索引保存、検索提供には費用が発生し得ます。停止後も保存は残り、`RESUME`すると提供に伴う費用も再開します。

`TARGET_LAG = '1 hour'`は更新鮮度の目標で、「1時間後に停止」や「毎時ちょうどに実行」ではありません。追加のTaskやdbtスケジュールは作りません。この5行で本番性能や費用を評価しません。

この補足の作成・検索・停止・削除は演習環境での動作確認前です。講師の案内に従ってください。

- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search)
- [ALTER CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/alter-cortex-search)
- [SEARCH_PREVIEW](https://docs.snowflake.com/en/sql-reference/functions/search_preview-snowflake-cortex)
- [提供リージョン・モデル・費用](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [補足教材の一覧へ戻る](README.md)