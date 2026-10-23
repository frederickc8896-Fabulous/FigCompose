"""
charts/confusion.py
===================
混淆矩阵定义 — 分类模型评估专用。

设计原则:
    - 只定义"confusion matrix 需要 x/y/value 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）

数据格式:
    长表: true_label, pred_label, count
    系统自动 groupby(true_label, pred_label) → count

支持的变体:
    - 计数混淆矩阵:       x + y (+ value column)
    - 归一化混淆矩阵:     x + y + normalize=True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Confusion(ChartSpec):
    """
    混淆矩阵规格。

    数据映射:
        x       — true label 列名（必需）
        y       — pred label 列名（必需）
        value   — 计数值列名（可选，无则自动 groupby count）

    选项:
        normalize  — True: 行归一化 (0~1), False: 原始计数
        annotate   — 是否在单元格显示数值
        fmt        — 数值格式

    Examples
    --------
    >>> Confusion(x="true_label", y="pred_label")
    >>> Confusion(x="true_label", y="pred_label", normalize=True)
    """

    chart_type: ClassVar[str] = "confusion"

    required_fields: ClassVar[List[str]] = ["x", "y"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "value": None,
    }

    # ── 实例字段 ──

    normalize: bool = False
    annotate: bool = True
    fmt: str = ".0f"

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[str]:
        return self.mapping.get("y")

    @property
    def value(self) -> Optional[str]:
        return self.mapping.get("value")

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: str,
        *,
        value: Optional[str] = None,
        title: Optional[str] = None,
        normalize: bool = False,
        annotate: bool = True,
        fmt: str = ".0f",
    ) -> "Confusion":
        mapping: Dict[str, Any] = {"x": x, "y": y}
        if value:
            mapping["value"] = value
        return cls(
            mapping=mapping,
            title=title,
            normalize=normalize,
            annotate=annotate,
            fmt=fmt,
        )

    def compute_requirements(self) -> Dict[str, Any]:
        group_by: List[str] = []
        if self.x:
            group_by.append(self.x)
        if self.y:
            group_by.append(self.y)
        # Explicit counts are additive; without a value column count raw rows.
        columns: Dict[str, List[str]] = {}
        if self.value and group_by:
            columns[self.value] = ["sum"]
        elif self.x and group_by:
            columns[self.x] = ["count"]
        return {
            "group_by": group_by,
            "columns": columns,
            "preprocess": [],
            "statistics": [],
        }

    def _chart_options(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        if self.normalize:
            opts["normalize"] = True
        if not self.annotate:
            opts["annotate"] = False
        if self.fmt != ".0f":
            opts["fmt"] = self.fmt
        return opts
