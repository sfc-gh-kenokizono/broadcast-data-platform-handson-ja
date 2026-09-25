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

### dbtはいつ動くのか

dbtは、ソースデータを監視して動き続ける仕組みではありません。**BuildやRunを開始したときに処理するバッチ方式**です。
この教材では流れを確認するため、人がNW01〜NW05とcommonを1回ずつBuildします。今回の全モデルは `table` として保存されるため、Buildのたびに対象テーブルを作り直します。

本番では、この手操作を自動化できます。プロジェクトをdbt project objectとしてデプロイし、Snowflake Tasksから決まった時刻にBuildを起動します。NW01〜NW05を実行し、すべて成功した後にcommonを実行する順序もTask graphで設定できます。Airflowなどの外部オーケストレーターから起動する方法もあります。

| dbt | Dynamic Table |
|---|---|
| BuildやRunが呼ばれたときに変換とテストを実行 | Snowflakeが `TARGET_LAG` に基づいて更新を管理 |
| 基本はバッチ処理。定期実行にはTaskなどを使う | 指定した鮮度を保つように継続的に更新 |
| Jinja、macro、テスト、DAGによる開発管理が得意 | 宣言したSELECT結果の鮮度維持が得意 |

この章は自動スケジュールの作成ではなく、1回のdbt Buildで何が起きるかをGUIで確認する章です。

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
| 青いコマンドボタン | `コンパイル` / `Build` | 選んだコマンドを開始 |
| コマンドボタン右側の▼ | 設定パネルを開く | コマンドの選択と「追加のフラグ」の入力に使う |

添付画面の実行結果領域には **Output、DAG、Performance** タブがあります。画面の版によって表示名やタブ構成が少し異なる場合があります。

- **Output**: 実行コマンド、標準出力、成功・失敗を確認します。
- **DAG**: source、モデル、テストの依存関係を図で確認します。
- **Performance**: 実行時間など、直近実行の性能情報を確認します。

Profileとselectorは役割が違います。

| 対象 | Profile | 追加のフラグ | 保存先 | ウェアハウス |
|---|---|---|---|---|
| NW01 | `nw01` | `--selector nw01` | `NW01` | `BCAST_PLATFORM_NW01_WH` |
| NW02 | `nw02` | `--selector nw02` | `NW02` | `BCAST_PLATFORM_NW02_WH` |
| NW03 | `nw03` | `--selector nw03` | `NW03` | `BCAST_PLATFORM_NW03_WH` |
| NW04 | `nw04` | `--selector nw04` | `NW04` | `BCAST_PLATFORM_NW04_WH` |
| NW05 | `nw05` | `--selector nw05` | `NW05` | `BCAST_PLATFORM_NW05_WH` |
| 5局統合 | `common` | `--selector common` | `COMMON` | `BCAST_PLATFORM_COMMON_WH` |

**selectorは実行するモデルとテストを選び、Profileはロール・DB・基本スキーマ・WHの組を選びます。必ず同じ名前の組み合わせにします。** 実際の出力スキーマは、モデルフォルダごとの設定も使って `NW01` などに固定されます。

3つの設定を、行き先と荷物にたとえると次のようになります。

- **Profile**: どの作業場所を使うか。ロール、データベース、基本スキーマ、ウェアハウスをまとめて選びます。
- **Environment**: `env.yml` から追加設定を渡す場所です。この教材では追加設定を使わないため、常に `環境なし` のままにします。Profileやselectorの代わりではありません。
- **selector**: プロジェクトの中から、今回処理するモデルとテストだけを選ぶ目印です。たとえば `--selector nw01` は、NW01用の4モデルと15テストに対象を絞ります。

つまり、`Profile=nw01` だけでは「NW01用の作業場所」を選んだだけです。`--selector nw01` も指定して、初めて「NW01の処理だけを、その作業場所で実行する」という組み合わせになります。

## 3. NW01をCompileして中身を見る

1. Projectが `dbt` であることを確認します。
2. Profileで `nw01` を選びます。
3. Environmentは `環境なし` のままにします。
4. Commandで `コンパイル` / `Compile` を選びます。
5. `コンパイル` ボタン右側の▼を開き、**追加のフラグ**の下に薄く表示される `オプション` 欄をクリックし、`--selector nw01` を入力します。
6. 青い `コンパイル` ボタンを押して実行します。

### DAG画面の見方

DAGは、データがどこから来て、どの順番で加工されるかを示す**処理の地図**です。

- 四角い箱は、RAW入力を表すsource、テーブルを作るモデル、実行前後の安全確認を行うoperationです。今回のWorkspace画面では、data testはDAGの箱として表示されません。
- 箱を結ぶ線は依存関係です。入力側から出力側へたどると、処理の順番が分かります。
- 箱を選ぶと、そのノードの名前や前後のつながりを確認できます。

アンカーノードは、DAGの中で「ここを中心に見たい」と指定する箱です。地図の注目地点のようなもので、選んでもモデル実行やテーブル作成は始まりません。`clean_viewing_nw01` をアンカーにすると、その前のRAW入力と後続モデルを見やすくできます。

画面上部の操作は、すべて使う必要はありません。表示名やアイコンはWorkspaceの版によって少し異なる場合があります。

| 操作 | 何が変わるか | この章での使い方 |
|---|---|---|
| `＋` / `－` | 図を拡大・縮小する | 文字や全体が見づらいときだけ使う |
| 全体表示のアイコン | 表示中のDAG全体が画面に収まるよう調整する | 図が画面外へ出たときに使う |
| 配置を戻すアイコン | 図の位置や拡大率を初期状態へ戻す | 操作中に見失ったときに使う |
| アンカーノード | 注目するsource、モデル、テストを1つ選ぶ | `clean_viewing_nw01` を選ぶ |
| 上流 | 選んだノードより前の処理を何段表示するかを指定する | RAW入力側を確認する。通常は初期値のままでよい |
| 下流 | 選んだノードより後の処理を何段表示するかを指定する | 後続モデルを確認する。通常は初期値のままでよい |
| 表示 | source、モデル、operationなど、表示するノードを絞る | この章では `すべて` のままにする |
| 列を表示 | Horizon Catalogから列と列単位のつながりを読み込む | この章の必須確認にはしない |

今回は次のつながりを確認できれば十分です。

```text
RAW.VIEWING_LOG_NW01
  ↓
clean_viewing_nw01
  ├→ mart_device_daily_nw01
  └→ viewing_minutes_nw01
        ↓
      mart_minute_audience_nw01
```

`--selector nw01` を付けずにCompileした場合は、ほかの局を含むプロジェクト全体がDAGへ表示されます。Compileはテーブルを作成・変更しないため、そのまま確認を続けて問題ありません。NW02以降でCompileを繰り返す必要もありません。

今回のプロジェクト全体をCompileすると、DAGには **29ノード** と表示されます。内訳は、22モデル、5つのRAW source、実行前後の安全確認を行う2つのoperationです。Compileログに表示される81個のdata testは、この29ノードには含まれません。NW01の15テストは、後続のBuild結果をOutputで確認します。

DAG内の緑色の **成功** は、直前に実行したコマンドにおける、そのノードの正常終了を表します。今回の画面ではCompile直後なので、モデルの定義をSnowflake SQLへ変換できたという意味です。**テーブル作成に成功したという意味ではありません。** RAW sourceは変換・作成するモデルではなく、すでに存在する入力テーブルなので、通常はCompileの成功バッジが付きません。

`on-run-start` と `on-run-end` のoperationは、実行範囲や結果を確認する安全チェックです。データを次のテーブルへ渡す処理ではないため、DAG上で線がつながっていなくても問題ありません。

**列を表示** は、DAGの箱に列名を展開する補助機能です。列情報はdbtのBuild結果そのものではなく、Snowflake Horizon Catalogから別に読み込みます。そのため、Buildが成功していても、カタログへの反映待ち、権限、またはWorkspace側の読み込み状態によって `列のロードに失敗しました` と表示される場合があります。これはモデル作成やテストの失敗を意味しません。この章では列表示を成功条件にせず、DAGの箱と線で処理順を確認します。

### Compileの確認

- **Output** でCompileコマンドの成功を確認します。Compileなので出力テーブルはまだ作られません。
- **DAG** を開き、アンカーノードで `clean_viewing_nw01` を選び、RAW入力と後続モデルのつながりを確認します。テスト件数はここでは確認しません。
- DAGのノードまたはファイル一覧から `clean_viewing_nw01.sql` を開きます。
- エディタ右上の **View Compiled SQL** を選びます。
- 左側の短いmacro呼び出しと、右側の展開済みSQLを見比べます。

ここで、`source()` が実テーブル名へ、macroが実際の共通SQLへ展開されることを確認できます。
NW01のテーブル作成と15テストの成功は、次のBuild直後のOutputで確認します。Compile直後の成功バッジだけでは、テーブル作成やテストの成功とは判定しません。

## 4. NW01をBuildする

Compileの後にRunへ切り替えず、次はBuildを実行します。

1. Projectを `dbt`、Profileを `nw01`、Environmentを `環境なし` にします。
2. Commandで `Build` を選びます。
3. `Build` ボタン右側の▼を開き、**追加のフラグ**の下に薄く表示される `オプション` 欄をクリックします。
4. `オプション` を置き換える形で `--selector nw01` を入力します。
5. 青い `Build` ボタンを押して実行します。
6. Output先頭の生成コマンドが `build --target nw01 --selector nw01` になっていることを確認します。
7. Outputに `build --target nw01` しか表示されない場合は、selectorが反映されていません。次の局へ進まず、追加のフラグを設定してBuildを再実行します。

`build --target nw01` だけの場合は、NW01用の環境でプロジェクト全体をBuildしようとします。このプロジェクトでは実行前の安全確認が対象範囲の不一致を検出し、`Selection/target mismatch` で停止します。データ処理に進む前の安全停止なので、`--selector nw01` を追加して再実行します。

**成功の目印:** 実行が成功し、モデル4件・テスト15件がすべて成功、エラー0件・スキップ0件です。ログには `Completed successfully` や `ERROR=0 SKIP=0` と表示されます。

### Outputの確認方法

Outputは、画面下部にある**実行ログ**です。dbtが何を実行し、どこまで成功したかを文字で確認します。

1. Buildが終わったら、画面下部の **出力 / Output** タブを選びます。すでにログが表示されている場合は、その画面がOutputです。
2. ログを一番下までスクロールします。
3. 最後の数行に `Completed successfully` があることを確認します。
4. その下の集計が `PASS=21 WARN=0 ERROR=0 SKIP=0 TOTAL=21` になっていることを確認します。

NW01の `TOTAL=21` の内訳は、**4モデル + 15テスト + 実行前後の安全確認2件**です。画面に `Finished running 2 project hooks, 4 table models, 15 data tests` と表示されていれば、対象も正しく絞れています。

```text
Completed successfully
Done. PASS=21 WARN=0 ERROR=0 SKIP=0 TOTAL=21
```

緑色の `コマンド実行が完了しました` だけでなく、必ずこの最終集計まで確認します。`ERROR` または `SKIP` が1件以上なら、次の局へ進みません。

### Build後にDAGを見る

はい、NW01のBuild成功をOutputで確認した後は、**DAGタブを開いて構いません**。ただし、DAGとOutputでは確認する目的が違います。

- **Output**: 4モデルと15テストが実際に成功したかを確認する場所
- **DAG**: RAW入力から4モデルへ、どの順番でデータが流れるかを見る場所

DAGではアンカーノードに `clean_viewing_nw01` を選び、NW01の入力と後続モデルの流れを確認します。テスト15件はDAG上ではなく、Outputの `15 data tests` と最終集計で確認します。**列を表示** が失敗しても、Outputが `ERROR=0 SKIP=0` ならNW01のBuildは成功です。この章では再実行や権限変更を行わず、そのまま次へ進みます。

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

1. Profile=`nw02`、追加のフラグ=`--selector nw02` でBuildし、成功を確認します。
2. Profile=`nw03`、追加のフラグ=`--selector nw03` でBuildし、成功を確認します。
3. Profile=`nw04`、追加のフラグ=`--selector nw04` でBuildし、成功を確認します。
4. Profile=`nw05`、追加のフラグ=`--selector nw05` でBuildし、成功を確認します。

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
- エラー文、局名、Profile、追加のフラグを確認します。
- 原因を直し、その局と同じ組み合わせでBuildを再実行します。
- 今回のOutputと期待件数を再確認します。

Buildは1つの大きなトランザクションではありません。テストや後半のモデルが失敗しても、途中まで作成したテーブルが残ることがあります。残っているテーブルだけを見て成功と判断しないでください。

この教材では、5局の成功を人が確認します。**今回の一連のBuildログだけ**を使い、過去の成功ログや残っているテーブルを今回の成功とみなしません。5局を確認している途中で、入力データやdbtファイルを変更しないでください。

## 6. 5局すべての成功後にcommonをBuildする

NW01〜NW05の5局すべてが成功したことを確認してから実行します。これが **5局ゲート** です。

1. Profileを `common` に変更します。
2. Commandは `Build` を選びます。
3. `Build` ボタン右側の▼を開き、**追加のフラグ**の `オプション` 欄に `--selector common` を入力します。
4. 青い `Build` ボタンを押して実行します。

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

## 補足：パイプラインの加工・数え方・テスト

ここからは任意です。本編の操作後に、dbtがどのようにデータを加工し、何をテストしているかを確認します。

### 1. `CLEAN_VIEWING`：RAWを整える

- RAW自体は変更せず、整形結果を局別の別テーブルへ保存します。
- 入力6列が完全一致する行を重複除外します。
- 次の不正な視聴区間を除外します。
  - 終了時刻が開始時刻以前
  - 視聴時間が24時間を超える
- ジャンルの前後の空白・大文字小文字・指定された全角表記を整え、次の8種類へ統一します。
  - `NEWS`、`DRAMA`、`VARIETY`、`ANIME`
  - `SPORTS`、`MUSIC`、`MOVIE`、`INFO`
- 開始時刻から終了時刻までの経過時間を、丸めずに分へ変換して `VIEW_MINUTES` に保存します。
- 配布RAW 1,050,648行から、完全重複300行、時刻逆転200行、24時間超148行を除き、1,050,000行になります。
- 同じイベントIDで内容が異なる行は勝手に統合せず、テストで検出します。

### 2. `MART_DEVICE_DAILY`：日次にまとめる

- 1行の単位は、**局・端末・視聴開始日・ジャンル**です。
- 同じ単位に属する視聴記録をまとめ、次を保存します。
  - `SESSION_COUNT`: 視聴記録の件数
  - `VIEW_MINUTES`: 視聴時間の合計
- 日付をまたぐ視聴も、全時間を開始日に計上します。
- 1,050,000件の視聴記録は1,045,120行にまとまりますが、`SESSION_COUNT` の合計は1,050,000回のままです。

### 3. `VIEWING_MINUTES`：1分枠へ展開する

- 各視聴区間を、少しでも重なる1分枠ごとの行へ展開します。
- 開始時刻は含み、終了時刻は含みません。
- たとえば08:00:50〜08:01:10の20秒間は、08:00と08:01の2つの分枠に入ります。
- 1行の単位は、**局・イベント・分**です。
- 全5局で、局・端末・分の組は延べ13,532,927件です。

### 4. `MART_MINUTE_AUDIENCE`：分ごとの端末数を数える

- 1行の単位は、**局・日付・分**です。
- 同じ分に複数の視聴記録がある端末は、1台として重複除外します。
- `VIEWING_DEVICES` は、その1分枠と少しでも重なった端末数です。
- 瞬間の同時視聴台数、視聴人数、局をまたいで重複除外したリーチではありません。

### 5. `COMMON`：5局の完成済みマートをまとめる

- `COMMON.VIEWING_DAILY` は、5局の `MART_DEVICE_DAILY` を `UNION ALL` します。
- `COMMON.MINUTE_AUDIENCE` は、5局の `MART_MINUTE_AUDIENCE` を `UNION ALL` します。
- RAWの整形や1分枠への展開はやり直しません。
- 局別の行はそのまま残します。局別端末数の単純合計は、全5局の重複除外済みリーチではありません。

### 6. Buildで実行するテスト

各局では、4モデルの作成に加えて15件のテストを実行します。

- `CLEAN_VIEWING`を確認します。
  - 必須列にNULLがない
  - `NETWORK_ID` が対象局と一致する
  - `EVENT_ID` が局内で一意
  - `DEVICE_ID` が教材の `C000001`〜`C020000`
  - ジャンルが8種類のいずれか
  - 視聴区間と `VIEW_MINUTES` が正しい
- `MART_DEVICE_DAILY`を確認します。
  - 必須列にNULLがない
  - 局・端末・日付・ジャンルの組が一意
  - 有効なRAW、整形後、日次マートで、視聴回数と時間が一致する
- `VIEWING_MINUTES`を確認します。
  - 必須列にNULLがない
  - 局・イベント・分の組が一意
  - イベントごとの最初の分・最後の分・分枠数・日付が正しい
- `MART_MINUTE_AUDIENCE`を確認します。
  - 必須列にNULLがない
  - 局・日付・分の組が一意
  - 分展開から数え直した重複なし端末数と一致する

commonでは6件のテストを実行します。

- 2つの共通表で、必須列にNULLがないことを確認します。
- 2つの共通表で、1行の単位が重複していないことを確認します。
- 局別マートと共通表の行数・視聴回数・視聴時間・分別端末数が一致することを確認します。

テスト数は次のとおりです。

- 各局: 15件 × 5局 = 75件
- common: 6件
- 合計: **81件**

`dbt/tests` にある22個のSQLファイル数と、実行される81個のテストノード数は異なります。汎用テストは `schema.yml` の定義から局別・モデル別に展開されるためです。

### 7. 数値を読むときの注意

- 総視聴時間は、750,698,536秒 ÷ 60 = 約12,511,642.266667分です。
- 視聴時間はFLOATで計算するため、最終確認では微小な丸め誤差を許容します。
- 行数、視聴回数、端末数、視聴時間は、それぞれ数えている対象が異なります。

## 補足：profiles.ymlと認証情報

`profiles.yml` の6つのtargetは、Profileドロップダウンの `nw01`〜`nw05`、`common` として表示されます。保存先スキーマは `dbt_project.yml` のフォルダ別設定と `generate_schema_name.sql` も使って、局別の `NW01`〜`NW05` と `COMMON` に固定します。
`account: ''` と `user: ''` は、Snowflake内の現在のアカウントとユーザーで実行するため意図的に空欄です。

### `USER$.PUBLIC` が空に見える理由

- `USER$.PUBLIC."broadcast-data-platform-handson-ja"` は、テーブルの保存先ではなく**Workspaceオブジェクトの場所**です。
- 画面左のデータベースエクスプローラーで `USER$.PUBLIC` の「オブジェクト」を開いても、通常のテーブルやビューは表示されません。
- 実行コマンドは、このWorkspace内の `/dbt` フォルダからプロジェクトファイルを読み込みます。
- 作成されるテーブルの保存先は、`dbt_project.yml` と `profiles.yml` により次へ固定されています。
  - 局別: `BCAST_PLATFORM_HANDSON.NW01`〜`NW05`
  - 共通: `BCAST_PLATFORM_HANDSON.COMMON`
- Workspaceのファイルは、データベースエクスプローラーではなく画面上部の**ワークスペース**タブから確認します。

つまり、`USER$.PUBLIC` が空に見えても正常です。Workspaceは「dbtファイルを置く場所」、`NW01`〜`NW05` と `COMMON` は「Build結果のテーブルを置く場所」です。

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

SQLでは `--target` がUIのProfile、`--selector` がUIの追加のフラグに相当します。ここでも同じ名前を組み合わせ、commonにグラフ展開の `+` を付けません。

## 参考

画面や実行結果が手順と異なる場合は、全体Buildへ変更せず講師へ確認してください。

- [Workspaces for dbt Projects on Snowflake](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-using-workspaces)
- [EXECUTE DBT PROJECT](https://docs.snowflake.com/en/sql-reference/sql/execute-dbt-project)
- [対応dbt Coreバージョン](https://docs.snowflake.com/en/user-guide/data-engineering/dbt-projects-on-snowflake-dbt-core-versions)