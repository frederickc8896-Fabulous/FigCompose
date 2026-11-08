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
    from data_visuals.renderer.mpl.charts.pie import _draw_pie
    from data_visuals.renderer.mpl.charts.radar import _draw_radar
    from data_visuals.renderer.mpl.charts.circular_bar import _draw_circular_bar
    from data_visuals.renderer.mpl.charts.chord import _draw_chord
    from data_visuals.renderer.mpl.charts.distribution import _draw_raincloud, _draw_ridgeline
    from data_visuals.renderer.mpl.charts.three_d import _draw_scatter3d, _draw_waterfall3d, _draw_bar3d
    from data_visuals.renderer.mpl.charts.paired import _draw_paired, _draw_estimation

    _BUILDERS.update({
        "bar": _draw_bar,
        "line": _draw_line,
        "scatter": _draw_scatter,
        "box": _draw_box,
        "heatmap": _draw_heatmap,
        "histogram": _draw_histogram,
        "confusion": _draw_confusion,
        "pie": _draw_pie,
        "donut": _draw_pie,
        "radar": _draw_radar,
        "circular_bar": _draw_circular_bar,
        "chord": _draw_chord,
        "raincloud": _draw_raincloud,
        "ridgeline": _draw_ridgeline,
        "scatter3d": _draw_scatter3d,
        "waterfall3d": _draw_waterfall3d,
        "bar3d": _draw_bar3d,
        "paired": _draw_paired,
        "estimation": _draw_estimation,
    })


_populate()
