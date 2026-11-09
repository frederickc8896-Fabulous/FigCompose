"""A single multi-stage alluvial flow built from weighted complete paths.

Run: python examples/alluvial_flows/generate.py
CSV: two to eight stage columns followed by count; one complete path per row.
Uses the native alluvial kind available in FigCompose 0.3.0.
FigCompose manages the canvas, physical typography, shared legend and export.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent
STAGES = ("entry", "explore", "trial", "decision", "outcome")
STAGE_TITLES = {"entry": "INITIAL CHOICE", "explore": "EXPLORATION",
                "trial": "FIRST TRIAL", "decision": "REASSESSMENT", "outcome": "FINAL CHOICE"}


def load_paths(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        columns = next(csv.reader(stream), [])
    if (not 3 <= len(columns) <= 9 or columns[-1] != "count"
            or len(set(columns)) != len(columns) or any(not name.strip() for name in columns)):
        raise ValueError("Supply 2–8 unique, named stage columns followed by count.")
    data = pd.read_csv(path, keep_default_na=False)
    stages = columns[:-1]
    if data.empty:
        raise ValueError("Supply at least one complete path.")
    if any(not isinstance(value, str) or not value.strip()
           for value in data[stages].to_numpy().flat):
        raise ValueError("Each path needs a nonempty category label at every stage.")
    weights = pd.to_numeric(data["count"], errors="raise").to_numpy(dtype=float)
    if (not np.isfinite(weights).all() or (weights <= 0).any()
            or not np.equal(weights, np.floor(weights)).all()):
        raise ValueError("Participant counts must be finite positive integers.")
    return data


def build_figure(data_path=None, profile_path=None) -> Figure:
    data = load_paths(data_path or HERE / "data.csv")
    cfg = FigureConfig.load(profile_path or HERE / "style.yaml")
    stages = tuple(column for column in data if column != "count")
    try:
        total = math.fsum(float(value) for value in data["count"])
    except OverflowError as exc:
        raise ValueError("Aggregated participant counts must remain finite.") from exc
    path_count = len(data.drop_duplicates(list(stages)))
    width_mm = max(210, 64 * len(stages))
    figure = Figure(data=data, config=cfg, rows=1, cols=1,
                    canvas={"width": width_mm, "height": 220},
                    title=f"{total:,.0f} people. {len(stages)} stages. {path_count} complete paths.")
    figure[0, 0].alluvial(stages=list(stages), value="count",
                          stage_titles=[STAGE_TITLES.get(stage, stage.replace("_", " ").upper())
                                        for stage in stages],
                          note="Ribbon width = people   /   Color = initial category   /   Synthetic data",
                          chart_opts={"value_label": "people"})
    return figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    export(build_figure(args.data, args.profile), args.out)


if __name__ == "__main__":
    main()
