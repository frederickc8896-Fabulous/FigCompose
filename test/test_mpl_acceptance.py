"""Acceptance checks for reusable, mixed-chart publication figures.

These assertions inspect rendered artists and their measured bounds instead of
comparing pixels, so font rasterization differences do not mask layout errors.
"""

from __future__ import annotations

from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.legend import Legend
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
import pytest

from demo.demo_publication_mixed import (
    build_publication_mixed,
    build_publication_stress,
    publication_data,
)


def _text(text: str) -> str:
    return " ".join(text.split())


def _legend_labels(legend) -> set[str]:
    return {_text(item.get_text()) for item in legend.get_texts()}


def _assert_inside(outer, inner, *, tolerance: float = 1.0) -> None:
    assert np.all(np.isfinite(inner.extents)), inner.extents
    assert inner.x0 >= outer.x0 - tolerance, (inner.extents, outer.extents)
    assert inner.y0 >= outer.y0 - tolerance, (inner.extents, outer.extents)
    assert inner.x1 <= outer.x1 + tolerance, (inner.extents, outer.extents)
    assert inner.y1 <= outer.y1 + tolerance, (inner.extents, outer.extents)


def _main_axes(figure):
    return [axis for axis in figure.axes if axis.get_title()]


def _header_legends(figure):
    return [artist for artist in figure._data_visuals_layout["header_artists"]
            if isinstance(artist, Legend)]


def test_acceptance_data_is_repeatable_and_builder_has_no_export_side_effect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pd.testing.assert_frame_equal(publication_data(), publication_data())
    mixed = build_publication_mixed().build()
    assert {subplot.chart_type for subplot in mixed.subplots} == {
        "bar", "line", "scatter", "box", "heatmap", "histogram", "confusion",
    }
    assert mixed.subplots[0].row_span == mixed.subplots[0].col_span == 2
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("build", [build_publication_mixed, build_publication_stress])
def test_publication_artists_fit_canvas_and_panels_do_not_collide(build):
    figure = build().render()
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        for axis in figure.axes:
            if axis.get_visible():
                _assert_inside(figure.bbox, axis.get_tightbbox(renderer))
        for legend in figure.legends:
            _assert_inside(figure.bbox, legend.get_window_extent(renderer))
        for text in figure.texts:
            if text.get_visible() and text.get_text():
                _assert_inside(figure.bbox, text.get_window_extent(renderer))
        for cell in figure._data_visuals_layout["cells"].values():
            box = cell["cell"]
            boundary = Bbox.from_bounds(
                box["x"], figure.bbox.height - box["y"] - box["h"], box["w"], box["h"],
            )
            axes = [cell["axes"]] + cell["secondary_axes"] + cell["colorbar_axes"]
            decorations = [axis.get_tightbbox(renderer) for axis in axes]
            decorations += [legend.get_window_extent(renderer) for legend in cell["legends"]]
            _assert_inside(boundary, Bbox.union(decorations))
        main_axes = _main_axes(figure)
        assert len(main_axes) == (7 if build is build_publication_mixed else 4)
        for first, second in combinations(main_axes, 2):
            overlap = first.get_tightbbox(renderer).intersection(
                first.get_tightbbox(renderer), second.get_tightbbox(renderer),
            )
            assert overlap is None or overlap.width <= 1 or overlap.height <= 1
        tick_sizes = {round(axis.xaxis.get_ticklabels()[0].get_fontsize(), 2)
                      for axis in main_axes if axis.xaxis.get_ticklabels()}
        assert len(tick_sizes) == 1, tick_sizes
    finally:
        plt.close(figure)


def test_mixed_figure_keeps_shared_and_independent_legends_separate():
    figure = build_publication_mixed().render()
    try:
        expected_models = set(publication_data()["model"])
        shared = _header_legends(figure)
        assert len(shared) == 1
        assert _legend_labels(shared[0]) == expected_models
        scatter_axis = next(axis for axis in _main_axes(figure)
                            if axis.get_title().startswith("(c)"))
        cells = figure._data_visuals_layout["cells"]
        scatter_legends = cells[(0, 3)]["legends"]
        assert scatter_legends
        assert set().union(*map(_legend_labels, scatter_legends)) == {"Clean input", "Shifted input"}
        assert cells[(0, 3)]["axes"] is scatter_axis
        assert all(not cell["legends"] for position, cell in cells.items()
                   if position != (0, 3))
    finally:
        plt.close(figure)


def test_mixed_titles_have_clearance_and_long_labels_do_not_shrink_neighbours():
    figure = build_publication_mixed().render()
    try:
        renderer = figure.canvas.get_renderer()
        cells = figure._data_visuals_layout["cells"]
        for cell in cells.values():
            axis = cell["axes"]
            title = axis.title.get_window_extent(renderer)
            if cell["legends"]:
                legends = [legend.get_window_extent(renderer) for legend in cell["legends"]]
                assert title.y0 - max(box.y1 for box in legends) >= axis.title.get_fontsize() * 0.2
                assert min(box.y0 for box in legends) - axis.bbox.y1 >= 5
            else:
                # A real visible gap, independent of font descent and DPI.
                assert title.y0 - axis.bbox.y1 >= axis.title.get_fontsize() * 0.5
        # The spanning bar's long rotated labels must not impose the same bottom
        # gutter on the short-label box plot and numeric-label histogram.
        bar = cells[(0, 0)]["axes"].bbox
        box = cells[(1, 2)]["axes"].bbox
        histogram = cells[(1, 3)]["axes"].bbox
        tick_size = cells[(1, 2)]["axes"].get_xticklabels()[0].get_fontsize()
        assert bar.y0 - box.y0 >= tick_size * 2
        assert bar.y0 - histogram.y0 >= tick_size * 2
        assert histogram.height > box.height
    finally:
        plt.close(figure)


def test_mixed_model_colors_are_reused_by_actual_bar_line_and_histogram_artists():
    figure = build_publication_mixed().render()
    try:
        axes = {axis.get_title()[:3]: axis for axis in _main_axes(figure)}
        bar_handles, bar_labels = axes["(a)"].get_legend_handles_labels()
        line_handles, line_labels = axes["(b)"].get_legend_handles_labels()
        hist_handles, hist_labels = axes["(e)"].get_legend_handles_labels()
        bars = {label: to_rgba(handle.patches[0].get_facecolor())[:3]
                for handle, label in zip(bar_handles, bar_labels)
                if hasattr(handle, "patches")}
        lines = {label: to_rgba(handle.get_color())[:3]
                 for handle, label in zip(line_handles, line_labels)
                 if hasattr(handle, "get_color")}
        hist = {label: to_rgba(handle.get_facecolor())[:3]
                for handle, label in zip(hist_handles, hist_labels)
                if hasattr(handle, "get_facecolor")}
        models = set(publication_data()["model"])
        assert models <= bars.keys() & lines.keys() & hist.keys()
        for model in models:
            assert bars[model] == pytest.approx(lines[model])
            assert bars[model] == pytest.approx(hist[model])
    finally:
        plt.close(figure)


def test_stress_legend_wraps_without_losing_models_or_reference_lines():
    figure = build_publication_stress().render()
    try:
        figure.canvas.draw()
        models = set(publication_data(many_models=True)["model"])
        shared = _header_legends(figure)
        assert set().union(*map(_legend_labels, shared)) == models
        renderer = figure.canvas.get_renderer()
        model_texts = [text for legend in shared for text in legend.get_texts()
                       if _text(text.get_text()) in models]
        assert len({round(text.get_window_extent(renderer).y0, 1) for text in model_texts}) > 1
        all_labels = set().union(*(_legend_labels(legend) for legend in figure.legends))
        assert {"Target accuracy", "Observed mean", "precision", "recall"} <= all_labels
        for legend in shared:
            _assert_inside(figure.bbox, legend.get_window_extent(renderer))
        secondary_axes = [axis for axis in figure.axes if axis.get_ylabel() == "latency"]
        assert len(secondary_axes) == 1
    finally:
        plt.close(figure)


def test_mixed_error_bars_use_standard_deviation_instead_of_bar_means():
    declared = build_publication_mixed()
    expected = declared.build().subplots[0].computed_data["accuracy_std"].to_numpy()
    figure = declared.render()
    try:
        axis = figure._data_visuals_layout["cells"][(0, 0)]["axes"]
        observed = []
        for container in axis.containers:
            errorbar = getattr(container, "errorbar", None)
            if errorbar is not None:
                for collection in errorbar.lines[2]:
                    for segment in collection.get_segments():
                        observed.append(abs(segment[1, 1] - segment[0, 1]) / 2)
        assert np.sort(observed) == pytest.approx(np.sort(expected))
    finally:
        plt.close(figure)


def test_stress_multi_y_averages_replicates_and_secondary_axis_reuses_model_colors():
    data = publication_data(many_models=True)
    figure = build_publication_stress(data).render()
    try:
        cells = figure._data_visuals_layout["cells"]
        measures = cells[(0, 1)]["axes"]
        expected = data.groupby("epoch")[["precision", "recall"]].mean()
        for line in measures.lines:
            if line.get_label() in expected.columns:
                assert line.get_xdata() == pytest.approx(expected.index.to_numpy())
                assert line.get_ydata() == pytest.approx(expected[line.get_label()].to_numpy())
        primary = cells[(0, 0)]["axes"]
        secondary = cells[(0, 0)]["secondary_axes"][0]
        primary_colors = sorted(to_rgba(line.get_color()) for line in primary.lines)
        secondary_colors = sorted(to_rgba(line.get_color()) for line in secondary.lines)
        assert len(primary_colors) == len(secondary_colors) == data["model"].nunique()
        assert primary_colors == secondary_colors
    finally:
        plt.close(figure)
