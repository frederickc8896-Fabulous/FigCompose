"""Three paired views: profiles, points and stacked amounts in 2D and 3D."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent
GROUPS = ("Group 1", "Group 2", "Group 3", "Group 4")
PARTS = ("Part A", "Part B", "Part C")


def read_data(path):
    data = pd.read_csv(path, keep_default_na=False, float_precision="round_trip")
    required = {"view", "series", "x", "y", "z", "signal", "component",
                "group_id", "sample", "amount", "stack"}
    if not required.issubset(data):
        raise ValueError("Expected the documented long-form profile/points/stacks CSV.")
    if set(data.view) != {"profile", "points", "stacks"}:
        raise ValueError("All three view types must be supplied.")
    for view, columns in (("profile", ("x", "signal")), ("points", ("x", "y", "z")),
                          ("stacks", ("group_id", "sample", "amount"))):
        rows = data[data.view == view]
        values = rows[list(columns)].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{view} has nonfinite values.")
        data.loc[rows.index, list(columns)] = values
    if not set(data[data.view.isin(("profile", "points"))].series).issubset(GROUPS):
        raise ValueError("This comparison template uses the four documented groups.")
    stacks = data[data.view == "stacks"]
    if stacks.duplicated(["component", "group_id", "sample"]).any() or len(stacks) != 27:
        raise ValueError("Supply three parts for every cell of the 3 x 3 stack grid.")
    if set(stacks.component) != set(PARTS) or set(stacks.group_id) != {1, 2, 3} or set(stacks["sample"]) != {1, 2, 3}:
        raise ValueError("Stack categories do not match this paired-view template.")
    labels = stacks[["group_id", "sample", "stack"]].drop_duplicates()
    if len(labels) != 9 or labels["stack"].nunique() != 9 or (labels["stack"].astype(str).str.len() == 0).any():
        raise ValueError("Stack labels must map one-to-one to the nine group/sample positions.")
    if not stacks.amount.between(0, 150).all() or stacks.groupby("stack").amount.sum().max() > 150:
        raise ValueError("Stack amounts must be nonnegative and total at most 150.")
    profiles = data[data.view == "profile"]
    if set(profiles.series) != set(GROUPS) or profiles.duplicated(["series", "x"]).any():
        raise ValueError("Supply four profiles with one observation per series/position pair.")
    if not profiles.x.between(0, 8).all() or not profiles.signal.between(0, 32).all():
        raise ValueError("Profile domain is position 0-8 and signal 0-32.")
    if not data[data.view == "points"][["x", "y", "z"]].apply(pd.to_numeric).apply(lambda col: col.between(0, 10)).all().all():
        raise ValueError("The three point coordinates must lie in [0, 10].")
    return data


def add_profiles(paper, row, data):
    paper[row, 0].line(x="x", y="signal", group="series", markers=False, area=True,
                     where={"view": "profile"}, title="01  Overlay the signals",
                     chart_opts={"xlabel": "Position", "ylabel": "Signal",
                                 "xlim": [0, 8], "ylim": [0, 32], "xticks": [0, 2, 4, 6, 8],
                                 "yticks": [0, 8, 16, 24, 32],
                                 "series_styles": {group: {"linewidth": 1.5} for group in GROUPS}})
    paper[row, 2].waterfall3d(x="x", y="signal", group="series", baseline=0,
                             where={"view": "profile"}, linewidth=1.7, fill_alpha=1,
                             elev=27, azim=-58, box_aspect=(1.6, 1.05, .95), zoom=1.09,
                             title="Separate them in depth",
                             chart_opts={"xlim": [0, 8], "ylim": [-.25, 3.25], "zlim": [0, 32],
                                         "xticks": [0, 2, 4, 6, 8], "zticks": [0, 10, 20, 30],
                                         "yticks": [0, 1, 2, 3], "yticklabels": ["G1", "G2", "G3", "G4"],
                                         "xlabel": "Position", "ylabel": "Series", "zlabel": "Signal",
                                         "legend": False})


def add_projections(paper, row, data):
    paper[row, 0].scatter(x="x", y="y", group="series", where={"view": "points"},
                        opacity=.95, title="02  Drop one coordinate",
                        chart_opts={"xlabel": "X", "ylabel": "Y", "xlim": [0, 10], "ylim": [0, 10],
                                    "xticks": [0, 5, 10], "yticks": [0, 5, 10],
                                    "series_styles": {group: {"size": 28, "edgecolor": "white", "linewidth": .55}
                                                      for group in GROUPS}})
    paper[row, 2].scatter3d(x="x", y="y", z="z", group="series", where={"view": "points"},
                           point_size=34, opacity=1, projections={"x": 0, "y": 10, "z": 0},
                           projection_lines=["z"], elev=25, azim=-58,
                           box_aspect=(1.1, 1.1, 1), zoom=1.06,
                           title="Recover Z; trace each projection",
                           chart_opts={"xlabel": "X", "ylabel": "Y", "zlabel": "Z",
                                       "xlim": [0, 10], "ylim": [0, 10], "zlim": [0, 10],
                                       "xticks": [0, 5, 10], "yticks": [0, 5, 10], "zticks": [0, 5, 10],
                                       "legend": False})


def add_stacks(paper, row, data):
    local = {"scope": "local", "position": "top", "ncols": 3,
             "fontsize": 8.5, "order": list(PARTS), "gap": 3}
    paper[row, 0].bar(x="stack", y="amount", group="component", stacked=True,
                    where={"view": "stacks"}, title="03  Compare all nine stacks",
                    chart_opts={"ylim": [0, 150], "yticks": [0, 50, 100, 150],
                                "xlabel": "Group / sample", "ylabel": "Amount", "legend": local})
    paper[row, 2].bar3d(x="group_id", y="sample", value="amount", group="component",
                       stacked=True, label_totals=True, where={"view": "stacks"},
                       elev=31, azim=-56, box_aspect=(1.15, 1.15, 1), zoom=1.06,
                       title="Arrange them in space; watch occlusion",
                       chart_opts={"xlim": [-.65, 2.65], "ylim": [-.65, 2.65], "zlim": [0, 150],
                                   "xticks": [0, 1, 2], "xticklabels": ["G1", "G2", "G3"],
                                   "yticks": [0, 1, 2], "yticklabels": ["S1", "S2", "S3"],
                                   "zticks": [0, 50, 100, 150],
                                   "xlabel": "Group", "ylabel": "Sample", "zlabel": "Amount", "legend": False})


VIEWS = ("overview", "profiles", "projections", "stacks")
TITLES = {"overview": "SAME DATA. NEW DIMENSION.",
          "profiles": "SIGNALS, GIVEN ROOM TO BREATHE.",
          "projections": "ONE POINT. THREE COORDINATES.",
          "stacks": "NINE STACKS. THE SAME TOTALS."}


def build_figure(data_path=None, profile_path=None, *, view="overview"):
    if view not in VIEWS:
        raise ValueError(f"Unknown comparison view: {view!r}")
    data = read_data(data_path or HERE / "data.csv")
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    overview = view == "overview"
    selected = VIEWS[1:] if overview else (view,)
    paper = Figure(data=data, layout=[[2, 3] for _ in selected], config=config,
                   canvas={"width": 245, "height": 345 if overview else 160},
                   title=TITLES[view])
    callbacks = {"profiles": add_profiles, "projections": add_projections, "stacks": add_stacks}
    for row, name in enumerate(selected):
        callbacks[name](paper, row, data)
    return paper


def generate(data_path=None, profile_path=None, *, out=None, views=VIEWS, write_report=False):
    destination = HERE if out is None else Path(out)
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    results = []
    for view in views:
        target = destination if view == "overview" else destination / view
        result = export(build_figure(data_path, profile_path, view=view), target,
                        config=config, write_report=write_report)
        result.update(view=view, destination=target.relative_to(destination).as_posix())
        results.append(result)
    (destination / "comparison_manifest.json").write_text(
        json.dumps({"synthetic": True, "views": results}, indent=2) + "\n", encoding="utf-8")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--view", choices=("all", *VIEWS), default="all")
    args = parser.parse_args()
    generate(args.data, args.profile, out=args.out,
             views=VIEWS if args.view == "all" else (args.view,))


if __name__ == "__main__":
    main()
