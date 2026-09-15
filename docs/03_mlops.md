# 第3章 MLOps体験

## 現在の状態

`notebooks/03_mlops.ipynb` は **14セル（Python 6セル・Markdown 8セル）を実装済み**です。旧版の「導入1セルのみ・追加ツールで停止」という記述は現状と異なるため取り下げました。セル番号は0始まりです。

2026-09-15にトライアル内のNotebook Project非対話実行で、学習・評価・Registry登録・WH推論・200台の保存・読戻し照合まで成功しました。登録時にcurrent database未指定で失敗したため、セル2でDBとMLスキーマを明示するよう修正しています。実行はPython3.11／snowflake-ml-python1.23.0、`V2.2-CPU-PY3.11` runtimeです。検証用コピーだけにロール明示・secondary roles NONEと保存許可を加え、配布版のロール検査と `SAVE_RESULTS = False` は維持しました。参加者の対話サービス起動権限・GUI操作は別途確認が必要です。[検証記録](verification.md)に実施範囲を記載しています。

## この章で学ぶこと

合成の視聴履歴から端末ごとの特徴量を作り、架空のスポーツ関心ラベルを予測します。学習、未学習端末での評価、モデルの名前・版の登録、その登録版での推論、使用した版と結果の保存を体験します。

年齢・性別・世帯構成の推定でも、実在の個人や視聴者の特定でもありません。端末と人を同一視せず、この合成データでの精度を実際の視聴者に対する有効性として説明しないでください。

## 前提と権限

- 第1章のロードと、第2章の5局・COMMONの計6回のdbt buildとテストを完了します。
- SnowsightのWorkspace NotebookでPythonランタイムを選びます。参加者のローカルPythonからSnowflakeに接続する手順ではありません。
- セル2は `BCAST_PLATFORM_ENGINEER_ROLE` を要求し、`BCAST_PLATFORM_COMMON_WH` を明示選択します。ユーザーの既定ロール・WHは変更しません。
- 必要なパッケージは `numpy`、`pandas`、`scikit-learn`、`snowflake-snowpark-python`、`snowflake-ml-python` です。利用するランタイム内での提供状況・バージョンは講師が確認します。
- `sql/01_setup.sql` の61–62行には、MLスキーマへの `USAGE, CREATE TABLE, CREATE MODEL, CREATE NOTEBOOK, CREATE STAGE` が明示されています。共通WHの `USAGE` も73行にあります。Notebook作成・モデル登録・結果テーブル作成を意図したセットアップです。これはファイル内の宣言確認であり、実アカウントの有効権限の証明ではありません。
- 入力のRAWテーブルとdbtテーブルはエンジニアロールで作成・所有する前提です。別ロールが作成した既存オブジェクトには読取や置換権限があるとは限りません。
- `CREATE NOTEBOOK` は既存Notebookの編集権限やWorkspaceへの書込権限を自動で保証しません。選択したWorkspaceでの編集・実行環境、必要に応じたcompute poolの利用権限は別途確認します。このセットアップはcompute poolを作成・付与しません。

学習はNotebookのPython環境、端末集計と登録モデルの推論は共通WHで行います。Notebook実行基盤の消費とWH消費は別です。登録は `target_platforms=['WAREHOUSE']` を指定しており、依存解決に失敗してもSPCSへ自動変更しません。

## 実際の14セル

| セル | 種別 | 実装内容 |
|---|---|---|
| 0 | Markdown | 目的・合成データの注意 |
| 1 | Markdown | 実行環境、既存版の扱い、結果置換の注意 |
| 2 | Python | imports、既存セッション、ロール検査、WH選択、モデル名・V1・7特徴量 |
| 3 | Markdown | 端末集計と入力件数上限の説明 |
| 4 | Python | 端末集計、割合計算、固定200台のID・NULL・既知100台・クラス各50台等の入力検査 |
| 5 | Markdown | 学習80台・評価20台と浅い決定木の説明 |
| 6 | Python | 層化分割、決定木と多数派ベースラインの学習・評価 |
| 7 | Markdown | 評価したモデルの登録、既存版で停止する方針 |
| 8 | Python | モデル・版の存在確認、relax_version=FalseでRegistry登録、登録版と関数の表示 |
| 9 | Markdown | Snowpark入力による登録モデル推論と特徴量での端末対応付け |
| 10 | Python | 7列をDoubleTypeでSnowpark化、登録版のpredict、最大201行取得、戻り値検査と200台への復元 |
| 11 | Markdown | 結果テーブルの置換を明示的に承認する説明 |
| 12 | Python | 保存フラグ、保存前検査、UTCの5列出力、PREDICTIONSの置換と読戻し照合 |
| 13 | Markdown | 振り返り・対象外・実機確認の必要性 |

## 入力・学習・評価

入力は `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY` と `BCAST_PLATFORM_HANDSON.RAW.DEVICE_LABELS` です。COMMONの日次行をそのまま学習・評価に分割せず、先に `DEVICE_ID` ごとに集計します。pandasへ取り込む上限は特徴量・ラベルそれぞれ201行で、200行と異なる場合に停止します。

モデル入力は `NEWS_SHARE, DRAMA_SHARE, VARIETY_SHARE, ANIME_SHARE, SPORTS_SHARE, TOTAL_MINUTES, TOTAL_SESSIONS` の7列です。ジャンル別視聴時間を総視聴時間で割った5割合と、総時間・区間数を使います。`DEVICE_ID`、`LABEL_AVAILABLE`、`TARGET_SPORTS_FAN` はモデル入力にしません。

公開100台の正解は0・1各50台、未公開100台の正解はNULLです。不明を0で埋めたり、生成器内部の未公開正解を復元したりしません。セル4では重複ID、ID自体のNULL、両入力それぞれの固定ID集合 `D0001..D0200` との一致、非有限特徴量、欠損フラグ、不正な既知・未知件数、未知への正解漏れ、不正ラベル、クラス不均衡を検査します。両入力のIDを同じ不正値に置き換えても停止します。

セル6は `train_test_split(test_size=0.2, random_state=42, stratify=...)` により80台・20台に分け、端末非重複をassertします。学習40/40、評価10/10です。モデルは **DecisionTreeClassifier(max_depth=3, min_samples_leaf=8, random_state=42)** であり、ロジスティック回帰ではありません。比較対象は `DummyClassifier(strategy='most_frequent')` です。

評価表はaccuracyとbalanced accuracyを表示します。ベースラインのbalanced accuracyはコード上では0.5の固定値ですが、この契約の層化分割では実測も0.5です。クラス構成を変更する教材では実測計算に変更してください。全200台の推論には学習80台も含まれるため、全件の結果で汎化精度を主張しません。同じ期間の別端末を採点しており、未来期間の評価ではありません。

## モデル登録と再実行

登録先は `BCAST_PLATFORM_HANDSON.ML.SPORTS_INTEREST_MODEL`、初期版は `V1` です。セル8は `show_models()` と必要時の `show_versions()` を調べ、同名・同版が見つかれば登録前に停止します。確認時の権限エラーは伝播し、「存在しない」と読み替えません。削除・上書き・自動再利用はしません。

別の版を作る場合はセル2の `MODEL_VERSION` を `V2` などに変更し、先頭から実行します。このNotebookでは既存版を自動再利用せず、停止して利用者の判断を求めます。

登録するのは80台で学習・20台で評価したモデルそのものです。全100台への再学習はありません。学習特徴量先頭10件をシグネチャ推定用に渡し、accuracyとベースラインaccuracyを記録します。`log_model` が返した `ModelVersion` をそのまま `registered_version` として推論に使用します。Registryから再取得するコードではありませんが、ローカルsklearnモデルのpredictを保存用に代用するコードでもありません。

`conda_dependencies` には `scikit-learn==学習環境の版` を指定し、`options={'relax_version': False}` で版制約の自動緩和を禁止しています。オフラインテストは両引数を検査します。ただし指定した版をWAREHOUSE向けに解決できるかは実環境で未検証です。解決不能なら停止する設計であり、この指定だけでPythonや全推移的依存関係まで同一になる保証ではありません。

## 推論の対応付け

セル10は7特徴量の重複を除き、全列 `DoubleType` の明示スキーマで `session.create_dataframe(...)` に渡します。そのSnowpark DataFrameを `registered_version.run(prediction_sdf, function_name='predict')` に渡し、返却Snowpark DataFrameを `registry_result.limit(201).to_pandas()` で取得します。入力特徴量と出力1列を検査し、列名を大文字化し、予測列を `PREDICTED_SPORTS_FAN` に変えます。行数・特徴量の一意性・0/1・NULLを検査し、元の200端末に `many_to_one` で左結合します。同じ特徴量の端末は同じ予測を共有し、戻り行順は使いません。

**Snowpark入力の特徴量保持にはSDK実装の根拠があります。** 導入済み `snowflake-ml-python 1.24.0` の `/opt/anaconda3/lib/python3.12/site-packages/snowflake/ml/model/_client/ops/model_ops.py:1029-1042`（`ModelOperator.invoke_method`）は、非Snowpark入力では `keep_order=True, output_with_input_features=False`、Snowpark入力では `keep_order=False, output_with_input_features=True` とし、`s_df = X` を使います。同ファイル1134-1139行の入力列dropはフラグがFalseの場合だけです。1142-1147行ではSnowpark入力に対して `df_res` をそのまま返します。テストはこの分岐をインストール済みソースのASTで確認しています。これは当該SDK版の静的根拠であり、全将来版の保証や実WH推論の成功証明ではありません。

以前のpandas入力経路は現在の実装では使いません。オフラインでは型付きSnowpark入力、Registryモックの戻り値、201行上限、入力行と値、順序を入れ替えた出力の対応を確認します。実ランタイムでの出力シグネチャ・列保持・float値の往復は別途確認してください。停止検査の削除やローカルpredictへのフォールバックで通過させないでください。

現在は「入力以外の列が1つ」という条件から予測列を選ぶため、`show_functions()` のシグネチャに基づく列名照合や大文字化後の列名衝突専用検査ではありません。これは残る検証範囲の限界であり、通常出力で失敗したという観測ではありません。float特徴量が往復でわずかに変化した場合も結合できず停止します。実機では表示された関数シグネチャ・列名・値の対応を確認してください。

## 保存と完了条件

セル12の初期値は次のとおりです。

```python
SAVE_RESULTS = False
```

このままではRuntimeErrorで停止し、テーブルを作成・置換しません。エラーを飛ばして完了扱いにせず、セル10まで成功し、既存結果を置き換えてよいと確認した場合だけTrueへ変更します。**このフラグはセル8でのモデル登録を止めるものではありません。**

保存先は `BCAST_PLATFORM_HANDSON.ML.PREDICTIONS`。`write.mode('overwrite').save_as_table(...)` により既存内容を置換し、履歴を追記する方式ではありません。

| 列 | 実装上の型 | 内容 |
|---|---|---|
| DEVICE_ID | StringType / VARCHAR | 端末ID |
| PREDICTED_SPORTS_FAN | LongType / INTEGER系 | 0または1 |
| MODEL_NAME | VARCHAR | 登録版オブジェクトのmodel_name |
| MODEL_VERSION | VARCHAR | 登録版オブジェクトのversion_name |
| PREDICTED_AT | TIMESTAMP_NTZ | current_timestampをconvert_timezoneでUTC変換後、NTZへcast |

正解・公開フラグ・学習区分・特徴量は保存しません。時刻は推論開始時刻ではなく、`sf.convert_timezone(sf.lit('UTC'), sf.current_timestamp()).cast('timestamp_ntz')` で作るUTCの保存時刻です。NTZ列自体はタイムゾーン情報を保持しないため、下流でもUTCとして扱います。実Snowflakeでの評価は未検証です。

**保存前後の検査は実装済みです。** セル12は保存前に200件・ID欠損/重複なし・固定ID集合・予測欠損なし/0・1・登録名と版が `registered_version` の属性に一致することを確認します。保存後は最大201行を読み戻し、200件・ID一意性、ID順に並べた端末と予測値の `assert_frame_equal(check_dtype=False)`、全行のモデル名・版の一致、日時の非NULLを確認してから成功を表示します。テストは各不正値、順序の入替え、保存失敗、読戻し失敗も検査します。

属性照合は予測DataFrameの生成履歴を暗号的・不変に結び付ける仕組みではありません。古くても形が正しい予測と新しい登録情報を手動で同時に差し替える操作までは検知しないため、上から順に実行します。読戻しでは型の厳密比較、日時が実際にUTCか・期待する範囲内かまでは確認しません。また置換後の検査失敗は自動ロールバックではありません。失敗時は後続へ進まず、実テーブルと実行状態を確認してください。

登録・推論・保存のどこかで失敗した場合は後続へ進みません。セル13の振り返りは、対応する操作が実際に成功した範囲だけを完了としてください。自動再学習、ドリフト監視、スケジュール実行は本章に含みません。

## オフライン検証

最終ローカル実行結果は **64 passed** です。DB・スキーマの初期化回帰テストを追加しました。失敗・スキップはなく、依存ライブラリの非推奨警告が1件あります。ローカル合格と、上記トライアル実行の証拠は区別します。

`notebooks/tests/test_mlops_offline.py` は実Notebookをnbformatで読み、実コードセルをASTでcompileして隔離した名前空間とモックで実行します。Notebookカーネルは使用せず、ipynbの内容は変更しません。セル12の許可経路だけはテスト中のAST上でFalseをTrueに変更します。ファイル自体の保存フラグはFalseのままです。

教材ルートからの再実行例:

```bash
PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python -B -m pytest -p no:cacheprovider --tb=short -q -s notebooks/tests/test_mlops_offline.py
```

- 全14セルのnbformat、全6コードセルのAST、Notebookの実行前後のバイト一致を検査します。
- 生成器を一時ディレクトリで実行し、6個のParquetのPAR1ヘッダー・フッターとZSTDを検査して読み直します。既存の `data/` は上書きしません。
- dbtのジャンル置換・ミリ秒差分による時間・局/端末/日/ジャンル集計に対応するpandas処理からセル4を試験します。SQLコンパイルやdbt実行の代わりではありません。
- セル4は小さなpandas式モックで実コード全体を試験し、集計を原本イベントから独立に算出した値と比較します。導入済みSnowpark local testingは集計後cast未対応で、条件式の数値変換にも差が出たため、これを回避するためにNotebookを変更していません。
- セル6は本物のsklearnで学習します。セル8・10はRegistryモックですが、セル10の入力はSnowpark local testingで作る本物のDataFrameとDoubleTypeスキーマです。モックは `run -> limit(201) -> to_pandas` を検査し、pandas入力への逆戻りを拒否します。ネットワーク接続はテスト中に拒否します。
- セル12の許可経路は接続不要のSnowpark local testingで置換・読戻しを試験します。導入済みSDKのcurrent_timestampモックはnaiveな時刻を返し、convert_timezoneで失敗しました。Notebookを変えず、テストの時計だけをタイムゾーン付きの固定値 `2026-09-15T09:30:00+09:00` に置き換え、実SDKのconvert_timezoneとNTZ castによる `2026-09-15T00:30:00` を確認します。実Snowflakeの時計やセッションタイムゾーンの検証ではありません。
- 不正入力、既存版・一覧異常・権限/登録失敗、relax_version=False、出力順の入れ替え、同じ特徴量の複数端末、入力列欠落、行欠落/余剰/重複、予測NULL/不正値、結合キー変化、推論/取得失敗、保存不許可・保存失敗を試験します。
- 旧 `test_characterizes_*` は拒否を期待する回帰テストへ変更済みです。両入力の同一不正ID/NULL、保存直前の件数/ID/予測/モデル属性異常は書込み前に停止することを確認します。別の読戻しモックで、保存後の件数/ID/予測値/モデル名/版/日時欠損/取得エラーを個別に注入し、成功表示前に停止することも確認します。

### 実測値

生成seed `20260701`、分割seed `42`、公開正解100台のみ使用。学習80台・未学習評価20台です。Python 3.12環境、scikit-learn 1.5.1、pandas 2.2.3、numpy 1.26.4、PyArrow 16.1.0、Snowpark 1.41.0、Snowflake ML 1.24.0で測定しました。

| モデル | 未学習20台のaccuracy | balanced accuracy |
|---|---|---|
| 決定木 | 0.60（12/20） | 0.60 |
| 多数派ベースライン | 0.50（10/20） | 0.50 |

決定木の混同行列は `[[7, 3], [5, 5]]`（行=正解0/1、列=予測0/1）。ベースラインとの差は2台だけです。合成データの小さな固定分割であり、実運用で優れている証拠ではありません。Snowflake上の浮動小数点集約やパッケージ差まで同一と保証する数値でもありません。

### 残る実機確認

- Snowsight取込・編集・選択ランタイムでの実行、Workspaceとオブジェクトの実効権限。
- 厳密なscikit-learn版指定を含むWAREHOUSE向け依存解決、Registry登録と関数シグネチャ。
- 実テーブルの集約結果、対象ランタイムSDKでのSnowpark入力/戻り列、float値の往復と200端末への対応。
- 実テーブルの置換権限・5列の型・200件の値/版/UTC保存時刻、および実際の読戻し成功。

これらは未実行であるため不明な項目です。オフラインで確認済みの修正を未修正の障害と呼んだり、ローカルテストの合格をSnowflakeテスト合格と記載したりしないでください。

## 参考

- [Model Registry: 登録・権限・依存関係](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)
- [WHでのバッチ推論: 入力と同じDataFrame型を返す](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/native-batch-inference-sql)
- [ModelVersion API: runとshow_functions](https://docs.snowflake.com/en/developer-guide/snowpark-ml/reference/latest/api/model/snowflake.ml.model.ModelVersion)
- [scikit-learnの登録対応とシグネチャ](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/built-in-models/scikit-learn)