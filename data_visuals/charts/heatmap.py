"""
charts/heatmap.py
=================
热力图定义 — 声明热力图所需的数据字段和计算需求。

设计原则:
    - 只定义"热力图需要 x/y/value 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色映射（属于 themes/）
    - 不负责实际聚合（属于 compute/）

热力图将两个分类维度映射为颜色矩阵:
    - x 轴: 分类变量 1
    - y 轴: 分类变量 2
    - 颜色: 数值变量 (value)

计算需求:
    groupby(x, y) → mean(value) 或 count(value)

支持的变体:
    - 基础热力图:        x + y + value
    - 计数热力图:        x + y (value 默认为 count)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Heatmap(ChartSpec):
    """
    热力图规格。

    数据映射:
        x       — x 轴分类列名（必需）
        y       — y 轴分类列名（必需）
        value   — 颜色映射的数值列名（必需）

    选项:
        annotate   — 是否在单元格显示数值，默认 True
        fmt        — 数值格式字符串，默认 ".2f"
        color_scheme — 颜色方案名，默认 ""(由主题决定)

    Examples
    --------
    >>> heatmap = Heatmap(x="method_a", y="method_b", value="correlation")
    >>> heatmap.compute_requirements()
    {'group_by': ['method_a', 'method_b'], 'columns': {'correlation': ['mean']}}

    >>> # 计数型热力图（需要先做 pivot/count）
    >>> heatmap = Heatmap(x="dataset", y="method", value="accuracy")
    """

    chart_type: ClassVar[str] = "heatmap"

    required_fields: ClassVar[List[str]] = ["x", "y", "value"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {}

    # ── 热力图特有选项 ──

    annotate: bool = True
    fmt: str = ".2f"
    color_scheme: str = ""  # 留空由主题决定

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[str]:
        return self.mapping.get("y")

    @property
    def value(self) -> Optional[str]:
        return self.mapping.get("value")

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: str,
        value: str,
        *,
        title: Optional[str] = None,
        annotate: bool = True,
        fmt: str = ".2f",
        color_scheme: str = "",
    ) -> "Heatmap":
        """
        快捷构造热力图。

        Parameters
        ----------
        x : str
            x 轴分类列名
        y : str
            y 轴分类列名
        value : str
            颜色映射的数值列名
        title : str | None
            子图标题
        annotate : bool
            单元格内显示数值
        fmt : str
            数值格式
        color_scheme : str
            颜色方案

        Returns
        -------
        Heatmap
        """
        return cls(
            mapping={"x": x, "y": y, "value": value},
            title=title,
            annotate=annotate,
            fmt=fmt,
            color_scheme=color_scheme,
        )

    # ── 计算需求 ──────────────────────────────────────────

    def compute_requirements(self) -> Dict[str, Any]:
        """
        热力图的计算需求。

        规则:
            - groupby(x, y) → mean(value) 或 count(value)
            - 如果 x-y 组合已在数据中是唯一的（如相关性矩阵），
              则不需要聚合，由 compute/ 层判断。
        """
        group_by: List[str] = []
        if self.x:
            group_by.append(self.x)
        if self.y:
            group_by.append(self.y)

        columns: Dict[str, List[str]] = {}
        if self.value:
            columns[self.value] = ["mean"]

        return {
            "group_by": group_by,
            "columns": columns,
            "preprocess": [],
            "statistics": [],
        }

    # ── 校验 ──────────────────────────────────────────────

    def validate(self, df: "pd.DataFrame") -> List[str]:  # type: ignore[override]
        """
        列存在性校验（委托基类） + x ≠ y 语义校验。
        """
        errors = super().validate(df)
        if self.x and self.y and self.x == self.y:
            errors.append(
                f"[heatmap] x 和 y 不应是同一列 '{self.x}'，"
                f"热力图需要两个不同的分类维度"
            )
        return errors

    # ── 选项导出 ──────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """导出热力图特有的选项（仅非默认值）。"""
        opts: Dict[str, Any] = {}
        if not self.annotate:
            opts["annotate"] = False
        if self.fmt != ".2f":
            opts["fmt"] = self.fmt
        if self.color_scheme:
            opts["color_scheme"] = self.color_scheme
        return opts
