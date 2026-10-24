"""Confusion matrices consume counts/normalised values from the compute layer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .helpers import (annotate_matrix, axis_labels, color_norm, color_scheme, colorbar,
                      frame, matrix_ticks, ordered, value_column)


def _draw_confusion(ax, sp, cfg, color_map):
    df = frame(sp.get("computed_data", []))
    if df.empty:
        return []
    mapping, opts = sp["data"], sp.get("options", {})
    x_col, y_col = mapping["x"], mapping["y"]
    column = value_column(df, mapping["value"]) if mapping.get("value") else f"{x_col}_count"
    if column not in df.columns:
        raise ValueError("Confusion data requires a value mapping or computed count column")
    labels = ordered(pd.concat([df[x_col], df[y_col]], ignore_index=True))
    matrix = df.pivot(index=y_col, columns=x_col, values=column).reindex(index=labels, columns=labels).fillna(0).to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(matrix), aspect="auto", interpolation="nearest",
                      cmap=color_scheme(sp, cfg), norm=color_norm(sp))
    annotate_matrix(ax, image, matrix, sp, cfg,
                    opts.get("fmt", opts.get("value_format", ".2f" if opts.get("normalize") else ".0f")))
    matrix_ticks(ax, labels, labels, cfg)
    axis_labels(ax, sp)
    colorbar(ax, image, sp, cfg)
    return []
