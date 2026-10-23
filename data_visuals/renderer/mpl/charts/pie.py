"""Native pie/donut builders with semantic colours and managed legends."""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Patch

from .helpers import _luminance, frame, ordered, series_color


def _draw_pie(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    group, value = mapping["group"], mapping.get("value")
    column = f"{value}_sum" if value else f"{group}_count"
    categories = opts.get("order") or ordered(df[group])
    values = df.set_index(group).loc[categories, column].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values < 0).any()
            or not np.isfinite(values.sum()) or values.sum() <= 0):
        raise ValueError("Pie/donut values must be finite, nonnegative and have a positive total.")
    colors = [series_color(category, i, cfg, color_map or {}) for i, category in enumerate(categories)]
    donut = sp.get("chart") == "donut"
    width = float(opts.get("width", 0.4)) if donut else None
    decimals = int(opts.get("percent_decimals", 0))
    threshold = float(opts.get("percent_threshold", 3.0))
    # Matplotlib casts its input to float32, which can overflow/underflow even
    # for valid float64 amounts. Bounded fractions retain the actual geometry.
    scaled = values / values.max()
    fractions = scaled / scaled.sum()
    percentages = iter(fractions * 100.0)

    def percentage(_value):
        # The callback argument is derived from float32 wedge geometry. Labels
        # and threshold decisions use the original float64 proportions.
        value = float(next(percentages))
        at_threshold = np.isclose(value, threshold, rtol=0, atol=1e-12)
        return f"{value:.{decimals}f}%" if value > 0 and (value >= threshold or at_threshold) else ""

    result = ax.pie(
        fractions, colors=colors, labels=None, normalize=True,
        startangle=float(opts.get("startangle", 90.0)),
        counterclock=bool(opts.get("counterclock", False)),
        autopct=percentage if opts.get("show_percent", True) else None,
        pctdistance=(1.0 - width / 2) if donut else 0.66,
        wedgeprops={"linewidth": max(0.5, cfg.axis_domain_width * 0.75),
                    "edgecolor": cfg.background, **({"width": width} if donut else {})},
        textprops={"fontsize": max(8.0, sp["font_sizes"]["tick"]),
                   "fontfamily": cfg.font_family, "color": cfg.text_color},
    )
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    if len(result) == 3:
        for color, text in zip(colors, result[2]):
            background = _luminance(color)
            def contrast(foreground):
                luminance = _luminance(foreground)
                return (max(luminance, background) + 0.05) / (min(luminance, background) + 0.05)
            text.set_color(max((cfg.text_color, cfg.background), key=contrast))
        # Percentages retain the declared physical font size. Their measured
        # widths and normalized locations provide a minimum square viewport;
        # the canvas can grow automatic height or reject an undersized fixed
        # Figure rather than rendering overlapping text.
        renderer = ax.figure.canvas.get_renderer()
        labels = [text for text in result[2] if text.get_text()]
        measured = [(text, text.get_window_extent(renderer)) for text in labels]
        diameter = 60.0
        for i, (first, first_box) in enumerate(measured):
            for second, second_box in measured[i + 1:]:
                dx, dy = np.abs(np.asarray(first.get_position()) - np.asarray(second.get_position())) / 2.5
                width = (first_box.width + second_box.width) * 36 / ax.figure.dpi + 1.5
                height = (first_box.height + second_box.height) * 36 / ax.figure.dpi + 1.5
                required = min(width / dx if dx > 1e-12 else np.inf,
                               height / dy if dy > 1e-12 else np.inf)
                diameter = max(diameter, float(required))
        ax._data_visuals_minimum_plot = (diameter, diameter)
    # Explicitly include percentages in measured export bounds. Legends are
    # separate handles, so zero-size categories retain their stable colours.
    ax._data_visuals_bounds_artists = list(result[2]) if len(result) == 3 else []
    return [Patch(facecolor=color, edgecolor="none", label=str(category))
            for category, color in zip(categories, colors)]
