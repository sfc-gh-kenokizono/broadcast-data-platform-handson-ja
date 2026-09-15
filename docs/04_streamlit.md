# 第4章 共通マートを可視化する

この章は、作成済みの `COMMON.VIEWING_DAILY` を Snowsight の Streamlit アプリから読み取ります。SQL・Python はローカルで作成した教材であり、対象アカウントでの作成・起動は未検証です。以下の画面操作は参加者が後から実施します。

## 前提

- 第2章で5局の dbt テストと共通マート作成が完了していること。`ML.PREDICTIONS` は未作成でも構いません。
- 作成ロールは `BCAST_PLATFORM_ENGINEER_ROLE`。データベースは `BCAST_PLATFORM_HANDSON`、配置先は `MART`、アプリ名は `VIEWING_APP`、クエリ用ウェアハウスは `BCAST_PLATFORM_COMMON_WH` とします。
- 作成ロールには、対象 DB・MART・COMMON の USAGE、MART の CREATE STREAMLIT、COMMON.VIEWING_DAILY の SELECT、共通ウェアハウスの USAGE が必要です。予測表示時だけ ML の USAGE と ML.PREDICTIONS の SELECT も必要です。準備は第1章と第3章で確認します。
- 所有者権限で実行する構成です。閲覧者へアプリを共有すると所有者が取得できる結果が表示されます。行レベルのアクセス制御を実装したアプリではありません。ACCOUNTADMIN をアプリ所有者にしないでください。
- 公開予定リポジトリは `sfc-gh-kenokizono/broadcast-data-platform-handson-ja` です。本ビルドで公開・push はしていません。Git 経路は講師が公開済みブランチを案内した後だけ利用します。

**必須経路は経路B（warehouse runtime）を推奨します。** 共通WHをアプリとSQLの実行に使い、compute pool の追加準備を必要としない最も単純な構成です。経路Aは Workspace 開発を試す補足で、第1章ではその compute pool の作成・USAGE 付与・Workspace の前提を準備していません。迷った場合は経路Bへ進んでください。両経路を続けて実行する必要はありません。同名の `VIEWING_APP` が既にある場合は、別経路で上書きせず講師に確認します。

## 使うソース

`app/streamlit_app.py` が入口、`app/queries.py` が集計 SQL です。この2ファイルを必ず同じフォルダに配置します。`app/environment.yml` は warehouse runtime 用です。`app/tests/` はローカルテスト専用で、デプロイ対象に含める必要はありません。

コンテナ用の `snowflake.yml` は同梱していません。未確認の compute pool 名を固定しないため、Workspace の UI が作る設定を、実際のアカウントに合わせて確認します。ローカル認証情報や `snowhouse` 接続設定はアプリに含めません。

## 経路A: Git Workspaceから作成（補足）

公式ドキュメントが案内する Workspace 開発経路です。**この経路の Python 実行基盤はコンテナ／compute pool です。共通ウェアハウスは SQL の実行用であり、compute pool を兼ねません。**

1. Snowsight の Workspaces で講師が用意した新教材の Git-backed Workspace を開きます。まだない場合は `+` から Git Workspace を作成し、公開済みの新教材リポジトリ／ブランチを選びます。旧教材は選びません。
2. `app/streamlit_app.py` を開きます。Streamlit ファイルの検出に伴う設定作成の案内が出た場合は、入口がこのファイル、`queries.py` が同じフォルダにあることを確認します。案内が出ない UI では `+ Add new → Streamlit app` で作ったフォルダのデモコードを新教材の2ファイルに置き換えます。既存の教材ファイルを上書きしないよう、配置先を確認します。
3. Settings／Execution で SQL 用 warehouse を `BCAST_PLATFORM_COMMON_WH` に設定します。利用可能な compute pool、USAGE 権限、アカウントの既定 pool を講師に確認します。Workspace の前提として既定 warehouse も確認しますが、この教材でユーザーの既定値を勝手に変更しません。
4. ランタイム組み込みの `streamlit`、`pandas`、`snowflake-snowpark-python` を使います。`environment.yml` はコンテナの依存定義として使いません。UI が生成した `pyproject.toml` に依存・バージョン指定がある場合は、対象環境の Artifact Repository／ネットワーク要件を確認してください。教材アプリ自体は外部 API・画像・フォント・CSS を読み込みません。
5. `Run` で私用の開発アプリを起動します。下記チェックを行います。Python ファイルを通常の Python ワークシートとして実行するのではなく、Streamlit の Run を使います。
6. `Deploy` を選び、名前 `VIEWING_APP`、配置先 `BCAST_PLATFORM_HANDSON.MART`、共通 warehouse と compute pool を再確認して公開します。共有先を指定する場合は `BCAST_PLATFORM_ANALYST_ROLE` のみにし、`PUBLIC` を選びません。
7. 下記「両経路共通: 作成後の共有と公開確認」へ進みます。Workspace の保存・Run と他ユーザー向けの Deploy は別です。Git への commit／push は本章では不要です。

設定生成の具体的なダイアログ・フォルダ検出・Deploy の表示名はアカウントの UI 展開状況により異なります。対象アカウントでのこの一連の操作は未検証です。ボタンがない場合に未確認の CLI デプロイへ切り替えず、経路Bを検討してください。

## 経路B: Projectsからソースを指定（推奨・必須経路）

Projects → Streamlit で **Run on warehouse** を選べることを確認します。公式の Git 連携ページには、`+ Streamlit` 横のメニューから **Create from repository** を選ぶ手順もあります。warehouse runtime で利用できる場合は次を設定します。

- リポジトリ: `BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO`。講師指定の公開済みブランチの `app/streamlit_app.py` を選びます。
- App location: `BCAST_PLATFORM_HANDSON.MART`。名前: `VIEWING_APP`。
- Query warehouse と App warehouse: どちらも `BCAST_PLATFORM_COMMON_WH`。
- 作成後にファイル一覧で `queries.py` と `environment.yml` もアプリのルートにあることを確認します。複数ファイルの取り込み範囲は実機未検証なので、欠けていれば新教材の対応ファイルを追加します。

このメニューがない場合、Projects → Streamlit → `+ Streamlit App` で新規作成し、**Run on warehouse** が選択できることを確認します。上記の配置先・warehouse を設定し、作成後のエディタの `+ Add → Upload file` またはファイル編集で `streamlit_app.py`、`queries.py`、`environment.yml` を配置して `Run` します。Git Workspace上のソースをコピーする方法でも構いません。UI上の変更がGitへ自動反映されるとは限りません。

warehouse runtime の依存設定は Python 3.11、Streamlit 1.50.0、pandas 2系、Snowpark です。1.50.0 は参照した公式対応リストに載っていますが、アカウントでの解決は未検証です。Packages の選択肢と合わせて講師が確認してください。旧教材の `ROOT_LOCATION` と内部ステージへのコピーを必須条件にはしていません。

warehouse runtime の作成画面がない場合は、講師に利用可否を確認して停止します。前提を確認しないまま container runtime に切り替えません。作成できたら、必ず次の共通手順へ進みます。所有者のエディタで `Run` できただけでは共有・公開確認は完了しません。

## 両経路共通: 作成後の共有と公開確認

1. 作成者ロール `BCAST_PLATFORM_ENGINEER_ROLE` で Projects → Streamlit を開き、`BCAST_PLATFORM_HANDSON.MART.VIEWING_APP` が存在することを確認します。名前だけでなく DB・スキーマ・所有者・実行基盤も確認します。
2. アプリの Share／共有で `BCAST_PLATFORM_ANALYST_ROLE` に閲覧用の USAGE を付与し、共有先に反映されたことを確認します。経路Aの Deploy 時に指定済みでも再確認します。編集権限や所有権は渡さず、`PUBLIC` には共有しません。共有先の DB・MART・共通WHへの USAGE は第1章の準備を確認します。
3. 経路Aは Deploy 済みの版、経路Bは閲覧者向けに公開される版を確認します。UI に Publish／公開があれば対象の版を確認して実行します。該当操作がない UI でも保存・所有者の `Run` だけで完了とせず、Projects → Streamlit から共有用の閲覧画面を開き直します。
4. 共有リンクを、`BCAST_PLATFORM_ANALYST_ROLE` を付与された閲覧者として開き、意図した版の実績タブとフィルターが動くことを確認します。単独学習ではアナリストロールを選び、所有者・管理者やセカンダリロールの権限に依存しない条件で確認します。同じアカウントに複数ユーザーがいる場合は、管理者が実在する閲覧者へのロール付与を確認します。権限を分離した閲覧確認ができなければ「所有者での動作のみ確認、共有は未検証」と記録します。
5. 下記の実機チェックを公開先の閲覧画面でも実施し、確認した版・ロール・結果を記録します。別ユーザーへの公開を、Workspace 内の私用開発アプリの起動だけで確認済みにしません。

## 指標と予測の読み方

- 期間全体のリーチは、選択期間・全選択局をまとめて `COUNT(DISTINCT DEVICE_ID)` で再計算します。各日・各局の distinct 値を足しません。端末数を人数・世帯数と呼びません。
- 総視聴時間は `SUM(VIEW_MINUTES)`、総視聴回数は `SUM(SESSION_COUNT)` です。マートの1行は局・端末・日・ジャンルであり、行数はセッション数ではありません。
- 視聴実績タブは3指標、日別推移、局別・ジャンル別内訳を表示します。空の共通マート・未選択の局・日付範囲の選択途中では案内だけを表示します。
- 予測タブは `予測結果を表示` を選んだときだけ問い合わせます。対象視聴端末を DISTINCT にしてから ML.PREDICTIONS と結合するため、複数日・局・ジャンルの視聴で端末数が増えません。
- 予測0／1は合成ラベルに対する二値分類です。確率や真の属性ではありません。選択期間は視聴端末の選別条件であり、学習期間・予測日時の条件ではありません。モデル名・バージョン・予測日時を併記します。
- 予測テーブルの未作成／不可視、空、未推論の端末を区別します。重複端末・不正クラス・モデル情報の欠損があれば表示を止めます。予測の問題で実績タブは止めません。正解ラベルは参照しません。
- SQL の日付・局は `?` のバインド変数です。局数に合わせたプレースホルダーだけを構築し、入力値は SQL に埋め込みません。SQL 内のテーブル名と集計切り口は固定です。
- 集計結果は60秒間キャッシュします。データ更新後は `再読込` を選びます。これはクエリ結果のキャッシュ削除であり、データ更新・モデル再学習ではありません。

## 実機チェック

1. ML未実行でも実績タブが表示されること。予測表示を選ぶと「未作成、または参照権限なし」の案内になること。
2. 2026-07-01から30日・全5局のリーチが、同条件の SQL の `COUNT(DISTINCT DEVICE_ID)` と一致すること。局別リーチの合計を比較対象にしないこと。
3. 1局・1日、複数局・複数日、局未選択、日付選択途中で例外にならないこと。
4. 第3章完了後、予測あり・なしの合計端末数が同条件の実績リーチと一致し、モデル名・バージョンが第3章の出力と一致すること。
5. 両経路共通の共有・公開確認を終え、アナリストの閲覧画面で意図した版が動き、想定外のデータが表示されないこと。この確認は本ビルドでは未実施です。

ローカルテストは `python -m unittest discover -s app/tests -v` です。Snowflake へ接続せず、SQLite のメモリ内 fixture と Streamlit AppTest のモックで確認します。Snowflake 方言のコンパイルや SiS ランタイム検証の代替ではありません。

テスト環境には `streamlit`、`pandas`、`snowflake-snowpark-python`、`PyYAML` が必要です。PyYAML は Agent SQL 内の YAML を検査するテスト用で、アプリ実行には不要です。本ビルドのテストは既存ローカル環境の Python 3.12／Streamlit 1.37.1 で実施しました。教材で指定した Python 3.11／Streamlit 1.50.0 と同一環境ではありません。

## 後片付け

経路Aの Workspace 内で起動した私用開発アプリと、Deploy した公開済み Streamlit オブジェクトは別々に管理します。まず各利用者が Workspace 側の対象開発アプリを停止し、不要になった教材専用アプリ／ソースを削除します。他の作業がある Workspace は削除しません。その後、[第1章の後片付け](01_setup.md#後片付け)に従って公開済みオブジェクトを含む教材環境を削除します。`sql/cleanup.sql` だけで Workspace の開発アプリまで停止・削除されるとはみなさず、残存・稼働状態を別途確認してください。共有・既定・システム管理の compute pool は削除・停止しません。

## 参照

2026-09-14 に公式ページの記載を確認しました。実際の UI 操作を検証した日付ではありません。

- [Workspaceでの作成・実行・Deploy](https://docs.snowflake.com/en/developer-guide/streamlit/streamlit-in-workspaces/streamlit-in-workspaces-create-run)
- [Workspaceの実行基盤と前提](https://docs.snowflake.com/en/developer-guide/streamlit/streamlit-in-workspaces/streamlit-in-workspaces-overview)
- [Gitリポジトリからのアプリ作成](https://docs.snowflake.com/en/developer-guide/streamlit/features/git-integration)
- [既存ソースから作成](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/creating-your-app)
- [依存パッケージと対応バージョン](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/dependency-management)

次は [第5章 セマンティックビューと Agent](05_agent.md) です。