"""Reusable marker roles, data-coordinate transitions, and optional point IDs."""

from itertools import combinations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
from matplotlib.markers import MarkerStyle
from matplotlib.transforms import Bbox
import numpy as np
import pytest

from data_visuals.renderer.mpl.annotations import place_point_labels
from data_visuals.renderer.mpl.charts.scatter import _draw_scatter, scatter_legend_handle
from data_visuals.renderer.mpl.config import MplConfig


def _subplot(rows, **options):
    return {"data": {"x": "cost", "y": "loss", "group": "role"},
            "font_sizes": {"axis_label": 8, "tick": 8}, "computed_data": rows,
            "options": options}


@pytest.fixture
def drawing():
    fig = plt.figure(figsize=(3, 2), dpi=72)
    ax = fig.add_axes((.15, .2, .8, .75))
    yield fig, ax, MplConfig("modern", physical=True)
    plt.close(fig)


def test_marker_roles_legend_and_transition_preserve_data_coordinates(drawing):
    fig, ax, cfg = drawing
    styles = {
        "baseline": {"marker": "*", "size": 100, "color": "blue", "edgecolor": "white", "linewidth": .5, "label": "Baseline"},
        "variants": {"marker": "o", "size": 16, "color": "orange"},
        "mean": {"marker": "D", "size": 36, "color": "orange", "facecolor": "none", "edgecolor": "orange", "linewidth": 1.1, "zorder": 5},
    }
    rows = [{"cost": 5, "loss": 30, "role": "baseline"},
            {"cost": 1, "loss": 70, "role": "variants"},
            {"cost": 2, "loss": 60, "role": "variants"},
            {"cost": 1.5, "loss": 65, "role": "mean"}]
    handles = _draw_scatter(ax, _subplot(rows, series_styles=styles, opacity=1,
        xlim=[0, 6.5], ylim=[0, 100], xticks=[0, 2, 4, 6], yticks=[0, 50, 100],
        guides=[{"axis": "x", "value": 5, "color": "gray", "linewidth": .75}],
        arrows=[{"start": [5, 30], "end": [1.5, 65], "color": "orange"}]), cfg, {})
    by_key = {handle._data_visuals_series_key: handle for handle in handles}
    assert [handle.get_label() for handle in handles] == ["Baseline", "mean", "variants"]
    for key, style in styles.items():
        artist = by_key[key]
        expected = MarkerStyle(style["marker"])
        np.testing.assert_array_equal(artist.get_paths()[0].vertices,
            expected.get_path().transformed(expected.get_transform()).vertices)
        np.testing.assert_allclose(artist.get_sizes(), style["size"])
        expected_xy = [(row["cost"], row["loss"]) for row in rows if row["role"] == key]
        np.testing.assert_allclose(artist.get_offsets(), expected_xy)
        legend = scatter_legend_handle(key, "red", style, cfg)
        assert legend.get_marker() == style["marker"]
        assert legend.get_markersize() ** 2 == pytest.approx(style["size"])
        assert legend.get_markerfacecolor() == style.get("facecolor", style["color"])
    assert by_key["mean"].get_facecolors().size == 0
    assert by_key["baseline"].get_facecolors()[0] == pytest.approx(to_rgba("blue"))
    assert ax.get_xlim() == (0, 6.5)
    assert ax.get_ylim() == (0, 100)
    assert ax.get_xticks().tolist() == [0, 2, 4, 6]
    np.testing.assert_allclose(ax.lines[0].get_xdata(), [5, 5])
    transition, = ax._data_visuals_scatter_arrows
    assert transition.xy == (1.5, 65)
    assert transition.xyann == (5, 30)
    fig.canvas.draw()
    assert place_point_labels(ax, cfg) == {"texts": [], "boxes": []}


@pytest.mark.parametrize("dpi", [72, 144])
def test_crowded_labels_follow_final_layout_without_moving_markers(drawing, dpi):
    fig, ax, cfg = drawing
    fig.set_dpi(dpi)
    rows = [{"cost": 1 + index / 20, "loss": 60 + index / 4,
             "role": "variants", "identifier": index + 1} for index in range(8)]
    rows.append({"cost": 5, "loss": 30, "role": "baseline", "identifier": None})
    handles = _draw_scatter(ax, _subplot(rows,
        point_labels={"column": "identifier", "fontsize": 8}, xlim=[0, 6.5], ylim=[0, 100],
        series_styles={"variants": {"size": 16}, "baseline": {"marker": "*", "size": 100}},
        arrows=[{"start": [5, 30], "end": [1.2, 61]}]), cfg, {})
    expected_offsets = [artist.get_offsets().copy() for artist in handles]
    # The renderer, rather than the chart builder, chooses the final axes box.
    ax.set_position((.12, .18, .84, .78))
    fig.canvas.draw()
    result = place_point_labels(ax, cfg)
    fig.canvas.draw()
    assert {text.get_text() for text in result["texts"]} == set("12345678")
    assert len(result["boxes"]) == 8
    renderer = fig.canvas.get_renderer()
    patches = [text.get_bbox_patch().get_window_extent(renderer) for text in result["texts"]]
    for box in patches:
        assert ax.bbox.contains(box.x0, box.y0)
        assert ax.bbox.contains(box.x1, box.y1)
    for first, second in combinations(patches, 2):
        assert Bbox.intersection(first, second) is None
    for expected, artist in zip(expected_offsets, handles):
        np.testing.assert_array_equal(artist.get_offsets(), expected)
    for text in result["texts"]:
        index = int(text.get_text()) - 1
        assert text.xy == (rows[index]["cost"], rows[index]["loss"])
        assert text.get_fontsize() == 8
    old_texts = result["texts"]
    repeated = place_point_labels(ax, cfg)
    assert len(repeated["texts"]) == 8
    assert all(text not in ax.texts for text in old_texts)
    assert len(ax.texts) == 9  # Eight IDs plus one transition arrow.


@pytest.mark.parametrize("options,match", [
    ({"series_styles": []}, "series_styles"),
    ({"series_styles": {"a": {"size": -2}}}, "size"),
    ({"series_styles": {"a": {"size": True}}}, "size"),
    ({"series_styles": {"a": {"linewidth": float("inf")}}}, "linewidth"),
    ({"series_styles": {"a": {"facecolor": "not-a-color"}}}, "facecolor"),
    ({"series_styles": {"a": {"marker": "not-a-marker"}}}, "marker"),
    ({"series_styles": {"a": {"area": 12}}}, "Unknown"),
    ({"xlim": [6, 0]}, "xlim"),
    ({"ylim": [0, float("inf")]}, "ylim"),
    ({"xticks": "012"}, "xticks"),
    ({"guides": None}, "guides"),
    ({"arrows": {}}, "arrows"),
    ({"guides": [{"axis": "z", "value": 5}]}, "guide"),
    ({"arrows": [{"start": [0, 0]}]}, "arrow"),
    ({"arrows": [{"start": [False, 0], "end": [1, 1]}]}, "start"),
    ({"point_labels": {"column": "missing"}}, "point_labels"),
    ({"point_labels": {"column": "cost", "fontsize": 0}}, "fontsize"),
])
def test_invalid_semantic_options_fail_early(drawing, options, match):
    _, ax, cfg = drawing
    with pytest.raises(ValueError, match=match):
        _draw_scatter(ax, _subplot([{"cost": 1, "loss": 3, "role": "a"}], **options), cfg, {})
