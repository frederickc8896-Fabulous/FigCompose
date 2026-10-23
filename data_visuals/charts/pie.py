"""Additive categorical composition; never average quantities into slices."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from data_visuals.charts import ChartSpec, register_chart


def _valid_order(order, actual) -> bool:
    """Malformed category lists should produce contract errors, not set errors."""
    try:
        return (isinstance(order, (list, tuple)) and len(order) == len(actual)
                and len(set(order)) == len(order) and set(order) == set(actual))
    except (TypeError, ValueError):
        return False


def _category_values(series):
    values = series.dropna().tolist()
    if not all(pd.api.types.is_scalar(value) for value in values):
        return None
    try:
        return series.dropna().unique().tolist()
    except (TypeError, ValueError):
        return None


def _plain_options(value):
    """Typed chart options retain a JSON-safe, backend-independent contract."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return [_plain_options(item) for item in value]
    return value


@register_chart
@dataclass
class Pie(ChartSpec):
    """Map ``group`` to categories and optional ``value`` to additive amounts.

    Without ``value``, each source row contributes one count. Category labels
    live in the managed legend, avoiding overlapping outside wedge labels.
    """

    chart_type: ClassVar[str] = "pie"
    required_fields: ClassVar[list[str]] = ["group"]
    optional_fields: ClassVar[dict[str, Any]] = {"value": None}

    show_percent: bool = True
    startangle: float = 90.0
    counterclock: bool = False
    percent_decimals: int = 0
    percent_threshold: float = 3.0
    order: list[Any] | None = None

    def validate(self, df: pd.DataFrame) -> list[str]:
        errors = super().validate(df)
        group, value = self.mapping.get("group"), self.mapping.get("value")
        for field, column in (("group", group), ("value", value)):
            if column is not None and (not isinstance(column, str) or not column):
                errors.append(f"[{self.chart_type}] {field} 必须是单个列名字符串。")
        if isinstance(group, str) and group in df:
            if df.empty or df[group].isna().any():
                errors.append(f"[{self.chart_type}] group 类别不能为空或缺失。")
            actual = _category_values(df[group])
            if actual is None:
                errors.append(f"[{self.chart_type}] group 类别必须是可分组的标量。")
            if self.order is not None:
                if actual is None or not _valid_order(self.order, actual):
                    errors.append(f"[{self.chart_type}] order 必须恰好包含当前面板的全部类别，不能重复。")
        if isinstance(value, str) and value in df:
            if (not pd.api.types.is_numeric_dtype(df[value])
                    or pd.api.types.is_complex_dtype(df[value])):
                errors.append(f"[{self.chart_type}] value 列 '{value}' 必须是有限非负实数。")
            else:
                values = df[value].to_numpy(dtype=float, na_value=np.nan)
                if not np.isfinite(values).all() or (values < 0).any():
                    errors.append(f"[{self.chart_type}] value 必须是有限非负数，不允许缺失。")
                elif not np.isfinite(values.sum()) or values.sum() <= 0:
                    errors.append(f"[{self.chart_type}] value 总和必须是有限正数。")
        if not isinstance(self.show_percent, bool) or not isinstance(self.counterclock, bool):
            errors.append(f"[{self.chart_type}] show_percent 与 counterclock 必须是布尔值。")
        if (not isinstance(self.startangle, Real) or isinstance(self.startangle, bool)
                or not np.isfinite(self.startangle)):
            errors.append(f"[{self.chart_type}] startangle 必须是有限角度。")
        if (not isinstance(self.percent_decimals, int) or isinstance(self.percent_decimals, bool)
                or not 0 <= self.percent_decimals <= 3):
            errors.append(f"[{self.chart_type}] percent_decimals 必须是 0–3 的整数。")
        if (not isinstance(self.percent_threshold, Real) or isinstance(self.percent_threshold, bool)
                or not np.isfinite(self.percent_threshold) or not 0 <= self.percent_threshold <= 100):
            errors.append(f"[{self.chart_type}] percent_threshold 必须在 0–100 之间。")
        return errors

    def compute_requirements(self) -> dict[str, Any]:
        group, value = self.mapping["group"], self.mapping.get("value")
        return {"group_by": [group], "columns": {value or group: ["sum" if value else "count"]},
                "preprocess": [], "statistics": []}

    def _chart_options(self) -> dict[str, Any]:
        defaults = {"show_percent": True, "startangle": 90.0, "counterclock": False,
                    "percent_decimals": 0, "percent_threshold": 3.0, "order": None}
        return {key: _plain_options(getattr(self, key)) for key, default in defaults.items()
                if getattr(self, key) != default}


@register_chart
@dataclass
class Donut(Pie):
    """A pie with a physical circular hole; ``width`` is a radius fraction."""

    chart_type: ClassVar[str] = "donut"
    width: float = 0.4

    def validate(self, df: pd.DataFrame) -> list[str]:
        errors = super().validate(df)
        if (not isinstance(self.width, Real) or isinstance(self.width, bool)
                or not np.isfinite(self.width) or not 0 < self.width < 1):
            errors.append("[donut] width 必须大于 0 且小于 1。")
        return errors

    def _chart_options(self) -> dict[str, Any]:
        return {**super()._chart_options(), "width": float(self.width)}
