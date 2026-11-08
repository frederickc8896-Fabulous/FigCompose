"""Validated undirected edge weights and explicit additive aggregation.

This module owns graph/weight semantics. Angular allocation and labels belong
to the renderer; no absent edge, isolated node or minimum weight is invented.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Any, Mapping

import numpy as np
import pandas as pd


def _plain(value):
    return value.item() if isinstance(value, np.generic) else value


def _node(value):
    value = _plain(value)
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    # Node identities remain JSON scalar IDs rather than arbitrary Real
    # implementations (for example Fraction, which JSON cannot serialize).
    return isinstance(value, (int, float)) and _finite(value)


def _finite(value):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def node_order(values):
    """A deterministic order independent of row order and edge orientation."""
    unique = list(dict.fromkeys(_plain(value) for value in values))
    try:
        return sorted(unique)
    except TypeError:
        return sorted(unique, key=lambda value: (type(value).__name__, str(value)))


def _sum(values):
    numbers = [float(value) for value in values]
    scale = max(numbers)
    result = math.fsum(value / scale for value in numbers) * scale
    if not math.isfinite(result):
        raise ValueError("[chord] Weight totals must remain finite; rescale the weight unit explicitly.")
    return result


def validate_chord_input(df, mapping: Mapping[str, Any], *, order=None,
                         aggregate=None, summary=False, ticks=True):
    errors = []
    if aggregate is not None and not (isinstance(aggregate, str) and aggregate == "sum"):
        errors.append("[chord] aggregate must be None or 'sum'.")
    if not isinstance(summary, bool) or not isinstance(ticks, bool):
        errors.append("[chord] summary and ticks must be booleans.")
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return [*errors, "[chord] Data must be a DataFrame with unique column names."]
    if not isinstance(mapping, Mapping):
        return [*errors, "[chord] Map source, target and value to three distinct columns."]
    columns = []
    for field in ("source", "target", "value"):
        column = mapping.get(field)
        if not isinstance(column, str) or not column or column not in df:
            errors.append(f"[chord] {field} must name an existing single column.")
        else:
            columns.append(column)
    if len(columns) != 3:
        return errors
    if len(set(columns)) != 3:
        return [*errors, "[chord] source, target and value must map to distinct columns."]
    if df.empty:
        return [*errors, "[chord] Supply at least one undirected edge."]
    source, target, value = columns
    labels = df[source].tolist() + df[target].tolist()
    if not all(_node(item) for item in labels):
        return [*errors, "[chord] Node IDs must be nonempty strings or finite real scalars, excluding booleans."]
    actual = node_order(labels)
    if len(actual) < 2:
        errors.append("[chord] At least two distinct nodes are required.")
    if order is not None:
        valid = isinstance(order, (list, tuple)) and all(_node(item) for item in order)
        if valid:
            valid = len(order) == len(actual) and len(set(order)) == len(order) and set(order) == set(actual)
        if not valid:
            errors.append("[chord] order must contain every observed node exactly once.")
    pairs = set()
    for first, second in df[[source, target]].itertuples(index=False, name=None):
        if first == second:
            errors.append("[chord] Self-links are not supported.")
            break
        pair = frozenset((first, second))
        if pair in pairs and aggregate is None:
            errors.append("[chord] Duplicate undirected pairs require aggregate='sum'.")
            break
        pairs.add(pair)
    numbers = df[value].tolist()
    if not all(_finite(item) and float(item) > 0 for item in numbers):
        errors.append("[chord] Every edge weight must be a finite positive real number.")
    return errors


def compute_chord(df, mapping, *, order=None, aggregate=None, summary=False, ticks=True):
    """Return canonical edges and JSON-safe graph summaries, without geometry."""
    errors = validate_chord_input(df, mapping, order=order, aggregate=aggregate,
                                  summary=summary, ticks=ticks)
    if errors:
        raise ValueError("\n".join(errors))
    source, target, value = (mapping[field] for field in ("source", "target", "value"))
    nodes = ([_plain(item) for item in order] if order is not None else
             node_order(df[source].tolist() + df[target].tolist()))
    ranks = {name: index for index, name in enumerate(nodes)}
    weights = {}
    for first, second, weight in df[[source, target, value]].itertuples(index=False, name=None):
        first, second = _plain(first), _plain(second)
        pair = (first, second) if ranks[first] < ranks[second] else (second, first)
        weights.setdefault(pair, []).append(float(weight))
    rows = [(first, second, _sum(values)) for (first, second), values in
            sorted(weights.items(), key=lambda item: (ranks[item[0][0]], ranks[item[0][1]]))]
    result = pd.DataFrame(rows, columns=[source, target, value])
    totals = {name: [] for name in nodes}
    for first, second, weight in rows:
        totals[first].append(weight)
        totals[second].append(weight)
    total = _sum([row[2] for row in rows])
    incident = total * 2
    if not math.isfinite(incident):
        raise ValueError("[chord] Incident weight total must remain finite; rescale the weight unit explicitly.")
    derived = {"chord": {
        "node_order": nodes,
        "nodes": [{"id": name, "total": _sum(totals[name])} for name in nodes],
        "node_count": len(nodes), "edge_count": len(rows),
        "total_weight": total, "incident_total": incident,
    }}
    return result, derived
