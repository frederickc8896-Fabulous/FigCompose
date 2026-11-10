"""Native 3D artists; all numerical summaries arrive from compute payloads."""
from __future__ import annotations

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle
from matplotlib.patches import Patch
from matplotlib.transforms import ScaledTranslation
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Line3D, Line3DCollection, Path3DCollection, Poly3DCollection

from data_visuals.core.identity import numeric_format_function
from .helpers import frame, grouped, series_color, series_style
from .scatter import _series_style as _validated_style


class _SeriesPath3DCollection(Path3DCollection):
    """Keep marker shapes beside their per-point colours after native depth sort.

    Matplotlib already reorders colours, sizes and linewidths, but leaves paths
    in input order. Isolate that version-sensitive adapter in this small class.
    """

    def do_3d_projection(self, *args, **kwargs):
        depth = super().do_3d_projection(*args, **kwargs)
        self.set_paths([self._figcompose_paths[index] for index in self._z_markers_idx])
        return depth


def _point_paths(collection, paths):
    collection.__class__ = _SeriesPath3DCollection
    collection._figcompose_paths = tuple(paths)
    collection.set_paths(paths)


class _WaterfallLine3D(Line3D):
    """Keep native, editable lines while their filled profile owns drawing."""

    def draw(self, renderer):
        if self._figcompose_profile_owner._drawing_profile:
            super().draw(renderer)


class _WaterfallProfile3D(Poly3DCollection):
    """Draw one parallel plane's fill and lines as a single depth-sorted unit."""

    def __init__(self, vertices, anchor, lines, **kwargs):
        self._figcompose_anchor = anchor
        self._figcompose_profile_lines = tuple(lines)
        self._drawing_profile = False
        super().__init__([vertices], **kwargs)
        for line in lines:
            line.__class__ = _WaterfallLine3D
            line._figcompose_profile_owner = self

    def do_3d_projection(self, *args, **kwargs):
        super().do_3d_projection(*args, **kwargs)
        # Common X/Z coordinates make ordering depend only on the parallel
        # depth planes, independent of curve height and sampling density.
        return float(proj3d.proj_transform(*self._figcompose_anchor,
                                          self.axes.get_proj())[2])

    def draw(self, renderer):
        if not self.get_visible():
            return
        super().draw(renderer)
        self._drawing_profile = True
        try:
            for line in self._figcompose_profile_lines:
                if line.axes is self.axes:
                    line.draw(renderer)
        finally:
            self._drawing_profile = False


def _alias(value, opts):
    aliases = opts.get("category_aliases", {})
    return aliases.get(value, aliases.get(str(value), value))


def _payload(sp, kind):
    payload = sp.get("derived_data", {}).get("three_d", {})
    if payload.get("kind") != kind:
        raise ValueError(f"{kind} needs its validated three_d compute payload")
    return payload


def _configure(ax, sp, cfg, labels):
    opts = sp.get("options", {})
    ax.set_proj_type(opts.get("proj_type", "ortho"))
    ax.view_init(elev=opts.get("elev", 25), azim=opts.get("azim", -58))
    ax.set_box_aspect(opts.get("box_aspect", (1, 1, 1)), zoom=opts.get("zoom", 1))
    actual = {}
    for axis, label in zip(("x", "y", "z"), labels):
        actual[axis] = str(opts.get(f"{axis}label", label))
        getattr(ax, f"set_{axis}label")(actual[axis], fontfamily=cfg.font_family,
                                        fontsize=sp["font_sizes"]["axis_label"], labelpad=1.5)
        # Apply explicit ranges before projecting native annotations. The common
        # axis layer also owns ticks, formats, validation and final overrides.
        if f"{axis}lim" in opts:
            getattr(ax, f"set_{axis}lim")(*opts[f"{axis}lim"])
        if opts.get(f"{axis}scale", "linear") != "linear":
            raise ValueError("native 3D charts currently require linear coordinate axes")
    ax._data_visuals_axis_labels = actual


def _handle(key, color, *, marker=None, size=25, linewidth=1, edgecolor="none", label=None,
            linestyle=None):
    result = Line2D([], [], color=color, linestyle=linestyle or ("none" if marker else "-"),
                    marker=marker, markersize=np.sqrt(size), linewidth=linewidth,
                    markeredgecolor=edgecolor, markeredgewidth=linewidth, markerfacecolor=color,
                    label=str(key) if label is None else str(label))
    result._figcompose_legend_key = key
    return result


def _draw_scatter3d(ax, sp, cfg, color_map):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    df = frame(sp.get("computed_data", []))
    payload = _payload(sp, "scatter3d")
    mapping, opts = sp["data"], sp.get("options", {})
    columns = [mapping[axis] for axis in ("x", "y", "z")]
    coordinates = df[columns].to_numpy(dtype=float)
    faces, edges, sizes, widths, paths, handles = [], [], [], [], [], []
    group = mapping.get("group")
    default_size = opts.get("point_size")
    default_size = cfg.scatter_point_size if default_size is None else default_size
    style_for = {}
    for index, (key, sub) in enumerate(grouped(df, group, opts.get("series_order"))):
        style = _validated_style(series_style(key, opts))
        if "zorder" in style:
            raise ValueError("scatter3d uses measured depth order; per-series zorder is not supported")
        color = series_color(key, index, cfg, color_map or {}, opts)
        edge = style.get("edgecolor", cfg.background)
        size = style.get("size", default_size)
        width = style.get("linewidth", .6)
        marker = MarkerStyle(style.get("marker", "o"))
        path = marker.get_path().transformed(marker.get_transform())
        style_for[key] = (style.get("facecolor", color), edge, size, width, path)
        if key is not None:
            handles.append(_handle(key, style.get("facecolor", color), marker=style.get("marker", "o"),
                                   size=size, linewidth=width, edgecolor=edge, label=style.get("label", key)))
    for _, row in df.iterrows():
        key = row[group] if group else None
        face, edge, size, width, path = style_for[key]
        faces.append(face); edges.append(edge); sizes.append(size); widths.append(width); paths.append(path)
    # Per-point colours and marker paths share a single global depth sort.
    points = ax.scatter(*coordinates.T, s=sizes, facecolors=faces, edgecolors=edges,
                        linewidths=widths, depthshade=False, alpha=opts.get("opacity", .95))
    _point_paths(points, paths)
    points._figcompose_original_points = True
    for axis, plane in payload["projections"].items():
        index = ("x", "y", "z").index(axis)
        if f"{axis}lim" in opts and not min(opts[f"{axis}lim"]) <= plane <= max(opts[f"{axis}lim"]):
            raise ValueError("an explicit projection plane must lie inside the explicit axis limits")
        projected = coordinates.copy()
        projected[:, index] = plane
        if axis in payload["projection_lines"]:
            links = Line3DCollection(np.stack((coordinates, projected), axis=1),
                                     colors=faces, linewidths=.45, alpha=.27)
            links._figcompose_projection_axis = axis
            ax.add_collection3d(links)
        walls = ax.scatter(*projected.T, s=np.asarray(sizes)*.4, facecolors=faces,
                           edgecolors="none", depthshade=False, alpha=.25)
        _point_paths(walls, paths)
        walls._figcompose_projection_axis = axis
    _configure(ax, sp, cfg, columns)
    return handles


def _draw_waterfall3d(ax, sp, cfg, color_map):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    payload = _payload(sp, "waterfall3d")
    opts, mapping = sp.get("options", {}), sp["data"]
    filled_profiles, depths, handles = [], [], []
    all_x, all_values = [], [payload["baseline"]]
    profiles = list(payload["profiles"])
    series_order = opts.get("order") or opts.get("series_order")
    if series_order:
        rank = {_alias(key, opts): i for i, key in enumerate(series_order)}
        profiles.sort(key=lambda item: rank.get(_alias(item["group"], opts), len(rank)))
    for index, item in enumerate(profiles):
        key = _alias(item["group"], opts)
        color = series_color(key, index, cfg, color_map or {}, opts)
        style = _validated_style(series_style(key, opts))
        if opts.get("fill", True) and "zorder" in style:
            raise ValueError("filled waterfall3d profiles use camera depth; per-series zorder is not supported")
        x, values = np.asarray(item["x"]), np.asarray(item["value"])
        depth = index * payload["depth_spacing"]
        width = style.get("linewidth", opts.get("linewidth"))
        width = cfg.line_stroke_width if width is None else width
        marker = style.get("marker", "o") if opts.get("markers", False) else None
        outline, = ax.plot(x, np.full(len(x), depth), values, color=color, linewidth=width,
                linestyle=style.get("linestyle", "-"), marker=marker,
                markersize=np.sqrt(style.get("size", cfg.marker_size)),
                markerfacecolor=style.get("facecolor", color),
                markeredgecolor=style.get("edgecolor", color), zorder=style.get("zorder", 2))
        if opts.get("fill", True):
            baseline = payload["baseline"]
            vertices = [(x[0], depth, baseline),
                        *zip(x, np.full(len(x), depth), values), (x[-1], depth, baseline)]
            lower, = ax.plot((x[-1], x[-1], x[0], x[0]), (depth,)*4,
                             (values[-1], baseline, baseline, values[0]),
                             color=color, linewidth=max(.4, width*.68))
            filled_profiles.append((vertices, depth, color, (outline, lower)))
        depths.append(depth)
        all_x.extend(x.tolist()); all_values.extend(values.tolist())
        handles.append(_handle(key, color, linewidth=width, marker=marker,
                               size=style.get("size", cfg.marker_size),
                               edgecolor=style.get("edgecolor", color),
                               linestyle=style.get("linestyle", "-"), label=style.get("label", key)))
    anchor_x = min(all_x)/2 + max(all_x)/2
    for vertices, depth, color, lines in filled_profiles:
        collection = _WaterfallProfile3D(
            vertices, (anchor_x, depth, payload["baseline"]), lines,
            facecolors=[color], edgecolors="none", linewidths=0,
            alpha=opts.get("fill_alpha", 1),
        )
        ax.add_collection3d(collection)
    ax.auto_scale_xyz(all_x, depths, all_values)
    ax.set_yticks(depths, labels=[str(_alias(item["group"], opts)) for item in profiles])
    _configure(ax, sp, cfg, (mapping["x"], mapping["group"], mapping["y"]))
    return handles


def _draw_bar3d(ax, sp, cfg, color_map):
    rows = sp.get("computed_data")
    if rows is None or len(rows) == 0:
        return []
    payload = _payload(sp, "bar3d")
    opts, mapping = sp.get("options", {}), sp["data"]
    cells, groups = payload["cells"], payload["groups"]
    colors = {}
    handles = []
    for index, raw in enumerate(groups):
        key = _alias(raw, opts)
        colors[raw] = series_color(key, index, cfg, color_map or {}, opts)
        if key is not None:
            handle = Patch(facecolor=colors[raw], edgecolor=cfg.background,
                           label=series_style(key, opts).get("label", str(key)))
            handle._figcompose_legend_key = key
            handles.append(handle)
    dx, dy = payload["width"]
    # One call keeps all six faces of every cuboid in one depth-sorted collection.
    collection = ax.bar3d([c["x_index"]-dx/2 for c in cells],
                          [c["y_index"]-dy/2 for c in cells],
                          [c["bottom"] for c in cells], dx, dy,
                          [c["height"] for c in cells],
                          color=[colors[c["group"]] for c in cells], shade=False,
                          edgecolor=cfg.background, linewidth=.65, zsort="average")
    collection._figcompose_cuboids = len(cells)
    ax.set_xticks(range(len(payload["x_order"])), labels=list(map(str, payload["x_order"])))
    ax.set_yticks(range(len(payload["y_order"])), labels=list(map(str, payload["y_order"])))
    _configure(ax, sp, cfg, (mapping["x"], mapping["y"], mapping["value"]))
    if opts.get("label_totals", False):
        formatter = numeric_format_function(opts.get("total_format") or opts.get("value_format", "g"), "total_format")
        size = max(8., sp["font_sizes"]["tick"] * 1.0625)
        labels = []
        transform = ax.transData + ScaledTranslation(0, size*.22/72, ax.figure.dpi_scale_trans)
        for item in payload["totals"]:
            text = ax.text2D(0, 0, formatter(item["value"]), ha="center", va="bottom",
                             fontfamily=cfg.font_family, fontsize=size, color=cfg.text_color,
                             transform=transform, clip_on=False)
            text._figcompose_total = item["value"]
            labels.append((text, item))

        def update_labels():
            matrix = ax.get_proj()
            for text, item in labels:
                x, y, _ = proj3d.proj_transform(item["x_index"], item["y_index"], item["top"], matrix)
                text.set_position((x, y))

        ax._figcompose_layout_callback = update_labels
        update_labels()
    return handles
