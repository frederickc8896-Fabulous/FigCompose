"""Draw box summaries from the compute layer using matplotlib primitives."""

from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.patches import Patch, Polygon, Rectangle

from .helpers import axis_labels, frame, ordered, reference_lines, series_color


def _draw_box(ax, sp, cfg, color_map):
    derived = sp.get("derived_data", {})
    summary = frame(derived.get("box_summary", []))
    if summary.empty:
        return []
    outliers = frame(derived.get("box_outliers", []))
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y_col, g_col = mapping["x"], mapping["y"], mapping.get("group")
    horizontal = opts.get("horizontal", False)
    categories = ordered(summary[x_col])
    cat_pos = {value: index for index, value in enumerate(categories)}
    groups = ordered(summary[g_col]) if g_col and g_col in summary.columns else [None]
    offsets = {value: (index - (len(groups) - 1) / 2) * 0.6 / len(groups)
               for index, value in enumerate(groups)}
    width = 0.6 / len(groups)
    handles = {}
    raw = frame(sp.get("computed_data", []))

    def segment(x1, y1, x2, y2, width=cfg.box_stroke_width):
        if horizontal:
            ax.plot([y1, y2], [x1, x2], color=cfg.box_stroke, linewidth=width)
        else:
            ax.plot([x1, x2], [y1, y2], color=cfg.box_stroke, linewidth=width)

    for _, row in summary.iterrows():
        group = row[g_col] if g_col and g_col in summary.columns else None
        center = cat_pos[row[x_col]] + offsets.get(group, 0)
        color = series_color(group, groups.index(group), cfg, color_map)
        q1, q3, median = row["Q1"], row["Q3"], row["median"]
        lower, upper = row.get("min", row.get("lower")), row.get("max", row.get("upper"))
        low_x, high_x = center - width / 2, center + width / 2
        if opts.get("notch"):
            count = row.get("count", 0)
            if not count and not raw.empty and x_col in raw and y_col in raw:
                values = raw[raw[x_col] == row[x_col]]
                if group is not None:
                    values = values[values[g_col] == group]
                count = values[y_col].count()
            if count:
                delta = 1.57 * (q3 - q1) / np.sqrt(count)
                nl, nu = median - delta, median + delta
                points = [(low_x, q1), (high_x, q1), (high_x, nl),
                          (center + width / 4, median), (high_x, nu), (high_x, q3),
                          (low_x, q3), (low_x, nu), (center - width / 4, median), (low_x, nl)]
                if horizontal:
                    points = [(y, x) for x, y in points]
                patch = Polygon(points, facecolor=to_rgba(color, 0.35),
                                edgecolor=cfg.box_stroke, linewidth=cfg.box_stroke_width)
            else:
                raise ValueError("Notched boxes require sample counts or raw computed data")
        else:
            xy = (q1, low_x) if horizontal else (low_x, q1)
            patch = Rectangle(xy, q3 - q1 if horizontal else width,
                              width if horizontal else q3 - q1,
                              facecolor=to_rgba(color, 0.35), edgecolor=cfg.box_stroke,
                              linewidth=cfg.box_stroke_width)
        ax.add_patch(patch)
        segment(center, lower, center, q1)
        segment(center, q3, center, upper)
        segment(center - width / 4, lower, center + width / 4, lower)
        segment(center - width / 4, upper, center + width / 4, upper)
        median_half = width / 4 if opts.get("notch") else width / 2
        segment(center - median_half, median, center + median_half, median,
                width=cfg.box_median_stroke_width)
        if group is not None and group not in handles:
            handles[group] = Patch(facecolor=to_rgba(color, 0.35), edgecolor=cfg.box_stroke,
                                   label=str(group))
    if opts.get("show_outliers", True) and not outliers.empty:
        for _, row in outliers.iterrows():
            if row[x_col] not in cat_pos:
                continue
            group = row[g_col] if g_col and g_col in outliers.columns else None
            center = cat_pos[row[x_col]] + offsets.get(group, 0)
            color = series_color(group, groups.index(group), cfg, color_map)
            x, y = (row[y_col], center) if horizontal else (center, row[y_col])
            ax.scatter(x, y, color=color, edgecolors="none", s=cfg.scatter_point_size,
                       alpha=0.8, zorder=5)
    if horizontal:
        ax.set_yticks(range(len(categories)), labels=categories)
        axis_labels(ax, sp, x=y_col, y=x_col)
    else:
        ax.set_xticks(range(len(categories)), labels=categories)
        axis_labels(ax, sp)
    ax.autoscale_view()
    mean = derived.get("overall_mean", {}).get(y_col)
    return [*handles.values(), *reference_lines(ax, sp, cfg, mean=mean, horizontal=horizontal)]
