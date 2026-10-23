"""Panel filters must precede aggregation and every derived statistic."""

from __future__ import annotations

import pandas as pd
import pytest

from data_visuals.core import Figure


def _figure(data, *, rows=1, cols=1):
    # These tests exercise the compute contract without a physical-layout solve.
    return Figure(data=data, rows=rows, cols=cols, aspect="16:10")


@pytest.fixture
def experiments():
    return pd.DataFrame({
        "backbone": ["small"] * 4 + ["large"] * 4,
        "training": ["single", "single", "multi", "multi"] * 2,
        "model": ["A", "B", "A", "B", "A", "B", "C", "C"],
        "x": [1, 2, 3, 4, 10, 20, 30, 40],
        "y": [2, 4, 6, 8, 100, 200, 300, 400],
    }, index=[13, 17, 23, 31, 41, 43, 47, 53])


def test_scatter_scalar_and_list_filters_select_each_panel_without_mutation(experiments):
    original = experiments.copy(deep=True)
    where = {"backbone": "small", "training": ["single", "multi"]}
    fig = _figure(experiments, cols=2)
    fig[0, 0].scatter(x="x", y="y", group="model", where=where)
    fig[0, 1].set("scatter", x="x", y="y", group="model", where={
        "backbone": ["large"], "training": "multi",
    })
    # Mutating a caller-owned declaration after assigning it cannot change it.
    where["training"].clear()
    left, right = fig.build().subplots

    pd.testing.assert_frame_equal(left.computed_data, original.iloc[:4])
    pd.testing.assert_frame_equal(right.computed_data, original.iloc[6:])
    pd.testing.assert_frame_equal(experiments, original)
    assert "where" not in left.data_mapping
    assert "where" not in right.chart_options
    assert fig.build().color_domains == {"model": ["A", "B", "C"]}
    # Renderer edits to one panel's payload must not reach the source frame.
    left.computed_data.loc[13, "y"] = -100
    pd.testing.assert_frame_equal(experiments, original)


def test_redeclaring_a_panel_rebuilds_its_filter(experiments):
    fig = _figure(experiments)
    fig[0, 0].scatter(x="x", y="y", where={"backbone": "small"})
    assert len(fig.build().subplots[0].computed_data) == 4
    fig[0, 0].set("scatter", x="x", y="y", where={"backbone": "large"})
    assert fig.build().subplots[0].computed_data["x"].tolist() == [10, 20, 30, 40]


def test_unused_source_categories_keep_their_global_color_slots(experiments):
    fig = _figure(experiments, cols=2)
    fig[0, 0].scatter(x="x", y="y", group="model", where={
        "backbone": "small", "model": "B",
    }, labels={"A": "First", "B": "Second", "C": "Third"})
    fig[0, 1].scatter(x="x", y="y", group="model", where={
        "backbone": "large", "model": "B",
    })
    spec = fig.build()
    assert spec.color_domains == {"model": ["First", "Second", "Third"]}
    assert all(panel.computed_data["model"].tolist() == ["Second"] * len(panel.computed_data)
               for panel in spec.subplots)


@pytest.mark.parametrize("where", [None, {}])
def test_absent_or_empty_filter_preserves_all_observations(experiments, where):
    fig = _figure(experiments)
    fig[0, 0].scatter(x="x", y="y", where=where)
    pd.testing.assert_frame_equal(fig.build().subplots[0].computed_data, experiments)


@pytest.mark.parametrize("value", [None, float("nan"), pd.NA, [None], ["A", None]])
def test_null_filters_work_with_nullable_columns(value):
    df = pd.DataFrame({
        "run": pd.Series(["A", None, "B"], dtype="string"),
        "x": [1, 2, 3], "y": [10, 20, 30],
    })
    fig = _figure(df)
    fig[0, 0].scatter(x="x", y="y", where={"run": value})
    expected = [1, 2] if isinstance(value, list) and len(value) == 2 else [2]
    assert fig.build().subplots[0].computed_data["x"].tolist() == expected


def test_bar_aggregation_and_uncertainty_use_filtered_replicates():
    df = pd.DataFrame({
        "run": ["target", "target", "other", "other"],
        "case": ["A"] * 4, "value": [1., 3., 100., 200.],
        "precomputed_error": [0.1, 0.3, 10., 20.],
    })
    fig = _figure(df, cols=2)
    fig[0, 0].bar(x="case", y="value", error="std", mean_line=True,
                  where={"run": "target"})
    fig[0, 1].bar(x="case", y="value", error="precomputed_error",
                  where={"run": "target"})
    repeated, precomputed = fig.build().subplots
    assert repeated.computed_data["value_mean"].tolist() == [2.]
    assert repeated.computed_data["value_std"].iloc[0] == pytest.approx(2 ** 0.5)
    assert repeated.derived_data["overall_mean"] == {"value_mean": 2.}
    assert precomputed.computed_data["precomputed_error"].tolist() == [0.2]


def test_line_means_and_secondary_axis_use_only_selected_replicates():
    df = pd.DataFrame({
        "run": ["target"] * 4 + ["other"] * 4,
        "step": [1, 1, 2, 2] * 2,
        "value": [1., 3., 5., 7., 100., 200., 300., 400.],
        "secondary": [10., 30., 50., 70., 1000., 2000., 3000., 4000.],
    })
    fig = _figure(df)
    fig[0, 0].line(x="step", y="value", y2="secondary", where={"run": "target"})
    computed = fig.build().subplots[0].computed_data
    assert computed["step"].tolist() == [1, 2]
    assert computed["value"].tolist() == [2., 6.]
    assert computed["secondary"].tolist() == [20., 60.]


def test_trend_and_density_do_not_reintroduce_filtered_out_observations(experiments):
    fig = _figure(experiments, cols=2)
    fig[0, 0].scatter(x="x", y="y", trend=True, where={"backbone": "small"})
    fig[0, 1].histogram(x="x", density=True, where={"backbone": "small"})
    scatter, histogram = fig.build().subplots
    trend = scatter.derived_data["trend_data"]
    density = histogram.derived_data["density_data"]
    assert trend["x"].tolist() == [1., 2., 3., 4.]
    assert trend["y"].tolist() == pytest.approx([2., 4., 6., 8.])
    assert density["x"].min() == 1.
    assert density["x"].max() == 4.


def test_box_quartiles_outliers_and_overall_mean_use_filtered_observations():
    df = pd.DataFrame({
        "run": ["target"] * 5 + ["other"] * 5,
        "case": ["A"] * 10,
        "value": [1., 2., 3., 4., 20., 100., 200., 300., 400., 2000.],
    })
    fig = _figure(df)
    fig[0, 0].box(x="case", y="value", mean_line=True, where={"run": "target"})
    derived = fig.build().subplots[0].derived_data
    assert derived["box_summary"]["Q1"].tolist() == [2.]
    assert derived["box_summary"]["median"].tolist() == [3.]
    assert derived["box_summary"]["Q3"].tolist() == [4.]
    assert derived["box_outliers"]["value"].tolist() == [20.]
    assert derived["overall_mean"] == {"value": 6.}


def test_confusion_normalization_uses_filtered_counts():
    df = pd.DataFrame({
        "run": ["target"] * 4 + ["other"] * 4,
        "truth": ["A", "A", "B", "B"] * 2,
        "prediction": ["A", "A", "B", "B", "B", "B", "A", "A"],
    })
    fig = _figure(df)
    fig[0, 0].confusion(x="truth", y="prediction", normalize=True,
                       where={"run": "target"})
    matrix = fig.build().subplots[0].derived_data["confusion_matrix"]
    counts = matrix.set_index(["truth", "prediction"])["truth_count"]
    assert counts.to_dict() == {("A", "A"): 1., ("A", "B"): 0.,
                                ("B", "A"): 0., ("B", "B"): 1.}


@pytest.mark.parametrize("where, message", [
    ("backbone == 'small'", "字典"),
    ([], "字典"),
    ({None: "small"}, "列名"),
    ({"missing": "small"}, "不存在.*missing"),
    ({"backbone": {}}, "标量"),
    ({"backbone": {"small"}}, "标量"),
    ({"backbone": ("small", "large")}, "标量"),
    ({"backbone": []}, "非空"),
    ({"backbone": [["small"]]}, "标量"),
    ({"backbone": "unknown"}, "没有数据"),
    ({"backbone": "small", "training": "unknown"}, "没有数据"),
])
def test_invalid_filters_identify_subplot_and_problem(experiments, where, message):
    fig = _figure(experiments)
    fig[0, 0].scatter(x="x", y="y", where=where)
    with pytest.raises(ValueError, match=rf"子图 \[0,0\] where.*{message}"):
        fig.build()
