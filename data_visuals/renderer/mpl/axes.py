"""Common, validated axis overrides applied after a statistical chart is drawn.

These options refer to the displayed axes, including horizontal bar/box plots.
Numeric formats use Python's format mini-language (``.1%`` scales by 100), or
a single ``{x:...}`` field with literal text (``{x:.1f}%`` adds a percent sign
without scaling). They never infer a unit from the data or column name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Real
from string import Formatter

import numpy as np


_CARTESIAN = {"bar", "line", "scatter", "box", "histogram"}
_MATRICES = {"heatmap", "confusion"}
_COMMON = {
    f"{axis}{suffix}"
    for axis in ("x", "y")
    for suffix in ("label", "lim", "ticks", "ticklabels", "scale", "format")
}
_MATRIX_OPTIONS = {
    f"{axis}{suffix}"
    for axis in ("x", "y")
    for suffix in ("label", "ticks", "ticklabels")
}
_SCALES = {"linear", "log", "symlog"}


def _number(value, name):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not np.isfinite(value)):
        raise ValueError(f"{name} must contain finite real numbers")
    return float(value)


def _sequence(value, name):
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError(f"{name} must be a sequence")
    # Arrays are accepted without allowing one-shot iterators that would be
    # exhausted between validation, layout measurements and final export.
    if not isinstance(value, Sequence) and not isinstance(value, np.ndarray):
        raise ValueError(f"{name} must be a sequence")
    if isinstance(value, np.ndarray) and value.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional sequence")
    return list(value)


def _format_function(value, name):
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


def validate_axis_options(kind, options):
    """Validate public axis options without mutating chart-specific options.

    Matrix axes are categorical: display names and fixed ticks/labels can be
    overridden, but numeric ranges, scales and formatters are rejected. Radar
    keeps its existing native radial ``ylim`` contract; other round/custom
    panels configure their native axes through their own interface.
    """
    if options is None:
        return
    if not isinstance(options, Mapping):
        raise ValueError("chart_opts must be a mapping")
    supplied = _COMMON.intersection(options)
    if kind in _MATRICES:
        unsupported = supplied - _MATRIX_OPTIONS
    elif kind == "radar":
        unsupported = supplied - {"ylim"}
    elif kind in _CARTESIAN:
        unsupported = set()
    else:
        unsupported = supplied
    if unsupported:
        raise ValueError(f"[{kind}] axis options are not applicable: {', '.join(sorted(unsupported))}")
    if kind not in _CARTESIAN | _MATRICES:
        return
    for axis in ("x", "y"):
        prefix = f"[{kind}] {axis}"
        if f"{axis}label" in options and not isinstance(options[f"{axis}label"], str):
            raise ValueError(f"{prefix}label must be a string; use '' to hide the title")
        if f"{axis}scale" in options:
            scale = options[f"{axis}scale"]
            if not isinstance(scale, str) or scale not in _SCALES:
                raise ValueError(f"{prefix}scale must be 'linear', 'log' or 'symlog'")
        scale = options.get(f"{axis}scale", "linear")
        if f"{axis}lim" in options:
            limits = _sequence(options[f"{axis}lim"], f"{prefix}lim")
            if len(limits) != 2:
                raise ValueError(f"{prefix}lim must contain two distinct finite real numbers")
            low, high = [_number(value, f"{prefix}lim") for value in limits]
            if low == high:
                raise ValueError(f"{prefix}lim endpoints must differ")
            if scale == "log" and min(low, high) <= 0:
                raise ValueError(f"{prefix}lim must be positive for a log scale")
        ticks = None
        if f"{axis}ticks" in options:
            ticks = [_number(value, f"{prefix}ticks")
                     for value in _sequence(options[f"{axis}ticks"], f"{prefix}ticks")]
            if scale == "log" and any(value <= 0 for value in ticks):
                raise ValueError(f"{prefix}ticks must be positive for a log scale")
        if f"{axis}ticklabels" in options:
            if ticks is None:
                raise ValueError(f"{prefix}ticklabels requires {axis}ticks")
            labels = _sequence(options[f"{axis}ticklabels"], f"{prefix}ticklabels")
            if not all(isinstance(label, str) for label in labels):
                raise ValueError(f"{prefix}ticklabels must contain strings")
            if len(labels) != len(ticks):
                raise ValueError(f"{prefix}ticklabels must have the same length as {axis}ticks")
        if f"{axis}format" in options:
            if f"{axis}ticklabels" in options:
                raise ValueError(f"{prefix}format and {axis}ticklabels cannot both format the same axis")
            _format_function(options[f"{axis}format"], f"{prefix}format")
    if kind in {"bar", "box"}:
        categorical = "y" if options.get("horizontal", False) else "x"
        _validate_category_axis(kind, categorical, options)


def _validate_category_axis(kind, axis, options):
    if options.get(f"{axis}scale", "linear") != "linear":
        raise ValueError(f"[{kind}] {axis}scale cannot change a categorical axis; use a linear scale")
    if f"{axis}format" in options:
        raise ValueError(f"[{kind}] {axis}format cannot format category names; use {axis}ticks/{axis}ticklabels")


def apply_axis_options(ax, sp):
    """Apply validated overrides once, after the chart and before facet sharing.

    Chart builders remain responsible for data limits (including uncertainty),
    category positions and sensible default labels. Explicit limits follow
    ticks because Matplotlib expands its range when assigning fixed ticks.
    """
    from matplotlib.ticker import FuncFormatter

    kind, options = sp.get("chart", ""), sp.get("options", {})
    if options is None:
        options = {}
    validate_axis_options(kind, options)
    if kind not in _CARTESIAN | _MATRICES:
        return
    if kind == "line" and ("xformat" in options or options.get("xscale", "linear") != "linear"):
        # Line's renderer uses integer positions for string categories. Treat
        # those positions as categories rather than expose them as numbers.
        import pandas as pd
        data = sp.get("computed_data", [])
        frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        column = sp.get("data", {}).get("x")
        if column in frame and not pd.api.types.is_numeric_dtype(frame[column]):
            _validate_category_axis(kind, "x", options)
    labels = dict(getattr(ax, "_data_visuals_axis_labels", {}))
    for axis in ("x", "y"):
        axis_object = ax.xaxis if axis == "x" else ax.yaxis
        old_limits = (ax.get_xlim if axis == "x" else ax.get_ylim)()
        if f"{axis}label" in options:
            labels[axis] = options[f"{axis}label"]
            (ax.set_xlabel if axis == "x" else ax.set_ylabel)(labels[axis])
        if f"{axis}scale" in options:
            (ax.set_xscale if axis == "x" else ax.set_yscale)(options[f"{axis}scale"])
        if f"{axis}ticks" in options:
            kwargs = {}
            if f"{axis}ticklabels" in options:
                kwargs["labels"] = list(options[f"{axis}ticklabels"])
            (ax.set_xticks if axis == "x" else ax.set_yticks)(list(options[f"{axis}ticks"]), **kwargs)
            # Matrix categories keep their complete extent and inverted y
            # direction even when users thin or rename their ticks.
            if kind in _MATRICES:
                (ax.set_xlim if axis == "x" else ax.set_ylim)(old_limits)
        if f"{axis}format" in options:
            function = _format_function(options[f"{axis}format"], f"[{kind}] {axis}format")
            axis_object.set_major_formatter(FuncFormatter(lambda value, pos, fn=function: fn(value)))
        if f"{axis}lim" in options:
            (ax.set_xlim if axis == "x" else ax.set_ylim)(*options[f"{axis}lim"])
    ax._data_visuals_axis_labels = labels
