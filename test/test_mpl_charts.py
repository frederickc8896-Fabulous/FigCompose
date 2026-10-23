"""Numerical and geometry regressions for the Matplotlib chart builders."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import numpy as np
import pytest

from data_visuals.renderer.mpl.charts.registry import _BUILDERS
from data_visuals.renderer.mpl.config import MplConfig


@pytest.fixture
def drawing():
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_axes([0.15, 0.2, 0.65, 0.65])
    yield fig, ax, MplConfig("general", 2)
    plt.close(fig)


def subplot(chart, mapping, rows, **opts):
    return {"chart": chart, "data": mapping, "computed_data": rows,
            "font_sizes": {"title": 17, "axis_label": 13, "tick": 11, "legend": 11},
            "options": opts}


@pytest.mark.parametrize("chart", list(_BUILDERS))
def test_empty_payload_does_not_create_extra_axes(drawing, chart):
    fig, ax, cfg = drawing
    assert _BUILDERS[chart](ax, subplot(chart, {}, []), cfg, {}) == []
    assert len(fig.axes) == 1


def test_horizontal_bar_groups_errors_reference_labels_and_y2(drawing):
    fig, ax, cfg = drawing
    sp = subplot("bar", {"x": "case", "y": "score", "group": "model", "error": "err", "y2": "cost"},
                 [{"case": c, "model": g, "score_mean": v, "err": .2, "cost_mean": v * 10}
                  for c, g, v in [("x", "A", 2), ("x", "B", 3), ("y", "A", 4), ("y", "B", 5)]],
                 horizontal=True, hline=3, hline_label="Target", mean_line=True, mean_line_label="Average")
    sp["derived_data"] = {"overall_mean": {"score_mean": 3.5}}
    handles = _BUILDERS["bar"](ax, sp, cfg, {"A": "red", "B": "blue"})
    assert [h.get_label() for h in handles] == ["A", "B", "Target", "Average"]
    assert ax._data_visuals_axis_labels == {"x": "score", "y": "case"}
    assert [p.get_width() for p in ax.patches] == [2, 4, 3, 5]
    assert len(ax.collections) == 2  # one error-bar collection per model
    assert handles[-2].get_color() == cfg.ref_line_color
    np.testing.assert_allclose(handles[-1].get_xdata(), [3.5, 3.5])
    twin, = ax._data_visuals_secondary_axes
    assert twin.get_xlabel() == "cost"
    assert twin.xaxis.label.get_fontsize() == 13
    assert len(fig.axes) == 2


def test_stacked_multi_y_uses_separate_positive_and_negative_baselines(drawing):
    _, ax, cfg = drawing
    sp = subplot("bar", {"x": "case", "y": ["first", "second", "third"]},
                 [{"case": "x", "first_mean": 2, "second_mean": -3, "third_mean": 4}], stacked=True)
    handles = _BUILDERS["bar"](ax, sp, cfg, {"first": "red", "second": "blue", "third": "green"})
    assert [h.get_label() for h in handles] == ["first", "second", "third"]
    assert [p.get_y() for p in ax.patches] == [0, 0, 2]
    assert [p.get_height() for p in ax.patches] == [2, -3, 4]


def test_percent_bar_consumes_normalized_payload(drawing):
    _, ax, cfg = drawing
    sp = subplot("bar", {"x": "case", "y": ["first", "second"]},
                 [{"case": "x", "first_mean": .25, "second_mean": .75}], stacked="percent")
    _BUILDERS["bar"](ax, sp, cfg, {})
    assert ax.patches[-1].get_y() + ax.patches[-1].get_height() == 1
    assert ax.yaxis.get_major_formatter().xmax == 1


def test_grouped_numeric_lines_y2_and_multi_y(drawing):
    _, ax, cfg = drawing
    rows = [{"epoch": x, "model": group, "loss": x + 1, "score": x + 2, "cost": x * 10}
            for group in ["B", "A"] for x in [10, 1, 4]]
    sp = subplot("line", {"x": "epoch", "y": ["loss", "score"], "group": "model", "y2": "cost"},
                 rows, markers=False, area=True, step=True)
    handles = _BUILDERS["line"](ax, sp, cfg, {"A": "red", "B": "blue"})
    assert len(handles) == 5
    np.testing.assert_array_equal(handles[0].get_xdata(), [1, 4, 10])
    assert handles[0].get_color() == "red"
    assert handles[0].get_drawstyle() == "steps-mid"
    assert handles[0].get_marker() == "None"
    twin, = ax._data_visuals_secondary_axes
    assert len(twin.lines) == 2
    assert [line.get_color() for line in twin.lines] == ["red", "blue"]
    assert {line.get_marker() for line in twin.lines} == {"D"}
    assert handles[-1].get_label() == "cost"
    assert handles[-1].get_marker() == "D"
    assert handles[-1].is_dashed()
    assert twin.yaxis.label.get_fontsize() == 13


def test_bar_error_mapped_to_y_uses_spread_not_mean(drawing):
    _, ax, cfg = drawing
    sp = subplot("bar", {"x": "case", "y": ["accuracy", "f1"], "error": "accuracy"},
                 [{"case": "A", "accuracy_mean": .8, "accuracy_std": .02,
                   "f1_mean": .7, "f1_std": .03}])
    _BUILDERS["bar"](ax, sp, cfg, {})
    np.testing.assert_allclose(ax.collections[0].get_segments()[0][:, 1], [.78, .82])
    np.testing.assert_allclose(ax.collections[1].get_segments()[0][:, 1], [.67, .73])


def test_ungrouped_dual_axis_line_labels_both_metrics(drawing):
    _, ax, cfg = drawing
    sp = subplot("line", {"x": "epoch", "y": "loss", "y2": "latency"},
                 [{"epoch": 1, "loss": .8, "latency": 3},
                  {"epoch": 2, "loss": .6, "latency": 4}])
    handles = _BUILDERS["line"](ax, sp, cfg, {})
    assert [handle.get_label() for handle in handles] == ["loss", "latency"]
    assert handles[1].get_color() == cfg.y2_color
    assert handles[1].get_marker() == "D"


def test_scatter_bubble_area_and_trend_payload_column(drawing):
    _, ax, cfg = drawing
    sp = subplot("scatter", {"x": "x", "y": "y", "group": "model", "size": "n"},
                 [{"x": 1, "y": 2, "n": 2, "model": "A"},
                  {"x": 2, "y": 3, "n": 8, "model": "B"}], trend=True, opacity=.4)
    sp["derived_data"] = {"trend_data": [{"x": 2, "y": 5, "model": "A"},
                                              {"x": 1, "y": 4, "model": "A"}]}
    handles = _BUILDERS["scatter"](ax, sp, cfg, {"A": "red", "B": "blue"})
    assert handles[1].get_sizes()[0] / handles[0].get_sizes()[0] == 4
    assert handles[0].get_alpha() == .4
    np.testing.assert_array_equal(ax.lines[0].get_ydata(), [4, 5])
    assert ax.lines[0].get_color() == "red"


def test_box_uses_actual_whisker_extrema_and_optional_outliers(drawing):
    _, ax, cfg = drawing
    sp = subplot("box", {"x": "case", "y": "score", "group": "model"}, [],
                 horizontal=True, show_outliers=False, mean_line=True)
    sp["derived_data"] = {
        "box_summary": [{"case": "x", "model": "A", "Q1": 2, "median": 3, "Q3": 4,
                         "min": 1, "max": 5, "lower": -1, "upper": 7}],
        "box_outliers": [{"case": "x", "model": "A", "score": 100}],
        "overall_mean": {"score": 3.2}}
    handles = _BUILDERS["box"](ax, sp, cfg, {"A": "red"})
    assert [h.get_label() for h in handles] == ["A", "Mean"]
    assert ax._data_visuals_axis_labels == {"x": "score", "y": "case"}
    np.testing.assert_array_equal(ax.lines[0].get_xdata(), [1, 2])
    assert not ax.collections
    assert ax.patches[0].get_facecolor() == to_rgba("red", .35)


def test_histogram_keeps_groups_and_common_bins(drawing):
    _, ax, cfg = drawing
    sp = subplot("histogram", {"x": "value", "group": "model"},
                 [{"value": v, "model": g} for g, values in [("A", [0, 1]), ("B", [2, 3, 4])]
                  for v in values], bins=2)
    handles = _BUILDERS["histogram"](ax, sp, cfg, {"A": "red", "B": "blue"})
    assert [h.get_label() for h in handles] == ["A", "B"]
    assert [p.get_x() for p in ax.patches] == [0, 2, 0, 2]
    assert sum(p.get_height() for p in ax.patches[:2]) == 2
    assert sum(p.get_height() for p in ax.patches[2:]) == 3
    assert ax._data_visuals_axis_labels["y"] == "Count"


def test_cumulative_density_integrates_kde_and_preserves_constant_group(drawing):
    _, ax, cfg = drawing
    sp = subplot("histogram", {"x": "value", "group": "model"},
                 [{"value": 0, "model": "A"}, {"value": 2, "model": "A"},
                  {"value": 1, "model": "B"}], density=True, cumulative=True)
    sp["derived_data"] = {"density_data": [{"value": v, "density": d, "model": "A"}
                                           for v, d in [(0, .2), (1, .6), (2, .2)]]}
    handles = _BUILDERS["histogram"](ax, sp, cfg, {})
    assert [h.get_label() for h in handles] == ["A", "B"]
    np.testing.assert_allclose(handles[0].get_ydata(), [0, .5, 1])
    assert ax._data_visuals_axis_labels["y"] == "Cumulative Probability"


@pytest.mark.parametrize("chart", ["heatmap", "confusion"])
def test_matrix_colorbar_does_not_resize_axes_and_obeys_annotation_option(drawing, chart):
    fig, ax, cfg = drawing
    sp = subplot(chart, {"x": "pred", "y": "true", "value": "value"},
                 [{"pred": "a", "true": "a", "value": 2},
                  {"pred": "b", "true": "a", "value": 1}], annotate=False, color_scheme="viridis")
    sp["_colorbar_box"] = [.85, .2, .02, .65]
    sp["_colorbar_font_size"] = 9
    before = ax.get_position().bounds
    _BUILDERS[chart](ax, sp, cfg, {})
    np.testing.assert_allclose(ax.get_position().bounds, before)
    assert len(fig.axes) == 2
    np.testing.assert_allclose(fig.axes[1].get_position().bounds, sp["_colorbar_box"])
    assert not ax.texts
    assert fig.axes[1].get_yticklabels()[0].get_fontsize() == 9


def test_heatmap_annotations_keep_missing_cells_blank_and_use_spec_font(drawing):
    _, ax, cfg = drawing
    sp = subplot("heatmap", {"x": "x", "y": "y", "value": "v"},
                 [{"x": "a", "y": "a", "v_mean": .2},
                  {"x": "b", "y": "b", "v_mean": .8}], fmt=".1f")
    _BUILDERS["heatmap"](ax, sp, cfg, {})
    assert [text.get_text() for text in ax.texts] == ["0.2", "0.8"]
    assert {text.get_fontsize() for text in ax.texts} == {11}


def test_confusion_keeps_classes_missing_from_one_axis(drawing):
    _, ax, cfg = drawing
    sp = subplot("confusion", {"x": "pred", "y": "true"},
                 [{"pred": "a", "true": "a", "pred_count": 2},
                  {"pred": "a", "true": "b", "pred_count": 1}])
    _BUILDERS["confusion"](ax, sp, cfg, {})
    np.testing.assert_array_equal(ax.images[0].get_array(), [[2, 0], [1, 0]])


@pytest.mark.parametrize("chart", ["heatmap", "confusion"])
def test_matrix_shared_domain_preserves_value_colours_and_explicit_domain_wins(drawing, chart):
    fig, ax, cfg = drawing
    sp = subplot(chart, {"x": "x", "y": "y", "value": "v"},
                 [{"x": "a", "y": "a", "v": .2}, {"x": "b", "y": "a", "v": .5}])
    sp["_color_limits"] = (0, 1)
    _BUILDERS[chart](ax, sp, cfg, {})
    first = ax.images[0]
    assert first.norm(.5) == .5
    other = fig.add_axes([.15, .2, .65, .65])
    sp["computed_data"][0]["v"] = .8
    _BUILDERS[chart](other, sp, cfg, {})
    np.testing.assert_array_equal(first.cmap(first.norm(.5)), other.images[0].cmap(other.images[0].norm(.5)))
    explicit = fig.add_axes([.15, .2, .65, .65])
    sp["options"]["color_domain"] = [0, 2]
    _BUILDERS[chart](explicit, sp, cfg, {})
    assert explicit.images[0].norm(.5) == .25


@pytest.mark.parametrize("domain", [[1, 1], [2, 1], [0, "1"], [0, float("inf")], [False, 1], [0]])
def test_matrix_rejects_invalid_explicit_colour_domains(drawing, domain):
    _, ax, cfg = drawing
    sp = subplot("heatmap", {"x": "x", "y": "y", "value": "v"},
                 [{"x": "a", "y": "a", "v": .2}], color_domain=domain)
    with pytest.raises(ValueError, match="Colour domain"):
        _BUILDERS["heatmap"](ax, sp, cfg, {})
