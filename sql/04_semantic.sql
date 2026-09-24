-- 目的: 視聴日・放送局・ジャンルと、リーチ・視聴時間・視聴回数の意味をセマンティックビューに定義します。
-- 前提: 第2章のCOMMON作成と03_check_common.sqlの確認が完了していること。
-- 実行方法: ハンズオン用アカウントで上から順に実行してください。
-- 新規作成用。既存 SV_VIEWING は自動置換せず、定義を確認してから扱ってください。
-- 完了の目安: 定義が表示され、最後の2つのSELECTで同じ期間の3指標が一致すること。
-- ここで得た値を、第5章でGUIから質問した回答と比較してください。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

-- DIMENSIONSは集計の切り口、METRICSは集計式です。説明文はAIが指標を解釈するときにも使われます。
CREATE SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  TABLES (
    viewing AS BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY
      COMMENT = '合成視聴データ。1行は放送局・端末・視聴日・ジャンル。5局のマートを UNION ALL したもの'
  )
  DIMENSIONS (
    viewing.view_date AS VIEW_DATE
      WITH SYNONYMS = ('視聴日', '日付')
      COMMENT = '視聴開始日。教材のデータ範囲は2026-05-01から2026-07-31',
    viewing.network_id AS NETWORK_ID
      WITH SYNONYMS = ('放送局', '局', 'ネットワーク')
      COMMENT = 'NW01, NW02, NW03, NW04, NW05',
    viewing.genre AS GENRE
      WITH SYNONYMS = ('ジャンル')
      COMMENT = '視聴開始時の番組ジャンル。NEWS=ニュース、DRAMA=ドラマ、VARIETY=バラエティ、ANIME=アニメ、SPORTS=スポーツ、MUSIC=音楽、MOVIE=映画、INFO=情報の8種類だけ。それ以外は不正値'
  )
  METRICS (
    viewing.distinct_reach AS COUNT(DISTINCT DEVICE_ID)
      WITH SYNONYMS = ('リーチ', '到達端末数', 'ユニーク端末数')
      COMMENT = '対象範囲内の端末IDの重複を除いた数。人数・世帯数ではない。日・局・ジャンル別のリーチは加算できない。範囲全体で再集計する',
    viewing.total_minutes AS SUM(VIEW_MINUTES)
      WITH SYNONYMS = ('総視聴時間', '視聴時間分')
      COMMENT = '各視聴区間の経過秒数を60で割った分数の合計。全区間を開始日・開始時のジャンルに計上する。番組ごとの正確な視聴時間や分別曲線の面積ではない',
    viewing.total_sessions AS SUM(SESSION_COUNT)
      WITH SYNONYMS = ('総視聴回数', 'セッション数')
      COMMENT = '各整形済み視聴区間を1回として数えた回数の合計。マートの行数ではなく SESSION_COUNT を加算する'
  )
  COMMENT = '5局共通の視聴実績。COMMON のみを参照。受講時も同条件の元テーブル集計と指標を照合する';

-- 分析用ロールから、このセマンティックビューを参照できるようにします。
GRANT SELECT, REFERENCES ON SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  TO ROLE BCAST_PLATFORM_ANALYST_ROLE;

-- ここからは作成後の読み取り確認。結果を第5章の比較に使います。
DESCRIBE SEMANTIC VIEW BCAST_PLATFORM_HANDSON.MART.SV_VIEWING;

SELECT * FROM SEMANTIC_VIEW(
  BCAST_PLATFORM_HANDSON.MART.SV_VIEWING
  METRICS viewing.distinct_reach, viewing.total_minutes, viewing.total_sessions
  WHERE viewing.view_date BETWEEN '2026-05-01'::DATE AND '2026-07-31'::DATE
);

-- 同じ期間を元テーブルから直接集計します。リーチは端末数であり、人数や世帯数ではありません。
-- TOTAL_MINUTESは分単位です。小数の末尾に丸め誤差がある場合は、表示桁だけで不一致と判断しないでください。
SELECT COUNT(DISTINCT DEVICE_ID) AS DISTINCT_REACH,
       SUM(VIEW_MINUTES) AS TOTAL_MINUTES,
       SUM(SESSION_COUNT) AS TOTAL_SESSIONS
FROM BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY
WHERE VIEW_DATE BETWEEN '2026-05-01'::DATE AND '2026-07-31'::DATE;