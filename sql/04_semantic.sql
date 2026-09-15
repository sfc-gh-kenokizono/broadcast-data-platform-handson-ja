-- 2026-09-15トライアルで作成・元テーブルとの指標一致を確認。
-- 第2章の COMMON 作成後に、参加者が対象環境で実行します。
-- 新規作成用。既存 SV_VIEWING は自動置換せず、定義を確認してから扱ってください。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

CREATE SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  TABLES (
    viewing AS BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY
      COMMENT = '合成視聴データ。1行は放送局・端末・視聴日・ジャンル。5局のマートを UNION ALL したもの'
  )
  DIMENSIONS (
    viewing.view_date AS VIEW_DATE
      WITH SYNONYMS = ('視聴日', '日付')
      COMMENT = '視聴日。教材のデータ範囲は2026-07-01から2026-07-30',
    viewing.network_id AS NETWORK_ID
      WITH SYNONYMS = ('放送局', '局', 'ネットワーク')
      COMMENT = 'NW01, NW02, NW03, NW04, NW05',
    viewing.genre AS GENRE
      WITH SYNONYMS = ('ジャンル')
      COMMENT = 'NEWS=ニュース、DRAMA=ドラマ、VARIETY=バラエティ、ANIME=アニメ、SPORTS=スポーツ'
  )
  METRICS (
    viewing.distinct_reach AS COUNT(DISTINCT DEVICE_ID)
      WITH SYNONYMS = ('リーチ', '到達端末数', 'ユニーク端末数')
      COMMENT = '対象範囲内の端末IDの重複を除いた数。人数・世帯数ではない。日・局・ジャンル別のリーチは加算できない。範囲全体で再集計する',
    viewing.total_minutes AS SUM(VIEW_MINUTES)
      WITH SYNONYMS = ('総視聴時間', '視聴時間分')
      COMMENT = '視聴分数の合計。単位は分',
    viewing.total_sessions AS SUM(SESSION_COUNT)
      WITH SYNONYMS = ('総視聴回数', 'セッション数')
      COMMENT = '視聴回数の合計。マートの行数ではなく SESSION_COUNT を加算する'
  )
  COMMENT = '5局共通の視聴実績。COMMON のみを参照。指標の実環境検証は教材実施時に行う';

GRANT SELECT, REFERENCES ON SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  TO ROLE BCAST_PLATFORM_ANALYST_ROLE;

-- ここからは作成後の読み取り確認。結果を第5章の比較に使います。
DESCRIBE SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING;

SELECT * FROM SEMANTIC_VIEW(
  BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  METRICS viewing.distinct_reach, viewing.total_minutes, viewing.total_sessions
  WHERE viewing.view_date BETWEEN '2026-07-01'::DATE AND '2026-07-30'::DATE
);

SELECT COUNT(DISTINCT DEVICE_ID) AS DISTINCT_REACH,
       SUM(VIEW_MINUTES) AS TOTAL_MINUTES,
       SUM(SESSION_COUNT) AS TOTAL_SESSIONS
FROM BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY
WHERE VIEW_DATE BETWEEN '2026-07-01'::DATE AND '2026-07-30'::DATE;