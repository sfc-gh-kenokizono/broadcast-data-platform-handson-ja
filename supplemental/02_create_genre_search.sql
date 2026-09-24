-- 目的（任意）: 教材用のジャンル説明5件を検索するCortex Searchサービスを作成します。
-- 前提: sql/01_01_setup.sqlが完了し、この機能を利用できる環境とMARTへのCREATE CORTEX SEARCH SERVICE権限があること。
-- 権限が不足する場合は講師に確認してください。このSQLは権限を追加しません。
-- 実行方法: ハンズオン用アカウントで接続情報を確認してから、上から順に実行してください。
-- 新規作成用です。同名のSVC_GENRE_GUIDEが既にある場合は、削除・置換せず講師に確認してください。
-- 完了の目安: 作成が成功し、最後のSEARCH_RESULTにGENREとGUIDE_TEXTを含む検索結果が表示されること。
-- Searchサービスの利用には料金が発生します。不要になったら教材の後片付け手順を確認してください。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
USE DATABASE BCAST_PLATFORM_HANDSON;
USE SCHEMA BCAST_PLATFORM_HANDSON.MART;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

-- 接続先・ロール・データベース・ウェアハウスが教材用であることを確認します。
SELECT CURRENT_ACCOUNT() AS ACCOUNT_NAME,
       CURRENT_ROLE() AS ROLE_NAME,
       CURRENT_DATABASE() AS DATABASE_NAME,
       CURRENT_WAREHOUSE() AS WAREHOUSE_NAME;

-- GUIDE_TEXTを検索対象、GENREを絞り込み用の属性として登録します。
-- 下の説明は実在番組の情報ではなく架空の5件です。本編の視聴実績や8ジャンル全体を検索するものではありません。
-- 作成時に初回の検索用データを準備し、以降の更新目標は1時間に設定します。
-- EMBEDDING_MODELは説明文を意味で比較するためのモデルの選択です。F1同居予測の学習とは別です。
-- FULLは検索元全体からの更新、ON_CREATEは作成時の初期化です。元は固定のVALUES 5件なので、視聴ログが増えても検索対象は増えません。
-- TARGET_LAGはデータの鮮度目標で、検索の応答時間ではありません。作成が成功したら下の問合せで結果の中身を確認します。
CREATE CORTEX SEARCH SERVICE BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE
    ON GUIDE_TEXT
    ATTRIBUTES GENRE
    WAREHOUSE = BCAST_PLATFORM_COMMON_WH
    TARGET_LAG = '1 hour'
    EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
    REFRESH_MODE = FULL
    INITIALIZE = ON_CREATE
AS
SELECT COLUMN1::VARCHAR AS GENRE,
       COLUMN2::VARCHAR AS GUIDE_TEXT
FROM VALUES
    ('NEWS', 'NEWS ニュース。社会の出来事、地域の話題、政治や経済の動きを伝えるジャンル。教材用の架空説明です。'),
    ('DRAMA', 'DRAMA ドラマ。登場人物の関係や成長を物語として描くジャンル。教材用の架空説明です。'),
    ('VARIETY', 'VARIETY バラエティ。トーク、クイズ、企画などを楽しむジャンル。教材用の架空説明です。'),
    ('ANIME', 'ANIME アニメ。アニメーションで物語やキャラクターを表現するジャンル。教材用の架空説明です。'),
    ('SPORTS', 'SPORTS スポーツ。試合の結果、選手の活躍、競技の解説や中継を扱うジャンル。教材用の架空説明です。');

-- スポーツに関する質問で最大3件を検索します。返された説明が質問の内容に合うか確認してください。
-- このサービスは本編のVIEWING_AGENTに自動追加されません。
-- SEARCH_RESULTは検索結果をまとめた1つの値です。最大3件とはその中の候補数で、SQL結果が3行になるという意味ではありません。
-- SPORTSの説明が質問に合う候補として含まれるか確認します。これは関連文の検索であり、視聴数の集計や回答文の生成ではありません。
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE',
    '{"query":"試合の結果や選手の活躍を知りたい","columns":["GENRE","GUIDE_TEXT"],"limit":3}'
) AS SEARCH_RESULT;