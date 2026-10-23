"""Validated, seed-balanced summaries for the rejection-description figure.

This module preserves every qualifying observation.  Individual description
points average five seeds; the overall rewrite point first averages all eight
rewrites within each seed, then averages the resulting five seed means.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


BACKBONE_ORDER = ("xsmall", "small", "roberta")
TRAINING_ORDER = ("Single-phrase", "Multi-phrase")
METRICS = ("id_false_reject_pct", "near_leak_pct", "near_auroc")
KEYS = ("backbone", "training", "seed")
REQUIRED_COLUMNS = (
    *KEYS,
    "description_id",
    "description_text",
    "pool",
    "score",
    "policy",
    "reference_budget",
    *METRICS,
    "tau_reference",
)


def _fail(message: str) -> None:
    raise ValueError(f"Invalid rejection-rewrite data: {message}")


def _validate(filtered: pd.DataFrame) -> tuple[pd.DataFrame, list[Any]]:
    if len(filtered) != 270:
        _fail(f"expected 270 qualifying rows; found {len(filtered)}")
    if filtered.isna().any().any():
        columns = filtered.columns[filtered.isna().any()].tolist()
        _fail(f"missing values in columns {columns}")
    if set(filtered["backbone"]) != set(BACKBONE_ORDER):
        _fail(f"expected backbones {BACKBONE_ORDER}")
    if set(filtered["training"]) != set(TRAINING_ORDER):
        _fail(f"expected training modes {TRAINING_ORDER}")
    if filtered.duplicated([*KEYS, "description_id"]).any():
        _fail("duplicate backbone/training/seed/description_id observations")

    for column in (*METRICS, "tau_reference"):
        try:
            values = pd.to_numeric(filtered[column], errors="raise").to_numpy(dtype=float)
        except (ValueError, TypeError):
            _fail(f"{column} must be numeric")
        if not np.isfinite(values).all():
            _fail(f"{column} contains non-finite values")
        if column.endswith("_pct") and not ((values >= 0) & (values <= 100)).all():
            _fail(f"{column} must be between 0 and 100")
        if column in ("near_auroc", "tau_reference") and not (
            (values >= 0) & (values <= 1)
        ).all():
            _fail(f"{column} must be between 0 and 1")

    # The first occurrence in the CSV defines the numbering used in every panel.
    descriptions = filtered[
        ["description_id", "description_text", "pool"]
    ].drop_duplicates()
    if descriptions["description_id"].duplicated().any():
        _fail("a description_id has inconsistent text or pool")
    if descriptions["description_text"].duplicated().any():
        _fail("description texts must be distinct")
    if any(not str(text).strip() for text in descriptions["description_text"]):
        _fail("description texts must not be empty")
    reference = descriptions.loc[descriptions["pool"] == "REF"]
    rewrites = descriptions.loc[descriptions["pool"] == "OUT"]
    if len(reference) != 1 or len(rewrites) != 8:
        _fail("expected one reference description and eight distinct OUT rewrites")

    seeds = filtered["seed"].drop_duplicates().tolist()
    if len(seeds) != 5:
        _fail(f"expected five shared seeds; found {len(seeds)}")
    expected_ids = set(descriptions["description_id"])
    for backbone in BACKBONE_ORDER:
        for training in TRAINING_ORDER:
            panel = filtered.loc[
                (filtered["backbone"] == backbone)
                & (filtered["training"] == training)
            ]
            if set(panel["seed"]) != set(seeds):
                _fail(f"{backbone}/{training} does not share all five seeds")
            for seed in seeds:
                subset = panel.loc[panel["seed"] == seed]
                if len(subset) != 9 or set(subset["description_id"]) != expected_ids:
                    _fail(f"{backbone}/{training}/seed={seed} lacks the full nine descriptions")
                ref_threshold = float(subset.loc[subset["pool"] == "REF", "tau_reference"].iloc[0])
                if not np.isclose(
                    subset["tau_reference"].to_numpy(dtype=float),
                    ref_threshold,
                    rtol=1e-12,
                    atol=1e-15,
                ).all():
                    _fail(
                        f"{backbone}/{training}/seed={seed} does not reuse the reference threshold"
                    )
                # Some exports carry a checkpoint identifier; validate it when
                # present.  The supplied CSV identifies models by the three KEYS.
                for column in ("checkpoint", "checkpoint_id", "checkpoint_path"):
                    if column in subset and subset[column].nunique() != 1:
                        _fail(f"{backbone}/{training}/seed={seed} changes {column}")
    return descriptions, seeds


def load_and_summarize(path: str | Path) -> dict[str, Any]:
    """Return validated source rows, 60 plot points, seed means, and mapping.

    Dictionary keys are ``filtered``, ``points``, ``seed_means``, ``mapping``,
    and JSON-serializable ``metadata``.  Point ``kind`` is one of ``reference``,
    ``rewrite``, or ``mean``.  ``rewrite_number`` is nullable: 1--8 for
    individual rewrites and missing for reference/overall-mean points.
    """
    source_path = Path(path).resolve()
    raw = pd.read_csv(source_path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    if missing:
        _fail(f"required columns are missing: {missing}")
    budget = pd.to_numeric(raw["reference_budget"], errors="coerce")
    selected = (
        raw["score"].eq("p_none")
        & raw["policy"].eq("fixed")
        & np.isclose(budget.to_numpy(dtype=float), 0.05, rtol=0, atol=1e-12)
        & raw["pool"].isin(("REF", "OUT"))
    )
    filtered = raw.loc[selected].copy().reset_index(drop=True)
    descriptions, seeds = _validate(filtered)
    for column in (*METRICS, "tau_reference"):
        filtered[column] = pd.to_numeric(filtered[column], errors="raise")

    mapping = descriptions.loc[
        descriptions["pool"] == "OUT", ["description_id", "description_text"]
    ].reset_index(drop=True)
    mapping.insert(0, "rewrite_number", range(1, len(mapping) + 1))
    rewrite_numbers = mapping.set_index("description_id")["rewrite_number"].to_dict()

    seed_means = (
        filtered.loc[filtered["pool"] == "OUT"]
        .groupby(list(KEYS), sort=False, as_index=False)[list(METRICS)]
        .mean()
    )
    seed_means["n_descriptions"] = 8

    points: list[dict[str, Any]] = []
    for backbone in BACKBONE_ORDER:
        for training in TRAINING_ORDER:
            panel = filtered.loc[
                (filtered["backbone"] == backbone)
                & (filtered["training"] == training)
            ]
            for description in descriptions.to_dict("records"):
                subset = panel.loc[
                    panel["description_id"] == description["description_id"]
                ]
                point = {
                    "backbone": backbone,
                    "training": training,
                    **description,
                    "kind": "reference" if description["pool"] == "REF" else "rewrite",
                    "rewrite_number": rewrite_numbers.get(description["description_id"]),
                    **subset[list(METRICS)].mean().to_dict(),
                    "n_seeds": 5,
                    "n_descriptions": 1,
                }
                points.append(point)
            panel_seed_means = seed_means.loc[
                (seed_means["backbone"] == backbone)
                & (seed_means["training"] == training)
            ]
            points.append(
                {
                    "backbone": backbone,
                    "training": training,
                    "description_id": "MEAN_rewrites",
                    "description_text": "Mean over rewrites",
                    "pool": "OUT",
                    "kind": "mean",
                    "rewrite_number": None,
                    **panel_seed_means[list(METRICS)].mean().to_dict(),
                    "n_seeds": 5,
                    "n_descriptions": 8,
                }
            )
    point_frame = pd.DataFrame(points)
    point_frame["rewrite_number"] = pd.array(
        point_frame["rewrite_number"], dtype="Int64"
    )
    provenance_columns = [
        name for name in ("source_file", "source_sha256") if name in filtered
    ]
    metadata: dict[str, Any] = {
        "source_path": str(source_path),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "source_rows": len(raw),
        "filtered_rows": len(filtered),
        "filter": {
            "score": "p_none",
            "policy": "fixed",
            "reference_budget": 0.05,
            "pool": ["REF", "OUT"],
        },
        "backbones": list(BACKBONE_ORDER),
        "training_modes": list(TRAINING_ORDER),
        "seeds": [seed.item() if hasattr(seed, "item") else seed for seed in seeds],
        "reference_descriptions": 1,
        "rewrite_descriptions": 8,
        "panels": 6,
        "plot_points": len(point_frame),
        "seed_rewrite_means": len(seed_means),
        "aggregation": "description: mean over five seeds; rewrite overall: mean of eight rewrites within each seed, then mean over five seeds",
        "threshold_check": "all eight rewrites reuse the REF tau_reference within each backbone/training/seed",
        "checkpoint_check": (
            "Explicit checkpoint identifiers checked where present; supplied CSV groups models by backbone/training/seed and does not include checkpoint IDs."
        ),
        "provenance": filtered[provenance_columns].drop_duplicates().to_dict("records")
        if provenance_columns
        else [],
    }
    return {
        "filtered": filtered,
        "points": point_frame,
        "seed_means": seed_means,
        "mapping": mapping,
        "metadata": metadata,
    }
