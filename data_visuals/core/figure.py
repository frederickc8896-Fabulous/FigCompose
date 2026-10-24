"""
core/figure.py
==============
Figure — 顶层用户 API 入口。

职责:
    - 接收用户输入 (data + layout + chart 声明 + 配置)
    - 编排 data → compute → layout → FigureSpec 全链路
    - 提供 .build() 产出 FigureSpec（供 renderer 消费）

不负责:
    - 实际统计计算 (属于 compute/)
    - 布局几何计算 (属于 layout/)
    - 渲染导出 (属于 renderer/)

设计原则（来自架构文档）:
    用户只需声明 x/y/layout，无需调 figsize/dpi/font/color。
"""

from __future__ import annotations

from typing import Optional, Dict, List, Any, Union, Tuple, Sequence
from dataclasses import fields as dataclass_fields
from collections.abc import Mapping
from copy import deepcopy
from numbers import Real
import warnings

import pandas as pd
import numpy as np

from data_visuals.core.config import FigureConfig, get_default_config
from data_visuals.core.canvas import normalize_canvas
from data_visuals.core.legend import merge_legend, normalize_legend
from data_visuals.core.identity import normalize_fields, normalize_series
from data_visuals.core.metadata import field_label, resolve_field_options
from data_visuals.core.spec import FigureSpec, SubplotSpec
from data_visuals.core.panel import CustomPanel
from data_visuals.charts import (
    ChartSpec,
    create_chart,
    list_chart_types,
    get_chart,
)
from data_visuals.layout.manager import build_layout
from data_visuals.layout.shared import detect_shared_axes
from data_visuals.data.schema import infer_column_types, validate_header, check_numeric_columns
from data_visuals.data.loader import load_csv
from data_visuals.data.labels import resolve_labels
from data_visuals.compute.aggregation import aggregate, mean_repeated_series
from data_visuals.compute.preprocess import normalize_percent_frame, complete_cartesian_grid, normalize_group_sum
from data_visuals.compute.statistics import overall_mean, loess_smooth, density_curve, boxplot_payload


def _filter_subplot_data(
    df: pd.DataFrame, where: Any, row: int, col: int,
) -> pd.DataFrame:
    """Apply declarative AND filters before chart validation and computation."""
    if where is None:
        return df
    prefix = f"子图 [{row},{col}] where"
    if not isinstance(where, Mapping):
        raise ValueError(f"{prefix} 必须是字典 {{列名: 标量或非空列表}}。")
    if not where:
        return df

    mask = pd.Series(True, index=df.index)
    for column, value in where.items():
        if not isinstance(column, str) or not column:
            raise ValueError(f"{prefix} 的列名必须是非空字符串，收到 {column!r}。")
        if column not in df.columns:
            raise ValueError(f"{prefix} 引用了不存在的列 '{column}'。")
        values = value if isinstance(value, list) else [value]
        if not values or any(not pd.api.types.is_scalar(item) for item in values):
            raise ValueError(
                f"{prefix}['{column}'] 必须是标量或非空标量列表，收到 {value!r}。"
            )
        # All null spellings select missing values, including nullable dtypes.
        non_null = [item for item in values if not pd.isna(item)]
        matches = df[column].isin(non_null)
        if len(non_null) != len(values):
            matches |= df[column].isna()
        mask &= matches

    result = df.loc[mask].copy()
    if result.empty:
        raise ValueError(f"{prefix}={dict(where)!r} 过滤后没有数据。请检查筛选值。")
    return result


# ═══════════════════════════════════════════════════════════════
# SubplotBuilder — 用户声明单子图的 DSL
# ═══════════════════════════════════════════════════════════════

class SubplotBuilder:
    """绑定到 Figure 中特定 (row, col) 的子图声明器。

    用法:
        fig[0, 0].bar(x="method", y="accuracy", error="std")
        fig[0, 1].line(x="epoch", y="loss")
    """

    def __init__(self, figure: "Figure", row: int, col: int) -> None:
        self._figure = figure
        self._row = row
        self._col = col

    def set(self, chart_type: str, **mapping: Any) -> "SubplotBuilder":
        """
        通用子图声明。

        Parameters
        ----------
        chart_type : str
            图表类型，通过 list_chart_types() 查询；原生绘制函数使用 custom()。
        title : str | None
            子图标题（可选关键词）
        y_columns : list[str] | None
            仅绘制 group 列中的这些值，其余行被过滤。
        labels : dict[str, str] | None
            显示名映射 {raw_value: display_name}。
        chart_opts : dict | None
            图表级选项，如 mean_line=True。会被合并到 chart.options 中。
        where : dict[str, scalar | list] | None
            在统计计算前筛选此子图的数据。列之间取交集，列表取任一值；
            None 值匹配缺失数据。全局分类颜色仍基于完整源数据确定。
        **mapping : Any
            数据映射: x, y, error, group, size, value 等
        """
        title = mapping.pop("title", None)
        y_columns = mapping.pop("y_columns", None)
        labels = mapping.pop("labels", None)
        domain = mapping.pop("domain", None)
        chart_opts = mapping.pop("chart_opts", None)
        where = mapping.pop("where", None)
        self._figure._set_subplot(
            self._row, self._col, chart_type, mapping,
            title=title, y_columns=y_columns, labels=labels, domain=domain,
            chart_opts=chart_opts,
            where=where,
        )
        return self

    def custom(
        self,
        draw,
        *,
        title: Optional[str] = None,
        payload: Any = None,
        min_size: Tuple[float, float] = (72.0, 48.0),
        preferred_aspect: float = 1.75,
        box_aspect: Optional[float] = None,
        axes: str = "off",
        limits: Optional[Sequence[Tuple[float, float]]] = None,
        projection: Optional[str] = None,
        axes_options: Optional[Mapping[str, Any]] = None,
        color_group: Optional[str] = None,
        categories: Optional[Sequence[Any]] = None,
        legend: Optional[Union[Dict[str, Any], bool]] = None,
    ) -> "SubplotBuilder":
        """Draw a custom Matplotlib panel inside the measured Figure layout.

        ``draw(ax, context)`` draws into the allocated axes and returns ``None``
        or ``PanelResult``. The framework owns the Figure, titles, legends and
        export; the callback owns the panel's nodes, text and connections.
        Dimensions in ``min_size`` are points; ``box_aspect`` is width/height.
        No DataFrame is required for a Figure containing only custom panels.
        ``projection`` chooses a registered Matplotlib Axes projection;
        ``axes_options`` supplies its native constructor options. Projected
        panels keep native ranges when ``limits`` is omitted.
        """
        panel = CustomPanel(
            draw=draw, payload=payload, min_size=min_size,
            preferred_aspect=preferred_aspect, box_aspect=box_aspect,
            axes=axes, limits=limits, projection=projection, axes_options=axes_options,
            color_group=color_group,
            categories=categories,
        )
        options = {} if legend is None else {"legend": normalize_legend(legend)}
        self._figure._subplot_decls[(self._row, self._col)] = {
            "chart_type": "custom",
            "mapping": {"group": color_group} if color_group is not None else {},
            "title": title,
            "chart_opts": options,
            "custom_panel": panel,
        }
        self._figure._spec = None
        return self

    def __getattr__(self, name: str):
        """支持 fig[0,0].bar(x=..., y=...) 语法糖。

        将 bar/line/scatter/box/heatmap 方法动态映射到 set()。
        """
        if name in list_chart_types():
            def _bind(**kwargs: Any) -> "SubplotBuilder":
                return self.set(name, **kwargs)
            return _bind
        raise AttributeError(
            f"SubplotBuilder 没有属性 '{name}'。"
            f"支持的图表类型: {list_chart_types()}"
        )


# ═══════════════════════════════════════════════════════════════
# Figure — 顶层 API
# ═══════════════════════════════════════════════════════════════

class Figure:
    """论文图表顶层入口。

    用法:
        >>> fig = Figure(data=df, rows=2, cols=2, theme="general")
        >>> fig[0, 0].bar(x="method", y="accuracy", error="std")
        >>> fig[0, 1].line(x="epoch", y="loss")
        >>> fig[1, 0].scatter(x="param", y="f1")
        >>> fig[1, 1].box(x="method", y="accuracy")
        >>> spec = fig.build()  # → FigureSpec
    """

    def __init__(
        self,
        data: Optional[pd.DataFrame] = None,
        *,
        # ── Layout 声明 ──
        rows: Optional[int] = None,
        cols: Optional[int] = None,
        layout: Optional[List[List[Union[int, Tuple[int, int], None]]]] = None,
        width_ratios: Optional[List[float]] = None,
        height_ratios: Optional[List[float]] = None,
        # ── 画布 ──
        canvas: Optional[Dict[str, Any]] = None,
        aspect: Optional[str] = None,
        base: Optional[str] = None,
        cell_base: Optional[str] = None,
        # ── 主题 / 配置 ──
        theme: Optional[str] = None,
        palette: Optional[str] = None,
        config: Optional[FigureConfig] = None,
        # ── 全局元信息 ──
        title: Optional[str] = None,
        # ── Legend ──
        legend: Optional[Union[Dict[str, Any], bool]] = None,
        legend_max_entries: Optional[int] = None,
        legend_position: Optional[str] = None,
        # ── 高级 ──
        dpi: Optional[int] = None,
        auto_margins: Optional[bool] = None,
    ) -> None:
        """构建 Figure 实例。

        Parameters
        ----------
        data : pd.DataFrame | None
            原始数据。可为 None（之后通过 add_data 追加）
        rows, cols : int | None
            均匀网格行列数。与 layout 互斥。
        layout : list[list] | None
            混合布局矩阵。优先级高于 rows/cols。
        width_ratios, height_ratios : list[float] | None
            仅在均匀网格模式下生效。按整张画布的可用宽高分配列宽/行高，
            类似 matplotlib GridSpec 的 ratio 定义。
        canvas : dict | None
            整图物理尺寸，例如 {"width": 180, "height": 110, "unit": "mm"}。
            省略 height 自动求解；省略 canvas 使用配置的默认物理宽度。
        aspect : str | None
            旧尺寸路径的画布宽高比；显式提供时保持兼容行为。
        base : str | None
            旧尺寸路径的尺寸档位，默认 "large"；不可与显式 canvas 混用。
        theme : str | None
            主题名，默认 "general"，也可选 "modern"
        palette : str | None
            原始精选整图配色，例如 curated-5-default；默认沿用主题
        config : FigureConfig | None
            全局配置对象（覆盖所有默认值）
        title : str | None
            全局标题
        legend_max_entries : int | None
            legend 最大条目数，None 为自动推断
        legend : dict | bool | None
            统一图例配置；局部 chart_opts.legend 按字段覆盖。距离与字号以 pt 计。
        legend_position : str | None
            legend 默认位置
        dpi : int | None
            输出 DPI
        auto_margins : bool
            是否自动推算边距
        """
        # ── 数据 ──
        self._data: Optional[pd.DataFrame] = data

        # ── 配置 ──
        cfg = config if config is not None else get_default_config()
        if not isinstance(cfg, FigureConfig):
            raise TypeError("config must be a FigureConfig; use FigureConfig.from_dict() or .load().")

        legacy_fields = {
            key for key, value in {"aspect": aspect, "base": base, "cell_base": cell_base}.items()
            if value is not None
        } | set(cfg.legacy_size_fields())
        explicit_canvas = canvas is not None or cfg.has_explicit_canvas()
        if explicit_canvas and legacy_fields:
            raise ValueError("显式 canvas 不能与显式旧尺寸参数 aspect/base/cell_base 同时使用。")
        self._canvas_request = (
            None if legacy_fields else normalize_canvas(canvas, default=cfg.canvas)
        )
        # False preserves an advanced Figure's declared topology. The simple
        # API replaces this with None or its optional maximum column count.
        self._auto_cols: Union[bool, int, None] = False

        self._theme = theme or cfg.theme
        self._palette = palette if palette is not None else cfg.palette
        self._aspect = aspect or cfg.aspect or "16:10"
        self._base = base or cfg.base or "large"
        self._cell_base = cell_base or cfg.cell_base
        self._dpi = dpi if dpi is not None else cfg.dpi
        self._title = title if title is not None else cfg.title
        self._legend_max_entries = legend_max_entries if legend_max_entries is not None else cfg.legend_max_entries
        self._legend_position = legend_position or cfg.legend_position
        self._legend = merge_legend(cfg.legend, legend)
        self._auto_margins = cfg.auto_margins if auto_margins is None else auto_margins
        self._font_family = cfg.font_family
        self._background = cfg.background
        self._facets = deepcopy(cfg.facets)
        self._category_colors = {
            column: dict(colors) for column, colors in cfg.category_colors.items()
        }
        self._fields = normalize_fields(cfg.fields)
        self._series = normalize_series(cfg.series)

        # ── Layout 解析 ──
        self._layout_matrix = layout
        self._rows = rows
        self._cols = cols
        self._width_ratios = width_ratios
        self._height_ratios = height_ratios

        if layout is not None:
            from data_visuals.layout.grid import parse_layout_weights
            self._rows, self._cols = parse_layout_weights(layout)
        else:
            if rows is None:
                self._rows = 2
            if cols is None:
                self._cols = 2

        # ── 子图声明 ──
        self._subplot_decls: Dict[Tuple[int, int], Dict[str, Any]] = {}

        # ── 构建结果缓存 ──
        self._spec: Optional[FigureSpec] = None

    # ── 数据 ──────────────────────────────────────────────

    @property
    def data(self) -> Optional[pd.DataFrame]:
        return self._data

    @data.setter
    def data(self, df: pd.DataFrame) -> None:
        self._data = df
        self._spec = None  # 数据变更后需重建

    @classmethod
    def from_csv(cls, path: str, **kwargs: Any) -> "Figure":
        """从 CSV 文件读取数据并创建 Figure。"""
        df = load_csv(path)
        return cls(data=df, **kwargs)

    def add_data(self, df: pd.DataFrame) -> "Figure":
        """追加数据（合并到现有 DataFrame）。"""
        if self._data is None:
            self._data = df
        else:
            self._data = pd.concat([self._data, df], ignore_index=True)
        self._spec = None
        return self

    # ── 子图声明 DSL ─────────────────────────────────────

    def __getitem__(self, key: Tuple[int, int]) -> SubplotBuilder:
        """支持 fig[0, 0].bar(...) 语法。

        Parameters
        ----------
        key : (row, col)

        Returns
        -------
        SubplotBuilder
        """
        if not isinstance(key, tuple) or len(key) != 2:
            raise TypeError(
                "Figure 索引必须是 (row, col) 元组，例如 fig[0, 0]"
            )
        row, col = key
        if not isinstance(row, int) or not isinstance(col, int):
            raise TypeError("行列索引必须是整数")
        if row < 0 or row >= self._rows:
            raise IndexError(
                f"行索引 {row} 超出范围 [0, {self._rows - 1}]"
            )
        if col < 0 or col >= self._cols:
            raise IndexError(
                f"列索引 {col} 超出范围 [0, {self._cols - 1}]"
            )
        return SubplotBuilder(self, row, col)

    def _set_subplot(
        self,
        row: int,
        col: int,
        chart_type: str,
        mapping: Dict[str, Any],
        *,
        title: Optional[str] = None,
        y_columns: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        domain: Optional[List[float]] = None,
        chart_opts: Optional[Dict[str, Any]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """内部方法：记录用户声明。"""
        # 校验图表类型
        get_chart(chart_type)  # 不存在会抛 ValueError

        if chart_opts is not None:
            if not isinstance(chart_opts, Mapping):
                raise ValueError("chart_opts must be a mapping")
            chart_opts = deepcopy(dict(chart_opts))
            if "legend" in chart_opts:
                chart_opts["legend"] = normalize_legend(chart_opts["legend"])

        self._subplot_decls[(row, col)] = {
            "chart_type": chart_type,
            "mapping": mapping,
            "title": title,
            "y_columns": y_columns,
            "labels": labels,
            "domain": domain,
            "chart_opts": chart_opts,
            "where": deepcopy(where),
        }
        self._spec = None

    # ── 构建 ──────────────────────────────────────────────

    def build(self) -> FigureSpec:
        """
        编排全链路: data → compute → layout → FigureSpec。

        1. 为每个子图创建 ChartSpec → 提取 compute_requirements
        2. 按 compute_requirements 执行聚合
        3. 调用 build_layout 获取几何/字体/Legend 占位
        4. 检测共享轴
        5. 组装 FigureSpec

        Returns
        -------
        FigureSpec

        Raises
        ------
        ValueError
            如果统计子图缺少 DataFrame，或子图声明为空。
        """
        if self._spec is not None:
            return self._spec

        if self._data is None and (
            not self._subplot_decls
            or any(decl["chart_type"] != "custom" for decl in self._subplot_decls.values())
        ):
            raise ValueError(
                "Figure 没有数据。请通过 Figure(data=df) 或 .add_data(df) 提供。"
            )

        if not self._subplot_decls:
            raise ValueError(
                "Figure 没有子图声明。请使用 fig[row, col].bar(...) 等语法。"
            )

        df = self._data

        # ── Step 0: 数据完整性前置校验 ──
        _hdr_warnings = validate_header(df, source_hint="Figure.data") if df is not None else []
        for w in _hdr_warnings:
            warnings.warn(w, stacklevel=2)

        # ── Step 1: 创建 ChartSpec，提取计算需求 ──
        chart_specs: Dict[Tuple[int, int], ChartSpec] = {}
        compute_reqs: Dict[Tuple[int, int], Dict[str, Any]] = {}
        panel_data: Dict[Tuple[int, int], pd.DataFrame] = {}

        for (row, col), decl in self._subplot_decls.items():
            if decl["chart_type"] == "custom":
                continue
            panel_df = _filter_subplot_data(df, decl.get("where"), row, col)
            panel_data[(row, col)] = panel_df
            ct = decl["chart_type"]
            mapping = dict(decl["mapping"])
            # Typed options must reach ChartSpec before validation and compute.
            # Renderer-only options (e.g. color_scheme) stay in chart_options.
            chart_class = get_chart(ct)
            option_fields = {
                item.name for item in dataclass_fields(chart_class)
                if item.init and item.name not in {"mapping", "title"}
            }
            mapping.update({
                key: value for key, value in (decl.get("chart_opts") or {}).items()
                if key in option_fields
            })
            subplot_title = decl.get("title")
            chart = create_chart(ct, mapping, title=subplot_title)
            # 校验
            errors = chart.validate(panel_df)
            if errors:
                raise ValueError(f"子图 [{row},{col}] ({ct}) 校验失败:\n" +
                                 "\n".join(f"  - {e}" for e in errors))
            # Axis options have one contract across statistical chart types.
            # Include typed options (notably horizontal) before checking which
            # displayed axis is categorical. Leave radar's native ylim to its
            # own ChartSpec validation.
            from data_visuals.renderer.mpl.axes import validate_axis_options
            axis_options = dict(chart.to_spec().get("options", {}))
            axis_options.update(decl.get("chart_opts") or {})
            validate_axis_options(ct, axis_options)
            chart_specs[(row, col)] = chart
            compute_reqs[(row, col)] = chart.compute_requirements()
            # Existing error columns contain precomputed uncertainty. Preserve
            # their mean rather than calculating the std of those std values.
            if ct == "bar":
                error_col = chart.mapping.get("error")
                if error_col and error_col in panel_df.columns and error_col not in chart.y_list:
                    compute_reqs[(row, col)]["columns"].setdefault(error_col, ["mean"])

        # ── Step 2: 执行计算 ──
        computed: Dict[Tuple[int, int], pd.DataFrame] = {}
        derived: Dict[Tuple[int, int], Dict[str, Any]] = {}
        for (row, col), req in compute_reqs.items():
            panel_df = panel_data[(row, col)]
            gb = req.get("group_by", [])
            cols = req.get("columns", {})
            derived[(row, col)] = {}
            chart = chart_specs.get((row, col))
            if chart and chart.chart_type in {"pie", "donut", "radar"}:
                # Observe only supplied categories. Categorical dtypes can
                # otherwise synthesize absent radar axes or zero-size slices.
                value = chart.mapping.get("value")
                source = panel_df
                if chart.chart_type in {"pie", "donut"} and value:
                    # Integer groupby sums can wrap before the renderer ever
                    # sees them. Amounts are real quantities; sum in float64
                    # without changing the caller's DataFrame or row counts.
                    source = panel_df.assign(**{value: panel_df[value].astype("float64")})
                grouped = source.groupby(gb, sort=False, observed=True, dropna=False)
                if chart.chart_type in {"pie", "donut"}:
                    value = chart.mapping.get("value")
                    if value:
                        result = grouped[value].sum().rename(f"{value}_sum")
                    else:
                        result = grouped.size().rename(f"{chart.mapping['group']}_count")
                    amounts = result.to_numpy(dtype=float)
                    if not np.isfinite(amounts).all() or (amounts < 0).any():
                        raise ValueError(
                            f"子图 [{row},{col}] ({chart.chart_type}) 聚合后的数量必须是有限非负数。"
                        )
                else:
                    value = chart.mapping["y"]
                    result = grouped[value].mean().rename(f"{value}_mean")
                computed[(row, col)] = result.reset_index()
            elif gb and cols:
                computed[(row, col)] = aggregate(panel_df, group_by=gb, columns=cols)
            else:
                # line/scatter: 不需要聚合，直接引用原始数据
                computed[(row, col)] = panel_df.copy()

            if not chart:
                continue
            if chart.chart_type == "line":
                y_columns = chart.mapping["y"]
                values = [y_columns] if isinstance(y_columns, str) else list(y_columns)
                if chart.mapping.get("y2"):
                    values.append(chart.mapping["y2"])
                computed[(row, col)] = mean_repeated_series(
                    panel_df, x_col=chart.mapping["x"], value_cols=values,
                    group_col=chart.mapping.get("group"),
                )
            if chart.chart_type == "bar":
                error_col = chart.mapping.get("error")
                if error_col and error_col in panel_df.columns and error_col not in chart.y_list:
                    error_mean = f"{error_col}_mean"
                    if error_mean in computed[(row, col)].columns:
                        computed[(row, col)][error_col] = computed[(row, col)][error_mean]

            preprocess_ops = req.get("preprocess", [])
            if "normalize_percent" in preprocess_ops:
                value_cols = [
                    f"{y_col}_mean" if f"{y_col}_mean" in computed[(row, col)].columns else y_col
                    for y_col in getattr(chart, "y_list", []) or ([chart.mapping.get("y")] if chart.mapping.get("y") else [])
                    if y_col is not None
                ]
                group_keys = [chart.mapping.get("x")]
                if chart.mapping.get("group"):
                    group_keys = [chart.mapping.get("x")]
                else:
                    group_keys = None
                computed[(row, col)] = normalize_percent_frame(
                    computed[(row, col)],
                    value_cols,
                    group_keys=group_keys,
                )

            statistics_ops = req.get("statistics", [])
            if "overall_mean" in statistics_ops:
                mean_columns = [
                    f"{y_col}_mean" if f"{y_col}_mean" in computed[(row, col)].columns else y_col
                    for y_col in getattr(chart, "y_list", []) or ([chart.mapping.get("y")] if chart.mapping.get("y") else [])
                    if y_col is not None
                ]
                derived[(row, col)]["overall_mean"] = overall_mean(computed[(row, col)], mean_columns)

            chart_type = chart.chart_type
            if chart_type == "scatter" and getattr(chart, "trend", False):
                x_col = chart.mapping.get("x")
                y_col = chart.mapping.get("y")
                group_col = chart.mapping.get("group")
                if isinstance(x_col, str) and isinstance(y_col, str):
                    derived[(row, col)]["trend_data"] = loess_smooth(
                        panel_df,
                        x_col=x_col,
                        y_col=y_col,
                        group_col=group_col if isinstance(group_col, str) else None,
                    )

            if chart_type == "histogram" and getattr(chart, "density", False):
                x_col = chart.mapping.get("x")
                group_col = chart.mapping.get("group")
                if isinstance(x_col, str):
                    derived[(row, col)]["density_data"] = density_curve(
                        panel_df,
                        value_col=x_col,
                        group_col=group_col if isinstance(group_col, str) else None,
                    )

            if chart_type == "confusion":
                x_col = chart.mapping.get("x")
                y_col = chart.mapping.get("y")
                if isinstance(x_col, str) and isinstance(y_col, str):
                    explicit_value = chart.mapping.get("value")
                    value_col = f"{explicit_value}_sum" if explicit_value else f"{x_col}_count"
                    if explicit_value:
                        computed[(row, col)][explicit_value] = computed[(row, col)][value_col]
                        value_col = explicit_value
                    confusion_df = complete_cartesian_grid(
                        computed[(row, col)],
                        x_col,
                        y_col,
                        value_col,
                        fill_value=0.0,
                    )
                    if getattr(chart, "normalize", False):
                        confusion_df = normalize_group_sum(
                            confusion_df,
                            group_col=y_col,
                            value_col=value_col,
                        )
                    computed[(row, col)] = confusion_df
                    derived[(row, col)]["confusion_matrix"] = confusion_df.copy()

            if chart_type == "box":
                x_col = chart.mapping.get("x")
                y_col = chart.mapping.get("y")
                group_col = chart.mapping.get("group")
                if isinstance(x_col, str) and isinstance(y_col, str):
                    group_by = [x_col]
                    if isinstance(group_col, str):
                        group_by.append(group_col)
                    summary_df, outliers_df = boxplot_payload(
                        panel_df,
                        group_by=group_by,
                        value_col=y_col,
                    )
                    derived[(row, col)]["box_summary"] = summary_df
                    derived[(row, col)]["box_outliers"] = outliers_df
                    if getattr(chart, "mean_line", False):
                        derived[(row, col)]["overall_mean"] = overall_mean(panel_df, [y_col])

        # ── Step 2.2: y_columns 过滤 ──
        # 用户可通过 fig[r,c].bar(..., y_columns=["var_a","var_c"]) 声明
        # 仅绘制 group 列的指定取值。过滤发生在聚合后，适用 bar/line/scatter。
        for (row, col), decl in self._subplot_decls.items():
            y_cols = decl.get("y_columns")
            if not y_cols:
                continue
            chart = chart_specs.get((row, col))
            group_col = chart.mapping.get("group") if chart else None
            if group_col and group_col in computed.get((row, col), pd.DataFrame()).columns:
                cdf = computed[(row, col)]
                matched = cdf[group_col].isin(y_cols)
                computed[(row, col)] = cdf[matched]
                for name, payload in derived[(row, col)].items():
                    if isinstance(payload, pd.DataFrame) and group_col in payload.columns:
                        derived[(row, col)][name] = payload[payload[group_col].isin(y_cols)].copy()
                # 校验: 过滤后是否为空 / 是否有值未匹配
                if computed[(row, col)].empty:
                    actual_values = sorted(cdf[group_col].unique())
                    warnings.warn(
                        f"子图 [{row},{col}] y_columns={y_cols} 过滤后数据为空。"
                        f"group 列 '{group_col}' 的实际值为: {actual_values}。"
                        f"请检查 y_columns 是否与数据中的值一致。",
                        stacklevel=2,
                    )
                elif len(y_cols) > 0:
                    unmatched = [v for v in y_cols if v not in set(cdf[group_col])]
                    if unmatched:
                        actual_values = sorted(cdf[group_col].unique())
                        warnings.warn(
                            f"子图 [{row},{col}] y_columns 中 {len(unmatched)} 个值 "
                            f"在数据中不存在: {unmatched}。"
                            f"group 列 '{group_col}' 的实际值为: {actual_values}。",
                            stacklevel=2,
                        )

        # ── Step 2.25: 数值列有效性校验 ──
        for (row, col), cdf in computed.items():
            chart = chart_specs.get((row, col))
            if not chart:
                continue
            y_col_name = chart.mapping.get("y")
            if isinstance(y_col_name, str) and y_col_name in cdf.columns:
                _num_warnings = check_numeric_columns(
                    cdf, [y_col_name],
                    source_hint=f"subplot[{row},{col}]",
                )
                for w in _num_warnings:
                    warnings.warn(w, stacklevel=2)

        # ── Step 2.3: 显示名映射 (labels) ──
        # 收集所有子图的实际 group 取值 → 合并 labels → 统一映射到 computed data
        # 合并用户 labels（取所有子图 labels 的并集）
        merged_user_labels: Dict[str, str] = {}
        for decl in self._subplot_decls.values():
            sub_labels = decl.get("labels") or {}
            merged_user_labels.update(sub_labels)

        # sidecar YAML fallback: 检测同目录下 <csv>.labels.yaml（仅当 Figure 未传入 labels 时）
        _label_map = resolve_labels(
            user_labels=merged_user_labels or None,
            y_columns=None,
        )

        # A paper registers raw identities per group column, independently of
        # which CSV happens to be used by this Figure. Display labels never
        # determine palette positions. Existing explicit labels take priority.
        group_label_maps = {
            column: {**{entry["id"]: entry["label"] for entry in entries}, **_label_map}
            for column, entries in self._series.items()
        }

        def display(column, value):
            return group_label_maps.get(column, _label_map).get(value, value)

        active_groups = {chart.mapping.get("group") for chart in chart_specs.values()}
        custom_categories: Dict[str, List[Any]] = {}
        for decl in self._subplot_decls.values():
            custom = decl.get("custom_panel")
            if custom is not None and custom.color_group is not None:
                active_groups.add(custom.color_group)
                custom_categories.setdefault(custom.color_group, []).extend(custom.categories or ())
        series_order = {}
        registered_styles = {}
        resolved_colors = {}
        for column, entries in self._series.items():
            if column not in active_groups:
                continue
            ids = {entry["id"] for entry in entries}
            observed = list(custom_categories.get(column, []))
            if df is not None and column in df.columns:
                # pandas.unique/set collapse True into numeric ID 1. Validate
                # raw observations before deduplicating semantic identities.
                observed.extend(df[column].tolist())
            unknown = [value for value in observed
                       if isinstance(value, (bool, np.bool_)) or not isinstance(value, (str, Real))
                       or pd.isna(value) or value not in ids]
            unknown = list({(type(value).__name__, repr(value)): value for value in unknown}.values())
            if unknown:
                raise ValueError(
                    f"series[{column!r}] has unregistered IDs: {unknown!r}; "
                    "register the complete paper-wide domain to keep identities stable."
                )
            names = [display(column, entry["id"]) for entry in entries]
            if len(set(names)) != len(names):
                raise ValueError(f"series[{column!r}] labels must keep each registered identity distinct.")
            series_order[column] = names
            registered_styles[column] = {}
            for entry in entries:
                name = display(column, entry["id"])
                registered_styles[column][name] = {
                    key: deepcopy(entry[key]) for key in ("color", "marker", "linestyle") if key in entry
                }
                if "color" in entry:
                    resolved_colors.setdefault(column, {})[name] = entry["color"]
        for column, colors in self._category_colors.items():
            resolved_colors.setdefault(column, {}).update({display(column, value): color for value, color in colors.items()})
        for column, styles in registered_styles.items():
            for name, style in styles.items():
                if name in resolved_colors.get(column, {}):
                    style["color"] = resolved_colors[column][name]

        def display_legend(options, column=None):
            result = deepcopy(options)
            def key(value):
                if column is not None:
                    return display(column, value)
                candidates = set()
                for group in active_groups:
                    if group is None:
                        continue
                    domain = [entry["id"] for entry in self._series.get(group, [])]
                    domain.extend(custom_categories.get(group, []))
                    if df is not None and group in df.columns:
                        domain.extend(df[group].dropna().unique().tolist())
                    if value in domain:
                        candidates.add(display(group, value))
                if len(candidates) > 1:
                    raise ValueError(
                        f"Global legend key {value!r} has different display names across groups; "
                        "configure chart_opts.legend separately for those panels."
                    )
                return next(iter(candidates), value)
            if result.get("order"):
                result["order"] = [key(value) for value in result["order"]]
            if result.get("labels"):
                result["labels"] = {key(value): label for value, label in result["labels"].items()}
            return result

        resolved_legend = display_legend(self._legend)

        # 应用映射到 computed data
        for (row, col), cdf in list(computed.items()):
            chart = chart_specs.get((row, col))
            group_col = chart.mapping.get("group") if chart else None
            labels = group_label_maps.get(group_col, _label_map)
            if group_col and group_col in cdf.columns and labels:
                cdf = cdf.copy()
                cdf[group_col] = cdf[group_col].map(labels).fillna(cdf[group_col])
                identity = ([group_col, chart.mapping["x"]] if chart.chart_type == "radar"
                            else [group_col])
                if chart.chart_type in {"pie", "donut", "radar"} and cdf.duplicated(identity).any():
                    raise ValueError(
                        f"子图 [{row},{col}] ({chart.chart_type}) labels 将不同类别合并为同名；"
                        "请为每个类别指定不同的显示名，或先在数据层明确合并。"
                    )
                computed[(row, col)] = cdf
            if group_col and labels:
                for name, payload in derived[(row, col)].items():
                    if isinstance(payload, pd.DataFrame) and group_col in payload.columns:
                        payload = payload.copy()
                        payload[group_col] = payload[group_col].map(labels).fillna(payload[group_col])
                        derived[(row, col)][name] = payload

        # Reserve colours from the full source domain before subplot filtering.
        color_domains: Dict[str, List[Any]] = deepcopy(series_order)
        for chart in chart_specs.values():
            group_col = chart.mapping.get("group")
            if group_col and group_col in df.columns and group_col not in color_domains:
                values = df[group_col].dropna().unique().tolist()
                mapped = [display(group_col, value) for value in values]
                color_domains[group_col] = sorted(
                    dict.fromkeys(mapped), key=lambda value: (type(value).__name__, str(value))
                )
        # Diagrams declare raw semantic categories directly. Resolve those
        # through the same display labels as statistical data, retaining raw
        # aliases for the callback's colour lookup instead of allocating a
        # second colour to the same category.
        category_aliases: Dict[str, Dict[Any, Any]] = {}
        for decl in self._subplot_decls.values():
            custom = decl.get("custom_panel")
            if custom is not None and custom.color_group is not None:
                group = custom.color_group
                raw_values = list(custom.categories or ())
                if df is not None and group in df.columns:
                    raw_values.extend(df[group].dropna().unique().tolist())
                aliases = category_aliases.setdefault(group, {})
                aliases.update({
                    value: display(group, value) for value in raw_values
                    if display(group, value) != value
                })
                domain = color_domains.setdefault(group, [])
                for value in custom.categories or ():
                    canonical = display(group, value)
                    if canonical not in domain:
                        domain.append(canonical)

        # ── Step 2.5: Legend 模式检测 ──
        # 收集所有子图中出现的 group 列名。
        # 若仅一种 group 列 → shared legend。
        # 若多种并存 → 选出现最多的那个做 shared legend，
        #   其余 group 列的子图保留局部图例。
        group_columns: Dict[str, set] = {}  # group_col_name → {(row,col), ...}
        forced_shared_groups = set()
        panel_legends = {}
        legend_groups = {}
        legend_counts = {}
        for (row, col), decl in self._subplot_decls.items():
            chart = chart_specs.get((row, col))
            custom = decl.get("custom_panel")
            options = decl.get("chart_opts") or {}
            g = custom.color_group if custom is not None else chart.mapping.get("group")
            legend_options = merge_legend(
                resolved_legend,
                display_legend(options["legend"], g) if "legend" in options else None,
                panel_explicit="legend" in options,
            )
            panel_legends[(row, col)] = legend_options
            measures = None if custom is not None else chart.mapping.get("y")
            measure_count = len(measures) if isinstance(measures, (list, tuple)) else 0
            if custom is not None:
                legend_counts[(row, col)] = len(color_domains.get(g, []))
            else:
                legend_counts[(row, col)] = (
                    df[g].nunique() if g in df.columns else measure_count if measure_count > 1 else 0
                )
            if g is None and measure_count > 1 and legend_options.get("scope") == "shared":
                # Explicitly shared wide-table measures form one virtual group.
                # Auto keeps the established per-panel multi-metric legends.
                g = "__measures__"
            elif g is None and custom is not None and legend_options.get("scope") == "shared":
                # Callback-provided handles may share a legend even when no
                # categorical colour domain is needed by the diagram itself.
                g = "__custom__"
            legend_groups[(row, col)] = g
            if (g is not None and legend_options.get("visible", True)
                    and legend_options.get("scope", "auto") != "local"):
                group_columns.setdefault(g, set()).add((row, col))
                if legend_options.get("scope") == "shared":
                    forced_shared_groups.add(g)

        has_any_group = len(group_columns) > 0
        if has_any_group:
            dominant_group = max(
                [g for g in group_columns if g in forced_shared_groups] or group_columns,
                key=lambda k: len(group_columns[k]),
            )
            # 若该 group 列出现在 >1 个子图中，启用共享 legend
            shared_legend = len(group_columns[dominant_group]) > 1 or bool(forced_shared_groups)
            shared_group_column = dominant_group if shared_legend else ""
        else:
            shared_legend = False
            shared_group_column = ""

        # 计算 legend 最大条目数
        actual_legend_max = 0
        for key, legend_options in panel_legends.items():
            if legend_options.get("visible", True):
                actual_legend_max = max(actual_legend_max, legend_counts[key])
        if actual_legend_max and self._legend_max_entries > 0:
            actual_legend_max = self._legend_max_entries

        # per-cell legend: 只统计不匹配 shared_group_column 的 cell 需要的条目数
        per_cell_legend_max = 0
        if shared_legend:
            for key, legend_options in panel_legends.items():
                if (legend_options.get("visible", True) and (
                    legend_groups[key] != shared_group_column or legend_options.get("scope") == "local"
                )):
                    per_cell_legend_max = max(per_cell_legend_max, legend_counts[key])

        # ── Step 2.6: 收集 legend 参考线条目 ──
        # 扫描所有子图的 chart_options，提取 hline / mean_line 信息供共享 legend 使用。
        reference_lines: List[Dict[str, str]] = []
        _seen_refs: set = set()
        for (row, col), chart in chart_specs.items():
            # 合并 chart spec 选项 + 用户 chart_opts 覆盖
            opts = dict(chart.to_spec().get("options", {}))
            decl = self._subplot_decls.get((row, col))
            if decl and decl.get("chart_opts"):
                opts.update(decl["chart_opts"])
            hline_val = opts.get("hline")
            hline_label = opts.get("hline_label")
            if hline_val is not None:
                ref_key = ("hline", str(hline_val), hline_label or "")
                if ref_key not in _seen_refs:
                    _seen_refs.add(ref_key)
                    label = hline_label or f"Ref: {hline_val}"
                    reference_lines.append({
                        "label": str(label),
                        "type": "hline",
                    })
            if opts.get("mean_line"):
                ref_key = ("mean_line", row, col)
                if ref_key not in _seen_refs:
                    _seen_refs.add(ref_key)
                    label = opts.get("mean_line_label") or "Overall Mean"
                    reference_lines.append({
                        "label": str(label),
                        "type": "mean_line",
                    })

        # ── Step 3: 构建 Layout ──
        layout_spec = build_layout(
            rows=self._rows,
            cols=self._cols,
            layout=self._layout_matrix,
            width_ratios=self._width_ratios,
            height_ratios=self._height_ratios,
            aspect=self._aspect,
            base=self._base,
            cell_base=self._cell_base,
            dpi=self._dpi,
            title=self._title,
            legend_max_entries=per_cell_legend_max if shared_legend else actual_legend_max,
            legend_default_position=self._legend_position,
            shared_legend=shared_legend,
            shared_group_column=shared_group_column,
            auto_margins=self._auto_margins,
        )

        # ── Step 4: 共享轴检测 ──
        chart_axes: List[Dict[str, Optional[str]]] = []
        for cell in layout_spec["cells"]:
            r, c = cell["row"], cell["col"]
            chart = chart_specs.get((r, c))
            if chart:
                chart_axes.append({
                    "x": chart.mapping.get("x", None),
                    "y": chart.mapping.get("y", None),
                })
            else:
                chart_axes.append({"x": None, "y": None})

        layout_spec = detect_shared_axes(layout_spec, chart_axes)
        # A drawing panel's coordinates have no statistical sharing semantics.
        # The legacy detector may mark cells with no y variable, so clear these
        # explicitly rather than inheriting another panel's numeric labels.
        for cell in layout_spec["cells"]:
            decl = self._subplot_decls.get((cell["row"], cell["col"]))
            if decl and decl["chart_type"] in {"custom", "pie", "donut", "radar"}:
                cell["shared_axes"] = {
                    "x_shared": False, "y_shared": False,
                    "x_shared_with": -1, "y_shared_with": -1,
                }

        # ── Step 5: 组装 FigureSpec ──
        subplots: List[SubplotSpec] = []

        for cell in layout_spec["cells"]:
            r, c = cell["row"], cell["col"]
            decl = self._subplot_decls.get((r, c))
            chart = chart_specs.get((r, c))

            if decl and chart:
                chart_opts = dict(chart.to_spec().get("options", {}))
                if decl.get("domain"):
                    chart_opts["domain"] = decl["domain"]
                if decl.get("chart_opts"):
                    if chart.chart_type in {"pie", "donut", "radar"}:
                        # The validated ChartSpec already resolved typed
                        # overrides and converted NumPy scalars to JSON-safe
                        # values. Reapply only renderer-specific options.
                        typed = {item.name for item in dataclass_fields(type(chart))
                                 if item.init and item.name not in {"mapping", "title"}}
                        chart_opts.update({key: value for key, value in decl["chart_opts"].items()
                                           if key not in typed})
                    else:
                        chart_opts.update(decl["chart_opts"])
                if chart.chart_type in {"pie", "donut"} and chart_opts.get("order"):
                    chart_opts["order"] = [display(chart.mapping.get("group"), value) for value in chart_opts["order"]]
                group = chart.mapping.get("group")
                if group in series_order:
                    chart_opts["series_order"] = list(series_order[group])
                styles = deepcopy(registered_styles.get(group, {}))
                explicit_styles = chart_opts.get("series_styles", {})
                if not isinstance(explicit_styles, Mapping):
                    raise ValueError("series_styles must map group values to styling dictionaries")
                for value, style in explicit_styles.items():
                    if not isinstance(style, Mapping):
                        raise ValueError("Each series_styles entry must be a styling dictionary")
                    name = display(group, value)
                    styles[name] = {**styles.get(name, {}), **deepcopy(style)}
                if styles:
                    chart_opts["series_styles"] = styles
                if "legend" in chart_opts:
                    chart_opts["legend"] = display_legend(normalize_legend(chart_opts["legend"]), group)
                chart_opts = resolve_field_options(
                    chart.chart_type, chart.mapping, chart_opts, self._fields, data=panel_data[(r, c)],
                )
                measures = chart.mapping.get("y")
                secondary = chart.mapping.get("y2")
                if isinstance(measures, (list, tuple)) or secondary:
                    measure_columns = list(measures) if isinstance(measures, (list, tuple)) else [measures]
                    if secondary:
                        measure_columns.append(secondary)
                    names = {value: field_label(value, self._fields, include_unit=False)
                             for value in measure_columns if value in self._fields}
                    if names:
                        chart_opts["measure_labels"] = {**names, **chart_opts.get("measure_labels", {})}
                validate_axis_options(chart.chart_type, chart_opts)
                sp = SubplotSpec(
                    row=r,
                    col=c,
                    row_span=cell.get("row_span", 1),
                    col_span=cell.get("col_span", 1),
                    chart_type=decl["chart_type"],
                    data_mapping=chart.to_spec().get("data", {}),
                    chart_options=chart_opts,
                    title=chart.title,
                    x=cell["x"],
                    y=cell["y"],
                    w=cell["w"],
                    h=cell["h"],
                    font_sizes=cell.get("font_sizes", {}),
                    label_margins=cell.get("label_margins", {}),
                    legend={**cell.get("legend", {}), **panel_legends[(r, c)]},
                    data_zone=cell.get("data_zone", {}),
                    shared_axes=cell.get("shared_axes", {}),
                    computed_data=computed.get((r, c)),
                    derived_data=derived.get((r, c), {}),
                )
            elif decl and decl["chart_type"] == "custom":
                custom_mapping = dict(decl["mapping"])
                group = decl["custom_panel"].color_group
                aliases = category_aliases.get(group)
                if aliases:
                    custom_mapping["category_aliases"] = dict(aliases)
                custom_options = deepcopy(decl.get("chart_opts") or {})
                if group in series_order:
                    custom_options["series_order"] = list(series_order[group])
                if "legend" in custom_options:
                    custom_options["legend"] = display_legend(custom_options["legend"], group)
                sp = SubplotSpec(
                    row=r, col=c,
                    row_span=cell.get("row_span", 1),
                    col_span=cell.get("col_span", 1),
                    chart_type="custom",
                    data_mapping=custom_mapping,
                    chart_options=custom_options,
                    title=decl.get("title"),
                    x=cell["x"], y=cell["y"], w=cell["w"], h=cell["h"],
                    font_sizes=cell.get("font_sizes", {}),
                    label_margins=cell.get("label_margins", {}),
                    legend={**cell.get("legend", {}), **panel_legends[(r, c)]},
                    data_zone=cell.get("data_zone", {}),
                    shared_axes=cell.get("shared_axes", {}),
                    custom_panel=decl["custom_panel"],
                )
            else:
                sp = SubplotSpec(
                    row=r,
                    col=c,
                    row_span=cell.get("row_span", 1),
                    col_span=cell.get("col_span", 1),
                    x=cell["x"],
                    y=cell["y"],
                    w=cell["w"],
                    h=cell["h"],
                    font_sizes=cell.get("font_sizes", {}),
                    label_margins=cell.get("label_margins", {}),
                    legend=cell.get("legend", {}),
                    data_zone=cell.get("data_zone", {}),
                    shared_axes=cell.get("shared_axes", {}),
                    derived_data=derived.get((r, c), {}),
                )
            subplots.append(sp)

        # 将 reference_lines 合并入 shared_legend
        merged_shared_legend = dict(layout_spec.get("shared_legend", {}))
        # Whole-figure legends may occupy a measured footer. Existing local
        # corner positions retain the historical shared top legend behavior.
        merged_shared_legend["position"] = self._legend.get(
            "position", "bottom" if self._legend_position == "bottom" else "top",
        )
        if reference_lines:
            merged_shared_legend["reference_lines"] = reference_lines

        spec = FigureSpec(
            version="0.1.0",
            canvas=layout_spec["canvas"],
            grid=layout_spec["grid"],
            margins=layout_spec["margins"],
            title=layout_spec["title"],
            subtitle=layout_spec["subtitle"],
            theme=self._theme,
            palette=self._palette,
            font_family=self._font_family,
            background=self._background,
            color_domains=color_domains,
            series_order=series_order,
            category_colors=resolved_colors,
            facets=deepcopy(self._facets),
            subplots=subplots,
            shared_legend=merged_shared_legend,
            legend=resolved_legend,
            _source_data=df,
        )

        if self._canvas_request is not None:
            from data_visuals.layout.physical import resolve_canvas_spec
            original_declarations = [
                self._subplot_decls[key] for key in sorted(self._subplot_decls)
            ]
            spec = resolve_canvas_spec(spec, self._canvas_request, auto_cols=self._auto_cols)
            if self._auto_cols is not False:
                active_subplots = [sp for sp in spec.subplots if sp.chart_type]
                self._subplot_decls = {
                    (sp.row, sp.col): decl
                    for sp, decl in zip(active_subplots, original_declarations)
                }
                self._rows = spec.grid["rows"]
                self._cols = spec.grid["cols"]
                self._layout_matrix = [
                    [sp.col_span for sp in active_subplots if sp.row == row]
                    for row in range(self._rows)
                ]
                self._width_ratios = None
                self._height_ratios = None

        self._spec = spec
        return spec

    # ── 渲染委托 ─────────────────────────────────────────

    def render(self, path: Optional[str] = None, *, backend: str = "matplotlib", **kwargs: Any) -> Any:
        """构建并渲染 Figure。

        Parameters
        ----------
        path : str | None
            输出路径。扩展名决定格式: .svg / .pdf / .png。
            None 时返回 Matplotlib Figure。
        backend : str
            仅支持 "matplotlib"；保留参数以兼容已有静态绘图调用。
        **kwargs : 透传给 renderer.export.save()

        Returns
        -------
        matplotlib.figure.Figure | None
        """
        from data_visuals.renderer.export import _validate_backend
        _validate_backend(backend)
        spec = self.build()
        if path is not None:
            from data_visuals.renderer.export import save
            save(spec, path, backend=backend, **kwargs)
            return None
        from data_visuals.renderer.mpl.canvas import figure_to_matplotlib
        return figure_to_matplotlib(spec, **kwargs)

    def show(self, *, backend: str = "matplotlib", **kwargs: Any) -> None:
        """在 Jupyter Notebook 中内联展示。"""
        self.display(backend=backend, **kwargs)

    def check(self, *, min_fontsize: float = 7.0, min_tick_gap: float = 1.0,
              tolerance: float = 1.0, debug=None):
        """Measure final typography and geometry without changing the figure.

        Returns a portable FigureReport. Optional ``debug`` saves a separate
        PNG/SVG/PDF with cell, data-rectangle and issue overlays. Impossible
        layouts retain the existing LayoutError and canvas-size hints.
        Custom drawing callbacks may run again, as during a regular export.
        """
        import matplotlib.pyplot as plt
        from data_visuals.core.quality import check_figure, _validate_check_options
        _validate_check_options(min_fontsize, min_tick_gap, tolerance, debug)
        rendered = self.render()
        try:
            return check_figure(rendered, min_fontsize=min_fontsize,
                                min_tick_gap=min_tick_gap, tolerance=tolerance, debug=debug)
        finally:
            plt.close(rendered)

    def display(self, *, backend: str = "matplotlib", **kwargs: Any) -> None:
        """在 Notebook 中展示 Matplotlib 图。"""
        from data_visuals.renderer.export import display, _validate_backend
        _validate_backend(backend)
        spec = self.build()
        display(spec, backend=backend, **kwargs)

    # ── 信息 ──────────────────────────────────────────────

    def __repr__(self) -> str:
        n_declared = len(self._subplot_decls)
        return (
            f"Figure(rows={self._rows}, cols={self._cols}, "
            f"theme='{self._theme}', subplots={n_declared}/{self._rows * self._cols})"
        )

    def summary(self) -> str:
        """打印 Figure 的可读摘要。"""
        if self._spec is None:
            spec = self.build()
        else:
            spec = self._spec
        return spec.summary()
