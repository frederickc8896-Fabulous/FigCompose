"""Scientific data-integrity checks for the rejection-rewrite case study."""

from math import fsum
from pathlib import Path

import pandas as pd
import pytest

from demo.rejection_rewrite_data import (
    BACKBONE_ORDER,
    METRICS,
    TRAINING_ORDER,
    load_and_summarize,
)


SOURCE = Path(__file__).resolve().parents[1] / "rejection_rewrite_plot_data.csv"


@pytest.fixture(scope="module")
def summary():
    return load_and_summarize(SOURCE)


def _write(tmp_path, frame):
    path = tmp_path / "rejection.csv"
    frame.to_csv(path, index=False)
    return path


def test_complete_case_study_and_numbering(summary):
    assert summary["metadata"]["source_rows"] == 270
    assert summary["metadata"]["filtered_rows"] == 270
    assert summary["metadata"]["seeds"] == [0, 7, 42, 99, 127]
    assert len(summary["points"]) == 60
    assert len(summary["seed_means"]) == 30
    assert summary["mapping"]["description_id"].tolist() == [
        "OUT_nomatch",
        "OUT_outside",
        "OUT_unrelated",
        "OUT_notinlist",
        "OUT_notabout",
        "OUT_notamong",
        "OUT_concerns",
        "OUT_otherthan",
    ]
    for _, panel in summary["points"].groupby(["backbone", "training"]):
        assert panel["kind"].value_counts().to_dict() == {
            "rewrite": 8,
            "reference": 1,
            "mean": 1,
        }
        rewrites = panel.loc[panel["kind"].eq("rewrite")]
        assert rewrites["rewrite_number"].tolist() == list(range(1, 9))
        assert rewrites["description_id"].tolist() == summary["mapping"][
            "description_id"
        ].tolist()


def test_every_description_point_is_a_five_seed_mean(summary):
    source = summary["filtered"]
    for point in summary["points"].to_dict("records"):
        if point["kind"] == "mean":
            continue
        rows = source.loc[
            source["backbone"].eq(point["backbone"])
            & source["training"].eq(point["training"])
            & source["description_id"].eq(point["description_id"])
        ]
        assert len(rows) == 5
        for metric in METRICS:
            assert point[metric] == pytest.approx(fsum(rows[metric]) / 5, abs=1e-12)


def test_overall_rewrite_mean_uses_all_eight_rewrites_in_each_seed(summary):
    source = summary["filtered"]
    for backbone in BACKBONE_ORDER:
        for training in TRAINING_ORDER:
            panel = source.loc[
                source["backbone"].eq(backbone)
                & source["training"].eq(training)
                & source["pool"].eq("OUT")
            ]
            point = summary["points"].loc[
                summary["points"]["backbone"].eq(backbone)
                & summary["points"]["training"].eq(training)
                & summary["points"]["kind"].eq("mean")
            ].iloc[0]
            for metric in METRICS:
                means = []
                for seed, rows in panel.groupby("seed"):
                    assert len(rows) == 8
                    expected = fsum(rows[metric]) / 8
                    reported = summary["seed_means"].loc[
                        summary["seed_means"]["backbone"].eq(backbone)
                        & summary["seed_means"]["training"].eq(training)
                        & summary["seed_means"]["seed"].eq(seed),
                        metric,
                    ].item()
                    assert reported == pytest.approx(expected, abs=1e-12)
                    means.append(expected)
                assert point[metric] == pytest.approx(fsum(means) / 5, abs=1e-12)


def test_known_operating_points_guard_against_aggregation_regressions(summary):
    # Independently recorded x/y means for the six panels, in display order.
    expected = (
        ("xsmall", "Single-phrase", 5.35, 27.275, 1.221875, 63.66875),
        ("small", "Single-phrase", 3.75, 36.95, 0.83125, 71.653125),
        ("roberta", "Single-phrase", 5.55, 23.425, 1.4625, 57.40625),
        ("xsmall", "Multi-phrase", 4.475, 27.525, 3.01875, 36.69375),
        ("small", "Multi-phrase", 5.175, 29.15, 3.525, 38.184375),
        ("roberta", "Multi-phrase", 4.55, 25.2, 3.359375, 29.359375),
    )
    for backbone, training, ref_x, ref_y, mean_x, mean_y in expected:
        panel = summary["points"].loc[
            summary["points"]["backbone"].eq(backbone)
            & summary["points"]["training"].eq(training)
        ].set_index("kind")
        assert panel.loc["reference", "id_false_reject_pct"] == pytest.approx(ref_x)
        assert panel.loc["reference", "near_leak_pct"] == pytest.approx(ref_y)
        assert panel.loc["mean", "id_false_reject_pct"] == pytest.approx(mean_x)
        assert panel.loc["mean", "near_leak_pct"] == pytest.approx(mean_y)


def test_filters_nonqualifying_rows_without_dropping_any_qualifying_rows(tmp_path):
    frame = pd.read_csv(SOURCE)
    extras = frame.iloc[:4].copy()
    extras.loc[extras.index[0], "score"] = "other_score"
    extras.loc[extras.index[1], "policy"] = "recalibrated"
    extras.loc[extras.index[2], "reference_budget"] = 0.1
    extras.loc[extras.index[3], "pool"] = "IN"
    result = load_and_summarize(_write(tmp_path, pd.concat([frame, extras])))
    assert result["metadata"]["source_rows"] == 274
    assert result["metadata"]["filtered_rows"] == 270
    assert len(result["mapping"]) == 8


def test_rejects_missing_rewrite_observation(tmp_path):
    with pytest.raises(ValueError, match="270 qualifying rows"):
        load_and_summarize(_write(tmp_path, pd.read_csv(SOURCE).iloc[:-1]))


def test_rejects_duplicate_observation_even_when_row_count_matches(tmp_path):
    frame = pd.read_csv(SOURCE)
    frame.iloc[-1] = frame.iloc[-2]
    with pytest.raises(ValueError, match="duplicate"):
        load_and_summarize(_write(tmp_path, frame))


def test_rejects_changed_threshold_for_an_individual_rewrite(tmp_path):
    frame = pd.read_csv(SOURCE)
    index = frame.index[frame["pool"].eq("OUT")][0]
    frame.loc[index, "tau_reference"] *= 1.1
    with pytest.raises(ValueError, match="reuse the reference threshold"):
        load_and_summarize(_write(tmp_path, frame))


def test_rejects_inconsistent_rewrite_text_across_seeds(tmp_path):
    frame = pd.read_csv(SOURCE)
    frame.loc[1, "description_text"] = "An accidentally changed rewrite."
    with pytest.raises(ValueError, match="inconsistent text"):
        load_and_summarize(_write(tmp_path, frame))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 100.1])
def test_rejects_unplottable_measurements(tmp_path, value):
    frame = pd.read_csv(SOURCE)
    frame.loc[1, "near_leak_pct"] = value
    with pytest.raises(ValueError, match="missing values|non-finite|between 0 and 100"):
        load_and_summarize(_write(tmp_path, frame))


def test_checks_checkpoint_identifier_if_export_provides_one(tmp_path):
    frame = pd.read_csv(SOURCE)
    frame["checkpoint_id"] = frame[list(("backbone", "training", "seed"))].astype(str).agg("/".join, axis=1)
    load_and_summarize(_write(tmp_path, frame))
    frame.loc[1, "checkpoint_id"] = "another-checkpoint"
    with pytest.raises(ValueError, match="changes checkpoint_id"):
        load_and_summarize(_write(tmp_path, frame))
