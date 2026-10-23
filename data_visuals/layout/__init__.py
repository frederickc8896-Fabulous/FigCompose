"""
layout/ — 排版布局引擎
=======================
负责将用户声明的网格划分为具体的 cell 坐标，并按比例推导所有字号和间距。

核心设计原则:
    - 用户只需声明 rows × cols + aspect(宽高比) + base(尺寸档位)
    - 所有尺寸按比例推导，不硬编码绝对值
    - 输出渲染器无关的 LayoutSpec 中间表示
    - SVG/PDF 用宽高比决定 viewBox，PNG 导出由 base 决定像素数

模块:
    grid      : 纯几何网格计算 (canvas → cell 坐标，含 col_span / row_span)
    sizing    : 智能尺寸引擎 (全局 canvas → 统一字号/间距/边界)
    manager   : 编排层 (aspect/base 解析 + grid + sizing → LayoutSpec)
    shared    : 共享轴检测 (同行/列 chart 合并 x/y 标注)
"""

from data_visuals.layout.grid import (
    Cell,
    GridSpec,
    compute_grid,
    compute_grid_auto_margins,
    compute_grid_mixed,
    compute_grid_mixed_auto,
    parse_layout_weights,
    CellWeight,
    _resolve_cell_weight,
)

from data_visuals.layout.sizing import (
    clamp,
    CellSizing,
    SizingSpec,
    compute_sizing,
    compute_figure_font_sizes,
    DEFAULT_FONT_RATIOS,
    DEFAULT_LIMITS,
    DEFAULT_SPACING_RATIOS,
)

from data_visuals.layout.manager import (
    build_layout,
    print_layout,
    parse_aspect,
    aspect_to_str,
    resolve_canvas,
    LegendPosition,
    AspectInput,
    BaseSize,
    BASE_SIZE_PRESETS,
    DEFAULT_LEGEND_FALLBACK,
)

from data_visuals.layout.shared import (
    detect_shared_axes,
)

from data_visuals.layout.auto import (
    auto_layout,
    CHART_CELL_RATIO,
    _factorize,
    _score_grid,
    _pick_best_grid,
)

__all__ = [
    # grid
    "Cell",
    "GridSpec",
    "compute_grid",
    "compute_grid_auto_margins",
    "compute_grid_mixed",
    "compute_grid_mixed_auto",
    "parse_layout_weights",
    "CellWeight",
    "_resolve_cell_weight",
    # sizing
    "clamp",
    "CellSizing",
    "SizingSpec",
    "compute_sizing",
    "compute_figure_font_sizes",
    "DEFAULT_FONT_RATIOS",
    "DEFAULT_LIMITS",
    "DEFAULT_SPACING_RATIOS",
    # manager
    "build_layout",
    "print_layout",
    "parse_aspect",
    "aspect_to_str",
    "resolve_canvas",
    "LegendPosition",
    "AspectInput",
    "BaseSize",
    "BASE_SIZE_PRESETS",
    "DEFAULT_LEGEND_FALLBACK",
    # shared
    "detect_shared_axes",
    # auto
    "auto_layout",
    "CHART_CELL_RATIO",
    "_factorize",
    "_score_grid",
    "_pick_best_grid",
]
