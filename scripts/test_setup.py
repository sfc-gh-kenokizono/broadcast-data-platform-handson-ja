"""Offline contract checks, not a Snowflake SQL parser or compilation test."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DATABASE = "BCAST_PLATFORM_HANDSON"
ENGINEER = "BCAST_PLATFORM_ENGINEER_ROLE"
NETWORKS = tuple(f"NW{number:02d}" for number in range(1, 6))


def sql_text(filename: str) -> str:
    text = (ROOT / "sql" / filename).read_text(encoding="utf-8")
    return re.sub(r"--[^\n]*", "", text).upper()


class SetupTests(unittest.TestCase):
    def test_raw_table_columns(self) -> None:
        setup = sql_text("01_setup.sql")
        for table, expected in (
            ("VIEWING_LOG_NW01", "EVENT_ID VARCHAR, NETWORK_ID VARCHAR, DEVICE_ID VARCHAR, VIEW_FROM TIMESTAMP_NTZ, VIEW_TO TIMESTAMP_NTZ, GENRE VARCHAR"),
            ("DEVICE_LABELS", "DEVICE_ID VARCHAR, LABEL_AVAILABLE BOOLEAN, TARGET_SPORTS_FAN INTEGER"),
        ):
            match = re.search(rf"CREATE TABLE IF NOT EXISTS {DATABASE}\.RAW\.{table}\s*\((.*?)\);", setup, re.DOTALL)
            self.assertIsNotNone(match)
            self.assertEqual(" ".join(match.group(1).split()), expected)
        for network in NETWORKS[1:]:
            self.assertRegex(setup, rf"CREATE TABLE IF NOT EXISTS {DATABASE}\.RAW\.VIEWING_LOG_{network}\s+LIKE {DATABASE}\.RAW\.VIEWING_LOG_NW01;")

    def test_schema_permissions_and_warehouses(self) -> None:
        setup = sql_text("01_setup.sql")
        for schema in ("RAW", *NETWORKS, "COMMON", "ML", "MART", "INTEGRATIONS"):
            self.assertIn(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.{schema};", setup)
            self.assertRegex(setup, rf"GRANT USAGE[^;]*ON SCHEMA {DATABASE}\.{schema} TO ROLE {ENGINEER};")
        for suffix in (*NETWORKS, "COMMON"):
            warehouse = f"BCAST_PLATFORM_{suffix}_WH"
            self.assertIn(f"CREATE WAREHOUSE IF NOT EXISTS {warehouse}", setup)
            self.assertIn(f"GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE {ENGINEER};", setup)
        for schema in ("RAW", *NETWORKS, "ML"):
            self.assertNotRegex(setup, rf"GRANT[^;]*ON SCHEMA {DATABASE}\.{schema} TO ROLE BCAST_PLATFORM_ANALYST_ROLE")

    def test_copy_contract(self) -> None:
        load = sql_text("02_load_parquet.sql")
        self.assertEqual(load.count("COPY INTO BCAST_PLATFORM_HANDSON.RAW."), 6)
        self.assertEqual(load.count("ON_ERROR = ABORT_STATEMENT FORCE = FALSE"), 6)
        self.assertNotIn("MATCH_BY_COLUMN_NAME", load)
        self.assertNotIn("VALIDATION_MODE", load)
        for network in NETWORKS:
            filename = f"viewing_log_{network.lower()}.parquet"
            self.assertTrue((ROOT / "data" / filename).is_file())
            self.assertIn(f"FILES = ('{filename.upper()}')", load)
            self.assertRegex(load, rf"COPY INTO {DATABASE}\.RAW\.VIEWING_LOG_{network}\s+\(EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE\)")
        self.assertEqual(load.count("$1:VIEW_FROM::TIMESTAMP_NTZ"), 6)
        self.assertEqual(load.count("$1:VIEW_TO::TIMESTAMP_NTZ"), 6)
        self.assertIn("$1:TARGET_SPORTS_FAN::INTEGER", load)

    def test_cleanup_only_new_objects(self) -> None:
        cleanup = sql_text("cleanup.sql")
        names = re.findall(r"DROP (?:DATABASE|WAREHOUSE|INTEGRATION|ROLE) IF EXISTS (\w+);", cleanup)
        expected = {
            DATABASE, ENGINEER, "BCAST_PLATFORM_ANALYST_ROLE", "BCAST_PLATFORM_GIT_API",
            *(f"BCAST_PLATFORM_{suffix}_WH" for suffix in (*NETWORKS, "COMMON")),
        }
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), len(expected))
        for filename in ("01_setup.sql", "02_load_parquet.sql", "cleanup.sql"):
            text = sql_text(filename)
            for forbidden in ("BCAST_VIEWING_HANDSON", "BCAST_HANDSON_WH", "ALTER USER", "CREATE OR REPLACE"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()