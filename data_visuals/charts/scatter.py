"""
charts/scatter.py
=================
散点图定义 — 声明散点图所需的数据字段和计算需求。

设计原则:
    - 只定义"散点图需要 x/y/group/size 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）
    - 不做计算：散点图直接使用原始值，无需聚合

支持的变体:
    - 基础散点:          x + y
    - 分组着色:          x + y + group
    - 气泡图:            x + y + size
    - 分组 + 气泡:       x + y + group + size
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Scatter(ChartSpec):
    """
    散点图规格。

    数据映射:
        x       — x 轴列名（必需）
        y       — y 轴列名（必需）→ 左轴
        y2      — 右轴列名（可选，启用双 y 轴）
        group   — 分组着色列名（可选）
        size    — 气泡大小列名（可选）

    选项:
        opacity  — 透明度 0~1，默认 0.7
        trend    — 是否显示趋势线，默认 False

    Examples
    --------
    >>> scatter = Scatter(x="param_count", y="accuracy", group="model_family")
    >>> scatter = Scatter(x="epoch", y="loss", y2="accuracy")  # 双轴
    >>> scatter.compute_requirements()
    {'group_by': [], 'columns': {}, 'preprocess': []}
    # 散点图无需聚合 — 直接使用原始值
    """

    chart_type: ClassVar[str] = "scatter"

    required_fields: ClassVar[List[str]] = ["x", "y"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "group": None,
        "size": None,
        "y2": None,
    }

    # ── 散点图特有选项 ──

    opacity: float = 0.7
    trend: bool = False  # 是否显示趋势线（回归线）

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[str]:
        return self.mapping.get("y")

    @property
    def y2(self) -> Optional[str]:
        """右轴列名（双 y 轴时使用）。"""
        return self.mapping.get("y2")

    @property
    def group(self) -> Optional[str]:
        return self.mapping.get("group")

    @property
    def size(self) -> Optional[str]:
        return self.mapping.get("size")

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: str,
        *,
        y2: Optional[str] = None,
        group: Optional[str] = None,
        size: Optional[str] = None,
        title: Optional[str] = None,
        opacity: float = 0.7,
        trend: bool = False,
    ) -> "Scatter":
        """
        快捷构造散点图。

        Parameters
        ----------
        x : str
            x 轴列名
        y : str
            y 轴列名 → 左轴
        y2 : str | None
            右轴列名（可选，启用双 y 轴）
        group : str | None
            分组着色列名
        size : str | None
            气泡大小列名
        title : str | None
            子图标题
        opacity : float
            透明度 (0~1)
        trend : bool
            趋势线

        Returns
        -------
        Scatter
        """
        mapping: Dict[str, Any] = {"x": x, "y": y}
        if y2:
            mapping["y2"] = y2
        if group:
            mapping["group"] = group
        if size:
            mapping["size"] = size

        return cls(
            mapping=mapping,
            title=title,
            opacity=opacity,
            trend=trend,
        )

    # ── 选项导出 ──────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """导出散点图特有的选项。"""
        opts: Dict[str, Any] = {}
        if self.opacity != 0.7:
            opts["opacity"] = self.opacity
        if self.trend:
            opts["trend"] = True
        return opts
