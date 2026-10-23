"""Actual layout/colour contracts shared by different charts and figure sizes."""
from copy import deepcopy

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.layout.manager import build_layout
from data_visuals.layout.placement import LayoutError


def _data(n_models=10):
    return pd.DataFrame([{"category": f"Task {i}", "model": f"Model {j:02}",
                          "value": i + j / 10, "value2": i * 2 + j / 10}
                         for i in range(1, 5) for j in range(n_models)])


def test_model_colours_survive_subsets_within_the_default_ten_colour_capacity():
    data = _data()
    first = Figure(data=data, rows=1, cols=1)
    first[0, 0].bar(x="category", y="value", group="model")
    second = Figure(data=data, rows=1, cols=1)
    second[0, 0].line(x="category", y="value", group="model", y_columns=["Model 03", "Model 09"])
    rendered = [first.render(), second.render()]
    try:
        maps = [item._data_visuals_layout["color_maps"]["model"] for item in rendered]
        assert maps[0] == maps[1]
        assert len(set(maps[0].values())) == 10
        lines = rendered[1].axes[0].lines
        assert {line.get_label(): line.get_color() for line in lines} == {
            key: maps[0][key] for key in ("Model 03", "Model 09")}
    finally:
        for item in rendered:
            plt.close(item)


def test_default_palette_rejects_an_oversized_original_domain_even_after_filtering():
    figure = Figure(data=_data(11), rows=1, cols=1)
    figure[0, 0].line(x="category", y="value", group="model", y_columns=["Model 03"])
    before = plt.get_fignums()
    with pytest.raises(ValueError, match="curated-10-default"):
        figure.render()
    assert plt.get_fignums() == before


def test_mixed_span_data_edges_align_including_colourbar_gutters():
    figure = Figure(data=_data(), layout=[[2], [1, 1]], aspect="4:3")
    figure[0, 0].bar(x="category", y="value", group="model")
    figure[1, 0].heatmap(x="category", y="model", value="value", chart_opts={"annotate": False})
    figure[1, 1].line(x="category", y="value", group="model")
    spec = figure.build()
    before = deepcopy(spec.to_dict())
    rendered = figure.render()
    try:
        cells = rendered._data_visuals_layout["cells"]
        assert cells[0, 0]["data_zone"]["x"] == pytest.approx(cells[1, 0]["data_zone"]["x"])
        end = lambda key: cells[key]["data_zone"]["x"] + cells[key]["data_zone"]["w"]
        assert end((0, 0)) == pytest.approx(end((1, 1)))
        assert rendered.get_size_inches()[0] / rendered.get_size_inches()[1] == pytest.approx(4 / 3, abs=0.002)
        assert spec.to_dict() == before
    finally:
        plt.close(rendered)


def test_font_and_background_overrides_do_not_leak_global_matplotlib_settings():
    before = dict(matplotlib.rcParams)
    figure = Figure(data=_data(), rows=1, cols=1,
                    config=FigureConfig(font_family="DejaVu Sans", background="#eeeeee"))
    figure[0, 0].line(x="category", y="value")
    rendered = figure.render()
    try:
        assert rendered.axes[0].xaxis.label.get_fontfamily() == ["DejaVu Sans"]
        assert rendered.get_facecolor()[:3] == pytest.approx((238 / 255,) * 3)
        assert dict(matplotlib.rcParams) == before
    finally:
        plt.close(rendered)


def test_heatmap_colour_domain_is_shared_across_partial_data():
    figure = Figure(data=_data(), rows=1, cols=2)
    for col in range(2):
        figure[0, col].heatmap(x="category", y="model", value="value", chart_opts={"annotate": False})
    spec = figure.build()
    spec.subplots[1].computed_data = spec.subplots[1].computed_data.query("value_mean > 3").copy()
    rendered = figure.render()
    try:
        first, second = [cell["axes"].images[0] for cell in rendered._data_visuals_layout["cells"].values()]
        assert first.norm.vmin == second.norm.vmin == pytest.approx(1)
        assert first.norm.vmax == second.norm.vmax == pytest.approx(4.9)
    finally:
        plt.close(rendered)


def test_insufficient_space_raises_and_closes_the_partial_figure():
    figure = Figure(data=_data(), rows=8, cols=8, base="small", aspect="16:9")
    for row in range(8):
        for col in range(8):
            figure[row, col].bar(x="category", y="value", group="model")
    before = plt.get_fignums()
    with pytest.raises(LayoutError):
        figure.render()
    assert plt.get_fignums() == before


def test_direct_cell_first_layout_sizes_canvas_from_actual_span_topology():
    layout = [[(3, 1)], [1, 1, 1], [1, 1, 1]]
    direct = build_layout(layout=layout, cell_base="large")
    explicit = build_layout(layout=layout, rows=3, cols=3, cell_base="large")
    assert direct["canvas"] == explicit["canvas"]


def test_categorical_ticks_refit_after_long_y_labels_reduce_the_final_axis_width():
    data = pd.DataFrame([{"x": "W" * 10 + str(i), "y": "Y" * 75 + str(j), "v": i + j}
                         for i in range(5) for j in range(2)])
    figure = Figure(data=data, rows=1, cols=1, base="small",
                    config=FigureConfig(font_family="DejaVu Sans"))
    figure[0, 0].heatmap(x="x", y="y", value="v")
    rendered = figure.render()
    try:
        renderer = rendered.canvas.get_renderer()
        axis = rendered._data_visuals_layout["cells"][0, 0]["axes"]
        boxes = [tick.get_window_extent(renderer) for tick in axis.get_xticklabels()]
        assert all(first.x1 < second.x0 for first, second in zip(boxes, boxes[1:]))
    finally:
        plt.close(rendered)
