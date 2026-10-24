"""Matplotlib grouped, stacked and horizontal bars."""

from __future__ import annotations

import numpy as np
from matplotlib.ticker import PercentFormatter

from .helpers import (axis_labels, frame, grouped, ordered, reference_lines,
                      secondary_axis, series_color, series_style, value_column)


def _draw_bar(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y = mapping["x"], mapping["y"]
    ys = [y] if isinstance(y, str) else list(y)
    g_col = mapping.get("group")
    horizontal, stacked = opts.get("horizontal", False), opts.get("stacked", False)
    cases = ordered(df[x_col])
    positions = np.arange(len(cases), dtype=float)
    if len(ys) > 1:
        series = [(name, df, name) for name in ys]
    else:
        series = [(key, sub, ys[0]) for key, sub in grouped(df, g_col, opts.get("series_order"))]
    count = len(series)
    width = cfg.bar_width_ratio / (1 if stacked else count)
    positive, negative = np.zeros(len(cases)), np.zeros(len(cases))
    handles = []
    for index, (key, sub, name) in enumerate(series):
        column = value_column(sub, name)
        sub = sub.groupby(x_col, sort=False).mean(numeric_only=True).reindex(cases)
        values = sub[column].to_numpy(dtype=float)
        locs = positions if stacked else positions + (index - (count - 1) / 2) * width
        bottom = np.where(values >= 0, positive, negative) if stacked else np.zeros(len(cases))
        errors = None
        if mapping.get("error"):
            error = mapping["error"]
            # Mapping error to the measured value requests its computed spread.
            # In particular, never mistake score_mean for a score error bar.
            if error in ys:
                candidates = (f"{name}_std", f"{name}_sem")
            else:
                candidates = (error, f"{error}_mean", f"{error}_std", f"{name}_std", f"{name}_sem")
            for candidate in candidates:
                if candidate in sub.columns:
                    errors = np.nan_to_num(np.abs(sub[candidate].to_numpy(dtype=float)))
                    break
        color = series_color(key, index, cfg, color_map, opts)
        style = series_style(key, opts, measure=len(ys) > 1)
        bar_fn = ax.barh if horizontal else ax.bar
        kwargs = {"height" if horizontal else "width": width,
                  "left" if horizontal else "bottom": bottom,
                  "xerr" if horizontal else "yerr": errors}
        bars = bar_fn(locs, values, color=color,
                      label=style.get("label", str(key) if key is not None else "_default"),
                      edgecolor=cfg.bar_stroke, linewidth=cfg.bar_stroke_width,
                      error_kw={"ecolor": cfg.error_bar_color, "elinewidth": cfg.error_bar_width,
                                "capsize": cfg.axis_tick_size}, **kwargs)
        if key is not None:
            bars._figcompose_legend_key = key
            handles.append(bars)
        if opts.get("show_value"):
            from data_visuals.core.identity import numeric_format_function
            formatter = numeric_format_function(opts.get("value_format", ".2f"), "value_format")
            labels = [formatter(v) if np.isfinite(v) else ""
                      for v in values]
            ax.bar_label(bars, labels=labels, label_type="center" if stacked else "edge",
                         padding=cfg.axis_label_padding if not stacked else 0,
                         fontsize=sp["font_sizes"]["tick"], fontfamily=cfg.font_family,
                         color=cfg.text_color)
        if stacked:
            positive += np.where(values >= 0, np.nan_to_num(values), 0)
            negative += np.where(values < 0, np.nan_to_num(values), 0)
    if horizontal:
        ax.set_yticks(positions, labels=cases)
        axis_labels(ax, sp, x=", ".join(ys), y=x_col)
    else:
        ax.set_xticks(positions, labels=cases)
        axis_labels(ax, sp)
    if stacked == "percent":
        (ax.xaxis if horizontal else ax.yaxis).set_major_formatter(PercentFormatter(1))
    mean = None
    if opts.get("mean_line"):
        means = sp.get("derived_data", {}).get("overall_mean", {})
        mean_values = [means.get(value_column(df, name), means.get(name)) for name in ys]
        mean_values = [v for v in mean_values if v is not None]
        values = df[[value_column(df, name) for name in ys]].to_numpy(dtype=float)
        if mean_values:
            mean = np.mean(mean_values)
        elif np.isfinite(values).any():
            mean = np.nanmean(values)
    handles += reference_lines(ax, sp, cfg, mean=mean, horizontal=horizontal)
    if mapping.get("y2"):
        y2_col = value_column(df, mapping["y2"])
        twin = secondary_axis(ax, sp, cfg, mapping["y2"], horizontal)
        for index, (_, sub) in enumerate(grouped(df, g_col, opts.get("series_order"))):
            secondary = sub.groupby(x_col, sort=False)[y2_col].mean().reindex(cases)
            locs = positions if stacked else positions + (index - (count - 1) / 2) * width
            if horizontal:
                twin.barh(locs, secondary, height=width * 0.5, color=cfg.y2_color, alpha=0.3)
            else:
                twin.bar(locs, secondary, width=width * 0.5, color=cfg.y2_color, alpha=0.3)
    return handles
