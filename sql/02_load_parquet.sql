-- 01_setup.sqlの後に実行。固定データコミットを取得できなければ停止する。
-- 同じリリースの再実行だけ許可。旧データは自動移行・削除しない。
-- 移行が必要な場合は管理者が承認済みのバックアップ付き移行手順を実施する。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
USE DATABASE BCAST_PLATFORM_HANDSON;
USE SCHEMA BCAST_PLATFORM_HANDSON.RAW;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

EXECUTE IMMEDIATE $$
DECLARE
  incompatible_schema EXCEPTION (-20001, 'RAW schema mismatch. Stop; use approved backup-first migration, not a database reset.');
  incompatible_data EXCEPTION (-20002, 'Existing RAW data is unversioned, changed, or a different release. No overwrite authorized. Ask the maintainer to perform an approved backup-first migration, then rerun setup/load.');
  incompatible_files EXCEPTION (-20003, 'F1_SIGNAL_V2 requires all eight commit-pinned files, exact row counts, consistent per-load file keys and valid F1 labels. Do not fall back to main or old stage files.');
  stale_predictions EXCEPTION (-20005, 'Existing ML.PREDICTIONS lacks F1_SIGNAL_V2 provenance. Stop; approved backup-first migration must invalidate predictions before loading.');
  lock_failed EXCEPTION (-20006, 'Expected exactly one dataset load lock. Stop and repair setup; do not run concurrent setup/migration.');
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

  ALTER GIT REPOSITORY BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO FETCH;
  COPY FILES INTO @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_RAW_STAGE/F1_SIGNAL_V2/
    FROM @BCAST_PLATFORM_HANDSON.INTEGRATIONS.BCAST_PLATFORM_REPO/commits/8a6f0cc234b30c3b54a4a63d68890bb7cb9f8887/data/
    FILES = ('viewing_log_nw01.parquet', 'viewing_log_nw02.parquet',
             'viewing_log_nw03.parquet', 'viewing_log_nw04.parquet',
             'viewing_log_nw05.parquet', 'program_master.parquet',
             'program_schedule.parquet', 'device_labels.parquet')
    DETAILED_OUTPUT = TRUE;
  SELECT COUNT(*) INTO :file_count FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
  IF (file_count != 8) THEN
    RAISE incompatible_files;
  END IF;
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
  SELECT COUNT(*) INTO :manifest_count FROM IDENTIFIER(:manifest_table);
  IF (pass_count != 8 OR manifest_count != 8) THEN
    RAISE incompatible_files;
  END IF;
  IF (viewing_rows != 1050648) THEN
    RAISE incompatible_files;
  END IF;
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

  BEGIN
    BEGIN TRANSACTION;
    UPDATE BCAST_PLATFORM_HANDSON.RAW.DATASET_LOAD_LOCK SET LAST_LOADER = :load_id WHERE LOCK_ID = 1;
    IF (SQLROWCOUNT != 1) THEN
      RAISE lock_failed;
    END IF;
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
    DELETE FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES;
    INSERT INTO BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES SELECT * FROM IDENTIFIER(:manifest_table);
    IF (SQLROWCOUNT != 8) THEN
      RAISE incompatible_data;
    END IF;
    COMMIT;
  EXCEPTION
    WHEN OTHER THEN
      ROLLBACK;
      RAISE;
  END;
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

SELECT DATASET_VERSION, TABLE_NAME, FILE_NAME, FILE_CONTENT_KEY, ROW_COUNT, ROW_FINGERPRINT, LOADED_AT
FROM BCAST_PLATFORM_HANDSON.RAW.DATASET_RELEASE_FILES ORDER BY TABLE_NAME;