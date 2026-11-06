"""Plot supplied asymmetric confidence bounds without recomputing intervals."""
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
    config = FigureConfig.load(HERE / "style.yaml" if profile_path is None else profile_path)
    return plot(
        HERE / "data.csv" if data_path is None else Path(data_path),
        config=config,
        x="condition", group="dataset", title="Beyond a point estimate",
        plots=[{"kind": "scatter", "metric": "mean_difference_pp",
                "title": "Mean difference and supplied intervals",
                "chart_opts": {
                    "opacity": 1,
                    "series_styles": {
                        entry["id"]: {"marker": "o", "size": 27, "color": entry["color"],
                                      "edgecolor": "white", "linewidth": .55, "zorder": 4}
                        for entry in config.series["dataset"]},
                    "errorbar": {"lower": "ci95_lower_pp", "upper": "ci95_upper_pp",
                                 "capsize": 2.3, "linewidth": 1.1, "alpha": .9},
                    "x_offsets": {"Dataset I": -6, "Dataset II": 0, "Dataset III": 6},
                    "xticks": [1, 2, 3, 4, 5],
                    "xticklabels": ["Condition 1", "Condition 2", "Condition 3", "Condition 4", "Condition 5"],
                    "xlabel": "Evaluation condition", "ylabel": "Accuracy change: B - A (pp)",
                    "guides": [{"axis": "y", "value": 0, "linestyle": "--",
                                "color": "#7B8793", "linewidth": .85}],
                }}],
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
