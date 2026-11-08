"""Concentric score tracks with exact angular geometry and managed styling."""
from __future__ import annotations

import math
import textwrap

import numpy as np
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Patch, Wedge

from data_visuals.core.identity import numeric_format_function
from data_visuals.renderer.mpl.presentation import blend
from .helpers import frame, grouped, ordered, series_color, series_style


EXTENT = 1.44
INNER, OUTER = .34, .985


def _xy(radius, angle):
    theta = np.deg2rad(angle)
    return np.array((radius * np.cos(theta), radius * np.sin(theta)))


def rounded_band(radius, start, span, width, color, *, rounded=True):
    """Return a band whose visible tangent rays retain the exact score span.

    Unlike round-ended strokes, cap centres are inset by asin(half_width / R).
    Very short values retain flat exact endpoints when two round caps cannot fit.
    """
    if span <= 0:
        return []
    end = start - span
    middle, half = radius - width / 2, width / 2
    inset = np.rad2deg(np.arcsin(half / middle))
    if not rounded or span <= 2 * inset:
        return [Wedge((0, 0), radius, end, start, width=width,
                      facecolor=color, edgecolor="none")]
    return [
        Wedge((0, 0), radius, end + inset, start - inset, width=width,
              facecolor=color, edgecolor="none"),
        Circle(_xy(middle, start - inset), half, facecolor=color, edgecolor="none"),
        Circle(_xy(middle, end + inset), half, facecolor=color, edgecolor="none"),
    ]


def _fraction(value, low, high):
    # Bounds may be finite while their difference overflows float64. Scale
    # before subtracting; this is geometry, not a transformation of stored data.
    scale = max(abs(low), abs(high), 1.0)
    return (value / scale - low / scale) / (high / scale - low / scale)


def _draw_circular_bar(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x, y, group = mapping["x"], mapping["y"], mapping["group"]
    objects = opts.get("order") or ordered(df[x])
    groups = grouped(df, group, opts.get("series_order"))
    payload = sp.get("derived_data", {}).get("circular_bar", {})
    summaries = {item["group"]: item["value"] for item in payload.get("summaries", [])}
    low, high = map(float, opts.get("value_range", (0, 100)))
    rounded = opts.get("rounded", True)
    count, series_count = len(objects), len(groups)
    position = opts.get("summary_position", "auto")
    top_summary = opts.get("summary") == "mean" and (position == "top" or (position == "auto" and cfg.showcase))
    header_rows = math.ceil(series_count / 4) if top_summary else 0
    plot_extent = 1.30 if top_summary else EXTENT
    header_extra = .40 * header_rows
    pitch = (OUTER - INNER) / count
    band = .75 * pitch
    sector = 360.0 / series_count
    gap = min(12.0, sector * .18)
    span = sector - gap
    size = max(8.0, sp["font_sizes"].get("tick", 8.0))
    ink = cfg.text_color
    muted = cfg.muted_text_color
    background_marks, data_marks, rules = [], [], []
    text_artists, ids, labels, ticks, handles, header_items = [], [], [], [], [], []
    formatter = numeric_format_function(opts.get("value_format", ".1f"), "value_format")
    tick_format = (numeric_format_function(opts["value_format"], "value_format")
                   if opts.get("value_format") else lambda value: f"{value:g}")

    def text(value, **kwargs):
        artist = ax.text(0, 0, value, fontsize=size, fontfamily=cfg.font_family,
                         color=ink, clip_on=False, **kwargs)
        text_artists.append(artist)
        return artist

    ax.set_xlim(-plot_extent, plot_extent)
    ax.set_ylim(-plot_extent, plot_extent + header_extra)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    ax.grid(False)
    ax.add_patch(Circle((0, 0), 1.012, facecolor=cfg.background,
                        edgecolor=blend(ink, cfg.background, .90), linewidth=.45, zorder=0))

    for column, (key, sub) in enumerate(groups):
        color = series_color(key, column, cfg, color_map or {}, opts)
        style = series_style(key, opts)
        display = style.get("label", str(key))
        start = 90 - gap / 2 - column * sector
        centre_angle = 90 - (column + .5) * sector
        values = sub.set_index(x).loc[objects, y].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values < low).any() or (values > high).any():
            raise ValueError("Circular scores must remain finite and inside value_range.")
        for row, value in enumerate(values):
            radius = INNER + (row + 1) * pitch
            background_marks.extend(rounded_band(radius, start, span, band,
                                                  cfg.support_fill(color), rounded=rounded))
            data_marks.extend(rounded_band(radius, start, span * _fraction(value, low, high),
                                           band, color, rounded=rounded))
        for fraction in (0.0, .5, 1.0):
            angle = start - span * fraction
            rules.append((_xy(1.003, angle), _xy(1.025, angle)))
            # Avoid low+high overflow when formatting the midpoint.
            value = low if fraction == 0 else high if fraction == 1 else low / 2 + high / 2
            ticks.append((text(tick_format(value), ha="center", va="center"), angle, fraction))

        name = text(display, ha="center", va="center", fontweight=cfg.cell_title_weight)
        summary = None
        if opts.get("summary") == "mean" and not top_summary:
            if key not in summaries:
                raise ValueError("Circular mean summaries must be supplied by the compute layer.")
            summary = text(f"Mean {formatter(summaries[key])}", ha="center", va="center",
                           fontstyle="italic")
            summary.set_color(cfg.annotation_color(color))
        labels.append((name, summary, centre_angle, display))
        if top_summary:
            if key not in summaries:
                raise ValueError("Circular mean summaries must be supplied by the compute layer.")
            columns = min(4, series_count)
            row, column_index = divmod(column, columns)
            x0 = -plot_extent + (column_index + .5) * (2 * plot_extent / columns)
            y0 = plot_extent + header_extra - .04 - row * .40
            heading = text(display, ha="center", va="center", fontweight=cfg.cell_title_weight)
            heading.set_fontsize(max(8.0, sp["font_sizes"]["axis_label"]))
            value = text(formatter(summaries[key]), ha="center", va="center", fontweight="bold")
            value.set_fontsize(max(12.0, sp["font_sizes"]["axis_label"] * (3 if cfg.showcase else 1.8)))
            caption = text(f"Mean · {tick_format(low)}–{tick_format(high)}", ha="center", va="center")
            caption.set_fontsize(max(8.0, sp["font_sizes"]["tick"]))
            caption.set_color(muted)
            half = (2 * plot_extent / columns) * .34
            support_line, = ax.plot([x0 - half, x0 + half], [y0] * 2,
                                   color=cfg.support_fill(color), linewidth=3, solid_capstyle="butt", zorder=3)
            value_line, = ax.plot([x0 - half, x0 - half + 2 * half * _fraction(summaries[key], low, high)],
                                 [y0] * 2, color=color, linewidth=3, solid_capstyle="butt", zorder=4)
            header_items.append((heading, value, caption, support_line, value_line, x0, y0, display, columns))
        handle = Patch(facecolor=color, edgecolor="none", label=display)
        handle._figcompose_legend_key = key
        handles.append(handle)

    ax.add_collection(PatchCollection(background_marks, match_original=True, zorder=1))
    ax.add_collection(PatchCollection(data_marks, match_original=True, zorder=2))
    ax.add_collection(LineCollection(rules, colors=cfg.support_line_color,
                                      linewidths=.5, zorder=3))

    for row, key in enumerate(objects):
        ids.append((text(str(key), ha="center", va="center"), INNER + (row + 1) * pitch - band / 2))
    id_heading = text("ID", ha="center", va="center")
    id_heading.set_color(muted)
    footer = text("Independent scales · Filled angle encodes value", ha="center", va="center")
    footer.set_color(muted)

    centre_objects = []
    if opts.get("center", "count") == "count":
        if "object_count" not in payload or "series_count" not in payload:
            raise ValueError("Circular centre counts must be supplied by the compute layer.")
        ax.add_patch(Circle((0, 0), .292, facecolor=blend(ink, cfg.background, .98),
                            edgecolor=blend(ink, cfg.background, .90), linewidth=.5, zorder=3))
        hero = text(str(payload["object_count"]), ha="center", va="center", zorder=4)
        unit = text(opts.get("object_label", "OBJECTS"), ha="center", va="center", zorder=4)
        series = text(f"{payload['series_count']} {opts.get('series_label', 'SERIES')}",
                      ha="center", va="center", zorder=4)
        series.set_color(muted)
        centre_objects = [hero, unit, series]

    # Thin rings remain representable without shrinking any physical text.
    # ID labels are selectively hidden when either pitch or gap is too small.
    ax._data_visuals_minimum_plot = (max(155.0, count * 6.0), max(155.0, count * 6.0))
    ax._data_visuals_bounds_artists = text_artists

    def update_layout():
        ax.apply_aspect()
        renderer = ax.figure.canvas.get_renderer()
        box = ax.get_window_extent(renderer)
        scale_pt = min(box.width / (2 * plot_extent), box.height / (2 * plot_extent + header_extra)) * 72 / ax.figure.dpi
        prop = FontProperties(family=cfg.font_family, size=size)

        def width(value):
            return renderer.get_text_width_height_descent(value, prop, ismath=False)[0] * 72 / ax.figure.dpi

        for heading, value, caption, support_line, value_line, x0, y0, display, columns in header_items:
            available = (2 * plot_extent / columns) * scale_pt * .88
            characters = max(4, int(available / (heading.get_fontsize() * .46)))
            heading.set_text(textwrap.fill(str(display), width=characters,
                                           break_long_words=False, break_on_hyphens=False))
            cursor = y0
            for artist in (heading, value, caption):
                height_pt = artist.get_window_extent(renderer).height * 72 / ax.figure.dpi
                artist.set_position((x0, cursor - height_pt / (2 * scale_pt)))
                cursor -= (height_pt + 2) / scale_pt
            cursor -= 3 / scale_pt
            support_line.set_ydata([cursor] * 2)
            value_line.set_ydata([cursor] * 2)

        stride = max(1, math.ceil((size + 1.5) / (pitch * scale_pt)))
        visible_ids = []
        for row, (artist, radius) in enumerate(ids):
            horizontal_room = 2 * radius * np.sin(np.deg2rad(gap / 2)) * scale_pt
            visible = row % stride == 0 and width(artist.get_text()) + 1 <= horizontal_room
            artist.set_visible(visible)
            artist.set_position((0, radius))
            artist.set_color(muted)
            if visible:
                visible_ids.append(objects[row])
        id_heading.set_visible(bool(visible_ids))
        id_heading.set_position((0, 1.135))
        id_heading.set_text("ID")
        middle = low / 2 + high / 2
        scale_text = "–".join(tick_format(value) for value in (low, middle, high))
        scale_label = opts.get("value_label", "Each sector")
        note = f"{scale_label}: {scale_text} · Filled angle encodes value"
        if len(visible_ids) < count:
            note = f"{scale_label}: {scale_text} · ID labels sampled"
        footer.set_text(textwrap.fill(note, width=max(18, int(box.width * 72 / ax.figure.dpi / (size * .43))),
                                      break_long_words=False, break_on_hyphens=False))

        for name, summary, angle, display in labels:
            if series_count <= 4:
                if series_count == 1:
                    # The full-circle track leaves useful corner space while
                    # its bottom midpoint must stay available for its tick.
                    anchor = np.array((-.95, 1.16))
                elif series_count == 4:
                    sx, sy = np.sign(_xy(1, angle))
                    anchor = np.array((.95 * sx, 1.16 * sy))
                else:
                    anchor = _xy(1.235, angle)
                # Wrap words in the available side wedge; never shrink text.
                available = max(40.0, (EXTENT - abs(anchor[0])) * scale_pt * 1.9)
                characters = max(6, int(available / max(size * .42, 1)))
                name.set_text(textwrap.fill(str(display), width=characters,
                                           break_long_words=False, break_on_hyphens=False))
                extra_lines = name.get_text().count("\n")
                if extra_lines:
                    anchor[1] += np.sign(anchor[1]) * extra_lines * size / (2 * scale_pt)
                name.set_rotation(0)
                name.set_position(anchor)
                if summary:
                    line_count = name.get_text().count("\n") + 1
                    summary.set_rotation(0)
                    summary.set_position((anchor[0], anchor[1] - (size * line_count / 2 + size * .7) / scale_pt))
            else:
                rotation = angle % 180 - 90
                tangent_width = max(35.0, np.deg2rad(sector) * 1.22 * scale_pt * .85)
                characters = max(5, int(tangent_width / max(size * .43, 1)))
                name.set_text(textwrap.fill(str(display), width=characters,
                                           break_long_words=False, break_on_hyphens=False))
                name.set_position(_xy(1.30, angle))
                name.set_rotation(rotation)
                name.set_rotation_mode("anchor")
                if summary:
                    summary.set_position(_xy(1.115, angle))
                    summary.set_rotation(rotation)
                    summary.set_rotation_mode("anchor")
            if summary:
                summary.set_fontsize(size)

        for artist, angle, fraction in ticks:
            artist.set_position(_xy(1.08, angle))
            artist.set_color(muted)
            # All sectors share the declared range. On many-sector charts a
            # compact common scale key replaces repeated endpoint labels;
            # the three tick marks on each sector remain visible.
            artist.set_visible(series_count <= 4 and not (series_count in (2, 3) and fraction == .5))

        if centre_objects:
            hero, unit, series = centre_objects
            diameter = .55 * scale_pt
            digits = max(1, len(hero.get_text()))
            hero_size = max(12.0, min(32.0, diameter * .43, diameter / (digits * .64)))
            hero.set_fontsize(hero_size)
            caption_width = max(width(unit.get_text()), width(series.get_text()))
            if caption_width > diameter * .93:
                needed = caption_width * (2 * EXTENT) / (.55 * .93)
                ax._data_visuals_minimum_plot = tuple(max(old, needed) for old in ax._data_visuals_minimum_plot)
            gap_pt = 1.5
            def height(artist):
                return artist.get_window_extent(renderer).height * 72 / ax.figure.dpi
            # Stack the measured text blocks, rather than mixing fixed data
            # offsets with a changing hero size. A small hole can omit the
            # redundant series count while retaining the requested object count.
            shown = [hero, unit, series]
            total = sum(height(artist) for artist in shown) + gap_pt * 2
            if total > diameter * .94:
                hero_size = max(12.0, min(hero_size, diameter * .94 - height(unit) - height(series) - 2 * gap_pt))
                hero.set_fontsize(hero_size)
                total = sum(height(artist) for artist in shown) + gap_pt * 2
            series.set_visible(total <= diameter * .94)
            if not series.get_visible():
                shown = [hero, unit]
                total = sum(height(artist) for artist in shown) + gap_pt
            cursor = total / 2
            for artist in shown:
                block = height(artist)
                artist.set_position((0, (cursor - block / 2) / scale_pt))
                cursor -= block + gap_pt

        # The note is a separate measured decoration below the outer labels,
        # not another annotation competing for the bottom sector's space.
        decoration_boxes = [artist.get_window_extent(renderer)
                            for name, summary, _, _ in labels
                            for artist in (name, summary) if artist is not None and artist.get_visible()]
        bottom = min([box.y0, *(box.y0 for box in decoration_boxes)])
        footer_height = footer.get_window_extent(renderer).height
        footer_y = bottom - footer_height / 2 - 5 * ax.figure.dpi / 72
        footer.set_position((0, ax.transData.inverted().transform((box.x0, footer_y))[1]))
        ax._figcompose_circular_diagnostics = {"shown_ids": list(visible_ids), "object_count": count,
                                              "series_count": series_count}

    ax._figcompose_layout_callback = update_layout
    update_layout()
    return handles
