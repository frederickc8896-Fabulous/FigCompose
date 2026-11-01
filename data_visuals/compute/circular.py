"""Validated circular-score data, explicit aggregation and optional summaries.

This module owns numerical semantics only. It neither normalizes values nor
chooses colours, angles, labels or figure dimensions.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd


def _finite_real(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _category_domain(series: pd.Series) -> list[Any] | None:
    """Validate every key before uniqueness can merge bool with numeric IDs."""
    values = series.tolist()
    for value in values:
        if (not pd.api.types.is_scalar(value) or isinstance(value, (bool, np.bool_))
                or pd.isna(value) or (isinstance(value, str) and not value.strip())):
            return None
        if isinstance(value, Real) and not _finite_real(value):
            return None
        try:
            hash(value)
        except TypeError:
            return None
    try:
        return series.unique().tolist()
    except (ValueError, TypeError):
        return None


def validate_circular_input(
    df: pd.DataFrame,
    mapping: Mapping[str, Any],
    *,
    value_range=(0, 100),
    aggregate=None,
    summary=None,
    center="count",
    order=None,
    rounded=True,
) -> list[str]:
    """Return contract errors without mutating the source observations."""
    errors: list[str] = []
    prefix = "[circular_bar]"
    valid_range = (
        isinstance(value_range, (list, tuple)) and len(value_range) == 2
        and all(_finite_real(value) for value in value_range)
        and value_range[0] < value_range[1]
    )
    if not valid_range:
        errors.append(f"{prefix} value_range 必须是两个有限实数，且下限小于上限。")
    if not (aggregate is None or isinstance(aggregate, str) and aggregate in {"mean", "median", "sum"}):
        errors.append(f"{prefix} aggregate 必须是 None、'mean'、'median' 或 'sum'。")
    if not (summary is None or isinstance(summary, str) and summary == "mean"):
        errors.append(f"{prefix} summary 必须是 None 或 'mean'。")
    if not (center is None or isinstance(center, str) and center == "count"):
        errors.append(f"{prefix} center 必须是 None 或 'count'。")
    if not isinstance(rounded, bool):
        errors.append(f"{prefix} rounded 必须是布尔值。")
    if not isinstance(df, pd.DataFrame):
        return [*errors, f"{prefix} 数据必须是 pandas DataFrame。"]
    if not df.columns.is_unique:
        return [*errors, f"{prefix} 数据列名不能重复。"]
    if not isinstance(mapping, Mapping):
        return [*errors, f"{prefix} mapping 必须声明 x、y 和 group 列。"]
    names = {}
    for field in ("x", "y", "group"):
        column = mapping.get(field)
        if not isinstance(column, str) or not column:
            errors.append(f"{prefix} {field} 必须是单个非空列名字符串。")
        elif column not in df:
            errors.append(f"{prefix} {field} 列 '{column}' 不存在。")
        else:
            names[field] = column
    if len(names) != 3:
        return errors
    if len(set(names.values())) != 3:
        return [*errors, f"{prefix} x、y 和 group 必须映射到不同列。"]
    if df.empty:
        return [*errors, f"{prefix} 数据不能为空。"]

    x, y, group = (names[field] for field in ("x", "y", "group"))
    objects, categories = _category_domain(df[x]), _category_domain(df[group])
    if objects is None:
        errors.append(f"{prefix} x 对象ID必须是完整、可分组的标量，不允许空值或布尔值。")
    if categories is None:
        errors.append(f"{prefix} group 指标必须是完整、可分组的标量，不允许空值或布尔值。")

    values = df[y].tolist()
    numeric = all(_finite_real(value) for value in values)
    if not numeric:
        errors.append(f"{prefix} y 必须是有限实数，不允许空值、布尔值或复数。")
    elif valid_range:
        lower, upper = (float(value) for value in value_range)
        if any(not lower <= float(value) <= upper for value in values):
            errors.append(f"{prefix} y 值必须位于 value_range 范围内，不会自动缩放或裁切。")

    if objects is not None and categories is not None:
        pairs = df[[x, group]].drop_duplicates()
        if len(pairs) != len(objects) * len(categories):
            errors.append(f"{prefix} 每个对象必须包含全部指标，缺失组合不能补零。")
        if aggregate is None and len(pairs) != len(df):
            errors.append(f"{prefix} x/group 存在重复记录；请显式指定 aggregate 后再聚合。")
    if order is not None:
        valid_order = isinstance(order, (list, tuple)) and objects is not None
        if valid_order:
            valid_order = _category_domain(pd.Series(list(order), dtype=object)) is not None
        if valid_order:
            try:
                valid_order = len(order) == len(objects) and len(set(order)) == len(order) and set(order) == set(objects)
            except (ValueError, TypeError):
                valid_order = False
        if not valid_order:
            errors.append(f"{prefix} order 必须恰好包含当前面板全部对象ID，不能重复。")
    return errors


def _aggregate_values(values, operation):
    """Avoid both int64 wraparound and intermediate float64 mean overflow."""
    numbers = np.asarray(values, dtype=float)
    scale = float(np.max(np.abs(numbers)))
    if scale == 0:
        return 0.0
    scaled = numbers / scale
    if operation == "mean":
        result = (math.fsum(float(value) for value in scaled) / len(scaled)) * scale
    elif operation == "median":
        result = float(np.median(scaled)) * scale
    else:
        result = math.fsum(float(value) for value in scaled) * scale
    if not math.isfinite(result):
        raise ValueError("[circular_bar] 聚合结果必须是有限实数。")
    return result


def compute_circular_bar(
    df: pd.DataFrame,
    mapping: Mapping[str, Any],
    *,
    value_range=(0, 100),
    aggregate=None,
    summary=None,
    center="count",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Produce one raw-scale score per object/metric and derived annotations.

    Repeats are rejected unless their aggregation is explicit. A mean summary
    gives every object one vote after aggregation, irrespective of replicate
    counts. Object and series counts describe observed categories only.
    """
    errors = validate_circular_input(df, mapping, value_range=value_range,
                                     aggregate=aggregate, summary=summary, center=center)
    if errors:
        raise ValueError("\n".join(errors))
    x, y, group = (mapping[field] for field in ("x", "y", "group"))
    source = df[[x, group, y]].copy()
    if aggregate is not None:
        source[y] = source[y].astype("float64")
        result = source.groupby([x, group], sort=False, observed=True, dropna=False)[y].agg(
            lambda values: _aggregate_values(values, aggregate)).reset_index()
        result = result[[x, group, y]]
    else:
        result = source.reset_index(drop=True)
    lower, upper = (float(value) for value in value_range)
    values = result[y].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < lower).any() or (values > upper).any():
        raise ValueError("[circular_bar] 聚合后的 y 必须是 value_range 内的有限实数，不能自动裁切。")

    summaries = []
    if summary == "mean":
        for key, subset in result.groupby(group, sort=False, observed=True, dropna=False):
            if isinstance(key, np.generic):
                key = key.item()
            summaries.append({"group": key, "value": _aggregate_values(subset[y], "mean")})
    derived = {"circular_bar": {
        "object_count": int(result[x].nunique()),
        "series_count": int(result[group].nunique()),
        "summaries": summaries,
    }}
    return result, derived
