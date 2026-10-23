"""Managed Matplotlib callbacks: build once, update on resize, measure artists."""
from __future__ import annotations

import math
from copy import copy

from data_visuals.core.panel import CustomPanel, PanelContext, PanelResult
from data_visuals.layout.placement import LayoutError


def create_panel_axes(fig, sp, rect):
    """Allocate the declared native projection while keeping panel ownership."""
    panel = sp.get("_custom_panel") if sp["chart"] == "custom" else None
    if sp["chart"] == "custom" and not isinstance(panel, CustomPanel):
        raise TypeError("A custom subplot requires its runtime CustomPanel; use Figure[row, col].custom(draw)")
    projection = panel.projection if panel else ("polar" if sp["chart"] == "radar" else None)
    options = dict(panel.axes_options) if panel else {}
    return fig.add_axes(rect, projection=projection,
                        label=f"data_visuals:{sp['row']},{sp['col']}", **options)


def position_axes(ax, zone, width, height):
    """Return the native active viewport (polar/3D/equal aspects may shrink it)."""
    ax.set_position((zone["x"] / width, 1 - (zone["y"] + zone["h"]) / height,
                     zone["w"] / width, zone["h"] / height))
    ax.apply_aspect()
    bounds = ax.get_position()
    return {"x": bounds.x0 * width, "y": (1 - bounds.y1) * height,
            "w": bounds.width * width, "h": bounds.height * height}


def panel_context(panel, sp, cfg, maps, width, height):
    fonts = dict(sp["font_sizes"])
    fonts.update(body=max(8.0, fonts["axis_label"]), annotation=max(8.0, fonts["tick"]))
    context_maps = {group: dict(colors) for group, colors in maps.items()}
    colors = context_maps.get(panel.color_group, {})
    for raw, canonical in sp["data"].get("category_aliases", {}).items():
        if canonical in colors:
            colors[raw] = colors[canonical]
    return PanelContext(
        payload=panel.payload, font_family=cfg.font_family, font_sizes=fonts,
        text_color=cfg.text_color, background=cfg.background,
        palette=tuple(cfg.get_palette()), color_map=colors,
        color_maps=context_maps, width_pt=width, height_pt=height,
        line_width=cfg.axis_domain_width,
    )


def _legend_handles(result, sp, context):
    """Resolve display-name aliases without changing the drawn artists."""
    aliases = sp["data"].get("category_aliases", {})
    handles = []
    for original in result.legend_handles:
        label = original.get_label()
        key = getattr(original, "_paperfig_legend_key", label)
        if key not in context.color_map:
            matches = [value for value in context.color_map if str(value) == str(key)]
            if len(matches) == 1:
                key = matches[0]
        canonical = aliases.get(key, key)
        # Legend glyphs can be detached proxies, or live node artists. Copy
        # before changing their label/key so semantic aliases cannot alter the
        # diagram, and repeated trials remain independent.
        handle = copy(original)
        handle._paperfig_legend_key = canonical
        if canonical != key and label == str(key):
            handle.set_label(str(canonical))
        handles.append(handle)
    return handles


def prepare_custom_panels(fig, subplots, cfg, maps, width, height):
    """Build before measuring shared legends, retaining these same axes later.

    The initial box is provisional. Size-dependent content uses result.layout,
    called again with the actual viewport after headers and gutters are known.
    """
    records, primary_axes = {}, {}
    if not any(sp["chart"] == "custom" for sp in subplots):
        return records, primary_axes
    # Build primary axes in panel order even when a diagram needs to be drawn
    # early to supply legend handles. Preserve the statistics-only path.
    for sp in subplots:
        box = sp["geometry"]
        primary_axes[sp["row"], sp["col"]] = create_panel_axes(fig, sp,
            (box["x"] / width, 1 - (box["y"] + box["h"]) / height,
             box["w"] / width, box["h"] / height),
        )
    for sp in subplots:
        if sp["chart"] != "custom":
            continue
        panel = sp.get("_custom_panel")
        if not isinstance(panel, CustomPanel):
            raise TypeError("A custom subplot requires its runtime CustomPanel; use Figure[row, col].custom(draw)")
        box = sp["geometry"]
        ax = primary_axes[sp["row"], sp["col"]]
        if panel.limits is not None:
            for name, limits in zip(("x", "y", "z"), panel.limits):
                getattr(ax, f"set_{name}lim")(limits)
        elif panel.projection in (None, "rectilinear"):
            for name in ("x", "y"):
                if (f"{name}lim" not in panel.axes_options
                        and panel.axes_options.get(f"{name}scale", "linear") == "linear"):
                    getattr(ax, f"set_{name}lim")((0, 1))
        ax.set_facecolor(cfg.background)
        if panel.axes == "off":
            ax.set_axis_off()
            ax.grid(False)
        context = panel_context(panel, sp, cfg, maps, box["w"], box["h"])
        axes_before = tuple(fig.axes)
        result = panel.draw(ax, context)
        if tuple(fig.axes) != axes_before:
            raise ValueError("custom draw must use the supplied Axes; extra axes need their own managed panels")
        if result is None:
            result = PanelResult()
        if not isinstance(result, PanelResult):
            raise TypeError("custom draw must return PanelResult or None")
        for artist in result.artists:
            if artist.figure is not fig:
                raise ValueError("PanelResult.artists must be added to the supplied Axes or Figure before return")
        records[sp["row"], sp["col"]] = {
            "axes": ax, "panel": panel, "result": result, "context": context,
            "handles": _legend_handles(result, sp, context),
        }
    return records, primary_axes


def position_custom(record, zone, sp, cfg, maps, width, height):
    """Fit declared aspect, apply native aspect, then update content in points.

    The returned zone is the actual active Axes box, including Matplotlib's
    equal-aspect adjustment. Geometry diagnostics and minimum-size checks must
    use this box rather than the larger nominal allocation.
    """
    panel, ax = record["panel"], record["axes"]
    allocation = dict(zone)
    zone = dict(zone)
    if panel.box_aspect is not None:
        ratio = panel.box_aspect
        fitted_w = min(zone["w"], zone["h"] * ratio)
        fitted_h = fitted_w / ratio
        zone["x"] += (zone["w"] - fitted_w) / 2
        zone["y"] += (zone["h"] - fitted_h) / 2
        zone["w"], zone["h"] = fitted_w, fitted_h
    actual = position_axes(ax, zone, width, height)
    if (panel.box_aspect is not None and
            abs(actual["w"] / actual["h"] - panel.box_aspect) > 1e-5):
        raise ValueError("custom box_aspect conflicts with native Axes aspect; choose one aspect constraint")
    min_w, min_h = panel.min_size
    if actual["w"] < min_w - .01 or actual["h"] < min_h - .01:
        # Include the amount of empty space required by a fixed aspect so that
        # the physical solver can increase height instead of guessing blindly.
        needed_w, needed_h = max(actual["w"], min_w), max(actual["h"], min_h)
        aspect = panel.box_aspect
        if aspect is None and (ax.get_aspect() != "auto" or ax.get_box_aspect() is not None):
            aspect = actual["w"] / actual["h"]
        if aspect is not None:
            needed_w = max(needed_w, needed_h * aspect)
            needed_h = max(needed_h, needed_w / aspect)
        raise LayoutError(
            f"Custom panel needs at least {min_w:g} x {min_h:g} pt of actual content space; "
            "increase canvas size or relax its aspect constraint.",
            axis="width" if needed_w > allocation["w"] + .01 else "height",
            required_width=needed_w, required_height=needed_h,
            subplot=(sp["row"], sp["col"]),
        )
    context = panel_context(panel, sp, cfg, maps, actual["w"], actual["h"])
    record["context"] = context
    if record["result"].layout is not None:
        record["result"].layout(ax, context)
    return actual


def custom_bounds(record, renderer):
    """Explicit artists may live at Figure level or opt out of Axes layout."""
    boxes = []
    if record is None:
        return boxes
    if record["axes"].name == "3d" and record["axes"]._axis3don:
        # Axes3D always calls its axes' tight-bbox in layout-only mode, which
        # omits the axis labels even for get_tightbbox(for_layout_only=False).
        # Their window extents are valid after draw and must reserve space.
        for axis in record["axes"]._axis_map.values():
            if axis.get_visible() and axis.label.get_visible() and axis.label.get_text():
                boxes.append(axis.label.get_window_extent(renderer))
    for artist in record["result"].artists:
        if not artist.get_visible():
            continue
        # Native 3D geometry is projected during draw; its inherited 2D window
        # extent can be infinite or describe unprojected data coordinates.
        # Axes3D.get_tightbbox measures the projected axes decorations instead.
        if _is_3d_artist(artist):
            continue
        box = artist.get_window_extent(renderer)
        if not all(math.isfinite(v) for v in box.extents):
            raise ValueError("Custom panel artist bounds must be finite")
        boxes.append(box)
    # Text.get_window_extent omits its padded background. Include those boxes
    # even for text discovered by Axes when draw() returned None.
    text_artists = list(record["axes"].texts) + list(record["result"].artists)
    seen = set()
    for artist in text_artists:
        if id(artist) in seen or not artist.get_visible() or _is_3d_artist(artist):
            continue
        seen.add(id(artist))
        getter = getattr(artist, "get_bbox_patch", None)
        patch = getter() if getter is not None else None
        if patch is not None and patch.get_visible():
            artist.update_bbox_position_size(renderer)
            box = patch.get_window_extent(renderer)
            if not all(math.isfinite(v) for v in box.extents):
                raise ValueError("Custom panel text-box bounds must be finite")
            boxes.append(box)
    return boxes


def _is_3d_artist(artist):
    from mpl_toolkits.mplot3d import art3d
    return isinstance(artist, (art3d.Line3D, art3d.Line3DCollection, art3d.Poly3DCollection,
                               art3d.Path3DCollection, art3d.Patch3D, art3d.Text3D))


def place_custom_title(record, renderer, cfg, height):
    """Place managed headings above content that extends beyond the axes.

    Exclude the managed title from content measurement to avoid a feedback
    loop. Outside annotations occupy real space before the title/top legend.
    """
    ax = record["axes"]
    title = ax.title
    visible = title.get_visible()
    title.set_visible(False)
    try:
        if ax.name == "3d":
            # Tick/axis-label projections are updated only by a draw. Measuring
            # their previous positions after a resize gives stale gutters.
            ax.figure.canvas.draw()
        boxes = [ax.get_tightbbox(renderer, for_layout_only=True)]
        boxes.extend(custom_bounds(record["custom"], renderer))
    finally:
        title.set_visible(visible)
    from matplotlib.transforms import Bbox
    content = Bbox.union([box for box in boxes if box is not None])
    record["content_bbox"] = content
    fs, zone = record["subplot"]["font_sizes"], record["zone"]
    overflow = max(0.0, content.y1 - (height - zone["y"]))
    local = record["local_legend"]
    if local.height and record["legend_options"].get("position", "top") == "top":
        gap = local.height + record["legend_gap"] + fs["tick"] * cfg.title_legend_gap
    else:
        gap = fs["title"] * cfg.subplot_title_gap
    x = title.get_position()[0]
    ax.set_title(title.get_text(), fontproperties=title.get_fontproperties().copy(),
                 color=title.get_color(), y=1.0, va="bottom", pad=overflow + gap)
    title.set_y(1.0)  # Axes3D.set_title applies a native .92 factor; PaperFig owns this header.
    title.set_x(x)
