# 任意講師デモ: App Runtime統合アプリ

この任意デモは、第4章のリッチな分析画面と第5章の `VIEWING_AGENT` を1つのWebアプリに統合します。Next.jsで作られ、Snowflakeでは `APPLICATION SERVICE` として動きます。

## 重要な前提

Snowflake App Runtimeはトライアルアカウントでは利用できません。受講者が使うトライアル環境へはDeployせず、本編のStreamlitとCoWorkを置き換えません。講師が同じデータ、Semantic View、Agentを用意した有償アカウントでのみDeployします。

ソースは [`app-runtime/`](../app-runtime/) にあります。現在の接続先 `snowhouse` へ自動Deployする手順でもありません。

## 統合される機能

| 領域 | 内容 |
|---|---|
| 分析ダッシュボード | 経営サマリー、視聴トレンド、F1在籍予測、毎分パルス |
| Agent | `VIEWING_AGENT`への日本語質問、複数ターン会話 |
| Agent結果 | 回答文、権限警告、表、Agent生成のVega-Liteグラフ |
| セキュリティ | SQLバインド、入力検証、サーバー側Agent実行、caller’s rights |

```text
ブラウザ
  ├─ Dashboard API → COMMON / ML（Application Service所有ロール）
  └─ Agent API → DATA_AGENT_RUN → VIEWING_AGENT（caller’s rights）
                                  └─ SV_VIEWING → COMMON.VIEWING_DAILY
```

## ローカルで確認する

リポジトリをPull後、`app-runtime/README.md`に従って `npm ci`、`npm test`、`npm run build` を実行します。トライアルや `snowhouse` をデータ接続先にして動作確認しません。

## 有償アカウントへDeployする

1. `BCAST_PLATFORM_HANDSON`の必要な表、Semantic View、Agentを有償アカウントへ用意します。
2. 接続先を確認し、管理者レビュー後に [`sql/06_app_runtime_setup.sql`](../sql/06_app_runtime_setup.sql) を実行します。
3. `app-runtime/README.md`に従い、`snow app setup`でそのアカウント用のmanifestを生成します。
4. `snow app validate`で構成を検証します。
5. `snow app deploy --verbose`でDeployし、返されたApplication Service URLを開きます。
6. ダッシュボード4画面と、質問例を使ったAgent応答・表・グラフを確認します。
7. 必要な利用ロールだけへApplication Serviceの `USAGE` を付与します。

接続先、データベース、スキーマ、WHを手書きで別アカウントへ流用しません。CLIが生成したmanifestを正本にします。
