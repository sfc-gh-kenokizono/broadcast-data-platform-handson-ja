"""Generate small, fictional viewing intervals and partially observed labels."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_SEED = 20260701
START = datetime(2026, 7, 1)
NETWORKS = tuple(f"NW{number:02d}" for number in range(1, 6))
GENRES = ("NEWS", "DRAMA", "VARIETY", "ANIME", "SPORTS")
FULLWIDTH = {
    "NEWS": "ＮＥＷＳ",
    "DRAMA": "ＤＲＡＭＡ",
    "VARIETY": "ＶＡＲＩＥＴＹ",
    "ANIME": "ＡＮＩＭＥ",
    "SPORTS": "ＳＰＯＲＴＳ",
}
VIEWING_SCHEMA = pa.schema([
    ("EVENT_ID", pa.string()),
    ("NETWORK_ID", pa.string()),
    ("DEVICE_ID", pa.string()),
    ("VIEW_FROM", pa.timestamp("us")),
    ("VIEW_TO", pa.timestamp("us")),
    ("GENRE", pa.string()),
])
LABEL_SCHEMA = pa.schema([
    ("DEVICE_ID", pa.string()),
    ("LABEL_AVAILABLE", pa.bool_()),
    ("TARGET_SPORTS_FAN", pa.int64()),
])


def build_tables(seed: int = DEFAULT_SEED) -> dict[str, pa.Table]:
    """All timestamps are fictional Japan wall-clock times without a timezone."""
    label_rng = random.Random(seed)
    known_targets = [0] * 50 + [1] * 50
    unknown_targets = [0] * 50 + [1] * 50
    label_rng.shuffle(known_targets)
    label_rng.shuffle(unknown_targets)
    latent_targets = known_targets + unknown_targets
    rows_by_network: dict[str, list[dict]] = {network: [] for network in NETWORKS}
    labels = []

    for device_number, latent_target in enumerate(latent_targets, start=1):
        device_id = f"D{device_number:04d}"
        rng = random.Random(f"{seed}:{device_id}")
        label_available = device_number <= 100
        labels.append({
            "DEVICE_ID": device_id,
            "LABEL_AVAILABLE": label_available,
            "TARGET_SPORTS_FAN": latent_target if label_available else None,
        })
        habit_class = 1 - latent_target if rng.random() < 0.15 else latent_target
        sports_probability = 0.16 + 0.22 * habit_class + rng.uniform(-0.12, 0.12)
        other_weights = [rng.uniform(0.7, 1.3) for _ in GENRES[:-1]]

        for day_number in range(30):
            for slot_number, start_hour in enumerate((6, 13, 20)):
                network = NETWORKS[(device_number + day_number + slot_number) % 5]
                view_from = START + timedelta(
                    days=day_number, hours=start_hour,
                    minutes=rng.randrange(90), seconds=rng.randrange(60),
                )
                view_to = view_from + timedelta(
                    minutes=rng.randint(8, 65), seconds=rng.randrange(60),
                )
                genre = (
                    "SPORTS" if rng.random() < sports_probability
                    else rng.choices(GENRES[:-1], weights=other_weights, k=1)[0]
                )
                variant = rng.randrange(4)
                rendered_genre = (genre, genre.lower(), FULLWIDTH[genre], f" {genre.lower()} ")[variant]
                rows_by_network[network].append({
                    "EVENT_ID": f"{network}-{device_id}-{day_number + 1:02d}-{slot_number + 1}",
                    "NETWORK_ID": network,
                    "DEVICE_ID": device_id,
                    "VIEW_FROM": view_from,
                    "VIEW_TO": view_to,
                    "GENRE": rendered_genre,
                })

    tables = {
        f"viewing_log_{network.lower()}.parquet": pa.Table.from_pylist(rows, schema=VIEWING_SCHEMA)
        for network, rows in rows_by_network.items()
    }
    tables["device_labels.parquet"] = pa.Table.from_pylist(labels, schema=LABEL_SCHEMA)
    return tables


def generate(output_dir: Path = DATA_DIR, seed: int = DEFAULT_SEED) -> dict[str, pa.Table]:
    tables = build_tables(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, table in tables.items():
        destination = output_dir / filename
        pq.write_table(
            table, destination, compression="zstd", compression_level=3,
            version="2.6", coerce_timestamps="us",
            use_deprecated_int96_timestamps=False,
            row_group_size=4096, use_dictionary=True, write_statistics=True,
        )
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    tables = generate(args.output_dir, args.seed)
    for filename, table in tables.items():
        print(f"{filename}: {table.num_rows:,} rows, {(args.output_dir / filename).stat().st_size:,} bytes")
    print(f"seed={args.seed}; pyarrow={pa.__version__}; ZSTD; timestamp[us] without timezone")
    print("Synthetic labels only: 100 known (50 per class), 100 unknown (NULL).")


if __name__ == "__main__":
    main()