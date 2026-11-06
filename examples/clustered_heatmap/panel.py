"""Circular Ward-clustered heatmap driven by an explicit data payload."""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.patches import Circle, Rectangle, Wedge
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from data_visuals.core import PanelContext, PanelResult


CIRCULAR_LIMITS = ((-1.29, 1.29), (-1.29, 1.29))
CIRCULAR_MIN_SIZE = (180, 180)
SUBJECTS = ("Math", "English", "Physics", "Geography")


def _accents(palette):
    """Choose legible accents without reordering the registered source colors."""
    colors = tuple(palette)
    if len(colors) < 4:
        raise ValueError("The four-category panels need a palette with at least four colors")
    return tuple(colors[index] for index in (2, 5, 6, 7)) if len(colors) >= 8 else colors[:4]


def _tint(color, amount=0.88):
    return tuple((1 - amount) * component + amount for component in to_rgb(color))


def _xy(radius, angle):
    radians = np.deg2rad(angle)
    return np.column_stack((radius * np.cos(radians), radius * np.sin(radians)))


def _text(ax, ctx, x, y, label, **kwargs):
    return ax.text(x, y, label, clip_on=False,
                   **ctx.text_kwargs("annotation", **kwargs))


def draw_clustered_heatmap(ax, ctx: PanelContext) -> PanelResult:
    """A 270-degree heatmap and a genuine radial hierarchical dendrogram.

    Rows are the Ward leaf order; inner-to-outer columns are traits V1--V9.
    The continuous scale is derived from the resolved Figure palette, with
    negative / zero / positive values mapped to blue / near-white / rose.
    Every second observation label is shown to keep 8 pt text readable.
    """
    observations, tree = ctx.payload["matrix"], ctx.payload["tree"]
    identifiers, traits = ctx.payload["identifiers"], ctx.payload["traits"]
    n, n_traits = observations.shape
    palette = tuple(ctx.palette)
    accents = _accents(palette)
    cluster_ids = fcluster(tree, t=4, criterion="maxclust")
    node_colors = {i: accents[cluster_ids[i] - 1] for i in range(n)}
    neutral = "#A8AFBC"
    for index, (left, right, _, _) in enumerate(tree):
        left_color, right_color = node_colors[int(left)], node_colors[int(right)]
        node_colors[n + index] = left_color if left_color == right_color else neutral
    branches = dendrogram(tree, no_plot=True,
                          link_color_func=lambda key: node_colors[key])
    order = np.asarray(branches["leaves"])
    values = observations[order]
    theta_start, sweep = 90.0, 270.0
    inner, outer = 0.40, 1.00
    annulus_width = (outer - inner) / n_traits
    angle_width = sweep / n
    # This is a per-panel data scale, not a new public preset. The Figure's
    # registered palette remains unchanged and drives both circular examples.
    cmap = LinearSegmentedColormap.from_list(
        "figcompose-palette-diverging",
        ((0.0, accents[3]), (0.27, accents[2]), (0.5, "#FBFAFD"),
         (0.74, _tint(accents[0], 0.42)), (1.0, accents[0])),
    )
    norm = Normalize(-1, 1)

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

    # A narrow outer track links the four real Ward clusters to the tree.
    # It is separate from the nine measured traits and uses categorical color.
    cluster_track = []
    for row, source_index in enumerate(order):
        cluster_track.append(Wedge(
            (0, 0), 1.025, theta_start + row * angle_width,
            theta_start + (row + 1) * angle_width, width=0.015,
            facecolor=accents[cluster_ids[source_index] - 1],
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
        if row % 2:
            continue
        angle = theta_start + angle_width * (row + 0.5)
        x, y = _xy(np.array([1.065]), np.array([angle]))[0]
        rotation = angle if not 90 < angle < 270 else angle + 180
        align = "left" if np.cos(np.deg2rad(angle)) >= 0 else "right"
        texts.append(_text(ax, ctx, x, y, str(identifiers[source_index]),
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
    texts.append(_text(ax, ctx, 0.64, 0.975, f"{n} × {n_traits}", ha="center", va="center",
                       fontsize=12, fontweight="bold"))
    texts.append(_text(ax, ctx, 0.64, 0.825, "samples × traits", ha="center", va="center"))
    texts.append(_text(ax, ctx, 0.64, 0.685, "Trait value", ha="center", va="center"))
    for value, x in (("−1", 0.32), ("0", 0.64), ("+1", 0.96)):
        texts.append(_text(ax, ctx, x, 0.455, value, ha="center", va="center"))
    texts.append(_text(ax, ctx, 0.64, 0.335, f"{traits[0]} → {traits[-1]}", ha="center", va="center"))
    texts.append(_text(ax, ctx, 0.64, 0.245, "inner → outer", ha="center", va="center"))
    for index, color in enumerate(accents):
        ax.add_patch(Rectangle((0.37 + index * 0.14, 0.15), 0.12, 0.025,
                               facecolor=color, edgecolor="none"))
    texts.append(_text(ax, ctx, 0.64, 0.065, "4 Ward clusters", ha="center", va="center"))
    ax.set_aspect("equal", adjustable="box")
    # Collections stay inside the declared data limits. Their inherited
    # get_window_extent() is infinite, so the explicit measurement contract
    # lists the text decorations, not those collections.
    return PanelResult(artists=tuple(texts))
