"""Resolve presentation metadata without changing source columns or values.

Metadata supplies defaults to the existing chart options. Explicit per-panel
options always take precedence, including fixed tick labels. Units are labels;
only an explicitly supplied numeric format controls how numbers are displayed.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import pandas as pd


def field_label(column, fields, *, include_unit=True):
    """Return a registered display name, optionally followed by ``(unit)``.

    The lookup always uses the original column identifier. Neither this helper
    nor the resolver renames data, rescales it, or infers percentage storage.
    """
    if column is None:
        return ""
    metadata = (fields or {}).get(column, {})
    label = metadata.get("label", str(column))
    unit = metadata.get("unit", "") if include_unit else ""
    return f"{label} ({unit})" if unit else label


def _columns(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _metadata(columns, fields):
    return [fields[column] for column in columns if column in fields]


def _common_property(columns, fields, property_name, option_name):
    """Only explicitly registered properties participate in compatibility.

    Profiles may describe more fields than a particular CSV contains, and a
    field with just a display name does not declare numeric formatting.
    """
    values = list(dict.fromkeys(
        metadata[property_name] for metadata in _metadata(columns, fields)
        if property_name in metadata
    ))
    if len(values) > 1:
        names = ", ".join(repr(column) for column in columns)
        raise ValueError(
            f"Fields {names} have incompatible {property_name} metadata on one axis; "
            f"set chart_opts.{option_name} explicitly or use separate axes."
        )
    return values[0] if values else None


def _axis_label(columns, fields, option_name):
    unit = _common_property(columns, fields, "unit", option_name)
    names = ", ".join(field_label(column, fields, include_unit=False) for column in columns)
    return f"{names} ({unit})" if unit else names


def _numeric_column(data, column):
    """Numeric axes can use a formatter; category positions cannot."""
    if data is None or not isinstance(column, str):
        return False
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    for candidate in (column, f"{column}_mean"):
        if candidate in frame:
            return (pd.api.types.is_numeric_dtype(frame[candidate])
                    and not pd.api.types.is_bool_dtype(frame[candidate]))
    return False


def _resolve_axis(options, axis, columns, fields, *, numeric):
    columns = _columns(columns)
    metadata = _metadata(columns, fields)
    if not metadata:
        return
    label_key, format_key = f"{axis}label", f"{axis}format"
    if label_key not in options and any("label" in item or "unit" in item for item in metadata):
        options[label_key] = _axis_label(columns, fields, label_key)
    # Fixed per-panel tick text is also an explicit formatting choice.
    if numeric and format_key not in options and f"{axis}ticklabels" not in options:
        numeric_format = _common_property(columns, fields, "format", format_key)
        if numeric_format is not None:
            options[format_key] = numeric_format


def _resolve_value(options, columns, fields, *, label=False):
    columns = _columns(columns)
    metadata = _metadata(columns, fields)
    if not metadata:
        return
    if label and "value_label" not in options and any(
        "label" in item or "unit" in item for item in metadata
    ):
        options["value_label"] = _axis_label(columns, fields, "value_label")
    # A matrix's established `fmt` controls annotations independently. The
    # renderer lets it override cell text while retaining value_format on the
    # colorbar, whose numeric values represent the same registered measure.
    if "value_format" not in options:
        numeric_format = _common_property(columns, fields, "format", "value_format")
        if numeric_format is not None:
            options["value_format"] = numeric_format


def resolve_field_options(kind, mapping, options, fields, *, data=None):
    """Return new chart options with applicable field defaults filled in.

    Cartesian option names refer to the displayed axes, so a horizontal bar
    resolves its measurement metadata to X. Matrix category labels are kept
    separate from their numeric value metadata. Normalized confusion matrices
    and percent-stacked bars keep their native transformed-value presentation:
    raw measurement units and formats no longer describe those values.

    Multiple measures sharing one axis must agree on explicitly registered
    units and formats, unless that axis has an explicit per-panel override.
    Metadata for fields absent from this panel has no effect.
    """
    resolved = deepcopy(dict(options or {}))
    if not fields:
        return resolved
    if not isinstance(fields, Mapping):
        raise ValueError("fields must be a mapping")
    if kind in {"pie", "donut", "custom"}:
        return resolved
    if kind in {"heatmap", "confusion"}:
        for axis in ("x", "y"):
            _resolve_axis(resolved, axis, mapping.get(axis), fields, numeric=False)
        if not (kind == "confusion" and resolved.get("normalize", False)):
            _resolve_value(resolved, mapping.get("value"), fields, label=True)
        return resolved
    if kind == "radar":
        _resolve_value(resolved, mapping.get("y"), fields)
        return resolved
    if kind == "histogram":
        _resolve_axis(resolved, "x", mapping.get("x"), fields, numeric=True)
        return resolved
    if kind in {"bar", "box"}:
        category_axis, value_axis = ("y", "x") if resolved.get("horizontal", False) else ("x", "y")
        _resolve_axis(resolved, category_axis, mapping.get("x"), fields, numeric=False)
        percent_stacked = kind == "bar" and resolved.get("stacked") == "percent"
        if not percent_stacked:
            _resolve_axis(resolved, value_axis, mapping.get("y"), fields, numeric=True)
            if kind == "bar" and resolved.get("show_value", False):
                _resolve_value(resolved, mapping.get("y"), fields)
        _resolve_axis(resolved, "y2", mapping.get("y2"), fields, numeric=True)
        return resolved
    if kind in {"line", "scatter"}:
        numeric_x = kind == "scatter" or _numeric_column(data, mapping.get("x"))
        _resolve_axis(resolved, "x", mapping.get("x"), fields, numeric=numeric_x)
        _resolve_axis(resolved, "y", mapping.get("y"), fields, numeric=True)
        _resolve_axis(resolved, "y2", mapping.get("y2"), fields, numeric=True)
    return resolved
