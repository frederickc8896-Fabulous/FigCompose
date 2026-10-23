"""
charts/line.py
=============
折线图定义 — 声明折线图所需的数据字段和计算需求。

设计原则:
    - 只定义"折线图需要 x/y/group 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）
    - 不做计算：折线图直接使用原始值，无需聚合

支持的变体:
    - 单线:              x + y
    - 多线 (分组):        x + y + group
    - 多变量线:           x + [y1, y2, ...]
    - 平滑曲线:           smooth=True
    - 面积图:             area=True
    - 带点标记:           markers=True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Union, ClassVar

from data_visuals.charts import ChartSpec, register_chart


@register_chart
@dataclass
class Line(ChartSpec):
    """
    折线图规格。

    数据映射:
        x       — x 轴列名（必需）
        y       — y 轴列名（必需，或 y 轴多列列表）→ 左轴
        y2      — 右轴列名（可选，启用双 y 轴）
        group   — 分组列名（可选，分组后每个 group 值画一条线）

    选项:
        smooth   — 是否平滑曲线，默认 False
        area     — 是否填充区域面积，默认 False
        markers  — 是否显示数据点标记，默认 True

    Examples
    --------
    >>> line = Line(x="epoch", y="loss", group="model")
    >>> line = Line(x="epoch", y="loss", y2="accuracy")  # 双轴
    >>> line.compute_requirements()
    {'group_by': [], 'columns': {}, 'preprocess': []}
    # 折线图无需聚合 — 直接使用原始值
    """

    chart_type: ClassVar[str] = "line"

    required_fields: ClassVar[List[str]] = ["x", "y"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "group": None,
        "y2": None,
    }

    # ── 折线图特有选项 ──

    smooth: bool = False
    area: bool = False
    markers: bool = True
    step: bool = False  # 阶梯线图

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[Union[str, List[str]]]:
        return self.mapping.get("y")

    @property
    def y2(self) -> Optional[str]:
        """右轴列名（双 y 轴时使用）。"""
        return self.mapping.get("y2")

    @property
    def group(self) -> Optional[str]:
        return self.mapping.get("group")

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: Union[str, List[str]],
        *,
        y2: Optional[str] = None,
        group: Optional[str] = None,
        title: Optional[str] = None,
        smooth: bool = False,
        area: bool = False,
        markers: bool = True,
        step: bool = False,
    ) -> "Line":
        """
        快捷构造折线图。

        Parameters
        ----------
        x : str
            x 轴列名
        y : str | list[str]
            y 轴列名（支持多列）→ 左轴
        y2 : str | None
            右轴列名（可选，启用双 y 轴）
        group : str | None
            分组列名
        title : str | None
            子图标题
        smooth : bool
            平滑曲线
        area : bool
            填充面积
        markers : bool
            显示数据点标记
        step : bool
            阶梯线图

        Returns
        -------
        Line
        """
        mapping: Dict[str, Any] = {"x": x, "y": y}
        if y2:
            mapping["y2"] = y2
        if group:
            mapping["group"] = group

        return cls(
            mapping=mapping,
            title=title,
            smooth=smooth,
            area=area,
            markers=markers,
            step=step,
        )


    # ── 选项导出 ──────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """导出折线图特有的选项（仅非默认值）。"""
        opts: Dict[str, Any] = {}
        if self.smooth:
            opts["smooth"] = True
        if self.area:
            opts["area"] = True
        if not self.markers:
            opts["markers"] = False
        if self.step:
            opts["step"] = True
        return opts
