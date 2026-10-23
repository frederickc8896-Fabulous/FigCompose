"""Inside legends participate in the real scatter-label placement pipeline."""
import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.renderer.mpl import annotations


@pytest.fixture(autouse=True)
def close_test_figures():
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


def _paper(position, frameon, point=None, labels=False):
    data = pd.DataFrame({"x": [2., 5., 8.], "y": [4., 5., 3.],
                         "group": ["Reference", "Rewrites", "Mean"], "identifier": [1, 2, 3]})
    if point is not None:
        data.loc[0, ["x", "y"]] = point
    paper = Figure(data=data, rows=1, cols=1, theme="modern",
                   canvas={"width": 4.2, "height": 3.6, "unit": "in"},
                   legend={"scope": "local", "position": position,
                           "frameon": frameon, "ncols": 1})
    options = {"xlim": [0, 10], "ylim": [0, 10], "xticks": [0, 5, 10], "yticks": [0, 5, 10],
               "series_styles": {"Reference": {"marker": "*", "label": "Reference description"},
                                 "Rewrites": {"marker": "o", "label": "Individual rewrites"},
                                 "Mean": {"marker": "D", "label": "Mean over rewrites"}}}
    if labels:
        options["point_labels"] = {"column": "identifier", "fontsize": 8}
    paper[0, 0].scatter(x="x", y="y", group="group", title="Operating points", chart_opts=options)
    return paper, data


def _cell(figure):
    return figure._data_visuals_layout["cells"][0, 0]


def _legend_boxes(figure):
    renderer = figure.canvas.get_renderer()
    return [artist.get_window_extent(renderer) for artist in _cell(figure)["legends"]]


@pytest.mark.parametrize("position", ["upper left", "upper right"])
@pytest.mark.parametrize("frameon", [False, True])
def test_inside_legend_changes_conflicting_point_label_placement_without_moving_points(
        monkeypatch, position, frameon):
    # Locate a marker just below a real legend. Its nearest unconstrained label
    # position lies inside the legend, making this a concrete collision case.
    template = _paper(position, frameon)[0].render()
    occupied = Bbox.union(_legend_boxes(template))
    display_point = ((occupied.x0 + occupied.x1) / 2, occupied.y0 - 4)
    point = _cell(template)["axes"].transData.inverted().transform(display_point)
    native_placement = annotations.place_point_labels
    with monkeypatch.context() as patch:
        patch.setattr(annotations, "place_point_labels",
                      lambda ax, cfg, *, obstacles=(): native_placement(ax, cfg))
        unconstrained = _paper(position, frameon, point=point, labels=True)[0].render()
    assert any(label.overlaps(legend) for label in _cell(unconstrained)["point_labels"]["boxes"]
               for legend in _legend_boxes(unconstrained))

    paper, original = _paper(position, frameon, point=point, labels=True)
    figure = paper.render()
    cell = _cell(figure)
    assert len(cell["point_labels"]["texts"]) == 3
    assert not any(label.overlaps(legend) for label in cell["point_labels"]["boxes"]
                   for legend in _legend_boxes(figure))
    assert {text.get_text() for text in cell["point_labels"]["texts"]} == {"1", "2", "3"}
    by_group = {artist._data_visuals_series_key: artist for artist in cell["axes"].collections}
    for group, rows in original.groupby("group"):
        np.testing.assert_allclose(by_group[group].get_offsets(), rows[["x", "y"]].to_numpy())
