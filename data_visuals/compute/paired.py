"""Explicit pair identities, descriptive changes and requested uncertainty."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, t

from data_visuals.compute.distribution import _domain, _number, _ordered


def _input(df, mapping, *, order, kind="paired", summary="mean", ci_method=None,
           confidence=None, bandwidth="scott", density_range=None):
    if kind == "paired" and density_range is not None:
        raise ValueError("density_range is only supported by estimation, which displays a KDE.")
    if not isinstance(df, pd.DataFrame) or df.empty or not df.columns.is_unique:
        raise ValueError("Paired data must be a nonempty DataFrame with unique columns.")
    names = {}
    for field in ("pair", "x", "y", "group", "lower", "upper"):
        column = mapping.get(field)
        if field in {"group", "lower", "upper"} and column is None:
            continue
        if not isinstance(column, str) or not column or column not in df:
            raise ValueError(f"Paired {field} must name an existing column.")
        names[field] = column
    if len({names["pair"], names["x"], names["y"]}) != 3:
        raise ValueError("pair, x and y must use different columns.")
    if not all(_number(value) for value in df[names["y"]]):
        raise ValueError("Paired y values must be finite real numbers, without booleans or missing values.")
    levels = _domain(df[names["x"]], "x")
    if order is None or len(levels) != 2:
        raise ValueError("Paired charts require an explicit order of exactly two observed levels.")
    levels = _ordered(levels, order)
    if len(levels) != 2:
        raise ValueError("Paired order must contain exactly two observed levels.")
    _domain(df[names["pair"]], "pair")
    groups = _domain(df[names["group"]], "group") if "group" in names else [None]
    if kind == "estimation" and len(groups) != 1:
        raise ValueError("Estimation requires one group per panel; select or facet explicitly for an unambiguous linked difference scale.")
    keys = [names["pair"], names["x"]]
    if "group" in names:
        keys.insert(0, names["group"])
    if df.duplicated(keys).any():
        raise ValueError("Duplicate pair/group/level observations require explicit preprocessing; they are not averaged.")
    if summary is not None and summary != "mean":
        raise ValueError("Paired summary must be 'mean' or None.")
    if kind == "estimation" and summary != "mean":
        raise ValueError("Paired estimation currently estimates the mean difference; summary must be 'mean'.")
    if ci_method is not None and ci_method != "paired_t":
        raise ValueError("ci_method must be explicitly 'paired_t' or None.")
    if confidence is not None and (not _number(confidence) or not 0 < confidence < 1):
        raise ValueError("confidence must be an explicit finite number strictly between 0 and 1.")
    bounds = "lower" in names or "upper" in names
    if bounds and not {"lower", "upper"} <= names.keys():
        raise ValueError("Supplied intervals require both lower and upper columns.")
    if bounds and ci_method is not None:
        raise ValueError("Choose supplied lower/upper bounds or ci_method, not both.")
    if ci_method == "paired_t" and confidence is None:
        raise ValueError("paired_t requires an explicit confidence level.")
    if kind == "estimation" and not bounds and ci_method is None:
        raise ValueError("Estimation requires supplied lower/upper bounds or an explicit ci_method and confidence.")
    if not bounds and ci_method is None and confidence is not None:
        raise ValueError("confidence requires supplied intervals or an explicit ci_method.")
    if not (bandwidth == "scott" if isinstance(bandwidth, str) else _number(bandwidth) and bandwidth > 0):
        raise ValueError("bandwidth must be 'scott' or a finite positive Gaussian KDE factor.")
    cells = []
    for group in groups:
        cell = df.loc[df[names["group"]] == group] if "group" in names else df
        ids = _domain(cell[names["pair"]], "pair")
        ids = sorted(ids, key=lambda value: (type(value).__name__, value))
        indexed = cell.set_index([names["pair"], names["x"]])
        if len(cell) != len(ids) * 2:
            raise ValueError(f"Group {group!r} contains incomplete pairs; no observations are silently dropped.")
        first, second = [], []
        for pair_id in ids:
            try:
                first.append(float(indexed.loc[(pair_id, levels[0]), names["y"]]))
                second.append(float(indexed.loc[(pair_id, levels[1]), names["y"]]))
            except KeyError as exc:
                raise ValueError(f"Pair {pair_id!r} in group {group!r} is incomplete.") from exc
        first, second = np.asarray(first), np.asarray(second)
        with np.errstate(over="ignore", invalid="ignore"):
            differences = second - first
            mean_a, mean_b = float(first.mean()), float(second.mean())
            mean = float(differences.mean())
        if not np.isfinite(np.r_[differences, mean_a, mean_b, mean]).all():
            raise ValueError("Paired differences and means must remain finite; values are not silently rescaled.")
        lower = upper = None
        if bounds:
            endpoints = []
            for field in ("lower", "upper"):
                values = cell[names[field]].tolist()
                if not all(_number(value) for value in values) or len(set(values)) != 1:
                    raise ValueError(f"Supplied {field} must be one finite constant per group, repeated on its observation rows.")
                endpoints.append(float(values[0]))
            lower, upper = endpoints
            if not lower <= mean <= upper:
                raise ValueError("Supplied interval requires lower <= mean paired difference <= upper.")
        if ci_method == "paired_t":
            if len(ids) < 2:
                raise ValueError("paired_t requires at least two complete pairs.")
            with np.errstate(over="ignore", invalid="ignore"):
                half = t.ppf((1 + confidence) / 2, len(ids) - 1) * np.std(differences, ddof=1) / np.sqrt(len(ids))
                lower, upper = float(mean - half), float(mean + half)
            if not np.isfinite([lower, upper]).all():
                raise ValueError("Paired t interval must remain finite.")
        cells.append({"group": group, "ids": ids, "first": first.tolist(), "second": second.tolist(),
                      "differences": differences.tolist(), "mean_a": mean_a, "mean_b": mean_b,
                      "mean": mean, "lower": lower, "upper": upper, "n": len(ids)})
    return names, levels, groups, cells


def validate_paired(df, mapping, **options):
    try:
        _input(df, mapping, **options)
    except (ValueError, TypeError, OverflowError) as exc:
        return [str(exc)]
    return []


def compute_paired(df, mapping, *, order, kind="paired", summary="mean", ci_method=None,
                   confidence=None, bandwidth="scott", density_range=None):
    """Pair by declared keys; differences are exactly order[1] minus order[0]."""
    names, levels, groups, cells = _input(
        df, mapping, order=order, kind=kind, summary=summary, ci_method=ci_method,
        confidence=confidence, bandwidth=bandwidth, density_range=density_range)
    if kind not in {"paired", "estimation"}:
        raise ValueError("Unknown paired chart kind.")
    if kind == "estimation":
        for cell in cells:
            values = np.asarray(cell["differences"])
            with np.errstate(over="ignore", invalid="ignore"):
                spread = np.std(values, ddof=1) if len(values) > 1 else 0
            if len(values) < 2 or not np.isfinite(spread) or spread <= 0:
                raise ValueError("Estimation KDE requires at least two varying paired differences.")
            low, high = min(float(values.min()), 0.), max(float(values.max()), 0.)
            padding = max(.5, .12 * (high - low))
            limits = [low - padding, high + padding]
            if density_range is not None:
                if (not isinstance(density_range, (list, tuple)) or len(density_range) != 2
                        or not all(_number(value) for value in density_range)
                        or density_range[0] >= density_range[1]
                        or density_range[0] > low or density_range[1] < high):
                    raise ValueError("density_range must contain all paired differences and zero, without clipping observations.")
                limits = list(density_range)
            grid = np.linspace(*limits, 256)
            try:
                density = gaussian_kde(values, bw_method=bandwidth)(grid)
            except (ValueError, np.linalg.LinAlgError) as exc:
                raise ValueError("Cannot estimate Gaussian KDE of paired differences.") from exc
            if not np.isfinite(grid).all() or not np.isfinite(density).all() or density.max() <= 0:
                raise ValueError("Estimation density coordinates must remain finite.")
            cell.update(grid=grid.tolist(), density=density.tolist(),
                        profile=(density / density.max()).tolist())
    columns = list(dict.fromkeys(names.values()))
    return df[columns].copy(), {"paired": {"kind": kind, "levels": levels, "groups": groups,
                                 "cells": cells, "summary": summary, "ci_method":
                                 "supplied" if "lower" in names else ci_method,
                                 "confidence": float(confidence) if confidence is not None else None,
                                 "direction": "second - first",
                                 "bandwidth": bandwidth.item() if isinstance(bandwidth, np.generic) else bandwidth}}
