"""User-facing contracts for CSV-to-Figure declarations."""

from __future__ import annotations

from copy import deepcopy
from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.transforms import Bbox
import pandas as pd
import pytest

from data_visuals import plot
from data_visuals.core import Figure


@pytest.fixture
def experiment():
    return pd.DataFrame({
        "dataset": ["A", "A", "B", "B", "A", "A", "B", "B"],
        "model": ["Base", "Ours", "Base", "Ours"] * 2,
        "epoch": [1] * 4 + [2] * 4,
        "accuracy": [0.71, 0.82, 0.73, 0.85, 0.75, 0.88, 0.76, 0.91],
        "f1": [0.68, 0.79, 0.70, 0.82, 0.72, 0.85, 0.73, 0.88],
        "latency": [12.0, 9.0, 12.5, 9.5, 11.8, 8.8, 12.2, 9.2],
        "truth": ["yes", "yes", "no", "no"] * 2,
        "prediction": ["yes", "yes", "yes", "no", "yes", "no", "no", "no"],
    })


def test_csv_and_dataframe_produce_the_same_figure(experiment, tmp_path):
    path = tmp_path / "results.csv"
    experiment.to_csv(path, index=False)
    options = {
        "plots": [{"kind": "bar", "metric": "accuracy"},
                  {"kind": "line", "x": "epoch", "metric": "f1"}],
        "x": "dataset", "group": "model", "style": "modern",
    }
    from_file = plot(path, **options)
    from_frame = plot(experiment, **options)
    assert isinstance(from_file, Figure)
    file_spec, frame_spec = from_file.build(), from_frame.build()
    assert file_spec.canvas == frame_spec.canvas
    assert file_spec.color_domains == frame_spec.color_domains
    for file_panel, frame_panel in zip(file_spec.subplots, frame_spec.subplots):
        assert file_panel.chart_type == frame_panel.chart_type
        assert file_panel.data_mapping == frame_panel.data_mapping
        pd.testing.assert_frame_equal(file_panel.computed_data, frame_panel.computed_data)


def test_csv_reading_options_support_non_comma_files(experiment, tmp_path):
    path = tmp_path / "results.csv"
    experiment.to_csv(path, index=False, sep=";")
    figure = plot(path, plots=[{"kind": "bar", "metric": "accuracy"}],
                  x="dataset", csv_options={"delimiter": ";"})
    panel = figure.build().subplots[0]
    expected = experiment.groupby("dataset")["accuracy"].mean()
    actual = panel.computed_data.set_index("dataset")["accuracy_mean"]
    pd.testing.assert_series_equal(actual, expected, check_names=False)
    with pytest.raises(ValueError, match="CSV"):
        plot(experiment, plots=[{"kind": "bar", "metric": "accuracy"}],
             x="dataset", csv_options={"delimiter": ";"})


def test_global_mappings_are_inherited_and_local_defaults_can_be_disabled(experiment):
    figure = plot(
        experiment, x="dataset", group="model",
        plots=[{"kind": "bar", "metric": "accuracy"},
               {"kind": "line", "x": "epoch", "metric": "f1", "group": None},
               {"kind": "scatter", "x": "latency", "metric": "accuracy", "group": "dataset"}],
    )
    first, second, third = figure.build().subplots
    assert first.data_mapping["x"] == "dataset"
    assert first.data_mapping["group"] == "model"
    assert second.data_mapping["x"] == "epoch"
    assert second.data_mapping.get("group") is None
    assert third.data_mapping["x"] == "latency"
    assert third.data_mapping["group"] == "dataset"
    with pytest.raises(ValueError, match="x"):
        plot(experiment, x="dataset", plots=[{"kind": "bar", "metric": "accuracy", "x": None}])


def test_histogram_uses_its_metric_without_inheriting_a_categorical_x(experiment):
    figure = plot(experiment, x="dataset", group="model", plots=[
        {"kind": "histogram", "metric": "accuracy"},
        {"kind": "histogram", "x": "latency", "group": None},
    ])
    first, second = figure.build().subplots
    assert first.data_mapping["x"] == "accuracy"
    assert first.data_mapping["group"] == "model"
    assert second.data_mapping["x"] == "latency"
    assert second.data_mapping.get("group") is None
    with pytest.raises(ValueError, match="x"):
        plot(experiment, x="dataset", plots=[{"kind": "histogram"}])


def test_matrix_axes_are_explicit_and_do_not_inherit_global_grouping(experiment):
    for kind in ("heatmap", "confusion"):
        panel = {"kind": kind, "y": "truth", "metric": "accuracy"}
        with pytest.raises(ValueError, match="x"):
            plot(experiment, x="dataset", group="model", plots=[panel])
        figure = plot(experiment, x="dataset", group="model", plots=[
            {**panel, "x": "prediction"},
        ])
        mapping = figure.build().subplots[0].data_mapping
        assert mapping["x"] == "prediction"
        assert mapping["y"] == "truth"
        assert mapping["value"] == "accuracy"
        assert mapping.get("group") is None


def test_each_declaration_is_a_panel_even_when_a_metric_is_repeated(experiment):
    figure = plot(experiment, x="dataset", plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "bar", "metric": "f1"},
        {"kind": "box", "metric": "accuracy"},
    ])
    panels = figure.build().subplots
    assert len(panels) == 3
    assert [panel.chart_type for panel in panels] == ["bar", "bar", "box"]
    assert [panel.data_mapping["y"] for panel in panels] == ["accuracy", "f1", "accuracy"]
    assert len({panel.title for panel in panels}) == 3
    assert all(metric in panel.title for metric, panel in zip(["accuracy", "f1", "accuracy"], panels))


def test_inputs_remain_reusable_after_build_and_render(experiment):
    declarations = [
        {"kind": "bar", "metric": "accuracy", "chart_opts": {"hline": 0.8}},
        {"kind": "line", "x": "epoch", "metric": "f1", "group": None},
    ]
    original_declarations = deepcopy(declarations)
    original_data = experiment.copy(deep=True)
    figure = plot(experiment, plots=declarations, x="dataset", group="model")
    rendered = figure.render()
    try:
        assert declarations == original_declarations
        pd.testing.assert_frame_equal(experiment, original_data)
    finally:
        plt.close(rendered)


def test_unknown_kind_identifies_the_failing_declaration(experiment):
    with pytest.raises(ValueError, match=r"plots\[0\].*does-not-exist"):
        plot(experiment, plots=[{"kind": "does-not-exist", "metric": "accuracy"}])


def test_unknown_style_reports_available_choices(experiment):
    with pytest.raises(FileNotFoundError, match="可用主题"):
        plot(experiment, plots=[{"kind": "bar", "metric": "accuracy"}],
             x="dataset", style="does-not-exist")


def test_missing_mapping_and_missing_csv_column_fail_before_export(experiment):
    with pytest.raises(ValueError, match="x"):
        plot(experiment, plots=[{"kind": "bar", "metric": "accuracy"}])
    with pytest.raises(ValueError, match="not_a_metric"):
        plot(experiment, x="dataset", plots=[{"kind": "bar", "metric": "not_a_metric"}])


def test_metric_alias_cannot_silently_override_a_native_mapping(experiment):
    declarations = [
        {"kind": "bar", "metric": "accuracy", "x": "dataset", "y": "f1"},
        {"kind": "histogram", "metric": "accuracy", "x": "latency"},
        {"kind": "heatmap", "metric": "accuracy", "x": "prediction", "y": "truth", "value": "f1"},
    ]
    for declaration in declarations:
        with pytest.raises(ValueError, match="metric.*重复"):
            plot(experiment, plots=[declaration])


def test_malformed_declarations_explain_the_expected_input(experiment):
    with pytest.raises(TypeError, match="plots"):
        plot(experiment, plots="accuracy")
    with pytest.raises(TypeError, match=r"plots\[0\]"):
        plot(experiment, plots=["accuracy"])
    with pytest.raises(ValueError, match="kind"):
        plot(experiment, plots=[{"metric": "accuracy"}])


def test_empty_figures_and_invalid_column_counts_fail_clearly(experiment):
    with pytest.raises(ValueError, match="子图"):
        plot(experiment, plots=[])
    for columns in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="cols"):
            plot(experiment, plots=[{"kind": "histogram", "metric": "accuracy"}], cols=columns)


def test_native_options_custom_titles_and_style_reuse_the_existing_pipeline(experiment):
    figure = plot(experiment, x="dataset", style="modern", plots=[
        {"kind": "bar", "y": "accuracy", "horizontal": True, "title": "Accuracy by dataset"},
        {"kind": "histogram", "x": "latency", "bins": 4, "title": None},
    ])
    spec = figure.build()
    assert spec.theme == "modern"
    assert spec.subplots[0].chart_options["horizontal"] is True
    assert spec.subplots[0].title == "Accuracy by dataset"
    assert spec.subplots[1].chart_options["bins"] == 4
    assert spec.subplots[1].title is None


def test_five_panels_fill_the_last_row_and_render_without_collisions(experiment):
    figure = plot(experiment, x="dataset", group="model", cols=3, style="modern", plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "line", "x": "epoch", "metric": "f1"},
        {"kind": "box", "metric": "latency"},
        {"kind": "scatter", "x": "latency", "metric": "accuracy"},
        {"kind": "histogram", "metric": "accuracy", "group": None},
    ]).render()
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        cells = list(figure._data_visuals_layout["cells"].values())
        assert len(cells) == 5
        rows = {}
        for record in cells:
            box = record["cell"]
            rows.setdefault(round(box["y"], 6), []).append(box)
        ordered_rows = [sorted(row, key=lambda box: box["x"]) for _, row in sorted(rows.items())]
        assert all(len(row) <= 3 for row in ordered_rows)
        top, bottom = ordered_rows[0], ordered_rows[-1]
        for row in ordered_rows:
            assert row[0]["x"] == pytest.approx(top[0]["x"])
            assert row[-1]["x"] + row[-1]["w"] == pytest.approx(top[-1]["x"] + top[-1]["w"])
            assert all(box["w"] == pytest.approx(row[0]["w"]) for box in row)
        if len(bottom) < len(top):
            assert bottom[0]["w"] > top[0]["w"]
        boxes = [cell["axes"].get_tightbbox(renderer) for cell in cells]
        for box in boxes:
            assert box.x0 >= figure.bbox.x0 - 1
            assert box.y0 >= figure.bbox.y0 - 1
            assert box.x1 <= figure.bbox.x1 + 1
            assert box.y1 <= figure.bbox.y1 + 1
        for first, second in combinations(boxes, 2):
            overlap = Bbox.intersection(first, second)
            assert overlap is None or overlap.width <= 1 or overlap.height <= 1
    finally:
        plt.close(figure)
