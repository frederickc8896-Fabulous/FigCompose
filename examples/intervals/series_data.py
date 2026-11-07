"""Validate paired observations and prepare statistics for the visual series.

All calculations happen before rendering. The views use the same observations;
KDEs describe their distribution and are not confidence intervals for the mean.
The supplied paired-t estimates are checked, then retained without alteration.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, t


PAIRED_COLUMNS = (
    "dataset", "condition", "paired_run", "method_a_pct", "method_b_pct",
    "paired_difference_pp",
)
ESTIMATE_COLUMNS = (
    "dataset", "condition", "n_pairs", "mean_difference_pp",
    "ci95_lower_pp", "ci95_upper_pp",
)
TOLERANCE = 1e-8


def _read(path, required, kind):
    frame = pd.read_csv(Path(path), keep_default_na=False)
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"{kind} is missing columns: {', '.join(sorted(missing))}.")
    if frame.empty:
        raise ValueError(f"{kind} must contain observations.")
    if any(not isinstance(value, str) or not value.strip() for value in frame["dataset"]):
        raise ValueError(f"{kind}.dataset must contain nonempty group names.")
    for column in required:
        if column != "dataset":
            _numeric(frame, column, kind)
    return frame


def _numeric(frame, column, kind):
    if any(isinstance(value, (bool, np.bool_)) for value in frame[column]):
        raise ValueError(f"{kind}.{column} must contain finite real numbers, not booleans.")
    try:
        numeric = pd.to_numeric(frame[column], errors="raise")
        values = numeric.to_numpy(dtype=float)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{kind}.{column} must contain finite real numbers.") from exc
    if not np.isfinite(values).all():
        raise ValueError(f"{kind}.{column} must contain finite real numbers.")
    frame[column] = numeric


def _limits(values):
    """A common displayed difference range, including the meaningful zero."""
    low, high = min(float(np.min(values)), 0.0), max(float(np.max(values)), 0.0)
    padding = max(.5, .12 * (high - low))
    return low - padding, high + padding


def _density(values, limits, label):
    if len(values) < 2 or not np.isfinite(np.std(values, ddof=1)) or np.std(values, ddof=1) <= 0:
        raise ValueError(f"{label}: a density needs at least two varying paired differences.")
    try:
        estimator = gaussian_kde(values, bw_method="scott")
        grid = np.linspace(*limits, 256)
        density = estimator(grid)
    except (ValueError, np.linalg.LinAlgError) as exc:
        raise ValueError(f"{label}: cannot estimate a density from the paired differences.") from exc
    if not np.isfinite(density).all():
        raise ValueError(f"{label}: the estimated density must be finite.")
    return grid, density


def _box_summary(values):
    q1, median, q3 = np.quantile(values, (.25, .5, .75))
    iqr = q3 - q1
    inside = values[(values >= q1 - 1.5 * iqr) & (values <= q3 + 1.5 * iqr)]
    low, high = float(inside.min()), float(inside.max())
    return {"q1": float(q1), "median": float(median), "q3": float(q3),
            "whisker_low": low, "whisker_high": high, "whislo": low, "whishi": high,
            "outliers": values[(values < low) | (values > high)].copy(), "n": len(values)}


def _verify_estimates(paired, summary):
    keys = ["dataset", "condition"]
    if summary.duplicated(keys).any():
        raise ValueError("Estimates must have one row per dataset and condition.")
    observed = set(paired[keys].itertuples(index=False, name=None))
    supplied = set(summary[keys].itertuples(index=False, name=None))
    if observed != supplied:
        raise ValueError("Estimates must match every observed dataset/condition, without extra cells.")
    for optional in ("sd_difference_pp", "se_mean_difference_pp"):
        if optional in summary:
            _numeric(summary, optional, "Estimates")
    lookup = summary.set_index(keys)
    for key, cell in paired.groupby(keys, sort=False):
        values = cell["difference_pp"].to_numpy(dtype=float)
        n = len(values)
        if n < 2:
            raise ValueError(f"{key}: at least two paired observations are required.")
        with np.errstate(over="ignore", invalid="ignore"):
            mean = float(values.mean())
            sd = float(values.std(ddof=1))
            se = sd / np.sqrt(n)
            half = float(t.ppf(.975, n - 1) * se)
        expected = {"mean_difference_pp": mean, "sd_difference_pp": sd,
                    "se_mean_difference_pp": se, "ci95_lower_pp": mean - half,
                    "ci95_upper_pp": mean + half}
        if not np.isfinite(list(expected.values())).all():
            raise ValueError(f"{key}: paired mean and interval calculations must remain finite.")
        stored = lookup.loc[key]
        if stored["n_pairs"] != n:
            raise ValueError(f"{key}: stored n_pairs does not match the paired observations.")
        for column, expected_value in expected.items():
            if column in summary and not np.isclose(stored[column], expected_value, rtol=0, atol=TOLERANCE):
                raise ValueError(f"{key}: stored {column} disagrees with the paired t calculation.")


def prepare_series(paired_path, estimates_path, *, condition=4, ridge_dataset=None):
    """Return detached inputs for native and custom views of paired differences.

    ``condition`` selects one condition for detailed distribution and paired
    views. The forest overview retains every estimate; the ridge view retains
    every condition from one named dataset. CSV values are never overwritten.
    """
    paired = _read(paired_path, PAIRED_COLUMNS, "Paired data")
    summary = _read(estimates_path, ESTIMATE_COLUMNS, "Estimates")
    if paired.duplicated(["dataset", "condition", "paired_run"]).any():
        raise ValueError("Paired data must have unique dataset/condition/paired_run keys.")
    with np.errstate(over="ignore", invalid="ignore"):
        differences = paired["method_b_pct"].to_numpy(dtype=float) - paired["method_a_pct"].to_numpy(dtype=float)
    if not np.isfinite(differences).all():
        raise ValueError("B - A must produce finite paired differences.")
    if not np.allclose(differences, paired["paired_difference_pp"], rtol=0, atol=TOLERANCE):
        raise ValueError("paired_difference_pp must equal method_b_pct - method_a_pct.")
    paired["difference_pp"] = differences
    _verify_estimates(paired, summary)
    names = tuple(paired["dataset"].drop_duplicates().tolist())
    conditions = tuple(paired["condition"].drop_duplicates().tolist())
    if isinstance(condition, (bool, np.bool_)) or condition not in conditions:
        raise ValueError(f"Selected condition must be one of {conditions!r}.")
    ridge_dataset = names[min(1, len(names) - 1)] if ridge_dataset is None else ridge_dataset
    if ridge_dataset not in names:
        raise ValueError(f"Selected ridge dataset must be one of {names!r}.")
    focus = paired.loc[paired["condition"] == condition].copy()
    if set(focus["dataset"]) != set(names):
        raise ValueError("Every dataset must have paired observations at the selected condition.")
    groups, paired_values, means = {}, {}, {}
    for name in names:
        cell = focus.loc[focus["dataset"] == name].sort_values("paired_run", kind="stable")
        groups[name] = cell["difference_pp"].to_numpy(dtype=float, copy=True)
        paired_values[name] = tuple(cell[column].to_numpy(copy=True)
                                    for column in ("method_a_pct", "method_b_pct", "paired_run"))
        means[name] = (float(cell["method_a_pct"].mean()), float(cell["method_b_pct"].mean()))
    ridge = {}
    for value in conditions:
        cell = paired.loc[(paired["dataset"] == ridge_dataset) & (paired["condition"] == value)]
        if cell.empty:
            raise ValueError("The selected ridge dataset must include every displayed condition.")
        ridge[value] = cell.sort_values("paired_run", kind="stable")["difference_pp"].to_numpy(dtype=float, copy=True)
    focus_limits = _limits(np.concatenate(list(groups.values())))
    ridge_limits = _limits(np.concatenate(list(ridge.values())))
    density = {name: _density(values, focus_limits, f"{name}, condition {condition}")
               for name, values in groups.items()}
    ridge_density = {value: _density(values, ridge_limits, f"{ridge_dataset}, condition {value}")
                     for value, values in ridge.items()}
    selected = summary.loc[summary["condition"] == condition].set_index("dataset")
    mean_ci = {name: (float(selected.loc[name, "mean_difference_pp"]),
                      float(selected.loc[name, "ci95_lower_pp"]),
                      float(selected.loc[name, "ci95_upper_pp"]),
                      int(selected.loc[name, "n_pairs"])) for name in names}
    observations = paired.copy()
    observations["record_type"] = "observation"
    estimates = summary.copy()
    estimates["record_type"] = "estimate"
    estimates["difference_pp"] = estimates["mean_difference_pp"]
    frame = pd.concat((observations, estimates), ignore_index=True, sort=False)
    return {"names": names, "conditions": conditions, "condition": condition,
            "ridge_dataset": ridge_dataset, "paired": paired, "focus": focus,
            "summary": summary, "frame": frame, "groups": groups, "ridge": ridge,
            "density": density, "ridge_density": ridge_density,
            "focus_limits": focus_limits, "ridge_limits": ridge_limits,
            "mean_ci": mean_ci, "paired_values": paired_values, "means": means,
            "box_summaries": {name: _box_summary(values) for name, values in groups.items()}}
