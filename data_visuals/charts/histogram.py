"""
charts/histogram.py
===================
直方图 & 密度曲线定义。

设计原则:
    - 只定义"histogram 需要 x/group 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）
    - 声明分箱与密度选项：原始观测和计算层密度曲线交给渲染器绘制

支持的变体:
    - 直方图:             x
    - 分组直方图:          x + group (叠加半透明)
    - 密度曲线:            x + density=True
    - 分组密度曲线:        x + group + density=True
    - 指定 bins:          bins=30
    - 累积分布:            cumulative=True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, ClassVar

import pandas as pd

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Histogram(ChartSpec):
    """
    直方图 / 密度曲线规格。

    数据映射:
        x       — 数值列名（必需）
        group   — 分组列名（可选，分组叠加或分组密度曲线）

    选项:
        bins        — 分箱数，默认 20
        density     — True → 密度曲线 (KDE)，False → 直方图
        cumulative  — 是否累积分布 (仅 density=False 时有效)

    Examples
    --------
    >>> Histogram(x="accuracy")
    >>> Histogram(x="accuracy", bins=30)
    >>> Histogram(x="loss", density=True)
    >>> Histogram(x="loss", group="model", density=True)
    """

    chart_type: ClassVar[str] = "histogram"

    required_fields: ClassVar[List[str]] = ["x"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "group": None,
    }

    # ── 实例字段 ──

    bins: int = 20
    density: bool = False
    cumulative: bool = False

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def group(self) -> Optional[str]:
        return self.mapping.get("group")

    @classmethod
    def from_mapping(
        cls,
        x: str,
        *,
        group: Optional[str] = None,
        title: Optional[str] = None,
        bins: int = 20,
        density: bool = False,
        cumulative: bool = False,
    ) -> "Histogram":
        mapping: Dict[str, Any] = {"x": x}
        if group:
            mapping["group"] = group
        return cls(
            mapping=mapping,
            title=title,
            bins=bins,
            density=density,
            cumulative=cumulative,
        )

    def compute_requirements(self) -> Dict[str, Any]:
        return {
            "group_by": [],
            "columns": {},
            "preprocess": [],
            "statistics": [],
        }

    def _chart_options(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self.bins != 20:
            opts["bins"] = self.bins
        if self.density:
            opts["density"] = True
        if self.cumulative:
            opts["cumulative"] = True
        return opts

    def validate(self, df: "pd.DataFrame") -> List[str]:  # type: ignore[override]
        errors = super().validate(df)
        if self.x and self.x in df.columns:
            if not pd.api.types.is_numeric_dtype(df[self.x]):
                errors.append(f"[histogram] x 列 '{self.x}' 必须是数值类型")
        return errors
