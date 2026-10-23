"""
charts/ — 图表类型定义层
========================

图表层只定义"画什么"：声明每个图表类型需要的数据字段映射，
以及触发哪些统计计算。不涉及渲染、颜色、布局。

设计原则（来自架构文档）：
    Chart 决定"画什么"，Compute 决定"怎么算"，
    Layout 决定"放哪里"，Theme 决定"长什么样"。

每条边界永不互侵 → 永不退化为 matplotlib 参数堆积。

支持图表类型：
    - bar      — 柱状图（支持 error bar）
    - line     — 折线图
    - scatter  — 散点图
    - box      — 箱线图
    - heatmap  — 热力图
    - histogram — 直方图
    - confusion — 混淆矩阵
    - pie / donut — 饼图与环形图
    - radar — 雷达图
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Optional, Dict, List, Any, Type, ClassVar

import pandas as pd


# ── 图表类型枚举 ──────────────────────────────────────────────

ChartType = str  # Names are resolved through the chart registry below.


# ═══════════════════════════════════════════════════════════════
# 基类：ChartSpec
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChartSpec:
    """
    图表类型规格基类。

    每个子类声明：
        - required_fields: 必须提供的数据列映射键
        - optional_fields: 可选的数据列映射键及其默认值
        - compute_ops:     该图表类型需要触发的统计计算操作

    实例化后可通过 .to_spec() 导出为 FigureSpec 的 chart 片段，
    或通过 .compute_requirements() 告知 compute 层该执行什么聚合。
    """

    # ── 子类覆盖的类变量 ──

    # 图表类型名称，子类必须覆盖
    chart_type: ClassVar[str] = ""

    # 必需的数据映射键（如 ["x", "y"]）
    required_fields: ClassVar[List[str]] = []

    # 可选的数据映射键，key=字段名, value=默认值（None 表示无默认值）
    optional_fields: ClassVar[Dict[str, Optional[str]]] = {}

    # ── 实例字段 ──

    # 数据映射：用户声明的 x/y/group/error 等 → CSV 列名
    mapping: Dict[str, Any] = field(default_factory=dict)

    # 子图标题（可选）
    title: Optional[str] = None

    def __post_init__(self) -> None:
        """校验子类声明的 chart_type 非空。"""
        if not self.__class__.chart_type:
            raise ValueError(f"{self.__class__.__name__} 必须定义 chart_type 类变量")

    # ── 校验 ──────────────────────────────────────────────

    def validate(self, df: pd.DataFrame) -> List[str]:
        """
        校验数据映射中引用的所有列是否在 DataFrame 中存在。

        遍历 required_fields + optional_fields 中已赋值的字段，
        自动处理 str 和 List[str] 两种值类型。

        Parameters
        ----------
        df : pd.DataFrame
            数据源

        Returns
        -------
        list[str] — 错误信息列表，空列表表示校验通过
        """
        errors: List[str] = []

        fields_to_check: set = set(self.__class__.required_fields)
        fields_to_check.update(self.__class__.optional_fields.keys())

        for field_name in fields_to_check:
            col_name = self.mapping.get(field_name)
            if col_name is None:
                continue  # 可选字段未提供

            if isinstance(col_name, str):
                if col_name not in df.columns:
                    errors.append(
                        f"[{self.chart_type}] 字段 '{field_name}' 映射到列 "
                        f"'{col_name}'，但该列不存在于数据中。"
                        f"有效列: {list(df.columns)}"
                    )
            elif isinstance(col_name, list):
                for cn in col_name:
                    if isinstance(cn, str) and cn not in df.columns:
                        errors.append(
                            f"[{self.chart_type}] 字段 '{field_name}' 中的列 "
                            f"'{cn}' 不存在于数据中。"
                            f"有效列: {list(df.columns)}"
                        )

        return errors

    def validate_fields(self, user_mapping: Dict[str, Any]) -> List[str]:
        """
        校验用户提供的映射是否包含所有必需字段。

        Parameters
        ----------
        user_mapping : dict
            用户提供的数据映射

        Returns
        -------
        list[str] — 缺失字段名列表
        """
        missing = []
        for f in self.__class__.required_fields:
            if f not in user_mapping or user_mapping[f] is None:
                missing.append(f)
        return missing

    # ── 计算需求 ──────────────────────────────────────────

    def compute_requirements(self) -> Dict[str, Any]:
        """
        返回该图表类型所需的统计计算描述。

        子类覆盖此方法以声明具体的聚合需求。
        返回格式供 compute/ 层消费：
            {
                "group_by": ["col1", "col2"],     # 分组列名
                "columns": {                       # 需聚合的列 → 算子列表
                    "col_name": ["mean", "std"]
                },
                "preprocess": [...],               # 预处理操作
                "statistics": [...],               # 额外统计量
            }

        Returns
        -------
        dict
        """
        return {
            "group_by": [],
            "columns": {},
            "preprocess": [],
            "statistics": [],
        }

    # ── 导出 ──────────────────────────────────────────────

    def _chart_options(self) -> Dict[str, Any]:
        """
        子类覆盖此方法，返回仅非默认值的渲染选项。

        只导出值不为默认值的选项 → spec 精简、无冗余。
        """
        return {}

    def to_spec(self) -> Dict[str, Any]:
        """
        导出为 FigureSpec 中 chart 片段的 dict 格式。

        Returns
        -------
        dict — 可直接合并到 FigureSpec["charts"][i] 中
        """
        spec: Dict[str, Any] = {
            "chart": self.chart_type,
            "data": self.mapping.copy(),
        }
        if self.title:
            spec["title"] = self.title
        opts = self._chart_options()
        if opts:
            spec["options"] = opts
        return spec

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v}" for k, v in self.mapping.items())
        return f"{self.__class__.__name__}({fields})"


# ═══════════════════════════════════════════════════════════════
# 图表注册中心
# ═══════════════════════════════════════════════════════════════

# name → ChartSpec 子类
_chart_registry: Dict[str, Type[ChartSpec]] = {}


def register_chart(cls: Type[ChartSpec]) -> Type[ChartSpec]:
    """装饰器：注册图表类型到全局注册表。"""
    chart_type = cls.chart_type
    if not chart_type:
        raise ValueError(f"{cls.__name__} 必须定义 chart_type 类变量")
    _chart_registry[chart_type] = cls
    return cls


def get_chart(chart_type: str) -> Type[ChartSpec]:
    """
    按名称获取图表类型类。

    Parameters
    ----------
    chart_type : str
        图表类型名称，可通过 list_chart_types() 查询。

    Returns
    -------
    type[ChartSpec]

    Raises
    ------
    ValueError — 未知的图表类型
    """
    if chart_type not in _chart_registry:
        raise ValueError(
            f"未知图表类型 '{chart_type}'。"
            f"已注册类型: {list_chart_types()}"
        )
    return _chart_registry[chart_type]


def list_chart_types() -> List[str]:
    """列出所有已注册的图表类型名称。"""
    return sorted(_chart_registry.keys())


def create_chart(
    chart_type: str,
    mapping: Dict[str, Any],
    *,
    title: Optional[str] = None,
) -> ChartSpec:
    """
    工厂函数：按名称创建图表规格实例。

    Parameters
    ----------
    chart_type : str
        图表类型名称
    mapping : dict
        数据映射，如 {"x": "method", "y": "accuracy", "error": "std"}
    title : str | None
        子图标题

    Returns
    -------
    ChartSpec 实例

    Examples
    --------
    >>> chart = create_chart("bar", {"x": "method", "y": "accuracy", "error": "std"})
    >>> chart.chart_type
    'bar'
    >>> chart.compute_requirements()
    {'group_by': ['method'], 'columns': {'accuracy': ['mean', 'std']}}
    """
    cls = get_chart(chart_type)

    if chart_type in {"pie", "donut"} and ("x" in mapping or "y" in mapping):
        raise ValueError(
            f"[{chart_type}] 饼图使用 group='类别列' 和 value='数量列'，不使用 x/y。"
            "省略 value 时按类别统计行数；快捷 API 的 metric 对应 value。"
        )

    mapping_fields = set(cls.required_fields) | set(cls.optional_fields.keys())
    chart_field_names = {
        field.name
        for field in dataclass_fields(cls)
        if field.init and field.name not in {"mapping", "title"}
    }

    pure_mapping: Dict[str, Any] = {}
    option_kwargs: Dict[str, Any] = {}
    unknown_keys: List[str] = []

    for key, value in mapping.items():
        if key in mapping_fields:
            pure_mapping[key] = value
        elif key in chart_field_names:
            option_kwargs[key] = value
        else:
            unknown_keys.append(key)

    if unknown_keys:
        raise ValueError(
            f"[{chart_type}] 未知参数: {unknown_keys}。"
            f"支持的数据映射: {sorted(mapping_fields)}；"
            f"支持的图表选项: {sorted(chart_field_names)}"
        )

    instance = cls(mapping=pure_mapping, title=title, **option_kwargs)
    missing = instance.validate_fields(pure_mapping)
    if missing:
        raise ValueError(
            f"[{chart_type}] 缺少必需字段: {missing}。"
            f"必需: {cls.required_fields}"
        )
    return instance


# ── 导入所有图表子类，触发 @register_chart 注册 ─────────────
# 放在文件末尾避免循环导入
from data_visuals.charts.bar import Bar  # noqa: E402, F401
from data_visuals.charts.line import Line  # noqa: E402, F401
from data_visuals.charts.scatter import Scatter  # noqa: E402, F401
from data_visuals.charts.box import Box  # noqa: E402, F401
from data_visuals.charts.heatmap import Heatmap  # noqa: E402, F401
from data_visuals.charts.histogram import Histogram  # noqa: E402, F401
from data_visuals.charts.confusion import Confusion  # noqa: E402, F401
from data_visuals.charts.pie import Pie, Donut  # noqa: E402, F401
from data_visuals.charts.radar import Radar  # noqa: E402, F401

