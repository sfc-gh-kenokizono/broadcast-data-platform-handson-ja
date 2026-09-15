"""Execute repository aggregation SQL offline; not Snowflake compilation tests."""

from datetime import datetime, timedelta
from pathlib import Path
import re
import sqlite3
import unittest


ROOT = Path(__file__).resolve().parents[1]
NETWORKS = tuple(f"NW{number:02d}" for number in range(1, 6))


def sqlite_sql(rendered: str) -> str:
    if any(marker in rendered for marker in ("{{", "{%", "{#")):
        raise ValueError("Unsupported template syntax in SQL fixture")
    translated = re.sub(
        r"(count\([^()]*\)|sum\([^()]*\)|\(datediff\([^()]*\)\s*/\s*[^()]+\))"
        r"::(integer|float)\b",
        lambda match: f"CAST({match.group(1)} AS {match.group(2)})",
        rendered,
        flags=re.IGNORECASE,
    )
    if "::" in translated:
        raise ValueError("Unsupported Snowflake cast in SQL fixture")
    return translated


def render_macro(name: str, argument: str, relation: str) -> str:
    source = (ROOT / "dbt" / "macros" / f"{name}.sql").read_text(encoding="utf-8")
    match = re.fullmatch(
        rf"\s*{{%\s*macro\s+{name}\({argument}\)\s*%}}(.*?){{%\s*endmacro\s*%}}\s*",
        source,
        re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Unsupported macro wrapper: {name}")
    rendered = re.sub(rf"{{{{\s*{argument}\s*}}}}", relation, match.group(1))
    return sqlite_sql(rendered)


def render_common() -> str:
    source = (ROOT / "dbt" / "models" / "common" / "viewing_daily.sql").read_text(
        encoding="utf-8"
    )
    rendered = re.sub(r"{{\s*config\(alias='VIEWING_DAILY'\)\s*}}", "", source)
    rendered = re.sub(
        r"{{\s*ref\('(mart_device_daily_nw0[1-5])'\)\s*}}", r"\1", rendered
    )
    return sqlite_sql(rendered)


def datediff(unit: str, start: str, end: str) -> int:
    if unit != "millisecond":
        raise ValueError(f"Unsupported datediff unit: {unit}")
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    return duration // timedelta(milliseconds=1)


class AggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.create_function("datediff", 3, datediff)
        self.connection.create_function(
            "to_date", 1, lambda value: datetime.fromisoformat(value).date().isoformat()
        )
        self.connection.execute(
            "CREATE TABLE raw_viewing (EVENT_ID TEXT, NETWORK_ID TEXT, DEVICE_ID TEXT, "
            "VIEW_FROM TEXT, VIEW_TO TEXT, GENRE TEXT)"
        )
        self.connection.execute(
            "CREATE VIEW clean_viewing AS "
            + render_macro("clean_viewing", "raw_relation", "raw_viewing")
        )
        self.daily_sql = render_macro("device_daily", "clean_relation", "clean_viewing")

    def add_session(
        self,
        event: str,
        start: str,
        end: str,
        genre: str = "SPORTS",
        network: str = "NW01",
        device: str = "D001",
    ) -> None:
        self.connection.execute(
            "INSERT INTO raw_viewing VALUES (?, ?, ?, ?, ?, ?)",
            (event, network, device, start, end, genre),
        )

    def daily_rows(self) -> list[tuple]:
        return self.connection.execute(self.daily_sql + " ORDER BY 1, 2, 3, 4").fetchall()

    def build_common(self) -> list[tuple]:
        for network in NETWORKS:
            suffix = network.lower()
            self.connection.execute(
                f"CREATE VIEW clean_viewing_{suffix} AS "
                f"SELECT * FROM clean_viewing WHERE NETWORK_ID = '{network}'"
            )
            self.connection.execute(
                f"CREATE TABLE mart_device_daily_{suffix} AS "
                + render_macro("device_daily", "clean_relation", f"clean_viewing_{suffix}")
            )
        return self.connection.execute(render_common() + " ORDER BY 1, 2, 3, 4").fetchall()

    def test_repeated_composite_key_counts_sessions_and_sums_minutes(self) -> None:
        for event, start, end in (
            ("E1", "10:00:00", "10:01:00"),
            ("E2", "11:00:00", "11:02:00"),
            ("E3", "12:00:00", "12:03:00"),
        ):
            self.add_session(event, f"2026-09-01 {start}", f"2026-09-01 {end}")
        self.assertEqual(
            self.daily_rows(), [("NW01", "D001", "2026-09-01", "SPORTS", 3, 6.0)]
        )

    def test_fractional_minutes_survive_cleaning_and_aggregation(self) -> None:
        self.add_session("E1", "2026-09-01 10:00:00.000", "2026-09-01 10:00:00.500")
        self.add_session("E2", "2026-09-01 11:00:00.250", "2026-09-01 11:01:30.750")
        rows = self.daily_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:5], ("NW01", "D001", "2026-09-01", "SPORTS", 2))
        self.assertAlmostEqual(rows[0][5], 91 / 60, places=12)
        self.assertIsInstance(rows[0][5], float)

    def test_every_composite_key_dimension_partitions_sessions(self) -> None:
        for event, network, device, day, genre in (
            ("E1", "NW01", "D001", "2026-09-01", "SPORTS"),
            ("E2", "NW02", "D001", "2026-09-01", "SPORTS"),
            ("E3", "NW01", "D002", "2026-09-01", "SPORTS"),
            ("E4", "NW01", "D001", "2026-09-02", "SPORTS"),
            ("E5", "NW01", "D001", "2026-09-01", " news "),
        ):
            self.add_session(event, f"{day} 10:00:00", f"{day} 10:01:00", genre, network, device)
        self.assertEqual(self.daily_rows(), [
            ("NW01", "D001", "2026-09-01", "NEWS", 1, 1.0),
            ("NW01", "D001", "2026-09-01", "SPORTS", 1, 1.0),
            ("NW01", "D001", "2026-09-02", "SPORTS", 1, 1.0),
            ("NW01", "D002", "2026-09-01", "SPORTS", 1, 1.0),
            ("NW02", "D001", "2026-09-01", "SPORTS", 1, 1.0),
        ])

    def test_midnight_sessions_allocate_all_minutes_to_start_date(self) -> None:
        self.add_session("E1", "2026-09-01 23:59:30", "2026-09-02 00:01:00")
        self.add_session("E2", "2026-09-01 23:59:00", "2026-09-02 00:00:00")
        self.add_session("E3", "2026-09-02 00:00:00", "2026-09-02 00:00:30")
        self.assertEqual(self.daily_rows(), [
            ("NW01", "D001", "2026-09-01", "SPORTS", 2, 2.5),
            ("NW01", "D001", "2026-09-02", "SPORTS", 1, 0.5),
        ])

    def test_common_model_preserves_all_five_station_aggregates(self) -> None:
        for network in NETWORKS:
            self.add_session(network + "A", "2026-09-01 10:00:00", "2026-09-01 10:00:30", network=network)
            self.add_session(network + "B", "2026-09-01 11:00:00", "2026-09-01 11:01:00", network=network)
        self.assertEqual(self.build_common(), [
            (network, "D001", "2026-09-01", "SPORTS", 2, 1.5) for network in NETWORKS
        ])

    def test_common_model_uses_union_all_even_for_identical_rows(self) -> None:
        self.add_session("E1", "2026-09-01 10:00:00", "2026-09-01 10:01:00")
        self.build_common()
        self.connection.execute(
            "INSERT INTO mart_device_daily_nw01 SELECT * FROM mart_device_daily_nw01"
        )
        self.assertEqual(self.connection.execute(render_common()).fetchall(), [
            ("NW01", "D001", "2026-09-01", "SPORTS", 1, 1.0),
            ("NW01", "D001", "2026-09-01", "SPORTS", 1, 1.0),
        ])


if __name__ == "__main__":
    unittest.main()