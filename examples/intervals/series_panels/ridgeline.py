"""Aligned KDE ridges show how a paired-change distribution shifts by condition."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba

from data_visuals.core import PanelResult


def add_panel(slot, bundle, support, *, title=None):
    conditions = tuple(bundle["conditions"])
    selected = bundle["ridge_dataset"]
    counts = {len(bundle["ridge"][condition]) for condition in conditions}
    sample_note = (f"{next(iter(counts))} pairs per condition" if len(counts) == 1
                   else "sample sizes shown per condition")

    def draw(ax, context):
        support.style_axes(ax, context, xlabel="Paired change: B - A (pp)",
                           ylabel="Condition")
        labels = [str(value) if len(counts) == 1 else f"{value} (n={len(bundle['ridge'][value])})"
                  for value in conditions]
        ax.set_yticks(range(len(conditions)), labels)
        ax.tick_params(axis="y", length=0, pad=5)
        ax.spines["left"].set_visible(False)
        ax.vlines(0, -.25, len(conditions) - .04, color="#8B97A3", linewidth=.75,
                  linestyles=(0, (3, 3)), zorder=0)
        color = context.color(selected)
        for index, condition in enumerate(conditions):
            grid, density = bundle["ridge_density"][condition]
            profile = np.asarray(density) / np.max(density)
            fill = to_rgba(color, .16 + .065 * index)
            ax.hlines(index, *bundle["ridge_limits"], color="#E5EAF0", linewidth=.5, zorder=0)
            ax.fill_between(grid, index, index + .76 * profile, facecolor=fill,
                            edgecolor="none", zorder=1 + index)
            ax.plot(grid, index + .76 * profile, color=color, linewidth=.9, zorder=2 + index)
            values = bundle["ridge"][condition]
            rug = ax.vlines(values, index - .08, index + .025,
                            color=to_rgba(color, .46), linewidth=.45, zorder=3 + index)
            rug.set_gid(f"ridgeline:observations:{condition}")
        note = ax.text(.02, .99, f"{selected}  |  {sample_note}",
                       transform=ax.transAxes, va="top", ha="left",
                       **context.text_kwargs("annotation", fontsize=8.5, color="#5C6876"))
        key = ax.text(.98, .015, "KDE ridges scaled to equal height",
                      transform=ax.transAxes, va="bottom", ha="right",
                      **context.text_kwargs("annotation", fontsize=8, color="#5C6876"))
        handles = support.handles(context, {**bundle, "names": (selected,)})
        return PanelResult(artists=(note, key), legend_handles=handles)

    slot.custom(draw, payload=bundle, axes="on", color_group="dataset", categories=(selected,),
                limits=(tuple(bundle["ridge_limits"]), (-.48, len(conditions) + .35)),
                min_size=(160, 135), preferred_aspect=1.3,
                title=title or "Ridgeline: changing distributions")
