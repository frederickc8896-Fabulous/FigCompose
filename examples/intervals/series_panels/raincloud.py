"""Half-density, all paired changes, and a median/IQR in one managed panel."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba

from data_visuals.core import PanelResult


def _swarm_offsets(ax, values, baseline, diameter_pt=2.8):
    """Keep each observed X value; separate nearby dots only along Y.

    Packing is deterministic and measured in points. The layout callback can
    therefore recompute it after the framework changes the physical viewport.
    No random noise, sampling, or new observations are introduced.
    """
    values = np.asarray(values, dtype=float)
    scale = 72.0 / ax.figure.dpi
    x_points = ax.transData.transform(np.column_stack((values, np.zeros(len(values)))))[:, 0] * scale
    offsets = np.zeros(len(values), dtype=float)
    order = np.argsort(values, kind="stable")
    for position, index in enumerate(order):
        previous = order[:position]
        nearby = previous[np.abs(x_points[previous] - x_points[index]) < diameter_pt]
        candidates = {0.0}
        for other in nearby:
            distance = abs(x_points[other] - x_points[index])
            candidates.add(float(offsets[other] + np.sqrt(max(0.0, diameter_pt ** 2 - distance ** 2))))
        for candidate in sorted(candidates):
            if all((x_points[index] - x_points[other]) ** 2
                   + (candidate - offsets[other]) ** 2 >= diameter_pt ** 2 - 1e-8
                   for other in nearby):
                offsets[index] = candidate
                break
    point_to_y = abs(ax.get_ylim()[1] - ax.get_ylim()[0]) / (ax.bbox.height * scale)
    return np.column_stack((values, baseline - offsets * point_to_y))


def add_panel(slot, bundle, support, *, title=None):
    """Declare a raincloud without allocating or positioning Matplotlib axes."""
    names = bundle["names"]
    bases = {name: len(names) - 1 - index for index, name in enumerate(names)}
    limits = (tuple(bundle["focus_limits"]), (-.84, len(names) - .10))
    counts = {len(bundle["groups"][name]) for name in names}
    sample_note = (f"{next(iter(counts))} pairs / dataset" if len(counts) == 1
                   else "all paired observations")

    def draw(ax, context):
        support.style_axes(ax, context, xlabel="Paired change: B - A (pp)")
        ax.set_yticks([bases[name] for name in names], names)
        ax.tick_params(axis="y", length=0, pad=6)
        ax.spines["left"].set_visible(False)
        ax.vlines(0, -.54, len(names) - .33, color="#8B97A3", linewidth=.75,
                  linestyles=(0, (3, 3)), zorder=0)
        points = []
        for name in names:
            base, color = bases[name], context.color(name)
            grid, density = bundle["density"][name]
            # Equal maximum height supports shape comparison; it is not a CI.
            profile = np.asarray(density) / np.max(density)
            ax.fill_between(grid, base + .075, base + .075 + .48 * profile,
                            facecolor=to_rgba(color, .33), edgecolor="none", zorder=1)
            ax.plot(grid, base + .075 + .48 * profile, color=color, linewidth=.85, zorder=2)
            summary = bundle["box_summaries"][name]
            ax.plot((summary["whislo"], summary["whishi"]), (base, base),
                    color=to_rgba(color, .65), linewidth=.8, solid_capstyle="round", zorder=3)
            ax.plot((summary["q1"], summary["q3"]), (base, base), color=color,
                    linewidth=3.5, solid_capstyle="round", zorder=4)
            ax.scatter((summary["median"],), (base,), s=13, facecolor="white",
                       edgecolor=color, linewidth=.75, zorder=5)
            values = bundle["groups"][name]
            collection = ax.scatter(values, np.full(len(values), base - .13), s=6,
                                    facecolor=to_rgba(color, .78), edgecolor="none", zorder=4)
            collection.set_gid("raincloud:observations:" + name)
            points.append((collection, values, base - .13))
        note = ax.text(.02, .99, f"Condition {bundle['condition']}  |  {sample_note}",
                       transform=ax.transAxes, va="top", ha="left",
                       **context.text_kwargs("annotation", fontsize=8.5, color="#5C6876"))
        key = ax.text(.02, .015, "Density + observations + median / IQR",
                      transform=ax.transAxes, va="bottom", ha="left",
                      **context.text_kwargs("annotation", fontsize=8, color="#5C6876"))

        def layout(current_ax, current_context):
            for collection, values, baseline in points:
                collection.set_offsets(_swarm_offsets(current_ax, values, baseline))

        return PanelResult(artists=(note, key), legend_handles=support.handles(context, bundle),
                           layout=layout)

    slot.custom(draw, payload=bundle, axes="on", color_group="dataset", categories=names,
                limits=limits, min_size=(160, 135), preferred_aspect=1.3,
                title=title or "Raincloud: shape, points and spread")
