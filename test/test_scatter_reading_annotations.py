"""Reading aids keep numeric coordinates and participate in layout measurement."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import numpy as np
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.renderer.mpl.charts.scatter import _draw_scatter
from data_visuals.renderer.mpl.config import MplConfig


@pytest.fixture
def drawing():
    fig = plt.figure(figsize=(4, 3), dpi=72)
    ax = fig.add_axes((.2, .2, .7, .7))
    yield fig, ax, MplConfig("modern", physical=True)
    plt.close(fig)


def _draw(ax, cfg, **options):
    return _draw_scatter(ax, {
        "data": {"x": "cost", "y": "loss"},
        "font_sizes": {"axis_label": 8, "tick": 8},
        "computed_data": [{"cost": 2, "loss": .25}, {"cost": 6, "loss": .75}],
        "options": options,
    }, cfg, {})


def test_custom_tick_labels_keep_numeric_positions_and_explicit_limits(drawing):
    _, ax, cfg = drawing
    _draw(ax, cfg, xticks=[0, 5, 10], xticklabels=["Low", "Medium", "High"],
          yticks=[0, 1], yticklabels=["Before", "After"], xlim=[0, 8], ylim=[.1, .9])
    np.testing.assert_array_equal(ax.get_xticks(), [0, 5, 10])
    np.testing.assert_array_equal(ax.get_yticks(), [0, 1])
    assert [label.get_text() for label in ax.get_xticklabels()] == ["Low", "Medium", "High"]
    assert [label.get_text() for label in ax.get_yticklabels()] == ["Before", "After"]
    assert ax.get_xlim() == (0, 8)  # An outside tick does not expand a requested domain.
    assert ax.get_ylim() == (.1, .9)
    np.testing.assert_array_equal(ax.collections[0].get_offsets(), [[2, .25], [6, .75]])


def test_reading_annotations_use_declared_coordinates_without_changing_data(drawing):
    fig, ax, cfg = drawing
    _draw(ax, cfg, xlim=[0, 8], ylim=[0, 1], annotations=[
        {"text": "Before to after", "xy": [.5, .9], "ha": "center", "va": "top"},
        {"text": "2.00 to 6.00", "xy": [4, .5], "coords": "data", "fontsize": 9,
         "ha": "right", "va": "bottom", "fontweight": "bold", "color": "#cc6600"},
    ])
    default, styled = ax._data_visuals_text_annotations
    assert default.xy == (.5, .9)
    assert default.xycoords == "axes fraction"
    assert default.get_fontsize() == 8
    assert default.get_fontfamily() == [cfg.font_family]
    assert default.get_ha() == "center"
    assert default.get_va() == "top"
    assert default.get_color() == cfg.text_color
    assert styled.xy == (4, .5)
    assert styled.xycoords == "data"
    assert styled.get_fontsize() == 9
    assert styled.get_fontweight() == "bold"
    assert styled.get_ha() == "right"
    assert styled.get_va() == "bottom"
    assert to_rgba(styled.get_color()) == to_rgba("#cc6600")
    fig.canvas.draw()
    for annotation in (default, styled):
        assert annotation.get_in_layout()
        box = annotation.get_window_extent(fig.canvas.get_renderer())
        assert ax.bbox.contains(box.x0, box.y0)
        assert ax.bbox.contains(box.x1, box.y1)
    assert ax.get_xlim() == (0, 8)
    assert ax.get_ylim() == (0, 1)


def test_annotation_font_size_is_physical_and_not_scaled_by_dpi(drawing):
    fig, ax, cfg = drawing
    _draw(ax, cfg, annotations=[{"text": "A readable annotation", "xy": [.05, .9]}])
    annotation, = ax._data_visuals_text_annotations
    widths_pt = []
    for dpi in (72, 144):
        fig.set_dpi(dpi)
        fig.canvas.draw()
        widths_pt.append(annotation.get_window_extent(fig.canvas.get_renderer()).width * 72 / dpi)
        assert annotation.get_fontsize() == 8
    assert widths_pt[0] == pytest.approx(widths_pt[1], abs=1)


def test_overflowing_annotation_is_included_in_axes_tightbbox(drawing):
    fig, ax, cfg = drawing
    _draw(ax, cfg, annotations=[{
        "text": "A deliberately long reading annotation", "xy": [1, .5], "ha": "left",
    }])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    annotation, = ax._data_visuals_text_annotations
    text_box = annotation.get_window_extent(renderer)
    measured_box = ax.get_tightbbox(renderer, for_layout_only=True)
    assert text_box.x1 > ax.bbox.x1
    assert measured_box.x1 >= text_box.x1
    assert measured_box.y0 <= text_box.y0
    assert measured_box.y1 >= text_box.y1


def _shared_y_figure(labels_by_column):
    figure = Figure(
        data=pd.DataFrame({"cost": [2, 6], "loss": [.25, .75]}), rows=1, cols=2,
        canvas={"width": 7, "height": 2.8, "unit": "in"},
        config=FigureConfig(facets={"sharey": True}),
    )
    for column, labels in enumerate(labels_by_column):
        options = {"yticks": [0, 1], "ylim": [0, 1]}
        if labels is not None:
            options["yticklabels"] = labels
        figure[0, column].scatter(x="cost", y="loss", title=None, chart_opts=options)
    return figure


def test_conflicting_labels_for_shared_numeric_ticks_raise_without_leaking_a_figure():
    figure = _shared_y_figure([["Before", "After"], ["Initial", "Final"]])
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match="identical yticklabels"):
        figure.render()
    assert set(plt.get_fignums()) == before


def test_labels_declared_only_in_later_panel_propagate_to_the_shared_axis():
    figure = _shared_y_figure([None, ["Before", "After"]]).render()
    try:
        cells = figure._data_visuals_layout["cells"]
        first, second = cells[0, 0]["axes"], cells[0, 1]["axes"]
        assert first.get_shared_y_axes().joined(first, second)
        np.testing.assert_array_equal(first.get_yticks(), [0, 1])
        np.testing.assert_array_equal(second.get_yticks(), [0, 1])
        assert [text.get_text() for text in first.get_yticklabels()] == ["Before", "After"]
        assert not second.get_yticklabels()  # Only the outer axis draws labels.
        assert [second.yaxis.get_major_formatter()(tick, index)
                for index, tick in enumerate(second.get_yticks())] == ["Before", "After"]
    finally:
        plt.close(figure)


@pytest.mark.parametrize("options,match", [
    ({"xticklabels": ["Only"]}, "xticklabels requires xticks"),
    ({"yticklabels": ["Only"]}, "yticklabels requires yticks"),
    ({"xticks": [0, 1], "xticklabels": ["Only"]}, "same length"),
    ({"yticks": [0], "yticklabels": ["A", "B"]}, "same length"),
    ({"xticks": [0], "xticklabels": "A"}, "list of strings"),
    ({"yticks": [0], "yticklabels": [4]}, "list of strings"),
    ({"xticks": [0], "xticklabels": ("A",)}, "list of strings"),
    ({"annotations": None}, "annotations"),
    ({"annotations": {}}, "annotations"),
    ({"annotations": ["text"]}, "annotation requires"),
    ({"annotations": [{"text": "Missing location"}]}, "annotation requires"),
    ({"annotations": [{"xy": [0, 0]}]}, "annotation requires"),
    ({"annotations": [{"text": "Extra", "xy": [0, 0], "unknown": 1}]}, "annotation requires"),
    ({"annotations": [{"text": 7, "xy": [0, 0]}]}, "annotations.text"),
    ({"annotations": [{"text": "A", "xy": [False, 0]}]}, "annotations.xy"),
    ({"annotations": [{"text": "A", "xy": [float("nan"), 0]}]}, "annotations.xy"),
    ({"annotations": [{"text": "A", "xy": [0, 1, 2]}]}, "annotations.xy"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "coords": "figure"}]}, "annotations.coords"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "fontsize": 0}]}, "fontsize"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "fontsize": True}]}, "fontsize"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "fontsize": float("inf")}]}, "fontsize"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "ha": "bottom"}]}, "annotations.ha"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "va": "left"}]}, "annotations.va"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "fontweight": "light"}]}, "fontweight"),
    ({"annotations": [{"text": "A", "xy": [0, 1], "color": "not-a-color"}]}, "annotations.color"),
])
def test_invalid_reading_aids_fail_with_clear_error(drawing, options, match):
    _, ax, cfg = drawing
    with pytest.raises(ValueError, match=match):
        _draw(ax, cfg, **options)
