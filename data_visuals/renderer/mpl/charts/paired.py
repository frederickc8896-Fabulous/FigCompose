"""Native pair trajectories and linked-scale paired estimation marks."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator, StrMethodFormatter

from data_visuals.core.identity import numeric_format_function
from .distribution import _display, _text, _wrap_label
from .helpers import series_color


def _payload(sp, kind):
    payload = sp.get("derived_data", {}).get("paired")
    if not payload or payload.get("kind") != kind:
        raise ValueError(f"{kind} requires computed complete-pair summaries.")
    return payload


def _handle(key, color):
    handle = Patch(facecolor=color, edgecolor="none", label=str(key))
    handle._figcompose_legend_key = key
    return handle


def _draw_paired(ax, sp, cfg, color_map):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    payload, opts, fonts = _payload(sp, "paired"), sp.get("options", {}), sp["font_sizes"]
    cells, levels = list(payload["cells"]), payload["levels"]
    if opts.get("series_order"):
        ranks = {value: index for index, value in enumerate(opts["series_order"])}
        cells.sort(key=lambda cell: ranks.get(_display(cell["group"], opts), len(ranks)))
    formatter = numeric_format_function(opts.get("summary_format", opts.get("value_format", ".2f")), "summary_format")
    unit = opts.get("difference_unit", "")
    all_values = np.concatenate([np.r_[cell["first"], cell["second"]] for cell in cells])
    low, high = float(all_values.min()), float(all_values.max())
    span = max(1., high - low)
    ax.set_xlim(-.7, (len(cells) - 1) * 2.9 + 1.7)
    ax.set_ylim(low - .16 * span, high + .45 * span)
    body, small = max(8., fonts["axis_label"]), max(8., fonts["tick"])
    hero = body * (1.5 if getattr(cfg, "showcase", False) else 1.35)
    text_artists, headers, summaries, handles = [], [], [], []
    for index, cell in enumerate(cells):
        raw = cell["group"]
        display = _display(raw, opts) if raw is not None else None
        color = series_color(display, index, cfg, color_map or {}, opts)
        left, right = index * 2.9, index * 2.9 + 1
        first, second = np.asarray(cell["first"]), np.asarray(cell["second"])
        ax.axvspan(left - .38, right + .38, facecolor=to_rgba(color, .035), edgecolor="none", zorder=0)
        segments = np.stack((np.column_stack((np.full(len(first), left), first)),
                             np.column_stack((np.full(len(second), right), second))), axis=1)
        trajectories = LineCollection(segments, colors=to_rgba(color, .30), linewidths=.7, zorder=1)
        trajectories.set_gid("paired:trajectories:" + str(raw))
        ax.add_collection(trajectories)
        for x, values, filled in ((left, first, False), (right, second, True)):
            marks = ax.scatter(np.full(len(values), x), values, s=8,
                               facecolor=to_rgba(color, .63) if filled else cfg.background,
                               edgecolor="none" if filled else to_rgba(color, .65),
                               linewidth=.5, zorder=2)
            marks.set_gid("paired:observations:" + str(raw) + (":second" if filled else ":first"))
        if payload["summary"] == "mean":
            ax.plot((left, right), (cell["mean_a"], cell["mean_b"]), color=color, linewidth=3.,
                    marker="o", markersize=6, markeredgecolor=cfg.background, markeredgewidth=.8, zorder=4)
            if opts.get("summary_label", True):
                value = formatter(cell["mean"]) + (" " + str(unit) if unit else "")
                artist = _text(ax, cfg, hero, (left + right) / 2, .87, value,
                               transform=ax.get_xaxis_transform(), ha="center", va="top", fontweight="bold", color=color)
                text_artists.append(artist); summaries.append(artist)
        if display is not None:
            artist = _text(ax, cfg, max(8., body * .95), (left + right) / 2, .98, str(display),
                           transform=ax.get_xaxis_transform(), ha="center", va="top", fontweight="bold", color=color)
            text_artists.append(artist); headers.append((artist, str(display)))
            handles.append(_handle(display, color))
        for x, label in ((left, levels[0]), (right, levels[1])):
            text_artists.append(_text(ax, cfg, body, x, -.025, str(label),
                                      transform=ax.get_xaxis_transform(), ha="center", va="top"))
    ax.set_xticks([])
    ax.set_xlabel(opts.get("category_label", "")); ax.set_ylabel(opts.get("value_label", sp["data"]["y"]))
    ax._data_visuals_axis_labels = {"x": ax.get_xlabel(), "y": ax.get_ylabel()}
    if "value_format" in opts:
        numeric = numeric_format_function(opts["value_format"], "value_format")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: numeric(value)))
    key = opts.get("key", "Thin: paired observations   |   thick: means" if payload["summary"] else "Lines join paired observations")
    if key:
        text_artists.append(_text(ax, cfg, small, .5, .015, str(key), transform=ax.transAxes,
                                  ha="center", va="bottom", color=cfg.muted_text_color))
    ax._data_visuals_bounds_artists = text_artists
    ax._data_visuals_minimum_plot = (max(120., len(cells) * 68.), 155.)

    def layout():
        ax.grid(False); ax.spines["bottom"].set_visible(False)
        renderer = ax.figure.canvas.get_renderer()
        room = ax.bbox.width / len(cells) * .85
        prop = FontProperties(family=cfg.font_family, size=max(8., body * .95))
        maximum = 0.
        for artist, raw in headers:
            artist.set_text(_wrap_label(raw, room, renderer, prop))
            maximum = max(maximum, artist.get_window_extent(renderer).height / ax.bbox.height)
        for artist in summaries:
            artist.set_y(.98 - maximum - .045 if headers else .94)
        # Header wrapping can need more space than short example names. Reserve
        # physical room above every raw value instead of covering observations.
        summary_height = max((artist.get_window_extent(renderer).height / ax.bbox.height
                              for artist in summaries), default=0.)
        reserved = maximum + summary_height + .10
        if reserved >= .75:
            from data_visuals.layout.placement import LayoutError
            raise LayoutError("Paired headings need more physical height; enlarge the canvas or simplify labels.",
                              axis="height", required_height=ax.figure.get_figheight() * 72 * reserved / .65)
        minimum_y = low - .16 * span
        required_top = minimum_y + (high - minimum_y) / max(.1, 1 - reserved)
        if "ylim" not in opts:
            ax.set_ylim(minimum_y, max(high + .45 * span, required_top))

    ax._figcompose_layout_callback = layout
    layout()
    return handles


def _draw_estimation(ax, sp, cfg, color_map):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    payload, opts, fonts = _payload(sp, "estimation"), sp.get("options", {}), sp["font_sizes"]
    cell, = payload["cells"]
    levels = payload["levels"]
    raw = cell["group"]; display = _display(raw, opts) if raw is not None else None
    color = series_color(display, 0, cfg, color_map or {}, opts)
    first, second = np.asarray(cell["first"]), np.asarray(cell["second"])
    grid, profile = np.asarray(cell["grid"]), np.asarray(cell["profile"])
    mean_a, mean_b, mean = cell["mean_a"], cell["mean_b"], cell["mean"]
    lower, upper = cell["lower"], cell["upper"]
    plotted = np.r_[first, second, mean_a + grid, mean_a + lower, mean_a + upper]
    low, high = float(plotted.min()), float(plotted.max())
    span = max(1., high - low)
    limits = [low - span * .07, high + span * .34]
    ax.set_xlim(-.38, 3.08); ax.set_ylim(*limits)
    ax.set_xticks([0, 1, 2.30], [str(levels[0]), str(levels[1]), opts.get("difference_title", "Paired change")])
    ax.tick_params(axis="x", length=0, pad=5)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4)); ax.yaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
    offsets = np.linspace(-.085, .085, cell["n"])
    for a, b, offset in zip(first, second, offsets):
        line, = ax.plot([offset, 1 + offset], [a, b], color=color, alpha=.24, linewidth=.7, zorder=1)
        line.set_gid("estimation:pair")
    for x, values, label in ((offsets, first, "first"), (1 + offsets, second, "second")):
        marks = ax.scatter(x, values, s=14, facecolor=color, alpha=.75,
                           edgecolor=cfg.background, linewidth=.25, zorder=3)
        marks.set_gid("estimation:observations:" + label)
    for x, value in ((0, mean_a), (1, mean_b)):
        ax.plot([x - .16, x + .16], [value, value], color=color, linewidth=2.1, solid_capstyle="round", zorder=4)
    ax.plot([1.57, 2.96], [mean_a, mean_a], color=cfg.ref_line_color,
            linewidth=.75, linestyle=(0, (3, 3)), zorder=0)
    ax.axvline(1.50, color=cfg.support_line_color, linewidth=.65, zorder=0)
    density_x = 2.30 + .58 * profile
    ax.fill_betweenx(mean_a + grid, 2.30, density_x, color=color, alpha=.44, linewidth=0, zorder=1)
    density_line, = ax.plot(density_x, mean_a + grid, color=color, linewidth=1., alpha=.9, zorder=2)
    density_line.set_gid("estimation:density")
    interval = ax.errorbar(2.10, mean_a + mean, yerr=[[mean - lower], [upper - mean]],
                           fmt="o", markersize=7.2, color=color, markeredgecolor=cfg.background,
                           markeredgewidth=.65, elinewidth=2.2, capsize=4, capthick=1.5, zorder=5)
    for artist in interval.lines[2]:
        artist.set_gid("estimation:interval")
    ax.set_xlabel(opts.get("category_label", "")); ax.set_ylabel(opts.get("value_label", sp["data"]["y"]))
    ax._data_visuals_axis_labels = {"x": ax.get_xlabel(), "y": ax.get_ylabel()}
    body, small = max(8., fonts["axis_label"]), max(8., fonts["tick"])
    secondary = ax.secondary_yaxis("right", functions=(lambda value: np.asarray(value) - mean_a,
                                                        lambda value: np.asarray(value) + mean_a))
    delta_limits = np.asarray(limits) - mean_a
    ticks = MaxNLocator(nbins=4).tick_values(*delta_limits)
    secondary.set_yticks([value for value in ticks if delta_limits[0] <= value <= delta_limits[1]])
    secondary.yaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
    if "value_format" in opts:
        numeric = numeric_format_function(opts["value_format"], "value_format")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: numeric(value)))
    if "difference_format" in opts:
        delta_format = numeric_format_function(opts["difference_format"], "difference_format")
        secondary.yaxis.set_major_formatter(FuncFormatter(lambda value, _: delta_format(value)))
    secondary.set_ylabel(opts.get("difference_label", f"Change: {levels[1]} - {levels[0]}"),
                         fontsize=fonts["axis_label"], fontfamily=cfg.font_family, color=cfg.text_color)
    secondary.tick_params(axis="y", labelsize=small, width=.6, length=3, pad=3, colors=cfg.text_color)
    for tick in secondary.get_yticklabels():
        tick.set_fontfamily(cfg.font_family)
    formatter = numeric_format_function(opts.get("summary_format", opts.get("difference_format", ".2f")), "summary_format")
    unit = opts.get("difference_unit", "")
    text_artists = [secondary.yaxis.label, *secondary.get_yticklabels()]
    note = opts.get("note", ((str(display) + "  |  ") if display is not None else "") + f"{cell['n']} pairs")
    text_artists.append(_text(ax, cfg, small, .01, .975, str(note), transform=ax.transAxes,
                              ha="left", va="top", color=cfg.muted_text_color))
    if opts.get("summary_label", True):
        text_artists.append(_text(ax, cfg, body * (2.1 if getattr(cfg, "showcase", False) else 1.8),
                                  .98, .86, formatter(mean) + (" " + str(unit) if unit else ""),
                                  transform=ax.transAxes, ha="right", va="top", fontweight="bold", color=color))
        text_artists.append(_text(ax, cfg, small, .98, .73, opts.get("summary_text", "mean paired change"),
                                  transform=ax.transAxes, ha="right", va="top", color=cfg.muted_text_color))
    level = payload["confidence"]
    ci_label = f"{level * 100:g}% CI" if level is not None else "Supplied interval"
    text_artists.append(ax.annotate("Mean\n" + ci_label, (2.10, mean_a + upper),
                                    xytext=(-2, 6), textcoords="offset points", ha="right", va="bottom",
                                    linespacing=1.1, fontsize=small, fontfamily=cfg.font_family, color=cfg.text_color))
    ax._data_visuals_bounds_artists = text_artists
    ax._data_visuals_minimum_plot = (150., 155.)

    def layout():
        ax.grid(False); ax.spines["bottom"].set_visible(False)
        secondary.spines["right"].set_color(cfg.axis_color)
        secondary.spines["right"].set_linewidth(.65)

    ax._figcompose_layout_callback = layout
    layout()
    return [_handle(display, color)] if display is not None else []
