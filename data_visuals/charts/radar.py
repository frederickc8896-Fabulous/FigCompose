"""Radar data contract: complete axes, repeated-observation means, raw scales."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _category_values, _plain_options, _valid_order


@register_chart
@dataclass
class Radar(ChartSpec):
    """Long-form ``x`` metric, ``y`` score, optionally grouped by series.

    Repeated group/metric observations are averaged. All groups must contain
    every axis; missing observations are never silently replaced with zeros.
    Scores share their original radial scale, without implicit normalization.
    """

    chart_type: ClassVar[str] = "radar"
    required_fields: ClassVar[list[str]] = ["x", "y"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None}

    order: list[Any] | None = None
    fill_alpha: float = 0.10
    markers: bool = True
    ylim: tuple[float, float] | list[float] | None = None
    label_width: int = 18

    def validate(self, df: pd.DataFrame) -> list[str]:
        errors = super().validate(df)
        x, y, group = (self.mapping.get(field) for field in ("x", "y", "group"))
        for field, column in (("x", x), ("y", y), ("group", group)):
            if column is not None and (not isinstance(column, str) or not column):
                errors.append(f"[radar] {field} 必须是单个列名字符串。")
        named = [column for column in (x, y, group) if isinstance(column, str)]
        if len(named) != len(set(named)):
            errors.append("[radar] x、y 和 group 必须映射到不同列。")
        if isinstance(x, str) and x in df:
            categories = _category_values(df[x])
            if categories is None:
                errors.append("[radar] x 指标类别必须是可分组的标量。")
                categories = []
            if df[x].isna().any() or len(categories) < 3:
                errors.append("[radar] x 至少需要三个非缺失的指标类别。")
            if self.order is not None:
                if not _valid_order(self.order, categories):
                    errors.append("[radar] order 必须恰好包含当前面板的全部指标，不能重复。")
            if isinstance(group, str) and group in df:
                if df[group].isna().any():
                    errors.append("[radar] group 类别不允许缺失。")
                if _category_values(df[group]) is None:
                    errors.append("[radar] group 类别必须是可分组的标量。")
                elif categories:
                    for key, sub in df.groupby(group, sort=False, observed=True):
                        if set(sub[x]) != set(categories):
                            errors.append(f"[radar] 组 {key!r} 缺少指标；所有组必须包含全部指标，不能补零。")
        if isinstance(y, str) and y in df:
            if (not pd.api.types.is_numeric_dtype(df[y])
                    or pd.api.types.is_complex_dtype(df[y])):
                errors.append(f"[radar] y 列 '{y}' 必须是有限非负实数。")
            else:
                values = df[y].to_numpy(dtype=float, na_value=np.nan)
                if not np.isfinite(values).all() or (values < 0).any():
                    errors.append("[radar] y 必须是有限非负数，不允许缺失。")
        if (not isinstance(self.fill_alpha, Real) or isinstance(self.fill_alpha, bool)
                or not np.isfinite(self.fill_alpha) or not 0 <= self.fill_alpha <= 1):
            errors.append("[radar] fill_alpha 必须在 0–1 之间。")
        if not isinstance(self.markers, bool):
            errors.append("[radar] markers 必须是布尔值。")
        if not isinstance(self.label_width, int) or isinstance(self.label_width, bool) or self.label_width < 4:
            errors.append("[radar] label_width 必须是至少为 4 的整数。")
        if self.ylim is not None:
            if (not isinstance(self.ylim, (list, tuple)) or len(self.ylim) != 2
                    or any(not isinstance(v, Real) or isinstance(v, bool) or not np.isfinite(v) for v in self.ylim)
                    or not 0 <= self.ylim[0] < self.ylim[1]):
                errors.append("[radar] ylim 必须是两个有限非负数，且下限小于上限。")
        return errors

    def compute_requirements(self) -> dict[str, Any]:
        keys = list(dict.fromkeys([self.mapping["x"], *([self.mapping["group"]] if self.mapping.get("group") else [])]))
        return {"group_by": keys, "columns": {self.mapping["y"]: ["mean"]},
                "preprocess": [], "statistics": []}

    def _chart_options(self) -> dict[str, Any]:
        defaults = {"order": None, "fill_alpha": 0.10, "markers": True,
                    "ylim": None, "label_width": 18}
        return {key: _plain_options(getattr(self, key)) for key, default in defaults.items()
                if getattr(self, key) != default}
