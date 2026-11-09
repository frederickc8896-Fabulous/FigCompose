"""Ward clustering of an explicitly scaled, complete wide numerical matrix."""
from __future__ import annotations

import math
from numbers import Integral, Real
from collections.abc import Mapping

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, leaves_list, linkage


def _real(value):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _identifier(value):
    if isinstance(value, np.generic):
        value = value.item()
    return (isinstance(value, str) and bool(value.strip()) or
            isinstance(value, (int, float)) and not isinstance(value, bool) and _real(value))


def validate_clustered_heatmap_input(df, mapping, *, value_range=(-1, 1),
                                     n_clusters=4, label_every=2):
    errors = []
    valid_range = (isinstance(value_range, (list, tuple)) and len(value_range) == 2
                   and all(_real(value) for value in value_range))
    if (not valid_range or not float(value_range[0]) < float(value_range[1])
            or not math.isfinite(float(value_range[1]) - float(value_range[0]))):
        errors.append("[clustered_heatmap] value_range must contain two increasing finite real values.")
    if not isinstance(n_clusters, Integral) or isinstance(n_clusters, (bool, np.bool_)) or n_clusters < 1:
        errors.append("[clustered_heatmap] n_clusters must be a positive integer.")
    if not isinstance(label_every, Integral) or isinstance(label_every, (bool, np.bool_)) or label_every < 1:
        errors.append("[clustered_heatmap] label_every must be a positive integer.")
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return [*errors, "[clustered_heatmap] Supply a DataFrame with unique column names."]
    if not isinstance(mapping, Mapping):
        return [*errors, "[clustered_heatmap] Map sample and traits to matrix columns."]
    sample, traits = mapping.get("sample"), mapping.get("traits")
    if not isinstance(sample, str) or not sample or sample not in df:
        errors.append("[clustered_heatmap] sample must name an existing ID column.")
    valid_traits = (isinstance(traits, (list, tuple)) and len(traits) >= 1
                    and all(isinstance(name, str) and bool(name) and name in df for name in traits))
    if not valid_traits:
        return [*errors, "[clustered_heatmap] traits must list existing numeric columns in radial order."]
    if len(set(traits)) != len(traits) or sample in traits:
        errors.append("[clustered_heatmap] sample and all traits must map to distinct columns.")
    if len(df) < 2:
        errors.append("[clustered_heatmap] At least two sample profiles are required.")
    if isinstance(n_clusters, Integral) and n_clusters > len(df):
        errors.append("[clustered_heatmap] n_clusters cannot exceed the number of samples.")
    if isinstance(sample, str) and sample in df:
        if not all(_identifier(value) for value in df[sample]) or df[sample].duplicated().any():
            errors.append("[clustered_heatmap] Sample IDs must be nonempty unique strings or finite numeric scalars.")
    values = df[list(traits)].to_numpy(dtype=object).ravel()
    if not all(_real(value) for value in values):
        errors.append("[clustered_heatmap] Trait values must be finite real numbers, excluding booleans.")
    elif valid_range and float(value_range[0]) < float(value_range[1]):
        low, high = map(float, value_range)
        if any(float(value) < low or float(value) > high for value in values):
            errors.append("[clustered_heatmap] Trait values must lie within the explicit value_range.")
    return errors


def compute_clustered_heatmap(df, mapping, *, value_range=(-1, 1), n_clusters=4,
                              label_every=2):
    """Return unchanged observations, genuine Ward distances and JSON-safe summaries.

    Input row order resolves tied observations; trait order is exactly the declared
    list. There is no implicit z-score, imputation or per-trait rescaling.
    """
    errors = validate_clustered_heatmap_input(df, mapping, value_range=value_range,
                                             n_clusters=n_clusters, label_every=label_every)
    if errors:
        raise ValueError("\n".join(errors))
    sample, traits = mapping["sample"], list(mapping["traits"])
    values = df[traits].to_numpy(dtype=float)
    try:
        tree = linkage(values, method="ward", metric="euclidean", optimal_ordering=True)
    except (ValueError, FloatingPointError, OverflowError) as exc:
        raise ValueError("[clustered_heatmap] Ward distances must remain finite; rescale the input unit explicitly.") from exc
    if not np.isfinite(tree).all():
        raise ValueError("[clustered_heatmap] Ward distances must remain finite; rescale the input unit explicitly.")
    if float(tree[:, 2].max()) <= 0:
        raise ValueError("[clustered_heatmap] At least two distinct profiles are needed for the radial Ward tree.")
    clusters = fcluster(tree, t=int(n_clusters), criterion="maxclust").astype(int)
    identifiers = [value.item() if isinstance(value, np.generic) else value for value in df[sample]]
    derived = {"clustered_heatmap": {
        "matrix": values.tolist(), "tree": tree.tolist(), "identifiers": identifiers,
        "traits": traits, "leaf_order": leaves_list(tree).astype(int).tolist(),
        "cluster_ids": clusters.tolist(), "cluster_count": int(clusters.max()),
        "sample_count": len(df), "trait_count": len(traits),
        "value_range": list(map(float, value_range)),
        "method": "ward", "metric": "euclidean", "optimal_ordering": True,
    }}
    return df[[sample, *traits]].reset_index(drop=True).copy(), derived
