"""Legend scaling regression tests."""

import pytest
import pandas as pd

from data_visuals.core import Figure
from data_visuals.layout.sizing import compute_figure_legend_font_size


def _build_demo_like_figure(rows: int, cols: int) -> Figure:
    df = pd.read_csv("mock_data/mock_2.csv")
    fig = Figure(data=df, rows=rows, cols=cols, title="Legend Scale", cell_base="large")
    for r in range(rows):
        for c in range(cols):
            fig[r, c].bar(x="case", y="metric1", group="model", title=f"Cell {r},{c}")
    return fig


def test_shared_and_cell_legends_use_same_figure_scale():
    fig = _build_demo_like_figure(3, 3)
    spec = fig.build().to_dict()

    shared_fs = spec["shared_legend"]["font_size"]
    cell_fs = spec["subplots"][0]["font_sizes"]["legend"]
    cell_meta_fs = spec["subplots"][0]["legend"]["font_size"]

    assert shared_fs == cell_fs == cell_meta_fs


def test_multi_subplot_legend_font_can_grow_beyond_old_cell_cap():
    fig = _build_demo_like_figure(3, 3)
    spec = fig.build().to_dict()

    # Old per-cell legend sizing was clamped by DEFAULT_LIMITS["legend"] max=20.
    # Figure-level legend sizing should scale with the whole canvas and exceed that
    # bound for a large multi-panel figure.
    assert spec["shared_legend"]["font_size"] > 20


def test_single_and_multi_subplot_legends_share_figure_level_model():
    single = _build_demo_like_figure(1, 1).build().to_dict()
    multi = _build_demo_like_figure(3, 3).build().to_dict()

    single_expected = compute_figure_legend_font_size(
        single["canvas"]["width"],
        single["canvas"]["height"],
    )
    multi_expected = compute_figure_legend_font_size(
        multi["canvas"]["width"],
        multi["canvas"]["height"],
    )

    assert single["subplots"][0]["font_sizes"]["legend"] == pytest.approx(single_expected, abs=0.1)
    assert multi["subplots"][0]["font_sizes"]["legend"] == pytest.approx(multi_expected, abs=0.1)
    assert multi["shared_legend"]["font_size"] == pytest.approx(multi_expected, abs=0.1)
    assert multi_expected > single_expected