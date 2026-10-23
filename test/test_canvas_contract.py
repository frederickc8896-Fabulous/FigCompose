"""Publication-size acceptance checks for the public physical canvas API."""

from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import re
import struct
import xml.etree.ElementTree as ET

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
import pandas as pd
import pytest

from data_visuals import plot
from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig, get_default_config, set_default_config
from data_visuals.layout.placement import LayoutError


@pytest.fixture
def observations():
    return pd.DataFrame({
        "dataset": ["A", "A", "B", "B"] * 2,
        "model": ["Base", "Ours"] * 4,
        "epoch": [1] * 4 + [2] * 4,
        "accuracy": [0.71, 0.82, 0.73, 0.85, 0.75, 0.88, 0.76, 0.91],
        "latency": [12.0, 9.0, 12.5, 9.5, 11.8, 8.8, 12.2, 9.2],
    })


@pytest.fixture(autouse=True)
def release_test_figures():
    existing = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - existing:
        plt.close(number)


def _declarations(count=1):
    choices = [
        {"kind": "bar", "metric": "accuracy", "title": "Accuracy"},
        {"kind": "line", "x": "epoch", "metric": "accuracy", "title": "Learning"},
        {"kind": "box", "metric": "latency", "title": "Latency"},
    ]
    return [deepcopy(choices[index % len(choices)]) for index in range(count)]


def _plot(data, *, count=1, **kwargs):
    return plot(data, x="dataset", group="model", plots=_declarations(count),
                style="modern", **kwargs)


def _axes(figure):
    return [axis for axis in figure.axes if axis.get_label().startswith("data_visuals:")]


def _role_sizes(figure):
    axes = _axes(figure)
    return {
        "axis_label": {label.get_fontsize() for axis in axes for label in (axis.xaxis.label, axis.yaxis.label)},
        "tick": {label.get_fontsize() for axis in axes for label in axis.get_xticklabels() + axis.get_yticklabels()},
        "subtitle": {axis.title.get_fontsize() for axis in axes},
        "legend": {text.get_fontsize() for legend in figure.legends for text in legend.get_texts()},
        "title": {text.get_fontsize() for text in figure.texts if text.get_text() == "Results"},
    }


def _assert_inside_canvas(figure):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    boxes = [axis.get_tightbbox(renderer) for axis in figure.axes]
    boxes.extend(legend.get_window_extent(renderer) for legend in figure.legends)
    boxes.extend(text.get_window_extent(renderer) for text in figure.texts if text.get_text())
    for box in boxes:
        assert box.x0 >= figure.bbox.x0 - 1
        assert box.y0 >= figure.bbox.y0 - 1
        assert box.x1 <= figure.bbox.x1 + 1
        assert box.y1 <= figure.bbox.y1 + 1
    # Axis decorations must fit their own cells, including independently
    # measured x/y labels, rather than overlapping an adjacent panel.
    for first, second in combinations([axis.get_tightbbox(renderer) for axis in _axes(figure)], 2):
        overlap = Bbox.intersection(first, second)
        assert overlap is None or overlap.width <= 1 or overlap.height <= 1


@pytest.mark.parametrize("count,size", [(1, (90, 65)), (3, (180, 110))])
def test_single_and_mixed_panels_respect_the_complete_physical_canvas(observations, count, size):
    figure = _plot(observations, count=count, title="Results",
                   canvas={"width": size[0], "height": size[1]}).render()
    try:
        assert figure.get_size_inches() * 25.4 == pytest.approx(size)
        assert len(_axes(figure)) == count
        _assert_inside_canvas(figure)
    finally:
        plt.close(figure)


def test_font_roles_and_strokes_remain_in_points_across_canvas_sizes(observations):
    figures = [
        _plot(observations, title="Results", canvas={"width": 90, "height": 65}).render(),
        _plot(observations, count=3, title="Results", canvas={"width": 180, "height": 110}).render(),
    ]
    try:
        single, mixed = [_role_sizes(figure) for figure in figures]
        assert all(single.values()), single
        assert all(mixed.values()), mixed
        assert single == mixed
        assert {axis.spines["left"].get_linewidth() for axis in _axes(figures[0])} == {
            axis.spines["left"].get_linewidth() for axis in _axes(figures[1])}
    finally:
        for figure in figures:
            plt.close(figure)


def test_equivalent_mm_and_inch_inputs_have_identical_layout_and_fonts(observations):
    figures = [
        _plot(observations, count=3, title="Results", canvas={"width": 180, "height": 110}).render(),
        _plot(observations, count=3, title="Results",
              canvas={"width": 180 / 25.4, "height": 110 / 25.4, "unit": "in"}).render(),
    ]
    try:
        assert figures[0].get_size_inches() == pytest.approx(figures[1].get_size_inches())
        assert _role_sizes(figures[0]) == _role_sizes(figures[1])
        for first, second in zip(_axes(figures[0]), _axes(figures[1])):
            assert first.get_position().bounds == pytest.approx(second.get_position().bounds)
    finally:
        for figure in figures:
            plt.close(figure)


def test_dpi_changes_pixel_density_without_changing_physical_layout(observations, tmp_path):
    figure = _plot(observations, title="Results", canvas={"width": 90, "height": 65})
    rendered = figure.render()
    try:
        positions = [axis.get_position().bounds for axis in _axes(rendered)]
        fonts = _role_sizes(rendered)
    finally:
        plt.close(rendered)
    before = plt.get_fignums()
    with matplotlib.rc_context({"savefig.bbox": "tight", "savefig.pad_inches": 2}):
        for dpi in (300, 600):
            path = tmp_path / f"figure_{dpi}.png"
            figure.render(path, dpi=dpi)
            actual = struct.unpack(">II", path.read_bytes()[16:24])
            assert actual == pytest.approx((90 * dpi / 25.4, 65 * dpi / 25.4), abs=1)
    assert plt.get_fignums() == before
    after = figure.render()
    try:
        assert _role_sizes(after) == fonts
        for actual, expected in zip([axis.get_position().bounds for axis in _axes(after)], positions):
            assert actual == pytest.approx(expected)
    finally:
        plt.close(after)


def test_vector_exports_keep_the_requested_outer_boundary(observations, tmp_path):
    figure = _plot(observations, count=3, title="Results", canvas={"width": 180, "height": 110})
    with matplotlib.rc_context({"savefig.bbox": "tight"}):
        figure.render(tmp_path / "physical.svg")
        figure.render(tmp_path / "physical.pdf")
    expected = (180 * 72 / 25.4, 110 * 72 / 25.4)
    svg = ET.parse(tmp_path / "physical.svg").getroot()
    actual = [float(svg.attrib[key].removesuffix("pt")) for key in ("width", "height")]
    assert actual == pytest.approx(expected)
    media_box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]",
                          (tmp_path / "physical.pdf").read_bytes())
    assert media_box is not None
    assert tuple(float(number) for number in media_box.groups()) == pytest.approx(expected)


INVALID_CANVASES = [
    {}, {"height": 65}, {"width": True}, {"width": False}, {"width": 0},
    {"width": -90}, {"width": float("nan")}, {"width": float("inf")},
    {"width": "90"}, {"width": 90, "height": True},
    {"width": 90, "height": 0}, {"width": 90, "height": -1},
    {"width": 90, "height": float("nan")}, {"width": 90, "height": float("inf")},
    {"width": 90, "height": "65"}, {"width": 90, "unit": "px"},
    {"width": 90, "unit": "cm"}, {"width": 90, "heigth": 65},
    (90, 65), 90, "90mm",
]


@pytest.mark.parametrize("canvas", INVALID_CANVASES)
@pytest.mark.parametrize("entry", ["plot", "Figure", "FigureConfig"])
def test_invalid_canvas_contract_is_rejected_at_every_public_entry(observations, canvas, entry):
    before = plt.get_fignums()
    with pytest.raises((ValueError, TypeError)):
        if entry == "plot":
            _plot(observations, canvas=canvas)
        elif entry == "Figure":
            Figure(data=observations, canvas=canvas)
        else:
            FigureConfig(canvas=canvas)
    assert plt.get_fignums() == before


@pytest.mark.parametrize("legacy", [
    {"aspect": "4:3"}, {"base": "small"}, {"cell_base": "small"},
    {"aspect": "16:10"}, {"base": "large"},
])
def test_explicit_canvas_and_legacy_size_cannot_silently_compete(observations, legacy):
    with pytest.raises(ValueError, match="canvas"):
        Figure(data=observations, canvas={"width": 90}, **legacy)
    with pytest.raises(ValueError, match="canvas"):
        FigureConfig(canvas={"width": 90}, **legacy)


def test_figure_config_carries_canvas_without_mutating_the_callers_dictionary(observations):
    requested = {"width": 90, "height": 65, "unit": "mm"}
    config = FigureConfig(canvas=requested, theme="modern")
    figure = Figure(data=observations, rows=1, cols=1, config=config)
    figure[0, 0].bar(x="dataset", y="accuracy", group="model", title="Accuracy")
    rendered = figure.render()
    try:
        assert rendered.get_size_inches() * 25.4 == pytest.approx((90, 65))
        assert requested == {"width": 90, "height": 65, "unit": "mm"}
    finally:
        plt.close(rendered)


def test_canvas_from_global_configuration_controls_single_and_multiple_panels(observations):
    original = get_default_config()
    set_default_config(FigureConfig(canvas={"width": 120}, theme="modern"))
    figures = []
    try:
        figures = [_plot(observations, count=count).render() for count in (1, 3)]
        assert all(figure.get_size_inches()[0] * 25.4 == pytest.approx(120) for figure in figures)
        assert all(figure.get_size_inches()[1] > 0 for figure in figures)
    finally:
        set_default_config(original)
        for figure in figures:
            plt.close(figure)


@pytest.mark.parametrize("canvas", [None, {"width": 180}, {"width": 180, "height": None}])
def test_default_and_explicit_auto_height_keep_a_stable_publication_width(observations, canvas):
    figures = [_plot(observations, count=count, canvas=canvas).render() for count in (1, 4)]
    try:
        assert all(figure.get_size_inches()[0] * 25.4 == pytest.approx(180) for figure in figures)
        assert all(figure.get_size_inches()[1] > 0 for figure in figures)
        for figure in figures:
            _assert_inside_canvas(figure)
    finally:
        for figure in figures:
            plt.close(figure)


def test_auto_height_accounts_for_a_wrapped_shared_legend(observations):
    short = pd.concat([observations.assign(model=f"M{index}") for index in range(10)], ignore_index=True)
    long = short.copy()
    long["model"] = long["model"].map({
        f"M{index}": f"Experiment configuration {index:02d} with a descriptive training procedure and evaluation setup"
        for index in range(10)
    })
    figures = [
        _plot(data, count=2, cols=1, canvas={"width": 90}).render()
        for data in (short, long)
    ]
    try:
        assert figures[1].get_size_inches()[0] == pytest.approx(figures[0].get_size_inches()[0])
        assert figures[1].get_size_inches()[1] > figures[0].get_size_inches()[1]
        assert _role_sizes(figures[1])["legend"] == _role_sizes(figures[0])["legend"]
        for figure in figures:
            _assert_inside_canvas(figure)
    finally:
        for figure in figures:
            plt.close(figure)


def test_long_titles_secondary_axis_and_colorbar_are_measured_inside_auto_canvas(observations):
    long = observations.copy()
    long["dataset"] = long["dataset"].map({
        "A": "Dataset with a longer descriptive name A",
        "B": "Dataset with a longer descriptive name B",
    })
    figure = plot(
        long, x="dataset", group="model", style="modern", canvas={"width": 180},
        title="Measured physical canvas for mixed panels with a long descriptive paper figure title",
        plots=[
            {"kind": "bar", "metric": "accuracy", "title": "Accuracy across benchmark datasets"},
            {"kind": "line", "x": "epoch", "metric": "accuracy", "y2": "latency",
             "title": "Accuracy and latency during training"},
            {"kind": "heatmap", "x": "dataset", "y": "model", "metric": "accuracy",
             "title": "Accuracy matrix", "annotate": True},
        ],
    ).render()
    try:
        assert figure.get_size_inches()[0] * 25.4 == pytest.approx(180)
        assert len(_axes(figure)) == 3
        assert len(figure.axes) >= 5  # three panels, a secondary axis, a colorbar
        _assert_inside_canvas(figure)
    finally:
        plt.close(figure)


def test_cols_is_an_upper_bound_and_can_reduce_for_a_narrow_canvas(observations):
    figure = _plot(observations, count=3, cols=3, canvas={"width": 90}).render()
    try:
        axes = _axes(figure)
        # Three narrow side-by-side panels cannot fit publication-size labels;
        # the planner may use fewer columns instead of preserving an exact grid.
        assert len({round(axis.get_position().y1, 6) for axis in axes}) > 1
        assert len(axes) == 3
        _assert_inside_canvas(figure)
    finally:
        plt.close(figure)


def test_fixed_canvas_reports_insufficient_space_and_releases_figure(observations):
    before = plt.get_fignums()
    with pytest.raises(LayoutError) as error:
        _plot(observations, count=3, title="Results",
              canvas={"width": 30, "height": 20}).render()
    assert str(error.value).strip()
    assert plt.get_fignums() == before


def test_auto_height_cannot_conceal_an_unreadable_width(observations):
    before = plt.get_fignums()
    with pytest.raises(LayoutError):
        _plot(observations, canvas={"width": 5}).render()
    assert plt.get_fignums() == before


def test_canvas_does_not_change_statistics_or_semantic_color_assignments(observations):
    original = observations.copy(deep=True)
    figures = [
        _plot(observations, count=2, canvas={"width": 90}).render(),
        _plot(observations, count=2, canvas={"width": 180}).render(),
    ]
    try:
        pd.testing.assert_frame_equal(observations, original)
        # Compare actual plotted bar heights and line coordinates, not a copy
        # of the normalizer's internal bookkeeping.
        first_bar, second_bar = [next(axis for axis in _axes(figure) if axis.patches) for figure in figures]
        assert [patch.get_height() for patch in first_bar.patches] == pytest.approx(
            [patch.get_height() for patch in second_bar.patches])
        assert [patch.get_facecolor() for patch in first_bar.patches] == [
            patch.get_facecolor() for patch in second_bar.patches]
        lines = [[line for axis in _axes(figure) for line in axis.lines
                  if line.get_label() in {"Base", "Ours"}] for figure in figures]
        assert len(lines[0]) == len(lines[1]) == 2
        for first, second in zip(*lines):
            assert first.get_xdata() == pytest.approx(second.get_xdata())
            assert first.get_ydata() == pytest.approx(second.get_ydata())
            assert first.get_color() == second.get_color()
    finally:
        for figure in figures:
            plt.close(figure)
