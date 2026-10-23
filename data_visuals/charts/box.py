"""
charts/box.py
=============
箱线图定义 — 声明箱线图所需的数据字段和计算需求。

设计原则:
    - 只定义"箱线图需要 x/y/group 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）
    - 不负责实际统计计算（属于 compute/）

箱线图的统计需求:
    groupby(x) → Q1, median, Q3, IQR, outlier detection
    这是所有图表类型中计算需求最复杂的。

支持的变体:
    - 单变量箱线图:      x + y
    - 分组箱线图:        x + y + group
    - 水平箱线图:        horizontal=True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Box(ChartSpec):
    """
    箱线图规格。

    数据映射:
        x       — 分类轴（必需）
        y       — 数值轴（必需）
        group   — 分组列名（可选，用于分组箱线图）

    选项:
        horizontal — 是否水平箱线图，默认 False
        show_outliers — 是否显示异常值点，默认 True
        notch     — 是否显示凹槽（median 置信区间），默认 False

    Examples
    --------
    >>> box = Box(x="method", y="accuracy")
    >>> box.compute_requirements()
    {
        'group_by': ['method'],
        'columns': {},
        'preprocess': [],
        'statistics': ['quartiles', 'iqr', 'outliers']
    }
    """

    chart_type: ClassVar[str] = "box"

    required_fields: ClassVar[List[str]] = ["x", "y"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "group": None,
    }

    # ── 箱线图特有选项 ──

    horizontal: bool = False
    show_outliers: bool = True
    notch: bool = False  # 中位数凹槽
    mean_line: bool = False
    mean_line_label: str = "Mean"

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[str]:
        return self.mapping.get("y")

    @property
    def group(self) -> Optional[str]:
        return self.mapping.get("group")

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: str,
        *,
        group: Optional[str] = None,
        title: Optional[str] = None,
        horizontal: bool = False,
        show_outliers: bool = True,
        notch: bool = False,
        mean_line: bool = False,
        mean_line_label: str = "Mean",
    ) -> "Box":
        """
        快捷构造箱线图。

        Parameters
        ----------
        x : str
            分类轴列名
        y : str
            数值轴列名
        group : str | None
            分组列名
        title : str | None
            子图标题
        horizontal : bool
            水平箱线图
        show_outliers : bool
            显示异常值
        notch : bool
            中位数凹槽

        Returns
        -------
        Box
        """
        mapping: Dict[str, Any] = {"x": x, "y": y}
        if group:
            mapping["group"] = group

        return cls(
            mapping=mapping,
            title=title,
            horizontal=horizontal,
            show_outliers=show_outliers,
            notch=notch,
            mean_line=mean_line,
            mean_line_label=mean_line_label,
        )

    # ── 计算需求 ──────────────────────────────────────────

    def compute_requirements(self) -> Dict[str, Any]:
        """
        箱线图的计算需求。

        箱线图需要分组统计量而非简单聚合:
            - groupby(x) → Q1, median, Q3, IQR
            - 异常值检测 (IQR × 1.5 法则)
            - 有 group 时 → groupby(x, group) → 同上

        这些统计量由 compute/statistics.py 提供，
        compute/aggregation.py 做分组聚合。
        """
        group_by: List[str] = [self.x] if self.x else []
        if self.group:
            group_by = [self.x, self.group]  # type: ignore[list-item]

        return {
            "group_by": group_by,
            "columns": {},  # box 需要分组后逐组计算统计量，不是标准 agg
            "preprocess": [],
            # 告知下游需要哪些统计量
            "statistics": ["quartiles", "iqr"],
        }

    # ── 选项导出 ──────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """导出箱线图特有的选项（仅非默认值）。"""
        opts: Dict[str, Any] = {}
        if self.horizontal:
            opts["horizontal"] = True
        if not self.show_outliers:
            opts["show_outliers"] = False
        if self.notch:
            opts["notch"] = True
        if self.mean_line:
            opts["mean_line"] = True
        if self.mean_line_label:
            opts["mean_line_label"] = self.mean_line_label
        return opts
