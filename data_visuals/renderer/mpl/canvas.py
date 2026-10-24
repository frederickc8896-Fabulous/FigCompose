"""Render a fixed canvas; measure decorations without tight layout or cropping."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox

from data_visuals.core.legend import normalize_legend
from data_visuals.layout.placement import LayoutError, align_gutters, cell_boxes, inset_box
from data_visuals.renderer.mpl.config import MplConfig
from data_visuals.renderer.mpl.styling import style_axis as _style_axis
from data_visuals.renderer.mpl.axes import apply_axis_options, validate_axis_options
from data_visuals.renderer.mpl.charts.registry import _BUILDERS
from data_visuals.renderer.mpl.custom import (
    prepare_custom_panels, position_custom, custom_bounds, place_custom_title,
    create_panel_axes, position_axes,
)

DPI = 72  # One design point is one measurement pixel, independent of export DPI.


def _frac_box(box, total_w, total_h, y_offset=0):
    return (box["x"] / total_w, 1 - (box["y"] + y_offset + box["h"]) / total_h,
            box["w"] / total_w, box["h"] / total_h)


def _sort_values(values):
    return sorted(set(values), key=lambda v: (type(v).__name__, str(v)))


def _text_width(renderer, text, prop):
    return max((renderer.get_text_width_height_descent(line, prop, False)[0]
                for line in str(text).split("\n")), default=0)


def _wrap(text, max_width, renderer, prop):
    """Wrap words and long tokens, preserving all text."""
    lines = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if current and _text_width(renderer, candidate, prop) > max_width:
                lines.append(current)
                current = ""
            if current:
                current += " "
            for char in word:
                if current and _text_width(renderer, current + char, prop) > max_width:
                    lines.append(current.rstrip())
                    current = char
                else:
                    current += char
        lines.append(current)
    return "\n".join(lines)


def _legend_options(spec, subplot=None):
    """Merge only explicit values; a subplot override requests a local legend."""
    options = normalize_legend(spec.get("legend"))
    if subplot is not None and "legend" in subplot.get("options", {}):
        local = normalize_legend(subplot["options"]["legend"])
        options = {**options, **local, "scope": local.get("scope", "local")}
    return options


def _legend_group(subplot, options):
    group = subplot["data"].get("group")
    measures = subplot["data"].get("y")
    if group is None and subplot["chart"] == "custom" and options.get("scope") == "shared":
        return "__custom__"
    if group is None and isinstance(measures, (list, tuple)) and len(measures) > 1 and options.get("scope") == "shared":
        return "__measures__"
    return group


def _legend_entries(handles, options, subplot=None):
    """Reorder/relabel glyphs without changing data or their category colours."""
    aliases = {}
    if subplot is not None:
        group = subplot["data"].get("group")
        styles = subplot.get("options", {}).get("series_styles", {})
        for row in subplot.get("computed_data", []):
            if group and group in row:
                key = row[group]
                style = styles.get(key, styles.get(str(key), {}))
                aliases[style.get("label", str(key))] = key
    entries = [(getattr(handle, "_paperfig_legend_key", aliases.get(handle.get_label(), handle.get_label())),
                handle, handle.get_label()) for handle in handles]
    order = options.get("order") or []
    ranks = {value: i for i, value in enumerate(order)}
    entries.sort(key=lambda entry: ranks.get(entry[0], len(ranks)))
    labels = options.get("labels") or {}
    return ([handle for _, handle, _ in entries],
            [labels.get(key, labels.get(str(key), label)) for key, _, label in entries])


def _shared_legend_blocks(fig, spec, cfg, group_cells, shared, maps, width, padding, default_size,
                          custom_records=None):
    from data_visuals.renderer.mpl.legends import MeasuredLegend
    options = _legend_options(spec)
    position = options.get("position", spec.get("shared_legend", {}).get("position", "top"))
    defaults = {"position": position, "fontsize": default_size, "ncols": None,
                "gap": padding * .8, "columnspacing": 8, "labelspacing": 3,
                "handlelength": 12, "handletextpad": 4, "borderpad": 3,
                "frameon": False, "anchor": None, "order": None, "labels": None}
    effective = []
    for column in sorted(shared):
        for sp in group_cells[column]:
            values = {key: _legend_options(spec, sp).get(key, value) for key, value in defaults.items()}
            for key in ("fontsize", "gap"):
                if values[key] is None:
                    values[key] = defaults[key]
            values["order"], values["labels"] = values["order"] or None, values["labels"] or None
            effective.append(values)
    if effective:
        if any(values != effective[0] for values in effective[1:]):
            raise ValueError("Shared legend overrides conflict between panels; configure the shared legend on Figure or use scope='local'")
        options = effective[0]
        position = options["position"]
    if shared and position not in ("top", "bottom", "left", "right"):
        raise ValueError("Shared legend.position must be top/bottom/left/right; use scope='local' for corners")
    side = position in ("left", "right")
    max_width = (min(width * .32, width - 2 * padding - cfg.min_plot_width - 30)
                 if side else width - 2 * padding)
    if shared and max_width <= 6:
        raise LayoutError("The canvas is too narrow for a side legend and readable axes; increase canvas width.",
                          axis="width", required_width=2 * padding + cfg.min_plot_width + 60)
    blocks = []
    for column in sorted(shared):
        cells = group_cells[column]
        # Custom content supplies actual glyphs. Statistical glyphs keep their
        # existing construction and take priority for repeated semantic keys.
        chart_cells = [sp for sp in cells if sp["chart"] != "custom"]
        visible = (_sort_values(name for sp in chart_cells for name in sp["data"]["y"])
                   if column == "__measures__" else
                   _sort_values(row[column] for sp in chart_cells
                                for row in sp.get("computed_data", []) if column in row))
        color_map = maps.get(column, {})
        if chart_cells and all(sp["chart"] == "scatter" for sp in chart_cells):
            handles = _shared_scatter_legend(chart_cells, visible, color_map, cfg)
        elif chart_cells and all(sp["chart"] in ("line", "radar") for sp in chart_cells):
            markers = [sp.get("options", {}).get("markers", True) for sp in chart_cells]
            handles = [Line2D([], [], color=color_map[v], marker="o" if all(markers) else None,
                              linewidth=cfg.line_stroke_width, markersize=math.sqrt(cfg.marker_size),
                              label=str(v)) for v in visible]
            for handle, value in zip(handles, visible):
                handle._paperfig_legend_key = value
        else:
            handles = [Patch(facecolor=color_map[v], edgecolor=cfg.bar_stroke,
                             linewidth=.5, label=str(v)) for v in visible]
            for handle, value in zip(handles, visible):
                handle._paperfig_legend_key = value
        seen = {getattr(handle, "_paperfig_legend_key", handle.get_label()) for handle in handles}
        for sp in cells:
            record = (custom_records or {}).get((sp["row"], sp["col"]))
            for handle in record["handles"] if record else ():
                label = handle.get_label()
                key = getattr(handle, "_paperfig_legend_key", label)
                if label and not label.startswith("_") and key not in seen:
                    handles.append(handle)
                    seen.add(key)
        handles, labels = _legend_entries(handles, options)
        if not handles:
            continue
        legend = MeasuredLegend(fig, handles, labels, options, cfg,
                                default_fontsize=default_size, max_width=max_width,
                                orientation="vertical" if side else "horizontal")
        heading = None
        heading_height = 0.0
        if len(shared) > 1:
            size = options.get("fontsize") or default_size
            prop = FontProperties(family=cfg.font_family, size=size)
            heading = fig.text(0, 0, _wrap(column, max_width, fig.canvas.get_renderer(), prop),
                               fontproperties=prop, ha="center", va="top", color=cfg.text_color)
            heading_height = heading.get_window_extent(fig.canvas.get_renderer()).height + 3
        blocks.append({"legend": legend, "heading": heading, "heading_height": heading_height})
    if len(blocks) == 1 and blocks[0]["heading"] is not None:
        blocks[0]["heading"].remove()
        blocks[0]["heading"] = None
        blocks[0]["heading_height"] = 0.0
    return blocks, position, options


def _place_shared_blocks(blocks, fig, position, options, width, height, padding, header):
    """Reserve the complete occupied edge band, including an explicit anchor."""
    if not blocks:
        return header, 0.0, 0.0, 0.0, []
    gap = options.get("gap")
    gap = padding * .8 if gap is None else gap
    block_width = max(max(block["legend"].width,
                          block["heading"].get_window_extent(fig.canvas.get_renderer()).width
                          if block["heading"] is not None else 0) for block in blocks)
    block_height = sum(block["legend"].height + block["heading_height"] for block in blocks)
    block_height += gap * (len(blocks) - 1)
    anchor = options.get("anchor")
    if anchor is not None:
        x, y = anchor[0] * width, (1 - anchor[1]) * height
        if position in ("top", "bottom"):
            x -= block_width / 2
            y -= block_height if position == "bottom" else 0
        else:
            x -= block_width if position == "right" else 0
            y -= block_height / 2
    elif position == "top":
        x, y = (width - block_width) / 2, header
    elif position == "bottom":
        x, y = (width - block_width) / 2, height - padding - block_height
    else:
        x = padding if position == "left" else width - padding - block_width
        y = header + padding + (height - header - 2 * padding - block_height) / 2
    if min(x, y) < -.5 or x + block_width > width + .5 or y + block_height > height + .5:
        raise LayoutError("Legend anchor or dimensions exceed the canvas; move the anchor or enlarge the canvas.",
                          axis="width" if x < 0 or x + block_width > width else "height",
                          required_width=max(width, block_width + 2 * padding),
                          required_height=max(height, header + block_height + 2 * padding))
    if position == "top" and y < header - .5:
        raise LayoutError("The anchored legend overlaps the figure title; lower legend.anchor or use automatic placement.",
                          axis="height", required_width=width, required_height=height + header - y)
    footer = left = right = 0.0
    if position == "top":
        header = y + block_height + gap
    elif position == "bottom":
        footer = height - padding - y + gap
    elif position == "left":
        left = x + block_width - padding + gap
    else:
        right = width - padding - x + gap
    artists = []
    for block in blocks:
        legend, heading = block["legend"], block["heading"]
        if heading is not None:
            heading.set_position(((x + block_width / 2) / width, 1 - y / height))
            artists.append(heading)
        y += block["heading_height"]
        artists.extend(legend.place(x + (block_width - legend.width) / 2, y))
        y += legend.height + gap
    return header, footer, left, right, artists


def _colour_maps(spec, cfg):
    domains = defaultdict(list)
    for column, values in spec.get("color_domains", {}).items():
        domains[column].extend(values)
    for sp in spec["subplots"]:
        column = sp["data"].get("group")
        if column:
            domains[column].extend(row[column] for row in sp.get("computed_data", [])
                                   if column in row and row[column] is not None)
        elif isinstance(sp["data"].get("y"), list):
            domains["__measures__"].extend(sp["data"]["y"])
    maps = {}
    for column, values in domains.items():
        values = _sort_values(values)
        if values:
            palette = cfg.get_palette(len(values))
            overrides = spec.get("category_colors", {}).get(column, {})
            maps[column] = {v: overrides.get(v, overrides.get(str(v), palette[i % len(palette)]))
                            for i, v in enumerate(values)}
    return maps


def _continuous_limits(subplots):
    """Use a common numeric colour scale for the same measure and colour scheme."""
    domains = defaultdict(list)
    keys = {}
    for sp in subplots:
        kind = sp["chart"]
        if kind not in ("heatmap", "confusion"):
            continue
        mapping, opts = sp["data"], sp.get("options", {})
        normalized = kind == "confusion" and opts.get("normalize", False)
        measure = mapping.get("value", f"{mapping['x']}_count")
        key = (kind, measure, repr(opts.get("color_scheme")), normalized)
        keys[sp["row"], sp["col"]] = key
        if normalized:
            domains[key].extend([0.0, 1.0])
        for row in sp.get("computed_data", []):
            value = row.get(f"{measure}_mean", row.get(measure))
            if isinstance(value, (int, float)) and math.isfinite(value):
                domains[key].append(float(value))
        if kind == "confusion" and not normalized:
            domains[key].append(0.0)
    for sp in subplots:
        key = keys.get((sp["row"], sp["col"]))
        values = domains.get(key, [])
        if values:
            low, high = min(values), max(values)
            sp["_color_limits"] = (low, high) if low != high else (low - 0.5, high + 0.5)


def _fit_ticks(ax, width, renderer, cfg, fs):
    if not getattr(ax, "_data_visuals_categorical_x", False):
        return
    if not hasattr(ax, "_data_visuals_raw_ticks"):
        ax._data_visuals_raw_ticks = (list(ax.get_xticks()), [t.get_text() for t in ax.get_xticklabels()])
    positions, raw = ax._data_visuals_raw_ticks
    if not raw:
        return
    prop = FontProperties(family=cfg.font_family, size=fs["tick"])
    labels = [_wrap(text, max(fs["tick"] * 5, width * 0.32), renderer, prop) for text in raw]
    spacing = width / len(labels)
    angle = 90
    for candidate in (0, 45, 60, 90):
        radians = math.radians(candidate)
        projected = max(_text_width(renderer, label, prop) * math.cos(radians) +
                        fs["tick"] * 1.2 * (label.count("\n") + 1) * math.sin(radians)
                        for label in labels)
        if projected <= spacing * 0.94:
            angle = candidate
            break
    else:
        required = len(labels) * max(
            fs["tick"] * 1.2 * (label.count("\n") + 1) for label in labels) / 0.94
        raise LayoutError(
            "Categorical tick labels are too dense; use a wider canvas or fewer columns.",
            axis="width", required_width=required,
        )
    # For vertical labels align the *rotated* bounding box below the ticks.
    # Anchoring an unrotated, horizontally centered label at 90 degrees leaves
    # half of its text above the baseline, inside the data region.
    limits = ax.get_xlim()
    ax.set_xticks(positions, labels, rotation=angle,
                  ha="center" if angle in (0, 90) else "right", va="top",
                  rotation_mode="default" if angle == 90 else "anchor")
    ax.set_xlim(limits, auto=None)


def figure_to_matplotlib(spec) -> plt.Figure:
    from data_visuals.core.spec import FigureSpec
    # Runtime callbacks stay outside the JSON-safe representation. Their
    # declarations preserve identity while mutable layout dictionaries detach.
    raw = spec.to_dict(runtime=True) if isinstance(spec, FigureSpec) else (
        spec.to_dict() if hasattr(spec, "to_dict") else spec)
    d = deepcopy(raw)
    width, height = float(d["canvas"]["width"]), float(d["canvas"]["height"])
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError("Canvas width and height must be finite and positive")
    cfg = MplConfig(d.get("theme", "general"), palette=d.get("palette"),
                    physical=d["canvas"].get("physical") is True)
    if d.get("font_family"):
        cfg.font_family = cfg._resolve_font(d["font_family"])
    cfg.background = d.get("background", cfg.background)
    with matplotlib.rc_context(cfg.rcparams()):
        fig = plt.figure(figsize=(width / DPI, height / DPI), dpi=DPI)
        try:
            fig.patch.set_facecolor(cfg.background)
            fig._data_visuals_rcparams = cfg.rcparams()
            try:
                return _render(fig, d, cfg, width, height)
            except LayoutError:
                if not getattr(fig, "_data_visuals_reclaiming", False):
                    raise
                # A reclamation probe is optional. Rebuild once with the
                # conservative solver if a locator, legend or native aspect
                # rejects the probe; never lose an already feasible canvas.
                fig.clear()
                return _render(fig, d, cfg, width, height, allow_reclaim=False)
        except BaseException:
            plt.close(fig)
            raise


def _canvas_error(error, box, key, width, height, padding, header, side=0):
    """Convert a cell's measured minimum into an absolute canvas-size hint."""
    available_w = max(1.0, width - 2 * padding - side)
    available_h = max(1.0, height - header - 2 * padding)
    required_w = error.required_width or box["w"]
    required_h = error.required_height or box["h"]
    error.required_width = max(width, 2 * padding + side + available_w * required_w / max(1.0, box["w"]))
    error.required_height = max(height, header + 2 * padding + available_h * required_h / max(1.0, box["h"]))
    error.subplot = key
    return error


def _inset(box, gutters, minimum, key, width, height, padding, header, side=0):
    try:
        return inset_box(box, gutters, minimum, key)
    except LayoutError as error:
        raise _canvas_error(error, box, key, width, height, padding, header, side) from None


def _fit_cell_ticks(ax, zone, box, renderer, cfg, fs, key, width, height, padding, header, side=0):
    try:
        _fit_ticks(ax, zone["w"], renderer, cfg, fs)
    except LayoutError as error:
        error.required_width = box["w"] + max(0, (error.required_width or zone["w"]) - zone["w"])
        raise _canvas_error(error, box, key, width, height, padding, header, side) from None


def _minimum_plot(sp, cfg, renderer):
    if sp["chart"] == "custom":
        return sp["_custom_panel"].min_size
    if sp["chart"] in ("pie", "donut", "radar"):
        return max(60.0, cfg.min_plot_width), max(60.0, cfg.min_plot_height)
    if not cfg.physical:
        return max(20.0, sp["font_sizes"]["tick"] * 2)
    minimum_w, minimum_h = cfg.min_plot_width, cfg.min_plot_height
    if sp["chart"] in ("heatmap", "confusion") and sp.get("options", {}).get("annotate", True):
        mapping, rows, opts = sp["data"], sp.get("computed_data", []), sp.get("options", {})
        xs = {str(row.get(mapping["x"])) for row in rows}
        ys = {str(row.get(mapping["y"])) for row in rows}
        if sp["chart"] == "confusion":
            xs = ys = xs | ys
        column = mapping.get("value", f"{mapping['x']}_count")
        fmt = opts.get("fmt", ".2f" if sp["chart"] == "heatmap" or opts.get("normalize") else ".0f")
        prop = FontProperties(family=cfg.font_family, size=sp["font_sizes"]["tick"])
        labels = [format(value, fmt) for row in rows
                  if isinstance(value := row.get(f"{column}_mean", row.get(column)), (int, float))
                  and math.isfinite(value)]
        cell_width = max((_text_width(renderer, label, prop) for label in labels), default=0) + 4
        minimum_w = max(minimum_w, len(xs) * cell_width)
        minimum_h = max(minimum_h, len(ys) * sp["font_sizes"]["tick"] * 1.6)
    return minimum_w, minimum_h


def _share_facet_axes(records, options):
    """Join ranges explicitly, retaining all panels' data when limits are automatic."""
    ordered = [records[key] for key in sorted(records)
               if records[key]["subplot"]["chart"] not in ("custom", "pie", "donut", "radar")
               and records[key]["axes"].name == "rectilinear"]
    if not ordered:
        return
    for name in ("x", "y"):
        if not options.get(f"share{name}"):
            continue
        scales = {getattr(record["axes"], f"get_{name}scale")() for record in ordered}
        if len(scales) != 1:
            raise ValueError(f"Shared facet {name} axes require identical {name}scale values")
        formats = {record["subplot"]["options"][f"{name}format"] for record in ordered
                   if f"{name}format" in record["subplot"].get("options", {})}
        if len(formats) > 1:
            raise ValueError(f"Shared facet {name} axes require identical {name}format values")
        formatter = next((getattr(record["axes"], f"{name}axis").get_major_formatter()
                          for record in ordered
                          if f"{name}format" in record["subplot"].get("options", {})), None)
        explicit = [tuple(record["subplot"].get("options", {})[f"{name}lim"])
                    for record in ordered if f"{name}lim" in record["subplot"].get("options", {})]
        if explicit and any(limits != explicit[0] for limits in explicit[1:]):
            raise ValueError(f"Shared facet {name} axes require identical explicit {name}lim values")
        ticks = [list(record["subplot"].get("options", {})[f"{name}ticks"])
                 for record in ordered if f"{name}ticks" in record["subplot"].get("options", {})]
        if ticks and any(values != ticks[0] for values in ticks[1:]):
            raise ValueError(f"Shared facet {name} axes require identical {name}ticks values")
        tick_labels = [list(record["subplot"].get("options", {})[f"{name}ticklabels"])
                       for record in ordered if f"{name}ticklabels" in record["subplot"].get("options", {})]
        if tick_labels and any(values != tick_labels[0] for values in tick_labels[1:]):
            raise ValueError(f"Shared facet {name} axes require identical {name}ticklabels values")
        if formats and tick_labels:
            raise ValueError(f"Shared facet {name} axes cannot combine {name}format with {name}ticklabels")
        axes = [record["axes"] for record in ordered]
        bounds = [getattr(ax, f"get_{name}lim")() for ax in axes]
        limits = explicit[0] if explicit else (min(b[0] for b in bounds), max(b[1] for b in bounds))
        # Categorical wrapping runs again during layout. Its per-panel cache
        # must describe the shared labels, including hidden outer tick labels;
        # otherwise a later panel can restore its old names to every sibling.
        raw_ticks = None
        if name == "x" and any(getattr(ax, "_data_visuals_categorical_x", False) for ax in axes):
            if ticks:
                positions = list(ticks[0])
                if tick_labels:
                    labels = list(tick_labels[0])
                else:
                    source = next(record["axes"] for record in ordered
                                  if f"{name}ticks" in record["subplot"].get("options", {}))
                    cached = getattr(source, "_data_visuals_raw_ticks", None)
                    if cached and list(cached[0]) == positions and len(cached[1]) == len(positions):
                        labels = list(cached[1])
                    else:
                        source_formatter = source.xaxis.get_major_formatter()
                        labels = [source_formatter(position, index) for index, position in enumerate(positions)]
            else:
                cached = next((ax._data_visuals_raw_ticks for ax in axes
                               if getattr(ax, "_data_visuals_raw_ticks", (None, []))[1]), None)
                if cached:
                    positions, labels = list(cached[0]), list(cached[1])
                else:
                    positions = list(axes[0].get_xticks())
                    source_formatter = axes[0].xaxis.get_major_formatter()
                    labels = [source_formatter(position, index) for index, position in enumerate(positions)]
            raw_ticks = positions, labels
        for ax in axes[1:]:
            getattr(ax, f"share{name}")(axes[0])
        if formatter is not None:
            getattr(axes[0], f"{name}axis").set_major_formatter(formatter)
        if ticks:
            getattr(axes[0], f"set_{name}ticks")(ticks[0], labels=tick_labels[0] if tick_labels else None)
        if raw_ticks is not None:
            positions, labels = raw_ticks
            axes[0].set_xticks(positions, labels=labels)
            for ax in axes:
                if getattr(ax, "_data_visuals_categorical_x", False):
                    ax._data_visuals_raw_ticks = (list(positions), list(labels))
        getattr(axes[0], f"set_{name}lim")(limits)


def _shared_scatter_legend(cells, visible, color_map, cfg):
    """Match effective glyphs, including defaults, in every participating panel."""
    from data_visuals.renderer.mpl.charts.scatter import scatter_legend_handle
    declared_order = []
    for sp in cells:
        styles = sp.get("options", {}).get("series_styles", {})
        if not isinstance(styles, Mapping):
            raise ValueError("series_styles must map group values to marker styling")
        declared_order.extend(value for value in styles if value in visible and value not in declared_order)
    visible = declared_order + [value for value in visible if value not in declared_order]
    handles = []
    for value in visible:
        variants = []
        signatures = []
        for sp in cells:
            group = sp["data"]["group"]
            if not any(row.get(group) == value for row in sp.get("computed_data", [])):
                continue
            opts = sp.get("options", {})
            styles = opts.get("series_styles", {})
            style = styles.get(value, styles.get(str(value), {}))
            handle = scatter_legend_handle(value, color_map[value], style, cfg)
            handle._paperfig_legend_key = value
            handle.set_alpha(opts.get("opacity", 0.7))
            signatures.append((repr(handle.get_marker()), handle.get_markersize(),
                               to_rgba(handle.get_markerfacecolor()), to_rgba(handle.get_markeredgecolor()),
                               handle.get_markeredgewidth(), handle.get_label(), handle.get_alpha()))
            variants.append(handle)
        if any(signature != signatures[0] for signature in signatures[1:]):
            raise ValueError(f"Shared legend has inconsistent series_styles or opacity for {value!r}")
        handles.append(variants[0])
    return handles


def _place_local_legend(record, renderer, width, height):
    """Outside legends grow measured gutters; corner legends stay in the axes."""
    legend, options, zone = record["local_legend"], record["legend_options"], record["zone"]
    if not legend.width or not legend.height:
        return []
    position, gap = options.get("position", "top"), record["legend_gap"]
    inside = position in ("upper left", "upper right", "lower left", "lower right")
    if inside:
        max_width = zone["w"] - 2 * gap
        if max_width <= 6:
            raise LayoutError("Inside legend gap fills the data rectangle; reduce gap or enlarge the canvas.",
                              axis="width", required_width=width + 2 * gap + 20 - zone["w"],
                              required_height=height)
        if legend.width > max_width + .1:
            legend.reflow(max_width)
        if legend.height + 2 * gap > zone["h"] + .5:
            raise LayoutError("Inside legend does not fit the data rectangle; enlarge the canvas or use an outside position.",
                              axis="height", required_width=width,
                              required_height=height + legend.height + 2 * gap - zone["h"])
    anchor = options.get("anchor")
    if anchor is not None:
        x, y = zone["x"] + anchor[0] * zone["w"], zone["y"] + (1 - anchor[1]) * zone["h"]
        if inside:
            x -= legend.width if position.endswith("right") else 0
            y -= legend.height if position.startswith("lower") else 0
        elif position in ("top", "bottom"):
            x -= legend.width / 2
            y -= legend.height if position == "top" else 0
        else:
            x -= legend.width if position == "left" else 0
            y -= legend.height / 2
    elif inside:
        x = zone["x"] + (zone["w"] - legend.width - gap if position.endswith("right") else gap)
        y = zone["y"] + (zone["h"] - legend.height - gap if position.startswith("lower") else gap)
    elif position == "top":
        x = record["box"]["x"] + (record["box"]["w"] - legend.width) / 2
        content_top = min(zone["y"], height - record["content_bbox"].y1) if record.get("custom") else zone["y"]
        y = content_top - gap - legend.height
    else:
        bboxes = [item.get_tightbbox(renderer, for_layout_only=True) for item in
                  [record["axes"]] + record["secondary_axes"] + record["colorbar_axes"]]
        bboxes.extend(custom_bounds(record.get("custom"), renderer))
        bbox = Bbox.union([box for box in bboxes if box is not None])
        if position == "bottom":
            x = record["box"]["x"] + (record["box"]["w"] - legend.width) / 2
            y = height - bbox.y0 + gap
        elif position == "left":
            x, y = bbox.x0 - gap - legend.width, zone["y"] + (zone["h"] - legend.height) / 2
        elif position == "right":
            x, y = bbox.x1 + gap, zone["y"] + (zone["h"] - legend.height) / 2
        else:
            raise ValueError(f"Unsupported local legend.position: {position!r}")
    if inside and (x < zone["x"] - .5 or y < zone["y"] - .5 or
                   x + legend.width > zone["x"] + zone["w"] + .5 or
                   y + legend.height > zone["y"] + zone["h"] + .5):
        raise ValueError("Inside legend.anchor places the legend outside its axes; move the anchor inward")
    return legend.place(x, y)


def _render(fig, d, cfg, width, height, *, allow_reclaim=True):
    fig._data_visuals_reclaiming = False
    renderer = fig.canvas.get_renderer()
    subplots = [sp for sp in d["subplots"] if sp.get("chart")]
    if not subplots:
        raise ValueError("FigureSpec has no charts to render")
    for sp in subplots:
        validate_axis_options(sp["chart"], sp.get("options", {}))
    facet_options = d.get("facets", {})
    if (facet_options and (facet_options.get("sharex") or facet_options.get("sharey"))
            and any(sp["chart"] in ("pie", "donut", "radar") for sp in subplots)):
        raise ValueError("Pie, donut and radar facets cannot share Cartesian axes; set facets.sharex/sharey=False")
    if facet_options:
        for sp in subplots:
            sp["font_sizes"] = {key: max(8.0, value) for key, value in sp["font_sizes"].items()}
    maps = _colour_maps(d, cfg)
    _continuous_limits(subplots)
    custom_records, primary_axes = prepare_custom_panels(fig, subplots, cfg, maps, width, height)
    group_cells = defaultdict(list)
    panel_legend_options = {}
    for sp in subplots:
        options = _legend_options(d, sp)
        panel_legend_options[sp["row"], sp["col"]] = options
        group = _legend_group(sp, options)
        if (group and options.get("visible", True)
                and options.get("scope", "auto") != "local"):
            group_cells[group].append(sp)
    shared = {column for column, cells in group_cells.items()
              if len(cells) > 1 or any(panel_legend_options[sp["row"], sp["col"]].get("scope") == "shared"
                                       for sp in cells)}
    padding = cfg.canvas_padding if cfg.physical else max(8.0, min(width, height) * 0.018)
    header = padding
    header_artists = []
    title_info = d.get("title", {})
    if title_info.get("text"):
        prop = FontProperties(family=cfg.font_family, size=title_info["font_size"], weight=cfg.title_weight)
        title = fig.text(0.5, 1 - header / height,
                         _wrap(title_info["text"], width - 2 * padding, renderer, prop),
                         ha="center", va="top", fontproperties=prop, color=cfg.text_color)
        header_artists.append(title)
        header += title.get_window_extent(renderer).height + padding * 0.8
    legend_fs = (cfg.font_sizes["legend"] if cfg.physical else
                 d.get("shared_legend", {}).get("font_size", subplots[0]["font_sizes"]["legend"]))
    blocks, shared_position, shared_options = _shared_legend_blocks(
        fig, d, cfg, group_cells, shared, maps, width, padding, legend_fs, custom_records)
    # Side legends are positioned after the shared note has been measured.
    deferred_side = shared_position in ("left", "right")
    if deferred_side:
        footer = left_reserve = right_reserve = 0.0
        shared_artists = []
    else:
        header, footer, left_reserve, right_reserve, shared_artists = _place_shared_blocks(
            blocks, fig, shared_position, shared_options, width, height, padding, header)
        header_artists.extend(shared_artists)
    if facet_options.get("note"):
        note_fs = max(8.0, subplots[0]["font_sizes"]["tick"])
        note_prop = FontProperties(family=cfg.font_family, size=note_fs)
        note = fig.text(0.5, 1 - header / height,
                        _wrap(facet_options["note"], width - 2 * padding, renderer, note_prop),
                        ha="center", va="top", fontproperties=note_prop, color=cfg.ref_line_color)
        header_artists.append(note)
        header += note.get_window_extent(renderer).height + padding * 0.5
    if deferred_side:
        header, footer, left_reserve, right_reserve, shared_artists = _place_shared_blocks(
            blocks, fig, shared_position, shared_options, width, height, padding, header)
        header_artists.extend(shared_artists)
        if blocks:
            occupied = [artist.get_window_extent(renderer) for artist in shared_artists]
            top = height - max(box.y1 for box in occupied)
            bottom = height - min(box.y0 for box in occupied)
            if top < header - .5 or bottom > height - padding + .5:
                raise LayoutError("Side legend does not fit below the title/note; enlarge the canvas or move legend.anchor.",
                                  axis="height", required_width=width,
                                  required_height=height + max(0, header - top) + max(0, bottom - height + padding))
    facet = None
    if facet_options:
        from data_visuals.renderer.mpl.facets import FacetLayout
        facet = FacetLayout(fig, d, cfg, renderer, width, height, padding, header, footer,
                            left_reserve, right_reserve)
    boxes = facet.initial_boxes() if facet else cell_boxes(d, header, padding, footer, left_reserve, right_reserve)
    hint_header = header + footer
    hint_side = left_reserve + right_reserve
    records, requirements = {}, {}
    for sp in subplots:
        key = sp["row"], sp["col"]
        fs, box = sp["font_sizes"], boxes[key]
        custom = custom_records.get(key)
        colorbar = sp["chart"] in ("heatmap", "confusion")
        minimum = _minimum_plot(sp, cfg, renderer)
        # Start with modest gutters and grow from actual measurements. Oversized
        # estimates otherwise persist through the monotone fitting passes.
        initial = {"left": fs["axis_label"] * 1.5, "right": fs["tick"] * 0.8,
                   "top": fs["title"] * 1.6 if sp.get("title") else 2.0,
                   "bottom": fs["axis_label"] * 1.5}
        if (custom and custom["panel"].axes == "off") or sp["chart"] in ("pie", "donut"):
            initial.update(left=2.0, right=2.0, bottom=2.0)
        if facet:
            initial["right"] = 2.0
            if facet_options.get("sharey") and sp["col"] > 0:
                initial["left"] = 2.0
            if facet_options.get("sharex") and sp["row"] < d["grid"]["rows"] - 1:
                initial["bottom"] = 2.0
        zone = _inset(box, initial, minimum, key, width, height, padding, hint_header, hint_side)
        ax = primary_axes[key] if key in primary_axes else create_panel_axes(
            fig, sp, _frac_box(zone, width, height))
        ax.set_position(_frac_box(zone, width, height))
        if colorbar:
            cb = {"x": zone["x"] + zone["w"] + fs["tick"] * 0.6, "y": zone["y"],
                  "w": fs["tick"] * 0.7, "h": zone["h"]}
            sp["_colorbar_box"] = _frac_box(cb, width, height)
            sp["_colorbar_font_size"] = fs["tick"]
        _style_axis(ax, fs, cfg, chart_type=sp["chart"])
        builder = _BUILDERS.get(sp["chart"])
        if builder is None and not custom:
            raise ValueError(f"Unknown chart type for matplotlib backend: {sp['chart']}")
        existing_axes = set(fig.axes)
        handles = (custom["handles"] if custom else
                   builder(ax, sp, cfg, maps.get(sp["data"].get("group", "__measures__"), {}))) or []
        apply_axis_options(ax, sp)
        runtime_minimum = getattr(ax, "_data_visuals_minimum_plot", None)
        if runtime_minimum is not None:
            minimum = tuple(max(old, new) for old, new in zip(minimum, runtime_minimum))
        auxiliaries = [extra for extra in fig.axes if extra not in existing_axes]
        secondary = list(getattr(ax, "_data_visuals_secondary_axes", []))
        cbars = [extra for extra in auxiliaries if extra not in secondary] if colorbar else []
        labels = getattr(ax, "_data_visuals_axis_labels", {})
        y_label = sp["data"].get("y", "")
        if isinstance(y_label, list):
            y_label = " / ".join(y_label)
        cartesian = not custom and sp["chart"] not in ("pie", "donut", "radar")
        if cartesian:
            ax.set_xlabel(labels.get("x", sp["data"].get("x", "")), labelpad=cfg.axis_title_padding)
            ax.set_ylabel(labels.get("y", y_label), labelpad=cfg.axis_title_padding)
        if facet and cartesian:
            if facet_options.get("xlabel") or (facet_options.get("sharex") and sp["row"] < d["grid"]["rows"] - 1):
                ax.set_xlabel("")
            if facet_options.get("ylabel") or (facet_options.get("sharey") and sp["col"] > 0):
                ax.set_ylabel("")
            ax.tick_params(labelbottom=not (facet_options.get("sharex") and sp["row"] < d["grid"]["rows"] - 1),
                           labelleft=not (facet_options.get("sharey") and sp["col"] > 0))
        _style_axis(ax, fs, cfg, chart_type=sp["chart"])
        if sp["chart"] == "radar":
            # Radar rings encode the values even in themes that suppress
            # Cartesian grids. Keep angular metric names at publication size.
            ax.tick_params(axis="both", labelsize=max(8.0, fs["tick"]))
            ax.grid(True, color=cfg.axis_grid_color, alpha=max(.35, cfg.grid_opacity), linewidth=.5)
        if (custom and custom["panel"].axes == "off") or sp["chart"] in ("pie", "donut"):
            ax.set_axis_off()
            ax.grid(False)
        for extra in secondary:
            _style_axis(extra, fs, cfg, secondary=True)
        for extra in cbars:
            extra.tick_params(labelsize=fs["tick"])
            for label in extra.get_yticklabels():
                label.set_fontfamily(cfg.font_family)
        categorical = sp["chart"] in ("bar", "box", "heatmap", "confusion", "line")
        if sp.get("options", {}).get("horizontal"):
            categorical = False
        if sp["chart"] == "line":
            categorical = any(isinstance(row.get(sp["data"].get("x")), str)
                              for row in sp.get("computed_data", []))
        ax._data_visuals_categorical_x = categorical
        _fit_cell_ticks(ax, zone, box, renderer, cfg, fs, key, width, height, padding, hint_header, hint_side)
        group = _legend_group(sp, panel_legend_options[key])
        uses_shared = group in shared and any(cell is sp for cell in group_cells[group])
        group_labels = {str(v) for v in maps.get(group, {})} if uses_shared else set()
        if uses_shared:
            group_labels.update(str(style.get("label")) for style in
                                sp.get("options", {}).get("series_styles", {}).values() if style.get("label"))
            # Return-only custom handles may have no semantic colour group.
            for cell in group_cells[group]:
                other = custom_records.get((cell["row"], cell["col"]))
                if other:
                    group_labels.update(handle.get_label() for handle in other["handles"])
        unique = {}
        for handle in handles:
            label = handle.get_label() if hasattr(handle, "get_label") else ""
            if label and not label.startswith("_") and label not in group_labels:
                unique.setdefault(str(label), handle)
        from data_visuals.renderer.mpl.legends import MeasuredLegend
        legend_options = panel_legend_options[key]
        local_position = legend_options.get("position", "top")
        local_width = (max(20, box["w"] * .32) if local_position in ("left", "right")
                       else box["w"] - 2 * padding)
        local_handles, local_labels = _legend_entries(list(unique.values()), legend_options, sp)
        local_legend = MeasuredLegend(fig, local_handles, local_labels, legend_options, cfg,
                                     default_fontsize=fs["legend"], max_width=local_width,
                                     orientation="vertical" if local_position in ("left", "right") else "horizontal")
        local_h = local_legend.height
        title_prop = FontProperties(family=cfg.font_family, size=fs["title"], weight=cfg.cell_title_weight)
        title_text = _wrap(sp.get("title") or "", box["w"] - 2 * padding,
                           renderer, title_prop)
        local_gap = legend_options.get("gap")
        local_gap = fs["tick"] * cfg.legend_axes_gap if local_gap is None else local_gap
        title_gap = (local_h + local_gap + fs["tick"] * cfg.title_legend_gap
                     if local_h and local_position == "top" else fs["title"] * cfg.subplot_title_gap)
        ax.set_title(title_text, fontproperties=title_prop, color=cfg.text_color,
                     y=1.0, va="bottom", pad=title_gap)
        ax.title.set_y(1.0)
        requirements[key] = initial
        records[key] = {"subplot": sp, "box": box, "axes": ax, "secondary_axes": secondary,
                        "custom": custom,
                        "colorbar_axes": cbars, "local_legend": local_legend, "local_artists": [],
                        "legend_options": legend_options, "legend_gap": local_gap,
                        "local_height": local_h, "minimum": minimum, "facet": facet is not None,
                        "axis_labels": {item: (item.get_xlabel(), item.get_ylabel())
                                        for item in [ax] + secondary}}
    if facet:
        _share_facet_axes(records, facet_options)
    # Only comparable chart families share horizontal decoration widths. A
    # matrix colorbar or polar label must not narrow an unrelated scatter plot.
    alignment_groups = None
    if cfg.physical and not facet:
        alignment_groups = {}
        for key, record in records.items():
            kind = record["subplot"]["chart"]
            family = ("cartesian" if kind in ("bar", "line", "scatter", "box", "histogram")
                      else "matrix" if kind in ("heatmap", "confusion")
                      else ("custom", key) if kind == "custom" else kind)
            alignment_groups[key] = family
    # First converge with monotone gutters. Then attempt one bounded reclamation
    # using final measured text; fall back if locator/wrapping changes expand it.
    saved_requirements = None
    recovery_active = False
    recovery_passes = 0
    reclaimed = False
    for iteration in range(12):
        gutters = align_gutters(
            subplots, requirements,
            vertical_tolerance=min(sp["font_sizes"]["tick"] for sp in subplots) * cfg.vertical_alignment_tolerance,
            alignment_groups=alignment_groups,
        )
        if facet:
            facet.place(records, requirements)
        for key, record in records.items():
            fs = record["subplot"]["font_sizes"]
            zone = (record["zone"] if facet else
                    _inset(record["box"], gutters[key], record["minimum"], key,
                           width, height, padding, hint_header, hint_side))
            if record["custom"]:
                try:
                    zone = position_custom(record["custom"], zone, record["subplot"], cfg, maps, width, height)
                except LayoutError as error:
                    # position_custom reports required content size; the solver
                    # needs the cell size including measured decorations.
                    error.required_width = record["box"]["w"] + max(0, (error.required_width or zone["w"]) - zone["w"])
                    error.required_height = record["box"]["h"] + max(0, (error.required_height or zone["h"]) - zone["h"])
                    raise _canvas_error(error, record["box"], key, width, height, padding, hint_header, hint_side) from None
            elif record["subplot"]["chart"] in ("pie", "donut", "radar"):
                allocation = zone
                zone = position_axes(record["axes"], zone, width, height)
                min_w, min_h = record["minimum"]
                if zone["w"] < min_w - .01 or zone["h"] < min_h - .01:
                    error = LayoutError(
                        "Round panels need at least 60 pt of actual content space; increase canvas size.",
                        axis="width" if allocation["w"] < min_w else "height",
                        required_width=record["box"]["w"] + max(0, min_w-zone["w"]),
                        required_height=record["box"]["h"] + max(0, min_h-zone["h"]), subplot=key)
                    raise _canvas_error(error, record["box"], key, width, height, padding, hint_header, hint_side)
            else:
                record["axes"].set_position(_frac_box(zone, width, height))
            record["zone"] = zone
            rect = _frac_box(zone, width, height)
            _fit_cell_ticks(record["axes"], zone, record["box"], renderer, cfg, fs,
                            key, width, height, padding, hint_header, hint_side)
            # Titles and legends belong to the cell, so asymmetric y-axis
            # gutters must not shift their visual center into a neighbouring cell.
            record["axes"].title.set_x(0.5 if facet else
                (record["box"]["x"] + record["box"]["w"] / 2 - zone["x"]) / zone["w"])
            for extra in record["secondary_axes"]:
                extra.set_position(rect)
            label_prop = FontProperties(family=cfg.font_family, size=fs["axis_label"])
            for item, (xlabel, ylabel) in record["axis_labels"].items():
                minimum_label = fs["axis_label"] * (2 if cfg.physical else 8)
                item.set_xlabel(_wrap(xlabel, max(zone["w"], minimum_label), renderer, label_prop))
                item.set_ylabel(_wrap(ylabel, max(zone["h"], minimum_label), renderer, label_prop))
            for extra in record["colorbar_axes"]:
                cb = {"x": zone["x"] + zone["w"] + fs["tick"] * 0.6, "y": zone["y"],
                      "w": fs["tick"] * 0.7, "h": zone["h"]}
                extra.set_position(_frac_box(cb, width, height))
            if record["custom"] or record["subplot"]["chart"] == "radar":
                place_custom_title(record, renderer, cfg, height)
            record["local_artists"] = _place_local_legend(record, renderer, width, height)
        fig.canvas.draw()
        renderer, changed = fig.canvas.get_renderer(), False
        for key, record in records.items():
            zone, fs = record["zone"], record["subplot"]["font_sizes"]
            bboxes = [item.get_tightbbox(renderer, for_layout_only=True) for item in
                      [record["axes"]] + record["secondary_axes"] + record["colorbar_axes"]]
            bboxes.extend(custom_bounds(record["custom"], renderer))
            bboxes.extend(artist.get_window_extent(renderer) for artist in record["local_artists"])
            bbox = Bbox.union([bb for bb in bboxes if bb is not None])
            pad = max(2.0, fs["tick"] * cfg.panel_padding)
            measured = {"left": max(0, zone["x"] - bbox.x0) + pad,
                        "right": max(0, bbox.x1 - zone["x"] - zone["w"]) + pad,
                        "top": max(0, bbox.y1 - (height - zone["y"])) + pad,
                        "bottom": max(0, height - zone["y"] - zone["h"] - bbox.y0) + pad}
            record["measured_gutters"] = measured
            record["gutters"] = gutters[key]
            for side, value in measured.items():
                if value > requirements[key][side] + 0.2:
                    requirements[key][side], changed = value, True
            full_boxes = [item.get_tightbbox(renderer) for item in
                          [record["axes"]] + record["secondary_axes"] + record["colorbar_axes"]]
            full_boxes.extend(custom_bounds(record["custom"], renderer))
            full_boxes.extend(artist.get_window_extent(renderer) for artist in record["local_artists"])
            record["decoration_bbox"] = tuple(Bbox.union([bb for bb in full_boxes if bb is not None]).bounds)
        if not changed:
            if (allow_reclaim and cfg.physical and not facet
                    and saved_requirements is None and iteration <= 8):
                compact = {key: {side: min(value, record["measured_gutters"][side] + 0.3)
                                 for side, value in requirements[key].items()}
                           for key, record in records.items()}
                if any(requirements[key][side] - compact[key][side] > 0.75
                       for key in compact for side in compact[key]):
                    saved_requirements = deepcopy(requirements)
                    requirements = compact
                    recovery_active = True
                    fig._data_visuals_reclaiming = True
                    continue
            reclaimed = recovery_active
            break
        if recovery_active:
            recovery_passes += 1
            if recovery_passes >= 2:
                requirements = saved_requirements
                recovery_active = False
                fig._data_visuals_reclaiming = False
    else:
        fig._data_visuals_reclaiming = saved_requirements is not None
        raise LayoutError(
            "Axis labels did not fit after measurement; increase canvas width or height.",
            axis="height", required_width=width, required_height=height * 1.1,
        )
    if facet:
        header_artists.extend(facet.decorate(records))
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    # Point labels use the final transform, after the measured layout converges.
    for record in records.values():
        if getattr(record["axes"], "_data_visuals_annotations", None):
            from data_visuals.renderer.mpl.annotations import place_point_labels
            obstacles = ([artist.get_window_extent(fig.canvas.get_renderer())
                          for artist in record["local_artists"]]
                         if record["legend_options"].get("position") in
                         ("upper left", "upper right", "lower left", "lower right") else [])
            record["point_labels"] = place_point_labels(record["axes"], cfg, obstacles=obstacles)
    fig.canvas.draw()
    diagnostics = {"canvas": (width, height), "header_height": header, "footer_height": footer,
                   "left_legend_width": left_reserve, "right_legend_width": right_reserve,
                   "shared_legends": shared_artists, "iterations": iteration + 1,
                   "color_maps": maps, "cells": {}, "header_artists": header_artists,
                   "gutter_reclaimed": reclaimed}
    for key, record in records.items():
        x, y, w, h = record["decoration_bbox"]
        box = record["box"]
        if (x < box["x"] - 1 or x + w > box["x"] + box["w"] + 1 or
                y < height - box["y"] - box["h"] - 1 or y + h > height - box["y"] + 1):
            overflow_w = max(0, box["x"] - x, x + w - box["x"] - box["w"])
            overflow_h = max(0, height - box["y"] - box["h"] - y,
                             y + h - height + box["y"])
            error = LayoutError(
                f"Subplot {key} decorations exceed its cell; increase canvas width or height.",
                axis="width" if overflow_w > 1 else "height",
                required_width=box["w"] + 2 * overflow_w,
                required_height=box["h"] + 2 * overflow_h, subplot=key,
            )
            raise _canvas_error(error, box, key, width, height, padding, hint_header, hint_side)
        diagnostics["cells"][key] = {"cell": record["box"], "data_zone": record["zone"],
                                    "minimum": record["minimum"],
                                    "gutters": dict(record["gutters"]),
                                    "measured_gutters": dict(record["measured_gutters"]),
                                    "alignment_group": alignment_groups.get(key) if alignment_groups else None,
                                    "decoration_bbox": record["decoration_bbox"], "axes": record["axes"],
                                    "secondary_axes": record["secondary_axes"],
                                    "colorbar_axes": record["colorbar_axes"], "legends": record["local_artists"],
                                    "custom_artists": list(record["custom"]["result"].artists) if record["custom"] else [],
                                    "point_labels": record.get("point_labels", {"texts": [], "boxes": []})}
    for artist in header_artists:
        bbox = artist.get_window_extent(renderer)
        overflow_w = max(0, -bbox.x0, bbox.x1 - width)
        overflow_h = max(0, -bbox.y0, bbox.y1 - height)
        if overflow_w > 1 or overflow_h > 1:
            raise LayoutError(
                "Figure title or shared legend exceeds the canvas; increase canvas width or height.",
                axis="width" if overflow_w > 1 else "height",
                required_width=width + 2 * overflow_w,
                required_height=height + 2 * overflow_h,
            )
    fig._data_visuals_layout = diagnostics
    fig._data_visuals_reclaiming = False
    return fig
