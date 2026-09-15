# 放送データ基盤ハンズオン

5局を別々に整え、最後にまとめて分析する日本語教材です。Snowsightにこのリポジトリを取り込み、手順に沿って演習します。

> 実施前に講師から利用アカウント・ロール・実行環境の案内を受けてください。データ処理・モデル登録と推論・Semantic View集計はトライアルで確認済みですが、参加者のGit Workspace経路、Streamlit画面、Agent GUI・CoWorkの一連の操作は未確認です。

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
- 本編はSnowsight中心です。データ生成やローカルPCでの検証は不要です。

## 前提

機能とパッケージが使用できるSnowflakeアカウント、管理者による初期準備、SnowsightのGit-backed Workspaceを用意します。ローカルPCのPythonは不要です。[公開リポジトリ](https://github.com/sfc-gh-kenokizono/broadcast-data-platform-handson-ja)を使い、[第1章](docs/01_setup.md)から進めます。

1アカウントに教材1組を想定します。同じアカウントに参加者ごとの独立環境を作る場合は全教材にわたる名前の変更が必要です。新DBは `BCAST_PLATFORM_HANDSON`。旧DB `BCAST_VIEWING_HANDSON` は変更しません。

## データ

架空200台・2026年7月の30日・視聴区間18,000行、各局3,600行です。時刻は日本の壁時計時刻を想定したTIMESTAMP_NTZです。5局共通の端末ID突合は済んでいる前提です。各局のリーチが同じになる等の人工的な設計があり、市場規模やモデル精度の根拠には使えません。

## フォルダの見方

- `docs/`：第1〜5章の受講手順とAgentへ貼り付ける文章。
- `data/`：取込用のParquet。生成済みなので、そのまま使います。
- `dbt/`：整形・集計と、演習で実行するデータ品質テスト。
- `notebooks/`：学習・評価・モデル登録・予測を行うNotebook。
- `app/`：Streamlitに配置する3ファイル。
- `sql/`：環境準備・取込・Semantic View・Agent・後片付け。
- `supplemental/`：希望者向けの補足教材。

## 終了

[cleanup.sql](sql/cleanup.sql)は教材環境を削除する操作です。保持するものを確認し、講師の案内に従って実行してください。Workspaceの開発アプリ等は別途停止・整理します。