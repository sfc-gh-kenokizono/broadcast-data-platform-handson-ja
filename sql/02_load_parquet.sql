-- 目的: mainブランチのdataフォルダにあるParquetファイル8個を確認し、教材のRAWテーブルに取り込みます。
-- 前提: 01_setup.sqlが完了し、最後のLISTで8個のファイルを確認できていること。
-- 実行方法: 同じハンズオン用アカウントで上から順に実行します。
-- EXECUTE IMMEDIATE $$から対応する$$;までは1つの処理です。途中だけを選択して実行しないでください。
-- 完了の目安: 最後の結果にF1_SIGNAL_V2の8行が表示され、各ROW_COUNTが下のEXPECTED_ROWSと一致します。
-- 再実行できるのは同じ版・同じ内容のデータだけです。旧データは自動移行・削除しません。
-- 移行が必要な場合は作業を止めて講師に相談し、管理者が承認済みのバックアップ付き手順を実施します。
-- 読取エラー時は作業を止め、講師へ確認してください。別のブランチや以前のファイルに切り替えないでください。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
USE DATABASE BCAST_PLATFORM_HANDSON;
USE SCHEMA BCAST_PLATFORM_HANDSON.RAW;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

EXECUTE IMMEDIATE $$
DECLARE
  -- 既存データの保護のため、表の構造・データの版・ファイル・予測結果・同時実行を確認します。
  -- エラーは確認を省略して進める合図ではありません。内容を講師に伝え、原因を確認してください。
  incompatible_schema EXCEPTION (-20001, '取込先テーブルの列名または型が教材と一致しません。ここで作業を止め、既存データを削除・上書きせずに講師へ確認してください。');
  incompatible_data EXCEPTION (-20002, '既にあるデータが、この教材の版と一致しません。上書きは行いません。作業を止めて講師に連絡し、管理者が承認したバックアップ付きの手順を実施してから、01_setup.sqlと02_load_parquet.sqlをやり直してください。');
  incompatible_files EXCEPTION (-20003, '教材のファイル8個、想定の行数、有効なラベルを確認できませんでした。別のブランチや以前のファイルへ切り替えず、作業を止めて講師に確認してください。');
  stale_predictions EXCEPTION (-20005, '既にある予測結果が、この教材データから作られたものか確認できません。作業を止めて講師に確認してください。予測結果を消して進めないでください。');
  lock_failed EXCEPTION (-20006, '取込の重複を防ぐ管理情報が想定と異なります。作業を止めて講師に確認してください。セットアップや取込を同時に実行しないでください。');
  definitions RESULTSET;
  definitions_table VARCHAR;
  pass_count INTEGER;
  manifest_count INTEGER;
  schema_mismatches INTEGER;
  file_count INTEGER;
  metadata_count INTEGER;
  existing_rows INTEGER;
  invalid_rows INTEGER;
  unique_devices INTEGER;
  panel_rows INTEGER;
  viewing_rows INTEGER DEFAULT 0;
  prediction_tables INTEGER;
  prediction_columns INTEGER;
  raw_table VARCHAR;
  snapshot_table VARCHAR;
  statement VARCHAR;
  load_id VARCHAR DEFAULT REPLACE(UUID_STRING(), '-', '');
  snapshots_prefix VARCHAR;
  manifest_table VARCHAR;
  load_time TIMESTAMP_NTZ DEFAULT SYSDATE();
BEGIN
  -- 実行ごとに異なる名前の一時テーブルを使い、確認が終わるまで既存のRAWデータに触れません。
  -- 下の一覧は、取り込む8ファイルの名前・期待件数・列の対応です。
  snapshots_prefix := 'BCAST_PLATFORM_HANDSON.RAW.LOAD_' || load_id || '_';
  manifest_table := snapshots_prefix || 'MANIFEST';
  definitions_table := snapshots_prefix || 'DEFINITIONS';
  CREATE TEMPORARY TABLE IDENTIFIER(:definitions_table) AS
    SELECT COLUMN1 AS TABLE_NAME, COLUMN2 AS FILE_NAME, COLUMN3 AS EXPECTED_ROWS,
           COLUMN4 AS COLUMNS_SQL, COLUMN5 AS PROJECTION_SQL
    FROM VALUES
      ('VIEWING_LOG_NW01', 'viewing_log_nw01.parquet', 195938,
       'EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE',
       '$1:EVENT_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:DEVICE_ID::VARCHAR, $1:VIEW_FROM::TIMESTAMP_NTZ, $1:VIEW_TO::TIMESTAMP_NTZ, $1:GENRE::VARCHAR'),
      ('VIEWING_LOG_NW02', 'viewing_log_nw02.parquet', 184465,
       'EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE',
       '$1:EVENT_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:DEVICE_ID::VARCHAR, $1:VIEW_FROM::TIMESTAMP_NTZ, $1:VIEW_TO::TIMESTAMP_NTZ, $1:GENRE::VARCHAR'),
      ('VIEWING_LOG_NW03', 'viewing_log_nw03.parquet', 179991,
       'EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE',
       '$1:EVENT_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:DEVICE_ID::VARCHAR, $1:VIEW_FROM::TIMESTAMP_NTZ, $1:VIEW_TO::TIMESTAMP_NTZ, $1:GENRE::VARCHAR'),
      ('VIEWING_LOG_NW04', 'viewing_log_nw04.parquet', 234324,
       'EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE',
       '$1:EVENT_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:DEVICE_ID::VARCHAR, $1:VIEW_FROM::TIMESTAMP_NTZ, $1:VIEW_TO::TIMESTAMP_NTZ, $1:GENRE::VARCHAR'),
      ('VIEWING_LOG_NW05', 'viewing_log_nw05.parquet', 255930,
       'EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE',
       '$1:EVENT_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:DEVICE_ID::VARCHAR, $1:VIEW_FROM::TIMESTAMP_NTZ, $1:VIEW_TO::TIMESTAMP_NTZ, $1:GENRE::VARCHAR'),
      ('DEVICE_LABELS', 'device_labels.parquet', 20000,
       'DEVICE_ID, LABEL_AVAILABLE, TARGET_F1', '$1:DEVICE_ID::VARCHAR, $1:LABEL_AVAILABLE::BOOLEAN, $1:TARGET_F1::INTEGER'),
      ('PROGRAM_MASTER', 'program_master.parquet', 60,
       'PROGRAM_ID, PROGRAM_NAME, NETWORK_ID, GENRE, TIME_SLOT, DURATION_MIN, SYNOPSIS',
       '$1:PROGRAM_ID::VARCHAR, $1:PROGRAM_NAME::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:GENRE::VARCHAR, $1:TIME_SLOT::VARCHAR, $1:DURATION_MIN::NUMBER(4,0), $1:SYNOPSIS::VARCHAR'),
      ('PROGRAM_SCHEDULE', 'program_schedule.parquet', 8747,
       'PROGRAM_ID, NETWORK_ID, AIR_DATE, AIR_FROM, AIR_TO',
       '$1:PROGRAM_ID::VARCHAR, $1:NETWORK_ID::VARCHAR, $1:AIR_DATE::DATE, $1:AIR_FROM::TIMESTAMP_NTZ, $1:AIR_TO::TIMESTAMP_NTZ');
  -- 取込先の列名と型が教材の定義どおりかを確認します。異なる場合はロード前に停止します。
  WITH expected AS (
    SELECT 'VIEWING_LOG_' || station.COLUMN1 AS TABLE_NAME,
           definition.COLUMN1 AS COLUMN_NAME, definition.COLUMN2 AS DATA_TYPE
    FROM (VALUES ('NW01'), ('NW02'), ('NW03'), ('NW04'), ('NW05')) AS station
    CROSS JOIN (VALUES ('EVENT_ID', 'TEXT'), ('NETWORK_ID', 'TEXT'), ('DEVICE_ID', 'TEXT'),
                       ('VIEW_FROM', 'TIMESTAMP_NTZ'), ('VIEW_TO', 'TIMESTAMP_NTZ'), ('GENRE', 'TEXT')) AS definition
    UNION ALL
    SELECT COLUMN1, COLUMN2, COLUMN3 FROM VALUES
      ('DEVICE_LABELS', 'DEVICE_ID', 'TEXT'), ('DEVICE_LABELS', 'LABEL_AVAILABLE', 'BOOLEAN'),
      ('DEVICE_LABELS', 'TARGET_F1', 'NUMBER'),
      ('PROGRAM_MASTER', 'PROGRAM_ID', 'TEXT'), ('PROGRAM_MASTER', 'PROGRAM_NAME', 'TEXT'),
      ('PROGRAM_MASTER', 'NETWORK_ID', 'TEXT'), ('PROGRAM_MASTER', 'GENRE', 'TEXT'),
      ('PROGRAM_MASTER', 'TIME_SLOT', 'TEXT'), ('PROGRAM_MASTER', 'DURATION_MIN', 'NUMBER'),
      ('PROGRAM_MASTER', 'SYNOPSIS', 'TEXT'),
      ('PROGRAM_SCHEDULE', 'PROGRAM_ID', 'TEXT'), ('PROGRAM_SCHEDULE', 'NETWORK_ID', 'TEXT'),
      ('PROGRAM_SCHEDULE', 'AIR_DATE', 'DATE'), ('PROGRAM_SCHEDULE', 'AIR_FROM', 'TIMESTAMP_NTZ'),
      ('PROGRAM_SCHEDULE', 'AIR_TO', 'TIMESTAMP_NTZ')
  ), actual AS (
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NUMERIC_SCALE
    FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'RAW' AND TABLE_NAME IN
      ('VIEWING_LOG_NW01', 'VIEWING_LOG_NW02', 'VIEWING_LOG_NW03', 'VIEWING_LOG_NW04',
       'VIEWING_LOG_NW05', 'DEVICE_LABELS', 'PROGRAM_MASTER', 'PROGRAM_SCHEDULE')
  )
  SELECT COUNT(*) INTO :schema_mismatches
  FROM expected FULL OUTER JOIN actual
    ON expected.TABLE_NAME = actual.TABLE_NAME AND expected.COLUMN_NAME = actual.COLUMN_NAME
  WHERE expected.COLUMN_NAME IS NULL OR actual.COLUMN_NAME IS NULL
     OR expected.DATA_TYPE != actual.DATA_TYPE
     OR (actual.DATA_TYPE = 'NUMBER' AND actual.NUMERIC_SCALE != 0);
  IF (schema_mismatches > 0) THEN
    RAISE incompatible_schema;
  END IF;

  -- GitHubのmainブランチを取得し、dataフォルダの8ファイルを内部ステージへコピーします。
  -- 演習中は配布データを変更しないでください。再取込時は保存済みの件数・内容との一致も検査します。
  ALTER GIT REPOSITORY BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO FETCH;
  COPY FILES INTO @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/
    FROM @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO/branches/main/data/
    FILES = ('viewing_log_nw01.parquet', 'viewing_log_nw02.parquet',
             'viewing_log_nw03.parquet', 'viewing_log_nw04.parquet',
             'viewing_log_nw05.parquet', 'program_master.parquet',
             'program_schedule.parquet', 'device_labels.parquet')
    DETAILED_OUTPUT = TRUE;
  SELECT COUNT(*) INTO :file_count FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  IF (file_count != 8) THEN
    RAISE incompatible_files;
  END IF;
  -- 各ファイルを一時テーブルへ読み、列・件数・ファイル内容の識別値を照合します。
  -- 検証結果は一時的な管理表にまとめ、全ファイルがそろったことを後で確認します。
  CREATE TEMPORARY TABLE IDENTIFIER(:manifest_table)
    LIKE BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES;
  pass_count := 0;
  definitions := (SELECT * FROM IDENTIFIER(:definitions_table) ORDER BY TABLE_NAME);
  FOR definition IN definitions DO
    raw_table := 'BCAST_PLATFORM_HANDSON.RAW.' || definition.TABLE_NAME;
    snapshot_table := snapshots_prefix || definition.TABLE_NAME;
    statement := 'SELECT COUNT(*) FROM (SELECT COLUMN_NAME FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.COLUMNS '
      || 'WHERE TABLE_SCHEMA = ''RAW'' AND TABLE_NAME = ''' || definition.TABLE_NAME || ''') AS expected '
      || 'FULL OUTER JOIN TABLE(INFER_SCHEMA(LOCATION => ''@BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/'
      || definition.FILE_NAME || ''', FILE_FORMAT => ''BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_PARQUET'')) AS actual '
      || 'ON expected.COLUMN_NAME = actual.COLUMN_NAME WHERE expected.COLUMN_NAME IS NULL OR actual.COLUMN_NAME IS NULL';
    EXECUTE IMMEDIATE :statement;
    SELECT $1 INTO :schema_mismatches FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
    IF (schema_mismatches > 0) THEN
      RAISE incompatible_files;
    END IF;
    CREATE TEMPORARY TABLE IDENTIFIER(:snapshot_table) LIKE IDENTIFIER(:raw_table);
    ALTER TABLE IDENTIFIER(:snapshot_table) ADD COLUMN _FILE_CONTENT_KEY VARCHAR;
    statement := 'COPY INTO ' || snapshot_table || ' (' || definition.COLUMNS_SQL || ', _FILE_CONTENT_KEY) '
      || 'FROM (SELECT ' || definition.PROJECTION_SQL || ', METADATA$FILE_CONTENT_KEY '
      || 'FROM @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/) '
      || 'FILES = (''' || definition.FILE_NAME || ''') '
      || 'FILE_FORMAT = (FORMAT_NAME = ''BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_PARQUET'') '
      || 'ON_ERROR = ABORT_STATEMENT FORCE = TRUE';
    EXECUTE IMMEDIATE :statement;
    SELECT COUNT(*), COUNT(DISTINCT _FILE_CONTENT_KEY), COUNT_IF(_FILE_CONTENT_KEY IS NULL)
      INTO :existing_rows, :file_count, :invalid_rows FROM IDENTIFIER(:snapshot_table);
    IF (existing_rows = 0 OR existing_rows IS DISTINCT FROM definition.EXPECTED_ROWS
        OR file_count != 1 OR invalid_rows > 0) THEN
      RAISE incompatible_files;
    END IF;
    IF (definition.TABLE_NAME IN ('VIEWING_LOG_NW01', 'VIEWING_LOG_NW02', 'VIEWING_LOG_NW03',
                                 'VIEWING_LOG_NW04', 'VIEWING_LOG_NW05')) THEN
      viewing_rows := viewing_rows + existing_rows;
    END IF;
    statement := 'INSERT INTO ' || manifest_table
      || ' SELECT ''F1_SIGNAL_V2'', ''' || definition.TABLE_NAME || ''', ''' || definition.FILE_NAME
      || ''', MIN(_FILE_CONTENT_KEY), COUNT(*), HASH_AGG(' || definition.COLUMNS_SQL || '), ? FROM ' || snapshot_table;
    EXECUTE IMMEDIATE :statement USING (load_time);
    pass_count := pass_count + 1;
  END FOR;
  -- 8ファイルと視聴ログ合計1,050,648行がそろっていることを確認します。
  SELECT COUNT(*) INTO :manifest_count FROM IDENTIFIER(:manifest_table);
  IF (pass_count != 8 OR manifest_count != 8) THEN
    RAISE incompatible_files;
  END IF;
  IF (viewing_rows != 1050648) THEN
    RAISE incompatible_files;
  END IF;
  -- 端末20,000台のうち、正解ラベルを使える2,000台だけに0/1が入り、残りはNULLであることを確認します。
  snapshot_table := snapshots_prefix || 'DEVICE_LABELS';
  SELECT COUNT(DISTINCT DEVICE_ID), COUNT_IF(LABEL_AVAILABLE), COUNT_IF(
      DEVICE_ID IS NULL OR NOT REGEXP_LIKE(DEVICE_ID, 'C[0-9]{6}')
      OR TRY_TO_NUMBER(SUBSTR(DEVICE_ID, 2)) NOT BETWEEN 1 AND 20000
      OR LABEL_AVAILABLE IS NULL
      OR (LABEL_AVAILABLE AND (TARGET_F1 IS NULL OR TARGET_F1 NOT IN (0, 1)))
      OR (NOT LABEL_AVAILABLE AND TARGET_F1 IS NOT NULL))
    INTO :unique_devices, :panel_rows, :invalid_rows FROM IDENTIFIER(:snapshot_table);
  IF (unique_devices != 20000 OR panel_rows != 2000 OR invalid_rows > 0) THEN
    RAISE incompatible_files;
  END IF;
  -- 局別ログの端末ID・局コード・視聴開始日時が教材の範囲内であることを確認します。
  FOR station IN 1 TO 5 DO
    snapshot_table := snapshots_prefix || 'VIEWING_LOG_NW0' || station;
    SELECT COUNT(*) INTO :invalid_rows FROM IDENTIFIER(:snapshot_table)
    WHERE DEVICE_ID IS NULL OR NOT REGEXP_LIKE(DEVICE_ID, 'C[0-9]{6}')
       OR TRY_TO_NUMBER(SUBSTR(DEVICE_ID, 2)) NOT BETWEEN 1 AND 20000
       OR NETWORK_ID IS DISTINCT FROM ('NW0' || :station)
       OR VIEW_FROM IS NULL OR VIEW_FROM < '2026-05-01'::TIMESTAMP_NTZ
       OR VIEW_FROM >= '2026-08-01'::TIMESTAMP_NTZ;
    IF (invalid_rows > 0) THEN
      RAISE incompatible_files;
    END IF;
  END FOR;

  -- ここからは複数表への変更をまとめて確定するトランザクションです。
  -- 管理用の1行を更新して取込同士の競合を防ぎます。セットアップや移行を並行して実行しないでください。
  BEGIN
    BEGIN TRANSACTION;
    UPDATE BCAST_PLATFORM_HANDSON.RAW.DATASET_LOAD_LOCK SET LAST_LOADER = :load_id WHERE LOCK_ID = 1;
    IF (SQLROWCOUNT != 1) THEN
      RAISE lock_failed;
    END IF;
    -- 再ロード前に、記録済みの版・ファイル名・件数・内容の照合値が今回のデータと一致するか調べます。
    SELECT COUNT(*) INTO :metadata_count FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES;
    SELECT COUNT(*) INTO :invalid_rows
    FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES AS old
    FULL OUTER JOIN IDENTIFIER(:manifest_table) AS incoming ON old.TABLE_NAME = incoming.TABLE_NAME
    WHERE old.DATASET_VERSION IS DISTINCT FROM incoming.DATASET_VERSION
       OR old.FILE_NAME IS DISTINCT FROM incoming.FILE_NAME
       OR old.ROW_COUNT IS DISTINCT FROM incoming.ROW_COUNT
       OR old.ROW_FINGERPRINT IS DISTINCT FROM incoming.ROW_FINGERPRINT;
    IF (metadata_count != 0 AND (metadata_count != 8 OR invalid_rows > 0)) THEN
      RAISE incompatible_data;
    END IF;
    -- 管理記録のない既存データや、ロード後に変更されたRAWデータは上書きせず停止します。
    -- 再ロード時のエラーは、別の教材データや参加者の変更を守るためのものです。削除で回避しないでください。
    pass_count := 0;
    definitions := (SELECT * FROM IDENTIFIER(:definitions_table) ORDER BY TABLE_NAME);
    FOR definition IN definitions DO
      raw_table := 'BCAST_PLATFORM_HANDSON.RAW.' || definition.TABLE_NAME;
      SELECT COUNT(*) INTO :existing_rows FROM IDENTIFIER(:raw_table);
      IF (metadata_count = 0 AND existing_rows > 0) THEN
        RAISE incompatible_data;
      END IF;
      IF (metadata_count = 8) THEN
        statement := 'SELECT COUNT(*) FROM (SELECT COUNT(*) AS ROW_COUNT, HASH_AGG('
          || definition.COLUMNS_SQL || ') AS ROW_FINGERPRINT FROM ' || raw_table
          || ') AS actual JOIN ' || manifest_table || ' AS expected ON expected.TABLE_NAME = '''
          || definition.TABLE_NAME || ''' WHERE actual.ROW_COUNT IS DISTINCT FROM expected.ROW_COUNT '
          || 'OR actual.ROW_FINGERPRINT IS DISTINCT FROM expected.ROW_FINGERPRINT';
        EXECUTE IMMEDIATE :statement;
        SELECT $1 INTO :invalid_rows FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        IF (invalid_rows > 0) THEN
          RAISE incompatible_data;
        END IF;
      END IF;
      pass_count := pass_count + 1;
    END FOR;
    IF (pass_count != 8) THEN
      RAISE incompatible_data;
    END IF;
    -- 予測結果が既にある場合は、今回と同じ版のデータから作られた記録があることを確認します。
    SELECT COUNT(*) INTO :prediction_tables FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = 'ML' AND TABLE_NAME = 'PREDICTIONS';
    IF (prediction_tables > 0) THEN
      statement := 'SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.ML.PREDICTIONS';
      EXECUTE IMMEDIATE :statement;
      SELECT $1 INTO :existing_rows FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
      IF (existing_rows > 0) THEN
        SELECT COUNT(*) INTO :prediction_columns FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.COLUMNS
          WHERE TABLE_SCHEMA = 'ML' AND TABLE_NAME = 'PREDICTIONS' AND COLUMN_NAME = 'DATASET_VERSION';
        IF (prediction_columns != 1) THEN
          RAISE stale_predictions;
        END IF;
        statement := 'SELECT COUNT(*) FROM BCAST_PLATFORM_HANDSON.ML.PREDICTIONS WHERE DATASET_VERSION IS DISTINCT FROM ''F1_SIGNAL_V2'' OR ? = 0';
        EXECUTE IMMEDIATE :statement USING (metadata_count);
        SELECT $1 INTO :invalid_rows FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
        IF (invalid_rows > 0) THEN
          RAISE stale_predictions;
        END IF;
      END IF;
    END IF;
    -- すべての事前確認を通過した場合だけ、8表の内容を確認済みの一時テーブルから入れ直します。
    -- DELETEを含むため、この部分だけを切り出して実行しないでください。
    pass_count := 0;
    definitions := (SELECT * FROM IDENTIFIER(:definitions_table) ORDER BY TABLE_NAME);
    FOR definition IN definitions DO
      raw_table := 'BCAST_PLATFORM_HANDSON.RAW.' || definition.TABLE_NAME;
      snapshot_table := snapshots_prefix || definition.TABLE_NAME;
      DELETE FROM IDENTIFIER(:raw_table);
      statement := 'INSERT INTO ' || raw_table || ' (' || definition.COLUMNS_SQL || ') SELECT '
        || definition.COLUMNS_SQL || ' FROM ' || snapshot_table;
      EXECUTE IMMEDIATE :statement;
      pass_count := pass_count + 1;
    END FOR;
    IF (pass_count != 8) THEN
      RAISE incompatible_data;
    END IF;
    -- 書込後にも件数と内容の照合値を確認し、途中でデータが欠けていないか調べます。
    pass_count := 0;
    definitions := (SELECT * FROM IDENTIFIER(:definitions_table) ORDER BY TABLE_NAME);
    FOR definition IN definitions DO
      raw_table := 'BCAST_PLATFORM_HANDSON.RAW.' || definition.TABLE_NAME;
      statement := 'SELECT COUNT(*) FROM (SELECT COUNT(*) AS ROW_COUNT, HASH_AGG('
        || definition.COLUMNS_SQL || ') AS ROW_FINGERPRINT FROM ' || raw_table
        || ') AS actual JOIN ' || manifest_table || ' AS expected ON expected.TABLE_NAME = '''
        || definition.TABLE_NAME || ''' WHERE actual.ROW_COUNT IS DISTINCT FROM expected.ROW_COUNT '
        || 'OR actual.ROW_FINGERPRINT IS DISTINCT FROM expected.ROW_FINGERPRINT';
      EXECUTE IMMEDIATE :statement;
      SELECT $1 INTO :invalid_rows FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
      IF (invalid_rows > 0) THEN
        RAISE incompatible_data;
      END IF;
      pass_count := pass_count + 1;
    END FOR;
    IF (pass_count != 8) THEN
      RAISE incompatible_data;
    END IF;
    -- 8表の確認後、取込記録も更新してまとめて確定します。
    DELETE FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES;
    INSERT INTO BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES SELECT * FROM IDENTIFIER(:manifest_table);
    IF (SQLROWCOUNT != 8) THEN
      RAISE incompatible_data;
    END IF;
    COMMIT;
  EXCEPTION
    WHEN OTHER THEN
      -- このトランザクション内で失敗した場合は表への変更を取り消し、元のエラーを表示します。
      -- ステージへコピー済みのファイルは取り消し対象ではありません。
      ROLLBACK;
      RAISE;
  END;
  -- 確定後、今回の確認に使った一時テーブルだけを片付けます。
  pass_count := 0;
  definitions := (SELECT * FROM IDENTIFIER(:definitions_table) ORDER BY TABLE_NAME);
  FOR definition IN definitions DO
    snapshot_table := snapshots_prefix || definition.TABLE_NAME;
    DROP TABLE IDENTIFIER(:snapshot_table);
    pass_count := pass_count + 1;
  END FOR;
  IF (pass_count != 8) THEN
    RAISE incompatible_files;
  END IF;
  DROP TABLE IDENTIFIER(:manifest_table);
  DROP TABLE IDENTIFIER(:definitions_table);
END;
$$;

-- 8行の取込記録を確認します。途中でエラーが出た場合、記録が表示されても今回の成功とは判断しないでください。
SELECT DATASET_VERSION, TABLE_NAME, FILE_NAME, FILE_CONTENT_KEY, ROW_COUNT, ROW_FINGERPRINT, LOADED_AT
FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES ORDER BY TABLE_NAME;