"""Native aligned participant tracks with descriptive cohort summaries."""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Patch, Rectangle, Wedge
from matplotlib.text import Text

from data_visuals.renderer.mpl.charts.helpers import frame as as_frame, series_color, series_style
from data_visuals.layout.placement import LayoutError


def _xy(theta, radius):
    return radius * np.cos(theta), radius * np.sin(theta)


def _participant_minimum_plot(ax, identifiers, fontsize, family):
    """Separate adjacent rotated ID rectangles along their connecting chord."""
    renderer = ax.figure.canvas.get_renderer()
    factor = 72 / ax.figure.dpi
    probe = Text(fontfamily=family, fontsize=fontsize, ha="center", va="center")
    probe.set_figure(ax.figure)
    dimensions = []
    for identifier in identifiers:
        probe.set_text(str(identifier))
        box = probe.get_window_extent(renderer)
        dimensions.append((box.width * factor, box.height * factor))
    half_angle = np.deg2rad(270 / len(identifiers)) / 2
    cosine, sine = np.cos(half_angle), np.sin(half_angle)
    # The tangent and radial axes rotate by half_angle around the chord.
    # This projection gives a separating axis for each adjacent label pair.
    required_radius = max((cosine * (first[0] + second[0]) / 2
                           + sine * (first[1] + second[1]) / 2 + .5) / (2 * sine)
                          for first, second in zip(dimensions, dimensions[1:]))
    return max(490.0, required_radius * 2.72 / 1.19)


def _participant_sector_gap(count):
    return min(.045, (270 / count) * .1)


def _draw_participant_tracks(ax, sp, cfg, color_map):
    frame = as_frame(sp.get("computed_data", []))
    if frame.empty:
        return []
    payload = sp.get("derived_data", {}).get("participant_tracks")
    if payload is None:
        raise ValueError("Participant summaries must be supplied by the compute layer.")
    mapping, opts = sp["data"], sp.get("options", {})
    identifier = mapping["id"]
    category_tracks, numeric_tracks = payload["categorical"], payload["numeric"]
    categories = payload["category_order"]
    aliases = opts.get("category_aliases", {})
    def canonical(value):
        return aliases.get(value, aliases.get(str(value), value))
    def color(value):
        key = canonical(value)
        index = categories.index(value) if value in categories else 0
        return series_color(key, index, cfg, color_map or {}, opts)
    def accent(value, fallback):
        if value is None:
            return fallback
        return color(value) if value in categories else value
    labels = opts.get("track_labels") or {}
    def heading(column):
        return labels.get(column, str(column).replace("_", " ").title())
    body_size = max(8.0, sp.get("font_sizes", {}).get("axis_label", 8.0))
    size_scale = body_size / 8
    ax.set_xlim(-1.36, 1.36)
    ax.set_ylim(-1.44, 1.28)
    ax.set_aspect("equal", adjustable="box")
    ax.apply_aspect()
    ax.set_axis_off()
    ax.grid(False)
    n = len(frame)
    step = 270.0 / n
    gap = _participant_sector_gap(n)
    minimum = _participant_minimum_plot(ax, frame[identifier].tolist(), body_size, cfg.font_family)
    ax._data_visuals_minimum_plot = (minimum, minimum)
    allocated = ax.get_position(original=True)
    width_pt = allocated.width * ax.figure.get_figwidth() * 72
    height_pt = allocated.height * ax.figure.get_figheight() * 72
    if min(width_pt, height_pt) + .01 < minimum:
        raise LayoutError(
            f"[participant_tracks] {n} participant IDs need a plotting square of at least "
            f"{minimum:.1f} pt at the requested font size. Increase the canvas width/height or shorten the IDs.",
            axis="width" if width_pt < minimum else "height",
            required_width=ax.figure.get_figwidth() * 72 + max(0.0, minimum - width_pt),
            required_height=ax.figure.get_figheight() * 72 + max(0.0, minimum - height_pt),
            subplot=(sp.get("row", 0), sp.get("col", 0)))
    angles = np.deg2rad(180 + (np.arange(n) + 0.5) * step)
    texts = []
    ink = cfg.text_color
    muted = "#77828f"
    grid = "#e0e5ec"
    outline = "#c4cdd8"

    def tint(color, amount=0.92):
        """Use a quiet tint of the resolved paper palette for track surfaces."""
        foreground = np.asarray(to_rgb(color))
        background = np.asarray(to_rgb(cfg.background))
        return foreground * (1 - amount) + background * amount

    def text(x, y, label, **kwargs):
        kwargs["fontsize"] = max(8.0, kwargs.pop("fontsize", 8.0) * size_scale)
        kwargs.setdefault("color", ink)
        artist = ax.text(x, y, label, fontfamily=cfg.font_family, clip_on=False, **kwargs)
        texts.append(artist)
        return artist

    def arc(radius, color=grid, linewidth=0.4, **kwargs):
        theta = np.linspace(np.pi, 2.5 * np.pi, 400)
        ax.plot(*_xy(theta, radius), color=color, linewidth=linewidth, **kwargs)

    categorical_bounds = ((.265, .355), (.375, .495), (.515, .625))
    tracks = [(track["column"], track["categories"], *bounds)
              for track, bounds in zip(category_tracks, categorical_bounds)]
    for column, _categories, inner, outer in tracks:
        for index, value in enumerate(frame[column]):
            patch = Wedge((0, 0), outer,
                          180 + index * step + gap,
                          180 + (index + 1) * step - gap,
                          width=outer - inner, facecolor=color(value),
                          edgecolor=cfg.background, linewidth=0.45)
            ax.add_patch(patch)
        arc(inner, color=outline, linewidth=0.35)
        arc(outer, color=outline, linewidth=0.35)

    numeric_bounds = ((.655, .855), (.89, 1.13))
    numeric = []
    for index, (track, bounds) in enumerate(zip(numeric_tracks, numeric_bounds)):
        low, high = track["range"]
        numeric.append((track["column"], *bounds, (low, high),
                        track["ticks"],
                        accent((opts.get("numeric_colors") or {}).get(track["column"]),
                               cfg.get_color(index))))
    for column, inner, outer, limits, ticks, track_color in numeric:
        ax.add_patch(Wedge((0, 0), outer, 180, 450, width=outer - inner,
                           facecolor=tint(track_color, .965), edgecolor="none", zorder=0))
        for tick in ticks:
            radius = inner + (tick - limits[0]) / (limits[1] - limits[0]) * (outer - inner)
            arc(radius, linewidth=0.4, linestyle=(0, (1.5, 2.5)), zorder=1)
            text(-radius, 0.035, f"{tick:g}", ha="center", va="bottom", fontsize=8,
                 color=muted, rotation=90)
        # True radial cell boundaries, with numerical scales independent by track.
        theta = np.deg2rad(180 + np.arange(n + 1) * step)
        boundaries = [[_xy(angle, inner), _xy(angle, outer)] for angle in theta]
        ax.add_collection(LineCollection(boundaries, colors=grid, linewidths=.25, zorder=1))
        radii = inner + (frame[column].to_numpy() - limits[0]) / (limits[1] - limits[0]) * (outer - inner)
        stems = [[_xy(angle, inner), _xy(angle, radius)] for angle, radius in zip(angles, radii)]
        ax.add_collection(LineCollection(stems, colors=[tint(track_color, .62)],
                                         linewidths=.65, zorder=2))
        ax.scatter(*_xy(angles, radii), s=13, color=track_color, linewidths=0.35,
                   edgecolors=cfg.background, zorder=4)
        arc(inner, color=outline, linewidth=.45, zorder=2)
        arc(outer, color=outline, linewidth=.45, zorder=2)

    # Tangential labels remain upright on both halves of the circle.
    for angle, sample_id in zip(angles, frame[identifier]):
        degrees = np.rad2deg(angle) % 360
        rotation = degrees - 90
        if 90 < rotation <= 270:
            rotation -= 180
        text(*_xy(angle, 1.19), sample_id, rotation=rotation,
             rotation_mode="anchor", ha="center", va="center", fontsize=8, color=muted)

    # The centre explains the unit of observation, rather than adding a second key.
    ax.add_patch(Circle((0, 0), .235, facecolor=tint(accent(opts.get("center_color"), cfg.get_color(0)), .87),
                        edgecolor="none", zorder=0))
    text(0, .065, f"{n}", ha="center", va="center", fontsize=23,
         color=accent(opts.get("accent_color"), cfg.get_color(1)))
    text(0, -.025, opts.get("center_label", "participants"), ha="center", va="center", fontsize=9)
    if opts.get("center_note"):
        text(0, -.105, opts["center_note"], ha="center", va="center", fontsize=8, color=muted)

    def distribution(track, x, low, high, track_color, heading, seed):
        column = track["column"]
        values = frame[column].to_numpy()
        y = 0.26 + (values - low) / (high - low) * 0.70
        # Fixed jitter, never dependent on sizing-trial invocation counts.
        jitter = np.random.default_rng(seed).uniform(-0.035, 0.035, n)
        for tick in (low, (low + high) / 2, high):
            ty = .26 + (tick - low) / (high - low) * .70
            ax.plot([x - .085, x + .085], [ty, ty], color=grid, linewidth=.4, zorder=0)
        q1, median, q3 = [.26 + (track[key] - low) / (high - low) * .70
                          for key in ("q1", "median", "q3")]
        ax.add_patch(Rectangle((x - 0.065, q1), 0.13, q3 - q1,
                               facecolor=tint(track_color, .93), edgecolor=track_color,
                               linewidth=0.65, zorder=1))
        minimum = .26 + (track["minimum"] - low) / (high - low) * .70
        maximum = .26 + (track["maximum"] - low) / (high - low) * .70
        ax.plot([x, x], [minimum, q1], color=track_color, linewidth=0.65)
        ax.plot([x, x], [q3, maximum], color=track_color, linewidth=0.65)
        ax.plot([x - .025, x + .025], [minimum, minimum], color=track_color, linewidth=0.65)
        ax.plot([x - .025, x + .025], [maximum, maximum], color=track_color, linewidth=0.65)
        ax.scatter(x + jitter, y, s=10, color=track_color, alpha=0.72,
                   edgecolors=cfg.background, linewidths=.25, zorder=3)
        ax.plot([x - 0.065, x + 0.065], [median, median], color=track_color, linewidth=1.2, zorder=5)
        text(x, 1.035, heading, ha="center", va="bottom", fontsize=9, fontweight="bold")
        text(x, 0.185, f"{track['median']:.1f}", ha="center", va="center", fontsize=10,
             color=track_color, fontweight="bold")

    for index, item in enumerate(reversed(numeric)):
        column, _, _, limits, _, track_color = item
        track = next(item for item in numeric_tracks if item["column"] == column)
        distribution(track, -1.025 + .260 * index, *limits, track_color, heading(column), 419 + index)

    def stacked_summary(track, x, heading):
        column, domain = track["column"], track["categories"]
        y = 0.265
        height = 0.70
        for category, proportion in zip(domain, track["proportions"]):
            track_color = color(category)
            ax.add_patch(Rectangle((x - 0.05, y), 0.10, height * proportion,
                                   facecolor=track_color, edgecolor=cfg.background, linewidth=0.5))
            if proportion >= 0.14:
                r, g, b = to_rgb(track_color)
                foreground = ink if 0.2126*r + 0.7152*g + 0.0722*b > 0.61 else "white"
                text(x, y + height * proportion / 2, f"{100 * proportion:.1f}%",
                     ha="center", va="center", fontsize=8, rotation=90, color=foreground)
            y += height * proportion
        ax.add_patch(Rectangle((x - 0.05, 0.265), 0.10, height,
                               facecolor="none", edgecolor=outline, linewidth=0.5))
        text(x, 1.0, heading, rotation=58, ha="left", va="bottom", fontsize=8.5,
             fontweight="bold")

    for index, track in enumerate(reversed(category_tracks)):
        stacked_summary(track, (-.57, -.435, -.31)[index], heading(track["column"]))
    for index in range(len(numeric_tracks)):
        text(-1.025 + .260 * index, .11, "median", ha="center", va="center", fontsize=8, color=muted)
    text(-.69, 1.225, "COHORT PROFILE", ha="center", va="center", fontsize=8, color=muted)
    order_label = opts.get("order_label") or (f"Ordered by {payload['order_by']}" if payload["order_by"] else "Ordered by ID")
    text(.70, 1.23, f"One participant per angle  /  {order_label}", ha="center", fontsize=8, color=muted)
    if opts.get("note"):
        text(0, -1.34, opts["note"], ha="center", va="center", fontsize=8, color=muted, linespacing=1.5)
    ax.set_aspect("equal", adjustable="box")
    prefixes = {category: heading(track["column"]) for track in category_tracks
                for category in track["categories"]}
    handles = []
    for category in categories:
        key = canonical(category)
        display = series_style(key, opts).get("label", f"{prefixes[category]}: {key}")
        handle = Patch(facecolor=color(category), edgecolor="none",
                       label=str(display))
        handle._figcompose_legend_key = key
        handles.append(handle)
    ax._data_visuals_bounds_artists = texts
    ax._figcompose_participant_tracks = {"count": n, "track_count": len(tracks) + len(numeric),
                                        "order": frame[identifier].tolist()}
    return handles
