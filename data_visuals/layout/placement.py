"""Numeric, deterministic placement within a fixed canvas.

The renderer measures decorations and supplies their extents. Grid topology,
ratios and the requested canvas remain fixed throughout placement.
"""
from __future__ import annotations


class LayoutError(ValueError):
    """The content cannot fit at the specified readable sizes."""

    def __init__(self, message, *, axis=None, required_width=None,
                 required_height=None, subplot=None):
        super().__init__(message)
        self.axis = axis
        self.required_width = required_width
        self.required_height = required_height
        self.subplot = subplot


def cell_boxes(spec, header, padding, footer=0, left_reserve=0, right_reserve=0):
    cells = spec["subplots"]
    if not cells:
        return {}
    width, height = spec["canvas"]["width"], spec["canvas"]["height"]
    # FigureSpec rounds each cell independently. Snap matching topology edges
    # before scaling so a spanning panel still aligns exactly with smaller ones.
    left, right, top, bottom = {}, {}, {}, {}
    for sp in cells:
        r, c, box = sp["row"], sp["col"], sp["geometry"]
        er, ec = r + sp.get("row_span", 1), c + sp.get("col_span", 1)
        left[c] = min(left.get(c, box["x"]), box["x"])
        right[ec] = max(right.get(ec, 0), box["x"] + box["w"])
        top[r] = min(top.get(r, box["y"]), box["y"])
        bottom[er] = max(bottom.get(er, 0), box["y"] + box["h"])
    x0, y0, x1, y1 = min(left.values()), min(top.values()), max(right.values()), max(bottom.values())
    available_w = width - 2 * padding - left_reserve - right_reserve
    available_h = height - header - footer - 2 * padding
    if min(available_w, available_h, x1 - x0, y1 - y0) <= 0:
        raise LayoutError(
            "Title and legends fill the canvas; use a larger canvas or fewer decorations.",
            axis="width" if available_w <= 0 else "height",
            required_width=max(width, 2 * padding + left_reserve + right_reserve + 40),
            required_height=max(height, header + footer + 2 * padding + 40),
        )
    sx, sy = available_w / (x1 - x0), available_h / (y1 - y0)
    return {(sp["row"], sp["col"]): {
        "x": padding + left_reserve + (left[sp["col"]] - x0) * sx,
        "y": header + padding + (top[sp["row"]] - y0) * sy,
        "w": (right[sp["col"] + sp.get("col_span", 1)] - left[sp["col"]]) * sx,
        "h": (bottom[sp["row"] + sp.get("row_span", 1)] - top[sp["row"]]) * sy,
    } for sp in cells}


def align_gutters(subplots, requirements, *, vertical_tolerance=None):
    """Align columns; share vertical gutters only for similar decorations.

    A long x label or a local legend must not shrink every neighbouring panel.
    None preserves strict alignment; a numeric tolerance clusters similar
    vertical requirements while retaining full horizontal edge alignment.
    """
    edges = {}
    result = {key: dict(value) for key, value in requirements.items()}
    sides = ("left", "right", "top", "bottom")
    for sp in subplots:
        key = r, c = sp["row"], sp["col"]
        if key not in requirements:
            continue
        topology = (c, c + sp.get("col_span", 1), r, r + sp.get("row_span", 1))
        for side, edge in zip(sides, topology):
            edges.setdefault((side, edge), []).append((key, requirements[key][side]))
    for (side, _), values in edges.items():
        if side in ("left", "right") or vertical_tolerance is None:
            maximum = max(value for _, value in values)
            for key, _ in values:
                result[key][side] = maximum
            continue
        cluster = []
        for key, value in sorted(values, key=lambda item: item[1]):
            if cluster and value - cluster[0][1] > vertical_tolerance:
                for member, _ in cluster:
                    result[member][side] = cluster[-1][1]
                cluster = []
            cluster.append((key, value))
        for member, _ in cluster:
            result[member][side] = cluster[-1][1]
    return result


def inset_box(box, gutters, minimum, key):
    width = box["w"] - gutters["left"] - gutters["right"]
    height = box["h"] - gutters["top"] - gutters["bottom"]
    min_width, min_height = minimum if isinstance(minimum, tuple) else (minimum, minimum)
    if width < min_width or height < min_height:
        raise LayoutError(
            f"Subplot {key} has only {width:.1f} x {height:.1f} design points after labels/legends. "
            "Use a larger canvas, fewer columns, or fewer panels.",
            axis="width" if width < min_width else "height",
            required_width=max(box["w"], min_width + gutters["left"] + gutters["right"]),
            required_height=max(box["h"], min_height + gutters["top"] + gutters["bottom"]),
            subplot=key,
        )
    return {"x": box["x"] + gutters["left"], "y": box["y"] + gutters["top"],
            "w": width, "h": height}
