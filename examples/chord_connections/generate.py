"""Undirected weighted chord diagram, drawn inside a FigCompose custom panel.

Run: python examples/chord_connections/generate.py
Replace data.csv with source,target,value; one row per undirected pair.
This is a reusable template, not an additional built-in chart kind.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
from matplotlib.path import Path as ArtistPath
from matplotlib.patches import Patch, PathPatch, Wedge
import numpy as np
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure, PanelResult

HERE = Path(__file__).resolve().parent


def load_connections(path):
    data = pd.read_csv(path, keep_default_na=False)
    if list(data.columns) != ["source", "target", "value"]:
        raise ValueError("CSV columns must be source,target,value in that order.")
    if data.empty:
        raise ValueError("The connection table must contain at least one edge.")
    values = pd.to_numeric(data["value"], errors="raise").to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Each connection value must be finite and positive.")
    names = list(dict.fromkeys(data["source"].tolist() + data["target"].tolist()))
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Node labels must be nonempty strings.")
    if len(names) < 3:
        raise ValueError("Use at least three groups for this chord template.")
    pairs = set()
    for source, target in data[["source", "target"]].itertuples(index=False, name=None):
        if source == target:
            raise ValueError("Self-links are not supported by this undirected template.")
        pair = frozenset((source, target))
        if pair in pairs:
            raise ValueError("Each undirected pair must appear only once; aggregate repeated pairs first.")
        pairs.add(pair)
    data = data.copy()
    data["value"] = values
    return data, tuple(names)


def connection_geometry(data, names):
    """Allocate both endpoints in the same value-to-angle scale."""
    totals = {name: 0.0 for name in names}
    for source, target, value in data.itertuples(index=False, name=None):
        totals[source] += value
        totals[target] += value
    gap = min(5.0, 36.0 / len(names))
    scale = (360.0 - gap * len(names)) / sum(totals.values())
    cursor = 90.0
    sectors = {}
    for name in names:
        stop = cursor - totals[name] * scale
        sectors[name] = (cursor, stop)
        cursor = stop - gap
    endpoints = {}
    for name in names:
        cursor = sectors[name][0]
        incident = [(index, row) for index, row in data.iterrows()
                    if name in (row["source"], row["target"])]
        incident.sort(key=lambda item: names.index(
            item[1]["target"] if item[1]["source"] == name else item[1]["source"]))
        for index, row in incident:
            stop = cursor - row["value"] * scale
            endpoints[index, name] = (cursor, stop)
            cursor = stop
        if not np.isclose(cursor, sectors[name][1], atol=1e-10):
            raise ArithmeticError("Chord endpoints do not fill their group sector.")
    return totals, sectors, endpoints, scale


def polar(angle, radius=.885):
    radians = np.deg2rad(angle)
    return radius * np.array((np.cos(radians), np.sin(radians)))


def ribbon(first, second):
    """Sample the angular endpoint spans and join them with cubic Bezier curves."""
    left = np.array([polar(angle) for angle in np.linspace(*first, 13)])
    right = np.array([polar(angle) for angle in np.linspace(*second, 13)])
    vertices = [left[0]]
    codes = [ArtistPath.MOVETO]
    for point in left[1:]:
        vertices.append(point)
        codes.append(ArtistPath.LINETO)
    vertices.extend((left[-1] * .18, right[0] * .18, right[0]))
    codes.extend((ArtistPath.CURVE4,) * 3)
    for point in right[1:]:
        vertices.append(point)
        codes.append(ArtistPath.LINETO)
    vertices.extend((right[-1] * .18, left[0] * .18, left[0]))
    codes.extend((ArtistPath.CURVE4,) * 3)
    vertices.append(left[0])
    codes.append(ArtistPath.CLOSEPOLY)
    return ArtistPath(vertices, codes)


def build_figure(data_path=None, profile_path=None) -> Figure:
    data, names = load_connections(data_path or HERE / "data.csv")
    cfg = FigureConfig.load(profile_path or HERE / "style.yaml")
    totals, sectors, endpoints, scale = connection_geometry(data, names)

    def draw(ax, context):
        text = []
        for index in data.sort_values("value", ascending=False).index:
            row = data.loc[index]
            shape = ribbon(endpoints[index, row["source"]], endpoints[index, row["target"]])
            ax.add_patch(PathPatch(shape, facecolor=context.color(row["source"]),
                                   edgecolor="white", linewidth=.35, alpha=.57, zorder=1))
        for name in names:
            start, stop = sectors[name]
            color = context.color(name)
            ax.add_patch(Wedge((0, 0), 1.015, stop, start, width=.095,
                               facecolor=color, edgecolor="white", linewidth=1.2, zorder=3))
            midpoint = (start + stop) / 2
            location = polar(midpoint, 1.19)
            text.append(ax.text(location[0], location[1] + .025, name,
                                ha="center", va="bottom",
                                **context.text_kwargs("body", fontsize=11, fontweight="bold")))
            text.append(ax.text(location[0], location[1] - .025, f"{totals[name]:g}",
                                ha="center", va="top",
                                **context.text_kwargs("body", fontsize=10, color="#657381")))
        total = float(data["value"].sum())
        text.append(ax.text(0, -1.39, f"{total:g} total connection weight  ·  {len(names)} groups", ha="center",
                            va="center", **context.text_kwargs("body", fontsize=10.5)))
        text.append(ax.text(0, -1.53, "Ribbon width = connection value\n"
                            "Color identifies one endpoint · links are undirected",
                            ha="center", va="center", linespacing=1.4,
                            **context.text_kwargs("annotation", fontsize=9.5)))
        handles = tuple(Patch(facecolor=context.color(name), edgecolor="none", label=name)
                        for name in names)
        return PanelResult(artists=text, legend_handles=handles)

    figure = Figure(config=cfg, rows=1, cols=1, canvas={"width": 210},
                    title="Shared structure, visible connections")
    # The panel includes the labels and reading note, not a padded square.
    # Keep equal data-unit scales so tightening this viewport preserves circles.
    x_limits, y_limits = (-1.40, 1.40), (-1.66, 1.20)
    aspect = (x_limits[1] - x_limits[0]) / (y_limits[1] - y_limits[0])
    figure[0, 0].custom(draw, color_group="group", categories=names,
                       limits=(x_limits, y_limits), min_size=(420, 420),
                       preferred_aspect=aspect, box_aspect=aspect)
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
