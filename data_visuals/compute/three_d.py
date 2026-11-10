"""Validated numeric payloads for explicit three-dimensional chart kinds.

The three axes have different meanings for each kind. Scatter uses measured
coordinates; waterfall depth is an ordered series index; bar uses two category
indices and nonnegative segment heights. This module never picks colours or
normalizes measurement units.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd

from data_visuals.compute.circular import _aggregate_values, _category_domain


def _number(value, name, *, positive=False, nonnegative=False):
    try:
        valid = (not isinstance(value, (bool, np.bool_)) and isinstance(value, Real)
                 and math.isfinite(float(value)))
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite real number")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return float(value)


def _ordered(values):
    values = list(values)
    try:
        return sorted(values)
    except TypeError:
        return sorted(values, key=lambda item: (type(item).__name__, str(item)))


def _domain(frame, column, order=None):
    domain = _category_domain(frame[column])
    if domain is None:
        raise ValueError(f"[3d] {column!r} needs finite, nonempty, non-boolean category keys")
    if order is None:
        return _ordered(domain)
    if (not isinstance(order, (list, tuple)) or len(order) != len(domain)
            or _category_domain(pd.Series(list(order), dtype=object)) is None
            or len(set(order)) != len(order) or set(order) != set(domain)):
        raise ValueError(f"[3d] order for {column!r} must contain every observed category exactly once")
    return list(order)


def _frame(df, mapping, required, optional=()):
    if not isinstance(df, pd.DataFrame) or df.empty or not df.columns.is_unique:
        raise ValueError("[3d] data must be a nonempty DataFrame with unique columns")
    if not isinstance(mapping, Mapping):
        raise ValueError("[3d] mappings must name source columns")
    names = {}
    for field in (*required, *optional):
        column = mapping.get(field)
        if field in optional and column is None:
            continue
        if not isinstance(column, str) or not column or column not in df:
            raise ValueError(f"[3d] {field} must name an existing source column")
        names[field] = column
    if len(set(names.values())) != len(names):
        raise ValueError("[3d] coordinate, measurement and grouping mappings must use distinct columns")
    return df[list(names.values())].copy(), names


def _numeric(frame, columns, *, nonnegative=False):
    for column in columns:
        values = [_number(value, f"[3d] {column}", nonnegative=nonnegative)
                  for value in frame[column].tolist()]
        frame[column] = np.asarray(values, dtype=float)


def validate_view(*, elev=25, azim=-58, box_aspect=(1, 1, 1), zoom=1,
                  proj_type="ortho"):
    _number(elev, "elev")
    _number(azim, "azim")
    _number(zoom, "zoom", positive=True)
    if proj_type not in ("ortho", "persp"):
        raise ValueError("proj_type must be 'ortho' or 'persp'")
    if not isinstance(box_aspect, (list, tuple)) or len(box_aspect) != 3:
        raise ValueError("box_aspect must contain three positive physical axis ratios")
    for value in box_aspect:
        _number(value, "box_aspect", positive=True)


def _aggregate(frame, keys, value, operation):
    if operation is not None and operation not in ("mean", "median", "sum"):
        raise ValueError("aggregate must be None, 'mean', 'median' or 'sum'")
    duplicate = frame.duplicated(keys).any()
    if duplicate and operation is None:
        raise ValueError("[3d] duplicate category/position records require explicit aggregate")
    if operation is None:
        return frame
    return frame.groupby(keys, sort=False, observed=True, dropna=False)[value].agg(
        lambda values: _aggregate_values(values, operation)).reset_index()


def compute_scatter3d(df, mapping, *, projections=None, projection_lines=None,
                      point_size=None, opacity=.95, **view):
    validate_view(**view)
    frame, names = _frame(df, mapping, ("x", "y", "z"), ("group",))
    _numeric(frame, [names[a] for a in ("x", "y", "z")])
    group = names.get("group")
    groups = _domain(frame, group) if group else [None]
    if point_size is not None:
        _number(point_size, "point_size", nonnegative=True)
    if not 0 <= _number(opacity, "opacity") <= 1:
        raise ValueError("opacity must be between zero and one")
    if projections is not None and (not isinstance(projections, Mapping)
                                    or set(projections) - {"x", "y", "z"}):
        raise ValueError("projections must explicitly map x/y/z to finite plane coordinates")
    planes = {axis: _number(value, f"projections.{axis}")
              for axis, value in (projections or {}).items()}
    if projection_lines is not None:
        if (not isinstance(projection_lines, (list, tuple))
                or any(axis not in planes for axis in projection_lines)
                or len(set(projection_lines)) != len(projection_lines)):
            raise ValueError("projection_lines must list unique axes from the explicit projection planes")
    if group:
        rank = {key: index for index, key in enumerate(groups)}
        indices = sorted(range(len(frame)), key=lambda i: (rank[frame.iloc[i][group]],
                         *(frame.iloc[i][names[a]] for a in ("x", "y", "z"))))
        frame = frame.iloc[indices]
    else:
        frame = frame.sort_values([names[a] for a in ("x", "y", "z")], kind="stable")
    return frame.reset_index(drop=True), {"three_d": {
        "kind": "scatter3d", "point_count": len(frame), "groups": groups,
        "projections": planes, "projection_lines": list(projection_lines or ())}}


def compute_waterfall3d(df, mapping, *, baseline=None, aggregate=None, order=None,
                        depth_spacing=1, fill=True, fill_alpha=1, linewidth=None,
                        markers=False, **view):
    validate_view(**view)
    baseline = _number(baseline, "waterfall3d baseline (explicit)")
    spacing = _number(depth_spacing, "depth_spacing", positive=True)
    if not isinstance(fill, bool) or not isinstance(markers, bool):
        raise ValueError("fill and markers must be booleans")
    if not 0 <= _number(fill_alpha, "fill_alpha") <= 1:
        raise ValueError("fill_alpha must be between zero and one")
    if linewidth is not None:
        _number(linewidth, "linewidth", nonnegative=True)
    frame, names = _frame(df, mapping, ("x", "y", "group"))
    x, value, group = (names[k] for k in ("x", "y", "group"))
    _numeric(frame, (x, value))
    groups = _domain(frame, group, order)
    frame = _aggregate(frame, [group, x], value, aggregate)
    profiles, records = [], []
    for index, key in enumerate(groups):
        rows = frame[frame[group] == key].sort_values(x, kind="stable")
        if len(rows) < 2:
            raise ValueError("waterfall3d needs at least two distinct positions per series")
        if not np.isfinite(rows[value].to_numpy(dtype=float)).all():
            raise ValueError("waterfall3d aggregated measurements must remain finite")
        records.append(rows)
        profiles.append({"group": key, "depth": index * spacing,
                         "x": rows[x].tolist(), "value": rows[value].tolist()})
    return pd.concat(records, ignore_index=True), {"three_d": {
        "kind": "waterfall3d", "profiles": profiles, "groups": groups,
        "baseline": baseline, "depth_spacing": spacing}}


def compute_bar3d(df, mapping, *, stacked=False, aggregate=None, x_order=None,
                  y_order=None, group_order=None, baseline=0, width=(.68, .68),
                  label_totals=False, total_format=None, **view):
    validate_view(**view)
    if not isinstance(stacked, bool) or not isinstance(label_totals, bool):
        raise ValueError("stacked and label_totals must be booleans")
    baseline = _number(baseline, "baseline")
    if not isinstance(width, (list, tuple)) or len(width) != 2:
        raise ValueError("bar3d width must contain two positive category-cell fractions")
    if any(not 0 < _number(w, "width", positive=True) <= 1 for w in width):
        raise ValueError("bar3d width must be at most one category cell")
    if total_format is not None:
        from data_visuals.core.identity import numeric_format_function
        numeric_format_function(total_format, "total_format")
    frame, names = _frame(df, mapping, ("x", "y", "value"), ("group",))
    x, y, value = (names[k] for k in ("x", "y", "value"))
    group = names.get("group")
    if stacked != bool(group):
        raise ValueError("bar3d group requires stacked=True; stacked=True requires group")
    _numeric(frame, (value,), nonnegative=True)
    xs, ys = _domain(frame, x, x_order), _domain(frame, y, y_order)
    groups = _domain(frame, group, group_order) if group else [None]
    if not group and group_order is not None:
        raise ValueError("group_order requires a grouped stacked bar3d")
    keys = [x, y, *([group] if group else [])]
    frame = _aggregate(frame, keys, value, aggregate)
    if len(frame) != len(xs) * len(ys) * len(groups):
        raise ValueError("bar3d requires every x/y cell and every declared component; missing cells cannot be filled with zero")
    table = {tuple(row[k] for k in keys): float(row[value])
             for row in frame.to_dict(orient="records")}
    cells, totals, records = [], [], []
    bottoms = {}
    for xi, xkey in enumerate(xs):
        for yi, ykey in enumerate(ys):
            values = [table[(xkey, ykey, *([g] if group else []))] for g in groups]
            try:
                # All segments are nonnegative: fsum gives the direct source
                # total without the extra scale/unscale rounding of aggregate.
                total = math.fsum(values)
                top = math.fsum([baseline, total])
            except OverflowError as error:
                raise ValueError("bar3d cumulative tops must remain finite") from error
            if not math.isfinite(top):
                raise ValueError("bar3d cumulative tops must remain finite")
            totals.append({"x": xkey, "y": ykey, "x_index": xi, "y_index": yi,
                           "value": total, "top": top})
            current = baseline
            for key, height in zip(groups, values):
                bottoms[(xkey, ykey, key)] = current
                current = math.fsum([current, height])
    # A stable part-major order preserves one global face-sort across all cubes.
    for key in groups:
        for xi, xkey in enumerate(xs):
            for yi, ykey in enumerate(ys):
                height = table[(xkey, ykey, *([key] if group else []))]
                bottom = bottoms[(xkey, ykey, key)]
                cells.append({"x": xkey, "y": ykey, "group": key, "x_index": xi,
                              "y_index": yi, "height": height, "bottom": bottom})
                records.append({x: xkey, y: ykey, value: height, **({group: key} if group else {})})
    return pd.DataFrame.from_records(records, columns=list(frame.columns)), {"three_d": {
        "kind": "bar3d", "cells": cells, "totals": totals, "x_order": xs,
        "y_order": ys, "groups": groups, "baseline": baseline, "width": list(width)}}
