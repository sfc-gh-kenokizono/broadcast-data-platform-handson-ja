# 第3章 MLOps体験: 合成世帯のF1在籍を推定する

第2章の共通マートから、テレビに対応する架空の世帯にF1層（20〜34歳の女性）がいるかを予測します。学習・評価したモデルを登録し、その登録版で20,000台を推論して、安全確認後に結果を保存します。

> すべて教材用の合成データです。現在の視聴者、個人の年齢・性別、人数を特定するものではありません。確率を合計して人口や実際のF1視聴者数に換算することもできません。

## 最初に行う操作

| 順番 | どこを開く | 正確な操作 | 成功の合図 |
|---:|---|---|---|
| 1 | SnowsightのGit Workspace | `notebooks/03_mlops.ipynb` を作成または開く | Notebookのセルが表示される |
| 2 | Notebook上部の接続メニュー | CPU、Python 3.12、runtime `v2.10`、`SYSTEM_COMPUTE_POOL_CPU (CPU_X64_S)`、Idle timeout 24時間を選ぶ | 接続済みになり、環境確認セルでPythonと5パッケージの版が表示される |
| 3 | Notebook | `SAVE_RESULTS = False` のまま、上から1セルずつ実行する | TRAIN / VALID / TESTが1,200 / 400 / 400台になる |
| 4 | 評価セル | TESTの評価値と混同行列を確認する | 参考値に近く、閾値が0.46と表示される |
| 5 | 登録セル | 未使用の版でモデルを登録し、`show_functions()` を確認する | `TV_F1_PRESENCE_MODEL` と版、`predict_proba` が確認できる |
| 6 | 推論セル | 登録版で20,000台を推論する | 20,000行、`PROB_NO_F1`・`PROB_F1`、確率合計1を確認できる |
| 7 | 保存セル | 全検査後に、そのセルの `SAVE_RESULTS` だけを `True` にして実行する | 「ステージングで20000台を照合後、既存の権限を引き継いで予測テーブルを一括公開しました。」と表示される |
| 8 | Notebook上部 | **Connected → サービス名 → Suspend** | **SUSPENDED** とNotebookの切断を確認できる |

## 1. Notebookを接続する

第2章の5局と共通マートのbuild・テストがすべて成功していることを確認してから始めます。実行ロールは `BCAST_PLATFORM_ENGINEER_ROLE`、Query warehouseは `BCAST_PLATFORM_COMMON_WH` です。DB `BCAST_PLATFORM_HANDSON` と `ML` スキーマは最初のコードセルで設定します。

| 設定 | 選ぶ値 |
|---|---|
| Compute type | CPU |
| Python | 3.12 |
| runtime | `v2.10` |
| Artifact repository | 画面に表示されるSnowflake管理のPyPI repository |
| compute pool | `SYSTEM_COMPUTE_POOL_CPU (CPU_X64_S)` |
| Idle timeout | 24時間（演習後に手動でSuspendする） |
| 実行ロール | `BCAST_PLATFORM_ENGINEER_ROLE` |
| Query warehouse | `BCAST_PLATFORM_COMMON_WH` |

特徴量の集計と登録モデルの推論はWH、学習はNotebookのPython環境で動きます。共通WHだけではNotebookのPythonは動きません。接続画面では上表の値を選び、**Create and connect** を押します。サービス名は自動入力された値のままで構いません。Custom image、GPU、External Access Integrationは使いません。

Python 3.12はSnowflake Notebooksのサポート対象です。runtime `v2.10` はPythonとは別に選ぶNotebook実行環境の版で、この画面で選べる値を使用します。接続後の環境確認セルとNotebook先頭セルで必要なパッケージを実際に読み込めることを確認します。

接続後、一時的なPythonセルで次を実行します。

```python
import sys
from importlib.metadata import version

print("Python:", sys.version.split()[0])
for package in (
    "numpy", "pandas", "scikit-learn",
    "snowflake-snowpark-python", "snowflake-ml-python",
):
    print(f"{package}: {version(package)}")
```

Python 3.12と5パッケージの版がエラーなく表示されれば成功です。表示された版は確認用であり、特定の版番号との完全一致は求めません。パッケージが見つからない場合は追加インストールせず、その画面を講師と確認します。`app/environment.yml` は第4章専用です。

確認セルは削除して構いません。教材の設定セルへ戻り、`SAVE_RESULTS = False` のまま上から実行します。サービスを再開した場合は変数や追加パッケージが消えるため、環境を再確認して先頭から実行します。画面操作は[Notebookの計算環境の設定](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-compute-setup)を参照してください。既存の教材データがある場合は、[第1章の注意](01_setup.md#実行前の確認)に従います。

## 2. 上から実行し、データと分割を確認する

視聴実績は `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY`、ラベルは `BCAST_PLATFORM_HANDSON.RAW.DEVICE_LABELS` です。対象は2026年5月1日〜7月31日、`C000001`〜`C020000` の20,000台です。

| 対象 | 台数 | ラベル |
|---|---:|---|
| 全テレビ | 20,000 | 全台が視聴実績とラベル表に登場 |
| パネル | 2,000 | `LABEL_AVAILABLE = TRUE`、`TARGET_F1` は0または1 |
| パネルの正解1 / 正解0 | 344 / 1,656 | 合成世帯にF1層がいる / いない |
| 非パネル | 18,000 | `LABEL_AVAILABLE = FALSE`、`TARGET_F1 = NULL` |

**NULLは不明であり0ではありません。** 非パネルは学習・評価に使いません。入力は視聴ログ5ファイル、番組マスター、番組表、ラベルの計8 Parquetファイルです。正常な視聴区間は1,050,000件、RAWは検査用の重複・不正区間を含む1,050,648件です。

WHでテレビ1台につき次の12列へ集計します。約104万行の日次マートや約1,353万行の分展開データはNotebookへ持ち込まず、取得は上限超過検知用の1行を含む最大20,001行です。

| 特徴量 | 内容 |
|---|---|
| `NEWS_SHARE`〜`INFO_SHARE` | NEWS、DRAMA、VARIETY、ANIME、SPORTS、MUSIC、MOVIE、INFOの時間割合 |
| `TOTAL_MINUTES` | 全局・全対象日の総視聴時間（分） |
| `TOTAL_SESSIONS` | 正常な元視聴区間の件数合計 |
| `ACTIVE_DAYS` | 視聴区間の開始日を重複なく数えた日数 |
| `MEAN_MINUTES` | 総視聴時間 ÷ 総視聴区間数 |

8つのジャンル割合の合計が1になることを確認します。視聴時間は各区間の実経過秒数を60で割り、開始日の開始時ジャンルへ全量計上します。番組境界で分けた厳密な番組別時間ではありません。`ACTIVE_DAYS` も開始日基準です。モデル入力はこの順番の12列だけで、端末ID、正解、公開フラグ、世帯構成は含めません。IDの欠損・重複・範囲違い、非有限値、ラベル契約の不一致があれば停止します。12列は小数点以下8桁にそろえてから分割します。

固定seed `20260918` の層化分割が次の件数になり、同じテレビが複数組にないことを確認します。

| 分割 | 全台数 | 正解0 | 正解1 |
|---|---:|---:|---:|
| 学習（TRAIN） | 1,200 | 994 | 206 |
| 検証（VALID） | 400 | 331 | 69 |
| 最終評価（TEST） | 400 | 331 | 69 |

## 3. 評価結果を確認する

採用モデルは `StandardScaler` と `LogisticRegression(C=1.0, max_iter=1000, random_state=42)` をつなぎ、`CalibratedClassifierCV(method='sigmoid', cv=3)` で学習用1,200台の中だけを使って確率を補正したものです。VALIDとTESTの正解は校正に使いません。

判定閾値はVALIDで0.05〜0.95を0.01刻みで比較し、precision・recallがともに0.60以上でF1スコアが最大になる **0.46** に固定済みです。TESTを見て閾値・特徴量・生成データを変更せず、VALIDを足した再学習もしません。基準モデルは `DummyClassifier(strategy='prior')` で、全台へ206/1,200 = 約0.171667を返します。

V2配布データのTEST 400台の参考値です。環境差で末尾の桁が少し違う場合があります。

| 指標 | 学習モデル | 基準モデル |
|---|---:|---:|
| ROC AUC | 0.988353 | 0.500000 |
| Average Precision（AP） | 0.953904 | 0.172500 |
| Brier score | 0.031873 | 0.142744 |
| 適合率（閾値0.46） | 0.873239 | 0.000000 |
| 再現率（閾値0.46） | 0.898551 | 0.000000 |

| 正解 / 予測 | 予測0 | 予測1 |
|---|---:|---:|
| 正解0 | 322 | 9 |
| 正解1 | 7 | 62 |

71台を1と判定し、62台が正解です。正解1の69台中7台を見逃し、正解0の9台を誤って1としました。VALIDはROC AUC 0.977714、AP 0.914482、Brier 0.045017で、TESTとは混ぜて報告しません。

## 4. 評価したモデルを登録する

登録先は `BCAST_PLATFORM_HANDSON.ML.TV_F1_PRESENCE_MODEL`、初期版は `V2` です。学習1,200台だけで作り、検証と最終評価を終えたモデルそのものを登録します。2,000台や20,000台で学習し直しません。

- 同名・同版があれば停止します。新規利用者は `V2`、登録済みなら未使用の `V3` などを講師と選び、先頭から実行します。既存版を削除・上書きしません。
- 依存パッケージは学習時のscikit-learn版に合わせ、推論先は `WAREHOUSE` に固定します。
- `classes_` が `[0, 1]` であることを確認し、0の確率、1の確率の順で明示したシグネチャを使います。
- `show_functions()` で `predict_proba` と入出力を確認します。返却列名を推測して0・1へ割り当てません。

## 5. 登録版で20,000台を推論する

Notebook内のモデルではなく、登録した版の `predict_proba` をWHで実行します。次をすべて確認してください。

- 20,000台すべてがあり、学習1,200台、VALID 400台、TEST 400台、非パネル18,000台を含む。
- `PROB_NO_F1` と `PROB_F1` は有限かつ0〜1で、行ごとの合計が1。
- `PROB_F1 >= 0.46` は `PREDICTED_HAS_F1 = 1`、未満は0。
- 入力特徴量と戻った特徴量を照合して端末IDへ対応付ける。同じ12項目なら同じ予測を対応付ける。
- 特徴量・確率の欠落、行数・出力名の不一致がない。

20,000台の出力は新しい精度評価ではありません。精度はTEST 400台の値です。登録や推論を再実行すると以前の保存可能状態は無効になります。失敗前の古い予測や、版名だけを変えた予測は保存しません。

## 6. 検査後だけ保存する

保存セルの初期値は変更せず、一度そのまま実行します。

```python
SAVE_RESULTS = False
```

確認メッセージで停止し、結果テーブルが変わらなければ意図した動作です。モデル登録はこの前に行われます。`False` はNotebook全体を読み取り専用にする設定ではありません。

1. 20,000台、ID集合、確率、閾値判定、実際に推論したモデル名・版、データ版を確認します。
2. `BCAST_PLATFORM_HANDSON.ML.PREDICTIONS` の既存結果を置き換えてよいか確認します。
3. 保存セルの `SAVE_RESULTS` だけを `True` にし、そのセルだけを実行します。

保存先は履歴追加ではなく置き換えです。期待する出力スキーマは次の8列です。

| 列 | 期待値 |
|---|---|
| `DEVICE_ID` | `C000001`〜`C020000`、欠損・重複なし |
| `PROB_F1` | 浮動小数、0〜1 |
| `PREDICTED_HAS_F1` | 閾値0.46による整数0・1 |
| `MODEL_NAME` | 実際に推論したモデル名 |
| `MODEL_VERSION` | 実際に推論した未使用版 |
| `PREDICTED_AT` | UTCの保存時刻、`TIMESTAMP_NTZ` |
| `PREDICTION_THRESHOLD` | 0.46 |
| `DATASET_VERSION` | `F1_SIGNAL_V2` |

保存処理は一時ステージングへ書き込み、最大20,001行を読み戻して20,000行と各項目を照合します。さらに入力RAWがNotebook開始時から変わっていないことを確認し、成功時だけ既存権限を引き継いで `PREDICTIONS` を1つのSQL文で置き換えます。`PREDICTED_AT` は視聴時刻ではありません。照合失敗時は既存テーブルを変更しません。公開時の通信エラーは完了状態を判断できないことがあるため、再実行せず講師へ確認します。

## 7. Notebookサービスを停止する

評価値・モデル版・必要な出力を記録し、同じサービスの別作業がないことを確認します。画面を閉じるだけ、またはShut down kernelだけでは停止しません。

1. **Connected → サービス名 → Suspend（一時停止）** を選びます。
2. **SUSPENDED** とNotebookの切断を確認します。
3. 別Notebookも切断されるため、共有中なら講師と停止時点を調整します。

共通WHとNotebookサービスは別です。共有・システム管理のcompute pool自体は停止・削除しません。保存済みモデルと `PREDICTIONS` は残ります。

## 任意: 設計上の補足

- 合成データV2は世帯構成と視聴傾向の関係を意図的に強めています。F1在籍ありは「若い女性の単身世帯」と「若いカップル世帯」の2テンプレートだけで、他の世帯構成、公平性、実世帯への適用性能は検証していません。
- 校正後でも、0.7を現実の在籍率70%とは保証できません。確率の合計を人数や全国推計へ変換しません。
- Permutation ImportanceはVALIDの説明専用です。列削除や再学習、TESTを見た調整には使いません。
- ID・特徴量・ラベル契約の検査、保存可能状態の無効化、一時ステージング検証、権限を引き継ぐ一括公開により、途中結果や不整合な版の公開を防ぎます。

次は [第4章 Streamlit](04_streamlit.md) で、視聴実績と合成世帯の推定を区別して確認します。

## 参考

- [Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)
- [WHでのバッチ推論](https://docs.snowflake.com/en/developer-guide/snowflake-ml/inference/native-batch-inference-sql)
- [Notebookサービスの停止と費用](https://docs.snowflake.com/en/user-guide/ui-snowsight/notebooks-in-workspaces/notebooks-in-workspaces-compute-setup)