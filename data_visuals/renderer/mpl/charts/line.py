"""Matplotlib lines with numeric/category axes and shared series colours."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from .helpers import (axis_labels, frame, grouped, ordered, secondary_axis,
                      series_color, series_style, line_legend_handle, value_column)


def _draw_line(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y = mapping["x"], mapping["y"]
    ys = [y] if isinstance(y, str) else list(y)
    categories = ordered(df[x_col])
    numeric = pd.api.types.is_numeric_dtype(df[x_col]) or pd.api.types.is_datetime64_any_dtype(df[x_col])
    xpos = {key: index for index, key in enumerate(categories)}
    g_col = mapping.get("group")
    handles = []
    for group_index, (key, sub) in enumerate(grouped(df, g_col, opts.get("series_order"))):
        sub = sub.sort_values(x_col, kind="stable")
        for value_index, name in enumerate(ys):
            series_key = key if key is not None else (name if len(ys) > 1 or mapping.get("y2") else None)
            color = series_color(series_key, group_index if key is not None else value_index,
                                 cfg, color_map)
            glyph = line_legend_handle(series_key, color, opts, cfg, measure=key is None)
            style = series_style(series_key, opts)
            color = glyph.get_color()
            x = sub[x_col].to_numpy() if numeric else sub[x_col].map(xpos).to_numpy()
            values = sub[value_column(sub, name, "")].to_numpy(dtype=float)
            px, py = x, values
            if opts.get("smooth") and pd.api.types.is_numeric_dtype(sub[x_col]):
                valid = np.isfinite(x) & np.isfinite(values)
                if valid.sum() > 2 and len(np.unique(x[valid])) == valid.sum():
                    from scipy.interpolate import PchipInterpolator
                    px = np.linspace(x[valid].min(), x[valid].max(), 200)
                    py = PchipInterpolator(x[valid], values[valid])(px)
            line, = ax.plot(px, py, marker=glyph.get_marker() if px is x else None,
                            color=color, label=glyph.get_label(),
                            linestyle=style.get("linestyle", "-"), linewidth=glyph.get_linewidth(),
                            markersize=glyph.get_markersize(), markerfacecolor=glyph.get_markerfacecolor(),
                            markeredgecolor=glyph.get_markeredgecolor(), zorder=style.get("zorder", 2),
                            drawstyle="steps-mid" if opts.get("step") else "default")
            if opts.get("markers", True) and px is not x:
                ax.plot(x, values, linestyle="none", marker=glyph.get_marker(), color=color,
                        markersize=glyph.get_markersize(), markerfacecolor=glyph.get_markerfacecolor(),
                        markeredgecolor=glyph.get_markeredgecolor(), zorder=style.get("zorder", 2))
            if opts.get("area"):
                ax.fill_between(px, py, color=color, alpha=0.2,
                                step="mid" if opts.get("step") else None)
            if series_key is not None:
                # Preserve the native artist return contract for ordinary
                # curves. A smoothed curve needs a legend proxy because its
                # markers are drawn separately at the original observations.
                handle = line if px is x else glyph
                handle._figcompose_legend_key = series_key
                handles.append(handle)
    if not numeric:
        ax.set_xticks(range(len(categories)), labels=categories)
    axis_labels(ax, sp)
    if mapping.get("y2"):
        has_groups = bool(g_col and g_col in df.columns)
        y2_label = series_style(mapping["y2"], opts, measure=True).get("label", str(mapping["y2"]))
        twin = secondary_axis(ax, sp, cfg, mapping["y2"],
                              color=cfg.text_color if has_groups else cfg.y2_color)
        y2_handle = None
        for index, (key, sub) in enumerate(grouped(df, g_col, opts.get("series_order"))):
            sub = sub.sort_values(x_col, kind="stable")
            x = sub[x_col].to_numpy() if numeric else sub[x_col].map(xpos).to_numpy()
            color = series_color(key, index, cfg, color_map) if has_groups else cfg.y2_color
            if has_groups:
                color = series_style(key, opts).get("color", color)
            y2_handle, = twin.plot(x, sub[value_column(sub, mapping["y2"], "")], marker="D",
                                  color=color, linestyle=cfg.y2_dash,
                                  linewidth=cfg.line_stroke_width, markersize=np.sqrt(cfg.marker_size),
                                  label="_secondary" if has_groups else y2_label)
        if has_groups:
            # Colour explains models; this separate neutral key explains the
            # secondary metric's dash and marker without duplicating models.
            metric_handle = Line2D([], [], color=cfg.text_color, linestyle=cfg.y2_dash,
                                   marker="D", linewidth=cfg.line_stroke_width,
                                   markersize=np.sqrt(cfg.marker_size), label=y2_label)
            metric_handle._figcompose_legend_key = mapping["y2"]
            handles.append(metric_handle)
        elif y2_handle is not None:
            y2_handle._figcompose_legend_key = mapping["y2"]
            handles.append(y2_handle)
    return handles
