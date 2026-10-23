"""Acceptance checks for measured, opt-in shared small-multiple layouts."""

from __future__ import annotations

from copy import deepcopy
from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.layout.placement import LayoutError


_FACETS = {
    "row_labels": ["Single-phrase", "Multi-phrase"],
    "col_labels": ["xsmall", "small", "RoBERTa"],
    "xlabel": "Actual ID false rejection (%)",
    "ylabel": "Near-OOD leakage (%)",
    "note": "Reference ID budget: 5% (vertical dashed line)",
    "sharex": True,
    "sharey": True,
}
_STYLES = {
    "reference": {"marker": "*", "size": 81, "label": "Reference description"},
    "rewrite": {"marker": "o", "size": 16, "label": "Individual rewrites"},
    "mean": {"marker": "D", "size": 36, "facecolor": "none", "label": "Mean over rewrites"},
}


@pytest.fixture(autouse=True)
def release_figures():
    existing = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - existing:
        plt.close(number)


def _observations():
    # Ranges differ in both directions and span several orders of magnitude,
    # making accidental first-panel limits and unequal gutters observable.
    return pd.DataFrame([
        {"row": row, "col": col, "kind": kind,
         "x": row * 10 + col * 3 + index,
         "y": row * 100 + col * 1000 + value}
        for row in range(2) for col in range(3)
        for index, (kind, value) in enumerate((("reference", 2), ("rewrite", 5), ("mean", 12)))
    ])


def _grid(*, facets=_FACETS, options=None, missing=None, canvas=None):
    figure = Figure(
        data=_observations(), rows=2, cols=3, theme="modern",
        canvas=canvas or {"width": 7, "height": 4.5, "unit": "in"},
        config=FigureConfig() if facets is None else FigureConfig(facets=deepcopy(facets)),
    )
    for row in range(2):
        for col in range(3):
            if (row, col) == missing:
                continue
            extra = options(row, col) if options else {}
            figure[row, col].scatter(
                x="x", y="y", group="kind", where={"row": row, "col": col},
                title=f"({chr(97 + row * 3 + col)}) AUROC: 0.937 → 0.931",
                chart_opts={"series_styles": deepcopy(_STYLES), **extra},
            )
    return figure


def _cells(figure):
    return figure._data_visuals_layout["cells"]


def _assert_inside_canvas(figure, artists):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    for artist in artists:
        assert artist.get_visible()
        box = artist.get_window_extent(renderer)
        assert box.width > 0 and box.height > 0
        assert box.x0 >= figure.bbox.x0 - 1
        assert box.y0 >= figure.bbox.y0 - 1
        assert box.x1 <= figure.bbox.x1 + 1
        assert box.y1 <= figure.bbox.y1 + 1


def test_shared_grid_equalizes_actual_data_regions_and_only_shows_outer_tick_labels():
    figure = _grid(options=lambda row, col: {"xlim": (0, 20), "ylim": (0, 2200)}).render()
    cells = _cells(figure)
    assert set(cells) == {(row, col) for row in range(2) for col in range(3)}
    widths = [cell["data_zone"]["w"] for cell in cells.values()]
    heights = [cell["data_zone"]["h"] for cell in cells.values()]
    assert widths == pytest.approx([widths[0]] * 6, abs=1e-7)
    assert heights == pytest.approx([heights[0]] * 6, abs=1e-7)
    assert min(widths) >= 45 and min(heights) >= 40
    first = cells[0, 0]["axes"]
    renderer = figure.canvas.get_renderer()
    for (row, col), cell in cells.items():
        ax, zone = cell["axes"], cell["data_zone"]
        actual = ax.get_window_extent(renderer)
        assert actual.width == pytest.approx(zone["w"], abs=1e-7)
        assert actual.height == pytest.approx(zone["h"], abs=1e-7)
        assert zone["x"] == pytest.approx(cells[0, col]["data_zone"]["x"])
        assert zone["y"] == pytest.approx(cells[row, 0]["data_zone"]["y"])
        assert bool(ax.get_xticklabels()) == (row == 1)
        assert bool(ax.get_yticklabels()) == (col == 0)
        assert ax.get_xlabel() == ax.get_ylabel() == ""
        assert ax.get_xlim() == pytest.approx((0, 20))
        assert ax.get_ylim() == pytest.approx((0, 2200))
        assert first.get_shared_x_axes().joined(first, ax)
        assert first.get_shared_y_axes().joined(first, ax)
        assert all(text.get_fontsize() >= 8 for text in ax.get_xticklabels() + ax.get_yticklabels())
    boxes = [Bbox.from_bounds(*cell["decoration_bbox"]) for cell in cells.values()]
    for left, right in combinations(boxes, 2):
        overlap = Bbox.intersection(left, right)
        assert overlap is None or overlap.width <= 1 or overlap.height <= 1


def test_automatic_shared_limits_cover_the_union_of_every_filtered_panel():
    independent = _grid(facets={**_FACETS, "sharex": False, "sharey": False}).render()
    expected = {}
    for direction in ("x", "y"):
        limits = [getattr(cell["axes"], f"get_{direction}lim")() for cell in _cells(independent).values()]
        assert len(set(limits)) == 6
        expected[direction] = (min(low for low, _ in limits), max(high for _, high in limits))
    plt.close(independent)
    shared = _grid().render()
    for cell in _cells(shared).values():
        assert cell["axes"].get_xlim() == pytest.approx(expected["x"])
        assert cell["axes"].get_ylim() == pytest.approx(expected["y"])
    first = _cells(shared)[0, 0]["axes"]
    first.set_xlim(-10, 30)
    assert all(cell["axes"].get_xlim() == pytest.approx((-10, 30)) for cell in _cells(shared).values())


def test_facet_headers_are_visible_measured_and_inside_the_export_frame():
    figure = _grid().render()
    header_artists = figure._data_visuals_layout["header_artists"]
    _assert_inside_canvas(figure, header_artists)
    texts = {artist.get_text(): artist for artist in header_artists if hasattr(artist, "get_text")}
    expected = set(_FACETS["row_labels"] + _FACETS["col_labels"])
    expected.update(_FACETS[field] for field in ("xlabel", "ylabel", "note"))
    assert set(texts) == expected
    assert all(artist.get_fontsize() >= 8 for artist in texts.values())
    assert all(artist.get_fontfamily() == ["Times New Roman"] for artist in texts.values())
    renderer = figure.canvas.get_renderer()
    for artist in texts.values():
        label_box = artist.get_window_extent(renderer)
        for cell in _cells(figure).values():
            intersection = Bbox.intersection(label_box, Bbox.from_bounds(*cell["decoration_bbox"]))
            assert intersection is None or intersection.width <= 1 or intersection.height <= 1


def test_shared_scatter_legend_preserves_semantic_order_markers_sizes_and_hollow_fill():
    figure = _grid().render()
    assert len(figure.legends) == 1
    legend = figure.legends[0]
    assert [text.get_text() for text in legend.get_texts()] == [style["label"] for style in _STYLES.values()]
    handles = legend.legend_handles
    assert all(isinstance(handle, Line2D) for handle in handles)
    assert [handle.get_marker() for handle in handles] == ["*", "o", "D"]
    assert [handle.get_markersize() for handle in handles] == pytest.approx([9, 4, 6])
    assert handles[-1].get_markerfacecolor() == "none"
    assert [handle.get_alpha() for handle in handles] == pytest.approx([0.7, 0.7, 0.7])
    assert all(not cell["legends"] for cell in _cells(figure).values())


@pytest.mark.parametrize("direction", ["x", "y"])
def test_shared_ticks_outside_explicit_limits_do_not_expand_the_requested_range(direction):
    figure = _grid(options=lambda row, col: {f"{direction}lim": (0, 5), f"{direction}ticks": [0, 6]}).render()
    for cell in _cells(figure).values():
        ax = cell["axes"]
        assert getattr(ax, f"get_{direction}lim")() == pytest.approx((0, 5))
        assert getattr(ax, f"get_{direction}ticks")().tolist() == [0, 6]


def test_a_default_circle_cannot_share_the_same_legend_entry_as_an_explicit_star():
    figure = _grid(options=lambda row, col: {
        "series_styles": {} if (row, col) == (1, 2) else {"reference": {"marker": "*"}},
    })
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match="Shared legend.*inconsistent"):
        figure.render()
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("direction", ["x", "y"])
def test_conflicting_explicit_shared_limits_raise_without_leaking_a_figure(direction):
    figure = _grid(options=lambda row, col: {f"{direction}lim": (0, 30 if (row, col) == (1, 2) else 20)})
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match=f"identical explicit {direction}lim"):
        figure.render()
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("field", ["row_labels", "col_labels"])
def test_incorrect_header_count_raises_without_leaking_a_figure(field):
    figure = _grid(facets={**_FACETS, field: ["Only one label"]})
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match=field):
        figure.render()
    assert set(plt.get_fignums()) == before


def test_long_middle_column_header_cannot_collide_with_neighbours_inside_the_canvas():
    long_label = "W" * 36
    preview = _grid().render()
    header = next(text for text in preview.texts if text.get_text() == "small")
    header.set_text(long_label)
    preview.canvas.draw()
    renderer = preview.canvas.get_renderer()
    box = header.get_window_extent(renderer)
    assert box.x0 >= 0 and box.x1 <= preview.bbox.width
    neighbours = [text for text in preview.texts if text.get_text() in ("xsmall", "RoBERTa")]
    assert any(Bbox.intersection(box, text.get_window_extent(renderer)) is not None for text in neighbours)
    plt.close(preview)

    figure = _grid(facets={**_FACETS, "col_labels": ["xsmall", long_label, "RoBERTa"]})
    before = set(plt.get_fignums())
    with pytest.raises(LayoutError) as failure:
        figure.render()
    assert failure.value.axis == "width"
    assert failure.value.required_width > 7 * 72
    assert set(plt.get_fignums()) == before


def test_long_rotated_row_header_requires_more_height_and_auto_canvas_preserves_its_font():
    long_label = "W" * 25
    facets = {**_FACETS, "row_labels": [long_label, "Multi-phrase"]}
    fixed = _grid(facets=facets)
    before = set(plt.get_fignums())
    with pytest.raises(LayoutError) as failure:
        fixed.render()
    assert failure.value.axis == "height"
    assert failure.value.required_height > 4.5 * 72
    assert set(plt.get_fignums()) == before

    automatic = _grid(facets=facets, canvas={"width": 7, "height": None, "unit": "in"}).render()
    assert automatic.get_size_inches()[0] == pytest.approx(7)
    assert automatic.get_size_inches()[1] > 4.5
    header = next(text for text in automatic.texts if text.get_text() == long_label)
    assert header.get_fontsize() == pytest.approx(9)
    bbox = header.get_window_extent(automatic.canvas.get_renderer())
    assert bbox.height <= _cells(automatic)[0, 0]["data_zone"]["h"]
    _assert_inside_canvas(automatic, [header])


def test_incomplete_facet_grid_raises_a_clear_error_and_closes_its_figure():
    figure = _grid(missing=(1, 2))
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match="complete rectangular grid"):
        figure.render()
    assert set(plt.get_fignums()) == before


def test_spanning_grid_is_rejected_without_leaking_a_figure():
    figure = Figure(data=_observations(), layout=[[2], [1, 1]],
                    config=FigureConfig(facets={"sharex": True}),
                    canvas={"width": 7, "height": 4.5, "unit": "in"})
    for row, col in ((0, 0), (1, 0), (1, 1)):
        figure[row, col].scatter(x="x", y="y")
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match="spanning panels"):
        figure.render()
    assert set(plt.get_fignums()) == before


@pytest.mark.parametrize("canvas", [
    {"width": 1.4, "height": 4.5, "unit": "in"},
    {"width": 7, "height": 0.9, "unit": "in"},
])
def test_too_small_facet_canvas_fails_with_dimensions_and_closes_the_figure(canvas):
    figure = _grid(canvas=canvas)
    before = set(plt.get_fignums())
    with pytest.raises(LayoutError) as failure:
        figure.render()
    assert failure.value.required_width is not None
    assert failure.value.required_height is not None
    assert set(plt.get_fignums()) == before


def test_empty_facets_preserves_ordinary_subplot_layout_and_tick_labels():
    original = _grid(facets=None)
    baseline = original.render()
    explicit = _grid(facets={}).render()
    assert original.build().facets == {}
    assert not baseline.texts
    assert not explicit.texts
    for key, first in _cells(baseline).items():
        second = _cells(explicit)[key]
        assert first["data_zone"] == pytest.approx(second["data_zone"])
        assert first["axes"].get_xticklabels() and first["axes"].get_yticklabels()
        assert second["axes"].get_xticklabels() and second["axes"].get_yticklabels()
