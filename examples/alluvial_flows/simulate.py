"""Create a reproducible five-stage cohort of weighted synthetic routes.

Run: python simulate.py --out data.csv
The 12 route motifs per initial category include stable preferences, gradual
switches, returns and multi-step exploration. Each CSV row is one complete
route followed by its integer number of simulated participants.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random


STAGES = ("entry", "explore", "trial", "decision", "outcome")
CATEGORIES = ("A", "B", "C", "D", "E")
SEED = 20261109
PARTICIPANTS = 1200
MOTIFS = (
    ("stable", (0, 0, 0, 0, 0), 48),
    ("late switch", (0, 0, 0, 0, 1), 24),
    ("decision switch", (0, 0, 0, 1, 1), 26),
    ("trial switch", (0, 0, 1, 1, 1), 22),
    ("early switch", (0, 1, 1, 1, 1), 20),
    ("early return", (0, 1, 1, 0, 0), 18),
    ("late return", (0, 0, 1, 1, 0), 16),
    ("repeated exploration", (0, 1, 0, 1, 0), 14),
    ("two-step trial", (0, 0, 1, 2, 2), 17),
    ("two-step decision", (0, 1, 1, 2, 2), 16),
    ("progressive exploration", (0, 1, 2, 3, 3), 10),
    ("cross-category exploration", (0, 2, 2, 4, 4), 9),
)


def generate_paths(total=PARTICIPANTS, seed=SEED):
    """Return 60 distinct complete paths whose positive counts sum to total."""
    route_count = len(CATEGORIES) * len(MOTIFS)
    if isinstance(total, bool) or not isinstance(total, int) or total < route_count:
        raise ValueError(f"total must be an integer of at least {route_count}.")
    rng = random.Random(seed)
    records, weights = [], []
    origin_factors = (1.10, .94, 1.02, .91, 1.03)
    for origin, factor in enumerate(origin_factors):
        for _name, offsets, base_weight in MOTIFS:
            route = tuple(CATEGORIES[(origin + offset) % len(CATEGORIES)]
                          for offset in offsets)
            records.append(route)
            weights.append(base_weight * factor * rng.uniform(.78, 1.22))

    # Reserve one participant per route, then apportion the remainder by
    # largest remainder. The row index resolves equal fractional parts.
    remaining = total - route_count
    weight_sum = sum(weights)
    raw = [weight / weight_sum * remaining for weight in weights]
    counts = [int(value) + 1 for value in raw]
    missing = total - sum(counts)
    order = sorted(range(route_count), key=lambda i: (-(raw[i] - int(raw[i])), i))
    for index in order[:missing]:
        counts[index] += 1
    rows = [dict(zip(STAGES, route), count=count)
            for route, count in zip(records, counts)]
    assert len({tuple(row[stage] for stage in STAGES) for row in rows}) == route_count
    assert all(row["count"] > 0 for row in rows)
    assert sum(row["count"] for row in rows) == total
    return rows


def write_csv(destination, rows):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(*STAGES, "count"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return destination


def describe(rows):
    marginals = {}
    for stage in STAGES:
        values = Counter()
        for row in rows:
            values[row[stage]] += row["count"]
        marginals[stage] = {category: values[category] for category in CATEGORIES}
    return {
        "synthetic": True,
        "participants": sum(row["count"] for row in rows),
        "complete_paths": len(rows),
        "stage_marginals": marginals,
        "minimum_path_count": min(row["count"] for row in rows),
        "maximum_path_count": max(row["count"] for row in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().with_name("data.csv"))
    parser.add_argument("--participants", type=int, default=PARTICIPANTS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    rows = generate_paths(args.participants, args.seed)
    destination = write_csv(args.out, rows)
    report = describe(rows)
    report.update(seed=args.seed, sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
