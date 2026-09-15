# 放送データ基盤ハンズオン

5局を別々に整え、最後にまとめて分析する日本語教材です。旧 `broadcast-viewing-handson-ja` を参考に、処理と費用の局別管理、MLOps体験を中心に再構成しました。

**状態：2026-09-15にトライアルでParquet取込、局別・共通dbt、モデル登録・推論・200台の保存、Semantic View集計を確認しました。GitHubリポジトリは非公開です。Streamlit・Agentは配置済みですが、GUI・CoWork・参加者操作の通し確認は未完了です。[検証記録](docs/verification.md)と[講師用チェックリスト](docs/instructor.md)を参照してください。**

## この教材で体験すること

- Parquetの内部をzstdで圧縮した5局のデータを取り込む。
- dbtで局ごとに表記を整え、テストで確認し、マートを作る。
- 局別WHで計算したあと、共通WHでだけ5局を統合する。
- Notebook1本でモデルを学習・評価・登録し、登録したモデルから予測する。
- 結果をStreamlitで見て、Semantic ViewとAgentを通してCoWorkから質問する。

```text
Parquet/zstd 5局分
   ├─ NW01用WH → 整形 → テスト → NW01マート
   ├─ NW02用WH → 整形 → テスト → NW02マート
   ├─ NW03用WH → 整形 → テスト → NW03マート
   ├─ NW04用WH → 整形 → テスト → NW04マート
   └─ NW05用WH → 整形 → テスト → NW05マート
                                ↓ 全局成功後
                  共通WH → UNION ALL → COMMON.VIEWING_DAILY
                                      ├─ Notebook → ML.PREDICTIONS
                                      ├─ Streamlit（実績＋予測）
                                      └─ Semantic View → Agent → CoWork
```

WH（ウェアハウス）は計算担当であり、データの保存場所ではありません。WH別の計算費用と、ストレージやAIの費用は別に確認します。

## 必須ルート

以下の順に進めます。3時間の枠を目標とした範囲ですが、実測による所要時間確認はまだです。補足はすべて飛ばして構いません。

| 順 | 内容 | 手順 | 操作するもの |
|---|---|---|---|
| 1 | 環境準備・Parquet取込 | [セットアップ](docs/01_setup.md) | `sql/01_setup.sql` → `sql/02_load_parquet.sql` |
| 2 | 局別dbtと最後の統合 | [dbt](docs/02_dbt.md) | 5局を各targetでbuild → common targetでbuild |
| 3 | MLOps | [Notebook手順](docs/03_mlops.md) | `notebooks/03_mlops.ipynb` |
| 4 | グラフで見る | [Streamlit](docs/04_streamlit.md) | warehouse runtime経路を推奨。`app/`の3ファイル |
| 5 | 自然言語で質問 | [SV・Agent・CoWork](docs/05_agent.md) | SVはSQL → AgentはGUI → 権限SQL → CoWork |

MLOpsは合成データのスポーツ関心ラベルを扱います。年齢・性別や実在の視聴者を識別しません。精度を追い込む教材ではなく、モデルに版を付けて予測結果を残す入口です。保存セルは誤操作防止のため明示的な確認が必要です。

## 補足・講師デモ・対象外

- **補足**：[基本SQL、Cortex Search、定期実行の考え方](supplemental/README.md)。Searchなしでも必須Agentは動く構成です。
- **講師デモのみ**：App Runtime。講師の既存環境で見せ、参加者は構築しません。
- **対象外**：DCR、外部モデルファイル持ち込み、高度な自動再学習、CoCo Desktopの参加者インストール。
- 本編はSnowsight中心。`scripts/`、ローカルのテストコマンド、`CONTRACT.md`は教材作成者向けです。

## 前提

機能とパッケージが使用できるSnowflakeアカウント、管理者による初期準備、SnowsightのGit-backed Workspaceを用意します。ローカルPCのPythonは受講者に不要です。現状のGitHubリポジトリは非公開のため、認証なしの教材Git取込SQLはそのままでは使えません。参加者向けの公開、または非公開Git用の認証設定を別途完了してから取り込みます。

1アカウントに教材1組を想定します。同じアカウントに参加者ごとの独立環境を作る場合は全教材にわたる名前の変更が必要です。新DBは `BCAST_PLATFORM_HANDSON`。旧DB `BCAST_VIEWING_HANDSON` は変更しません。

## データ

架空200台・2026年7月の30日・視聴区間18,000行、各局3,600行です。時刻は日本の壁時計時刻を想定したTIMESTAMP_NTZです。5局共通の端末ID突合は済んでいる前提です。各局のリーチが同じになる等の人工的な設計があり、市場規模やモデル精度の根拠には使えません。

## 終了・検証

[講師用チェックリスト](docs/instructor.md)と[検証記録](docs/verification.md)に実施範囲を記録します。[cleanup.sql](sql/cleanup.sql)は新教材を削除する破壊的操作なので、保持するものを確認してから、コメントを読んで必要な箇所だけ実行します。Workspace開発アプリ等は別途停止・整理します。