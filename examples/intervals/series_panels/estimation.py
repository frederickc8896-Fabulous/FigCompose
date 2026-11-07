"""Paired estimation inside one FigCompose-managed Matplotlib axes.

The two scales are linked exactly: the displayed difference coordinate is
``mean(A) + (B - A)``. The right axis therefore reads actual paired differences,
while the left axis retains raw percentages. The density represents individual
paired differences, not a sampling distribution of the mean.
"""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from data_visuals.core import PanelResult


def add_panel(slot, bundle, support, *, title=None):
    """Declare a paired raw-observation / difference-distribution panel."""
    name = bundle["ridge_dataset"]
    original_a, original_b, pair_ids = bundle["paired_values"][name]
    original_a = np.asarray(original_a, dtype=float)
    original_b = np.asarray(original_b, dtype=float)
    mean_a, mean_b = bundle["means"][name]
    mean, lower, upper, count = bundle["mean_ci"][name]
    grid, density = bundle["density"][name]
    grid, density = np.asarray(grid), np.asarray(density)
    # These bounds include both raw observations and the translated difference
    # distribution. No values are trimmed merely to enlarge the effect.
    plotted_y = np.concatenate((original_a, original_b, mean_a + grid,
                                [mean_a + lower, mean_a + upper]))
    minimum, maximum = float(plotted_y.min()), float(plotted_y.max())
    spread = max(1.0, maximum - minimum)
    limits = ((-.38, 3.08), (minimum - spread * .07, maximum + spread * .19))
    # Fixed, paired offsets distinguish observations without random jitter or
    # moving either endpoint's measured value. Same offset belongs to each ID.
    offsets = np.linspace(-.085, .085, len(pair_ids))
    density_x = 2.30 + .47 * density / float(density.max())

    def draw(ax, context):
        color = context.color(name)
        support.style_axes(ax, context, ylabel="Accuracy (%)")
        ax.grid(False)
        ax.set_xticks([0, 1, 2.30], ["Method A", "Method B", "Paired change"])
        ax.tick_params(axis="x", length=0, pad=5)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        ax.spines["bottom"].set_visible(False)

        # Pair identity is preserved in both line endpoints and the tiny
        # horizontal offset. Grey connections leave the distribution readable.
        for first, second, offset in zip(original_a, original_b, offsets):
            ax.plot([offset, 1 + offset], [first, second], color=color,
                    alpha=.16, linewidth=.55, zorder=1)
        ax.scatter(offsets, original_a, s=11, facecolor=color, alpha=.65,
                   edgecolor="white", linewidth=.25, zorder=3)
        ax.scatter(1 + offsets, original_b, s=11, facecolor=color, alpha=.65,
                   edgecolor="white", linewidth=.25, zorder=3)
        ax.plot([-.16, .16], [mean_a, mean_a], color=color, linewidth=2.1,
                solid_capstyle="round", zorder=4)
        ax.plot([.84, 1.16], [mean_b, mean_b], color=color, linewidth=2.1,
                solid_capstyle="round", zorder=4)

        # A zero difference is anchored exactly at the observed mean of A.
        ax.plot([1.57, 2.96], [mean_a, mean_a], color="#8B959E",
                linewidth=.75, linestyle=(0, (3, 3)), zorder=0)
        ax.axvline(1.50, color="#E4E8EC", linewidth=.65, zorder=0)
        ax.fill_betweenx(mean_a + grid, 2.30, density_x,
                         color=color, alpha=.23, linewidth=0, zorder=1)
        ax.plot(density_x, mean_a + grid, color=color, linewidth=1.0,
                alpha=.9, zorder=2)
        center = mean_a + mean
        ax.errorbar(2.10, center, yerr=[[mean - lower], [upper - mean]],
                    fmt="o", markersize=5.2, color=color,
                    markeredgecolor="white", markeredgewidth=.65,
                    elinewidth=1.6, capsize=3, capthick=1.2, zorder=5)

        secondary = ax.secondary_yaxis("right", functions=(
            lambda value: value - mean_a, lambda value: value + mean_a))
        delta_limits = np.asarray(limits[1]) - mean_a
        ticks = MaxNLocator(nbins=4).tick_values(*delta_limits)
        secondary.set_yticks([value for value in ticks
                             if delta_limits[0] <= value <= delta_limits[1]])
        secondary.yaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        secondary.set_ylabel("Paired change B - A (pp)",
                             **context.text_kwargs("axis_label"))
        secondary.tick_params(axis="y", labelsize=max(8, context.font_sizes["tick"]),
                              width=.6, length=3, pad=3, colors=context.text_color)
        secondary.spines["right"].set_color("#A3ADB7")
        secondary.spines["right"].set_linewidth(.65)
        for tick in secondary.get_yticklabels():
            tick.set_fontfamily(context.font_family)

        header = ax.text(.01, .975,
                         f"{name}  |  condition {bundle['condition']}  |  {count} pairs",
                         transform=ax.transAxes, ha="left", va="top",
                         **context.text_kwargs("annotation", fontsize=8.5,
                                               color="#536270"))
        interval_label = ax.annotate("Mean\n95% CI", (2.10, mean_a + upper),
                                     xytext=(-2, 6), textcoords="offset points",
                                     ha="right", va="bottom", linespacing=1.1,
                                     **context.text_kwargs("annotation", fontsize=8))
        # Secondary ticks/label are explicit measured decoration artists. The
        # secondary axis is a child of this supplied axes, not another panel.
        artists = [header, interval_label, secondary.yaxis.label,
                   *secondary.get_yticklabels()]
        return PanelResult(
            artists=artists,
            legend_handles=(Patch(facecolor=color, edgecolor="none", label=name),),
        )

    return slot.custom(draw, payload=bundle, axes="on", color_group="dataset",
                       categories=(name,), title=title or "Paired estimation",
                       preferred_aspect=1.3, min_size=(150, 120), limits=limits)
