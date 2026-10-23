"""Place optional scatter labels in physical points after the canvas has settled.

Only text moves. Marker coordinates and arrow endpoints remain the supplied data.
The bounded deterministic search avoids markers, other labels, and the axes edge.
"""

from __future__ import annotations

import math
from numbers import Real

from matplotlib.font_manager import FontProperties
from matplotlib.path import Path
from matplotlib.transforms import Bbox
import numpy as np


def _label(value):
    if isinstance(value, Real) and np.isfinite(value) and float(value).is_integer():
        return str(int(value))
    return str(value)


def place_point_labels(ax, cfg, *, obstacles=()):
    """Return ``texts`` and ``boxes``; safe to repeat after an axes resize.

    Scatter builders supply ``ax._data_visuals_annotations``. The canvas calls
    this helper after its measured layout pass, followed by a final draw.
    Distances are points even when the Figure uses a DPI other than 72.
    ``obstacles`` are display-pixel bounding boxes of existing decorations,
    such as an inside legend; labels must also clear these occupied regions.
    """
    state = getattr(ax, "_data_visuals_annotations", None)
    if not state:
        return {"texts": [], "boxes": []}
    for text in state.get("texts", []):
        text.remove()
    state["texts"], state["boxes"] = [], []
    options = state.get("point_labels")
    if not options:
        return {"texts": [], "boxes": []}
    points = state.get("points", [])
    requests = [point for point in points if point["label"] is not None]
    if not requests:
        return {"texts": [], "boxes": []}
    renderer = ax.figure.canvas.get_renderer()
    scale = ax.figure.dpi / 72
    font_size = float(options.get("fontsize", cfg.font_sizes["tick"]))
    prop = FontProperties(family=cfg.font_family, size=font_size)
    positions = ax.transData.transform([point["xy"] for point in requests])
    occupied = list(obstacles)
    for point in points:
        center = ax.transData.transform(point["xy"])
        radius = point["radius"] * scale
        occupied.append(Bbox.from_bounds(center[0] - radius, center[1] - radius, 2 * radius, 2 * radius))
    arrows = [Path(ax.transData.transform(segment)) for segment in state.get("arrows", [])]
    boundary = ax.bbox.padded(-1.5 * scale)
    crowding = (np.linalg.norm(positions[:, None] - positions[None, :], axis=2) < 18 * scale).sum(axis=1)
    order = sorted(range(len(requests)), key=lambda index: (-crowding[index], _label(requests[index]["label"]), index))
    texts, boxes = [], []
    try:
        for index in order:
            point, center = requests[index], positions[index]
            label = _label(point["label"])
            width, height, descent = renderer.get_text_width_height_descent(label, prop, False)
            width, height = width + 2 * scale, max(font_size * scale, height + descent) + scale
            candidates = []
            for radius in (7, 10, 14, 19, 25, 32, 40):
                for angle in (30, -30, 0, 60, -60, 90, -90, 120, -120, 150, -150, 180):
                    radians = math.radians(angle)
                    candidates.append((radius * math.cos(radians) * scale, radius * math.sin(radians) * scale))
            for target_x in np.arange(boundary.x0 + 7 * scale, boundary.x1 - 3 * scale, 10 * scale):
                for target_y in np.arange(boundary.y0 + 7 * scale, boundary.y1 - 3 * scale, 11 * scale):
                    candidates.append((target_x - center[0], target_y - center[1]))
            best = None
            for dx, dy in candidates:
                box = Bbox.from_bounds(center[0] + dx - width / 2, center[1] + dy - height / 2, width, height)
                if not (boundary.contains(box.x0, box.y0) and boundary.contains(box.x1, box.y1)):
                    continue
                if any(box.overlaps(other) for other in occupied):
                    continue
                score = dx * dx + dy * dy + (160 * scale * scale if any(arrow.intersects_bbox(box) for arrow in arrows) else 0)
                if best is None or score < best[0]:
                    best = score, dx, dy, box
            if best is None:
                raise ValueError(f"Cannot place point label {label!r} without overlap; increase the canvas size.")
            _, dx, dy, box = best
            annotation = ax.annotate(
                label, xy=point["xy"], xytext=(dx / scale, dy / scale), textcoords="offset points",
                ha="center", va="center", fontsize=font_size, fontfamily=cfg.font_family, color=cfg.text_color,
                arrowprops={"arrowstyle": "-", "color": point["color"], "lw": 0.45, "shrinkA": 1.8, "shrinkB": 2.7},
                bbox={"boxstyle": "square,pad=0.04", "fc": cfg.background, "ec": "none", "alpha": 0.93},
                zorder=6,
            )
            annotation.set_gid(f"{ax.get_gid() or ax.get_label()}-point-label-{index}")
            texts.append(annotation)
            boxes.append(box)
            occupied.append(box.padded(0.8 * scale))
    except Exception:
        for text in texts:
            text.remove()
        raise
    state["texts"], state["boxes"] = texts, boxes
    return {"texts": texts, "boxes": boxes}
