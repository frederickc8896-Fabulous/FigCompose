"""Whole-figure legends reserve measured space beneath single-column panels."""

from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.layout.placement import LayoutError


_CANVAS = {"width": 3.4, "height": 4.45, "unit": "in"}
_LABELS = ("xsmall", "small", "RoBERTa")
_MARKERS = ("o", "s", "^")
_FACETS = {
    "sharex": True,
    "sharey": True,
    "xlabel": "Actual ID false rejection (%)",
    "ylabel": "Leakage difference (pp)",
}


@pytest.fixture(autouse=True)
def close_test_figures():
    existing = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - existing:
        plt.close(number)


def _figure(*, position="bottom", facets=True, canvas=None, labels=_LABELS):
    frame = pd.DataFrame([
        {"panel": panel, "backbone": label, "x": node, "y": -12 + i * 2 + j + panel}
        for panel in range(2)
        for i, label in enumerate(labels)
        for j, node in enumerate((0.875, 1.875, 4.875, 9.875))
    ])
    figure = Figure(
        data=frame, rows=2, cols=1, theme="modern", legend_position=position,
        canvas=canvas or dict(_CANVAS),
        config=FigureConfig(facets=_FACETS) if facets else FigureConfig(),
    )
    styles = {
        label: {"marker": _MARKERS[i % 3], "size": 16}
        for i, label in enumerate(labels)
    }
    for row in range(2):
        figure[row, 0].scatter(
            x="x", y="y", group="backbone", where={"panel": row},
            title=f"({chr(97 + row)}) {'Near' if row == 0 else 'Far'}-OOD",
            chart_opts={"series_styles": styles, "opacity": 1,
                        "xlim": (0, 10.5), "ylim": (-15, 1)},
        )
    return figure


def _layout(figure):
    return figure._data_visuals_layout


def _legend_boxes(figure):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    return [legend.get_window_extent(renderer) for legend in figure.legends]


def _assert_inside_canvas(figure, artists):
    renderer = figure.canvas.get_renderer()
    for artist in artists:
        box = artist.get_window_extent(renderer)
        assert box.x0 >= figure.bbox.x0 - 0.5
        assert box.y0 >= figure.bbox.y0 - 0.5
        assert box.x1 <= figure.bbox.x1 + 0.5
        assert box.y1 <= figure.bbox.y1 + 0.5


def _assert_bottom_legend_clears_axes(figure):
    legends = _legend_boxes(figure)
    assert legends
    cells = _layout(figure)["cells"]
    lowest_decoration = min(cell["decoration_bbox"][1] for cell in cells.values())
    assert max(box.y1 for box in legends) < lowest_decoration
    for first, second in combinations(legends, 2):
        overlap = Bbox.intersection(first, second)
        assert overlap is None or overlap.width < 0.5 or overlap.height < 0.5
    _assert_inside_canvas(figure, figure.legends + _layout(figure)["header_artists"])


def test_single_column_facets_put_legend_below_shared_xlabel_and_keep_series_identity():
    paper = _figure()
    assert paper.build().shared_legend["position"] == "bottom"
    figure = paper.render()
    assert figure.get_size_inches() == pytest.approx((3.4, 4.45))
    cells = _layout(figure)["cells"]
    upper, lower = cells[0, 0]["axes"], cells[1, 0]["axes"]
    assert upper.get_shared_x_axes().joined(upper, lower)
    assert upper.get_shared_y_axes().joined(upper, lower)
    assert upper.get_xlim() == lower.get_xlim()
    assert upper.get_ylim() == lower.get_ylim()
    assert not upper.get_xticklabels()
    assert lower.get_xticklabels()
    assert all(not cell["legends"] for cell in cells.values())
    assert cells[0, 0]["data_zone"]["w"] == pytest.approx(cells[1, 0]["data_zone"]["w"])
    assert cells[0, 0]["data_zone"]["h"] == pytest.approx(cells[1, 0]["data_zone"]["h"])
    _assert_bottom_legend_clears_axes(figure)
    xlabel = next(text for text in figure.texts if text.get_text() == _FACETS["xlabel"])
    xlabel_box = xlabel.get_window_extent(figure.canvas.get_renderer())
    assert max(box.y1 for box in _legend_boxes(figure)) < xlabel_box.y0
    assert xlabel_box.y1 < cells[1, 0]["decoration_bbox"][1]
    handles = [handle for legend in figure.legends for handle in legend.legend_handles]
    labels = [text.get_text() for legend in figure.legends for text in legend.get_texts()]
    assert set(labels) == set(_LABELS)
    assert all(isinstance(handle, Line2D) for handle in handles)
    by_label = dict(zip(labels, handles))
    for cell in cells.values():
        markers = {artist._data_visuals_series_key: artist for artist in cell["axes"].collections}
        for label, marker in zip(_LABELS, _MARKERS):
            assert by_label[label].get_marker() == marker
            assert to_rgba(by_label[label].get_markerfacecolor()) == pytest.approx(
                markers[label].get_facecolors()[0]
            )


def test_ordinary_panels_reserve_footer_in_automatic_height_canvas():
    paper = _figure(facets=False, canvas={"width": 3.4, "unit": "in"})
    figure = paper.render()
    assert paper.build().canvas["height_auto"] is True
    assert figure.get_size_inches()[0] == pytest.approx(3.4)
    assert _layout(figure)["footer_height"] > 0
    assert all(cell["axes"].get_xlabel() for cell in _layout(figure)["cells"].values())
    _assert_bottom_legend_clears_axes(figure)


def test_long_shared_legend_wraps_into_measured_rows_without_shrinking_text():
    labels = tuple(f"Backbone variant {i}" for i in range(1, 8))
    figure = _figure(labels=labels).render()
    assert len(figure.legends) > 1
    texts = [text for legend in figure.legends for text in legend.get_texts()]
    assert {text.get_text() for text in texts} == set(labels)
    assert all(text.get_fontsize() >= 8 for text in texts)
    assert _layout(figure)["footer_height"] > 30
    _assert_bottom_legend_clears_axes(figure)
    xlabel = next(text for text in figure.texts if text.get_text() == _FACETS["xlabel"])
    assert max(box.y1 for box in _legend_boxes(figure)) < xlabel.get_window_extent(
        figure.canvas.get_renderer()
    ).y0


def test_multiple_shared_groups_keep_footer_headings_and_legends_separate():
    data = pd.DataFrame({
        "x": [1, 2, 3, 4], "y": [-4, -3, -2, -1],
        "architecture": ["Small", "Small", "Large", "Large"],
        "training": ["Single", "Multi", "Single", "Multi"],
    })
    paper = Figure(data=data, rows=2, cols=2, theme="modern", legend_position="bottom",
                   canvas={"width": 7, "height": 4.45, "unit": "in"})
    for row in range(2):
        for col, group in enumerate(("architecture", "training")):
            paper[row, col].scatter(x="x", y="y", group=group, title=None)
    figure = paper.render()
    _assert_bottom_legend_clears_axes(figure)
    labels = {text.get_text() for legend in figure.legends for text in legend.get_texts()}
    assert labels == {"Small", "Large", "Single", "Multi"}
    headings = [text for text in figure.texts if text.get_text() in ("architecture", "training")]
    assert len(headings) == 2
    renderer = figure.canvas.get_renderer()
    occupied = _legend_boxes(figure) + [text.get_window_extent(renderer) for text in headings]
    for first, second in combinations(occupied, 2):
        overlap = Bbox.intersection(first, second)
        assert overlap is None or overlap.width < 0.5 or overlap.height < 0.5
    lowest_decoration = min(cell["decoration_bbox"][1] for cell in _layout(figure)["cells"].values())
    assert all(text.get_window_extent(renderer).y1 < lowest_decoration for text in headings)


def test_default_shared_legend_still_occupies_the_header():
    paper = _figure(position=None)
    assert paper.build().shared_legend["position"] == "top"
    figure = paper.render()
    assert _layout(figure)["footer_height"] == 0
    highest_decoration = max(
        cell["decoration_bbox"][1] + cell["decoration_bbox"][3]
        for cell in _layout(figure)["cells"].values()
    )
    assert min(box.y0 for box in _legend_boxes(figure)) > highest_decoration
    _assert_inside_canvas(figure, figure.legends)


@pytest.mark.parametrize("facets", [True, False])
def test_small_canvas_rejects_footer_overflow_without_leaking_figures(facets):
    before = set(plt.get_fignums())
    paper = _figure(facets=facets, canvas={"width": 3.4, "height": 0.95, "unit": "in"})
    with pytest.raises(LayoutError) as failure:
        paper.render()
    assert failure.value.required_width is not None
    assert failure.value.required_height is not None
    assert set(plt.get_fignums()) == before
