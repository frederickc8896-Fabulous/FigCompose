"""Explicit shared overrides and extreme dimensions never fail silently."""
import matplotlib.pyplot as plt
from matplotlib.legend import Legend
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.layout.placement import LayoutError


@pytest.fixture(autouse=True)
def close_figures():
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


def _paper(*, rows=2, legend=None, canvas=None, panel_options=None):
    paper = Figure(data=pd.DataFrame({"x": [1, 2, 3], "y": [3, 2, 1], "g": ["A", "B", "C"]}),
                   rows=rows, cols=1, legend=legend,
                   canvas=canvas or {"width": 120, "height": 130})
    for row in range(rows):
        options = {} if panel_options is None else panel_options.get(row, {})
        paper[row, 0].scatter(x="x", y="y", group="g", chart_opts=options)
    return paper


def test_a_single_panel_can_declare_its_shared_style_explicitly():
    figure = _paper(rows=1, panel_options={0: {"legend": {
        "scope": "shared", "position": "bottom", "fontsize": 10, "ncols": 3,
    }}}).render()
    assert len(figure.legends) == 1
    legend = figure.legends[0]
    assert all(text.get_fontsize() == 10 for text in legend.get_texts())
    assert legend.get_window_extent(figure.canvas.get_renderer()).y1 < figure.axes[0].bbox.y0


def test_conflicting_shared_styles_are_reported_without_leaking_figures():
    before = set(plt.get_fignums())
    with pytest.raises(ValueError, match="Shared legend overrides conflict"):
        _paper(legend={"scope": "shared"}, panel_options={
            0: {"legend": {"scope": "shared", "ncols": 1}},
            1: {"legend": {"scope": "shared", "ncols": 3}},
        }).render()
    assert set(plt.get_fignums()) == before


def test_a_large_local_font_does_not_change_the_shared_default_font():
    figure = _paper(legend={"scope": "shared", "position": "bottom"}, panel_options={
        0: {"legend": {"position": "upper right", "fontsize": 12}},
    }).render()
    layout = figure._data_visuals_layout
    shared = [artist for artist in layout["shared_legends"] if isinstance(artist, Legend)]
    local = [artist for artist in layout["cells"][0, 0]["legends"] if isinstance(artist, Legend)]
    assert shared and local
    assert {text.get_fontsize() for legend in shared for text in legend.get_texts()} == {8}
    assert {text.get_fontsize() for legend in local for text in legend.get_texts()} == {12}


def test_an_explicit_shared_null_font_restores_the_theme_default():
    figure = _paper(rows=1, legend={"fontsize": 12}, panel_options={
        0: {"legend": {"scope": "shared", "fontsize": None}},
    }).render()
    assert {text.get_fontsize() for legend in figure.legends for text in legend.get_texts()} == {8}


@pytest.mark.parametrize("width", [10, 20])
def test_impossible_side_strip_reports_a_layout_error(width):
    with pytest.raises(LayoutError) as failure:
        _paper(rows=1, legend={"scope": "shared", "position": "left"},
               canvas={"width": width, "height": 80}).render()
    assert failure.value.axis == "width"
    assert failure.value.required_width is not None


def test_impossible_inside_gap_reports_a_layout_error():
    with pytest.raises(LayoutError) as failure:
        _paper(rows=1, legend={"scope": "local", "position": "upper right", "gap": 200}).render()
    assert failure.value.axis == "width"

