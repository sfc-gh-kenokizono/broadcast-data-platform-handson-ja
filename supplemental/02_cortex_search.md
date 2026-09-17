# 補足 Cortex Searchでジャンルの説明を探す

**この演習は任意です。本編を進めるために実行する必要はありません。**

本編のAgentでは、表の数値を集計しました。
ここでは別の使い方として、「知りたいことに近い説明文を探す」検索を試します。

たとえば「試合の結果や選手の活躍を知りたい」と入力したとき、SPORTSの説明を見つけられるかを確認します。
検索対象は、教材用に書いた5ジャンルの説明文だけです。
本編の2026年5月1日〜7月31日の視聴実績は8ジャンルですが、この独立した演習ではNEWS・DRAMA・VARIETY・ANIME・SPORTSだけを使います。MUSIC（音楽）・MOVIE（映画）・INFO（情報）の説明は検索対象に含みません。

## Cortex Searchは何をするもの？

Cortex Searchは、文章から関連する情報を探すためのサービスです。
検索しやすいように文章の情報を用意し、検索時に近い内容を返します。

| 言葉 | この演習での意味 |
|---|---|
| 検索サービス | 検索対象を準備し、問い合わせを受け付ける仕組み |
| 索引（インデックス） | 検索しやすいように整理した情報 |
| 埋め込みモデル | 文章の特徴を数値で表すためのモデル |
| `SEARCH_PREVIEW` | SQLから検索を試すための機能 |

```text
5ジャンルの説明文 → 検索用の索引を作る
                          ↓
                  日本語の文章で検索
                          ↓
                 関連するジャンルと説明を返す
```

これは、検索結果として説明文を返す演習です。
生成AIが新しい回答文を作るところまでは行いません。
視聴実績の集計、番組名・CMの検索、F1同居の確率・予測ラベルも対象外です。

**本編の `VIEWING_AGENT` は変更せず、別Agentも作りません。**
本編では引き続き `SV_VIEWING` の分析ツールだけを使います。

## 1. 実行前に確認する

第1章のセットアップが終わった、新教材のアカウントを使います。
この検索の入力はSQL内の固定5行なので、dbt・共通マート・MLは不要です。

講師へ、次の項目を確認してください。

- Cortex Searchと `snowflake-arctic-embed-l-v2.0` を、対象リージョンで使える。
- 教材ロールでDB・MART・共通WHと埋め込みモデルを利用できる。
- 管理者が `SVC_GENRE_GUIDE` という既存サービスがないことを確認している。
- 終了時に誰が停止・削除するかが決まっている。

利用できない場合は、この補足を省略します。
勝手に別モデルへ変更したり、アカウント全体の設定を変えたりしないでください。

### 作成権限を管理者に準備してもらう

第1章には、Cortex Searchサービスを作る権限は含まれていません。
MARTの所有者など、権限を付与できる管理者が対象と影響を確認し、承認後に次を実行します。

```sql
GRANT CREATE CORTEX SEARCH SERVICE
  ON SCHEMA BCAST_PLATFORM_HANDSON.MART
  TO ROLE BCAST_PLATFORM_ENGINEER_ROLE;
```

受講者自身が管理者ロールのままサービスを作る手順ではありません。
`SNOWFLAKE.CORTEX_USER` が付いているだけでも、この作成権限の代わりにはなりません。

同名サービスがある場合は、削除や上書きで回避せず停止します。
自分の一覧に見えないだけでは、存在しないと断定できないため、管理者に確認してもらいます。

## 2. 検索サービスを作る

[02_create_genre_search.sql](02_create_genre_search.sql) を開きます。

1. 冒頭の `USE` と確認用SELECTを実行し、アカウント・ロール・DB・WHを確認します。
2. `CREATE CORTEX SEARCH SERVICE ...` を1文として実行します。
3. エラーなく作成できたら、次の検索へ進みます。

| 項目 | 値 |
|---|---|
| 作成ロール | `BCAST_PLATFORM_ENGINEER_ROLE` |
| サービス | `BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE` |
| 検索する文章の列 | `GUIDE_TEXT` |
| ジャンルの列 | `GENRE` |
| 作成・更新用WH | `BCAST_PLATFORM_COMMON_WH` |
| 検索対象 | SQL内の `VALUES` に書いた5行 |

`VALUES` は、SQLの中に行を直接書く方法です。
別のソース用テーブルやビューを作らず、NEWS・DRAMA・VARIETY・ANIME・SPORTSの説明を用意します。

作成時に最初の索引を準備する設定が `INITIALIZE = ON_CREATE` です。
固定5行を読むため `REFRESH_MODE = FULL` を指定しており、既存テーブルの変更追跡には依存しません。
これは演習用の構成で、大きなデータでも同じ方式を推奨する意味ではありません。

## 3. 日本語で検索する

作成SQL末尾の `SEARCH_PREVIEW` を1回実行します。
検索文は、あらかじめ次を指定してあります。

```text
試合の結果や選手の活躍を知りたい
```

結果の `GENRE` と `GUIDE_TEXT` を読んでみましょう。
**SPORTSの説明が含まれるか、検索文と返された内容が合っているか**を確認します。

検索は最大3件を求める設定です。順位や、必ず同じ件数が返ることを保証するものではありません。
5件すべてが返らなくても、そのことだけで失敗とはしません。

結果が空、初期化が未完了、権限エラーの場合は、講師へ確認します。
再試行を何度も繰り返す前に、初期化状態やモデルの利用可否を確認してください。
`SEARCH_PREVIEW` は試験用であり、アプリの応答性能を測る用途には使いません。

## 4. 終わったらサービスを停止する

**共通WHが自動停止しても、Searchサービスの提供は停止しません。**
検索を試したら、所有者と共同利用者への影響を確認して、サービス自体を停止します。

まず次を実行し、対象と所有者を確認します。

```sql
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

自分が作った `SVC_GENRE_GUIDE` で、停止してよいことを確認したら次を実行します。

```sql
ALTER CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE SUSPEND;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

`SUSPEND` は、INDEXING（索引の更新）とSERVING（検索の提供）の両方を停止します。
**一覧で両方が停止したことを確認してください。**
停止・再開には `OPERATE` 権限が必要です。作成時の所有者ロールで行い、所有者が変わっていれば依頼します。

### 不要なら削除する

停止しても索引の保存は残ります。
サービスが不要になり、利用する人や処理がないことを確認した場合だけ、次を実行します。

```sql
DROP CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE;
SHOW CORTEX SEARCH SERVICES IN SCHEMA BCAST_PLATFORM_HANDSON.MART;
```

削除には所有権（`OWNERSHIP`）が必要です。
所有者として一覧から消えたことを確認します。
共通WH・MARTスキーマ・本編Agent・既存テーブルは削除しません。
追加した作成権限を取り消すかは、他の用途を確認した管理者が判断します。

## 費用と更新設定の補足

作成・更新時のWH処理と埋め込みに加え、索引保存や検索提供にも費用が発生し得ます。
停止後も保存は残り、`RESUME` で再開すれば提供に伴う費用も再開します。
再開は次に試す必要がある場合だけ、所有者が行います。

`TARGET_LAG = '1 hour'` は、データ更新の鮮度目標です。
**「1時間後に止まる」「毎時ちょうどに実行する」という設定ではありません。**
CREATE後はSearch自身が更新を管理しますが、追加のTaskやdbtのスケジュールは作りません。

実運用では、他の処理への影響を避ける専用WHも検討します。
この5行の演習結果で、本番の性能や費用を評価しないでください。

## 参考

公式構文は確認していますが、このアカウントでの作成・検索・停止・削除は未検証です。
講師の案内に従い、結果を確認しながら進めてください。

- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search)
- [ALTER CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/alter-cortex-search)
- [SEARCH_PREVIEW](https://docs.snowflake.com/en/sql-reference/functions/search_preview-snowflake-cortex)
- [提供リージョン・モデル・費用](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [補足教材の一覧へ戻る](README.md)