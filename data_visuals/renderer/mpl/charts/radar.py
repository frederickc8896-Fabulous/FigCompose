"""Polar radar renderer; no implicit rescaling across metric axes."""

from __future__ import annotations

import textwrap

import numpy as np
from matplotlib.ticker import MaxNLocator

from .helpers import frame, grouped, ordered, series_color, value_column


def _draw_radar(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    if ax.name != "polar":
        raise ValueError("Radar requires a polar Matplotlib axes.")
    mapping, opts = sp["data"], sp.get("options", {})
    x, y, group = mapping["x"], mapping["y"], mapping.get("group")
    categories = opts.get("order") or ordered(df[x])
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False)
    closed_angles = np.r_[angles, angles[0]]
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    handles, maximum = [], 0.0
    for index, (key, sub) in enumerate(grouped(df, group)):
        if set(sub[x]) != set(categories):
            raise ValueError("Radar groups must contain all metric axes; missing values are not filled with zero.")
        values = sub.set_index(x).loc[categories, value_column(sub, y)].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Radar scores must be finite and nonnegative.")
        color = series_color(key, index, cfg, color_map or {})
        closed = np.r_[values, values[0]]
        line, = ax.plot(closed_angles, closed, color=color,
                        linewidth=cfg.line_stroke_width,
                        marker="o" if opts.get("markers", True) else None,
                        markersize=min(5.0, np.sqrt(cfg.marker_size)),
                        label=str(key) if key is not None else "_default")
        alpha = float(opts.get("fill_alpha", 0.10))
        if alpha:
            ax.fill(closed_angles, closed, color=color, alpha=alpha, linewidth=0)
        if key is not None:
            handles.append(line)
        maximum = max(maximum, float(values.max()))
    ax.set_xticks(angles, labels=[textwrap.fill(str(category), width=int(opts.get("label_width", 18)),
                                              break_long_words=False, break_on_hyphens=False)
                                for category in categories])
    ax.set_ylim(*(opts.get("ylim") or (0.0, maximum * 1.08 if maximum > 0 else 1.0)))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4, min_n_ticks=3))
    ax.set_rlabel_position(22.5)
    label_size = max(8.0, sp["font_sizes"]["tick"])
    ax.tick_params(axis="x", pad=5, labelsize=label_size)
    ax.tick_params(axis="y", labelsize=label_size)
    for text in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        text.set_fontfamily(cfg.font_family)
        text.set_color(cfg.text_color)
    for angle, text in zip(angles, ax.get_xticklabels()):
        # Polar ticks default to centered text; long side labels then extend
        # into the circle. Anchor every label toward the outside, including
        # diagonal axes, using the actual rendered orientation.
        rendered_angle = angle * ax.get_theta_direction() + ax.get_theta_offset()
        horizontal, vertical = np.cos(rendered_angle), np.sin(rendered_angle)
        text.set_ha("left" if horizontal > 1e-8 else "right" if horizontal < -1e-8 else "center")
        text.set_va("bottom" if vertical > 1e-8 else "top" if vertical < -1e-8 else "center")
    ax._data_visuals_bounds_artists = list(ax.get_xticklabels())
    return handles
