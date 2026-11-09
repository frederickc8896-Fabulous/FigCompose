"""Native radial matrix geometry with Ward distances from the compute layer."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.patches import Rectangle, Wedge
from scipy.cluster.hierarchy import dendrogram

from .helpers import color_scheme, frame


CIRCULAR_LIMITS = ((-1.29, 1.29), (-1.29, 1.29))


def _accents(palette, count):
    colors = tuple(palette)
    if count > len(colors):
        raise ValueError("[clustered_heatmap] The selected palette must cover all Ward clusters.")
    if len(colors) >= 8:
        indices = [2, 5, 6, 7, *[i for i in range(len(colors)) if i not in (2, 5, 6, 7)]]
        return tuple(colors[index] for index in indices)
    return colors


def _tint(color, amount=0.88):
    return tuple((1 - amount) * component + amount for component in to_rgb(color))


def _xy(radius, angle):
    radians = np.deg2rad(angle)
    return np.column_stack((radius * np.cos(radians), radius * np.sin(radians)))


def _draw_clustered_heatmap(ax, sp, cfg, color_map):
    """Draw a 270-degree heatmap, distance-preserving tree and cluster ring."""
    if frame(sp.get("computed_data", [])).empty:
        return []
    payload = sp.get("derived_data", {}).get("clustered_heatmap")
    if not payload:
        raise ValueError("Clustered-heatmap summaries must be supplied by the compute layer.")
    opts = sp.get("options", {})
    observations, tree = np.asarray(payload["matrix"]), np.asarray(payload["tree"])
    identifiers, traits = payload["identifiers"], payload["traits"]
    size = max(8.0, sp["font_sizes"].get("axis_label", 8.0))
    def text(x, y, label, **kwargs):
        style = {"fontsize": size, "fontfamily": cfg.font_family, "color": cfg.text_color}
        style.update(kwargs)
        return ax.text(x, y, label, clip_on=False, **style)
    ax.set_xlim(*CIRCULAR_LIMITS[0])
    ax.set_ylim(*CIRCULAR_LIMITS[1])
    ax.set_axis_off()
    ax.grid(False)

    n, n_traits = observations.shape
    palette = tuple(cfg.categorical_palette)
    cluster_colors = opts.get("cluster_colors")
    accents = _accents(palette, 0 if cluster_colors is not None else payload["cluster_count"])
    if cluster_colors is not None:
        if (not isinstance(cluster_colors, (list, tuple))
                or len(cluster_colors) < payload["cluster_count"]):
            raise ValueError("[clustered_heatmap] cluster_colors must cover every computed cluster.")
        node_accents = tuple(cluster_colors)
    else:
        node_accents = accents
    cluster_ids = np.asarray(payload["cluster_ids"])
    node_colors = {i: node_accents[cluster_ids[i] - 1] for i in range(n)}
    neutral = "#A8AFBC"
    for index, (left, right, _, _) in enumerate(tree):
        left_color, right_color = node_colors[int(left)], node_colors[int(right)]
        node_colors[n + index] = left_color if left_color == right_color else neutral
    branches = dendrogram(tree, no_plot=True,
                          link_color_func=lambda key: node_colors[key])
    order = np.asarray(payload["leaf_order"])
    if branches["leaves"] != order.tolist():
        raise ValueError("Ward dendrogram geometry and computed leaf order disagree.")
    values = observations[order]
    theta_start, sweep = 90.0, 270.0
    inner, outer = 0.40, 1.00
    annulus_width = (outer - inner) / n_traits
    angle_width = sweep / n
    # This is a per-panel data scale, not a new public preset. The Figure's
    # registered palette remains unchanged and drives both circular examples.
    scale_accents = accents if len(accents) >= 4 else (accents[0], accents[0], accents[-1], accents[-1])
    cmap = LinearSegmentedColormap.from_list(
        "figcompose-palette-diverging",
        ((0.0, scale_accents[3]), (0.27, scale_accents[2]), (0.5, "#FBFAFD"),
         (0.74, _tint(scale_accents[0], 0.42)), (1.0, scale_accents[0])),
    )
    cmap = color_scheme(sp, cfg, default=cmap)
    low, high = payload["value_range"]
    norm = Normalize(low, high)

    cells = []
    for row in range(n):
        for column in range(n_traits):
            radius = inner + annulus_width * (column + 1)
            cells.append(Wedge((0, 0), radius,
                               theta_start + row * angle_width,
                               theta_start + (row + 1) * angle_width,
                               width=annulus_width,
                               facecolor=cmap(norm(values[row, column])),
                               edgecolor=(1, 1, 1, 0.65), linewidth=0.30))
    heatmap = PatchCollection(cells, match_original=True, zorder=2)
    ax.add_collection(heatmap)

    # The annotation track links real Ward clusters to the same computed tree.
    cluster_track = []
    for row, source_index in enumerate(order):
        cluster_track.append(Wedge(
            (0, 0), 1.025, theta_start + row * angle_width,
            theta_start + (row + 1) * angle_width, width=0.015,
            facecolor=node_accents[cluster_ids[source_index] - 1],
            edgecolor="white", linewidth=0.20,
        ))
    ax.add_collection(PatchCollection(cluster_track, match_original=True, zorder=3))

    # Preserve linkage distances radially. The two child stems are radial;
    # the merge is an arc at the common parent distance.
    max_distance = float(tree[:, 2].max())
    leaf_radius, root_radius = 0.377, 0.045
    lines, line_colors = [], []
    for x_values, heights, color in zip(branches["icoord"], branches["dcoord"],
                                       branches["color_list"]):
        angles = theta_start + sweep * (np.asarray(x_values) / 10) / n
        radii = leaf_radius - np.asarray(heights) / max_distance * (leaf_radius - root_radius)
        lines.append(_xy(radii[:2], angles[:2]))
        line_colors.append(color)
        arc_angles = np.linspace(angles[1], angles[2], max(6, int(abs(angles[2] - angles[1]))))
        lines.append(_xy(np.full(len(arc_angles), radii[1]), arc_angles))
        line_colors.append(color)
        lines.append(_xy(radii[2:], angles[2:]))
        line_colors.append(color)
    dendrogram_lines = LineCollection(lines, colors=line_colors,
                                      linewidths=0.72, capstyle="round", zorder=3)
    ax.add_collection(dendrogram_lines)

    texts = []
    for row, source_index in enumerate(order):
        if row % opts.get("label_every", 2):
            continue
        angle = theta_start + angle_width * (row + 0.5)
        x, y = _xy(np.array([1.065]), np.array([angle]))[0]
        rotation = angle if not 90 < angle < 270 else angle + 180
        align = "left" if np.cos(np.deg2rad(angle)) >= 0 else "right"
        texts.append(text(x, y, str(identifiers[source_index]),
                           ha=align, va="center", rotation=rotation,
                           rotation_mode="anchor"))

    # The open quadrant becomes a compact reading key. All text still uses
    # physical point sizes from FigCompose and all objects use this one Axes.
    gradient_patches = []
    for index in range(128):
        gradient_patches.append(Rectangle((0.32 + 0.64 * index / 128, 0.535),
                                          0.64 / 128 + 0.0001, 0.045,
                                          facecolor=cmap(index / 127), linewidth=0))
    gradient = PatchCollection(gradient_patches, match_original=True)
    ax.add_collection(gradient)
    texts.append(text(0.64, 0.975, f"{n} × {n_traits}", ha="center", va="center",
                       fontsize=size * 1.5, fontweight=cfg.cell_title_weight))
    texts.append(text(0.64, 0.825, "samples × traits", ha="center", va="center"))
    texts.append(text(0.64, 0.685, "Trait value", ha="center", va="center"))
    for value, x in ((f"{low:g}".replace("-", "−"), 0.32),
                     (f"{low / 2 + high / 2:g}", 0.64),
                     ((f"+{high:g}" if high > 0 else f"{high:g}"), 0.96)):
        texts.append(text(x, 0.455, value, ha="center", va="center"))
    texts.append(text(0.64, 0.335, f"{traits[0]} → {traits[-1]}", ha="center", va="center"))
    texts.append(text(0.64, 0.245, "inner → outer", ha="center", va="center"))
    count = payload["cluster_count"]
    for index, color in enumerate(node_accents[:count]):
        ax.add_patch(Rectangle((0.37 + index * 0.56 / count, 0.15), 0.48 / count, 0.025,
                               facecolor=color, edgecolor="none"))
    texts.append(text(0.64, 0.065, f"{count} Ward clusters", ha="center", va="center"))
    ax.set_aspect("equal", adjustable="box")
    # Collections stay inside the declared data limits. Their inherited
    # get_window_extent() is infinite, so the explicit measurement contract
    # lists the text decorations, not those collections.
    ax._data_visuals_bounds_artists = texts
    ax._data_visuals_minimum_plot = (220.0, 220.0)
    ax._figcompose_clustered_heatmap_diagnostics = {
        "sample_count": n, "trait_count": n_traits, "cell_count": n * n_traits,
        "branch_count": len(tree), "cluster_count": count,
        "leaf_order": order.tolist(), "value_range": [low, high],
    }
    return []
