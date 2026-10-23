"""Validate the supplied, preaggregated matched-ID training comparison.

The CSV already contains paired-seed bootstrap intervals.  Loading it neither
aggregates observations nor recomputes confidence intervals.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PANEL_ORDER = ("near_ood", "far_ood")
BACKBONE_ORDER = ("xsmall", "small", "roberta")
NOMINAL_BUDGETS = (1.0, 2.0, 5.0, 10.0)
ACTUAL_ID_NODES = (0.875, 1.875, 4.875, 9.875)
NUMERIC_COLUMNS = (
    "n_rewrites",
    "nominal_id_budget_pct",
    "actual_id_false_reject_pct",
    "single_phrase_leakage_pct",
    "multi_phrase_leakage_pct",
    "delta_leakage_pp",
    "ci95_lower_pp",
    "ci95_upper_pp",
    "errorbar_lower_pp",
    "errorbar_upper_pp",
    "n_paired_seeds",
    "bootstrap_replicates",
)
REQUIRED_COLUMNS = (
    "panel",
    "backbone",
    "score",
    "policy",
    "description_pool",
    *NUMERIC_COLUMNS,
    "ci_method",
    "delta_definition",
    "source_file",
    "source_sha256",
)
EXPECTED_SETTINGS = {
    "score": "p_none",
    "policy": "test_id_oracle",
    "description_pool": "OUT",
    "n_rewrites": 8,
    "n_paired_seeds": 5,
    "ci_method": "paired_seed_bootstrap",
    "bootstrap_replicates": 5000,
    "delta_definition": "multi_phrase_minus_single_phrase",
}


def _fail(message: str) -> None:
    raise ValueError(f"Invalid matched-training data: {message}")


def _validate(data: pd.DataFrame) -> list[float]:
    missing = sorted(set(REQUIRED_COLUMNS) - set(data.columns))
    if missing:
        _fail(f"required columns are missing: {missing}")
    if len(data) != 24:
        _fail(f"expected all 24 preaggregated rows; found {len(data)}")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        _fail("required columns contain missing values")
    if set(data["panel"]) != set(PANEL_ORDER):
        _fail(f"expected panels {PANEL_ORDER}")
    if set(data["backbone"]) != set(BACKBONE_ORDER):
        _fail(f"expected backbones {BACKBONE_ORDER}")

    values = {}
    for column in NUMERIC_COLUMNS:
        try:
            values[column] = pd.to_numeric(data[column], errors="raise").to_numpy(
                dtype=float
            )
        except (TypeError, ValueError):
            _fail(f"{column} must be numeric")
        if not np.isfinite(values[column]).all():
            _fail(f"{column} contains non-finite values")

    for column, expected in EXPECTED_SETTINGS.items():
        observed = values[column] if column in values else data[column]
        if not (observed == expected).all():
            _fail(f"{column} must be {expected!r} in every row")
    if set(values["nominal_id_budget_pct"]) != set(NOMINAL_BUDGETS):
        _fail(f"expected nominal ID budgets {NOMINAL_BUDGETS}")
    if data.duplicated(["panel", "backbone", "nominal_id_budget_pct"]).any():
        _fail("duplicate panel/backbone/nominal ID budget observations")

    # With the domains, row count and unique keys checked above, every panel
    # contains all three backbones at all four matched operating points.
    nodes = []
    for nominal, expected_actual in zip(NOMINAL_BUDGETS, ACTUAL_ID_NODES):
        node = values["actual_id_false_reject_pct"][
            values["nominal_id_budget_pct"] == nominal
        ]
        if not np.isclose(node, expected_actual, rtol=0, atol=1e-10).all():
            _fail(
                f"nominal budget {nominal:g}% must share the actual ID node "
                f"{expected_actual:g}% across panels and backbones"
            )
        nodes.append(float(node[0]))

    for column in (
        "actual_id_false_reject_pct",
        "single_phrase_leakage_pct",
        "multi_phrase_leakage_pct",
    ):
        if not ((values[column] >= 0) & (values[column] <= 100)).all():
            _fail(f"{column} must be between 0 and 100")
    delta = values["delta_leakage_pp"]
    if not np.isclose(
        delta,
        values["multi_phrase_leakage_pct"] - values["single_phrase_leakage_pct"],
        rtol=0,
        atol=1e-10,
    ).all():
        _fail("delta_leakage_pp must equal Multi-phrase minus Single-phrase")
    lower, upper = values["ci95_lower_pp"], values["ci95_upper_pp"]
    if not ((lower <= delta) & (delta <= upper)).all():
        _fail("each confidence interval must contain its reported delta")
    for column, expected in (
        ("errorbar_lower_pp", delta - lower),
        ("errorbar_upper_pp", upper - delta),
    ):
        if not (values[column] >= 0).all():
            _fail(f"{column} must be nonnegative")
        if not np.isclose(values[column], expected, rtol=0, atol=1e-10).all():
            _fail(f"{column} disagrees with the supplied confidence interval")
    for column in ("source_file", "source_sha256"):
        if not data[column].map(lambda value: bool(str(value).strip())).all():
            _fail(f"{column} must not be empty")
    return sorted(nodes)


def load_matched_training_data(path: str | Path) -> dict[str, Any]:
    """Return all source rows unchanged, four actual-ID nodes, and provenance.

    ``data`` retains the CSV's column order, row order, values, and any extra
    columns.  ``nodes`` contains actual percentages rather than nominal budget
    labels.  The validation is strict: unexpected rows are rejected, not hidden
    by a filter.  Source JSON names and hashes are recorded as declarations.
    """
    source_path = Path(path).resolve()
    data = pd.read_csv(source_path)
    nodes = _validate(data)
    metadata: dict[str, Any] = {
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_rows": len(data),
        "plot_rows": len(data),
        "filter": dict(EXPECTED_SETTINGS),
        "panels": list(PANEL_ORDER),
        "backbones": list(BACKBONE_ORDER),
        "nominal_id_budgets_pct": list(NOMINAL_BUDGETS),
        "actual_id_nodes_pct": nodes,
        "delta_definition": EXPECTED_SETTINGS["delta_definition"],
        "ci_method": EXPECTED_SETTINGS["ci_method"],
        "confidence_level": 0.95,
        "bootstrap_replicates": EXPECTED_SETTINGS["bootstrap_replicates"],
        "n_paired_seeds": EXPECTED_SETTINGS["n_paired_seeds"],
        "n_rewrites": EXPECTED_SETTINGS["n_rewrites"],
        "aggregation": "none; all 24 preaggregated estimates and intervals are retained",
        "provenance": data[["source_file", "source_sha256"]]
        .drop_duplicates()
        .to_dict("records"),
        "provenance_check": (
            "The CSV itself is hashed. source_file and source_sha256 in its "
            "rows are supplied provenance declarations; original JSON and "
            "paired seed samples were not provided, so their contents and "
            "bootstrap intervals are not independently recomputed or verified."
        ),
    }
    return {"data": data, "nodes": nodes, "metadata": metadata}
