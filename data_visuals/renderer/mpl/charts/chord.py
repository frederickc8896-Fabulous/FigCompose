"""Weighted undirected ribbons, with physical label and tick placement."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.path import Path
from matplotlib.patches import Patch, PathPatch, Wedge

from .helpers import frame, series_color, series_style


def polar(angle, radius=.885):
    radians = np.deg2rad(angle)
    return radius * np.array((np.cos(radians), np.sin(radians)))


def ribbon(first, second):
    """The original sampled endpoints joined by cubic Bézier curves."""
    left = np.array([polar(angle) for angle in np.linspace(*first, 13)])
    right = np.array([polar(angle) for angle in np.linspace(*second, 13)])
    vertices, codes = [left[0]], [Path.MOVETO]
    for point in left[1:]:
        vertices.append(point)
        codes.append(Path.LINETO)
    vertices.extend((left[-1] * .18, right[0] * .18, right[0]))
    codes.extend((Path.CURVE4,) * 3)
    for point in right[1:]:
        vertices.append(point)
        codes.append(Path.LINETO)
    vertices.extend((right[-1] * .18, left[0] * .18, left[0]))
    codes.extend((Path.CURVE4,) * 3)
    vertices.append(left[0])
    codes.append(Path.CLOSEPOLY)
    return Path(vertices, codes)


def chord_geometry(df, mapping, payload):
    """Allocate both endpoints on one scale without overflowing small weights."""
    source, target, value = (mapping[key] for key in ("source", "target", "value"))
    names = payload["node_order"]
    totals = {item["id"]: item["total"] for item in payload["nodes"]}
    gap = min(5.0, 36.0 / len(names))
    available = 360.0 - gap * len(names)
    incident = payload["incident_total"]
    scale = available / incident if incident >= np.finfo(float).tiny else math.inf

    def span(weight):
        return weight * scale if math.isfinite(scale) else (weight / incident) * available

    cursor, sectors, endpoints = 90.0, {}, {}
    for name in names:
        stop = cursor - span(totals[name])
        sectors[name] = (cursor, stop)
        cursor = stop - gap
    ranks = {name: index for index, name in enumerate(names)}
    for name in names:
        cursor = sectors[name][0]
        incident_rows = [(index, row) for index, row in df.iterrows()
                         if name in (row[source], row[target])]
        incident_rows.sort(key=lambda item: ranks[
            item[1][target] if item[1][source] == name else item[1][source]])
        for index, row in incident_rows:
            stop = cursor - span(float(row[value]))
            endpoints[index, name] = (cursor, stop)
            cursor = stop
        if not math.isclose(cursor, sectors[name][1], abs_tol=1e-9):
            raise ArithmeticError("Chord endpoint spans must fill their node sector.")
    return sectors, endpoints


def _nice_step(maximum, target=6):
    raw = maximum / max(1, target)
    if raw <= 0 or not math.isfinite(raw):
        return maximum
    power = 10.0 ** math.floor(math.log10(raw))
    if power == 0:
        return maximum
    candidates = [power * factor for factor in (1, 2, 2.5, 5, 10)]
    return min((item for item in candidates if item > 0 and math.isfinite(item)),
               key=lambda item: abs(math.log(item / raw)))


def _draw_chord(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    payload = sp.get("derived_data", {}).get("chord")
    if not payload:
        raise ValueError("Chord graph summaries must be supplied by the compute layer.")
    source, target, value = (mapping[key] for key in ("source", "target", "value"))
    names = payload["node_order"]
    totals = {item["id"]: item["total"] for item in payload["nodes"]}
    sectors, endpoints = chord_geometry(df, mapping, payload)
    aliases = opts.get("category_aliases", {})
    canonical = lambda name: aliases.get(name, aliases.get(str(name), name))
    colors = {name: series_color(canonical(name), index, cfg, color_map or {}, opts)
              for index, name in enumerate(names)}
    summary = opts.get("summary", False)
    size = max(8.0, sp["font_sizes"].get("axis_label", 8.0))
    caption_size = max(8.0, round(size * .73, 1))
    ink, muted = cfg.text_color, cfg.muted_text_color
    text_artists, labels, leaders, handles = [], [], [], []
    ax.set_xlim(-1.40, 1.40)
    ax.set_ylim(-2.10 if summary else -1.42, 1.26 if summary else 1.42)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()
    ax.grid(False)

    def text(message, *, fontsize=size, color=ink, **kwargs):
        artist = ax.text(0, 0, message, fontsize=fontsize, color=color,
                         fontfamily=cfg.font_family, clip_on=False, **kwargs)
        text_artists.append(artist)
        return artist

    for index in df.sort_values(value, ascending=False, kind="stable").index:
        row = df.loc[index]
        patch = PathPatch(ribbon(endpoints[index, row[source]], endpoints[index, row[target]]),
                          facecolor=colors[row[source]], edgecolor=cfg.background,
                          linewidth=.65, alpha=.72, zorder=1)
        patch._figcompose_chord_edge = (row[source], row[target], float(row[value]))
        ax.add_patch(patch)
    for name in names:
        start, stop = sectors[name]
        ax.add_patch(Wedge((0, 0), 1.015, stop, start, width=.095,
                           facecolor=colors[name], edgecolor=cfg.background, linewidth=1.2, zorder=3))
        for index, row in df.iterrows():
            if name in (row[source], row[target]):
                first, last = endpoints[index, name]
                ax.add_patch(Wedge((0, 0), .910, last, first, width=.024,
                                   facecolor=colors[name], edgecolor=cfg.background,
                                   linewidth=.65, zorder=3))
        angle = (start + stop) / 2
        display = series_style(canonical(name), opts).get("label", str(canonical(name)))
        title = text(str(display), ha="center", va="bottom", fontweight=cfg.cell_title_weight)
        total = text(f"{totals[name]:g}", ha="center", va="top", color=muted)
        labels.append((name, angle, str(display), title, total))
        leader, = ax.plot([], [], color=colors[name], linewidth=1.0, zorder=3, clip_on=False)
        leaders.append(leader)
        handle = Patch(facecolor=colors[name], edgecolor="none", label=str(display))
        handle._figcompose_legend_key = canonical(name)
        handles.append(handle)
    tick_collection = LineCollection([], linewidths=.8, zorder=3)
    ax.add_collection(tick_collection)
    metrics = []
    if summary:
        for number, caption in ((payload["node_count"], "GROUPS"),
                                (payload["edge_count"], "UNDIRECTED LINKS"),
                                (payload["total_weight"], "TOTAL WEIGHT")):
            hero = text(f"{number:g}", ha="center", va="center", fontsize=size * 2.23,
                        fontweight=cfg.cell_title_weight)
            unit = text(caption, ha="center", va="center", fontsize=caption_size, color=muted)
            metrics.append((hero, unit))
        reading = text("Wider ribbons = stronger connections", ha="center", va="center",
                       fontsize=max(8.0, size * .92), fontweight=cfg.cell_title_weight)
    else:
        reading = None
    note = text("", ha="center", va="center", fontsize=caption_size, color=muted)
    ax._data_visuals_bounds_artists = text_artists
    ax._data_visuals_minimum_plot = (190.0, 190.0)

    def update_layout():
        ax.apply_aspect()
        renderer = ax.figure.canvas.get_renderer()
        box = ax.get_window_extent(renderer)
        points = ax.transData.transform(((0, 0), (1, 0), (0, 1)))
        scale = np.linalg.norm(points[1] - points[0]) * 72 / ax.figure.dpi
        if scale <= 0:
            return
        factor = ax.figure.dpi / 72

        def height(artist):
            return artist.get_window_extent(renderer).height / factor

        def width(artist):
            return artist.get_window_extent(renderer).width / factor

        def wrap(message, artist, maximum):
            prop = artist.get_fontproperties()
            def measure(value):
                return renderer.get_text_width_height_descent(value, prop, ismath=False)[0] / factor
            chunks, line = [], ""
            for word in message.split():
                candidate = f"{line} {word}".strip()
                if line and measure(candidate) > maximum:
                    chunks.append(line)
                    line = word
                else:
                    line = candidate
                while len(line) > 1 and measure(line) > maximum:
                    cut = len(line) - 1
                    while cut > 1 and measure(line[:cut]) > maximum:
                        cut -= 1
                    chunks.append(line[:cut])
                    line = line[cut:]
            return "\n".join([*chunks, line])

        # Preserve the compact radial layout when measured labels fit. Large
        # domains or long labels use two ordered columns with measured spacing.
        radial = len(names) <= 6
        boxes = []
        for (_, angle, display, title, total), leader in zip(labels, leaders):
            title.set_text(display)
            if width(title) > scale * .60:
                radial = False
            title.set_ha("center")
            total.set_ha("center")
            gap = .4 * size / scale
            radius = 1.19
            for _ in range(18):
                location = polar(angle, radius)
                title.set_position((location[0], location[1] + gap))
                total.set_position((location[0], location[1] - gap))
                clearance = []
                for artist in (title, total):
                    data_box = artist.get_window_extent(renderer).transformed(ax.transData.inverted())
                    nearest = (np.clip(0, data_box.x0, data_box.x1), np.clip(0, data_box.y0, data_box.y1))
                    clearance.append(np.linalg.norm(nearest))
                if min(clearance) > 1.025:
                    break
                radius += .02
            first, last = polar(angle, 1.065), polar(angle, max(1.105, radius - .085))
            leader.set_data((first[0], last[0]), (first[1], last[1]))
            for artist in (title, total):
                measured = artist.get_window_extent(renderer)
                data_box = measured.transformed(ax.transData.inverted())
                nearest = (np.clip(0, data_box.x0, data_box.x1), np.clip(0, data_box.y0, data_box.y1))
                if np.linalg.norm(nearest) <= 1.018:
                    radial = False
                if any(measured.overlaps(other) for other in boxes):
                    radial = False
                boxes.append(measured)
        if not radial:
            label_width = max(32.0, min(75.0, scale * .44))
            for side in (-1, 1):
                column = [(item, leader) for item, leader in zip(labels, leaders)
                          if (1 if math.cos(math.radians(item[1])) >= 0 else -1) == side]
                column.sort(key=lambda pair: math.sin(math.radians(pair[0][1])))
                placed = []
                for item, leader in column:
                    name, angle, display, title, total = item
                    title.set_text(wrap(display, title, label_width))
                    title.set_ha("left" if side > 0 else "right")
                    total.set_ha(title.get_ha())
                    block = height(title) + height(total) + 3.0
                    desired = polar(angle, 1.06)[1] * scale
                    center = max(desired, placed[-1][0] + (placed[-1][1] + block) / 2 + 4.0) if placed else desired
                    placed.append((center, block, item, leader))
                if placed:
                    bottom = placed[0][0] - placed[0][1] / 2
                    top = placed[-1][0] + placed[-1][1] / 2
                    shift = (top + bottom) / 2
                    for center, block, item, leader in placed:
                        _, angle, _, title, total = item
                        center -= shift
                        x = side * 1.13
                        split = center + (height(total) - height(title)) / 2
                        title.set_position((x, (split + 1.5) / scale))
                        total.set_position((x, (split - 1.5) / scale))
                        start = polar(angle, 1.045)
                        leader.set_data((start[0], side * 1.075, x - side * 2 / scale),
                                        (start[1], center / scale, center / scale))
                    required_height = top - bottom + 20
                    required_width = max(width(item[3]) for _, _, item, _ in placed) * 2 + 180
                    ax._data_visuals_minimum_plot = tuple(max(old, new) for old, new in zip(
                        ax._data_visuals_minimum_plot, (required_width, required_height)))

        segments, tick_colors = [], []
        target_ticks = max(2, min(7, int(scale * .40 / size)))
        step = _nice_step(max(totals.values()), target_ticks)
        if opts.get("ticks", True):
            for name in names:
                # A bounded integer loop avoids allocating a range proportional
                # to a large or very small scientific weight unit.
                count = min(64, max(0, math.ceil(totals[name] / step) - 1))
                for index in range(1, count + 1):
                    fraction = (step * index) / totals[name]
                    start, stop = sectors[name]
                    angle = start + (stop - start) * fraction
                    segments.append((polar(angle, 1.025), polar(angle, 1.048)))
                    tick_colors.append(colors[name])
        tick_collection.set_segments(segments)
        tick_collection.set_colors(tick_colors)
        lower = min(-1.07 * scale, *(artist.get_window_extent(renderer).y0 / factor
                    - points[0, 1] / factor for _, _, _, title, total in labels for artist in (title, total)))
        cursor = lower - max(10.0, size)
        if metrics:
            metric_height = max(height(hero) for hero, _ in metrics)
            cursor -= metric_height / 2
            for x, (hero, unit) in zip((-.92, 0, .92), metrics):
                hero.set_position((x, cursor / scale))
                unit.set_position((x, (cursor - metric_height / 2 - height(unit) / 2 - 5) / scale))
            cursor -= metric_height / 2 + max(height(unit) for _, unit in metrics) + 15
            reading.set_position((0, cursor / scale))
            cursor -= height(reading) / 2 + 10
        tick_note = f"Outer arc = incident weight · ticks every {step:g} units" if opts.get("ticks", True) else "Outer arc = incident weight"
        note.set_text(tick_note + "\nColor identifies one endpoint; links are undirected")
        note.set_position((0, (cursor - height(note) / 2) / scale))
        ax._figcompose_chord_diagnostics = {
            "node_count": len(names), "edge_count": len(df), "label_layout": "radial" if radial else "columns",
            "tick_step": step if opts.get("ticks", True) else None,
            "tick_count": len(segments), "summary": bool(summary),
        }

    ax._figcompose_layout_callback = update_layout
    update_layout()
    return handles
