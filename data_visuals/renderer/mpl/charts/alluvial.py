"""Continuous ribbons and marginal node cards for complete weighted paths."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.path import Path
from matplotlib.patches import Patch, PathPatch, Rectangle

from data_visuals.compute.alluvial import alluvial_geometry
from .helpers import frame, series_color, series_style


def flow_path(x0, x1, start, end):
    low0, high0 = start
    low1, high1 = end
    middle = (x0 + x1) / 2
    vertices = [(x0, high0), (middle, high0), (middle, high1), (x1, high1),
                (x1, low1), (middle, low1), (middle, low0), (x0, low0), (x0, high0)]
    return Path(vertices, [Path.MOVETO, *([Path.CURVE4] * 3), Path.LINETO,
                           *([Path.CURVE4] * 3), Path.CLOSEPOLY])


def _draw_alluvial(ax, sp, cfg, color_map):
    paths = frame(sp.get("computed_data", []))
    if paths.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    payload = sp.get("derived_data", {}).get("alluvial")
    if not payload:
        raise ValueError("[alluvial] Compute layer must supply stage marginals.")
    stages, value = mapping["stages"], mapping["value"]
    categories, totals, nodes, slots = alluvial_geometry(paths, mapping, payload)
    total = payload["total_weight"]
    def amount(weight):
        if "value_format" in opts:
            from data_visuals.core.identity import numeric_format_function
            return numeric_format_function(opts["value_format"], "value_format")(weight)
        return f"{weight:,.0f}" if float(weight).is_integer() else f"{weight:g}"
    xs = np.linspace(.055, .945, len(stages))
    width = min(.080, .27 / len(stages))
    aliases = opts.get("category_aliases", {})
    canonical = lambda key: aliases.get(key, aliases.get(str(key), key))
    colors = {key: series_color(canonical(key), index, cfg, color_map or {}, opts)
              for index, key in enumerate(categories[stages[0]])}
    titles = opts.get("stage_titles") or [stage.replace("_", " ").upper() for stage in stages]
    # The same physical role scales serve publication and showcase themes.
    body = max(8., sp["font_sizes"]["axis_label"] * 10 / 9)
    texts = []
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.set_axis_off()

    def label(x, y, content, size=1, **kwargs):
        artist = ax.text(x, y, str(content), ha=kwargs.pop("ha", "center"), va="center",
                         fontsize=max(8, body * size), fontfamily=cfg.font_family,
                         color=kwargs.pop("color", cfg.text_color), clip_on=False, **kwargs)
        texts.append(artist)
        return artist

    for left in range(len(stages) - 1):
        for index in paths.sort_values(value, ascending=False, kind="stable").index:
            row = paths.loc[index]
            patch = PathPatch(flow_path(xs[left] + width / 2, xs[left + 1] - width / 2,
                                        slots[stages[left], index], slots[stages[left + 1], index]),
                              facecolor=to_rgba(colors[row[stages[0]]], .90),
                              edgecolor=(1, 1, 1, .75), linewidth=.24, zorder=2)
            patch.set_gid(f"route:{index}:{left}")
            ax.add_patch(patch)
    node_labels, headers = [], []
    for number, (x, stage, title) in enumerate(zip(xs, stages, titles), 1):
        header_x = .022 if number == 1 else (.978 if number == len(stages) else x)
        align = "left" if number == 1 else ("right" if number == len(stages) else "center")
        headers.append(label(header_x, .973, f"{number:02d}  {title}", 1.25, fontweight="bold", ha=align))
        label(x, .929, f"{amount(total)} {opts.get('value_label', 'weight')}", color=cfg.muted_text_color)
        for category in categories[stage]:
            low, high = nodes[stage, category]
            card = Rectangle((x - width / 2, low), width, high - low,
                             facecolor=cfg.background, edgecolor="#DAE2EA", linewidth=.65, zorder=4)
            card.set_gid(f"node:{stage}:{category}")
            ax.add_patch(card)
            stripe_width = width * .105
            for index, row in paths[paths[stage] == category].iterrows():
                start, stop = slots[stage, index]
                for side, edge in enumerate((x - width / 2 + .001, x + width / 2 - stripe_width - .001)):
                    stripe = Rectangle((edge, start), stripe_width, stop - start,
                                       facecolor=colors[row[stages[0]]], edgecolor="none", zorder=5)
                    stripe.set_gid(f"origin-slot:{stage}:{index}:{side}")
                    ax.add_patch(stripe)
            middle = (low + high) / 2
            count = totals[stage][category]
            display = (series_style(canonical(category), opts).get("label", canonical(category))
                       if stage == stages[0] else category)
            group = (label(x, middle + .027, display, 1.1, fontweight="bold", zorder=6),
                     label(x, middle - .005, amount(count), 1.25, fontweight="bold", zorder=6),
                     label(x, middle - .035, f"{count / total:.1%}", .95, color=cfg.muted_text_color, zorder=6))
            node_labels.append((card, group))
    if opts.get("note"):
        label(.5, .042, opts["note"], color=cfg.muted_text_color)
    ax._data_visuals_bounds_artists = texts
    ax._data_visuals_minimum_plot = (max(180., 108. * len(stages)), 420.)

    def layout():
        renderer = ax.figure.canvas.get_renderer()
        from data_visuals.layout.placement import LayoutError
        header_boxes = [artist.get_window_extent(renderer) for artist in headers]
        gap_px = ax.figure.dpi / 72 * 2
        for first, second in zip(header_boxes, header_boxes[1:]):
            if first.x1 + gap_px > second.x0:
                overlap = first.x1 + gap_px - second.x0
                raise LayoutError("[alluvial] Stage titles overlap; shorten stage_titles or enlarge the canvas width.",
                                  axis="width", required_width=ax.figure.get_figwidth() * 72 + overlap * 72 / ax.figure.dpi * len(stages))
        for card, group in node_labels:
            box = card.get_window_extent(renderer)
            boxes = [artist.get_window_extent(renderer) for artist in group]
            if any(item.x0 < box.x0 or item.x1 > box.x1 for item in boxes):
                required = max(item.width for item in boxes) / max(box.width, 1e-12)
                raise LayoutError("[alluvial] Node labels need wider cards; enlarge the canvas width or shorten category labels.",
                                  axis="width", required_width=ax.figure.get_figwidth() * 72 * required)
            if any(item.y0 < box.y0 or item.y1 > box.y1 for item in boxes):
                gap = 2 * ax.figure.dpi / 72
                needed = sum(item.height for item in boxes) + 2 * gap
                if needed > box.height:
                    raise LayoutError("[alluvial] Node labels need taller cards; enlarge canvas height or combine small categories.",
                                      axis="height", required_height=ax.figure.get_figheight() * 72 * needed / max(box.height, 1e-12))
                cursor = (box.y0 + box.y1 + needed) / 2
                for artist, item in zip(group, boxes):
                    point = ax.transData.inverted().transform(((box.x0 + box.x1) / 2, cursor - item.height / 2))
                    artist.set_position(point)
                    cursor -= item.height + gap

    ax._figcompose_layout_callback = layout
    handles = []
    for category in categories[stages[0]]:
        key = canonical(category)
        handle = Patch(facecolor=to_rgba(colors[category], .90), edgecolor="none",
                       label=series_style(key, opts).get("label", str(key)))
        handle._figcompose_legend_key = key
        handles.append(handle)
    return handles
