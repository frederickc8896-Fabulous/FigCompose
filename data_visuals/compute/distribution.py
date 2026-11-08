"""Validated distribution summaries; no colours, artists or display offsets."""
from __future__ import annotations

from collections.abc import Mapping
from numbers import Real

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde


def _number(value):
    return (isinstance(value, Real) and not isinstance(value, (bool, np.bool_))
            and np.isfinite(value))


def _domain(values, name):
    result = []
    for value in values:
        value = value.item() if isinstance(value, np.generic) else value
        if (not pd.api.types.is_scalar(value) or isinstance(value, (bool, np.bool_))
                or pd.isna(value) or isinstance(value, str) and not value.strip()):
            raise ValueError(f"{name} requires nonempty scalar categories, without missing values or booleans.")
        if isinstance(value, Real) and not _number(value):
            raise ValueError(f"{name} categories must remain finite.")
        if not isinstance(value, (str, int, float)):
            raise ValueError(f"{name} categories must be JSON scalar strings or finite numbers.")
        try:
            hash(value)
        except TypeError as exc:
            raise ValueError(f"{name} categories must be hashable scalars.") from exc
        if value not in result:
            result.append(value)
    return result


def _ordered(domain, order, name="order"):
    if order is None:
        return domain
    if not isinstance(order, (list, tuple)):
        raise ValueError(f"{name} must contain every category exactly once.")
    checked = _domain(order, name)
    if len(checked) != len(order) or len(checked) != len(domain) or set(checked) != set(domain):
        raise ValueError(f"{name} must contain every category exactly once.")
    return checked


def _input(df, mapping, *, bandwidth="scott", normalization="peak", order=None,
           horizontal=True, summary="median"):
    if not isinstance(df, pd.DataFrame) or df.empty or not df.columns.is_unique:
        raise ValueError("Distribution data must be a nonempty DataFrame with unique column names.")
    if not isinstance(mapping, Mapping):
        raise ValueError("Distribution mappings require x=category and y=value.")
    names = {}
    for field in ("x", "y", "group"):
        column = mapping.get(field)
        if field == "group" and column is None:
            continue
        if not isinstance(column, str) or not column or column not in df:
            raise ValueError(f"Distribution {field} must name an existing column.")
        names[field] = column
    if names["x"] == names["y"] or names.get("group") == names["y"]:
        raise ValueError("Distribution measurements and categories must use different columns.")
    if not (bandwidth == "scott" if isinstance(bandwidth, str) else _number(bandwidth) and bandwidth > 0):
        raise ValueError("bandwidth must be 'scott' or a finite positive Gaussian KDE factor.")
    if not isinstance(normalization, str) or normalization not in {"peak", "area"}:
        raise ValueError("normalization must be 'peak' or 'area'.")
    if not isinstance(horizontal, bool):
        raise ValueError("horizontal must be a boolean.")
    if summary is not None and summary != "median":
        raise ValueError("Distribution summary must be 'median' or None.")
    if not all(_number(value) for value in df[names["y"]]):
        raise ValueError("Distribution y values must be finite real numbers, without booleans or missing values.")
    categories = _ordered(_domain(df[names["x"]], "x"), order)
    groups = _domain(df[names["group"]], "group") if "group" in names else [None]
    cells = []
    for category in categories:
        for group in groups:
            selected = df[names["x"]] == category
            if "group" in names:
                selected &= df[names["group"]] == group
            values = df.loc[selected, names["y"]].to_numpy(dtype=float, copy=True)
            if not len(values):
                continue
            with np.errstate(over="ignore", invalid="ignore"):
                deviation = np.std(values, ddof=1) if len(values) > 1 else 0
            if len(values) < 2 or not np.isfinite(deviation) or deviation <= 0:
                raise ValueError(f"Distribution cell {category!r}/{group!r} needs at least two varying values for KDE.")
            cells.append((category, group, values))
    return names, categories, groups, cells


def validate_distribution(df, mapping, **options):
    """Validate every observation; neither aggregate nor drop input rows."""
    try:
        _input(df, mapping, **options)
    except (ValueError, TypeError, OverflowError) as exc:
        return [str(exc)]
    return []


def compute_distribution(df, mapping, *, kind="raincloud", bandwidth="scott",
                         normalization="peak", order=None, horizontal=True,
                         summary="median"):
    """Return raw observations and deterministic, JSON-safe density summaries.

    Gaussian KDE uses its declared factor. ``peak`` makes each layer equally
    tall; ``area`` uses one common density scale across all layers. Neither is
    an uncertainty interval or an observation count encoding.
    """
    names, categories, groups, cells = _input(
        df, mapping, bandwidth=bandwidth, normalization=normalization,
        order=order, horizontal=horizontal, summary=summary)
    if kind not in {"raincloud", "ridgeline"}:
        raise ValueError("Unknown distribution kind.")
    values = df[names["y"]].to_numpy(dtype=float)
    low, high = float(values.min()), float(values.max())
    with np.errstate(over="ignore", invalid="ignore"):
        padding = max(.5, .12 * (high - low))
        limits = np.asarray([low - padding, high + padding])
    if not np.isfinite(limits).all() or limits[0] >= limits[1]:
        raise ValueError("Distribution range is too large for finite density coordinates.")
    grid = np.linspace(*limits, 256)
    layers = []
    for category, group, observations in cells:
        try:
            density = gaussian_kde(observations, bw_method=bandwidth)(grid)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise ValueError(f"Cannot estimate Gaussian KDE for {category!r}/{group!r}.") from exc
        if not np.isfinite(density).all() or density.max() <= 0:
            raise ValueError("Gaussian KDE must produce finite positive density coordinates.")
        q1, median, q3 = np.quantile(observations, [.25, .5, .75])
        inside = observations[(observations >= q1 - 1.5 * (q3 - q1))
                              & (observations <= q3 + 1.5 * (q3 - q1))]
        layers.append({"category": category, "group": group,
                       "values": observations.tolist(), "grid": grid.tolist(),
                       "density": density.tolist(), "n": len(observations),
                       "q1": float(q1), "median": float(median), "q3": float(q3),
                       "whislo": float(inside.min()), "whishi": float(inside.max())})
    common_peak = max(max(layer["density"]) for layer in layers)
    for layer in layers:
        denominator = max(layer["density"]) if normalization == "peak" else common_peak
        layer["profile"] = (np.asarray(layer["density"]) / denominator).tolist()
    columns = list(dict.fromkeys(names.values()))
    return df[columns].copy(), {"distribution": {
        "kind": kind, "categories": categories, "groups": groups, "layers": layers,
        "value_limits": limits.tolist(), "bandwidth": bandwidth.item() if isinstance(bandwidth, np.generic) else bandwidth,
        "normalization": normalization, "kernel": "gaussian", "summary": summary}}
