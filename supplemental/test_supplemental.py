import json
from pathlib import Path
import re
import sqlite3
import unittest


DIRECTORY = Path(__file__).resolve().parent
BASIC_SQL = (DIRECTORY / "01_basic.sql").read_text(encoding="utf-8")
SEARCH_SQL = (DIRECTORY / "02_create_genre_search.sql").read_text(encoding="utf-8")


class SupplementalTests(unittest.TestCase):
    def test_basic_read_only(self):
        statements = [statement.strip() for statement in BASIC_SQL.split(";") if statement.strip()]
        self.assertEqual(len(statements), 8)
        self.assertTrue(all(re.match(r"^(USE|SELECT|WITH)\b", statement) for statement in statements))
        self.assertIsNone(re.search(r"\b(CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|MERGE|CALL|COPY|GRANT)\b", BASIC_SQL))

    def test_context_and_database_scope(self):
        for sql_text in (BASIC_SQL, SEARCH_SQL):
            self.assertIn("USE ROLE BCAST_PLATFORM_ENGINEER_ROLE;", sql_text)
            self.assertIn("USE SECONDARY ROLES NONE;", sql_text)
            self.assertIn("USE WAREHOUSE BCAST_PLATFORM_COMMON_WH;", sql_text)
            identifiers = re.findall(r"\bBCAST_[A-Z0-9_]+", sql_text)
            self.assertEqual(set(identifiers), {
                "BCAST_PLATFORM_HANDSON", "BCAST_PLATFORM_ENGINEER_ROLE", "BCAST_PLATFORM_COMMON_WH"
            })

    def test_aggregate_contract(self):
        self.assertIn("SUM(SESSION_COUNT)", BASIC_SQL)
        self.assertIn("COUNT(DISTINCT DEVICE_ID)", BASIC_SQL)
        self.assertIn("FROM BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY", BASIC_SQL)
        self.assertIn("VIEW_DATE < '2026-07-31'::DATE", BASIC_SQL)

    def test_fold_seven_into_three(self):
        fold_sql = BASIC_SQL[BASIC_SQL.index("WITH fixture"):]
        sqlite_sql = fold_sql.replace("SELECT * FROM VALUES", "VALUES").replace("::TIMESTAMP_NTZ", "")
        with sqlite3.connect(":memory:") as connection:
            rows = connection.execute(sqlite_sql).fetchall()
        self.assertEqual(rows, [
            ("DEMO001", "NW01", "NEWS", "2026-07-01 08:00:00", "2026-07-01 08:50:00", 4, 7, 3),
            ("DEMO001", "NW01", "NEWS", "2026-07-01 09:00:00", "2026-07-01 09:20:00", 2, 7, 3),
            ("DEMO001", "NW01", "NEWS", "2026-07-01 10:00:00", "2026-07-01 10:05:00", 1, 7, 3),
        ])

    def test_search_is_new_and_self_contained(self):
        self.assertEqual(SEARCH_SQL.count("CREATE CORTEX SEARCH SERVICE "), 1)
        self.assertNotRegex(SEARCH_SQL, r"\b(OR REPLACE|IF NOT EXISTS|ALTER|DROP|GRANT|TASK|AGENT)\b")
        self.assertIn("REFRESH_MODE = FULL", SEARCH_SQL)
        self.assertIn("INITIALIZE = ON_CREATE", SEARCH_SQL)
        self.assertEqual(re.findall(r"\bFROM\s+(\w+)", SEARCH_SQL), ["VALUES"])
        self.assertEqual(re.findall(r"\('([A-Z]+)',", SEARCH_SQL), ["NEWS", "DRAMA", "VARIETY", "ANIME", "SPORTS"])

    def test_search_request(self):
        request = json.loads(re.search(r"'(\{\"query\".*?\})'", SEARCH_SQL).group(1))
        self.assertEqual(request["columns"], ["GENRE", "GUIDE_TEXT"])
        self.assertEqual(request["limit"], 3)
        self.assertEqual(SEARCH_SQL.count("BCAST_PLATFORM_HANDSON.MART.SVC_GENRE_GUIDE"), 2)

    def test_main_does_not_reference_scratch(self):
        root = DIRECTORY.parent
        main_files = [root / "sql/04_semantic.sql", root / "sql/05_agent.sql", root / "docs/agent_texts.md"]
        for main_file in main_files:
            self.assertNotIn("SVC_GENRE_GUIDE", main_file.read_text(encoding="utf-8"))

    def test_local_document_links(self):
        for document in DIRECTORY.glob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if not link.startswith("https://"):
                    self.assertTrue((DIRECTORY / link).is_file(), link)


if __name__ == "__main__":
    unittest.main(verbosity=2)