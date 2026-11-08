"""Native distribution marks consuming computed density and summary payloads."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from data_visuals.core.identity import numeric_format_function
from .helpers import series_color


def swarm_offsets(ax, values, baseline, diameter_pt=2.8, *, horizontal=True):
    """Deterministic physical packing; the measured coordinate never changes."""
    values = np.asarray(values, dtype=float)
    scale = 72 / ax.figure.dpi
    positions = (np.column_stack((values, np.zeros(len(values)))) if horizontal else
                 np.column_stack((np.zeros(len(values)), values)))
    value_axis = 0 if horizontal else 1
    points = ax.transData.transform(positions)[:, value_axis] * scale
    offsets = np.zeros(len(values))
    order = np.argsort(values, kind="stable")
    for position, index in enumerate(order):
        previous = order[:position]
        nearby = previous[np.abs(points[previous] - points[index]) < diameter_pt]
        candidates = {0.0}
        for other in nearby:
            candidates.add(float(offsets[other] + np.sqrt(max(
                0., diameter_pt ** 2 - (points[other] - points[index]) ** 2))))
        for candidate in sorted(candidates):
            if all((points[index] - points[other]) ** 2 + (candidate - offsets[other]) ** 2
                   >= diameter_pt ** 2 - 1e-8 for other in nearby):
                offsets[index] = candidate
                break
    limits = ax.get_ylim() if horizontal else ax.get_xlim()
    extent = ax.bbox.height if horizontal else ax.bbox.width
    shift = offsets * abs(limits[1] - limits[0]) / (extent * scale)
    return (np.column_stack((values, baseline - shift)) if horizontal else
            np.column_stack((baseline - shift, values)))


def _display(raw, opts):
    aliases = opts.get("category_aliases", {})
    return aliases.get(raw, aliases.get(str(raw), raw))


def _text(ax, cfg, size, x, y, value, **kwargs):
    return ax.text(x, y, value, fontsize=size, fontfamily=cfg.font_family,
                   color=kwargs.pop("color", cfg.text_color), clip_on=False, **kwargs)


def _wrap_label(value, width, renderer, font):
    """Measured wrapping, including long tokens, without abbreviating labels."""
    lines, current = [], ""
    for word in str(value).split():
        candidate = f"{current} {word}" if current else word
        if current and renderer.get_text_width_height_descent(candidate, font, False)[0] > width:
            lines.append(current); current = ""
        if current:
            current += " "
        for char in word:
            if current and renderer.get_text_width_height_descent(current + char, font, False)[0] > width:
                lines.append(current.rstrip()); current = char
            else:
                current += char
    return "\n".join([*lines, current])


def _draw_distribution(ax, sp, cfg, color_map, *, kind):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    opts = sp.get("options", {})
    payload = sp.get("derived_data", {}).get("distribution")
    if not payload or payload.get("kind") != kind:
        raise ValueError(f"{kind} requires computed distribution summaries.")
    layers = list(payload["layers"])
    if opts.get("series_order") and sp["data"].get("group") != sp["data"].get("x"):
        category_rank = {value: index for index, value in enumerate(payload["categories"])}
        group_rank = {value: index for index, value in enumerate(opts["series_order"])}
        layers.sort(key=lambda layer: (category_rank[layer["category"]],
                                       group_rank.get(_display(layer["group"], opts), len(group_rank))))
    horizontal = opts.get("horizontal", True)
    fonts = sp["font_sizes"]
    small = max(8., fonts["tick"])
    body = max(8., fonts["axis_label"])
    hero = body * (1.8 if getattr(cfg, "showcase", False) else 1.5)
    ink, muted = cfg.text_color, cfg.muted_text_color
    names, handles, points, text_artists, vertical_summaries = [], [], [], [], []
    formatter = numeric_format_function(opts.get("summary_format", opts.get("value_format", ".2f")), "summary_format")
    if "value_format" in opts:
        tick_formatter = numeric_format_function(opts["value_format"], "value_format")
        (ax.xaxis if horizontal else ax.yaxis).set_major_formatter(
            FuncFormatter(lambda value, _: tick_formatter(value)))
    count = len(layers)
    group_column = sp["data"].get("group")
    reverse = kind == "raincloud"
    summary = opts.get("summary", "median")
    top_space = .05 if kind == "raincloud" else .35
    layer_limits = (-.84, count + top_space) if kind == "raincloud" else (-.48, count + .35)
    if horizontal:
        ax.set_xlim(*payload["value_limits"]); ax.set_ylim(*layer_limits)
    else:
        ax.set_ylim(*payload["value_limits"]); ax.set_xlim(*layer_limits)

    def line(value, layer, **kwargs):
        return ax.plot(value, layer, **kwargs) if horizontal else ax.plot(layer, value, **kwargs)

    def stripe(value, low, high, **kwargs):
        return ax.vlines(value, low, high, **kwargs) if horizontal else ax.hlines(value, low, high, **kwargs)

    seen = []
    for index, layer in enumerate(layers):
        base = count - 1 - index if reverse else index
        raw_key = layer["group"] if group_column else layer["category"]
        display_key = _display(raw_key, opts) if group_column else raw_key
        color = series_color(display_key, payload["groups"].index(layer["group"])
                             if group_column else index, cfg, color_map or {}, opts)
        label = str(layer["category"])
        if group_column == sp["data"]["x"]:
            label = str(display_key)
        elif group_column and len(payload["groups"]) > 1:
            label += " · " + str(display_key)
        names.append((base, label))
        grid = np.asarray(layer["grid"]); profile = np.asarray(layer["profile"])
        bottom = base + .075 if kind == "raincloud" else base
        height = .60 if kind == "raincloud" else .95
        alpha = .48 if kind == "raincloud" else .18 + .44 * index / max(count - 1, 1)
        if horizontal:
            ax.fill_between(grid, bottom, bottom + height * profile,
                            facecolor=to_rgba(color, alpha), edgecolor="none", zorder=1 + index / 100)
        else:
            ax.fill_betweenx(grid, bottom, bottom + height * profile,
                             facecolor=to_rgba(color, alpha), edgecolor="none", zorder=1 + index / 100)
        line(grid, bottom + height * profile, color=color, linewidth=1.25, zorder=2)
        if summary == "median":
            stripe(layer["median"], bottom,
                   bottom + height * np.interp(layer["median"], grid, profile),
                   color=cfg.background, linewidth=1.6, zorder=3)
        values = np.asarray(layer["values"])
        if kind == "raincloud":
            if summary == "median":
                line((layer["whislo"], layer["whishi"]), (base, base), color=to_rgba(color, .65),
                     linewidth=.8, solid_capstyle="round", zorder=3)
                line((layer["q1"], layer["q3"]), (base, base), color=color,
                     linewidth=4.8, solid_capstyle="round", zorder=4)
                xy = ([layer["median"]], [base]) if horizontal else ([base], [layer["median"]])
                ax.scatter(*xy, s=13, facecolor=cfg.background, edgecolor=color, linewidth=.75, zorder=5)
            xy = (values, np.full(len(values), base - .13)) if horizontal else (np.full(len(values), base - .13), values)
            collection = ax.scatter(*xy, s=7.5, facecolor=to_rgba(color, .85), edgecolor="none", zorder=4)
            collection.set_gid("raincloud:observations:" + str(raw_key))
            points.append((collection, values, base - .13))
            if summary == "median" and opts.get("summary_label", True):
                transform = ax.get_yaxis_transform() if horizontal else ax.get_xaxis_transform()
                positions = ((.98, base + .53), (.98, base + .29)) if horizontal else ((base + .53, .98), (base + .53, .88))
                number = _text(ax, cfg, hero, *positions[0], formatter(layer["median"]),
                               transform=transform, ha="right" if horizontal else "center", va="center", fontweight="bold", color=color)
                caption = _text(ax, cfg, small, *positions[1], opts.get("summary_text", "median"),
                                transform=transform, ha="right" if horizontal else "center", va="center", color=muted)
                text_artists.extend((number, caption))
                if not horizontal:
                    vertical_summaries.append((number, caption, base + .53))
        else:
            rug = stripe(values, base - .08, base + .025, color=to_rgba(color, .46), linewidth=.45, zorder=3)
            rug.set_gid("ridgeline:observations:" + str(layer["category"]))
        if group_column and raw_key not in seen:
            handle = Patch(facecolor=color, edgecolor="none", label=str(display_key))
            handle._figcompose_legend_key = display_key
            handles.append(handle); seen.append(raw_key)
    positions, labels = zip(*names)
    if horizontal:
        ax.set_yticks(positions, labels)
        ax.set_xlabel(opts.get("value_label", sp["data"]["y"])); ax.set_ylabel(opts.get("category_label", ""))
    else:
        ax.set_xticks(positions, labels)
        ax.set_ylabel(opts.get("value_label", sp["data"]["y"])); ax.set_xlabel(opts.get("category_label", ""))
    ax._data_visuals_axis_labels = {"x": ax.get_xlabel(), "y": ax.get_ylabel()}
    if opts.get("reference") is not None:
        from data_visuals.compute.distribution import _number
        if not _number(opts["reference"]):
            raise ValueError("reference must be a finite real value.")
        (ax.axvline if horizontal else ax.axhline)(opts["reference"], color=cfg.ref_line_color,
                                                   linewidth=.75, linestyle=(0, (3, 3)), zorder=0)
    note = opts.get("note")
    key = opts.get("key", (("Density + observations + median / IQR" if summary else "Density + observations") if kind == "raincloud"
                           else f"Gaussian KDE · {payload['normalization']} normalization"))
    if note:
        text_artists.append(_text(ax, cfg, small, .02, .99, str(note), transform=ax.transAxes,
                                  va="top", ha="left", color=muted))
    if key:
        text_artists.append(_text(ax, cfg, small, .02 if kind == "raincloud" else .98, .015,
                                  str(key), transform=ax.transAxes, va="bottom",
                                  ha="left" if kind == "raincloud" else "right", color=muted))
    ax._data_visuals_bounds_artists = text_artists
    minimum = (150., max(135., count * 43.)) if horizontal else (max(150., count * 43.), 135.)
    ax._data_visuals_minimum_plot = minimum

    def update_layout():
        ax.grid(False)
        (ax.spines["left"] if horizontal else ax.spines["bottom"]).set_visible(False)
        ax.tick_params(axis="y" if horizontal else "x", length=0, pad=6)
        renderer = ax.figure.canvas.get_renderer()
        prop = FontProperties(family=cfg.font_family, size=fonts["tick"])
        room = max(35., ax.bbox.width * 72 / ax.figure.dpi * (.32 if horizontal else 1 / max(count, 1)))
        wrapped = [_wrap_label(label, room * ax.figure.dpi / 72, renderer, prop) for label in labels]
        old_limits = ax.get_ylim() if horizontal else ax.get_xlim()
        (ax.set_yticks if horizontal else ax.set_xticks)(positions, wrapped)
        (ax.set_ylim if horizontal else ax.set_xlim)(old_limits)
        label_height = max(fonts["tick"] * 1.3 * (value.count("\n") + 1) + 7 for value in wrapped)
        if horizontal:
            ax._data_visuals_minimum_plot = (minimum[0], max(minimum[1], count * label_height))
        for number, caption, x in vertical_summaries:
            number_height = number.get_window_extent(renderer).height / ax.bbox.height
            caption_height = caption.get_window_extent(renderer).height / ax.bbox.height
            gap = 2. * ax.figure.dpi / 72 / ax.bbox.height
            number.set_position((x, .98 - number_height / 2))
            caption.set_position((x, .98 - number_height - gap - caption_height / 2))
        for collection, values, baseline in points:
            offsets = swarm_offsets(ax, values, baseline, horizontal=horizontal)
            collection.set_offsets(offsets)
            packed = offsets[:, 1 if horizontal else 0]
            if baseline - float(packed.min()) > .58:
                from data_visuals.layout.placement import LayoutError
                extent = ax.bbox.height if horizontal else ax.bbox.width
                factor = (baseline - float(packed.min())) / .58
                total = ax.figure.get_figheight() if horizontal else ax.figure.get_figwidth()
                required = total * 72 + extent * 72 / ax.figure.dpi * (factor - 1)
                raise LayoutError("Raincloud observations need more physical space; enlarge the canvas.",
                                  axis="height" if horizontal else "width",
                                  **{"required_height" if horizontal else "required_width": required})

    ax._figcompose_layout_callback = update_layout
    update_layout()
    return handles


def _draw_raincloud(ax, sp, cfg, color_map):
    return _draw_distribution(ax, sp, cfg, color_map, kind="raincloud")


def _draw_ridgeline(ax, sp, cfg, color_map):
    return _draw_distribution(ax, sp, cfg, color_map, kind="ridgeline")
