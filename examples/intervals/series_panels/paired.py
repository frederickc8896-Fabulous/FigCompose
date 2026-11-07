"""Preserve individual A/B pairing rather than comparing unrelated clouds."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba

from data_visuals.core import PanelResult


def add_panel(slot, bundle, support, *, title=None):
    names = bundle["names"]
    all_values = np.concatenate([np.concatenate(bundle["paired_values"][name][:2]) for name in names])
    low, high = float(np.min(all_values)), float(np.max(all_values))
    span = max(1.0, high - low)
    limits = ((-.7, (len(names) - 1) * 2.9 + 1.7), (low - .16 * span, high + .20 * span))

    def draw(ax, context):
        support.style_axes(ax, context, ylabel="Accuracy (%)")
        labels = []
        for index, name in enumerate(names):
            left, right = index * 2.9, index * 2.9 + 1
            color = context.color(name)
            first, second, pair_ids = bundle["paired_values"][name]
            ax.axvspan(left - .38, right + .38, facecolor=to_rgba(color, .035), edgecolor="none", zorder=0)
            segments = np.stack((np.column_stack((np.full(len(first), left), first)),
                                 np.column_stack((np.full(len(second), right), second))), axis=1)
            trajectories = LineCollection(segments, colors=to_rgba(color, .22), linewidths=.55, zorder=1)
            trajectories.set_gid("paired:trajectories:" + name)
            ax.add_collection(trajectories)
            ax.scatter(np.full(len(first), left), first, s=6.5, facecolor="white",
                       edgecolor=to_rgba(color, .65), linewidth=.5, zorder=2)
            ax.scatter(np.full(len(second), right), second, s=6.5,
                       facecolor=to_rgba(color, .63), edgecolor="none", zorder=2)
            means = bundle["means"][name]
            ax.plot((left, right), means, color=color, linewidth=2.1,
                    marker="o", markersize=4.8, markeredgecolor="white", markeredgewidth=.7, zorder=4)
            labels.append(ax.text((left + right) / 2, .96, name, ha="center", va="top",
                                  transform=ax.get_xaxis_transform(),
                                  **context.text_kwargs("body", fontsize=9, fontweight="bold", color=color)))
            # These are local method labels within three repeated pairs,
            # rather than distinct categories on a single numerical X scale.
            for x, label in ((left, "A"), (right, "B")):
                labels.append(ax.text(x, -.025, label, transform=ax.get_xaxis_transform(),
                                      ha="center", va="top",
                                      **context.text_kwargs("body", fontsize=9)))
        ax.set_xticks([])
        ax.tick_params(axis="x", length=0, pad=5)
        ax.spines["bottom"].set_visible(False)
        note = ax.text(.5, .015, "Thin: paired runs   |   thick: means",
                       transform=ax.transAxes, ha="center", va="bottom",
                       **context.text_kwargs("annotation", fontsize=8, color="#5C6876"))
        return PanelResult(artists=(*labels, note), legend_handles=support.handles(context, bundle))

    slot.custom(draw, payload=bundle, axes="on", color_group="dataset", categories=names,
                limits=limits, min_size=(160, 135), preferred_aspect=1.3,
                title=title or f"Paired trajectories | condition {bundle['condition']}")
