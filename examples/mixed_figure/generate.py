"""Four native panels from one small CSV and one reusable paper profile."""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent
export_figure = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]


def build_figure(data_path=None, profile_path=None, *, subset_path=None):
    complete = pd.read_csv(HERE / "data.csv" if data_path is None else data_path)
    subset = pd.read_csv(HERE / "subset.csv" if subset_path is None else subset_path)
    frames = [complete.assign(csv_source="complete"), subset.assign(csv_source="subset")]
    paper = Figure(data=pd.concat(frames, ignore_index=True), rows=2, cols=2,
                   config=FigureConfig.load(HERE / "style.yaml" if profile_path is None else profile_path),
                   title="One profile, four panels | Reusable series identities")
    paper[0, 0].bar(
        x="task", y="quality", group="method", title="(a) Mean quality | All methods",
        where={"csv_source": "complete", "epoch": 12},
        chart_opts={"ylim": [0, 1], "yticks": [0, .25, .50, .75, 1]},
    )
    paper[0, 1].line(
        x="epoch", y="quality", group="method", title="(b) Learning curves | Same identities",
        where={"csv_source": "complete"},
        chart_opts={"ylim": [.60, .94], "yticks": [.60, .70, .80, .90], "xticks": [1, 4, 8, 12]},
    )
    paper[1, 0].scatter(
        x="latency", y="quality", group="method", title="(c) Separate CSV | Method A absent",
        where={"csv_source": "subset", "epoch": 12},
        chart_opts={"ylim": [.83, .94], "yticks": [.84, .88, .92],
                    "xlim": [13, 29], "xticks": [15, 20, 25]},
    )
    paper[1, 1].box(
        x="task", y="quality", group="method", title="(d) Final-epoch variation | Raw seeds",
        where={"csv_source": "complete", "epoch": 12},
        chart_opts={"ylim": [.78, .94], "yticks": [.80, .84, .88, .92]},
    )
    return paper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--subset", type=Path, default=HERE / "subset.csv")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export_figure(build_figure(args.data, args.profile, subset_path=args.subset), args.out,
                  config=FigureConfig.load(args.profile))


if __name__ == "__main__":
    main()
