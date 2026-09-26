# 5局横断 視聴インテリジェンス - App Runtime

既存のStreamlit分析画面と `VIEWING_AGENT` 問い合わせを、1つのNext.jsアプリへ統合した講師デモです。Snowflake App Runtimeの `APPLICATION SERVICE` として動かすことを前提にしています。

> Snowflake App Runtimeはトライアルアカウントでは利用できません。このソースはローカル開発と有償アカウントでの講師デモ用です。受講者向けの本編は引き続き `app/` のStreamlitとChapter 5のCoWorkを使います。

## 機能

- 重複除外リーチ、総視聴時間、視聴区間、1台あたり視聴の経営サマリー
- 日別・局別・ジャンル別の視聴トレンド
- 検証済みF1在籍予測スナップショットの分布
- 局別の毎分視聴パルス
- `BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT` への複数ターン問い合わせ
- Agentが返す回答、警告、表、Vega-Liteグラフの表示

## Snowflake参照先

- `BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY`
- `BCAST_PLATFORM_HANDSON.COMMON.MINUTE_AUDIENCE`
- `BCAST_PLATFORM_HANDSON.ML.PREDICTIONS`
- `BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT`
- Query warehouse: `BCAST_PLATFORM_COMMON_WH`

ダッシュボードはApplication Service所有ロールで問い合わせます。Agentは利用者の権限を尊重するため、API routeからcaller’s rightsで `SNOWFLAKE.CORTEX.DATA_AGENT_RUN` を実行します。利用者の既定ロール・既定WHと、Application Service所有ロールへのcaller grantが必要です。

## ローカル検証

Node.js 22以降とSnowflake CLI接続が必要です。既定接続がトライアルや検証対象外アカウントの場合、実データへの問い合わせは行わずテストとビルドだけを実行してください。

```bash
npm ci
npm test
npm run build
```

適切な有償アカウントへの接続がある場合だけ、ローカル画面を起動します。

```bash
SNOWFLAKE_CONNECTION_NAME=<paid-account-connection> npm run dev
```

## 有償アカウントへ配置

1. 同じワークショップオブジェクトを有償アカウントへ用意します。
2. `sql/06_app_runtime_setup.sql` を管理者と確認して実行します。
3. このフォルダでテンプレート付属のbuild-only `app.yml`を一時退避します。
4. `snow app setup --app-name BCAST_VIEWING_INTELLIGENCE --database BCAST_PLATFORM_HANDSON --schema MART --warehouse BCAST_PLATFORM_COMMON_WH --dry-run` を実行します。
5. 問題がなければ `--dry-run` を外し、生成されたmanifestへbuild-only `app.yml`の `install` / `build` / `run` と表示情報をマージします。
6. `snow app validate`、`snow app deploy --verbose` の順に実行します。
7. `GRANT USAGE ON APPLICATION SERVICE ... TO ROLE BCAST_PLATFORM_ANALYST_ROLE` を実行して共有します。

CLIが生成するmanifest形式を正本とし、手作業で接続先を `snowhouse` やトライアルアカウントへ固定しません。

## 主要ファイル

| パス | 役割 |
|---|---|
| `components/broadcast-workspace.tsx` | 条件、画面切替、全体レイアウト |
| `components/dashboard.tsx` | 4つの分析ビューとチャート |
| `components/agent-workspace.tsx` | 複数ターンAgent UIと表・グラフ表示 |
| `app/api/dashboard/` | パラメータ検証済みの分析API |
| `app/api/agent/route.ts` | caller’s rightsによるAgent実行 |
| `lib/broadcast.ts` | SQL生成と予測完全性検証 |
| `lib/agent.ts` | Agent入力・応答型と検証 |
| `lib/snowflake.ts` | App RuntimeのSnowflake接続 |
