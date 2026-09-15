"""Local regression checks, including deliberate corruption in temporary files."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from audit_data import audit
from generate_data import build_tables, generate


class DataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.tables = generate(self.directory)

    def replace_rows(self, filename: str, rows: list[dict]) -> None:
        table = pa.Table.from_pylist(rows, schema=self.tables[filename].schema)
        pq.write_table(table, self.directory / filename, compression="zstd")

    def test_audit_and_byte_reproducibility(self) -> None:
        self.assertEqual(audit(self.directory)["viewing_rows"], 18000)
        hashes = {name: hashlib.sha256((self.directory / name).read_bytes()).hexdigest() for name in self.tables}
        generate(self.directory)
        self.assertEqual(hashes, {name: hashlib.sha256((self.directory / name).read_bytes()).hexdigest() for name in self.tables})
        self.assertFalse(self.tables["device_labels.parquet"].equals(build_tables(7)["device_labels.parquet"]))

    def test_unknown_label_rejected(self) -> None:
        filename = "device_labels.parquet"
        rows = self.tables[filename].to_pylist()
        rows[-1]["TARGET_SPORTS_FAN"] = 0
        self.replace_rows(filename, rows)
        with self.assertRaisesRegex(ValueError, "Unknown target must be NULL"):
            audit(self.directory)

    def test_cross_station_overlap_rejected(self) -> None:
        filename = "viewing_log_nw02.parquet"
        rows = self.tables[filename].to_pylist()
        source = next(row for row in self.tables["viewing_log_nw01.parquet"].to_pylist() if row["DEVICE_ID"] == rows[0]["DEVICE_ID"])
        rows[0]["VIEW_FROM"], rows[0]["VIEW_TO"] = source["VIEW_FROM"], source["VIEW_TO"]
        self.replace_rows(filename, rows)
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            audit(self.directory)

    def test_bad_timestamp_rejected(self) -> None:
        filename = "viewing_log_nw01.parquet"
        rows = self.tables[filename].to_pylist()
        rows[0]["VIEW_TO"] = rows[0]["VIEW_FROM"]
        self.replace_rows(filename, rows)
        with self.assertRaisesRegex(ValueError, "Invalid timestamp"):
            audit(self.directory)

    def test_non_zstd_rejected(self) -> None:
        filename = "device_labels.parquet"
        pq.write_table(self.tables[filename], self.directory / filename, compression="snappy")
        with self.assertRaisesRegex(ValueError, "Not ZSTD"):
            audit(self.directory)

    def test_schema_drift_rejected(self) -> None:
        filename = "device_labels.parquet"
        table = self.tables[filename].append_column("EXTRA", pa.array([0] * 200))
        pq.write_table(table, self.directory / filename, compression="zstd")
        with self.assertRaisesRegex(ValueError, "Schema mismatch"):
            audit(self.directory)

    def test_missing_station_rejected(self) -> None:
        (self.directory / "viewing_log_nw05.parquet").unlink()
        with self.assertRaisesRegex(ValueError, "Missing file"):
            audit(self.directory)

    def test_duplicate_event_rejected(self) -> None:
        filename = "viewing_log_nw01.parquet"
        rows = self.tables[filename].to_pylist()
        rows[1]["EVENT_ID"] = rows[0]["EVENT_ID"]
        self.replace_rows(filename, rows)
        with self.assertRaisesRegex(ValueError, "Duplicate EVENT_ID"):
            audit(self.directory)


if __name__ == "__main__":
    unittest.main()