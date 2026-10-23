"""Grouped histogram/KDE rendering using one common bin range."""

from __future__ import annotations

import numpy as np

from .helpers import axis_labels, frame, grouped, series_color


def _draw_histogram(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, g_col = mapping["x"], mapping.get("group")
    cumulative, use_density = opts.get("cumulative", False), opts.get("density", False)
    values = np.asarray(df[x_col].dropna(), dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return []
    bins = np.histogram_bin_edges(values, bins=opts.get("bins", 20))
    density = frame(sp.get("derived_data", {}).get("density_data", [])) if use_density else frame([])
    handles = []
    for index, (key, sub) in enumerate(grouped(df, g_col)):
        color = series_color(key, index, cfg, color_map)
        curve = density
        if not density.empty and key is not None and g_col in density:
            curve = density[density[g_col] == key]
        if use_density and not curve.empty:
            curve = curve.sort_values(x_col, kind="stable")
            x, y = curve[x_col].to_numpy(dtype=float), curve["density"].to_numpy(dtype=float)
            if cumulative:
                y = np.r_[0.0, np.cumsum((y[1:] + y[:-1]) * np.diff(x) / 2)]
                if y[-1] > 0:
                    y = y / y[-1]
            ax.fill_between(x, y, alpha=0.2, color=color)
            artist, = ax.plot(x, y, linewidth=cfg.line_stroke_width, color=color,
                              label=str(key) if key is not None else "_default")
        else:
            # A KDE is undefined for constant or singleton groups. Render their
            # empirical density on the same bins rather than omit the group.
            sample = np.asarray(sub[x_col].dropna(), dtype=float)
            sample = sample[np.isfinite(sample)]
            if not len(sample):
                continue
            _, _, bars = ax.hist(sample, bins=bins, cumulative=cumulative, density=use_density,
                                 color=color, edgecolor=cfg.background, alpha=0.7,
                                 label=str(key) if key is not None else "_default")
            artist = bars[0]
            artist.set_label(str(key) if key is not None else "_default")
        if key is not None:
            handles.append(artist)
    if use_density:
        label = "Cumulative Probability" if cumulative else "Density"
    else:
        label = "Cumulative Count" if cumulative else "Count"
    axis_labels(ax, sp, y=label)
    return handles
