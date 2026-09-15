# Cortex Search：架空ジャンル説明の検索（任意）

このガイドは**本編とは別の拡張（augmentation）**です。`NEWS / DRAMA / VARIETY / ANIME / SPORTS` の説明を探すだけの小さな実験です。旧教材の番組マスター・CMマスターを使わず、旧教材と同じ番組／CM検索を再現するものでもありません。視聴実績の集計、番組名検索、CM検索、関心ラベルの推定はできません。

本編 `BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT` のツール・指示・公開設定は変更しません。本編は `SV_VIEWING` だけを使う Analyst-only のままで、Searchを作成せずに完了できます。ここでは別Agentも作りません。

## 実行前ゲート

1. [セットアップ](../docs/01_setup.md) 後の新教材アカウントであることを確認します。Searchは共通マート・dbt・MLに依存しません。データソースは作成SQL内の架空の固定5行だけです。
2. 講師が対象リージョンで Cortex Search と多言語モデル `snowflake-arctic-embed-l-v2.0` を利用できること、管理ポリシーと費用を確認します。利用不可ならこの補足を省略します。別モデルへの自動置換やアカウント設定変更はしません。
3. エンジニアのDB・MART・共通WHのUSAGE、埋め込みモデル利用権限を確認します。セットアップには `SNOWFLAKE.CORTEX_USER` の付与がありますが、`CREATE CORTEX SEARCH SERVICE` は含まれていません。次の権限だけを、MART所有者など付与権限を持つ管理者が承認後に追加します。参加者が管理者ロールでサービスを作る手順ではありません。

```sql
GRANT CREATE CORTEX SEARCH SERVICE
  ON SCHEMA BCAST_PLATFORM_HANDSON.MART
  TO ROLE BCAST_PLATFORM_ENGINEER_ROLE;
```

4. 管理者／所有者がMART内の既存サービスを確認し、`SVC_GENRE_GUIDE` が未使用であることを確認します。参加者に一覧が見えないだけでは不存在の証明になりません。既存の場合は停止し、`OR REPLACE`、`IF NOT EXISTS` や無断のDROPで回避しません。
5. 誰が終了時の停止・削除を行うかを決めます。作成者は `BCAST_PLATFORM_ENGINEER_ROLE`。所有権が別ロールへ移ったら、その所有者に確認します。追加の利用権限をアナリストやPUBLICへ付与する手順は含めません。

## 作成と試行

[02_create_genre_search.sql](02_create_genre_search.sql) を開き、一文ずつ選択実行します。冒頭のセッション情報を確認した後にCREATEへ進み、失敗したらそこで停止します。`CREATE` は新規作成だけで、ソース用テーブルやビューは作りません。

作成先は `BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE`、WHは `BCAST_PLATFORM_COMMON_WH` です。固定 `VALUES` を直接読むため `REFRESH_MODE = FULL` を明示し、既存テーブルのchange trackingには依存しません。これは小さな演習用の選択で、大規模データへの推奨ではありません。通常の運用では他処理への影響を考慮した専用WHも検討します。

`INITIALIZE = ON_CREATE` で初回索引を作成します。成功後、末尾の `SEARCH_PREVIEW` を1回実行します。「試合の結果や選手の活躍を知りたい」に対し、`SPORTS` の説明が含まれるか、返却列が `GENRE, GUIDE_TEXT` かを読みます。順位や全5件の返却は保証しません。これは検索結果であり、生成AIによる回答文ではありません。生成回答への組み込みは別の設計・評価対象です。

結果が空、未ロード、権限エラーなら成功とは扱いません。講師が初期化状態とモデル提供状況を確認し、再試行を連打しません。`SEARCH_PREVIEW` は試験向けであり、アプリの低遅延性能測定には使いません。

## 費用と終了処理

Searchは作成時のWH処理・埋め込みに加え、索引の保存や検索提供にも費用が発生し得ます。**共通WHの自動停止だけではSearchの提供は停止しません。** `TARGET_LAG = '1 hour'` は更新の鮮度目標で、1時間後の停止設定でも、毎時ちょうどの実行時刻でもありません。CREATE後はSearch自身の更新管理が動きます。ここで「スケジュールを作らない」とは追加のdbt／Taskスケジュールを作成しない意味です。

試行後は、自分が作成したサービスであることと共同利用者への影響を確認してから、次の停止を行います。停止・削除は作成SQLに混ぜていません。

```sql
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

所有者と対象名を確認後、次を選択実行します。`SUSPEND` は INDEXING と SERVING の両方を停止します。停止／再開にはOPERATE、削除にはOWNERSHIPが必要です。教材では作成時の所有者ロールが実施し、権限不足なら所有者へ依頼します。

```sql
ALTER CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE SUSPEND;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

両方が停止したことを確認します。停止は削除ではなく、索引などの保存は残ります。再開すると費用も再開するため、次の試行が必要なときだけ所有者が `RESUME` を行います。不要なら、依存する利用者がいないことを再確認して、この1サービスだけを削除します。

```sql
DROP CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

所有者権限で一覧から消えたことを確認します。共有のMART、共通WH、本編Agent、既存テーブルは削除しません。追加した作成権限の取り消しは、他の演習で使わないことを確認した管理者が判断します。

## 検証と参照

公式構文は確認していますが、対象アカウントでのコンパイル・作成・検索・停止・削除は未検証です。実施する講師が各ゲートの結果を記録してください。

- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search)
- [ALTER CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/alter-cortex-search)
- [SEARCH_PREVIEW](https://docs.snowflake.com/en/sql-reference/functions/search_preview-snowflake-cortex)
- [提供リージョン・モデル・費用](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)