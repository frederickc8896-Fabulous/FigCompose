"""
charts/bar.py
=============
柱状图定义 — 声明柱状图所需的数据字段和计算需求。

设计原则:
    - 只定义"柱状图需要 x/y/error/group/hline/mean_line 字段"
    - 不负责渲染（属于 renderer/）
    - 不负责颜色（属于 themes/）
    - 不做实际计算（属于 compute/）

支持的变体:
    - 单变量柱状图:          x + y
    - 带 error bar:         x + y + error
    - 分组柱状图:            x + y + group
    - 分组 + error:         x + y + group + error
    - 堆叠柱状图:            x + y + group + stacked=True
    - 百分比堆叠:            x + y + group + stacked="percent"
    - 多列宽表堆叠:          x + y=["col1","col2","col3"] + stacked=True
    - 多列百分比堆叠:        x + y=["col1","col2","col3"] + stacked="percent"
    - 固定基准线:            x + y + hline=0.85
    - 整体均值线:            x + y + mean_line=True
    - 水平柱状图:            horizontal=True
    - 双轴 (右轴 y2):       x + y + y2="f1"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import copy
from typing import Optional, Dict, List, Any, ClassVar, Union, Literal

from data_visuals.charts import ChartSpec, register_chart

# ── 类型别名 ─────────────────────────────────────────────────

StackedMode = Union[bool, Literal["percent"]]
YInput = Union[str, List[str]]


@register_chart
@dataclass
class Bar(ChartSpec):
    """
    柱状图规格。

    ── 数据映射 ──
        x            — 分类轴（必需）
        y            — 数值轴（必需）→ 左轴。
                       单列 str 或 多列 List[str]（宽表堆叠时）
        y2           — 右轴列名（可选，启用双 y 轴）
        error        — 误差列名（可选，对应 std/sem 列）
        group        — 分组列名（可选）
                       有 group + stacked=False → 分组并排
                       有 group + stacked=True  → 常规堆叠

    ── 选项 ──
        horizontal   — 是否水平柱状图，默认 False
        stacked      — False: 并排分组 | True: 数值堆叠 | "percent": 百分比堆叠
        hline        — 固定基准线 y 值（可选，如 SOTA 水平线）
        hline_label  — 基准线图例标签
        mean_line    — 是否显示整体均值线
        mean_line_label — 均值线图例标签

    Examples
    --------
    >>> # 基础
    >>> Bar(x="method", y="accuracy")
    >>>
    >>> # 分组并排
    >>> Bar(x="method", y="accuracy", group="dataset")
    >>>
    >>> # 堆叠（长表 group 方式）
    >>> Bar(x="method", y="accuracy", group="dataset", stacked=True)
    >>>
    >>> # 百分比堆叠
    >>> Bar(x="method", y="accuracy", group="dataset", stacked="percent")
    >>>
    >>> # 宽表多列堆叠
    >>> Bar(x="method", y=["accuracy", "precision", "recall"], stacked=True)
    >>>
    >>> # 基准线 + 均值线
    >>> Bar(x="method", y="accuracy", hline=0.85, hline_label="SOTA", mean_line=True)
    >>>
    >>> # 双轴 + 基准线
    >>> Bar(x="method", y="accuracy", y2="f1", hline=0.90)
    """

    chart_type: ClassVar[str] = "bar"

    required_fields: ClassVar[List[str]] = ["x", "y"]
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {
        "error": None,
        "group": None,
        "y2": None,
    }

    # ── 实例字段 ──────────────────────────────────────────

    horizontal: bool = False
    stacked: StackedMode = False

    # 参考线
    hline: Optional[float] = None
    hline_label: str = ""
    mean_line: bool = False
    mean_line_label: str = "Mean"
    show_value: bool = False
    value_format: str = ".2f"

    # ── 属性（从 mapping 提取） ─────────────────────────

    @property
    def x(self) -> Optional[str]:
        return self.mapping.get("x")

    @property
    def y(self) -> Optional[YInput]:
        return self.mapping.get("y")

    @property
    def y_list(self) -> List[str]:
        """将 y 统一为列表形式。"""
        val = self.y
        if val is None:
            return []
        if isinstance(val, str):
            return [val]
        return list(val)

    @property
    def is_multi_y(self) -> bool:
        """是否为多列 y（宽表堆叠模式）。"""
        return len(self.y_list) > 1

    @property
    def y2(self) -> Optional[str]:
        return self.mapping.get("y2")

    @property
    def error(self) -> Optional[str]:
        return self.mapping.get("error")

    @property
    def group(self) -> Optional[str]:
        return self.mapping.get("group")

    # ── 快捷判断 ──────────────────────────────────────────

    @property
    def is_stacked(self) -> bool:
        """是否堆叠（含常规堆叠和百分比堆叠）。"""
        return self.stacked is not False

    @property
    def is_percent_stacked(self) -> bool:
        """是否为百分比堆叠。"""
        return self.stacked == "percent"

    @property
    def is_grouped(self) -> bool:
        """是否为分组并排（有 group 且非堆叠）。"""
        return bool(self.group) and not self.is_stacked

    @property
    def has_reference_lines(self) -> bool:
        """是否有参考线（hline 或 mean_line）。"""
        return self.hline is not None or self.mean_line

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_mapping(
        cls,
        x: str,
        y: YInput,
        *,
        y2: Optional[str] = None,
        error: Optional[str] = None,
        group: Optional[str] = None,
        title: Optional[str] = None,
        horizontal: bool = False,
        stacked: StackedMode = False,
        hline: Optional[float] = None,
        hline_label: str = "",
        mean_line: bool = False,
        mean_line_label: str = "Mean",
        show_value: bool = False,
        value_format: str = ".2f",
    ) -> "Bar":
        """
        快捷构造柱状图。

        Parameters
        ----------
        x : str
            分类轴列名
        y : str | list[str]
            数值轴列名 → 左轴。单列或多列（宽表堆叠）
        y2 : str | None
            右轴列名（双 y 轴）
        error : str | None
            误差列名
        group : str | None
            分组列名
        title : str | None
            子图标题
        horizontal : bool
            水平柱状图
        stacked : bool | "percent"
            堆叠模式
        hline : float | None
            固定基准线 y 值
        hline_label : str
            基准线标签
        mean_line : bool
            显示整体均值线
        mean_line_label : str
            均值线标签

        Returns
        -------
        Bar
        """
        mapping: Dict[str, Any] = {"x": x, "y": y}
        if y2:
            mapping["y2"] = y2
        if error:
            mapping["error"] = error
        if group:
            mapping["group"] = group

        return cls(
            mapping=mapping,
            title=title,
            horizontal=horizontal,
            stacked=stacked,
            hline=hline,
            hline_label=hline_label,
            mean_line=mean_line,
            mean_line_label=mean_line_label,
            show_value=show_value,
            value_format=value_format,
        )

    # ── 校验 ──────────────────────────────────────────────

    def validate(self, df: "pd.DataFrame") -> List[str]:  # type: ignore[override]
        """
        列存在性校验（委托基类） + 柱状图特有语义校验。
        """
        validation_chart = self
        if self.error == "std" and "std" not in df.columns:
            # "std" may request uncertainty computed from repeated y samples.
            validation_chart = copy(self)
            validation_chart.mapping = dict(self.mapping)
            validation_chart.mapping.pop("error")
        errors = ChartSpec.validate(validation_chart, df)

        if self.group and self.is_multi_y:
            errors.append(
                "[bar] 不能同时指定 group 和多列 y。"
                "group 模式使用长表数据（单列 y），多列 y 模式使用宽表数据。"
            )

        if self.is_percent_stacked:
            if not self.group and not self.is_multi_y:
                errors.append(
                    "[bar] 百分比堆叠需要 group 或多列 y 来提供分段依据。"
                )

        return errors

    # ── 计算需求 ──────────────────────────────────────────

    def compute_requirements(self) -> Dict[str, Any]:
        """
        柱状图的计算需求。

        规则:
            ┌─────────────────────┬──────────────────────────────────┐
            │ 条件                 │ 需求                             │
            ├─────────────────────┼──────────────────────────────────┤
            │ 基础                 │ groupby(x) → mean(y)             │
            │ + group              │ groupby(x, group) → mean(y)      │
            │ + 多列 y             │ groupby(x) → mean(y1,y2,y3)      │
            │ + error              │ 额外 std(y)                      │
            │ + y2                 │ 额外 mean(y2)                    │
            │ + mean_line          │ statistics: overall_mean(y...)   │
            │ + stacked="percent"   │ preprocess: normalize_percent    │
            │ + hline              │ 不需要计算                        │
            └─────────────────────┴──────────────────────────────────┘
        """
        group_by: List[str] = [self.x] if self.x else []
        if self.group:
            group_by = [self.x, self.group]  # type: ignore[list-item]

        columns: Dict[str, List[str]] = {}

        # 所有 y 列（多列时每个都是一段）
        for y_col in self.y_list:
            columns[y_col] = ["mean"]

        # 双轴 y2
        if self.y2:
            columns[self.y2] = ["mean"]

        # error: 对 y 列追加 std
        if self.error:
            for y_col in self.y_list:
                if y_col in columns and "std" not in columns[y_col]:
                    columns[y_col].append("std")

        preprocess: List[str] = []
        if self.is_percent_stacked:
            preprocess.append("normalize_percent")

        statistics: List[str] = []
        if self.mean_line:
            statistics.append("overall_mean")

        # hline 不需要计算 — renderer 直接画线

        return {
            "group_by": group_by,
            "columns": columns,
            "preprocess": preprocess,
            "statistics": statistics,
        }

    # ── 选项导出 ──────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """导出柱状图特有的渲染选项（仅非默认值）。"""
        opts: Dict[str, Any] = {}

        if self.horizontal:
            opts["horizontal"] = True

        if self.is_percent_stacked:
            opts["stacked"] = "percent"
        elif self.stacked is True:
            opts["stacked"] = True

        if self.hline is not None:
            opts["hline"] = self.hline
            if self.hline_label:
                opts["hline_label"] = self.hline_label

        if self.mean_line:
            opts["mean_line"] = True
            if self.mean_line_label and self.mean_line_label != "Mean":
                opts["mean_line_label"] = self.mean_line_label

        if self.show_value:
            opts["show_value"] = True
            if self.value_format and self.value_format != ".2f":
                opts["value_format"] = self.value_format

        return opts

    def to_spec(self) -> Dict[str, Any]:
        spec = super().to_spec()
        # 确保多列 y 以 list 形式进入 spec（基类用 mapping.copy 浅复制，引用不变）
        if self.is_multi_y:
            spec["data"]["y"] = self.y_list
        return spec
