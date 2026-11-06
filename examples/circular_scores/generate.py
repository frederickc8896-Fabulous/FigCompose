"""Independent score tracks with native circular_bar; no drawing callback."""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")

from data_visuals import FigureConfig, plot

HERE = Path(__file__).resolve().parent
export_figure = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]


def build_figure(data_path=None, profile_path=None):
    return plot(
        HERE / "data.csv" if data_path is None else Path(data_path),
        config=FigureConfig.load(HERE / "style.yaml" if profile_path is None else profile_path),
        x="participant", group="subject", title="Four subjects, ten individual profiles",
        plots=[{"kind": "circular_bar", "metric": "score", "summary": "mean", "title": None}],
    )


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
