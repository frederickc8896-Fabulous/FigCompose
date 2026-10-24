"""Matplotlib scatter and bubble plots; statistics come from the compute layer."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Real

import numpy as np
import pandas as pd
from matplotlib.colors import is_color_like
from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle
from matplotlib.transforms import ScaledTranslation

from .helpers import axis_labels, frame, grouped, secondary_axis, series_color, value_column


_STYLE_KEYS = {"marker", "size", "color", "facecolor", "edgecolor", "linewidth", "zorder", "label"}


def _number(value, name, *, minimum=None):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not np.isfinite(value) or (minimum is not None and value < minimum)):
        raise ValueError(f"{name} must be a finite number" + (f" >= {minimum}" if minimum is not None else ""))
    return float(value)


def _series_style(style):
    if not isinstance(style, Mapping):
        raise ValueError("Each scatter series style must be a mapping")
    unknown = set(style) - _STYLE_KEYS
    if unknown:
        raise ValueError(f"Unknown scatter series style fields: {sorted(map(str, unknown))}")
    result = dict(style)
    for name in ("size", "linewidth", "zorder"):
        if name in result:
            result[name] = _number(result[name], f"series_styles.{name}", minimum=None if name == "zorder" else 0)
    for name in ("color", "facecolor", "edgecolor"):
        if name in result and not is_color_like(result[name]):
            raise ValueError(f"series_styles.{name} must be a Matplotlib color")
    if "marker" in result:
        try:
            MarkerStyle(result["marker"])
        except (ValueError, TypeError) as exc:
            raise ValueError("series_styles.marker must be a Matplotlib marker") from exc
    if "label" in result and not isinstance(result["label"], str):
        raise ValueError("series_styles.label must be a string")
    return result


def scatter_legend_handle(key, color, style, cfg):
    """Use the same marker, area and edge as the corresponding scatter series."""
    style = _series_style(style)
    color = style.get("color", color)
    return Line2D([], [], linestyle="none", marker=style.get("marker", "o"),
                  markersize=np.sqrt(style.get("size", cfg.scatter_point_size)),
                  markerfacecolor=style.get("facecolor", color),
                  markeredgecolor=style.get("edgecolor", "none"),
                  markeredgewidth=style.get("linewidth", 1), color=color,
                  label=style.get("label", str(key) if key is not None else "_default"))


def _interval_options(df, y_col, specification):
    """Validate supplied absolute interval endpoints without recomputing statistics."""
    allowed = {"lower", "upper", "capsize", "linewidth", "alpha"}
    if (not isinstance(specification, Mapping) or set(specification) - allowed
            or not {"lower", "upper"} <= set(specification)):
        raise ValueError("errorbar requires lower and upper column names, with optional capsize, linewidth and alpha")
    for name in ("lower", "upper"):
        column = specification[name]
        if not isinstance(column, str) or column not in df:
            raise ValueError(f"errorbar.{name} must name an existing column")
    values = {}
    for name, column in (("lower", specification["lower"]), ("upper", specification["upper"]), ("y", y_col)):
        values[name] = np.asarray([_number(value, f"errorbar.{name}") for value in df[column]], dtype=float)
    if np.any(values["lower"] > values["y"]) or np.any(values["y"] > values["upper"]):
        raise ValueError("errorbar requires lower <= plotted y <= upper for every row")
    options = {name: _number(specification.get(name, default), f"errorbar.{name}", minimum=0)
               for name, default in (("capsize", 2), ("linewidth", .85), ("alpha", .8))}
    if options["alpha"] > 1:
        raise ValueError("errorbar.alpha must be between 0 and 1")
    return values, options


def _physical_x_offsets(options):
    """Horizontal group dodging is a display offset in points, never a new x value."""
    raw = options.get("x_offsets", {})
    if not isinstance(raw, Mapping):
        raise ValueError("x_offsets must map group values to finite physical point offsets")
    offsets = {key: _number(value, "x_offsets") for key, value in raw.items()}
    if any(offsets.values()):
        for incompatible in ("point_labels", "trend"):
            if options.get(incompatible):
                raise ValueError(f"Nonzero x_offsets cannot be combined with {incompatible}")
    return offsets


def _coordinates(values, name):
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must contain two finite numbers")
    try:
        if len(values) != 2:
            raise ValueError(f"{name} must contain two finite numbers")
        return tuple(_number(value, name) for value in values)
    except TypeError as exc:
        raise ValueError(f"{name} must contain two finite numbers") from exc


def _text_annotations(ax, specs, cfg):
    """Add declarative text in data or axes coordinates at a physical font size."""
    if not isinstance(specs, (list, tuple)):
        raise ValueError("annotations must be a list of text annotation specifications")
    allowed = {"text", "xy", "coords", "fontsize", "ha", "va", "color", "fontweight"}
    annotations = []
    for spec in specs:
        if not isinstance(spec, Mapping) or set(spec) - allowed or not {"text", "xy"} <= set(spec):
            raise ValueError("Each annotation requires text and xy, with optional text styling")
        if not isinstance(spec["text"], str):
            raise ValueError("annotations.text must be a string")
        xy = _coordinates(spec["xy"], "annotations.xy")
        coords = spec.get("coords", "axes fraction")
        if not isinstance(coords, str) or coords not in ("data", "axes fraction"):
            raise ValueError("annotations.coords must be 'data' or 'axes fraction'")
        ha, va = spec.get("ha", "left"), spec.get("va", "center")
        weight = spec.get("fontweight", "normal")
        for name, value, choices in (("ha", ha, ("left", "center", "right")),
                                      ("va", va, ("top", "center", "bottom")),
                                      ("fontweight", weight, ("normal", "bold"))):
            if not isinstance(value, str) or value not in choices:
                raise ValueError(f"annotations.{name} must be one of {choices}")
        default_size = cfg.font_sizes.get("axis_label", 8)
        if cfg.physical:
            default_size = max(8, default_size)
        size = _number(spec.get("fontsize", default_size), "annotations.fontsize", minimum=0)
        if size == 0:
            raise ValueError("annotations.fontsize must be positive")
        color = spec.get("color", cfg.text_color)
        if not is_color_like(color):
            raise ValueError("annotations.color must be a Matplotlib color")
        annotations.append(ax.annotate(
            spec["text"], xy=xy, xycoords=coords, fontsize=size,
            fontfamily=cfg.font_family, color=color, fontweight=weight,
            ha=ha, va=va, annotation_clip=False, clip_on=False,
        ))
    ax._data_visuals_text_annotations = annotations
    return annotations


def _decorations(ax, opts, cfg):
    """Render data-coordinate guides and transitions, independent of a study."""
    guides, arrow_specs = opts.get("guides", []), opts.get("arrows", [])
    if not isinstance(guides, (list, tuple)):
        raise ValueError("guides must be a list of guide specifications")
    if not isinstance(arrow_specs, (list, tuple)):
        raise ValueError("arrows must be a list of arrow specifications")
    for guide in guides:
        allowed = {"axis", "value", "color", "linestyle", "linewidth"}
        if not isinstance(guide, Mapping) or set(guide) - allowed or guide.get("axis") not in ("x", "y"):
            raise ValueError("Each guide requires axis='x' or 'y', value, and optional line styling")
        value = _number(guide.get("value"), "guides.value")
        draw = ax.axvline if guide["axis"] == "x" else ax.axhline
        draw(value, color=guide.get("color", cfg.ref_line_color),
             linestyle=guide.get("linestyle", "--"),
             linewidth=_number(guide.get("linewidth", cfg.line_stroke_width), "guides.linewidth", minimum=0),
             zorder=1, label="_guide")
    arrows, segments = [], []
    for arrow in arrow_specs:
        allowed = {"start", "end", "color", "linewidth", "mutation_scale", "shrinkA", "shrinkB"}
        if not isinstance(arrow, Mapping) or set(arrow) - allowed or not {"start", "end"} <= set(arrow):
            raise ValueError("Each arrow requires start and end coordinates and optional arrow styling")
        start, end = _coordinates(arrow["start"], "arrows.start"), _coordinates(arrow["end"], "arrows.end")
        props = {"arrowstyle": "-|>", "color": arrow.get("color", cfg.text_color)}
        for key, default in (("linewidth", 1), ("mutation_scale", 9), ("shrinkA", 4), ("shrinkB", 4)):
            props[key] = _number(arrow.get(key, default), f"arrows.{key}", minimum=0)
        arrows.append(ax.annotate("", xy=end, xytext=start, arrowprops=props, zorder=2))
        segments.append((start, end))
    return arrows, segments


def _draw_scatter(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", [])).reset_index(drop=True)
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y_col, g_col = mapping["x"], mapping["y"], mapping.get("group")
    raw_styles = opts.get("series_styles", {})
    if not isinstance(raw_styles, Mapping):
        raise ValueError("series_styles must map group values to marker styling")
    styles = {key: _series_style(style) for key, style in raw_styles.items()}
    intervals = _interval_options(df, y_col, opts["errorbar"]) if "errorbar" in opts else None
    x_offsets = _physical_x_offsets(opts)
    if mapping.get("y2") and any(x_offsets.values()):
        raise ValueError("Nonzero x_offsets cannot be combined with y2")
    labels = opts.get("point_labels")
    if labels is not None:
        if (not isinstance(labels, Mapping) or set(labels) - {"column", "fontsize"}
                or not isinstance(labels.get("column"), str) or labels["column"] not in df):
            raise ValueError("point_labels requires an existing column and optional fontsize")
        if "fontsize" in labels and _number(labels["fontsize"], "point_labels.fontsize", minimum=0) == 0:
            raise ValueError("point_labels.fontsize must be positive")
    sizes = pd.Series(cfg.scatter_point_size, index=df.index, dtype=float)
    if mapping.get("size"):
        raw_sizes = pd.to_numeric(df[mapping["size"]], errors="coerce")
        if (raw_sizes < 0).any() or raw_sizes.isin([float("inf"), float("-inf")]).any():
            raise ValueError("Scatter bubble sizes must be finite and non-negative")
        if raw_sizes.max() > 0:
            sizes = raw_sizes.fillna(0) / raw_sizes.max() * cfg.scatter_point_size * 4
        else:
            sizes = raw_sizes.fillna(0)
    handles, obstacles, errorbars = [], [], {}
    displaced_data = False
    for index, (key, sub) in enumerate(grouped(df, g_col)):
        color = series_color(key, index, cfg, color_map)
        style = styles.get(key, styles.get(str(key), {}))
        color = style.get("color", color)
        offset_pt = x_offsets.get(key, x_offsets.get(str(key), 0))
        # Composition order matters: map data to display first, then add points.
        transform = (ax.transData if offset_pt == 0 else
                     ax.transData + ScaledTranslation(offset_pt / 72, 0, ax.figure.dpi_scale_trans))
        group_sizes = np.full(len(sub), style["size"]) if "size" in style else sizes.loc[sub.index].to_numpy()
        if intervals is not None:
            values, interval_style = intervals
            positions = sub.index.to_numpy()
            y = values["y"][positions]
            errorbars[key] = ax.errorbar(
                sub[x_col], y,
                yerr=np.vstack((y - values["lower"][positions], values["upper"][positions] - y)),
                fmt="none", color=color, capsize=interval_style["capsize"],
                elinewidth=interval_style["linewidth"], capthick=interval_style["linewidth"],
                alpha=interval_style["alpha"], zorder=style.get("zorder", 1) - .1,
                transform=transform, label="_interval",
            )
        artist = ax.scatter(sub[x_col], sub[y_col], s=group_sizes, marker=style.get("marker", "o"),
                            facecolors=style.get("facecolor", color),
                            edgecolors=style.get("edgecolor", "none"),
                            linewidths=style.get("linewidth", 1), zorder=style.get("zorder", 1),
                            label=style.get("label", str(key) if key is not None else "_default"),
                            alpha=opts.get("opacity", 0.7), transform=transform)
        artist._data_visuals_series_key = key
        artist._data_visuals_x_offset_pt = offset_pt
        if offset_pt:
            # A display-space translation prevents Matplotlib from recognising
            # transData as the collection's data branch. Preserve automatic
            # limits from the actual coordinates, including supplied CI bounds;
            # group dodging must not change the numerical data domain.
            xy = np.ma.filled(artist.get_offsets(), np.nan)
            ax.update_datalim(xy)
            if intervals is not None:
                ax.update_datalim(np.column_stack((xy[:, 0], values["lower"][positions])))
                ax.update_datalim(np.column_stack((xy[:, 0], values["upper"][positions])))
            displaced_data = True
        for (_, row), area in zip(sub.iterrows(), group_sizes):
            xy = (row[x_col], row[y_col])
            if not all(pd.notna(value) and isinstance(value, Real) and np.isfinite(value) for value in xy):
                continue
            label = row[labels["column"]] if labels else None
            obstacles.append({"xy": tuple(map(float, xy)), "radius": np.sqrt(area) / 2 + style.get("linewidth", 1) / 2 + 1,
                              "color": color, "label": None if pd.isna(label) else label})
        if key is not None:
            handles.append(artist)
    if displaced_data:
        # Explicit chart limits are applied later by the common axis layer. This also
        # honours any axes whose automatic scaling was already disabled.
        ax.autoscale_view()
    ax._data_visuals_errorbars = errorbars
    if opts.get("trend"):
        trend = frame(sp.get("derived_data", {}).get("trend_data", []))
        if not trend.empty:
            trend_col = "trend" if "trend" in trend.columns else y_col
            for index, (key, sub) in enumerate(grouped(trend, g_col)):
                sub = sub.sort_values(x_col, kind="stable")
                color = series_color(key, index, cfg, color_map) if key is not None else cfg.trend_line_color
                ax.plot(sub[x_col], sub[trend_col], color=color, linewidth=cfg.line_stroke_width)
    axis_labels(ax, sp)
    if mapping.get("y2"):
        twin = secondary_axis(ax, sp, cfg, mapping["y2"])
        twin.scatter(df[x_col], df[value_column(df, mapping["y2"], "")],
                     color=cfg.y2_color, marker="D", s=sizes,
                     alpha=opts.get("opacity", 0.7), edgecolors="none")
    arrows, segments = _decorations(ax, opts, cfg)
    _text_annotations(ax, opts.get("annotations", []), cfg)
    ax._data_visuals_scatter_arrows = arrows
    ax._data_visuals_annotations = {"point_labels": dict(labels) if labels else None,
                                   "points": obstacles, "arrows": segments,
                                   "texts": [], "boxes": []}
    return handles
