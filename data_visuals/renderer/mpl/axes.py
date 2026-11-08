"""Common, validated axis overrides applied after a statistical chart is drawn.

These options refer to the displayed axes, including horizontal bar/box plots.
Numeric formats use Python's format mini-language (``.1%`` scales by 100), or
a single ``{x:...}`` field with literal text (``{x:.1f}%`` adds a percent sign
without scaling). They never infer a unit from the data or column name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from numbers import Real

import numpy as np


from data_visuals.charts.families import CARTESIAN_CHARTS, THREE_D_CHARTS

_CARTESIAN = set(CARTESIAN_CHARTS)
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
    from data_visuals.core.identity import numeric_format_function
    return numeric_format_function(value, name)


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
    if kind in THREE_D_CHARTS:
        supplied |= {f"z{suffix}" for suffix in ("label", "lim", "ticks", "ticklabels", "scale", "format")}.intersection(options)
    if kind in _MATRICES:
        unsupported = supplied - _MATRIX_OPTIONS
    elif kind == "radar":
        unsupported = supplied - {"ylim"}
    elif kind in _CARTESIAN | THREE_D_CHARTS:
        unsupported = set()
    else:
        unsupported = supplied
    if unsupported:
        raise ValueError(f"[{kind}] axis options are not applicable: {', '.join(sorted(unsupported))}")
    if kind not in _CARTESIAN | _MATRICES | THREE_D_CHARTS:
        return
    for axis in (("x", "y", "z") if kind in THREE_D_CHARTS else ("x", "y")):
        prefix = f"[{kind}] {axis}"
        if f"{axis}label" in options and not isinstance(options[f"{axis}label"], str):
            raise ValueError(f"{prefix}label must be a string; use '' to hide the title")
        if f"{axis}scale" in options:
            scale = options[f"{axis}scale"]
            if not isinstance(scale, str) or scale not in _SCALES:
                raise ValueError(f"{prefix}scale must be 'linear', 'log' or 'symlog'")
            if kind in THREE_D_CHARTS and scale != "linear":
                raise ValueError(f"{prefix}scale currently supports linear coordinates only")
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
    if kind in {"raincloud", "ridgeline"}:
        _validate_category_axis(kind, "y" if options.get("horizontal", True) else "x", options)
    if kind == "waterfall3d":
        _validate_category_axis(kind, "y", options)
    if kind == "bar3d":
        for axis in ("x", "y"):
            _validate_category_axis(kind, axis, options)


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
    if kind not in _CARTESIAN | _MATRICES | THREE_D_CHARTS:
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
    for axis in (("x", "y", "z") if kind in THREE_D_CHARTS else ("x", "y")):
        axis_object = getattr(ax, f"{axis}axis")
        old_limits = getattr(ax, f"get_{axis}lim")()
        if f"{axis}label" in options:
            labels[axis] = options[f"{axis}label"]
            getattr(ax, f"set_{axis}label")(labels[axis])
        if f"{axis}scale" in options:
            getattr(ax, f"set_{axis}scale")(options[f"{axis}scale"])
        if f"{axis}ticks" in options:
            kwargs = {}
            if f"{axis}ticklabels" in options:
                kwargs["labels"] = list(options[f"{axis}ticklabels"])
            getattr(ax, f"set_{axis}ticks")(list(options[f"{axis}ticks"]), **kwargs)
            # Matrix categories keep their complete extent and inverted y
            # direction even when users thin or rename their ticks.
            if kind in _MATRICES:
                getattr(ax, f"set_{axis}lim")(old_limits)
        if f"{axis}format" in options:
            function = _format_function(options[f"{axis}format"], f"[{kind}] {axis}format")
            axis_object.set_major_formatter(FuncFormatter(lambda value, pos, fn=function: fn(value)))
        if f"{axis}lim" in options:
            getattr(ax, f"set_{axis}lim")(*options[f"{axis}lim"])
    ax._data_visuals_axis_labels = labels
