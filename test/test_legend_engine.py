"""Physical legend overrides are measured and preserve scientific artists."""
from itertools import chain

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
import numpy as np
import pytest

from data_visuals.layout.placement import LayoutError
from data_visuals.renderer.mpl.config import MplConfig
from data_visuals.renderer.mpl.legends import MeasuredLegend


@pytest.fixture
def drawing():
    fig = plt.figure(figsize=(4, 4), dpi=72)
    yield fig, MplConfig("modern", physical=True)
    plt.close(fig)


def _handles(labels):
    return [Line2D([], [], linestyle="", marker=marker, markersize=4 + i,
                   color=color, markerfacecolor=color, markeredgecolor="white",
                   markeredgewidth=0.5, label=label)
            for i, (label, marker, color) in enumerate(zip(
                labels, chain.from_iterable([("o", "s", "^")] * len(labels)),
                chain.from_iterable([("#264653", "#e76f51", "#2a9d8f")] * len(labels))))]


def _engine(drawing, labels=("xsmall", "small", "RoBERTa"), *, handles=None,
            width=270, height=None, orientation="horizontal", **options):
    fig, cfg = drawing
    return MeasuredLegend(fig, handles or _handles(labels), labels, options, cfg,
                          default_fontsize=8, max_width=width, max_height=height,
                          orientation=orientation)


def _texts(engine):
    return [text for legend, _, _ in engine.rows for text in legend.get_texts()]


@pytest.mark.parametrize("dpi", [72, 144, 300])
def test_actual_block_extent_is_in_points_at_every_dpi(drawing, dpi):
    fig, _ = drawing
    fig.set_dpi(dpi)
    engine = _engine(drawing, ncols=2, frameon=True, borderpad=5)
    assert not any(artist.get_visible() for artist in engine.artists)
    artists = engine.place(12, 25)
    assert artists is engine.artists
    fig.canvas.draw()
    bbox = Bbox.union([artist.get_window_extent(fig.canvas.get_renderer()) for artist in artists])
    factor = 72 / dpi
    assert bbox.x0 * factor == pytest.approx(12)
    assert (fig.bbox.height - bbox.y1) * factor == pytest.approx(25)
    assert bbox.width * factor == pytest.approx(engine.width)
    assert bbox.height * factor == pytest.approx(engine.height)
    assert all(text.get_fontfamily() == ["Times New Roman"] for text in _texts(engine))
    before = list(engine.artists)
    engine.place(17, 30)
    assert all(old is new for old, new in zip(before, engine.artists))
    assert len(fig.legends) == 2


def test_automatic_rows_retain_long_legend_labels_and_input_order(drawing):
    labels = tuple(f"Backbone variant {i}" for i in range(1, 8))
    engine = _engine(drawing, labels, width=232)
    assert len(engine.rows) > 1
    assert [text.get_text() for text in _texts(engine)] == list(labels)
    assert engine.width <= 232
    assert all(text.get_fontsize() == 8 for text in _texts(engine))


def test_none_fontsize_inherits_resolved_fontsize(drawing):
    fig, cfg = drawing
    labels = ("xsmall", "small")
    engine = MeasuredLegend(fig, _handles(labels), labels, {"fontsize": None}, cfg,
                            default_fontsize=11, max_width=200)
    assert engine.fontsize == 11
    assert all(text.get_fontsize() == 11 for text in _texts(engine))


def test_fixed_columns_wrap_labels_without_reducing_columns_or_fontsize(drawing):
    labels = tuple(f"Backbone variant {i}" for i in range(1, 9))
    engine = _engine(drawing, labels, width=180, ncols=3, fontsize=10)
    assert [len(row.get_texts()) for row, _, _ in engine.rows] == [3, 3, 2]
    assert engine.width <= 180 + 1e-6
    assert any("\n" in text.get_text() for text in _texts(engine))
    assert ["".join(text.get_text().split()) for text in _texts(engine)] == [
        "".join(label.split()) for label in labels]
    assert all(text.get_fontsize() == 10 for text in _texts(engine))


@pytest.mark.parametrize("options", [{}, {"ncols": 2}])
def test_many_descriptive_entries_need_only_linear_actual_legend_measurements(drawing, monkeypatch, options):
    fig, _ = drawing
    labels = tuple(f"Experiment configuration {i:02d} with a descriptive training procedure and evaluation setup"
                   for i in range(10))
    native_legend = fig.legend
    measurements = []

    def counted_legend(*args, **kwargs):
        legend = native_legend(*args, **kwargs)
        measurements.append(legend)
        return legend

    monkeypatch.setattr(fig, "legend", counted_legend)
    engine = _engine(drawing, labels, width=240, **options)
    assert len(measurements) <= 3 * len(labels)
    assert engine.width <= 240 + 1e-6
    assert ["".join(text.get_text().split()) for text in _texts(engine)] == [
        "".join(label.split()) for label in labels]


def test_an_unbroken_long_label_is_preserved_when_wrapped(drawing):
    label = "EvaluationConfiguration" * 25
    engine = _engine(drawing, (label,), width=180, ncols=1)
    assert len(engine.rows) == 1
    assert engine.width <= 180 + 1e-6
    assert _texts(engine)[0].get_text().replace("\n", "") == label


def test_impossible_fixed_columns_report_width_and_leave_no_artists(drawing):
    fig, _ = drawing
    existing = list(fig.legends)
    with pytest.raises(LayoutError) as error:
        _engine(drawing, width=25, ncols=3)
    assert error.value.axis == "width"
    assert error.value.required_width > 25
    assert fig.legends == existing
    assert not fig.artists


def test_height_failure_reports_measured_size_and_cleans_artists(drawing):
    fig, _ = drawing
    with pytest.raises(LayoutError) as error:
        _engine(drawing, ncols=1, height=15, frameon=True)
    assert error.value.axis == "height"
    assert error.value.required_height > 15
    assert error.value.required_width > 0
    assert not fig.legends
    assert not fig.artists


@pytest.mark.parametrize("option,expected_width,expected_height", [
    ("columnspacing", 10, 0),
    ("labelspacing", 0, 5),
    ("handlelength", 15, 0),
    ("handletextpad", 15, 0),
    ("borderpad", 10, 10),
])
def test_point_spacing_overrides_change_measured_extent(drawing, option, expected_width, expected_height):
    labels = ("A", "B", "C", "D", "E", "F")
    defaults = {"columnspacing": 8, "labelspacing": 3, "handlelength": 12,
                "handletextpad": 4, "borderpad": 3}
    engine = _engine(drawing, labels, ncols=3)
    initial_w, initial_h = engine.width, engine.height
    engine.remove()
    changed = _engine(drawing, labels, ncols=3, **{option: defaults[option] + 5})
    assert changed.width - initial_w == pytest.approx(expected_width)
    assert changed.height - initial_h == pytest.approx(expected_height)


def test_one_frame_surrounds_all_rows_with_explicit_padding(drawing):
    fig, _ = drawing
    engine = _engine(drawing, ncols=1, frameon=True, borderpad=5)
    engine.place(10, 20)
    assert len(fig.artists) == 1
    assert all(not legend.get_frame_on() for legend, _, _ in engine.rows)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    frame = engine.frame.get_window_extent(renderer)
    rows = [legend.get_window_extent(renderer) for legend, _, _ in engine.rows]
    assert rows[0].y1 == pytest.approx(frame.y1 - 5)
    assert rows[-1].y0 == pytest.approx(frame.y0 + 5)
    assert all(frame.x0 <= box.x0 and frame.x1 >= box.x1 for box in rows)


def test_vertical_defaults_to_one_column_but_explicit_columns_take_precedence(drawing):
    engine = _engine(drawing, orientation="vertical")
    assert len(engine.rows) == 3
    engine.remove()
    explicit = _engine(drawing, orientation="vertical", ncols=2)
    assert [len(row.get_texts()) for row, _, _ in explicit.rows] == [2, 1]


@pytest.mark.parametrize("options,orientation", [
    ({}, "vertical"), ({"ncols": 1}, "horizontal"),
])
def test_single_column_rows_align_marker_centers_and_label_starts(drawing, options, orientation):
    fig, _ = drawing
    labels = ("A", "A longer series label", "Intermediate")
    engine = _engine(drawing, labels, orientation=orientation, **options)
    engine.place(10, 20)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    text_lefts = [text.get_window_extent(renderer).x0 for text in _texts(engine)]
    assert text_lefts == pytest.approx([text_lefts[0]] * len(labels))
    marker_centers = []
    for legend, _, _ in engine.rows:
        handle = legend.legend_handles[0]
        marker_centers.append(handle.get_transform().transform(handle.get_xydata())[1, 0])
    assert marker_centers == pytest.approx([marker_centers[0]] * len(labels))


def test_explicit_multiple_columns_start_at_the_same_content_left(drawing):
    fig, _ = drawing
    labels = ("A longer first entry", "B", "Short", "D", "Last")
    engine = _engine(drawing, labels, ncols=2)
    engine.place(10, 20)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    lefts = [legend.get_texts()[0].get_window_extent(renderer).x0
             for legend, _, _ in engine.rows]
    assert lefts == pytest.approx([lefts[0]] * 3)


def test_invisible_legend_occupies_zero_space_and_creates_no_artists(drawing):
    fig, _ = drawing
    engine = _engine(drawing, width=1, height=1, visible=False, frameon=True)
    assert engine.width == engine.height == 0
    assert engine.place(3, 4) == []
    assert not fig.legends
    assert not fig.artists


def test_reflow_replaces_old_artists_and_preserves_placement(drawing):
    fig, _ = drawing
    labels = tuple(f"Backbone variant {i}" for i in range(1, 8))
    engine = _engine(drawing, labels, width=270, frameon=True)
    engine.place(10, 20)
    original = list(engine.artists)
    old_height = engine.height
    engine.reflow(120)
    assert engine.height > old_height
    assert len(fig.legends) == len(engine.rows)
    assert all(artist not in fig.legends and artist not in fig.artists for artist in original)
    assert all(artist.get_visible() for artist in engine.artists)
    fig.canvas.draw()
    assert engine.frame.get_window_extent(fig.canvas.get_renderer()).x0 == pytest.approx(10)
    engine.remove()
    engine.remove()
    assert not fig.legends
    assert not fig.artists


def test_handles_preserve_marker_identity_without_changing_data(drawing):
    fig, _ = drawing
    ax = fig.add_axes((.15, .2, .7, .6))
    point = ax.scatter([1, 2], [3, 4], c="#264653", s=25, marker="D", label="Observed")
    original_offsets = point.get_offsets().copy()
    original_sizes = point.get_sizes().copy()
    engine = _engine(drawing, labels=("Observed",), handles=[point], ncols=1)
    engine.place(10, 10)
    fig.canvas.draw()
    clone = engine.rows[0][0].legend_handles[0]
    assert clone.get_facecolors()[0] == pytest.approx(to_rgba("#264653"))
    np.testing.assert_array_equal(point.get_offsets(), original_offsets)
    np.testing.assert_array_equal(point.get_sizes(), original_sizes)
    np.testing.assert_array_equal(clone.get_paths()[0].vertices, point.get_paths()[0].vertices)


def test_row_major_label_order_retains_each_associated_marker_and_color(drawing):
    labels = tuple(f"Group {i}" for i in range(7))
    handles = _handles(labels)
    engine = _engine(drawing, labels, handles=handles, ncols=3)
    drawn = [(text.get_text(), handle)
             for legend, _, _ in engine.rows
             for text, handle in zip(legend.get_texts(), legend.legend_handles)]
    assert [label for label, _ in drawn] == list(labels)
    for (_, clone), original in zip(drawn, handles):
        assert clone.get_marker() == original.get_marker()
        assert clone.get_markersize() == original.get_markersize()
        assert clone.get_markerfacecolor() == original.get_markerfacecolor()


@pytest.mark.parametrize("options", [
    {"ncols": 0}, {"ncols": 1.5}, {"ncols": True}, {"fontsize": 0},
    {"fontsize": float("inf")}, {"columnspacing": -1}, {"borderpad": float("nan")},
    {"frameon": "yes"}, {"visible": 1},
])
def test_invalid_options_fail_before_creating_artists(drawing, options):
    fig, _ = drawing
    with pytest.raises(ValueError):
        _engine(drawing, **options)
    assert not fig.legends
    assert not fig.artists
