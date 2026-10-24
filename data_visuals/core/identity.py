"""Validated paper metadata, independent of data aggregation and rendering.

Field formats change text only. Series IDs remain raw data values; their
registered order reserves palette positions even when a figure omits a series.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Integral, Real
from string import Formatter
from typing import Any


_FIELD_KEYS = frozenset({"label", "unit", "format"})
_SERIES_KEYS = frozenset({"id", "label", "color", "marker", "linestyle"})


def numeric_format_function(value: Any, name: str = "format"):
    """Compile an explicit numeric format without inferring a data unit.

    ``.1%`` scales 0–1 values by 100 for display; ``{x:.1f}%`` appends a
    percent sign to values already expressed as percentages.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty Python numeric format, e.g. '.2f' or '{{x:.1f}}%'")
    if "{" in value or "}" in value:
        try:
            fields = [(field, spec, conversion) for _, field, spec, conversion in Formatter().parse(value)
                      if field is not None]
        except ValueError as exc:
            raise ValueError(f"{name} has an invalid numeric format") from exc
        if (len(fields) != 1 or fields[0][0] != "x" or fields[0][2] is not None
                or "{" in fields[0][1] or "}" in fields[0][1]):
            raise ValueError(f"{name} templates require exactly one '{{x:...}}' field")
        function = lambda number: value.format(x=number)
    else:
        function = lambda number: format(number, value)
    try:
        function(0.125)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise ValueError(f"{name} has an invalid numeric format: {value!r}") from exc
    return function


def _column_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} keys must be nonempty column names.")
    return value


def normalize_fields(value: Any) -> dict[str, dict[str, str]]:
    """Copy field display labels, units and explicit numeric format strings."""
    if not isinstance(value, Mapping):
        raise ValueError("fields must be a mapping from column names to metadata.")
    result = {}
    for raw_column, metadata in value.items():
        column = _column_name(raw_column, "fields")
        context = f"fields[{column!r}]"
        if not isinstance(metadata, Mapping):
            raise ValueError(f"{context} must be a mapping.")
        unknown = set(metadata) - _FIELD_KEYS
        if unknown:
            raise ValueError(f"{context} contains unknown fields: {', '.join(sorted(map(str, unknown)))}")
        normalized = {}
        for key, item in metadata.items():
            if not isinstance(item, str):
                raise ValueError(f"{context}.{key} must be a string.")
            if key == "format":
                numeric_format_function(item, f"{context}.format")
            normalized[key] = item
        result[column] = normalized
    return result


def _identity_scalar(value: Any, context: str) -> str | int | float:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a string or finite number; bool/null IDs are not supported.")
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        try:
            number = float(value)
        except (ValueError, OverflowError):
            number = float("inf")
        if isfinite(number):
            return number
    raise ValueError(f"{context} must be a string or finite number; bool/null IDs are not supported.")


def _json_sequence(value: Any, context: str) -> list:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{context} must be a JSON-compatible sequence.")
    result = []
    for item in value:
        if isinstance(item, (list, tuple)):
            result.append(_json_sequence(item, context))
        elif isinstance(item, str):
            result.append(item)
        else:
            result.append(_identity_scalar(item, context))
    return result


def _normalize_color(value: Any, context: str):
    from matplotlib.colors import is_color_like

    color = value if isinstance(value, str) else _json_sequence(value, context)
    if not is_color_like(color):
        raise ValueError(f"{context} must be a valid Matplotlib color.")
    return color


def _normalize_marker(value: Any, context: str):
    from matplotlib.markers import MarkerStyle

    if isinstance(value, str):
        marker = value
    elif isinstance(value, Integral) and not isinstance(value, bool):
        marker = int(value)
    else:
        marker = _json_sequence(value, context)
    try:
        MarkerStyle(marker)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{context} must be a valid Matplotlib marker.") from exc
    return marker


def _normalize_linestyle(value: Any, context: str):
    from matplotlib.lines import Line2D

    if isinstance(value, str):
        style = value
    else:
        parts = _json_sequence(value, context)
        if len(parts) != 2 or not isinstance(parts[1], list):
            raise ValueError(f"{context} must be a Matplotlib line style or [offset, dash_sequence].")
        offset = parts[0]
        pattern = parts[1]
        if (not isinstance(offset, (int, float))
                or not all(isinstance(item, (int, float)) and item >= 0 for item in pattern)
                or (pattern and not any(pattern))):
            raise ValueError(f"{context} dash lengths must be finite, nonnegative and not all zero.")
        style = (offset, tuple(pattern))
    try:
        Line2D([], [], linestyle=style)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{context} must be a valid Matplotlib line style.") from exc
    return style


def normalize_series(value: Any) -> dict[str, list[dict[str, Any]]]:
    """Copy ordered series declarations and validate their raw IDs and styles.

    Labels must be unique within a column, since legends and color aliases use
    those display names. Numeric 1 and 1.0 identify the same pandas category.
    """
    if not isinstance(value, Mapping):
        raise ValueError("series must be a mapping from group columns to ordered identity lists.")
    result = {}
    for raw_column, entries in value.items():
        column = _column_name(raw_column, "series")
        context = f"series[{column!r}]"
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence) or not entries:
            raise ValueError(f"{context} must be a nonempty ordered list of identities.")
        normalized, ids, labels = [], set(), set()
        for index, entry in enumerate(entries):
            item_context = f"{context}[{index}]"
            if not isinstance(entry, Mapping):
                raise ValueError(f"{item_context} must be a mapping containing an id.")
            unknown = set(entry) - _SERIES_KEYS
            if unknown:
                raise ValueError(f"{item_context} contains unknown fields: {', '.join(sorted(map(str, unknown)))}")
            if "id" not in entry:
                raise ValueError(f"{item_context} requires an id.")
            identity = _identity_scalar(entry["id"], f"{item_context}.id")
            label = entry.get("label", str(identity))
            if not isinstance(label, str):
                raise ValueError(f"{item_context}.label must be a string.")
            if identity in ids:
                raise ValueError(f"{context} contains duplicate id: {identity!r}.")
            if label in labels:
                raise ValueError(f"{context} contains duplicate label: {label!r}.")
            ids.add(identity)
            labels.add(label)
            item = {"id": identity, "label": label}
            for key, normalizer in (("color", _normalize_color), ("marker", _normalize_marker),
                                    ("linestyle", _normalize_linestyle)):
                if key in entry:
                    item[key] = normalizer(entry[key], f"{item_context}.{key}")
            normalized.append(item)
        result[column] = normalized
    return result
