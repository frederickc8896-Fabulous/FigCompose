"""Shared helpers; geometry and theme decisions stay with the canvas."""

from __future__ import annotations

from numbers import Real

import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb

from data_visuals.utils.colors import SEQUENTIAL_SCHEMES


def frame(rows):
    return rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)


def ordered(values):
    values = list(pd.unique(values))
    try:
        return sorted(values)
    except TypeError:
        return sorted(values, key=lambda value: (type(value).__name__, str(value)))


def grouped(df, column):
    if column and column in df.columns:
        return [(key, df[df[column].isna()] if pd.isna(key) else df[df[column] == key])
                for key in ordered(df[column])]
    return [(None, df)]


def series_color(key, index, cfg, color_map):
    return color_map.get(key, color_map.get(str(key), cfg.get_color(index)))


def value_column(df, name, suffix="_mean"):
    for candidate in (f"{name}{suffix}", name):
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Computed data is missing the value column {name!r}")


def axis_labels(ax, sp, x=None, y=None):
    mapping = sp["data"]
    x = mapping.get("x", "") if x is None else x
    y = mapping.get("y", "") if y is None else y
    if isinstance(y, (list, tuple)):
        y = ", ".join(map(str, y))
    labels = {"x": str(x), "y": str(y)}
    ax._data_visuals_axis_labels = labels
    ax.set_xlabel(labels["x"], fontsize=sp["font_sizes"]["axis_label"])
    ax.set_ylabel(labels["y"], fontsize=sp["font_sizes"]["axis_label"])


def secondary_axis(ax, sp, cfg, label, horizontal=False, color=None):
    color = cfg.y2_color if color is None else color
    twin = ax.twiny() if horizontal else ax.twinx()
    twin.patch.set_visible(False)
    twin.grid(False)
    axis = "x" if horizontal else "y"
    twin.tick_params(axis=axis, labelsize=sp["font_sizes"]["tick"],
                     colors=color, width=cfg.axis_tick_width,
                     length=cfg.axis_tick_size, pad=cfg.axis_label_padding)
    for name, spine in twin.spines.items():
        spine.set_linewidth(cfg.axis_domain_width)
        spine.set_visible(name == ("top" if horizontal else "right"))
        spine.set_color(color)
    setter = twin.set_xlabel if horizontal else twin.set_ylabel
    setter(str(label), fontsize=sp["font_sizes"]["axis_label"],
           fontfamily=cfg.font_family, fontweight=cfg.axis_label_weight,
           color=color, labelpad=cfg.axis_title_padding)
    for tick in (twin.get_xticklabels() if horizontal else twin.get_yticklabels()):
        tick.set_family(cfg.font_family)
        tick.set_weight(cfg.tick_label_weight)
    twins = getattr(ax, "_data_visuals_secondary_axes", [])
    ax._data_visuals_secondary_axes = [*twins, twin]
    return twin


def reference_lines(ax, sp, cfg, mean=None, horizontal=False):
    opts = sp.get("options", {})
    handles = []
    draw = ax.axvline if horizontal else ax.axhline
    if opts.get("hline") is not None:
        handles.append(draw(float(opts["hline"]), color=cfg.ref_line_color,
                            linestyle=cfg.ref_dash, linewidth=cfg.line_stroke_width,
                            label=opts.get("hline_label") or "_reference"))
    if opts.get("mean_line") and mean is not None and np.isfinite(mean):
        handles.append(draw(float(mean), color=cfg.mean_line_color,
                            linestyle=cfg.mean_line_dash, linewidth=cfg.line_stroke_width,
                            label=opts.get("mean_line_label") or "Mean"))
    return handles


def color_scheme(sp, cfg, default=None):
    scheme = sp.get("options", {}).get("color_scheme")
    if isinstance(scheme, (list, tuple)):
        return LinearSegmentedColormap.from_list("custom", scheme)
    if isinstance(scheme, str) and scheme:
        if scheme in SEQUENTIAL_SCHEMES:
            return LinearSegmentedColormap.from_list(scheme, SEQUENTIAL_SCHEMES[scheme])
        return colormaps[scheme]
    return cfg.sequential_cmap if default is None else default


def color_norm(sp):
    """Explicit user domains override the canvas's shared colour limits."""
    domain = sp.get("options", {}).get("color_domain")
    if domain is None:
        domain = sp.get("_color_limits")
    if domain is None:
        return None
    try:
        valid = len(domain) == 2 and all(
            isinstance(value, Real) and not isinstance(value, (bool, np.bool_))
            and np.isfinite(value) for value in domain
        )
    except TypeError:
        valid = False
    if not valid or domain[0] >= domain[1]:
        raise ValueError("Colour domain must contain two finite numbers with lower < upper")
    return Normalize(vmin=float(domain[0]), vmax=float(domain[1]))


def colorbar(ax, image, sp, cfg):
    """Draw only in an explicitly allocated rectangle; never resize the axes."""
    rect = sp.get("_colorbar_box")
    if rect is None:
        return None
    cax = ax.figure.add_axes(rect)
    cax._data_visuals_colorbar = True
    result = ax.figure.colorbar(image, cax=cax)
    cax.tick_params(labelsize=sp.get("_colorbar_font_size", sp["font_sizes"]["tick"]),
                    color=cfg.axis_color, labelcolor=cfg.text_color,
                    width=cfg.axis_tick_width, length=cfg.axis_tick_size)
    result.outline.set_edgecolor(cfg.axis_domain_color)
    result.outline.set_linewidth(cfg.axis_domain_width)
    for tick in cax.get_yticklabels():
        tick.set_family(cfg.font_family)
        tick.set_weight(cfg.tick_label_weight)
    return result


def _luminance(color):
    rgb = np.asarray(to_rgb(color))
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(linear @ [0.2126, 0.7152, 0.0722])


def annotate_matrix(ax, image, matrix, sp, cfg, fmt):
    if not sp.get("options", {}).get("annotate", True):
        return
    for (row, col), value in np.ndenumerate(matrix):
        if not np.isfinite(value):
            continue
        lum = _luminance(image.cmap(image.norm(value))[:3])
        def contrast(color):
            fg = _luminance(color)
            return (max(lum, fg) + 0.05) / (min(lum, fg) + 0.05)
        text_color = max((cfg.text_color, cfg.background), key=contrast)
        ax.text(col, row, format(value, fmt), ha="center", va="center",
                fontsize=sp["font_sizes"]["tick"], fontfamily=cfg.font_family,
                fontweight=cfg.tick_label_weight, color=text_color)


def matrix_ticks(ax, xs, ys, cfg):
    ax.set_xticks(range(len(xs)), labels=xs)
    ax.set_yticks(range(len(ys)), labels=ys)
    ax.set_xticks(np.arange(len(xs) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(ys) + 1) - 0.5, minor=True)
    ax.grid(False)
    ax.grid(which="minor", color=cfg.heatmap_cell_stroke,
            linewidth=cfg.heatmap_cell_stroke_width)
    ax.tick_params(which="minor", bottom=False, left=False)
