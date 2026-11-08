"""Native circular scores and compute-derived summaries, with no callback."""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
import pandas as pd

from data_visuals import FigureConfig, plot

HERE = Path(__file__).resolve().parent
export_figure = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]


def build_figure(data_path=None, profile_path=None):
    data = pd.read_csv(HERE / "data.csv" if data_path is None else Path(data_path))
    config = FigureConfig.load(HERE / "style.yaml" if profile_path is None else profile_path)
    return plot(data, config=config, x="participant", group="subject",
                title=f"{data['participant'].nunique()} people.\n"
                      f"{data['subject'].nunique()} different score profiles.",
                plots=[{"kind": "circular_bar", "metric": "score", "summary": "mean",
                        "summary_position": "top", "chart_opts": {"object_label": "People",
                        "series_label": "Subjects", "value_label": "Score per subject"}}])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export_figure(build_figure(args.data, args.profile), args.out,
                  config=FigureConfig.load(args.profile))


if __name__ == "__main__":
    main()
