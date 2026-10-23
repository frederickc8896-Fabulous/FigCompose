"""Integrity checks for supplied paired training differences and intervals."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from demo.matched_training_data import (
    ACTUAL_ID_NODES,
    BACKBONE_ORDER,
    NOMINAL_BUDGETS,
    PANEL_ORDER,
    load_matched_training_data,
)


SOURCE = Path(__file__).resolve().parents[1] / "matched_id_training_gains_plot_data.csv"


@pytest.fixture(scope="module")
def loaded():
    return load_matched_training_data(SOURCE)


def _write(tmp_path, data):
    path = tmp_path / "matched.csv"
    data.to_csv(path, index=False)
    return path


def test_retains_every_preaggregated_value_and_all_columns(loaded):
    pd.testing.assert_frame_equal(loaded["data"], pd.read_csv(SOURCE), check_exact=True)
    assert loaded["data"].shape == (24, 21)
    assert loaded["nodes"] == pytest.approx(ACTUAL_ID_NODES, abs=1e-12)
    for panel in PANEL_ORDER:
        for backbone in BACKBONE_ORDER:
            rows = loaded["data"].loc[
                loaded["data"]["panel"].eq(panel)
                & loaded["data"]["backbone"].eq(backbone)
            ]
            assert rows["nominal_id_budget_pct"].tolist() == list(NOMINAL_BUDGETS)
            assert rows["actual_id_false_reject_pct"].tolist() == pytest.approx(
                ACTUAL_ID_NODES, abs=1e-12
            )


def test_interval_direction_and_known_zero_crossings(loaded):
    data = loaded["data"]
    assert (data["delta_leakage_pp"] < 0).all()
    crossing = data.loc[(data["ci95_lower_pp"] <= 0) & (data["ci95_upper_pp"] >= 0)]
    assert set(
        crossing[["panel", "backbone", "nominal_id_budget_pct"]].itertuples(
            index=False, name=None
        )
    ) == {
        ("near_ood", "xsmall", 5.0),
        ("near_ood", "xsmall", 10.0),
        ("far_ood", "small", 2.0),
    }
    first = data.iloc[0]
    assert first["delta_leakage_pp"] == pytest.approx(-11.55)
    assert first["ci95_lower_pp"] == pytest.approx(-13.371875)
    assert first["ci95_upper_pp"] == pytest.approx(-8.3125)
    assert first["errorbar_lower_pp"] == pytest.approx(1.821875)
    assert first["errorbar_upper_pp"] == pytest.approx(3.2375)


def test_metadata_hashes_csv_and_distinguishes_declared_provenance(loaded):
    metadata = loaded["metadata"]
    assert metadata["source_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert metadata["source_rows"] == metadata["plot_rows"] == 24
    assert metadata["n_paired_seeds"] == 5
    assert metadata["n_rewrites"] == 8
    assert metadata["bootstrap_replicates"] == 5000
    assert metadata["ci_method"] == "paired_seed_bootstrap"
    assert "not independently recomputed or verified" in metadata["provenance_check"]
    json.dumps(metadata, allow_nan=False)


def test_preserves_shuffled_rows_and_additional_columns(tmp_path):
    data = pd.read_csv(SOURCE).sample(frac=1, random_state=3).reset_index(drop=True)
    data["review_note"] = [f"source row {i}" for i in range(len(data))]
    source = _write(tmp_path, data)
    pd.testing.assert_frame_equal(
        load_matched_training_data(source)["data"], pd.read_csv(source), check_exact=True
    )


@pytest.mark.parametrize("kind", ["missing", "additional", "duplicate"])
def test_rejects_incomplete_or_duplicate_condition_grid(tmp_path, kind):
    data = pd.read_csv(SOURCE)
    if kind == "missing":
        data = data.iloc[:-1]
    elif kind == "additional":
        data = pd.concat([data, data.iloc[:1]], ignore_index=True)
    else:
        data.iloc[-1] = data.iloc[-2]
    with pytest.raises(ValueError, match="24 preaggregated rows|duplicate"):
        load_matched_training_data(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("score", "other"),
        ("policy", "fixed"),
        ("description_pool", "REF"),
        ("n_rewrites", 7),
        ("n_paired_seeds", 4),
        ("ci_method", "unpaired_bootstrap"),
        ("bootstrap_replicates", 1000),
        ("delta_definition", "single_phrase_minus_multi_phrase"),
    ],
)
def test_rejects_a_changed_scientific_comparison(tmp_path, column, value):
    data = pd.read_csv(SOURCE)
    data.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        load_matched_training_data(_write(tmp_path, data))


def test_rejects_one_unmatched_actual_id_operating_point(tmp_path):
    data = pd.read_csv(SOURCE)
    data.loc[0, "actual_id_false_reject_pct"] += 0.1
    with pytest.raises(ValueError, match="must share the actual ID node"):
        load_matched_training_data(_write(tmp_path, data))


def test_accepts_roundoff_without_changing_original_node_values(tmp_path):
    data = pd.read_csv(SOURCE)
    data.loc[0, "actual_id_false_reject_pct"] += 1e-12
    source = _write(tmp_path, data)
    pd.testing.assert_frame_equal(
        load_matched_training_data(source)["data"], pd.read_csv(source), check_exact=True
    )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("single_phrase_leakage_pct", 101.0, "between 0 and 100"),
        ("delta_leakage_pp", 11.55, "Multi-phrase minus Single-phrase"),
        ("ci95_lower_pp", 0.0, "contain its reported delta"),
        ("ci95_upper_pp", -20.0, "contain its reported delta"),
        ("errorbar_lower_pp", -0.1, "nonnegative"),
        ("errorbar_upper_pp", 4.0, "disagrees with"),
        ("delta_leakage_pp", float("inf"), "non-finite"),
        ("errorbar_upper_pp", float("nan"), "missing values"),
        ("ci95_upper_pp", "invalid", "must be numeric"),
    ],
)
def test_rejects_invalid_values_or_inconsistent_errorbar_geometry(
    tmp_path, column, value, message
):
    data = pd.read_csv(SOURCE)
    if isinstance(value, str):
        data[column] = data[column].astype(object)
    data.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        load_matched_training_data(_write(tmp_path, data))


def test_rejects_missing_interval_column(tmp_path):
    data = pd.read_csv(SOURCE).drop(columns="ci95_lower_pp")
    with pytest.raises(ValueError, match="required columns are missing"):
        load_matched_training_data(_write(tmp_path, data))
