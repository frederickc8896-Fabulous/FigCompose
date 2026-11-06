"""Three paired views: profiles, points and stacked amounts in 2D and 3D."""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
from matplotlib.collections import PolyCollection
import numpy as np
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure, PanelResult

HERE = Path(__file__).resolve().parent
GROUPS = ("Group 1", "Group 2", "Group 3", "Group 4")
PARTS = ("Part A", "Part B", "Part C")


def style_3d(ax, context, labels):
    ax.set_proj_type("ortho")
    for axis, label in zip((ax.xaxis, ax.yaxis, ax.zaxis), labels):
        axis.set_label_text(label, **context.text_kwargs("axis_label"))
        axis.labelpad = 1.5
        axis.pane.set_facecolor((.97, .98, .99, .12))
        axis.pane.set_edgecolor((.80, .84, .88, .3))
        axis._axinfo["grid"].update(color=(.75, .79, .85, .25), linewidth=.45)
        axis.line.set_color("#A6B3C8")
        axis.line.set_linewidth(.5)
    ax.tick_params(labelsize=context.font_sizes["tick"], pad=0)
    for text in (*ax.get_xticklabels(), *ax.get_yticklabels(), *ax.get_zticklabels()):
        text.set_fontfamily(context.font_family)


def draw_profiles(ax, context):
    frame = context.payload
    polygons, colors = [], []
    for index, group in enumerate(GROUPS):
        data = frame[frame.series == group].sort_values("x")
        x, y = data.x.to_numpy(), data.signal.to_numpy()
        polygons.append([(x[0], 0), *zip(x, y), (x[-1], 0)])
        colors.append(context.color(group))
        ax.plot(x, np.full(len(x), index), y, color=colors[-1], linewidth=.8)
    collection = PolyCollection(polygons, facecolors=colors, alpha=.65,
                                edgecolors=colors, linewidths=.5)
    ax.add_collection3d(collection, zs=range(4), zdir="y")
    ax.set_yticks(range(4), labels=("G1", "G2", "G3", "G4"))
    ax.set_xticks((0, 2, 4, 6, 8))
    ax.set_zticks((0, 10, 20, 30))
    ax.set_box_aspect((1.3, 1, .9))
    style_3d(ax, context, ("Position", "Series", "Signal"))
    return PanelResult()


def draw_projections(ax, context):
    frame = context.payload
    for group in GROUPS:
        data = frame[frame.series == group]
        color = context.color(group)
        x, y, z = (data[column].to_numpy() for column in ("x", "y", "z"))
        ax.scatter(x, y, z, color=color, s=22, depthshade=False,
                   edgecolors="white", linewidths=.45)
        ax.scatter(x, y, np.zeros(len(x)), color=color, s=9, alpha=.18, depthshade=False)
        ax.scatter(np.zeros(len(x)), y, z, color=color, s=9, alpha=.18, depthshade=False)
        ax.scatter(x, np.full(len(x), 10.), z, color=color, s=9, alpha=.18, depthshade=False)
    ax.set_xticks((0, 5, 10))
    ax.set_yticks((0, 5, 10))
    ax.set_zticks((0, 5, 10))
    ax.set_box_aspect((1, 1, 1))
    style_3d(ax, context, ("X", "Y", "Z"))
    return PanelResult()


def draw_stacks(ax, context):
    frame = context.payload
    for index, part in enumerate(PARTS):
        records = frame[frame.component == part]
        bottom = np.array([
            frame[(frame.group_id == group) & (frame["sample"] == sample)
                  & frame.component.isin(PARTS[:index])].amount.sum()
            for group, sample in zip(records.group_id, records["sample"])
        ])
        ax.bar3d(records.group_id.to_numpy() - 1.34,
                 records["sample"].to_numpy() - 1.34, bottom, .68, .68,
                 records.amount.to_numpy(), color=context.color(part), shade=False,
                 edgecolor="white", linewidth=.4, zsort="average")
    ax.set_xticks(range(3), labels=("G1", "G2", "G3"))
    ax.set_yticks(range(3), labels=("S1", "S2", "S3"))
    ax.set_zticks((0, 50, 100, 150))
    ax.set_box_aspect((1, 1, 1))
    style_3d(ax, context, ("Group", "Sample", "Amount"))
    return PanelResult()


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


def build_figure(data_path=None, profile_path=None):
    data = read_data(data_path or HERE / "data.csv")
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    paper = Figure(data=data, rows=3, cols=2, config=config,
                   canvas={"width": 245, "height": 325},
                   title="Same data, different views | What does depth add?")
    paper[0, 0].line(x="x", y="signal", group="series", markers=False,
                     where={"view": "profile"}, title="(a) Profiles | Direct comparison",
                     chart_opts={"xlabel": "Position", "ylabel": "Signal",
                                 "xlim": [0, 8], "ylim": [0, 32]})
    paper[0, 1].custom(draw_profiles, payload=data[data.view == "profile"],
                       projection="3d", axes="on", color_group="series", categories=GROUPS,
                       limits=((0, 8), (-.25, 3.25), (0, 32)),
                       axes_options={"elev": 24, "azim": -58}, legend=False,
                       title="(b) Waterfall | Separate overlapping signals", min_size=(180, 170))
    paper[1, 0].scatter(x="x", y="y", group="series", where={"view": "points"},
                        title="(c) XY projection | The Z coordinate is omitted",
                        chart_opts={"xlabel": "X", "ylabel": "Y", "xlim": [0, 10], "ylim": [0, 10]})
    paper[1, 1].custom(draw_projections, payload=data[data.view == "points"],
                       projection="3d", axes="on", color_group="series", categories=GROUPS,
                       limits=((0, 10), (0, 10), (0, 10)),
                       axes_options={"elev": 24, "azim": -58}, legend=False,
                       title="(d) 3D points | Shadows repeat the same samples", min_size=(180, 170))
    local = {"scope": "local", "position": "upper left", "ncols": 3,
             "fontsize": 8, "order": list(PARTS)}
    paper[2, 0].bar(x="stack", y="amount", group="component", stacked=True,
                    where={"view": "stacks"}, title="(e) Stacks | All nine totals are visible",
                    chart_opts={"ylim": [0, 150], "yticks": [0, 50, 100, 150],
                                "xlabel": "Group / sample", "ylabel": "Amount", "legend": local})
    paper[2, 1].custom(draw_stacks, payload=data[data.view == "stacks"],
                       projection="3d", axes="on", color_group="component", categories=PARTS,
                       limits=((-.65, 2.65), (-.65, 2.65), (0, 150)),
                       axes_options={"elev": 24, "azim": -58}, legend=False,
                       title="(f) 3D stacks | Rear cells can be obscured", min_size=(180, 170))
    return paper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    export(build_figure(args.data, args.profile), args.out, config=FigureConfig.load(args.profile))


if __name__ == "__main__":
    main()
