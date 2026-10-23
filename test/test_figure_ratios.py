"""Test Figure API support for figure-level width and height ratios."""

import pytest

from data_visuals.core import Figure


def test_figure_width_height_ratios_flow_into_layout(sample_df):
    fig = Figure(
        data=sample_df,
        rows=2,
        cols=2,
        aspect="4:3",
        base="medium",
        width_ratios=[2, 1],
        height_ratios=[1, 2],
        title="Ratio Grid",
    )
    fig[0, 0].bar(x="method", y="accuracy")
    fig[0, 1].bar(x="method", y="accuracy")
    fig[1, 0].bar(x="method", y="accuracy")
    fig[1, 1].bar(x="method", y="accuracy")

    spec = fig.build().to_dict()
    cells = {(sp["row"], sp["col"]): sp for sp in spec["subplots"]}

    assert cells[(0, 0)]["geometry"]["w"] == pytest.approx(cells[(0, 1)]["geometry"]["w"] * 2, abs=0.3)
    assert cells[(1, 0)]["geometry"]["h"] == pytest.approx(cells[(0, 0)]["geometry"]["h"] * 2, abs=0.3)