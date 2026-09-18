-- 任意の移行補助。通常のセットアップから自動実行しない。
-- 破棄可能と確認済みの旧小規模DEVICE_LABELSだけが対象。
-- 実行する場合のみFALSEをTRUEに変更する。DB・局別RAW・マスタ・モデルは削除しない。
-- 旧局別データが残る場合、02_load_parquet.sqlは停止する。別途移行方針を確認する。
USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;
USE SECONDARY ROLES NONE;
USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;

EXECUTE IMMEDIATE $$
DECLARE
  confirm_disposable_small_labels BOOLEAN DEFAULT FALSE;
  refused EXCEPTION (-20004, 'Reset refused: explicitly confirm disposable old small DEVICE_LABELS and its exact legacy schema.');
  column_count INTEGER;
  legacy_columns INTEGER;
  label_rows INTEGER;
  release_tables INTEGER;
BEGIN
  IF (NOT confirm_disposable_small_labels) THEN
    RAISE refused;
  END IF;
  SELECT COUNT(*) INTO :release_tables
  FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'RAW' AND TABLE_NAME = 'DATASET_RELEASE_FILES';
  IF (release_tables > 0) THEN
    RAISE refused;
  END IF;
  SELECT COUNT(*), COUNT_IF(
    (COLUMN_NAME = 'DEVICE_ID' AND DATA_TYPE = 'TEXT') OR
    (COLUMN_NAME = 'LABEL_AVAILABLE' AND DATA_TYPE = 'BOOLEAN') OR
    (COLUMN_NAME = 'TARGET_SPORTS_FAN' AND DATA_TYPE = 'NUMBER' AND NUMERIC_SCALE = 0)
  ) INTO :column_count, :legacy_columns
  FROM BCAST_PLATFORM_HANDSON.INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'RAW' AND TABLE_NAME = 'DEVICE_LABELS';
  IF (column_count != 3 OR legacy_columns != 3) THEN
    RAISE refused;
  END IF;
  SELECT COUNT(*) INTO :label_rows FROM BCAST_PLATFORM_HANDSON.RAW.DEVICE_LABELS;
  IF (label_rows > 200) THEN
    RAISE refused;
  END IF;
  DROP TABLE BCAST_PLATFORM_HANDSON.RAW.DEVICE_LABELS;
END;
$$;