"""Inspect final Matplotlib artists in physical points without changing layout.

The report describes rendered geometry, not scientific correctness or an
aesthetic score.  Clipped text is measured only where it can actually render;
arbitrary diagram nodes and projected 3D text are deliberately outside the
collision checks.
"""
from __future__ import annotations

from collections.abc import Mapping
from itertools import combinations
import math
from numbers import Real
from pathlib import Path

import matplotlib as mpl
from matplotlib.collections import PathCollection
from matplotlib.font_manager import FontProperties
from matplotlib.legend import Legend
from matplotlib.markers import MarkerStyle
from matplotlib.path import Path as MplPath
from matplotlib.patches import Rectangle
from matplotlib.text import Annotation, Text
from matplotlib.transforms import Bbox

from data_visuals.core.quality import FigureReport, QualityIssue


def _number(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        requirement = "positive" if positive else "nonnegative"
        raise ValueError(f"{name} must be a finite {requirement} number")
    return float(value)


def _safe(value):
    """Use built-in JSON scalars, retaining the type of category identities."""
    if isinstance(value, MarkerStyle):
        return _safe(value.get_path().transformed(value.get_transform()))
    if isinstance(value, MplPath):
        return {"vertices": _safe(value.vertices), "codes": _safe(value.codes)}
    if hasattr(value, "item") and getattr(value, "ndim", 0) == 0:
        value = value.item()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Real):
        if not math.isfinite(value):
            raise ValueError("Quality report values must be finite")
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or hasattr(value, "tolist"):
        return [_safe(item) for item in value]
    raise TypeError(f"Cannot describe {type(value).__name__} in a quality report")


def _box(bbox, height, scale):
    return {"x": float(bbox.x0 * scale), "y": float((height - bbox.y1) * scale),
            "w": float(max(0, bbox.width * scale)), "h": float(max(0, bbox.height * scale))}


def _bbox(box):
    return Bbox.from_bounds(box["x"], box["y"], box["w"], box["h"])


def _union(boxes):
    return Bbox.union([_bbox(box) for box in boxes]).bounds if boxes else None


def _finite_bbox(bbox):
    return bbox is not None and all(math.isfinite(v) for v in bbox.extents)


def _intersects(a, b, tolerance):
    return (min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > tolerance
            and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > tolerance)


def _outside(box, container, tolerance):
    return (box["x"] < container["x"] - tolerance or box["y"] < container["y"] - tolerance
            or box["x"] + box["w"] > container["x"] + container["w"] + tolerance
            or box["y"] + box["h"] > container["y"] + container["h"] + tolerance)


def _rectangle(box):
    return [(box["x"], box["y"]), (box["x"] + box["w"], box["y"]),
            (box["x"] + box["w"], box["y"] + box["h"]),
            (box["x"], box["y"] + box["h"])]


def _text_bbox(text, renderer):
    # Annotation can be visible=True while its anchor is intentionally outside
    # the data view. Matplotlib then omits it entirely from the actual draw.
    if isinstance(text, Annotation) and not text._check_xy(renderer):
        return None
    bbox = text.get_tightbbox(renderer)
    if not _finite_bbox(bbox) or bbox.width <= 0 or bbox.height <= 0:
        return None
    patch = text.get_bbox_patch()
    if patch is not None and patch.get_visible():
        patch_box = patch.get_tightbbox(renderer)
        if _finite_bbox(patch_box) and patch_box.width > 0 and patch_box.height > 0:
            bbox = Bbox.union([bbox, patch_box])
    return bbox


def _polygon(text, box, renderer, scale):
    """An oriented text rectangle avoids false overlap on rotated tick labels.

    Text's measured axis-aligned bounds contain its rotated rectangle. Its
    native layout provides the unrotated width; the other side follows from
    the measured projection. For clipped text or padded boxes the visible
    axis-aligned rectangle is the appropriate conservative approximation.
    """
    angle = math.radians(float(text.get_rotation()))
    patch = text.get_bbox_patch()
    native = text.get_window_extent(renderer)
    clipped = text.get_clip_on() and (text.get_clip_box() is not None or text.get_clip_path() is not None)
    if (abs(math.sin(angle)) < 1e-10 or clipped
            or (patch is not None and patch.get_visible())):
        return _rectangle(box)
    _, lines, _ = text._get_layout(renderer)
    width = max((line[1][0] for line in lines), default=0)
    c, s = math.cos(angle), math.sin(angle)
    height = ((native.width - abs(c) * width) / abs(s) if abs(s) > abs(c)
              else (native.height - abs(s) * width) / abs(c))
    vertices = [(x * c - y * s, x * s + y * c)
                for x, y in ((0, 0), (width, 0), (width, max(0, height)), (0, max(0, height)))]
    min_x, max_y = min(x for x, _ in vertices), max(y for _, y in vertices)
    return [(box["x"] + (x - min_x) * scale, box["y"] + (max_y - y) * scale)
            for x, y in vertices]


def _polygon_overlap(a, b, tolerance):
    for polygon in (a, b):
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            nx, ny = -(q[1] - p[1]), q[0] - p[0]
            length = math.hypot(nx, ny)
            if not length:
                continue
            first = [(x * nx + y * ny) / length for x, y in a]
            second = [(x * nx + y * ny) / length for x, y in b]
            if min(max(first), max(second)) - max(min(first), min(second)) <= tolerance:
                return False
    return True


def _point_segment_distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    square = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / square)) if square else 0
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def _polygon_gap(a, b):
    if _polygon_overlap(a, b, 0):
        return 0.0
    return min(_point_segment_distance(point, p, q)
               for source, target in ((a, b), (b, a)) for point in source
               for p, q in zip(target, target[1:] + target[:1]))


def _spec_dict(spec):
    if spec is None:
        return {}
    if isinstance(spec, Mapping):
        return spec
    if hasattr(spec, "to_dict"):
        return spec.to_dict(runtime=True)
    raise TypeError("spec must be a FigureSpec, mapping, or None")


def _style(fig, spec, diagnostics):
    maps = diagnostics.get("color_maps", {})
    style = {"palette": spec.get("palette"), "theme": spec.get("theme"),
             "font": _safe(getattr(fig, "_data_visuals_font", {})),
             "color_maps": {str(column): [{"id": _safe(key), "color": _safe(color)}
                                         for key, color in colors.items()]
                            for column, colors in maps.items()},
             "panels": [], "artist_styles": []}
    for subplot in spec.get("subplots", []):
        options = subplot.get("options", {})
        style["panels"].append({"panel": [int(subplot["row"]), int(subplot["col"])],
                                "group": subplot.get("data", {}).get("group"),
                                "series_order": _safe(options.get("series_order", [])),
                                "series_styles": [{"id": _safe(key), "style": _safe(value)}
                                                  for key, value in options.get("series_styles", {}).items()]})
    # Palette registration alone cannot reveal a callback or downstream user
    # changing a live glyph. Record actual visual properties independently of
    # the semantic defaults so a reproducibility snapshot sees that change.
    owners = {}
    for key, cell in diagnostics.get("cells", {}).items():
        key = tuple(key) if not isinstance(key, str) else tuple(map(int, key.split(",")))
        for role, axes in (("primary", [cell["axes"]]), ("secondary", cell.get("secondary_axes", [])),
                           ("colorbar", cell.get("colorbar_axes", []))):
            for index, ax in enumerate(axes):
                owners[id(ax)] = f"panel:{key[0]},{key[1]}:{role}:{index}"
    def rgba(color):
        return list(map(float, mpl.colors.to_rgba(color)))
    def unique_rows(values):
        result, seen = [], set()
        for row in values:
            safe = _safe(row)
            key = tuple(safe)
            if key not in seen:
                result.append(safe)
                seen.add(key)
        return result
    for ax_index, ax in enumerate(fig.axes):
        if not ax.get_visible():
            continue
        prefix = owners.get(id(ax), f"axes:{ax_index}")
        for index, line in enumerate(ax.lines):
            if not line.get_visible():
                continue
            marker = line.get_marker()
            if isinstance(marker, mpl.path.Path):
                marker = {"vertices": _safe(marker.vertices), "codes": _safe(marker.codes)}
            style["artist_styles"].append({"id": f"{prefix}:line:{index}", "kind": "line",
                "color": rgba(line.get_color()), "linewidth": float(line.get_linewidth()),
                "linestyle": _safe(line.get_linestyle()), "marker": _safe(marker),
                "dash_pattern": _safe(getattr(line, "_unscaled_dash_pattern", None)),
                "markersize": float(line.get_markersize()), "alpha": _safe(line.get_alpha()),
                "markerfacecolor": rgba(line.get_markerfacecolor()),
                "markeredgecolor": rgba(line.get_markeredgecolor())})
        for index, collection in enumerate(ax.collections):
            if not collection.get_visible():
                continue
            faces, edges = collection.get_facecolors(), collection.get_edgecolors()
            collection_style = {"id": f"{prefix}:collection:{index}", "kind": "collection",
                "facecolors": unique_rows(faces), "edgecolors": unique_rows(edges),
                "facecolor_count": len(faces), "edgecolor_count": len(edges),
                "linewidths": _safe(collection.get_linewidths()),
                "linestyles": _safe(collection.get_linestyles()), "alpha": _safe(collection.get_alpha())}
            if isinstance(collection, PathCollection):
                # Scatter paths describe marker glyphs. Generic collection
                # paths (CI segments, contours, etc.) are source coordinates
                # and must never be copied into a presentation snapshot.
                paths, seen_paths = [], set()
                for path in collection.get_paths():
                    key = (tuple(map(tuple, path.vertices)),
                           tuple(path.codes) if path.codes is not None else None)
                    if key not in seen_paths:
                        paths.append(_safe(path))
                        seen_paths.add(key)
                collection_style.update(sizes=_safe(collection.get_sizes()), marker_paths=paths)
            style["artist_styles"].append(collection_style)
        for index, patch in enumerate(ax.patches):
            if patch.get_visible():
                style["artist_styles"].append({"id": f"{prefix}:patch:{index}", "kind": "patch",
                    "facecolor": rgba(patch.get_facecolor()), "edgecolor": rgba(patch.get_edgecolor()),
                    "linewidth": float(patch.get_linewidth()), "linestyle": _safe(patch.get_linestyle()),
                    "alpha": _safe(patch.get_alpha())})
        for index, image in enumerate(ax.images):
            if image.get_visible():
                cmap = image.get_cmap()
                style["artist_styles"].append({"id": f"{prefix}:image:{index}", "kind": "image",
                    "cmap": cmap.name, "clim": _safe(image.get_clim()),
                    "colormap_samples": [_safe(cmap(index / 16)) for index in range(17)],
                    "colormap_under": _safe(cmap.get_under()), "colormap_over": _safe(cmap.get_over()),
                    "colormap_bad": _safe(cmap.get_bad()),
                    "alpha": _safe(image.get_alpha())})
    return style


def analyze_figure(fig, spec=None, *, min_fontsize=7.0, min_tick_gap=1.0,
                   tolerance=1.0):
    """Report final visible text, layout, colours, and conservative collisions.

    All positions use a top-left origin in points (1/72 inch), even when the
    Figure uses a different raster DPI. The function draws but never resizes,
    relabels, or repositions artists. It accepts ordinary Matplotlib figures as
    well as FigCompose figures; layout cells require FigCompose diagnostics.
    """
    min_fontsize = _number(min_fontsize, "min_fontsize", positive=True)
    min_tick_gap = _number(min_tick_gap, "min_tick_gap")
    tolerance = _number(tolerance, "tolerance")
    if not hasattr(fig, "canvas") or not hasattr(fig, "axes"):
        raise TypeError("fig must be a Matplotlib Figure")
    spec = _spec_dict(spec if spec is not None else getattr(fig, "_data_visuals_quality_context", None))
    context = mpl.rc_context(getattr(fig, "_data_visuals_rcparams", {}))
    with context:
        fig.canvas.draw()
        return _analyze_drawn(fig, spec, min_fontsize, min_tick_gap, tolerance)


def _analyze_drawn(fig, spec, min_fontsize, min_tick_gap, tolerance):
    renderer = fig.canvas.get_renderer()
    scale, height = 72.0 / fig.dpi, fig.bbox.height
    width_pt, height_pt = float(fig.bbox.width * scale), float(height * scale)
    canvas = {"width_pt": width_pt, "height_pt": height_pt,
              "width_mm": width_pt * 25.4 / 72, "height_mm": height_pt * 25.4 / 72}
    diagnostics = getattr(fig, "_data_visuals_layout", {})
    cells = diagnostics.get("cells", {})
    subplots = {(item["row"], item["col"]): item for item in spec.get("subplots", [])}
    panels, elements, issues, limitations = [], [], [], [
        "Measured bounds and text collisions do not assess scientific meaning or visual quality.",
        "Arbitrary diagram nodes, connectors, data marks, and annotation collisions are not checked.",
    ]
    seen, axes_owners, tick_groups, regions, panel_elements = set(), {}, {}, [], {}
    tick_locations = {}
    actual_axes = {}
    for key, record in cells.items():
        key = tuple(key) if not isinstance(key, str) else tuple(map(int, key.split(",")))
        ax = record.get("axes")
        if ax is None or not ax.get_visible():
            continue
        actual_axes[key] = ax
        for role, axes in (("primary", [ax]), ("secondary", record.get("secondary_axes", [])),
                           ("colorbar", record.get("colorbar_axes", []))):
            for index, axis in enumerate(axes):
                axes_owners[id(axis)] = (key, role, index)
        zone = _box(ax.get_window_extent(renderer), height, scale)
        cell = {name: float(record["cell"][name]) for name in ("x", "y", "w", "h")}
        cell_area = cell["w"] * cell["h"]
        minimum = record.get("minimum", [])
        if isinstance(minimum, (list, tuple)):
            minimum = {"width": float(minimum[0]), "height": float(minimum[1])} if len(minimum) == 2 else {}
        panels.append({"id": f"{key[0]},{key[1]}", "row": int(key[0]), "col": int(key[1]),
                       "chart_type": subplots.get(key, {}).get("chart", record.get("chart_type", ax.name)), "cell": cell,
                       "data_zone": zone, "minimum": _safe(minimum),
                       "gutters": _safe(record.get("gutters", {})),
                       "measured_gutters": _safe(record.get("measured_gutters", {})),
                       "data_area_fraction": zone["w"] * zone["h"] / cell_area if cell_area else 0.0})
        if _outside(zone, cell, tolerance):
            issues.append(QualityIssue("data_zone_overflow", "error",
                f"Panel {key}: the live Axes viewport extends beyond its allocated cell; rebuild the canvas layout or move the Axes back inside its cell.",
                panel=key, bounds=[zone, cell]))
    # Bare Matplotlib axes have no allocated layout cell: report their actual
    # viewport as both cell and data region and state this limitation explicitly.
    for index, ax in enumerate(fig.axes):
        if id(ax) not in axes_owners:
            key = (index, 0)
            while key in actual_axes:
                key = (key[0] + 1, 0)
            axes_owners[id(ax)] = (key, "axes", index)
            if ax.get_visible():
                actual_axes[key] = ax
                zone = _box(ax.get_window_extent(renderer), height, scale)
                panels.append({"id": f"{key[0]},{key[1]}", "row": int(key[0]), "col": int(key[1]),
                    "chart_type": "colorbar" if hasattr(ax, "_colorbar") else ax.name,
                    "cell": dict(zone), "data_zone": zone, "minimum": {"width": 0.0, "height": 0.0},
                    "gutters": {side: 0.0 for side in ("left", "right", "top", "bottom")},
                    "data_area_fraction": 1.0})
                if not any("unmanaged" in item for item in limitations):
                    limitations.append("For unmanaged Matplotlib axes, cell equals the actual viewport; no layout-cell allocation is inferred.")
    canvas_box = {"x": 0.0, "y": 0.0, "w": width_pt, "h": height_pt}
    for ax in fig.axes:
        if ax.get_visible():
            zone = _box(ax.get_window_extent(renderer), height, scale)
            if _outside(zone, canvas_box, tolerance):
                key, role, index = axes_owners[id(ax)]
                issues.append(QualityIssue("axes_overflow", "error",
                    f"Panel {key} {role} Axes {index}: the viewport extends beyond the canvas; rebuild the layout, increase the canvas dimensions, or move the Axes inward.",
                    panel=key, bounds=[zone, canvas_box]))

    def add_text(text, identifier, kind, panel=None, *, tick_group=None, decoration=False):
        if id(text) in seen or not isinstance(text, Text) or not text.get_visible() or not text.get_text().strip():
            return
        seen.add(id(text))
        if mpl.colors.to_rgba(text.get_color(), text.get_alpha())[3] == 0:
            return
        from mpl_toolkits.mplot3d.art3d import Text3D
        if isinstance(text, Text3D):
            if not any("Text3D" in item for item in limitations):
                limitations.append("Text3D and projected 3D data artists have no reliable 2D text bounds and are not checked.")
            return
        bbox = _text_bbox(text, renderer)
        if bbox is None:
            return
        box = _box(bbox, height, scale)
        family = FontProperties(fname=mpl.font_manager.findfont(text.get_fontproperties())).get_name()
        element = {"id": identifier, "kind": kind, "panel": list(panel) if panel else None,
                   "text": str(text.get_text()), "bbox": box,
                   "font_size": float(text.get_fontsize()), "font_family": family}
        elements.append(element)
        if panel is not None:
            panel_elements.setdefault(panel, []).append(box)
        if box["x"] < -tolerance or box["y"] < -tolerance or box["x"] + box["w"] > width_pt + tolerance or box["y"] + box["h"] > height_pt + tolerance:
            issues.append(QualityIssue("text_overflow", "error", f"{identifier}: text extends beyond the canvas; enlarge the canvas or move the text inward.", panel=panel, bounds=[box]))
        if element["font_size"] < min_fontsize - 1e-6:
            issues.append(QualityIssue("font_size_below_minimum", "warning", f"{identifier}: {element['font_size']:g} pt text is below {min_fontsize:g} pt; increase its font size.", panel=panel, bounds=[box]))
        polygon = _polygon(text, box, renderer, scale) if tick_group is not None or decoration else None
        if tick_group is not None:
            tick_groups.setdefault(tick_group, []).append((element, polygon))
        if decoration:
            regions.append({"id": identifier, "kind": kind, "panel": panel, "bbox": box,
                            "polygon": polygon})

    legend_owners = {}
    for key, record in cells.items():
        key = tuple(key) if not isinstance(key, str) else tuple(map(int, key.split(",")))
        for artist in record.get("legends", []):
            if isinstance(artist, Legend):
                legend_owners[id(artist)] = key
    shared_ids = {id(item) for item in diagnostics.get("shared_legends", []) if isinstance(item, Legend)}
    legend_counter = {}
    legends = list(fig.legends) + [ax.get_legend() for ax in fig.axes if ax.get_legend() is not None]
    for legend in legends:
        if not legend.get_visible() or (legend.axes is not None and not legend.axes.get_visible()):
            continue
        panel = legend_owners.get(id(legend))
        if panel is None and id(legend) not in shared_ids and legend.axes is not None:
            panel = axes_owners[id(legend.axes)][0]
        scope = f"panel:{panel[0]},{panel[1]}:legend" if panel is not None else "figure:legend"
        index = legend_counter.get(scope, 0)
        legend_counter[scope] = index + 1
        identifier = f"{scope}:{index}"
        for text_index, text in enumerate(legend.get_texts()):
            add_text(text, f"{identifier}:text:{text_index}", "legend", panel)
        add_text(legend.get_title(), f"{identifier}:title", "legend_title", panel)
        bbox = legend.get_window_extent(renderer)
        if _finite_bbox(bbox):
            box = _box(bbox, height, scale)
            regions.append({"id": identifier, "kind": "legend", "panel": panel,
                            "bbox": box, "polygon": _rectangle(box)})

    custom_owners = {id(artist): key for key, record in cells.items()
                     for artist in record.get("custom_artists", [])}
    header_ids = {id(item) for item in diagnostics.get("header_artists", [])}
    title = spec.get("title", {}).get("text")
    for index, text in enumerate(fig.texts):
        panel = custom_owners.get(id(text))
        kind = "figure_title" if title and text.get_text() == title else "figure_text"
        add_text(text, f"figure:text:{index}", kind, panel,
                 decoration=panel is None and (id(text) in header_ids or not cells))
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        panel, role, index = axes_owners[id(ax)]
        prefix = f"panel:{panel[0]},{panel[1]}:{role}:{index}"
        for title_position, text in (("center", ax.title), ("left", ax._left_title), ("right", ax._right_title)):
            add_text(text, f"{prefix}:title:{title_position}", "panel_title", panel, decoration=True)
        axes_visible = ax._axis3don if ax.name == "3d" else ax.axison
        if axes_visible:
            for axis_name, axis in ax._axis_map.items():
                if not axis.get_visible():
                    continue
                add_text(axis.label, f"{prefix}:{axis_name}:label", "axis_label", panel, decoration=True)
                add_text(axis.get_offset_text(), f"{prefix}:{axis_name}:offset", "axis_offset", panel, decoration=True)
                # Only native ticks within the view interval are drawn. Using
                # get_ticklabels alone would report hidden off-range ticks.
                if ax.name == "3d":
                    # Re-running _update_ticks here resets projected native
                    # label positions to unprojected 2D data coordinates.
                    low, high = sorted(axis.get_view_interval())
                    ticks = [tick for tick in axis.majorTicks + axis.minorTicks
                             if low - 1e-12 <= tick.get_loc() <= high + 1e-12]
                else:
                    ticks = axis._update_ticks()
                for tick_index, tick in enumerate(ticks):
                    for side, text in (("1", tick.label1), ("2", tick.label2)):
                        group = (panel, role, index, axis_name, side) if ax.name == "rectilinear" else None
                        identifier = f"{prefix}:{axis_name}:tick:{tick_index}:{side}"
                        tick_locations[identifier] = float(tick.get_loc())
                        add_text(text, identifier, "tick_label", panel,
                                 tick_group=group, decoration=True)
        if ax.name == "3d" and not any("Projected axis" in item for item in limitations):
            limitations.append("Projected axis ticks are measured, but 3D tick spacing and internal data/text collisions are not checked.")
        for text_index, text in enumerate(ax.texts):
            add_text(text, f"{prefix}:text:{text_index}", "annotation" if isinstance(text, Annotation) else "panel_text", panel)
    for key, record in cells.items():
        key = tuple(key) if not isinstance(key, str) else tuple(map(int, key.split(",")))
        for index, artist in enumerate(record.get("custom_artists", [])):
            # Explicit returned artists may be added directly to Figure rather
            # than Axes.texts/figure.texts. Retain their declared panel owner.
            if isinstance(artist, Text):
                add_text(artist, f"panel:{key[0]},{key[1]}:custom:text:{index}", "panel_text", key)

    for group, labels in tick_groups.items():
        dimension = "x" if group[3] == "x" else "y"
        labels.sort(key=lambda item: item[0]["bbox"][dimension] + item[0]["bbox"]["w" if dimension == "x" else "h"] / 2)
        repeated = {}
        for element, _ in labels:
            previous = repeated.get(element["text"].strip())
            if previous is not None and tick_locations[previous["id"]] != tick_locations[element["id"]]:
                issues.append(QualityIssue("duplicate_tick_labels", "warning",
                    f"{previous['id']} and {element['id']}: distinct tick positions display the same label {element['text']!r}; use a more precise numeric format or fewer ticks.",
                    panel=group[0], bounds=[previous["bbox"], element["bbox"]]))
            else:
                repeated[element["text"].strip()] = element
        for (first, polygon_a), (second, polygon_b) in zip(labels, labels[1:]):
            bounds = [first["bbox"], second["bbox"]]
            if _polygon_overlap(polygon_a, polygon_b, tolerance):
                issues.append(QualityIssue("tick_label_overlap", "warning", f"{first['id']} and {second['id']}: adjacent tick labels overlap; use fewer ticks, shorter labels, rotation, or a wider panel.", panel=group[0], bounds=bounds))
            elif _polygon_gap(polygon_a, polygon_b) < min_tick_gap - 1e-6:
                issues.append(QualityIssue("tick_label_gap", "warning", f"{first['id']} and {second['id']}: tick-label clearance is below {min_tick_gap:g} pt; use fewer ticks or increase panel space.", panel=group[0], bounds=bounds))

    # Compare owned decoration regions, never every native annotation or data
    # artist. Within a legend its text and glyphs intentionally share a block.
    for first, second in combinations(regions, 2):
        if (first["panel"] == second["panel"] and first["kind"] in ("tick_label", "axis_offset")
                and second["kind"] in ("tick_label", "axis_offset")):
            continue
        if not _intersects(first["bbox"], second["bbox"], tolerance):
            continue
        if not _polygon_overlap(first["polygon"], second["polygon"], tolerance):
            continue
        panel = first["panel"] if first["panel"] == second["panel"] else None
        issues.append(QualityIssue("decoration_overlap", "warning", f"{first['id']} and {second['id']}: visible decorations overlap; adjust legend placement, labels, or canvas dimensions.", panel=panel, bounds=[first["bbox"], second["bbox"]]))
    for panel in panels:
        key = (panel["row"], panel["col"])
        box = _union(panel_elements.get(key, []))
        panel["decoration_bbox"] = dict(zip(("x", "y", "w", "h"), map(float, box))) if box else None
    style = _style(fig, spec, diagnostics)
    font = style.get("font", {})
    requested, resolved = font.get("requested"), font.get("resolved")
    primary = requested.split(",", 1)[0].strip().strip("\"'") if isinstance(requested, str) else None
    if primary and primary.lower() not in ("serif", "sans-serif", "monospace", "cursive", "fantasy") and resolved and primary.casefold() != str(resolved).casefold():
        issues.append(QualityIssue("font_substitution", "info", f"Requested font {requested!r} resolved to {resolved!r}; install the requested font to reproduce its typography."))
    return FigureReport(canvas=canvas, panels=panels, elements=elements, issues=issues,
                        style=style, limitations=limitations)


def write_debug(fig, report, path, *, dpi=150):
    """Save a fixed-canvas geometry overlay, then remove all temporary artists."""
    dpi = _number(dpi, "dpi", positive=True)
    destination = Path(path)
    if destination.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("debug output must use .png, .svg, or .pdf")
    overlays = []
    width, height = report.canvas["width_pt"], report.canvas["height_pt"]

    def rectangle(box, color, linewidth=.7, linestyle="-"):
        if not box:
            return
        artist = Rectangle((box["x"] / width, 1 - (box["y"] + box["h"]) / height),
                           box["w"] / width, box["h"] / height,
                           transform=fig.transFigure, fill=False, edgecolor=color,
                           linewidth=linewidth, linestyle=linestyle, zorder=10000,
                           clip_on=False)
        artist.set_in_layout(False)
        fig.add_artist(artist)
        overlays.append(artist)

    try:
        for panel in report.panels:
            rectangle(panel.get("cell"), "#3975b9", linestyle="--")
            rectangle(panel.get("data_zone"), "#00856a")
        for issue in report.issues:
            if issue.severity == "info":
                continue
            for box in issue.bounds:
                rectangle(box, "#c83737" if issue.severity == "error" else "#d17a00", 1.0)
        rc = {**getattr(fig, "_data_visuals_rcparams", {}), "savefig.bbox": None,
              "savefig.pad_inches": 0, "savefig.dpi": dpi}
        with mpl.rc_context(rc):
            fig.savefig(destination, dpi=dpi, bbox_inches=None, pad_inches=0)
    finally:
        for artist in reversed(overlays):
            artist.remove()
