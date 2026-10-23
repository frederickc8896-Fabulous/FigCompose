"""
core/spec.py
============
FigureSpec — 系统内部统一中间表示（AST 角色）。

职责:
    - 定义 FigureSpec 数据结构，作为所有上下游模块的合约
    - 上游组装: Figure → FigureSpec
    - 下游消费: renderer/mpl/ 按 FigureSpec 测量排版与渲染

不负责:
    - 数据计算 (属于 compute/)
    - 布局计算 (属于 layout/)
    - 渲染导出 (属于 renderer/)

设计原则:
    - 纯数据容器（dataclass），无副作用
    - 可序列化为 JSON-safe dict（供 renderer 消费）
    - SubplotSpec 捆绑 chart 定义 + 几何信息 + 字体/legend 预留
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

import pandas as pd

from data_visuals.core.facets import normalize_facets
from data_visuals.core.legend import normalize_legend
from data_visuals.core.panel import CustomPanel


# ═══════════════════════════════════════════════════════════════
# SubplotSpec — 单个子图的完整规格
# ═══════════════════════════════════════════════════════════════

@dataclass
class SubplotSpec:
    """Figure 中单个子图的完整规格。

    捆绑三个来源的产物:
        charts/   → chart_type, data_mapping, chart_options
        layout/   → geometry, font_sizes, label_margins, legend, data_zone
        compute/  → computed_data (聚合后的 DataFrame 或 dict)
    """

    # ── 网格位置 ──
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1

    # ── 图表定义 (来自 charts/) ──
    chart_type: str = ""
    data_mapping: Dict[str, Any] = field(default_factory=dict)
    chart_options: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None

    # ── 几何信息 (来自 layout/) ──
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    # ── 字体 (来自 layout/sizing) ──
    font_sizes: Dict[str, float] = field(default_factory=dict)
    # {"title": 14.0, "axis_label": 12.0, "tick": 10.0, "legend": 10.0}

    # ── 轴标注预留空间 ──
    label_margins: Dict[str, float] = field(default_factory=dict)
    # {"x_label_height": 21.6, "y_label_width": 60.0}

    # ── Legend 占位 ──
    legend: Dict[str, Any] = field(default_factory=dict)
    # {"max_entries": 0, "font_size": 10.0, "reserved_height": 0,
    #  "reserved_width": 0, "default_position": "top-right",
    #  "fallback": [...], "deferred": True}

    # ── 数据绘图区 ──
    data_zone: Dict[str, float] = field(default_factory=dict)
    # {"x": 90.0, "y": 60.0, "w": 800.0, "h": 500.0}

    # ── 共享轴标记 ──
    shared_axes: Dict[str, Any] = field(default_factory=dict)
    # {"x_shared": False, "y_shared": False,
    #  "x_shared_with": -1, "y_shared_with": -1}

    # ── 计算后的数据 ──
    computed_data: Optional[pd.DataFrame] = None
    derived_data: Dict[str, Any] = field(default_factory=dict)

    # Runtime drawing adapters intentionally remain outside chart_options and
    # the JSON representation. Their callback and payload retain their identity.
    custom_panel: Optional[CustomPanel] = field(default=None, repr=False)

    def to_dict(self, *, runtime: bool = False) -> Dict[str, Any]:
        """Serialize statistical panels to JSON, or retain runtime adapters.

        Custom drawing callbacks cannot be represented in JSON. The renderer
        opts into ``runtime=True`` to receive the original adapter; the default
        raises instead of silently dropping a panel's content.
        """
        if self.custom_panel is not None and not runtime:
            raise TypeError(
                "Custom panels contain runtime drawing callbacks and cannot be serialized to JSON. "
                "Use to_dict(runtime=True) only for in-process Matplotlib rendering."
            )
        d: Dict[str, Any] = {
            "row": self.row,
            "col": self.col,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "chart": self.chart_type,
            "data": self.data_mapping,
            "geometry": {
                "x": self.x, "y": self.y,
                "w": self.w, "h": self.h,
            },
            "font_sizes": self.font_sizes,
            "label_margins": self.label_margins,
            "legend": self.legend,
            "data_zone": self.data_zone,
            "shared_axes": self.shared_axes,
        }
        if self.chart_options:
            d["options"] = self.chart_options
        if self.title:
            d["title"] = self.title
        if self.custom_panel is not None:
            d["_custom_panel"] = self.custom_panel
        if self.computed_data is not None:
            d["computed_data"] = self.computed_data.to_dict(orient="records")
        if self.derived_data:
            serialized: Dict[str, Any] = {}
            for key, value in self.derived_data.items():
                if isinstance(value, pd.DataFrame):
                    serialized[key] = value.to_dict(orient="records")
                else:
                    serialized[key] = value
            d["derived_data"] = serialized
        return d


# ═══════════════════════════════════════════════════════════════
# FigureSpec — 整张图的完整中间表示
# ═══════════════════════════════════════════════════════════════

@dataclass
class FigureSpec:
    """整张论文图的完整中间表示（AST）。

    FigureSpec 是系统中所有模块解耦的关键:
        - 上游 (data/compute/charts/layout) 只产出 Spec 片段
        - 下游 (renderer) 只消费完整 Spec
    """

    # ── 版本 ──
    version: str = "0.1.0"

    # ── 画布 ──
    canvas: Dict[str, Any] = field(default_factory=dict)
    # Physical path uses pt for width/height and geometry, preserving the
    # original mm/in request and solved width_mm/height_mm in this mapping.
    # Legacy aspect/base/cell_base specifications remain distinguishable.

    # ── 网格 ──
    grid: Dict[str, Any] = field(default_factory=dict)
    # {"rows": 2, "cols": 2, "gap": 12.0}

    # ── 边距 ──
    margins: Dict[str, float] = field(default_factory=dict)
    # {"top": 50.0, "bottom": 40.0, "left": 60.0, "right": 30.0}

    # ── 全局标题 ──
    title: Dict[str, Any] = field(default_factory=dict)
    # {"text": "", "font_size": 18.0}
    subtitle: Dict[str, Any] = field(default_factory=dict)
    # {"text": "", "font_size": 12.6}

    # ── 主题 ──
    theme: str = "general"
    palette: Optional[str] = None

    # ── 字体族 ──
    font_family: Optional[str] = None  # None = use theme font; set explicitly to override

    # ── 背景色 ──
    background: str = "#ffffff"

    # Full category domains keep colours stable when subplots filter the data.
    color_domains: Dict[str, List[Any]] = field(default_factory=dict)
    category_colors: Dict[str, Dict[str, str]] = field(default_factory=dict)
    # Optional repeated-panel headers and shared axis labels/limits.
    facets: Dict[str, Any] = field(default_factory=dict)

    # ── 子图列表 ──
    subplots: List[SubplotSpec] = field(default_factory=list)

    # ── 共享 Legend (所有子图使用同一 group 列时生效) ──
    shared_legend: Dict[str, Any] = field(default_factory=dict)
    # {"enabled": True, "group_column": "dataset",
    #  "font_size": 12.0, "reserved_height": 24.0}

    # Explicit global legend overrides; renderer resolves defaults per scope.
    legend: Dict[str, Any] = field(default_factory=dict)

    # ── 原始数据引用（不参与序列化，仅供调试）──
    _source_data: Optional[pd.DataFrame] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.facets = normalize_facets(self.facets)
        self.legend = normalize_legend(self.legend)

    @property
    def n_subplots(self) -> int:
        return len(self.subplots)

    def get_subplot(self, row: int, col: int) -> Optional[SubplotSpec]:
        """按行列坐标查找子图。"""
        for sp in self.subplots:
            if sp.row == row and sp.col == col:
                return sp
        return None

    def iter_subplots(self):
        """按行优先遍历所有子图。"""
        return iter(self.subplots)

    def to_dict(self, *, runtime: bool = False) -> Dict[str, Any]:
        """Serialize to JSON-safe data, or retain custom adapters for rendering."""
        return {
            "version": self.version,
            "canvas": self.canvas,
            "grid": self.grid,
            "margins": self.margins,
            "title": self.title,
            "subtitle": self.subtitle,
            "theme": self.theme,
            "palette": self.palette,
            "font_family": self.font_family,
            "background": self.background,
            "color_domains": self.color_domains,
            "category_colors": self.category_colors,
            "facets": normalize_facets(self.facets),
            "subplots": [sp.to_dict(runtime=runtime) for sp in self.subplots],
            "shared_legend": self.shared_legend,
            "legend": normalize_legend(self.legend),
        }

    def summary(self) -> str:
        """返回 FigureSpec 的可读摘要。"""
        if self.canvas.get("physical"):
            dimensions = (
                f"{self.canvas['width_mm']:.2f}×{self.canvas['height_mm']:.2f} mm "
                f"({self.canvas.get('width'):.2f}×{self.canvas.get('height'):.2f} pt)"
            )
        else:
            dimensions = f"{self.canvas.get('width')}×{self.canvas.get('height')}"
        lines = [
            f"FigureSpec v{self.version}",
            f"  Canvas: {dimensions} "
            f"@ {self.canvas.get('dpi')}dpi ({self.canvas.get('aspect')})",
            f"  Grid: {self.grid.get('rows')}×{self.grid.get('cols')}",
            f"  Theme: {self.theme}",
            f"  Subplots: {self.n_subplots}",
        ]
        for sp in self.subplots:
            lines.append(
                f"    [{sp.row},{sp.col}] {sp.chart_type} "
                f"({sp.w:.0f}×{sp.h:.0f}) "
                f"geom({sp.x:.0f},{sp.y:.0f})"
            )
        return "\n".join(lines)
