# 開始前の準備確認

講師と受講者で、開始前にこの表を埋めます。空欄がある場合は該当する章を開始しません。講師専用の検証記録ではなく、受講者に案内する実行条件の確認表です。

| 確認するもの | 指定・合格条件 | 当日の確認結果 |
|---|---|---|
| アカウントと利用者 | 講師指定の演習用アカウント。固定名の環境は1アカウント1組 | 未記入 |
| 教材の版 | GitHub mainの対象commitと、Git Workspaceの版を一致させる。データ取込用GitリポジトリもFETCHする | 未記入 |
| 作成ロール | BCAST_PLATFORM_ENGINEER_ROLEを本人に付与済み。管理者ロールに頼らず実行できる | 未記入 |
| 閲覧ロール | BCAST_PLATFORM_ANALYST_ROLEを閲覧確認する本人に付与済み | 未記入 |
| dbt | DBT_VERSION 1.9.4。NW01の選択が2モデル＋7テストで、作成・検査SQLがNW01用WHで動く | 未記入 |
| Notebookのcompute pool | 講師が実在するpool名を案内。x86、NOTEBOOKワークロードを許可、作成ロールにUSAGEあり | 未記入 |
| NotebookのPython・runtime | 講師が選択する組み合わせを案内し、受講者の対話実行で確認。下記の過去検証値だけで合格とはしない | 未記入 |
| Notebookのパッケージ | numpy、pandas、scikit-learn、snowflake-snowpark-python、snowflake-ml-pythonがimportできる。モデル登録時の依存解決も確認 | 未記入 |
| Notebookの待機タイムアウト | サービス作成時に15分を選ぶ。選べない場合は講師が利用可能な値と終了時の停止担当を案内 | 未記入 |
| Streamlit | warehouse runtime、Python 3.11、Streamlit 1.50.0、pandas 2系、Snowpark。3ファイルの配置と閲覧ロールでの表示確認 | 未記入 |
| Agent・CoWork | 第5章の既定ロール・既定WH・モデル利用可否を講師が確認。共有先でも質問が成功する | 未記入 |
| 終了担当 | 各自のNotebookサービスを停止し、共有poolを停止・削除しないことを確認 | 未記入 |

## 過去の検証値と当日の準備は別

2026-09-15のトライアル非対話実行ではPython 3.11、runtime `V2.2-CPU-PY3.11`、snowflake-ml-python 1.23.0でモデル登録・推論・保存を確認しました。これは現在の選択肢や、受講者の対話サービスでの成功を保証するものではありません。講師は当日の選択値とパッケージ版を記録し、Notebookを上から通してください。

既存のpoolやアカウント設定を受講者が変更する手順ではありません。利用権限が不足する場合は管理者が対象と影響を確認して準備します。共通WHのUSAGEやCREATE NOTEBOOKだけでNotebookサービスの準備済みとは判断しません。

## 実機の完了条件

Git Workspace作成 → Parquet取込 → dbtの6回のbuild → Notebook保存・照合 → Streamlitの共有先表示 → Agent・CoWorkへの質問を、同じ教材版で確認します。SQLによるオブジェクト作成だけでは画面操作の確認を代替しません。説明・画面操作・待ち時間・質疑を含めた時間を測定し、3時間以内と未計測のまま案内しません。

講師デモのApp Runtimeは別プロジェクトです。このリポジトリには含まず、作成・デプロイ・表示確認が終わるまでは準備中として扱います。

出典: [Notebookの計算環境・停止・タイムアウト](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-compute-setup)