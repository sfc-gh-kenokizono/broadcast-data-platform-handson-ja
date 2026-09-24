-- 目的（任意）: ジャンル別の視聴指標と、重なる視聴区間をまとめるSQLの考え方を確認します。
-- 前提: 第2章のCOMMON作成とsql/02_check_common.sqlの確認が完了していること。
-- 実行方法: ハンズオン用アカウントで上から順に実行してください。参照だけで、既存の表は変更しません。
-- 完了の目安: ジャンル別の集計結果と、末尾の例でINPUT_ROWS=7、FOLDED_ROWS=3が表示されること。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
USE DATABASE BCAST_PLATFORM_HANDSON;
USE SCHEMA BCAST_PLATFORM_HANDSON.MART;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

-- 接続先・ロール・データベース・ウェアハウスが教材用であることを確認してから続けてください。
SELECT CURRENT_ACCOUNT() AS ACCOUNT_NAME,
       CURRENT_ROLE() AS ROLE_NAME,
       CURRENT_DATABASE() AS DATABASE_NAME,
       CURRENT_WAREHOUSE() AS WAREHOUSE_NAME;

-- リーチはジャンルごとに重複を除いた端末数です。ジャンル別の値を足して全体リーチにはできません。
-- 視聴回数はSESSION_COUNT、視聴時間はVIEW_MINUTES（分）の合計で確認します。
-- 例えば同じ端末がNEWSとSPORTSを見れば両方のリーチに1ずつ入ります。人数・世帯数やF1層の人数を数えているわけではありません。
-- 結果は期間内のジャンル別集計です。本編のデータがそろっていれば8ジャンルを確認でき、次は区間のまとめ方を小さな例で学びます。
SELECT GENRE,
       COUNT(DISTINCT DEVICE_ID) AS DISTINCT_REACH,
       SUM(SESSION_COUNT) AS TOTAL_SESSIONS,
       SUM(VIEW_MINUTES) AS TOTAL_MINUTES
FROM BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY
WHERE VIEW_DATE >= '2026-05-01'::DATE
  AND VIEW_DATE < '2026-08-01'::DATE
GROUP BY GENRE
ORDER BY GENRE;

-- 以下は表に保存しない7行の例です。同じ端末・局・ジャンルで重なる区間や接する区間をまとめます。
-- 期待する3区間は08:00〜08:50（4行）、09:00〜09:20（2行）、10:00〜10:05（1行）です。
-- 実データの加工処理を変更するものではありません。WITHから末尾のSELECTまでまとめて実行してください。
WITH fixture (EVENT_ID, DEVICE_ID, NETWORK_ID, GENRE, FROM_TEXT, TO_TEXT) AS (
    SELECT * FROM VALUES
        (1, 'C000001', 'NW01', 'NEWS', '2026-07-01 08:00:00', '2026-07-01 08:30:00'),
        (2, 'C000001', 'NW01', 'NEWS', '2026-07-01 08:05:00', '2026-07-01 08:10:00'),
        (3, 'C000001', 'NW01', 'NEWS', '2026-07-01 08:25:00', '2026-07-01 08:40:00'),
        (4, 'C000001', 'NW01', 'NEWS', '2026-07-01 08:40:00', '2026-07-01 08:50:00'),
        (5, 'C000001', 'NW01', 'NEWS', '2026-07-01 09:00:00', '2026-07-01 09:10:00'),
        (6, 'C000001', 'NW01', 'NEWS', '2026-07-01 09:10:00', '2026-07-01 09:20:00'),
        (7, 'C000001', 'NW01', 'NEWS', '2026-07-01 10:00:00', '2026-07-01 10:05:00')
), typed_intervals AS (
    -- 文字列の時刻を日時型へ変換し、大小比較やMIN/MAXで視聴区間を扱えるようにします。
    SELECT EVENT_ID, DEVICE_ID, NETWORK_ID, GENRE,
           FROM_TEXT::TIMESTAMP_NTZ AS VIEW_FROM,
           TO_TEXT::TIMESTAMP_NTZ AS VIEW_TO
    FROM fixture
), preceding_bounds AS (
    -- 08:25開始の直前行は08:10終了ですが、その前の区間は08:30まで続いています。直前行だけだと誤って分断します。
    -- 自分より前の全行の終了時刻の最大値を使うと、短い区間が長い区間に内包される場合もつながりを判定できます。
    SELECT *,
           MAX(VIEW_TO) OVER (
               PARTITION BY DEVICE_ID, NETWORK_ID, GENRE
               ORDER BY VIEW_FROM, VIEW_TO, EVENT_ID
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS PREVIOUS_MAX_TO
    FROM typed_intervals
), boundaries AS (
    -- 最初の行、または既存区間と隙間がある行だけNEW_GROUP=1にします。終了と開始が同時刻なら同じ区間に含めます。
    SELECT *,
           CASE WHEN PREVIOUS_MAX_TO IS NULL OR VIEW_FROM > PREVIOUS_MAX_TO
                THEN 1 ELSE 0 END AS NEW_GROUP
    FROM preceding_bounds
), numbered AS (
    -- NEW_GROUPの累積和をグループ番号にします。隙間に出会うたび1増えるので、連続する行を同じ番号で集計できます。
    SELECT *,
           SUM(NEW_GROUP) OVER (
               PARTITION BY DEVICE_ID, NETWORK_ID, GENRE
               ORDER BY VIEW_FROM, VIEW_TO, EVENT_ID
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
           ) AS INTERVAL_GROUP
    FROM boundaries
), folded AS (
    -- 同じ番号の最も早い開始と最も遅い終了で1区間にまとめます。SOURCE_ROWSはその区間にまとめた入力行数です。
    SELECT DEVICE_ID, NETWORK_ID, GENRE,
           MIN(VIEW_FROM) AS VIEW_FROM,
           MAX(VIEW_TO) AS VIEW_TO,
           COUNT(*) AS SOURCE_ROWS
    FROM numbered
    GROUP BY DEVICE_ID, NETWORK_ID, GENRE, INTERVAL_GROUP
)
-- 結果3行のSOURCE_ROWSは4・2・1、各行のINPUT_ROWSは7、FOLDED_ROWSは3なら期待どおりです。
-- 重なりをまとめると区間数や時間の意味が変わります。この例を本編のdbtに追加する操作ではありません。
SELECT DEVICE_ID, NETWORK_ID, GENRE, VIEW_FROM, VIEW_TO, SOURCE_ROWS,
       SUM(SOURCE_ROWS) OVER () AS INPUT_ROWS,
       COUNT(*) OVER () AS FOLDED_ROWS
FROM folded
ORDER BY DEVICE_ID, NETWORK_ID, GENRE, VIEW_FROM;