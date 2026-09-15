# 検証・統合レビュー記録

確認日：2026-09-15。**トライアルでのバックエンド検証を追加しました。参加者のGUI操作まで含む通し成功や配布準備完了を意味しません。**

## トライアル実行結果

### GitHub作成・旧環境削除の追記

2026-09-15、ユーザー依頼で `sfc-gh-kenokizono/broadcast-data-platform-handson-ja` を非公開で作成。認証なしのGit取込は未対応のままで、参加者向け公開または認証設定が必要です。同じ依頼で、接続先 `OYCIPEF-KO72266` を再確認後、旧 `BCAST_VIEWING_HANDSON` と配下オブジェクト、`BCAST_HANDSON_WH`、`BCAST_GIT_API`、`BCAST_ANALYST_ROLE`、`BCAST_ENGINEER_ROLE` を削除しました。旧ロールのDB外権限は旧WH・旧Git統合・CORTEX_USERのみ、Git統合の参照元は旧リポジトリのみと確認しました。旧シェアはなく、NW01_VIEWERロールも存在しませんでした。新DB、共有compute pool、ローカル旧教材・バックアップには触れていません。以下の「旧環境を保持」は初回検証終了時点の履歴です。

本教材のApp Runtimeはローカル未作成・未デプロイです。今回配置したアプリはStreamlitで、App Runtimeの検証実績ではありません。

接続先は `trial-cocotest`、組織 `OYCIPEF`、アカウント `KO72266`。専用SQLツールのconnection指定は別アカウントを返したため、識別確認だけで停止し、以後は接続名を明示したSnowflake CLIでこのトライアルだけを変更しました。

- `01_setup.sql` の第1〜4節成功。新DB・6WH・専用ロール・RAWを作成。未公開GitHubへの第5節は未実施。
- 6個のParquetを内部ステージへ直接PUTし、`02_load_parquet.sql` のLIST以降を実行。各局3,600行、ラベル200行、日時の論理型、既知100／未知NULL100／各クラス50／漏洩0を確認。Git経由コピーとは別経路。
- ネイティブdbt Core 1.9.4／adapter 1.9.2で全6 build成功。5局は各2モデル＋7テスト、COMMONは1モデル＋3テスト。合計11モデル・38テスト、失敗・skipなし。PASS出力には各呼出しのhookも含まれます。
- クエリ履歴で各局WHにCTAS 2件＋テストSELECT 7件、共通WHにCTAS 1件＋テストSELECT 3件を確認。モデル作成のWHだけでなくテストも分離。
- デプロイ時の全体compileをガードが拒否したため、`flags.WHICH`でcompile/parse/ls/listだけを除外。flagsが不明ならbuild扱いで検査を維持。修正後、誤ったnw01 target＋nw02 tagのbuildを実機で拒否した（query ID `01c713c1-0204-ad6f-0005-167600161806`）。
- dbt検証は、27個のソースをステージ経由で `COMMON.BCAST_PLATFORM_DBT_PROJECT` に配置して実施。参加者の `FROM WORKSPACE` 経路やGUIボタン操作の確認ではありません。
- Notebookは `ML.TRIAL_MLOPS` の非対話実行、runtime `V2.2-CPU-PY3.11`、既存 `SYSTEM_COMPUTE_POOL_CPU` を使用。最初の登録時にcurrent database未指定で失敗し、配布用セル2へ `use_database` と `use_schema` を追加して再実行成功。
- 検証用コピーだけに `use_role`、secondary roles NONE、`SAVE_RESULTS=True` を追加。配布版はロール検査と保存確認Falseを維持。ユーザーの既定ロール・WHは変更していません。NPOの起動は管理者、モデル操作はエンジニアロールで実施したため、参加者のNotebook起動権限を証明するものではありません。
- Registry `ML.SPORTS_INTEREST_MODEL` V1を登録、WAREHOUSE推論成功。Python3.11、snowflake-ml-python1.23.0。登録metricsはaccuracy0.60／baseline0.50。`ML.PREDICTIONS` は200行・200端末・不正クラス0、V1、UTC保存時刻2026-09-15 01:42:47.438。Notebook内の読戻し照合も成功。
- Semantic View作成と元テーブル比較成功。リーチ200、視聴時間667,632.866664分、視聴回数18,000で一致。secondary roles NONEのアナリストロールでも参照成功。
- Agentの保険SQLで `MART.VIEWING_AGENT` を新規作成しUSAGEを付与。Streamlitはステージ経由で `MART.VIEWING_APP` に配置しUSAGEを付与。アナリストロールで両オブジェクトの表示を確認。自然言語回答やアプリ画面の成功とは区別します。
- ブラウザーはDOM未接続エラーのため、Streamlit表示・GUI作成比較・CoWork質問は未確認。
- 旧 `BCAST_VIEWING_HANDSON`、旧WH・ロール・Git統合は新教材と衝突しないため削除なし。共有compute poolの削除・設定変更なし。新しい検証オブジェクトはトライアルに残しています。
- COPY再実行は全6ファイルがLOAD_SKIPPED（File was loaded before）。各局3,600行・ラベル200行を維持しました。
- このトライアルでNotebookを再実行する場合は、既存V1を消さず `MODEL_VERSION='V2'` などへ明示変更してください。配布版V1のままでは意図どおり停止します。Agent・SVも既に存在するため、新規CREATEをそのまま繰り返しません。
- 終了時点で局別5WHはSUSPENDED、共通WHはAUTO_SUSPEND=60、Notebookのcompute poolは実行job0件・IDLE・AUTO_SUSPEND=300でした。共有poolは設定を変えず自動停止に任せています。

## 最終結果

| 対象 | 結果 | 検査範囲 |
|---|---|---|
| Parquet監査 | PASS | zstd、6ファイル、型、18,000区間、200台、未知ラベルNULL、区間非重複 |
| データ回帰テスト | 8件PASS | 再現性と不正データ検出 |
| セットアップ契約 | 4件PASS | 名前・列・WH権限宣言・ロード参照・cleanupの範囲 |
| 集計回帰テスト | 6件PASS | 実マクロのSQLをSQLite用に最小変換して実行。複数イベントの合算、分数、粒度、日跨ぎ、UNION ALL |
| アプリ | 24件PASS | メモリ内データとStreamlitモック。重複排除・バインド・予測未作成時・GUIコピー文一致 |
| Notebook | 64件PASS | 構造・AST、実セルをオフラインfixtureで検査。既存版停止・漏洩防止・推論対応・保存前後チェック・DB/スキーマ初期化 |
| 補足 | 8件PASS | 基本SQL読取範囲・区間結合・架空Search参照・リンク |
| dbt | オフラインPASS | 11モデル・38データテスト。6 parse＋26 ls。各局2モデル7テスト、共通1モデル3テスト |

ローカル回帰テスト合計は114件です。追加のNotebook初期化テストを含む64件、setup4件、集計6件を今回再実行しました。Notebookでは依存ライブラリの非推奨警告が1件ありました。dbtのオフライン検査と、上記の実データベース上での38テスト合格は別の検証です。

ローカル環境：Python 3.12、PyArrow 16.1.0、dbt Core 1.11.7／dbt-snowflake 1.11.3。アプリのローカルStreamlitは1.37.1で、教材指定のSiSバージョンの検証とは別です。

## レビューで直した点

- Streamlitの両作成経路で公開とアナリストへの共有確認を行うよう統一した。
- Warehouse runtimeを推奨経路にし、Workspace開発アプリ・compute poolの前提と別途後片付けを明記した。
- 別ユーザーの受講者へのロール付与、CoWorkの既定ロール・WHの事前確認を追加した。
- dbtの教材テストを127件から38件へ減らし、dbt1.9で使えない新しい引数記法を除いた。
- Notebookのpandas推論で入力列が消える問題を、型付きSnowpark入力へ変更して解消した。今回のトライアルでも推論・端末対応付け・保存まで成功。
- Notebookで正規端末ID、保存前の重複・値、登録版の一致、UTC保存日時、保存後の値照合を追加した。
- モデル登録は依存版を緩和せず、同名同版があれば停止する。旧モデルを削除しない。
- 実データに同一マートキーの複数イベントがないため、別途オフラインfixtureで合算をテストした。
- 修正前Notebookを説明する古い手順とREADMEの検証記録リンクを修正した。

## MLの参考結果

合成データ・固定分割のローカル実行では、学習80台／評価20台、決定木のaccuracyおよびbalanced accuracyは0.60、多数派基準は0.50でした。小さな教育用データの一度の評価であり、本番精度や一般化性能の保証ではありません。全200台の予測を精度評価に使いません。

## 未実施の実機確認

- GitHub公開・Git連携、参加者Workspace経由の取込・dbt実行。
- 参加者のNotebookサービス起動権限、対話カーネルとロール選択、保存確認の操作。
- StreamlitのSiS起動・公開・アナリスト閲覧。
- GUI保存内容とAgent SQLの同等性、CoWorkの実効権限と質問結果。
- 必須ルートを3時間以内に実施できるか。

GitHub作成・commit・pushは実施していません。旧リポジトリと復元バックアップは変更していません。

## ローカル再検証

教材作成者向け。ルートフォルダで依存導入済みPythonを使います。受講者のPCで実行する手順ではありません。

```bash
python -B scripts/audit_data.py
python -B scripts/test_data.py
python -B scripts/test_setup.py
python -B scripts/test_aggregation.py
python -m unittest discover -s app/tests
python -m pytest -q -p no:cacheprovider notebooks/tests/test_mlops_offline.py
python -B supplemental/test_supplemental.py
python -B dbt/verification/verify_local.py
```

Notebookの検査はpytestで行います。unittest discoverでは収集されず、0テストになるため検査成功として扱いません。dbtの検証器はローカルにtarget/logsを生成しますが、ネットワークは遮断して実行する設計です。