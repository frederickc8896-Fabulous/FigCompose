"""
renderer/mpl/charts/registry.py
================================
Matplotlib chart builder registry — maps chart type names to _draw_* functions.

Builders consume computed data, resolved styles and allocated axes.
"""

from __future__ import annotations

from typing import Dict, Callable

_BUILDERS: Dict[str, Callable] = {}


def _populate() -> None:
    from data_visuals.renderer.mpl.charts.bar import _draw_bar
    from data_visuals.renderer.mpl.charts.line import _draw_line
    from data_visuals.renderer.mpl.charts.scatter import _draw_scatter
    from data_visuals.renderer.mpl.charts.box import _draw_box
    from data_visuals.renderer.mpl.charts.heatmap import _draw_heatmap
    from data_visuals.renderer.mpl.charts.histogram import _draw_histogram
    from data_visuals.renderer.mpl.charts.confusion import _draw_confusion

    _BUILDERS.update({
        "bar": _draw_bar,
        "line": _draw_line,
        "scatter": _draw_scatter,
        "box": _draw_box,
        "heatmap": _draw_heatmap,
        "histogram": _draw_histogram,
        "confusion": _draw_confusion,
    })


_populate()
