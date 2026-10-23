"""Matplotlib lines with numeric/category axes and shared series colours."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from .helpers import (axis_labels, frame, grouped, ordered, secondary_axis,
                      series_color, value_column)


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
    for group_index, (key, sub) in enumerate(grouped(df, g_col)):
        sub = sub.sort_values(x_col, kind="stable")
        for value_index, name in enumerate(ys):
            series_key = key if key is not None else (name if len(ys) > 1 or mapping.get("y2") else None)
            color = series_color(series_key, group_index if key is not None else value_index,
                                 cfg, color_map)
            x = sub[x_col].to_numpy() if numeric else sub[x_col].map(xpos).to_numpy()
            values = sub[value_column(sub, name, "")].to_numpy(dtype=float)
            px, py = x, values
            if opts.get("smooth") and pd.api.types.is_numeric_dtype(sub[x_col]):
                valid = np.isfinite(x) & np.isfinite(values)
                if valid.sum() > 2 and len(np.unique(x[valid])) == valid.sum():
                    from scipy.interpolate import PchipInterpolator
                    px = np.linspace(x[valid].min(), x[valid].max(), 200)
                    py = PchipInterpolator(x[valid], values[valid])(px)
            line, = ax.plot(px, py, marker="o" if opts.get("markers", True) and px is x else None,
                            color=color, label=str(series_key) if series_key is not None else "_default",
                            linewidth=cfg.line_stroke_width, markersize=np.sqrt(cfg.marker_size),
                            drawstyle="steps-mid" if opts.get("step") else "default")
            if opts.get("markers", True) and px is not x:
                ax.plot(x, values, linestyle="none", marker="o", color=color,
                        markersize=np.sqrt(cfg.marker_size))
            if opts.get("area"):
                ax.fill_between(px, py, color=color, alpha=0.2,
                                step="mid" if opts.get("step") else None)
            if series_key is not None:
                handles.append(line)
    if not numeric:
        ax.set_xticks(range(len(categories)), labels=categories)
    axis_labels(ax, sp)
    if mapping.get("y2"):
        has_groups = bool(g_col and g_col in df.columns)
        twin = secondary_axis(ax, sp, cfg, mapping["y2"],
                              color=cfg.text_color if has_groups else cfg.y2_color)
        y2_handle = None
        for index, (key, sub) in enumerate(grouped(df, g_col)):
            sub = sub.sort_values(x_col, kind="stable")
            x = sub[x_col].to_numpy() if numeric else sub[x_col].map(xpos).to_numpy()
            color = series_color(key, index, cfg, color_map) if has_groups else cfg.y2_color
            y2_handle, = twin.plot(x, sub[value_column(sub, mapping["y2"], "")], marker="D",
                                  color=color, linestyle=cfg.y2_dash,
                                  linewidth=cfg.line_stroke_width, markersize=np.sqrt(cfg.marker_size),
                                  label="_secondary" if has_groups else str(mapping["y2"]))
        if has_groups:
            # Colour explains models; this separate neutral key explains the
            # secondary metric's dash and marker without duplicating models.
            handles.append(Line2D([], [], color=cfg.text_color, linestyle=cfg.y2_dash,
                                  marker="D", linewidth=cfg.line_stroke_width,
                                  markersize=np.sqrt(cfg.marker_size), label=str(mapping["y2"])))
        elif y2_handle is not None:
            handles.append(y2_handle)
    return handles
