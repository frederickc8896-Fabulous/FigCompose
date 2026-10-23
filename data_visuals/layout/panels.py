"""Plan a compact, ordered grid for the CSV plotting entry point."""

from __future__ import annotations

import math


def plan_panels(
    count: int, cols: int | None = None,
) -> tuple[list[list[int]], list[tuple[int, int]], float]:
    """Return span weights, declaration positions and a canvas aspect ratio.

    ``cols`` is the maximum number of panels in a row. The last row fills
    the available width instead of leaving unused grid cells. Geometry,
    decoration measurement and collision checks still use the normal layout
    and renderer pipeline.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("至少需要一个子图。")
    if cols is not None and (
        isinstance(cols, bool) or not isinstance(cols, int) or cols < 1
    ):
        raise ValueError("cols 必须是正整数，或省略以自动排版。")

    columns = min(count, cols if cols is not None else min(3, math.ceil(math.sqrt(count))))
    row_counts = [min(columns, count - start) for start in range(0, count, columns)]
    units = math.lcm(*row_counts)
    layout = [[units // n] * n for n in row_counts]
    positions = [
        (row, col * (units // n))
        for row, n in enumerate(row_counts)
        for col in range(n)
    ]
    # Avoid excessively wide or tall canvases for one-row/one-column figures.
    aspect = min(2.0, max(0.75, (4 / 3) * columns / len(row_counts)))
    return layout, positions, aspect
