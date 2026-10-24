"""Heatmaps with preallocated colour bars and optional cell annotations."""

from __future__ import annotations

import numpy as np

from .helpers import (annotate_matrix, axis_labels, color_norm, color_scheme, colorbar,
                      frame, matrix_ticks, ordered, value_column)


def _draw_heatmap(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y_col = mapping["x"], mapping["y"]
    column = value_column(df, mapping["value"])
    xs, ys = ordered(df[x_col]), ordered(df[y_col])
    matrix = df.pivot(index=y_col, columns=x_col, values=column).reindex(index=ys, columns=xs).to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(matrix), aspect="auto", interpolation="nearest",
                      cmap=color_scheme(sp, cfg), norm=color_norm(sp))
    annotate_matrix(ax, image, matrix, sp, cfg, opts.get("fmt", opts.get("value_format", ".2f")))
    matrix_ticks(ax, xs, ys, cfg)
    axis_labels(ax, sp)
    colorbar(ax, image, sp, cfg)
    return []
