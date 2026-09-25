# 第4章 視聴実績と予測をグラフで見る

第2章の分析表と第3章の予測結果を、期間や放送局を選べるStreamlit画面で確認します。本編はSnowsightの **Projects → Streamlit** でwarehouse runtimeを使い、最後にアナリストロールで共有を確認します。Git Workspaceでの開発は任意の補足です。

## 最初に行う操作

| 順番 | どこを開く | 正確な操作 | 成功の合図 |
|---:|---|---|---|
| 1 | Snowsightの **Projects → Streamlit** | **+ Streamlit App** を開き、**Run on warehouse** を選ぶ | warehouse runtimeの作成画面が表示される |
| 2 | Streamlit作成画面 | Query / App warehouseを `BCAST_PLATFORM_COMMON_WH` にし、リポジトリから作成するか3ファイルを配置する | `streamlit_app.py`、`queries.py`、`environment.yml` がそろう |
| 3 | Streamlit画面 | **Run** を選ぶ | 画面上部に「5局の視聴データ」と表示される |
| 4 | 「視聴実績・推移」タブ | 全5局、2026年5月1日〜7月31日を選ぶ | 20,000台、1,050,000回、12,511,642.3分と表示される |
| 5 | 「分内視聴端末数」「F1在籍の予測」タブ | 1日を選んで「分別曲線を表示」をオンにし、「予測結果を表示」もオンにする | 5系列と、欠損のない予測・モデル版・閾値0.46が表示される |
| 6 | Projects → Streamlit | `BCAST_PLATFORM_HANDSON.MART.VIEWING_APP` を公開し、`BCAST_PLATFORM_ANALYST_ROLE` に `USAGE` を付与する | アナリストロールでKPI・グラフ・予測を見られる |

**共有先に `PUBLIC` を指定しないでください。** このアプリは所有者権限でデータを読みます。所有者は `ACCOUNTADMIN` ではなく `BCAST_PLATFORM_ENGINEER_ROLE` にします。利用者ごとの行制御は実装していないため、教材データだけを共有し、正解ラベルを画面へ追加しません。

## 1. 前提と3ファイルを確認する

- 第2章の5局とcommonのbuild・テストが完了している。
- `BCAST_PLATFORM_ENGINEER_ROLE` で `COMMON.VIEWING_DAILY`、`COMMON.MINUTE_AUDIENCE`、共通WHを利用できる。
- 第3章を実施した場合は、20,000台の保存・照合とNotebookサービス停止まで完了している。
- 同名の `VIEWING_APP` がある場合は講師へ用途を確認し、上書きしない。

| ファイル | 役割 |
|---|---|
| [streamlit_app.py](../app/streamlit_app.py) | 画面、入力欄、グラフ |
| [queries.py](../app/queries.py) | 集計SQL |
| [environment.yml](../app/environment.yml) | warehouse runtime用のPython・パッケージ指定 |

3ファイルは同じ `app` フォルダに置きます。入口だけ配置すると、集計SQLのファイルが見つからず起動できません。

## 2. warehouse runtimeでRunする（推奨・本編）

Snowsightの **Projects → Streamlit → + Streamlit App** を開き、**Run on warehouse** を選びます。本編ではPythonとSQLをウェアハウスで実行するため、compute poolは不要です。

| 項目 | 値 |
|---|---|
| リポジトリ | `BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO` |
| ブランチ | 講師指定。通常は `main` |
| 入口 | `app/streamlit_app.py` |
| アプリ名 | `VIEWING_APP` |
| DB / スキーマ | `BCAST_PLATFORM_HANDSON` / `MART` |
| Query / App warehouse | `BCAST_PLATFORM_COMMON_WH` |

**Create from repository** があれば表の値で取り込みます。なければ新規アプリを作成し、教材の3ファイルを同じフォルダへアップロードします。Python 3.11、Streamlit 1.50.0、pandas 2系、Snowparkを `environment.yml` とPackages欄で確認し、**Run** を選びます。画面上部に **「5局の視聴データ」** が表示されれば成功です。

**Run on warehouse** が選べない場合は、準備なしに別方式や未確認のCLI手順へ切り替えず講師へ確認します。Streamlit側の編集はGitHubへ自動反映されるとは限らず、この章でcommit・pushは不要です。教材アプリは外部API・画像・フォント・CSSを取得しません。

## 3. KPIとグラフを確認する

左側で全5局、2026年5月1日〜7月31日を選び、「視聴実績・推移」タブを開きます。

| KPI | 意味 | V2全5局・全期間の期待値 |
|---|---|---:|
| 期間全体のリーチ | 1回以上視聴した端末の重複なし件数 | 20,000台 |
| 総視聴時間 | 各視聴区間の経過秒数 ÷ 60の合計 | 12,511,642.3分 |
| 総視聴回数 | 整形済み視聴区間の `SESSION_COUNT` 合計 | 1,050,000回 |

未丸めの総視聴時間は約12,511,642.266667分です。画面は小数第1位まで表示するため、SQL値も小数第1位へ丸めて比較します。未丸めのSQL集計値同士を比べる場合だけ、[第2章](02_dbt.md)の許容誤差を使います。

共通表の6列は `NETWORK_ID`、`DEVICE_ID`、`VIEW_DATE`、`GENRE`、`SESSION_COUNT`、`VIEW_MINUTES` です。端末IDは `C000001`〜`C020000`、ジャンルはNEWS、DRAMA、VARIETY、ANIME、SPORTS、MUSIC、MOVIE、INFOの8種類です。全区間を開始日と開始時ジャンルへ計上するため、番組ごとの厳密な視聴時間ではありません。

次も操作してみましょう。

1. NW01だけにして、日別グラフと局別内訳が変わることを確認します。
2. 1日または数日へ期間を変えます。
3. 局をすべて外し、「放送局を1つ以上選んでください」と表示されることを確認します。
4. 日付を片方だけにし、開始日・終了日の案内を確認します。

局別・日別・ジャンル別のリーチは足しません。同じ端末が複数局を見ても、選択範囲全体では1台です。視聴回数も表の行数ではなく `SESSION_COUNT` を合計します。単位は端末で、人数や世帯数ではありません。

## 4. 分別曲線を確認する

「分内視聴端末数」タブで **1日だけ**を選び、「分別曲線を表示」をオンにします。日付は左側の期間とは別、放送局の選択は共通です。全5局ならNW01〜NW05の5系列が表示されます。

参照列は `COMMON.MINUTE_AUDIENCE` の `NETWORK_ID`、`VIEW_DATE`、`MINUTE_AT`、`VIEWING_DEVICES` だけです。分内視聴端末数は、その1分に少しでも視聴した端末の重複なし件数です。08:00:59〜08:01:01なら08:00と08:01の両方に数えます。同時視聴者数ではなく、局をまたぐ合計線も表示しません。欠損をゼロ補完・補間せず、曲線の面積を正確な総視聴時間とも扱いません。

## 5. 予測結果を確認する

「F1在籍の予測」タブで **「予測結果を表示」** をオンにします。オンにするまでは予測テーブルへ問い合わせません。

1. 確率ヒストグラム、予測0・1の内訳、モデル名、版、保存閾値を第3章と比べます。
2. 0・1の合計が、同じ条件の実績リーチと一致することを確認します。
3. 予測欠損や不正値があれば、条件を変えて隠さず第3章の保存・照合を確認します。

参照する `ML.PREDICTIONS` は `DEVICE_ID`、`PROB_F1`、`PREDICTED_HAS_F1`、`MODEL_NAME`、`MODEL_VERSION`、`PREDICTED_AT`、`PREDICTION_THRESHOLD`、`DATASET_VERSION` の8列です。モデルは `TV_F1_PRESENCE_MODEL`、初期版は `V2`、登録済み環境では第3章で選んだ未使用の `V3` などです。閾値はVALIDで選んだ0.46で、0.5へ読み替えません。日時はUTCの `TIMESTAMP_NTZ`、データ版は `F1_SIGNAL_V2` です。

ヒストグラムは0.1刻みで、最後の区間だけ1.0を含みます。グラフと表は選択期間・局に視聴実績がある端末だけが対象です。同じ端末は重複を除いてから予測へ結び付けます。期間や局の変更は表示対象の変更で、再学習ではありません。

F1は合成世帯に20〜34歳の女性が在籍するかという期間不変の属性です。現在の視聴者、実際のF1視聴者数、確認済み世帯数ではありません。V2は学習しやすい関係を強めた合成データで、確率の校正後も現実の精度を保証せず、確率を人数や全国推計へ換算しません。`RAW.DEVICE_LABELS` の正解ラベルや非公開の世帯構成は読み取りも表示もしません。

| 表示 | 確認すること |
|---|---|
| 予測未作成・参照権限なし | 第3章の保存と所有者ロールの参照権限 |
| 空・欠損・不正な確率、閾値、ID、モデル情報 | 第3章の20,000台の保存・照合 |
| 列不足・データ版不一致 | 版名だけを書き換えず講師へ確認 |
| Snowflake接続切れ | アプリを再起動。未作成・ゼロ件とは区別する |

予測に問題があっても実績画面は利用できます。「再読込」はキャッシュを捨てて最新結果を取得する操作で、データ更新や再学習ではありません。

## 6. Deployしてアナリスト共有を確認する

1. **Projects → Streamlit** で `BCAST_PLATFORM_HANDSON.MART.VIEWING_APP` を開き、Query / App warehouseが `BCAST_PLATFORM_COMMON_WH` であることを確認します。
2. DB・スキーマ・アプリ名と、所有者が `BCAST_PLATFORM_ENGINEER_ROLE` であることを確認します。
3. **Share / 共有** で `BCAST_PLATFORM_ANALYST_ROLE` に閲覧用の `USAGE` を付与します。
4. UIに **Publish / 公開** があれば、意図した版を確認して公開します。
5. 共有用の閲覧画面を開き直し、アナリストロールでKPI、フィルター、日別・内訳・分別曲線・予測の各グラフを確認します。

`USAGE` は利用権限で、編集権限や所有権ではありません。閲覧者にはアプリの `USAGE` に加え、DB・MART・共通WHの `USAGE` が必要です。所有者にはDB・MART・COMMON・共通WHの利用権限、MARTへのアプリ作成権限、共通マートの `SELECT` が必要です。予測表示にはMLスキーマと `PREDICTIONS` の参照権限も必要です。共有のためにRAWや正解ラベルを公開しません。

他の強い権限が同時に有効だと、アナリスト権限だけで見られたか判断できません。講師の案内に従い、必要ならアナリストロールを付与した別ユーザーで確認します。閲覧用ロールで確認できるまで、共有成功とはしません。

## 任意: Git Workspaceで開発する補足経路

本編を完了した場合は実行不要です。Workspaceで開発アプリを動かす場合だけ、講師の案内に従って使います。この方式ではPython用のcompute poolが別途必要で、`BCAST_PLATFORM_COMMON_WH` はSQL用です。

1. Git Workspaceで `app/streamlit_app.py` を開き、同じフォルダの `queries.py` を確認します。
2. 案内がない場合は **+ Add new → Streamlit app** で作ったフォルダに教材のPython 2ファイルを配置します。元の教材ファイルは上書きしません。
3. **Settings / Execution** でSQL用WHを `BCAST_PLATFORM_COMMON_WH` にします。既定WHなどのユーザー設定を勝手に変更しません。
4. 講師指定のcompute poolと利用権限を確認し、**Run** を選びます。
5. 必要な場合だけ **Deploy** で `BCAST_PLATFORM_HANDSON.MART.VIEWING_APP` へ公開し、「6. Deployしてアナリスト共有を確認する」に戻ります。

Workspaceではランタイム組み込みの `streamlit`、`pandas`、`snowflake-snowpark-python` を使い、warehouse runtime用の `environment.yml` は依存設定に使いません。コンテナ用の `snowflake.yml` は配布していません。`pyproject.toml` が生成された場合は、パッケージ取得先とネットワーク前提を講師と確認します。

## 任意: 実装上の安全策

- 日付・局はSQL文字列へ直接つながず、バインド変数で渡します。
- 集計結果は60秒キャッシュし、「再読込」で破棄します。
- 予測全体の検査と表示集計を同じSQL・キャッシュで扱い、全20,000台のID、一意性、確率、閾値、クラス、単一モデル版、`F1_SIGNAL_V2` を確認します。
- 予測と分別曲線はチェックを入れたときだけ取得し、エラーを「視聴ゼロ」として表示しません。

## 後片付け

本編を続ける場合はアプリを残して [第5章](05_agent.md) へ進みます。教材が不要になったら[第1章の後片付け](01_setup.md#後片付け)に従います。

Workspaceの開発アプリと公開済みStreamlitは別管理です。開発アプリを先に停止し、不要な教材専用ソースを整理します。DB削除だけで開発アプリも停止したと判断しません。他の作業があるWorkspaceや、共有・既定・システム管理のcompute poolは削除しません。

## 参考

- [既存ソースから作成](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/creating-your-app)
- [Gitリポジトリから作成](https://docs.snowflake.com/en/developer-guide/streamlit/features/git-integration)
- [依存パッケージと対応バージョン](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/dependency-management)
- [Workspaceでの作成・実行・Deploy](https://docs.snowflake.com/en/developer-guide/streamlit/streamlit-in-workspaces/streamlit-in-workspaces-create-run)
- [Workspaceの実行基盤](https://docs.snowflake.com/en/developer-guide/streamlit/streamlit-in-workspaces/streamlit-in-workspaces-overview)