"""Tests for compute-side derived_data payloads in Figure.build()."""

import pytest
import pandas as pd

from data_visuals.core import Figure


def test_scatter_trend_writes_trend_data_into_derived_data():
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 1, 2, 3, 4],
        "y": [2, 3, 5, 7, 1, 2, 2.5, 4],
        "group": ["A", "A", "A", "A", "B", "B", "B", "B"],
    })

    fig = Figure(data=df, rows=1, cols=1)
    fig[0, 0].scatter(x="x", y="y", group="group", trend=True)
    spec = fig.build()
    sp = spec.subplots[0]

    trend_df = sp.derived_data["trend_data"]
    assert not trend_df.empty
    assert {"x", "y", "group"}.issubset(trend_df.columns)
    assert set(trend_df["group"].unique()) == {"A", "B"}


def test_histogram_density_writes_density_data_into_derived_data():
    df = pd.DataFrame({
        "score": [0.1, 0.2, 0.25, 0.3, 0.8, 0.85, 0.9, 0.95],
        "group": ["L", "L", "L", "L", "H", "H", "H", "H"],
    })

    fig = Figure(data=df, rows=1, cols=1)
    fig[0, 0].histogram(x="score", group="group", density=True)
    spec = fig.build()
    sp = spec.subplots[0]

    density_df = sp.derived_data["density_data"]
    assert not density_df.empty
    assert {"score", "density", "group"}.issubset(density_df.columns)
    assert set(density_df["group"].unique()) == {"L", "H"}


def test_box_writes_summary_and_outliers_into_derived_data():
    df = pd.DataFrame({
        "case": ["C1"] * 10 + ["C2"] * 10,
        "model": ["A"] * 5 + ["B"] * 5 + ["A"] * 5 + ["B"] * 5,
        "value": [
            1.00, 1.02, 1.04, 1.06, 4.50,
            1.10, 1.12, 1.14, 1.16, 1.18,
            2.00, 2.02, 2.04, 2.06, 2.08,
            2.10, 2.12, 2.14, 2.16, 6.00,
        ],
    })

    fig = Figure(data=df, rows=1, cols=1)
    fig[0, 0].box(x="case", y="value", group="model", mean_line=True)
    spec = fig.build()
    sp = spec.subplots[0]

    summary_df = sp.derived_data["box_summary"]
    outliers_df = sp.derived_data["box_outliers"]
    mean_map = sp.derived_data["overall_mean"]

    assert not summary_df.empty
    assert {"case", "model", "Q1", "median", "Q3", "lower", "upper"}.issubset(summary_df.columns)
    assert not outliers_df.empty
    assert {"case", "model", "value"}.issubset(outliers_df.columns)
    assert mean_map["value"] == pytest.approx(df["value"].mean())


def test_confusion_normalize_writes_matrix_into_derived_data():
    df = pd.DataFrame({
        "truth": ["A", "A", "A", "B", "B", "B"],
        "pred": ["A", "A", "B", "A", "B", "B"],
    })

    fig = Figure(data=df, rows=1, cols=1)
    fig[0, 0].confusion(x="truth", y="pred", normalize=True)
    spec = fig.build()
    sp = spec.subplots[0]

    matrix_df = sp.derived_data["confusion_matrix"]
    assert not matrix_df.empty
    assert len(matrix_df) == 4
    count_col = "truth_count"
    assert count_col in matrix_df.columns
    row_sums = matrix_df.groupby("pred", sort=True)[count_col].sum()
    assert all(value == pytest.approx(1.0) for value in row_sums)