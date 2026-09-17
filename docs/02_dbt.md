# 第2章 dbtで視聴データを整え、5局をまとめる

第1章では、5局のファイルを、それぞれのRAWテーブルへ取り込みました。
まだ ` news ` と `NEWS` のような表記の違いが残っています。

この章では、**各局で表記をそろえ、データを確認してから、分析しやすい表を作ります。**
最後に、5局分の完成した表を1つにまとめます。

## まず、何のためにdbtを使うの？

SQLを1つずつ実行するだけでも、表記の修正や集計はできます。
ただ、処理が増えると「どのSQLを先に動かすか」「結果に問題がないか」を毎回確認する必要があります。

**dbtは、SQLで書いたデータ加工と、その結果のテストをまとめて管理する道具です。**
この教材にはSQLとテストを用意してあるので、ゼロから書く必要はありません。
内容を読み、局を指定して実行し、結果を確認していきましょう。

> 💡 この章の「dbtモデル」は、テーブルを作るためのSQLです。
> 第3章の「機械学習モデル」とは別の意味です。

### この章で使う言葉

| 言葉 | この教材での意味 |
|---|---|
| RAW（ロー） | 取り込んだ原本を残す場所。ここは書き換えません |
| クレンジング | 空白や大文字・小文字などの違いを整えること |
| マート | グラフや分析に使いやすい形へまとめた表 |
| モデル | dbtでは、出力テーブルを作るSQLの定義 |
| テスト | 空欄・重複・想定外の値などがないか調べる処理 |
| `build` | テーブル作成とテストを、依存する順番に実行するコマンド |
| `target` | 実行ロール・保存先・ウェアハウスをまとめた設定 |
| タグ | 「NW01の処理」など、実行対象を選ぶための目印 |

## 1. データがどう変わるかを見る

まずはNW01の1局だけで考えます。

```text
RAW.VIEWING_LOG_NW01        取り込んだ視聴記録
          ↓ 表記をそろえ、視聴分数を計算
NW01.CLEAN_VIEWING          整えた視聴記録 → テスト
          ↓ 端末・日付・ジャンルごとに集計
NW01.MART_DEVICE_DAILY      分析用の表     → テスト
```

### 処理① 表記をそろえ、視聴時間を計算する

`CLEAN_VIEWING` では、ジャンル名を次のように整えます。

| 入力の例 | 処理後 | 何を変えたか |
|---|---|---|
| ` news ` | `NEWS` | 前後の空白を取り、大文字へ変更 |
| `　ＳＰＯＲＴＳ　` | `SPORTS` | 全角の空白を取り、指定の半角表記へ変更 |
| `DRAMA` | `DRAMA` | 既にそろっている値はそのまま |

さらに、視聴開始 `VIEW_FROM` と視聴終了 `VIEW_TO` の差から、視聴分数 `VIEW_MINUTES` を作ります。
たとえば08:00から08:10までなら、10分です。

**原本のRAWテーブルは変更せず、整えた結果を別テーブルへ保存します。**
知らないジャンルや不正な時刻を、勝手に別の値へ置き換えたり削除したりはしません。
後続のテストで問題を見つけるためです。

### 処理② 端末・日付・ジャンルごとにまとめる

`MART_DEVICE_DAILY` では、「同じ局・同じ端末・同じ日・同じジャンル」の記録をまとめます。

次は仕組みを説明するための例です。配布データの実際の行ではありません。
局・端末・日付が同じ場合を考えてみましょう。

| 集計前の記録 | ジャンル | 視聴時間 |
|---|---|---|
| 1回目 | NEWS | 10分 |
| 2回目 | NEWS | 20分 |
| 3回目 | SPORTS | 15分 |

集計すると、次の2行になります。

| ジャンル | `SESSION_COUNT`（視聴回数） | `VIEW_MINUTES`（視聴分数） |
|---|---|---|
| NEWS | 2回 | 30分 |
| SPORTS | 1回 | 15分 |

ここで、**表は2行ですが、視聴は3回、視聴した端末は1台**です。
後のグラフでも「行数」「視聴回数」「端末数」を区別して使います。

> 💡 今回の配布データは、このまとめ方でも各行が1回のままになる構成です。
> 日次集計後に行数が減らなくても異常ではありません。
> 章末の確認SQLでは、上のように3回を2行へまとめる例も試せます。

### 処理③ 5局の完成した表をまとめる

NW02〜NW05でも同じ処理を行います。
**各局の作成とテストがすべて成功してから**、共通テーブルを作ります。

```text
NW01の原本 → 整形 → テスト → NW01のマート → テスト ─┐
NW02の原本 → 整形 → テスト → NW02のマート → テスト ─┤
NW03の原本 → 整形 → テスト → NW03のマート → テスト ─┼→ COMMON.VIEWING_DAILY
NW04の原本 → 整形 → テスト → NW04のマート → テスト ─┤   完成した表を縦につなぐ
NW05の原本 → 整形 → テスト → NW05のマート → テスト ─┘
```

縦につなぐ処理が `UNION ALL` です。列をそろえて、5局分の行を並べます。
ここでは再集計や重複の削除は行いません。

原本を最初に1つへまとめないので、各局の加工とテストを、その局専用のウェアハウスで動かせます。
どの局の処理に計算資源を使ったか、後から確認しやすくなります。

## 2. 開くファイルと実行場所を確認する

第1章で作ったGit Workspaceを開きます。
この章でWorkspaceを作り直したり、ローカルPCへdbtをインストールしたりする必要はありません。

**開始前の確認**

- 第1章のロードが終わり、RAWの5局が各3,600行になっている。
- ロールとして `BCAST_PLATFORM_ENGINEER_ROLE` を選べる。
- 講師が案内した環境で、dbtバージョン `1.9.4` を使える。
- 第1章で作った6つのウェアハウスを使える。

最初は次のファイルだけ見てみましょう。すべて暗記する必要はありません。

| 開くファイル | 読み取ること |
|---|---|
| [clean_viewing.sql](../dbt/macros/clean_viewing.sql) | 前後空白の除去、ジャンル表記の変更、分数の計算 |
| [device_daily.sql](../dbt/macros/device_daily.sql) | 端末・日付・ジャンルごとの件数と時間の合計 |
| [viewing_daily.sql](../dbt/models/common/viewing_daily.sql) | 完成した5局のマートを `UNION ALL` する処理 |
| [profiles.yml](../dbt/profiles.yml) | どの局にどのウェアハウスを使うか |

最初の2ファイルにある `macro` は、**5局で繰り返し使うSQLの部品**という意味です。
同じ整形ルールを5回書かずに済むようにしています。
共通の部品を使っても、1回の入力は1局分だけです。

### 実行対象とウェアハウスは別々に選ぶ

「NW01の処理を選ぶ」ことと、「NW01のウェアハウスを使う」ことは別です。
実行コマンドでは、両方を同じ局にそろえます。

| 局・統合先 | `--target` | 保存先スキーマ | 使うウェアハウス |
|---|---|---|---|
| NW01 | `nw01` | `NW01` | `BCAST_PLATFORM_NW01_WH` |
| NW02 | `nw02` | `NW02` | `BCAST_PLATFORM_NW02_WH` |
| NW03 | `nw03` | `NW03` | `BCAST_PLATFORM_NW03_WH` |
| NW04 | `nw04` | `NW04` | `BCAST_PLATFORM_NW04_WH` |
| NW05 | `nw05` | `NW05` | `BCAST_PLATFORM_NW05_WH` |
| 5局の統合 | `common` | `COMMON` | `BCAST_PLATFORM_COMMON_WH` |

> ⚠️ SQLエディタのウェアハウスを選んだだけでは、dbtの実行先を選んだことにはなりません。
> 以下の `--target` を省略しないでください。

## 3. NW01で、実行対象だけを確認する

SnowsightのWorkspace内でSQLエディタを開き、次のSQLを貼り付けて実行します。
これは **`ls`（対象一覧の表示）なので、テーブルは作りません。**

Workspaceの名前を変更して作成した場合は、SQL内の `"broadcast-data-platform-handson-ja"` を実際の名前へ変更してください。
`USER$` は実行者自身のWorkspaceを参照するための表記です。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'ls --target nw01 --select tag:nw01 --indirect-selection cautious';
```

### コマンドの読み方

| 記述 | 意味 |
|---|---|
| `PROJECT_ROOT = 'dbt'` | Workspace内の `dbt/` フォルダを使う |
| `DBT_VERSION = '1.9.4'` | この教材で使うdbtの版 |
| `--target nw01` | NW01用の保存先・ウェアハウス設定を使う |
| `--select tag:nw01` | NW01というタグが付いた処理を選ぶ |
| `--indirect-selection cautious` | 関連テストの自動選択を慎重に行い、他局にまたがるテストを巻き込まない |

最後の指定は、今はそのまま使って構いません。
**実行先を選ぶのが `target`、処理を選ぶのが `select`** と押さえてください。

✅ 一覧に、NW01の **2モデルと7テストだけ**が含まれることを確認します。
他局やcommonの処理が含まれる、実行環境がこの指定を受け付けない場合は、講師へ確認してください。
全体実行に置き換えて先へ進まないでください。

## 4. NW01のテーブルを作り、テストする

今度は `ls` を `build` に変えます。
dbtが整形テーブルを作り、テストし、問題がなければ日次マート作成へ進みます。

**下の5文は、1文ずつ実行してください。**
まずNW01を実行し、次の「成功の見方」で確認してから、NW02〜NW05へ進みます。
共通テーブルの作成は、まだ実行しません。

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

### 成功の見方① 実行結果とログ

実行結果で `Success = TRUE`、`EXCEPTION` にエラーがないことを確認します。
続いて `STDOUT` を開きます。STDOUTは、dbtが出した処理経過のログです。

確認する目印は次のとおりです。

- `Completed successfully` が表示されている。
- モデル2件とテスト7件が成功している。
- `ERROR=0 SKIP=0` になっている。

`SKIP` は「その処理を実行しなかった」という意味です。
前段のテストが失敗すると、後段のマート作成がスキップされることがあります。
テーブルが見えていても、以前の実行で作ったものかもしれません。**今回のログ**で確認します。

なお、補助処理（hook）が成功数に含まれる場合があります。
合計の数字だけでなく、2モデル・7テストの内訳を見てください。

### 成功の見方② データの件数

NW01のbuild成功後、次の確認SQLを実行します。
原本と整形後の件数、日次マートの視聴回数を比べます。

```sql
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE WAREHOUSE BCAST_PLATFORM_NW01_WH;
SELECT
  (SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.RAW.VIEWING_LOG_NW01) AS RAW_ROWS,
  (SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.NW01.CLEAN_VIEWING) AS CLEAN_ROWS,
  (SELECT SUM(SESSION_COUNT) FROM BCAST_PLATFORM_HANDSON.NW01.MART_DEVICE_DAILY) AS MART_SESSIONS;
```

| 結果の列 | 期待値 | 確認していること |
|---|---|---|
| `RAW_ROWS` | 3,600行 | 原本の件数 |
| `CLEAN_ROWS` | 3,600行 | 整形時に記録が抜けていないか |
| `MART_SESSIONS` | 3,600回 | 集計後も元の視聴回数が残っているか |

NW02以降を確認するときは、SQL内の **WH・スキーマ・RAWテーブル名の `NW01` をすべて同じ局番号へ変更**します。
どの局でも期待値は同じです。

### 成功の見方③ 計算したウェアハウス

Snowsightの **Monitoring → Query History（クエリ履歴）** を開きます。
自分のユーザーと、今実行した時刻で絞り込みます。

dbtを呼び出したSQLのほかに、dbtが発行したテーブル作成SQLやテストSQLがあります。
これが「子クエリ」です。

1. `NW01.CLEAN_VIEWING` と `NW01.MART_DEVICE_DAILY` を作る `CREATE TABLE ... AS SELECT` を探します。
2. テスト用の `SELECT`（`count(*) as failures` など）を探します。
3. どちらもWarehouseが `BCAST_PLATFORM_NW01_WH` になっていることを確認します。

親の `EXECUTE DBT PROJECT` の表示だけではなく、**実際に表を作ったSQLと検査したSQL**を見るのがポイントです。
履歴やログが見つからなければ、講師と一緒に確認してください。

## 5. 残りの4局を実行する

NW01で手順を確認できたら、第4節のNW02〜NW05のSQLを順番に実行します。
各局で「ログ・件数・ウェアハウス」の3点を同じように確認します。

| 局 | 作成とテスト | 整形後の件数／マートの回数 | 計算先 |
|---|---|---|---|
| NW01 | 2モデル＋7テスト成功 | 3,600行／3,600回 | NW01用WH |
| NW02 | 2モデル＋7テスト成功 | 3,600行／3,600回 | NW02用WH |
| NW03 | 2モデル＋7テスト成功 | 3,600行／3,600回 | NW03用WH |
| NW04 | 2モデル＋7テスト成功 | 3,600行／3,600回 | NW04用WH |
| NW05 | 2モデル＋7テスト成功 | 3,600行／3,600回 | NW05用WH |

**1局でも失敗したら、commonへ進みません。**
原因を確認し、該当局の同じbuildをやり直します。
エラー文と局名、実行したSQLを講師へ伝えてください。

> ⚠️ この教材では、5回の成功を人が確認します。
> 「全局が成功したら自動で次へ進む」仕組みは作っていません。
> 確認中は入力データやSQLを変更せず、過去の成功ログと混ぜないでください。

## 6. 最後に5局を統合する

5局がすべて成功したら、次の1文を実行します。
今度は `--target common` で、共通ウェアハウスを使います。

```sql
EXECUTE DBT PROJECT FROM WORKSPACE USER$.PUBLIC."broadcast-data-platform-handson-ja"
  PROJECT_ROOT = 'dbt'
  DBT_VERSION = '1.9.4'
  ARGS = 'build --target common --select tag:common --indirect-selection cautious';
```

完成するのは `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY` です。
既に作った5局のマートを読み取るだけで、局別の整形や集計をやり直す処理ではありません。

✅ **1モデルと3テストが成功し、`ERROR=0 SKIP=0` になっていること**を確認します。
作成SQLとテストSQLの計算先は `BCAST_PLATFORM_COMMON_WH` です。
局別テーブルが作り直されていないこともクエリ履歴で確認します。

> ⚠️ `--select +viewing_daily`、`--select +tag:common`、対象指定なしの全体buildには変更しないでください。
> `+` は前段の処理も選ぶ指定なので、局別処理まで共通WHで動かすことにつながります。
> 教材には指定の混在を拒否する補助処理がありますが、基本は上記のSQLをそのまま使います。

### 統合結果を確認する

[sql/03_check_common.sql](../sql/03_check_common.sql) を開き、区切って実行します。

| 確認 | 期待する結果 |
|---|---|
| 共通マートの行数 | 18,000行 |
| 全期間・全5局のリーチ | 200端末 |
| 総視聴回数 | 18,000回 |
| 総視聴時間 | 約667,632.866664分 |
| 局別マート合計との比較 | 行数差・回数差は0、分数差の絶対値は0.000001分以下 |

最後のSQLは、説明用の3記録をその場で集計する例です。
**マート2行・視聴3回・リーチ1端末・45分**になることを確認しましょう。
保存済みの教材データは変更しません。

ここまで成功したら、[第3章 MLOps](03_mlops.md)へ進みます。

## 何をテストしたのか、振り返る

各局の7テストは、次の内容です。

| 対象 | テスト内容 | 見つけたい問題の例 |
|---|---|---|
| 整形後の表 | 必須列にNULLがないか | 端末IDや開始時刻が空欄 |
| 整形後の表 | イベントIDが局内で一意か | 同じ記録が重複 |
| 整形後の表 | 局番号が自局だけか | NW01の表にNW02が混入 |
| 整形後の表 | ジャンルが指定の5種類か | 整形できない表記が残る |
| 整形後の表 | 終了が開始より後で、分数が正か | 終了時刻が開始時刻より前 |
| 日次マート | 必須列にNULLがないか | 集計キーや数値が空欄 |
| 日次マート | 局・端末・日付・ジャンルの組が一意か | 同じ集計行が二重にある |

共通マートでは、必須列のNULL、4列の組の一意性、局別マートとの局ごとの件数一致を調べます。
**各局7件 × 5局 ＋ 共通3件 ＝ 合計38件**です。
38種類の別々のルールがあるのではなく、同じ検査を局ごとに適用しています。

### テストが成功すれば、すべて正しい？

いいえ。このテストは、データの正しさをすべて保証するものではありません。
たとえば表が空でも、「重複がない」というテストは成功し得ます。
そのため、手順では件数・回数・時間も別に確認しました。

また、`NEWS` を誤って `SPORTS` に変更しても、どちらも許可したジャンルなので、許容値のテストだけでは検出できません。
テストの範囲と、確認できていないことを区別して使いましょう。

テスト失敗で、既に作ったテーブルが自動で元へ戻るわけではありません。
失敗したときは後の章へ進まず、修正後に対象局とcommonを必要に応じて再実行します。

## 補足：コードをもう少し読みたい方へ

ここからは仕組みを詳しく知りたい方向けです。本編の操作を終えてから読んで構いません。

### テーブルの作り方と1行の意味

dbtが作る11個の出力は、すべて計算結果を保存するテーブルです。
設定上の `materialized: table` がこれに当たります。参照時まで計算を先送りするビューではありません。

| 出力 | 1行が表すもの |
|---|---|
| 各局の `CLEAN_VIEWING` | その局の視聴記録1件 |
| 各局の `MART_DEVICE_DAILY` | 局・端末・日付・ジャンルごとの集計 |
| `COMMON.VIEWING_DAILY` | 局別マートと同じ単位の集計 |

「1行が何を表すか」をデータの**粒度**と呼びます。
同じ端末が複数日・複数局に登場するので、端末IDだけでは集計行を一意にできません。
機械学習の正解ラベル・予測値は、このdbt処理には含めていません。

### 表記と日時の扱い

- 全角→半角の変換は、5つのジャンルの指定表記だけに対応します。任意の文字列を自動正規化する処理ではありません。
- 視聴日は開始日時から取り出します。日付をまたぐ入力があっても開始日の実績として扱い、日別には分割しません。配布データ自体には日跨ぎはありません。
- 視聴時間はミリ秒単位の差を60,000で割り、小数点以下6桁へ丸めた分数をFLOATへ変換します。厳密な無丸め計算ではありません。
- 日時型 `TIMESTAMP_NTZ` にはタイムゾーンの変換を加えません。

### その他のファイル

| ファイル | 役割 |
|---|---|
| [dbt_project.yml](../dbt/dbt_project.yml) | プロジェクト名、保存するスキーマ、タグ、table指定 |
| [selectors.yml](../dbt/selectors.yml) | 局別・commonの選択条件に名前を付ける |
| [generate_schema_name.sql](../dbt/macros/generate_schema_name.sql) | スキーマ名を `NW01_NW01` などへ連結せず、そのまま使う |
| [assert_execution_scope.sql](../dbt/macros/assert_execution_scope.sql) | target・ロール・WH・選択範囲の不一致を拒否する |
| [models/nw01/](../dbt/models/nw01/) | NW01の2モデル。他局も同じフォルダ構成 |
| [models/schema.yml](../dbt/models/schema.yml) | 列の説明と共通のテスト定義 |
| [tests/](../dbt/tests/) | 区間検査5件と統合件数検査1件 |

`profiles.yml` の `account: ''` と `user: ''` は、Snowflake内で実行するため意図的に空欄です。
パスワード・鍵・トークンを追記しないでください。ローカルdbt Core用の接続設定ではありません。
外部パッケージを使わないため、`dbt deps` も不要です。

この教材は **1つのdbtプロジェクトと6つのtarget** で構成しています。
局ごとに独立したdbtプロジェクトを連携するdbt Meshの構成ではありません。

### `ref()`、タグ、テストの関係

`ref()` は、別のdbtモデルを参照するための記述です。
参照先のテーブル名を解決し、処理の前後関係もdbtへ伝えます。この関係図をDAGと呼びます。

commonのSQLは5局のマートを `ref()` で読みますが、選択したのはcommonだけなので、既存マートを使います。
common targetでも、参照先は `BCAST_PLATFORM_HANDSON.NW01.MART_DEVICE_DAILY` などの局別スキーマのままです。

列定義に付ける共通の検査がgeneric test、個別のSQLとして書く検査がsingular testです。
局別の区間テストは自局だけを参照します。統合件数テストは5局とcommonの6モデルを参照します。

`cautious` は、依存先がすべて選ばれたテストだけを自動選択します。
一方、commonの件数テストは `common` タグで明示的に選ぶので実行されます。
`--select viewing_daily` だけへ変更すると、件数テストが対象から外れるため、代替手順にしないでください。

`--selector nw01` は、教材では `--select tag:nw01 --indirect-selection cautious` と同じ選択です。
実行先を選ぶ `--target nw01` は、いずれの場合も別途必要です。

### テストだけをやり直す場合

次はNW03とcommonの例です。テーブルは作り直さず、既存の結果を検査します。
commonのテストは、common build後にだけ実行してください。

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
テストだけ、または作成だけの `run` は、本編で求めるbuild成功の代わりにはなりません。

補助macroは実行指定の間違いを検出するものです。
任意のSQLや変更済みプロジェクトまで制限するアクセス制御でも、過去5回の成功を管理する仕組みでもありません。
dbtの実行基盤の消費と、各ウェアハウスで行う加工・テストSQLの消費も別です。

## 参考

dbt project objectを使う局別処理はトライアルで確認しています。
この章のGit Workspace経路の通し操作は未確認のため、画面・実行結果が手順と異なる場合は講師に確認してください。

- [EXECUTE DBT PROJECT](https://docs.snowflake.com/en/sql-reference/sql/execute-dbt-project)
- [対応dbt Coreバージョン](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions)