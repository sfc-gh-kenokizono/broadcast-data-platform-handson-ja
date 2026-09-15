"""Read-only audit of Parquet files against CONTRACT.md; no Snowflake access."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

import pyarrow as pa
import pyarrow.parquet as pq


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NETWORKS = tuple(f"NW{number:02d}" for number in range(1, 6))
DEVICES = {f"D{number:04d}" for number in range(1, 201)}
START = datetime(2026, 7, 1)
END = datetime(2026, 7, 31)
FULLWIDTH = {
    "ＮＥＷＳ": "NEWS", "ＤＲＡＭＡ": "DRAMA", "ＶＡＲＩＥＴＹ": "VARIETY",
    "ＡＮＩＭＥ": "ANIME", "ＳＰＯＲＴＳ": "SPORTS",
}
GENRES = {"NEWS", "DRAMA", "VARIETY", "ANIME", "SPORTS"}
EXPECTED_VIEWING_SCHEMA = pa.schema([
    ("EVENT_ID", pa.string()), ("NETWORK_ID", pa.string()),
    ("DEVICE_ID", pa.string()), ("VIEW_FROM", pa.timestamp("us")),
    ("VIEW_TO", pa.timestamp("us")), ("GENRE", pa.string()),
])
EXPECTED_LABEL_SCHEMA = pa.schema([
    ("DEVICE_ID", pa.string()), ("LABEL_AVAILABLE", pa.bool_()),
    ("TARGET_SPORTS_FAN", pa.int64()),
])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_checked(path: Path, schema: pa.Schema) -> list[dict]:
    require(path.is_file(), f"Missing file: {path.name}")
    parquet = pq.ParquetFile(path)
    require(parquet.schema_arrow.equals(schema), f"Schema mismatch: {path.name}")
    require(parquet.metadata.num_rows > 0, f"Empty file: {path.name}")
    for group_number in range(parquet.metadata.num_row_groups):
        group = parquet.metadata.row_group(group_number)
        for column_number in range(group.num_columns):
            column = group.column(column_number)
            require(column.compression == "ZSTD", f"Not ZSTD: {path.name}/{column.path_in_schema}")
    for column_number, field in enumerate(schema):
        if pa.types.is_timestamp(field.type):
            physical = parquet.schema.column(column_number)
            logical = json.loads(physical.logical_type.to_json())
            require(
                physical.physical_type == "INT64"
                and logical.get("Type") == "Timestamp"
                and logical.get("isAdjustedToUTC") is False
                and logical.get("timeUnit") == "microseconds",
                f"Timestamp logical type mismatch: {path.name}/{field.name}",
            )
    return parquet.read().to_pylist()


def audit(data_dir: Path = DATA_DIR) -> dict:
    intervals = defaultdict(list)
    seconds_by_device = defaultdict(Counter)
    row_counts = {}
    expected_days = {(START + timedelta(days=offset)).date() for offset in range(30)}
    for network in NETWORKS:
        rows = read_checked(data_dir / f"viewing_log_{network.lower()}.parquet", EXPECTED_VIEWING_SCHEMA)
        row_counts[network] = len(rows)
        require(len(rows) == 3600, f"Expected 3600 rows: {network}")
        require(len({row["EVENT_ID"] for row in rows}) == len(rows), f"Duplicate EVENT_ID: {network}")
        require({row["DEVICE_ID"] for row in rows} == DEVICES, f"Device coverage mismatch: {network}")
        seen_days, seen_genres, variants = set(), set(), set()
        for row in rows:
            require(all(value is not None for value in row.values()), f"NULL viewing field: {network}")
            require(bool(row["EVENT_ID"].strip()), f"Empty EVENT_ID: {network}")
            require(row["NETWORK_ID"] == network, f"Wrong station: {network}")
            view_from, view_to = row["VIEW_FROM"], row["VIEW_TO"]
            require(view_from.tzinfo is None and view_to.tzinfo is None, "Timezone must be absent")
            require(START <= view_from < view_to < END, "Invalid timestamp order or period")
            require(view_from.date() == view_to.date(), "Session crosses midnight")
            genre_text = row["GENRE"].strip().upper()
            genre = FULLWIDTH.get(genre_text, genre_text)
            require(genre in GENRES, f"Unknown genre: {row['GENRE']}")
            seen_days.add(view_from.date())
            seen_genres.add(genre)
            if row["GENRE"] != row["GENRE"].strip():
                variants.add("spaces")
            if row["GENRE"].strip().islower():
                variants.add("lowercase")
            if genre_text in FULLWIDTH:
                variants.add("fullwidth")
            device_id = row["DEVICE_ID"]
            intervals[device_id].append((view_from, view_to, network))
            seconds_by_device[device_id][genre] += (view_to - view_from).total_seconds()
        require(seen_days == expected_days, f"Missing day: {network}")
        require(seen_genres == GENRES, f"Missing genre: {network}")
        require(variants == {"spaces", "lowercase", "fullwidth"}, f"Missing cleansing examples: {network}")

    for device_id, device_intervals in intervals.items():
        device_intervals.sort()
        for previous, current in zip(device_intervals, device_intervals[1:]):
            require(previous[1] <= current[0], f"Overlapping intervals across stations: {device_id}")

    labels = read_checked(data_dir / "device_labels.parquet", EXPECTED_LABEL_SCHEMA)
    require(len(labels) == 200, "Expected 200 label rows")
    require({row["DEVICE_ID"] for row in labels} == DEVICES, "Label device coverage/uniqueness mismatch")
    known_ids = {f"D{number:04d}" for number in range(1, 101)}
    classes = Counter()
    shares = defaultdict(list)
    for row in labels:
        device_id = row["DEVICE_ID"]
        known = device_id in known_ids
        require(row["LABEL_AVAILABLE"] is known, "Known device set must be D0001..D0100")
        target = row["TARGET_SPORTS_FAN"]
        if known:
            require(type(target) is int and target in (0, 1), "Known target must be binary")
            classes[target] += 1
            durations = seconds_by_device[device_id]
            shares[target].append(durations["SPORTS"] / sum(durations.values()))
        else:
            require(target is None, "Unknown target must be NULL, not zero or a hidden label")
    require(classes == Counter({0: 50, 1: 50}), "Known labels must contain 50 per class")
    require(min(shares[1]) < max(shares[0]) and min(shares[0]) < max(shares[1]), "Sports shares must overlap between classes")
    require(0.03 < mean(shares[1]) - mean(shares[0]) < 0.4, "Expected a modest, noisy sports relationship")
    return {
        "rows_by_station": row_counts,
        "viewing_rows": sum(row_counts.values()),
        "devices": len(intervals), "known_labels": sum(classes.values()),
        "unknown_labels": 100,
        "mean_sports_minutes_share_by_label": {str(target): round(mean(values), 4) for target, values in sorted(shares.items())},
        "checks": "ZSTD, exact schemas, logical timestamps, 30 days, 5 stations, genres, uniqueness, no overlaps, NULL unknown targets, noisy labels",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    try:
        summary = audit(args.data_dir)
    except (ValueError, OSError, pa.ArrowException) as error:
        parser.exit(1, f"DATA AUDIT: FAIL: {error}\n")
    print("DATA AUDIT: PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()