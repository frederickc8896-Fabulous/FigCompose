"""Validate aligned cohort tracks and compute their descriptive summaries."""
from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real

import numpy as np
import pandas as pd


def _plain(value):
    return value.item() if isinstance(value, np.generic) else value


def _label(value):
    value = _plain(value)
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except (ValueError, OverflowError):
        return False


def _number(value):
    try:
        return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _ordered(values):
    values = list(dict.fromkeys(_plain(value) for value in values))
    try:
        return sorted(values)
    except TypeError:
        return sorted(values, key=lambda value: (type(value).__name__, str(value)))


def validate_participant_tracks(df, mapping, *, numeric_ranges=None,
                                category_orders=None, order_by=None, numeric_ticks=None, **options):
    errors = []
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return ["[participant_tracks] Data must have unique column names."]
    if not isinstance(mapping, Mapping):
        return ["[participant_tracks] Map id, categorical and numeric columns."]
    group = mapping.get("group")
    if group is not None and (not isinstance(group, str) or not group.strip()):
        errors.append("[participant_tracks] group must be a nonempty color-domain name.")
    identifier = mapping.get("id")
    categorical, numeric = mapping.get("categorical"), mapping.get("numeric")
    if not isinstance(identifier, str) or identifier not in df:
        errors.append("[participant_tracks] id must name an existing column.")
    for name, columns, maximum in (("categorical", categorical, 3), ("numeric", numeric, 2)):
        if (not isinstance(columns, (list, tuple)) or not 1 <= len(columns) <= maximum
                or any(not isinstance(column, str) or column not in df for column in columns)):
            errors.append(f"[participant_tracks] {name} must list 1–{maximum} existing columns.")
    if errors:
        return errors
    columns = [identifier, *categorical, *numeric]
    if len(set(columns)) != len(columns):
        return ["[participant_tracks] The ID and track columns must be distinct."]
    if len(df) < 3:
        return ["[participant_tracks] Supply at least three participants."]
    if not all(_label(value) for value in df[identifier]) or df[identifier].duplicated().any():
        errors.append("[participant_tracks] IDs must be nonempty JSON scalars and unique.")
    if not isinstance(numeric_ranges, Mapping) or set(numeric_ranges) != set(numeric):
        errors.append("[participant_tracks] numeric_ranges must give an explicit [low, high] for every numeric track.")
    else:
        for column in numeric:
            limits = numeric_ranges[column]
            if (not isinstance(limits, (list, tuple)) or len(limits) != 2
                    or not all(_number(value) for value in limits) or limits[0] >= limits[1]
                    or not math.isfinite(float(limits[1]) - float(limits[0]))
                    or float(limits[1]) - float(limits[0]) <= 0):
                errors.append(f"[participant_tracks] The range for {column!r} needs finite endpoints and a finite positive span; rescale the unit explicitly.")
                continue
            values = df[column].tolist()
            if not all(_number(value) and limits[0] <= value <= limits[1] for value in values):
                errors.append(f"[participant_tracks] {column!r} values must be finite real numbers within the explicit range.")
    if numeric_ticks is not None:
        if not isinstance(numeric_ticks, Mapping) or not set(numeric_ticks).issubset(numeric):
            errors.append("[participant_tracks] numeric_ticks may name only numeric tracks.")
        else:
            for column, ticks in numeric_ticks.items():
                limits = numeric_ranges.get(column) if isinstance(numeric_ranges, Mapping) else None
                if (not isinstance(ticks, (list, tuple)) or not ticks or not all(_number(value) for value in ticks)
                        or len(set(ticks)) != len(ticks) or any(left >= right for left, right in zip(ticks, ticks[1:]))
                        or (isinstance(limits, (list, tuple)) and len(limits) == 2
                            and all(_number(value) for value in limits)
                            and any(value < limits[0] or value > limits[1] for value in ticks))):
                    errors.append(f"[participant_tracks] Ticks for {column!r} must increase within its explicit range.")
    if category_orders is not None and (not isinstance(category_orders, Mapping)
                                         or not set(category_orders).issubset(categorical)):
        errors.append("[participant_tracks] category_orders may name only categorical tracks.")
        category_orders = None
    for column in categorical:
        values = df[column].tolist()
        if not all(_label(value) for value in values):
            errors.append(f"[participant_tracks] {column!r} categories must be nonempty JSON scalars.")
            continue
        order = (category_orders or {}).get(column)
        if order is not None:
            if (not isinstance(order, (list, tuple)) or not all(_label(value) for value in order)
                    or len(set(order)) != len(order) or not set(values).issubset(order)):
                errors.append(f"[participant_tracks] The category order for {column!r} must uniquely cover observed categories.")
    if order_by is not None and (not isinstance(order_by, str) or order_by not in numeric):
        errors.append("[participant_tracks] order_by must name a numeric track, or be None for ID order.")
    for name in ("track_labels", "numeric_colors"):
        value = options.get(name)
        allowed = set(categorical) | set(numeric) if name == "track_labels" else set(numeric)
        if value is not None and (not isinstance(value, Mapping) or not set(value).issubset(allowed)
                                  or not all(isinstance(item, str) and item for item in value.values())):
            errors.append(f"[participant_tracks] {name} must map track columns to nonempty strings.")
    for name in ("note", "center_label", "center_note", "order_label", "center_color", "accent_color"):
        value = options.get(name)
        if value is not None and not isinstance(value, str):
            errors.append(f"[participant_tracks] {name} must be a string or None.")
    return errors


def compute_participant_tracks(df, mapping, *, numeric_ranges=None,
                               category_orders=None, order_by=None, numeric_ticks=None, **options):
    """Preserve one row per person; derive distributions without recoding values."""
    errors = validate_participant_tracks(df, mapping, numeric_ranges=numeric_ranges,
                                         category_orders=category_orders, order_by=order_by,
                                         numeric_ticks=numeric_ticks, **options)
    if errors:
        raise ValueError("\n".join(errors))
    identifier, categorical, numeric = (mapping[key] for key in ("id", "categorical", "numeric"))
    def identity_key(value):
        value = _plain(value)
        return (0, value) if isinstance(value, (int, float)) else (1, value)
    indices = sorted(range(len(df)), key=lambda index: (
        float(df.iloc[index][order_by]) if order_by else 0,
        identity_key(df.iloc[index][identifier])))
    result = df.iloc[indices][[identifier, *categorical, *numeric]].copy().reset_index(drop=True)
    for column in numeric:
        result[column] = result[column].astype(float)
    categories = []
    for column in categorical:
        domain = [_plain(value) for value in (category_orders or {}).get(column, _ordered(result[column]))]
        counts = result[column].value_counts().to_dict()
        categories.append({"column": column, "categories": domain,
                           "counts": [int(counts.get(value, 0)) for value in domain],
                           "proportions": [float(counts.get(value, 0) / len(result)) for value in domain]})
    summaries = []
    for column in numeric:
        values = result[column].to_numpy(dtype=float)
        q1, median, q3 = np.quantile(values, (.25, .5, .75))
        low, high = [float(value) for value in numeric_ranges[column]]
        summaries.append({"column": column, "range": [low, high],
                          "ticks": [float(value) for value in (numeric_ticks or {}).get(column, [low, (low + high) / 2, high])],
                          "minimum": float(values.min()), "maximum": float(values.max()),
                          "q1": float(q1), "median": float(median), "q3": float(q3)})
    return result, {"participant_tracks": {
        "count": len(result), "categorical": categories, "numeric": summaries,
        "category_order": list(dict.fromkeys(value for track in categories for value in track["categories"])),
        "order_by": order_by,
    }}
