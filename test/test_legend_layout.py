"""Public legend overrides participate in real physical-canvas layout."""
from itertools import combinations
import struct

import matplotlib.pyplot as plt
from matplotlib.legend import Legend
from matplotlib.patches import FancyBboxPatch
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
import pytest

from data_visuals.core import Figure, FigureConfig
from data_visuals.layout.placement import LayoutError


_LABELS = ("A", "B", "C")
_STYLES = {"A": {"marker": "o"}, "B": {"marker": "s"}, "C": {"marker": "^"}}
_FACETS = {"sharex": True, "sharey": True,
           "xlabel": "Actual ID false rejection (%)", "ylabel": "Leakage difference (pp)"}


@pytest.fixture(autouse=True)
def close_test_figures():
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


def _paper(legend, *, local=None, canvas=None, facets=True, title="Training differences", rows=2):
    data = pd.DataFrame([
        {"panel": panel, "model": model, "x": x, "y": -8 + i * 2 + x / 3 + panel}
        for panel in range(rows) for i, model in enumerate(_LABELS) for x in (1, 2, 5, 10)
    ])
    paper = Figure(
        data=data, rows=rows, cols=1, title=title, theme="modern", legend=legend,
        canvas=canvas or {"width": 115, "height": 130},
        config=FigureConfig(facets=_FACETS if facets else {}),
    )
    for row in range(rows):
        options = {"series_styles": _STYLES, "xlim": (0, 11), "ylim": (-10, 1)}
        if local and row in local:
            options["legend"] = local[row]
        paper[row, 0].scatter(x="x", y="y", group="model", where={"panel": row},
                              title=f"({chr(97 + row)}) Panel {row + 1}", chart_opts=options)
    return paper


def _legends(figure):
    legends = list(figure.legends)
    legends.extend(ax.get_legend() for ax in figure.axes if ax.get_legend() is not None)
    # Both Figure-level artists and native Axes legends are accepted.
    for cell in figure._data_visuals_layout["cells"].values():
        legends.extend(cell["legends"])
    return list({id(legend): legend for legend in legends if isinstance(legend, Legend)}.values())


def _frames(figure):
    return [artist for artist in figure.artists
            if isinstance(artist, FancyBboxPatch) and artist.get_visible()]


def _boxes(figure):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    return [legend.get_window_extent(renderer) for legend in _legends(figure)]


def _no_overlap(first, second):
    overlap = Bbox.intersection(first, second)
    return overlap is None or overlap.width < 0.5 or overlap.height < 0.5


def _assert_inside(outer, inner, tolerance=0.6):
    assert inner.x0 >= outer.x0 - tolerance
    assert inner.y0 >= outer.y0 - tolerance
    assert inner.x1 <= outer.x1 + tolerance
    assert inner.y1 <= outer.y1 + tolerance


@pytest.mark.parametrize("position", ["top", "bottom", "left", "right"])
def test_shared_four_sides_clear_panels_shared_axis_labels_and_canvas(position):
    figure = _paper({"scope": "shared", "position": position, "ncols": 1}).render()
    assert tuple(figure.get_size_inches()) == pytest.approx((115 / 25.4, 130 / 25.4))
    renderer = figure.canvas.get_renderer()
    boxes = _boxes(figure)
    assert boxes
    protected = [ax.get_tightbbox(renderer) for ax in figure.axes]
    protected += [text.get_window_extent(renderer) for text in figure.texts
                  if text.get_text() in (*_FACETS.values(), "Training differences")]
    for box in boxes:
        _assert_inside(figure.bbox, box)
        assert all(_no_overlap(box, decoration) for decoration in protected)
    assert all(_no_overlap(first, second) for first, second in combinations(boxes, 2))
    axes_box = Bbox.union([ax.get_window_extent(renderer) for ax in figure.axes])
    if position == "top":
        assert min(box.y0 for box in boxes) > axes_box.y1
    elif position == "bottom":
        assert max(box.y1 for box in boxes) < axes_box.y0
    elif position == "left":
        assert max(box.x1 for box in boxes) < axes_box.x0
    else:
        assert min(box.x0 for box in boxes) > axes_box.x1
    assert figure.axes[0].get_shared_x_axes().joined(*figure.axes)
    assert figure.axes[0].get_shared_y_axes().joined(*figure.axes)


@pytest.mark.parametrize("position", ["top", "bottom", "left", "right"])
def test_hidden_shared_legend_reclaims_its_physical_strip(position):
    shown = _paper({"scope": "shared", "position": position, "ncols": 1}).render()
    hidden = _paper({"scope": "shared", "position": position, "visible": False}).render()
    assert not _legends(hidden)
    shown_zone = shown._data_visuals_layout["cells"][0, 0]["data_zone"]
    hidden_zone = hidden._data_visuals_layout["cells"][0, 0]["data_zone"]
    dimension = "h" if position in ("top", "bottom") else "w"
    assert hidden_zone[dimension] > shown_zone[dimension] + 5


def test_font_columns_and_physical_spacing_change_real_legend_geometry():
    figure = _paper({"scope": "shared", "position": "bottom", "fontsize": 10,
                     "ncols": 2, "frameon": True, "columnspacing": 16,
                     "labelspacing": 7, "handlelength": 20,
                     "handletextpad": 6, "borderpad": 5}).render()
    legends = _legends(figure)
    renderer = figure.canvas.get_renderer()
    assert len(_frames(figure)) == 1
    texts = [text for legend in legends for text in legend.get_texts()]
    handles = [handle for legend in legends for handle in legend.legend_handles]
    assert all(text.get_fontsize() == 10 for text in texts)
    text_boxes = [text.get_window_extent(renderer) for text in texts]
    row_centers = sorted({round((box.y0 + box.y1) / 2, 3) for box in text_boxes})
    assert len(row_centers) == 2
    assert max(sum(abs((box.y0 + box.y1) / 2 - row) < 0.01 for box in text_boxes)
               for row in row_centers) == 2
    for handle, text_box in zip(handles, text_boxes):
        line_xy = handle.get_transform().transform(handle.get_path().vertices)
        assert np.ptp(line_xy[:, 0]) == pytest.approx(20, abs=0.5)
        assert text_box.x0 - line_xy[:, 0].max() == pytest.approx(6, abs=0.5)
    compact = _paper({"scope": "shared", "position": "bottom", "fontsize": 10,
                      "ncols": 2, "frameon": False, "columnspacing": 2,
                      "labelspacing": 1, "handlelength": 20,
                      "handletextpad": 6, "borderpad": 0}).render()
    compact_box = Bbox.union(_boxes(compact))
    large_box = _frames(figure)[0].get_window_extent(renderer)
    assert large_box.width > compact_box.width + 15
    assert large_box.height > compact_box.height + 10
    assert not _frames(compact)


def test_requested_legend_gap_is_a_physical_clearance():
    near = _paper({"scope": "shared", "position": "bottom", "gap": 2}).render()
    far = _paper({"scope": "shared", "position": "bottom", "gap": 14}).render()
    def clearance(figure):
        renderer = figure.canvas.get_renderer()
        label = next(text for text in figure.texts if text.get_text() == _FACETS["xlabel"])
        return label.get_window_extent(renderer).y0 - max(box.y1 for box in _boxes(figure))
    assert clearance(far) >= clearance(near) + 10


@pytest.mark.parametrize("position", ["upper left", "upper right", "lower left", "lower right"])
def test_local_corner_stays_inside_axes_without_shrinking_data(position):
    figure = _paper({"scope": "local", "position": position, "fontsize": 8}, rows=1).render()
    hidden = _paper({"scope": "local", "position": position, "visible": False}, rows=1).render()
    assert len(_legends(figure)) == 1
    ax = figure.axes[0]
    axes_box = ax.get_window_extent(figure.canvas.get_renderer())
    box = _boxes(figure)[0]
    _assert_inside(axes_box, box)
    assert ax.get_position().bounds == pytest.approx(hidden.axes[0].get_position().bounds)
    if "left" in position:
        assert (box.x0 + box.x1) / 2 < (axes_box.x0 + axes_box.x1) / 2
    else:
        assert (box.x0 + box.x1) / 2 > (axes_box.x0 + axes_box.x1) / 2
    if "upper" in position:
        assert (box.y0 + box.y1) / 2 > (axes_box.y0 + axes_box.y1) / 2
    else:
        assert (box.y0 + box.y1) / 2 < (axes_box.y0 + axes_box.y1) / 2


def test_subplot_override_inherits_fields_and_defaults_to_local_scope():
    figure = _paper(
        {"scope": "shared", "position": "top", "fontsize": 9,
         "frameon": True, "labels": {"A": "Reference"}},
        local={1: {"position": "lower left", "fontsize": 8}},
    ).render()
    renderer = figure.canvas.get_renderer()
    lower = figure._data_visuals_layout["cells"][1, 0]
    local_legends = [artist for artist in lower["legends"] if isinstance(artist, Legend)]
    assert len(local_legends) == 1
    legend = local_legends[0]
    assert all(text.get_fontsize() == 8 for text in legend.get_texts())
    assert len(_frames(figure)) == 2
    assert [text.get_text() for text in legend.get_texts()] == ["Reference", "B", "C"]
    _assert_inside(lower["axes"].get_window_extent(renderer), legend.get_window_extent(renderer))
    assert any(text.get_fontsize() == 9 for other in _legends(figure) if other is not legend
               for text in other.get_texts())


@pytest.mark.parametrize("position", ["top", "bottom", "left", "right"])
def test_local_external_sides_clear_ticks_and_axis_titles(position):
    figure = _paper({"scope": "local", "position": position, "ncols": 1},
                    rows=1, facets=False).render()
    renderer = figure.canvas.get_renderer()
    ax = figure.axes[0]
    protected = [ax.get_window_extent(renderer), ax.title.get_window_extent(renderer),
                 ax.xaxis.label.get_window_extent(renderer), ax.yaxis.label.get_window_extent(renderer)]
    protected.extend(text.get_window_extent(renderer)
                     for text in ax.get_xticklabels() + ax.get_yticklabels() if text.get_visible())
    for box in _boxes(figure):
        _assert_inside(figure.bbox, box)
        assert all(_no_overlap(box, item) for item in protected)


def test_order_and_display_labels_preserve_original_series_colors_and_markers():
    figure = _paper({"scope": "shared", "position": "bottom", "ncols": 3,
                     "order": ["C", "A", "B"],
                     "labels": {"A": "Reference", "C": "Ours"}}).render()
    legend = _legends(figure)[0]
    assert [text.get_text() for text in legend.get_texts()] == ["Ours", "Reference", "B"]
    assert [handle.get_marker() for handle in legend.legend_handles] == ["^", "o", "s"]
    markers = {artist._data_visuals_series_key: artist for artist in figure.axes[0].collections
               if hasattr(artist, "_data_visuals_series_key")}
    from matplotlib.colors import to_rgba
    for raw, handle in zip(("C", "A", "B"), legend.legend_handles):
        assert to_rgba(handle.get_markerfacecolor(), alpha=handle.get_alpha()) == pytest.approx(
            markers[raw].get_facecolors()[0])


@pytest.mark.parametrize("position,anchor,dimension", [
    ("top", [0.5, 0.98], "y1"), ("bottom", [0.5, 0.02], "y0"),
    ("left", [0.02, 0.5], "x0"), ("right", [0.98, 0.5], "x1"),
])
def test_explicit_shared_anchor_uses_figure_fraction_and_reserves_space(position, anchor, dimension):
    figure = _paper({"scope": "shared", "position": position, "anchor": anchor,
                     "frameon": True, "ncols": 1}, title=None).render()
    box = _frames(figure)[0].get_window_extent(figure.canvas.get_renderer())
    expected = anchor[1] * figure.bbox.height if dimension.startswith("y") else anchor[0] * figure.bbox.width
    assert getattr(box, dimension) == pytest.approx(expected, abs=1)
    renderer = figure.canvas.get_renderer()
    assert all(_no_overlap(box, ax.get_tightbbox(renderer)) for ax in figure.axes)


def test_explicit_local_anchor_uses_axes_fraction():
    figure = _paper({"scope": "local", "position": "lower left", "anchor": [0.1, 0.2],
                     "frameon": True}, rows=1).render()
    ax = figure.axes[0]
    box = _frames(figure)[0].get_window_extent(figure.canvas.get_renderer())
    expected = ax.transAxes.transform((0.1, 0.2))
    assert (box.x0, box.y0) == pytest.approx(expected, abs=1)
    _assert_inside(ax.get_window_extent(figure.canvas.get_renderer()), box)


def test_automatic_height_solves_bottom_legend_and_fixed_canvas_rejects_overflow():
    paper = _paper({"scope": "shared", "position": "bottom", "fontsize": 11, "ncols": 1},
                   canvas={"width": 90})
    figure = paper.render()
    assert figure.get_size_inches()[0] == pytest.approx(90 / 25.4)
    renderer = figure.canvas.get_renderer()
    assert all(_no_overlap(box, ax.get_tightbbox(renderer))
               for box in _boxes(figure) for ax in figure.axes)
    before = set(plt.get_fignums())
    with pytest.raises(LayoutError):
        _paper({"scope": "shared", "position": "bottom", "fontsize": 16, "ncols": 1},
               canvas={"width": 90, "height": 35}).render()
    assert set(plt.get_fignums()) == before


def test_legend_physical_size_and_export_canvas_do_not_depend_on_dpi(tmp_path):
    options = {"scope": "shared", "position": "right", "fontsize": 9,
               "frameon": True, "ncols": 1, "gap": 6}
    paper = _paper(options, canvas={"width": 4, "height": 5, "unit": "in"})
    initial = paper.render()
    initial_boxes = np.array([box.bounds for box in _boxes(initial)])
    initial_axes = np.array([ax.get_position().bounds for ax in initial.axes])
    for dpi in (100, 300):
        output = tmp_path / f"legend_{dpi}.png"
        paper.render(str(output), dpi=dpi)
        assert struct.unpack(">II", output.read_bytes()[16:24]) == (4 * dpi, 5 * dpi)
    repeated = paper.render()
    np.testing.assert_allclose([box.bounds for box in _boxes(repeated)], initial_boxes)
    np.testing.assert_allclose([ax.get_position().bounds for ax in repeated.axes], initial_axes)


def test_figure_config_legend_is_inherited_and_constructor_can_override_one_field():
    data = pd.DataFrame({"x": [1, 2, 3], "y": [3, 2, 1], "model": list(_LABELS)})
    paper = Figure(data=data, rows=1, cols=1, canvas={"width": 110, "height": 80},
                   config=FigureConfig(legend={"scope": "shared", "position": "bottom",
                                               "fontsize": 10, "frameon": True}),
                   legend={"ncols": 3})
    paper[0, 0].scatter(x="x", y="y", group="model")
    figure = paper.render()
    legend = _legends(figure)[0]
    assert len(_frames(figure)) == 1
    assert all(text.get_fontsize() == 10 for text in legend.get_texts())
    assert legend.get_window_extent(figure.canvas.get_renderer()).y1 < figure.axes[0].bbox.y0
