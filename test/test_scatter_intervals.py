"""Supplied asymmetric intervals and physical group dodging preserve numeric data."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import numpy as np
import pytest

from data_visuals.renderer.mpl.charts.scatter import _draw_scatter
from data_visuals.renderer.mpl.config import MplConfig


ROWS = [
    {"x": .875, "difference": -12, "lower": -16, "upper": -10, "base": "a"},
    {"x": 1.875, "difference": -18, "lower": -21, "upper": -13, "base": "a"},
    {"x": .875, "difference": -7, "lower": -10, "upper": -1, "base": "b"},
    {"x": 1.875, "difference": -9, "lower": -9, "upper": -5, "base": "b"},
]
STYLES = {"a": {"marker": "o", "color": "#496d8e", "size": 20},
          "b": {"marker": "D", "color": "#b3664a", "size": 24, "facecolor": "none", "edgecolor": "#b3664a"}}


@pytest.fixture
def drawing():
    fig = plt.figure(figsize=(3.5, 2.5), dpi=72)
    ax = fig.add_axes((.2, .2, .7, .7))
    yield fig, ax, MplConfig("modern", physical=True)
    plt.close(fig)


def _draw(ax, cfg, rows=None, **options):
    return _draw_scatter(ax, {
        "data": {"x": "x", "y": "difference", "group": "base"},
        "font_sizes": {"axis_label": 8, "tick": 8},
        "computed_data": ROWS if rows is None else rows,
        "options": {"series_styles": STYLES, "opacity": 1,
                    "xlim": [0, 11], "ylim": [-25, 5], **options},
    }, cfg, {"a": "red", "b": "blue"})


def test_supplied_interval_endpoints_colors_and_markers_are_preserved(drawing):
    fig, ax, cfg = drawing
    handles = _draw(ax, cfg, errorbar={"lower": "lower", "upper": "upper", "capsize": 2.5,
                                      "linewidth": .9, "alpha": .65})
    assert set(ax._data_visuals_errorbars) == {"a", "b"}
    for handle in handles:
        key = handle._data_visuals_series_key
        rows = [row for row in ROWS if row["base"] == key]
        np.testing.assert_array_equal(handle.get_offsets(), [[row["x"], row["difference"]] for row in rows])
        container = ax._data_visuals_errorbars[key]
        center, caps, collections = container.lines
        assert center is None  # Independent scatter markers provide the shape and legend.
        assert len(caps) == 2
        line, = collections
        np.testing.assert_array_equal(line.get_segments(), [
            [[row["x"], row["lower"]], [row["x"], row["upper"]]] for row in rows])
        np.testing.assert_allclose(line.get_colors()[0], to_rgba(STYLES[key]["color"], .65))
        np.testing.assert_allclose(line.get_linewidths(), [.9])
        assert line.get_alpha() == .65
        assert handle.get_alpha() == 1
        for cap in caps:
            assert cap.get_markersize() == 5
            assert cap.get_markeredgewidth() == .9
            assert cap.get_alpha() == .65
    assert handles[1].get_facecolors().size == 0
    fig.canvas.draw()


@pytest.mark.parametrize("dpi", [72, 144])
def test_dodging_shifts_markers_and_intervals_by_physical_points_without_changing_x(drawing, dpi):
    fig, ax, cfg = drawing
    fig.set_dpi(dpi)
    offsets = {"a": -3.25, "b": 3.25}
    handles = _draw(ax, cfg, errorbar={"lower": "lower", "upper": "upper"}, x_offsets=offsets)
    # Both size and position may change during canvas measurement.
    ax.set_position((.15, .18, .8, .78))
    fig.canvas.draw()
    for handle in handles:
        key = handle._data_visuals_series_key
        rows = [row for row in ROWS if row["base"] == key]
        raw_xy = np.array([[row["x"], row["difference"]] for row in rows])
        np.testing.assert_array_equal(handle.get_offsets(), raw_xy)
        reference = ax.transData.transform(raw_xy)
        visible = handle.get_offset_transform().transform(raw_xy)
        np.testing.assert_allclose((visible - reference) * 72 / dpi,
                                   np.tile([offsets[key], 0], (len(rows), 1)), atol=1e-12)
        _, caps, (line,) = ax._data_visuals_errorbars[key].lines
        for index, row in enumerate(rows):
            segment = np.array([[row["x"], row["lower"]], [row["x"], row["upper"]]])
            np.testing.assert_array_equal(line.get_segments()[index], segment)
            displaced = line.get_transform().transform(segment) - ax.transData.transform(segment)
            np.testing.assert_allclose(displaced * 72 / dpi, [[offsets[key], 0]] * 2, atol=1e-12)
        for cap in caps:
            xy = np.column_stack([cap.get_xdata(), cap.get_ydata()]).astype(float)
            displaced = cap.get_transform().transform(xy) - ax.transData.transform(xy)
            np.testing.assert_allclose(displaced * 72 / dpi, [[offsets[key], 0]] * len(rows), atol=1e-12)


def test_omitting_options_keeps_legacy_scatter_without_intervals_or_offsets(drawing):
    _, ax, cfg = drawing
    handles = _draw(ax, cfg)
    assert ax._data_visuals_errorbars == {}
    assert not ax.containers
    assert not ax.lines
    for handle in handles:
        assert handle._data_visuals_x_offset_pt == 0
        assert handle.get_offset_transform() is ax.transData


def test_default_interval_styling_and_ungrouped_series(drawing):
    _, ax, cfg = drawing
    sp = {"data": {"x": "x", "y": "difference"}, "computed_data": ROWS,
          "font_sizes": {"axis_label": 8, "tick": 8},
          "options": {"errorbar": {"lower": "lower", "upper": "upper"}, "x_offsets": {None: 2}}}
    assert _draw_scatter(ax, sp, cfg, {}) == []
    _, caps, (line,) = ax._data_visuals_errorbars[None].lines
    np.testing.assert_allclose(line.get_linewidths(), [.85])
    assert line.get_alpha() == .8
    assert all(cap.get_markersize() == 4 for cap in caps)


@pytest.mark.parametrize("specification,match", [
    (None, "errorbar requires"),
    ([], "errorbar requires"),
    ({"lower": "lower"}, "errorbar requires"),
    ({"lower": "lower", "upper": "upper", "unknown": 1}, "errorbar requires"),
    ({"lower": "missing", "upper": "upper"}, "errorbar.lower"),
    ({"lower": "lower", "upper": True}, "errorbar.upper"),
    ({"lower": "lower", "upper": "upper", "capsize": -1}, "errorbar.capsize"),
    ({"lower": "lower", "upper": "upper", "capsize": True}, "errorbar.capsize"),
    ({"lower": "lower", "upper": "upper", "linewidth": float("inf")}, "errorbar.linewidth"),
    ({"lower": "lower", "upper": "upper", "alpha": -1}, "errorbar.alpha"),
    ({"lower": "lower", "upper": "upper", "alpha": 1.01}, "errorbar.alpha"),
])
def test_invalid_interval_specifications_are_rejected_before_drawing(drawing, specification, match):
    _, ax, cfg = drawing
    with pytest.raises(ValueError, match=match):
        _draw(ax, cfg, errorbar=specification)
    assert not ax.collections


@pytest.mark.parametrize("column,value,match", [
    ("lower", float("nan"), "errorbar.lower"),
    ("upper", float("inf"), "errorbar.upper"),
    ("difference", float("-inf"), "errorbar.y"),
    ("lower", "-16", "errorbar.lower"),
    ("upper", True, "errorbar.upper"),
    ("lower", -10, "lower <= plotted y <= upper"),
    ("upper", -14, "lower <= plotted y <= upper"),
])
def test_invalid_endpoints_or_estimates_are_not_repaired_or_dropped(drawing, column, value, match):
    _, ax, cfg = drawing
    rows = [dict(row) for row in ROWS]
    rows[0][column] = value
    with pytest.raises(ValueError, match=match):
        _draw(ax, cfg, rows, errorbar={"lower": "lower", "upper": "upper"})
    assert not ax.collections


@pytest.mark.parametrize("options,match", [
    ({"x_offsets": None}, "x_offsets"),
    ({"x_offsets": [1, 2]}, "x_offsets"),
    ({"x_offsets": {"a": True}}, "x_offsets"),
    ({"x_offsets": {"a": float("nan")}}, "x_offsets"),
    ({"x_offsets": {"a": "2"}}, "x_offsets"),
    ({"x_offsets": {"a": 2}, "point_labels": {"column": "base"}}, "cannot be combined with point_labels"),
    ({"x_offsets": {"a": 2}, "trend": True}, "cannot be combined with trend"),
])
def test_invalid_or_unsupported_offset_options_fail_explicitly(drawing, options, match):
    _, ax, cfg = drawing
    with pytest.raises(ValueError, match=match):
        _draw(ax, cfg, **options)
    assert not ax.collections


def test_zero_offsets_allow_point_labels_and_panel_annotations_remain_explicit(drawing):
    _, ax, cfg = drawing
    _draw(ax, cfg, x_offsets={"a": 0, "b": 0}, point_labels={"column": "base"},
          annotations=[{"text": "panel note", "xy": [.5, .9]}])
    assert ax._data_visuals_annotations["point_labels"] == {"column": "base"}
    assert ax._data_visuals_text_annotations[0].xy == (.5, .9)
