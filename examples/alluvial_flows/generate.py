"""Three-stage alluvial diagram with a common count scale and conserved paths.

Run: python examples/alluvial_flows/generate.py
Replace data.csv with entry,decision,outcome,count; each row is a complete path.
This is a reusable custom template, not an additional built-in chart kind.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
from matplotlib.path import Path as ArtistPath
from matplotlib.patches import Patch, PathPatch, Rectangle
import numpy as np
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure, PanelResult

HERE = Path(__file__).resolve().parent
STAGES = ("entry", "decision", "outcome")


def load_paths(path):
    data = pd.read_csv(path, keep_default_na=False)
    if list(data.columns) != [*STAGES, "count"]:
        raise ValueError("CSV columns must be entry,decision,outcome,count in that order.")
    if data.empty:
        raise ValueError("Supply at least one complete path.")
    if any(not isinstance(value, str) or not value.strip()
           for value in data[list(STAGES)].to_numpy().flat):
        raise ValueError("Each path needs three nonempty category labels.")
    weights = pd.to_numeric(data["count"], errors="raise").to_numpy(dtype=float)
    if (not np.isfinite(weights).all() or (weights <= 0).any()
            or not np.equal(weights, np.floor(weights)).all()):
        raise ValueError("Participant counts must be finite positive integers.")
    data = data.copy()
    data["count"] = weights
    # Repeated identical paths represent additive counts, not repeated estimates.
    result = data.groupby(list(STAGES), sort=False, as_index=False)["count"].sum()
    if not np.isfinite(result["count"]).all():
        raise ValueError("Aggregated participant counts must remain finite.")
    return result


def flow_geometry(data):
    """One count-to-height scale; allocate the same path weight at every stage."""
    categories = {stage: tuple(dict.fromkeys(data[stage])) for stage in STAGES}
    if max(map(len, categories.values())) > 8:
        raise ValueError("This compact template supports at most eight categories per stage.")
    total = float(data["count"].sum())
    gap = .045
    scale = (.72 - gap * (max(map(len, categories.values())) - 1)) / total
    totals = {stage: data.groupby(stage, sort=False)["count"].sum().to_dict() for stage in STAGES}
    nodes = {}
    slots = {}
    ordered = data.sort_values(list(STAGES), kind="stable")
    for stage in STAGES:
        height = total * scale + gap * (len(categories[stage]) - 1)
        cursor = .88 - (.72 - height) / 2
        for label in categories[stage]:
            stop = cursor - totals[stage][label] * scale
            nodes[stage, label] = (stop, cursor)
            inner_cursor = cursor
            for index, row in ordered[ordered[stage] == label].iterrows():
                inner_stop = inner_cursor - row["count"] * scale
                slots[stage, index] = (inner_stop, inner_cursor)
                inner_cursor = inner_stop
            if not np.isclose(inner_cursor, stop, atol=1e-12):
                raise ArithmeticError("Path widths do not fill their node.")
            cursor = stop - gap
    return categories, totals, nodes, slots, scale


def flow_path(x0, x1, start, end):
    low0, high0 = start
    low1, high1 = end
    middle = (x0 + x1) / 2
    vertices = [(x0, high0), (middle, high0), (middle, high1), (x1, high1),
                (x1, low1), (middle, low1), (middle, low0), (x0, low0), (x0, high0)]
    codes = [ArtistPath.MOVETO, *([ArtistPath.CURVE4] * 3), ArtistPath.LINETO,
             *([ArtistPath.CURVE4] * 3), ArtistPath.CLOSEPOLY]
    return ArtistPath(vertices, codes)


def build_figure(data_path=None, profile_path=None) -> Figure:
    data = load_paths(data_path or HERE / "data.csv")
    cfg = FigureConfig.load(profile_path or HERE / "style.yaml")
    categories, totals, nodes, slots, scale = flow_geometry(data)

    def draw(ax, context):
        text = []
        xs = (.11, .50, .89)
        width = .057
        total = float(data["count"].sum())
        ordered = data.sort_values(list(STAGES), kind="stable")
        for left, right in zip(range(2), range(1, 3)):
            for index in data.sort_values("count", ascending=False).index:
                row = data.loc[index]
                ax.add_patch(PathPatch(flow_path(xs[left] + width / 2, xs[right] - width / 2,
                                                 slots[STAGES[left], index], slots[STAGES[right], index]),
                                       facecolor=context.color(row["entry"]),
                                       edgecolor=(1, 1, 1, .55),
                                       linewidth=.16, alpha=.62, zorder=1))
        for number, (x, stage, title) in enumerate(
                zip(xs, STAGES, ("Before trial", "After trial", "Final choice")), start=1):
            text.append(ax.text(x, .984, f"{number:02d}", ha="center", va="center",
                                **context.text_kwargs("annotation", fontsize=9, color="#7B8797")))
            text.append(ax.text(x, .943, title, ha="center", va="center",
                                **context.text_kwargs("body", fontsize=11.5, fontweight="bold")))
            ax.plot((x - .056, x + .056), (.912, .912), color="#D6DEE8", linewidth=.6, zorder=0)
            for label in categories[stage]:
                low, high = nodes[stage, label]
                ax.add_patch(Rectangle((x - width / 2, low), width, high - low,
                                       facecolor="#FBFCFE", edgecolor="#B4C0D0", linewidth=.65, zorder=3))
                # The thin stripe retains each original path slot and color.
                # Its composition is data, not a new color for the current category.
                for index, row in ordered[ordered[stage] == label].iterrows():
                    slot_low, slot_high = slots[stage, index]
                    ax.add_patch(Rectangle((x - width / 2 + .002, slot_low), .0065,
                                           slot_high - slot_low, facecolor=context.color(row["entry"]),
                                           edgecolor="none", zorder=4))
                middle = (low + high) / 2
                count = float(totals[stage][label])
                text.append(ax.text(x + .003, middle + .033, label,
                                    ha="center", va="center", zorder=5,
                                    **context.text_kwargs("body", fontsize=11.5, fontweight="bold")))
                text.append(ax.text(x + .003, middle - .002, f"{count:g}",
                                    ha="center", va="center", zorder=5,
                                    **context.text_kwargs("body", fontsize=11, fontweight="bold")))
                text.append(ax.text(x + .003, middle - .036, f"{count / total:.1%}",
                                    ha="center", va="center", zorder=5,
                                    **context.text_kwargs("annotation", fontsize=9, color="#657386")))
        text.append(ax.text(.5, .075, f"{total:g} participants · one common count scale at every stage",
                            ha="center", va="center", **context.text_kwargs("body", fontsize=9.5)))
        text.append(ax.text(.5, .03, "Band / stripe color = initial choice · % = share of all participants",
                            ha="center", va="center", **context.text_kwargs("annotation", fontsize=9)))
        handles = tuple(Patch(facecolor=context.color(label), edgecolor="none", alpha=.62,
                              label=f"Initially {label}") for label in categories["entry"])
        return PanelResult(artists=text, legend_handles=handles)

    figure = Figure(config=cfg, rows=1, cols=1, canvas={"width": 210, "height": 180},
                    title="Same participants, changing preferences")
    figure[0, 0].custom(draw, color_group="entry", categories=categories["entry"],
                       limits=((0, 1), (0, 1)), min_size=(440, 300), preferred_aspect=1.35)
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
