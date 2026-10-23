"""
layout/manager.py
=================
Layout 编排层 — 将 grid + sizing 组装为统一的 LayoutSpec 中间表示。

核心重构: 放弃手动 px，改用 aspect(宽高比) + base(相对尺寸档位)。
    - SVG/PDF: 宽高比决定 viewBox，物理尺寸由外部容器控制
    - PNG: base 决定基准像素宽度，导出时按 DPI 映射
    - 旧式 canvas_width/height 保留兼容，但不推荐

职责:
    - 接收用户声明 (rows, cols, aspect, base)
    - 解析宽高比 + base_size → canvas px
    - 调用 grid.py 做网格划分
    - 调用 sizing.py 做智能尺寸推导
    - 输出 LayoutSpec dict（渲染器无关的中间格式）
"""

from __future__ import annotations

import re
from typing import Optional, Dict, List, Any, Literal, Union, Tuple

from data_visuals.layout.grid import (
    compute_grid,
    compute_grid_auto_margins,
    compute_grid_ratios,
    compute_grid_ratios_auto_margins,
    compute_grid_mixed,
    compute_grid_mixed_auto,
    parse_layout_weights,
    GridSpec,
    Cell,
)
from data_visuals.layout.sizing import (
    compute_sizing,
    compute_figure_font_sizes,
    SizingSpec,
    DEFAULT_FONT_RATIOS,
    DEFAULT_LIMITS,
    DEFAULT_SPACING_RATIOS,
    CELL_SIZE_PRESETS,
)

# ── 类型 ──────────────────────────────────────────────────────

LegendPosition = Literal[
    "top-right", "top-left", "top-center",
    "bottom-right", "bottom-left", "bottom-center",
    "right", "left",
]

LegendFallback = Literal["bottom", "none"]

# legend fallback 优先级：放不下时按此顺序尝试
DEFAULT_LEGEND_FALLBACK: List[str] = ["right", "bottom"]

AspectInput = Union[str, float, Tuple[int, int]]
BaseSize = Literal["small", "medium", "large", "poster"]

# base_size → 基准 canvas 宽度 (px)
BASE_SIZE_PRESETS: Dict[str, int] = {
    "small":  800,
    "medium": 1200,
    "large":  1800,
    "poster": 3600,
}

DEFAULT_ASPECT: str = "16:10"
DEFAULT_BASE: str = "medium"


# ── 宽高比解析 ────────────────────────────────────────────────

def parse_aspect(value: AspectInput) -> float:
    """解析宽高比为浮点数 (width / height)。

    Parameters
    ----------
    value : str | float | tuple[int, int]
        "16:9", 1.5, (4, 3) 等

    Returns
    -------
    float — width / height

    Examples
    --------
    parse_aspect("16:9") → 1.777...
    parse_aspect(1.5)    → 1.5
    parse_aspect((4, 3))  → 1.333...
    """
    if isinstance(value, (int, float)):
        ratio = float(value)
    elif isinstance(value, tuple) and len(value) == 2:
        ratio = value[0] / value[1]
    elif isinstance(value, str):
        m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)\s*$", value)
        if m:
            ratio = float(m.group(1)) / float(m.group(2))
        else:
            try:
                ratio = float(value)
            except ValueError:
                raise ValueError(
                    f"无法解析宽高比 '{value}'。"
                    f"支持格式: '16:9', '4:3', 1.5, (4, 3)"
                )
    else:
        raise TypeError(f"宽高比类型不支持: {type(value).__name__}")

    if ratio <= 0:
        raise ValueError(f"宽高比必须 > 0，当前值: {ratio}")

    return ratio


def aspect_to_str(ratio: float) -> str:
    """将浮点宽高比转为友好字符串，如 1.5 → '3:2'"""
    presets = {
        16/9: "16:9",
        16/10: "16:10",
        4/3: "4:3",
        3/2: "3:2",
        5/4: "5:4",
        1.0: "1:1",
    }
    for val, label in presets.items():
        if abs(ratio - val) < 0.01:
            return label
    return f"{ratio:.2f}"


def resolve_canvas(
    *,
    aspect: AspectInput = DEFAULT_ASPECT,
    base: str = DEFAULT_BASE,
) -> Tuple[int, int]:
    """解析 aspect + base → canvas (width_px, height_px)。

    Parameters
    ----------
    aspect : str | float | tuple
        宽高比，默认 "16:10"
    base : str
        尺寸档位: "small" | "medium" | "large" | "poster"

    Returns
    -------
    (width, height) — 整数 px

    Examples
    --------
    resolve_canvas(aspect="16:9", base="medium") → (1200, 675)
    resolve_canvas(aspect="4:3", base="small")   → (800, 600)
    """
    ratio = parse_aspect(aspect)
    if base not in BASE_SIZE_PRESETS:
        raise ValueError(
            f"未知 base_size '{base}'。可选: {list(BASE_SIZE_PRESETS.keys())}"
        )
    base_w = BASE_SIZE_PRESETS[base]
    height = int(round(base_w / ratio))
    return base_w, height


def resolve_canvas_from_cell(
    *,
    cell_base: str,
    rows: int,
    cols: int,
    aspect: AspectInput = DEFAULT_ASPECT,
) -> Tuple[int, int]:
    """cell-first 模式: target_cell × rows/cols + margins → canvas。

    边距和间距按 cell 较短边 × 比例计算，与 sizing.py 的 clamp 逻辑一致。
    算出的 canvas 再按 aspect 约束微调（优先保宽，调高度）。

    Parameters
    ----------
    cell_base : str
        cell 尺寸档位: "small" | "medium" | "large" | "poster"
    rows, cols : int
        网格行列数
    aspect : str | float | tuple
        画布宽高比约束

    Returns
    -------
    (width, height) — 整数 px

    Examples
    --------
    resolve_canvas_from_cell(cell_base="large", rows=2, cols=2)
    → (1800, 1125)  ← 与 canvas-first base="large" 完全一致

    resolve_canvas_from_cell(cell_base="large", rows=3, cols=3)
    → (2691, 1682)  ← 自动扩大
    """
    if cell_base not in CELL_SIZE_PRESETS:
        raise ValueError(
            f"未知 cell_base '{cell_base}'。可选: {list(CELL_SIZE_PRESETS.keys())}"
        )
    from data_visuals.layout.sizing import clamp

    ref_w, ref_h = CELL_SIZE_PRESETS[cell_base]
    ref_min = min(ref_w, ref_h)

    margin = clamp(ref_min * 0.04, 20, 80)
    gap = clamp(ref_min * 0.015, 8, 40)

    canvas_w = margin * 2 + cols * ref_w + (cols - 1) * gap
    canvas_h = margin * 2 + rows * ref_h + (rows - 1) * gap

    ratio = parse_aspect(aspect)
    current = canvas_w / canvas_h
    if current > ratio:
        canvas_h = canvas_w / ratio
    else:
        canvas_w = canvas_h * ratio

    return int(round(canvas_w)), int(round(canvas_h))


# ── 主 API ────────────────────────────────────────────────────

def build_layout(
    rows: Optional[int] = None,
    cols: Optional[int] = None,
    *,
    # ── 混合布局 (优先级最高) ──
    layout: Optional[List[List[Union[int, Tuple[int, int], None]]]] = None,
    # ── 推荐：宽高比模式 ──
    aspect: AspectInput = DEFAULT_ASPECT,
    base: str = DEFAULT_BASE,
    # ── cell-first 模式（优先级高于 base）──
    cell_base: Optional[str] = None,
    # ── 旧式兼容：显式 px（优先级高于 aspect/cell_base）──
    canvas_width: Optional[float] = None,
    canvas_height: Optional[float] = None,
    # ── 通用 ──
    dpi: int = 150,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    # ── Legend（延迟决策）──
    legend_max_entries: int = 0,
    legend_default_position: str = "top-right",
    legend_fallback: Optional[List[str]] = None,
    # ── 共享 Legend（全图唯一 legend，放主标题下方）──
    shared_legend: bool = False,
    shared_group_column: str = "",
    auto_margins: bool = True,
    manual_margins: Optional[Dict[str, float]] = None,
    manual_gap: Optional[float] = None,
    width_ratios: Optional[List[float]] = None,
    height_ratios: Optional[List[float]] = None,
    font_ratios: Optional[Dict[str, float]] = None,
    font_limits: Optional[Dict[str, tuple]] = None,
    spacing_ratios: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    构建完整的 LayoutSpec（渲染器无关的中间格式）。

    一次调用完成: 宽高比解析 → 网格划分 → 尺寸推导 → 结构化输出。

    支持三种模式 (按优先级):
        1. layout 参数 → 混合布局，自动推断 rows/cols
        2. rows + cols 参数 → 均匀网格
        3. 两者都不传 → 默认 2×2

    Parameters
    ----------
    layout : list[list[int | (int,int) | None]] | None
        【混合布局】二维权重矩阵，支持 col_span 和 row_span。
        每个单元格可以是:
            int          → col_span 权重, row_span=1
            (int, int)   → (col_span, row_span) 跨行跨列
            None / 0     → 占位符（被上方跨行 cell 占用）
        例如:
            [[3, 1], [4]]                       → 纯 col_span
            [[(2, 2), 1, 1], [None, 2, 1]]     → 包含 row_span 的布局

    rows, cols : int | None
        【均匀网格】行列数。layout 不为 None 时自动推断，可省略。

    aspect : str | float | tuple
        【推荐】画布宽高比。默认 "16:10"。
        支持: "16:9", "4:3", "3:2", "1:1", 1.5, (4,3) 等
    base : str
        【推荐】基准尺寸档位。默认 "medium"。
        small=800 / medium=1200 / large=1800 / poster=3600 (基准宽度 px)

    canvas_width, canvas_height : float | None
        【兼容】显式画布 px。设置后将忽略 aspect + base

    dpi : int
        输出 DPI，默认 150（PNG 导出时生效）
    title / subtitle : str | None
        全局主/副标题
    legend_max_entries : int
        每个 cell 的 legend 最大条目数（预留空间上限），0 表示无 legend
    legend_default_position : str
        legend 首选位置，默认 "top-right"。最终位置由 renderer 根据内容宽度决定
    legend_fallback : list[str] | None
        legend 放不下时的备选位置列表，None 使用默认 ["right", "bottom"]
    auto_margins : bool
        True: 按比例自动推算边距
    manual_margins : dict | None
        手动边距 {"top":..., "bottom":..., "left":..., "right":...}
    manual_gap : float | None
        手动 cell 间距
    width_ratios / height_ratios : list[float] | None
        仅在均匀网格模式生效。按整张画布的可用宽高分配列宽/行高，
        类似 matplotlib GridSpec 的 width_ratios / height_ratios。
    font_ratios / font_limits / spacing_ratios : dict | None
        字号/间距比例覆盖

    Returns
    -------
    dict — LayoutSpec

    Examples
    --------
    >>> # 混合布局（含 row_span）
    >>> spec = build_layout(
    ...     layout=[[(2, 2), 1, 1], [None, 2, 1]],
    ...     aspect="16:9", base="medium",
    ... )
    >>> # Row 0: 大图 col_span=2 row_span=2 + 2 个小图
    >>> # Row 1: 中间 2 个小图（左边被大图占用） + 1 个小图

    >>> # 均匀网格
    >>> spec = build_layout(rows=2, cols=2, aspect="4:3", base="medium")

    >>> # 兼容: 显式 px
    >>> spec = build_layout(rows=2, cols=2, canvas_width=960, canvas_height=640)
    """
    # Resolve topology before cell-first canvas sizing, including direct callers.
    if layout is not None:
        rows, cols = parse_layout_weights(layout)
    else:
        rows = 2 if rows is None else rows
        cols = 2 if cols is None else cols

    # ── 0. 解析画布尺寸 ──
    # 优先级: 显式 px > cell_base (cell-first) > base (canvas-first)
    if canvas_width is not None and canvas_height is not None:
        cw = float(canvas_width)
        ch = float(canvas_height)
        resolved_aspect = cw / ch
    elif cell_base is not None:
        cw, ch = resolve_canvas_from_cell(
            cell_base=cell_base, rows=rows or 2, cols=cols or 2, aspect=aspect,
        )
        cw = float(cw)
        ch = float(ch)
        resolved_aspect = cw / ch
    else:
        cw, ch = resolve_canvas(aspect=aspect, base=base)
        cw = float(cw)
        ch = float(ch)
        resolved_aspect = cw / ch

    # ── 0.5 推断 rows/cols ──
    if layout is not None:
        rows, cols = parse_layout_weights(layout)
    else:
        if rows is None:
            rows = 2
        if cols is None:
            cols = 2

    # ── 1. 网格计算 ──
    if layout is not None:
        # 混合布局模式
        if auto_margins:
            gs = compute_grid_mixed_auto(
                layout=layout,
                canvas_width=cw,
                canvas_height=ch,
                gap=manual_gap,
            )
        else:
            margins = manual_margins or {}
            gs = compute_grid_mixed(
                layout=layout,
                canvas_width=cw,
                canvas_height=ch,
                margin_top=margins.get("top", 50),
                margin_bottom=margins.get("bottom", 40),
                margin_left=margins.get("left", 60),
                margin_right=margins.get("right", 30),
                gap_x=manual_gap if manual_gap is not None else 14,
                gap_y=manual_gap if manual_gap is not None else 14,
            )
    elif width_ratios is not None or height_ratios is not None:
        if auto_margins:
            gs = compute_grid_ratios_auto_margins(
                rows=rows,
                cols=cols,
                canvas_width=cw,
                canvas_height=ch,
                gap=manual_gap,
                width_ratios=width_ratios,
                height_ratios=height_ratios,
            )
        else:
            margins = manual_margins or {}
            gs = compute_grid_ratios(
                rows=rows,
                cols=cols,
                canvas_width=cw,
                canvas_height=ch,
                margin_top=margins.get("top", 50),
                margin_bottom=margins.get("bottom", 40),
                margin_left=margins.get("left", 60),
                margin_right=margins.get("right", 30),
                gap=manual_gap if manual_gap is not None else 14,
                width_ratios=width_ratios,
                height_ratios=height_ratios,
            )
    elif auto_margins:
        gs = compute_grid_auto_margins(
            rows=rows, cols=cols,
            canvas_width=cw, canvas_height=ch,
            gap=manual_gap,
        )
    else:
        margins = manual_margins or {}
        gs = compute_grid(
            rows=rows, cols=cols,
            canvas_width=cw, canvas_height=ch,
            margin_top=margins.get("top", 50),
            margin_bottom=margins.get("bottom", 40),
            margin_left=margins.get("left", 60),
            margin_right=margins.get("right", 30),
            gap=manual_gap if manual_gap is not None else 14,
        )

    use_direct_grid_geometry = (
        layout is not None or
        width_ratios is not None or
        height_ratios is not None
    )

    # ── 2. 尺寸推导 ──
    if use_direct_grid_geometry:
        # 混合布局：用 grid cells 的真实几何计算每个 cell sizing
        ss = compute_sizing(
            rows=rows, cols=cols,
            canvas_width=cw, canvas_height=ch,
            legend_max_entries_per_cell=legend_max_entries,
            font_ratios=font_ratios,
            font_limits=font_limits,
            spacing_ratios=spacing_ratios,
        )
        # 用 grid cells 覆盖几何，但保留字体推算
        margin_top = ss.margin_top
        margin_bottom = ss.margin_bottom
        margin_left = ss.margin_left
        margin_right = ss.margin_right
        gap = ss.gap
        main_title_font = ss.main_title_font_size
    else:
        ss = compute_sizing(
            rows=rows, cols=cols,
            canvas_width=cw, canvas_height=ch,
            legend_max_entries_per_cell=legend_max_entries,
            font_ratios=font_ratios,
            font_limits=font_limits,
            spacing_ratios=spacing_ratios,
        )
        margin_top = ss.margin_top
        margin_bottom = ss.margin_bottom
        margin_left = ss.margin_left
        margin_right = ss.margin_right
        gap = ss.gap
        main_title_font = ss.main_title_font_size

    # ── 3. 组装 LayoutSpec（统一处理）──
    from data_visuals.layout.sizing import DEFAULT_FONT_RATIOS as FR
    from data_visuals.layout.sizing import DEFAULT_LIMITS as FL

    font_ratios_merged = {**FR, **(font_ratios or {})}
    font_limits_merged = {**FL, **(font_limits or {})}
    figure_fonts = compute_figure_font_sizes(
        cw, ch,
        font_ratios=font_ratios_merged,
        font_limits=font_limits_merged,
    )
    main_title_font = figure_fonts["main_title"]
    figure_cell_title_fs = figure_fonts["title"]
    figure_axis_fs = figure_fonts["axis_label"]
    figure_tick_fs = figure_fonts["tick"]
    figure_legend_fs = figure_fonts["legend"]

    cells_list: List[Dict[str, Any]] = []

    if use_direct_grid_geometry:
        # 对每个 grid cell 单独做 sizing
        for gc in gs.cells:
            title_fs = figure_cell_title_fs
            axis_fs = figure_axis_fs
            tick_fs = figure_tick_fs
            legend_fs = figure_legend_fs
            x_label_h = axis_fs * 1.8
            y_label_w = axis_fs * 5.0
            legend_h = legend_fs * 1.8 * __import__('math').ceil(legend_max_entries / 3) if legend_max_entries > 0 else 0

            dz_x = gc.x + y_label_w
            dz_y = gc.y + title_fs * 1.5 + legend_h
            dz_w = gc.w - y_label_w
            dz_h = gc.h - title_fs * 1.5 - x_label_h - legend_h

            cells_list.append({
                "row": gc.row, "col": gc.col,
                "x": round(gc.x, 1),
                "y": round(gc.y, 1),
                "w": round(gc.w, 1),
                "h": round(gc.h, 1),
                "col_span": gc.col_span, "row_span": gc.row_span,
                "font_sizes": {
                    "title": round(title_fs, 1),
                    "axis_label": round(axis_fs, 1),
                    "tick": round(tick_fs, 1),
                    "legend": round(legend_fs, 1),
                },
                "label_margins": {
                    "x_label_height": round(x_label_h, 1),
                    "y_label_width": round(y_label_w, 1),
                },
                "legend": {
                    "max_entries": legend_max_entries,
                    "font_size": round(legend_fs, 1),
                    "reserved_height": round(legend_h, 1),
                    "reserved_width": round(gc.w * 0.7, 1),
                    "default_position": legend_default_position if legend_max_entries > 0 else "none",
                    "fallback": legend_fallback or DEFAULT_LEGEND_FALLBACK,
                    "deferred": True,   # renderer 拿到实际内容后再定 final position
                },
                "data_zone": {
                    "x": round(dz_x, 1), "y": round(dz_y, 1),
                    "w": round(dz_w, 1), "h": round(dz_h, 1),
                },
            })
    else:
        for i, cell_sizing in enumerate(ss.iter_cells()):
            gc = gs.cells[i] if i < len(gs.cells) else None
            col_span = gc.col_span if gc else 1
            row_span = gc.row_span if gc else 1
            legend_fs = figure_legend_fs
            cells_list.append({
            "row": cell_sizing.row,
            "col": cell_sizing.col,
            "x": round(cell_sizing.x, 1),
            "y": round(cell_sizing.y, 1),
            "w": round(cell_sizing.w, 1),
            "h": round(cell_sizing.h, 1),
            "col_span": col_span,
            "row_span": row_span,
            "font_sizes": {
                "title": round(cell_sizing.title_font_size, 1),
                "axis_label": round(cell_sizing.axis_label_font_size, 1),
                "tick": round(cell_sizing.tick_label_font_size, 1),
                "legend": round(legend_fs, 1),
            },
            "label_margins": {
                "x_label_height": round(cell_sizing.x_label_height, 1),
                "y_label_width": round(cell_sizing.y_label_width, 1),
            },
            "legend": {
                "max_entries": cell_sizing.legend_max_entries,
                "font_size": round(legend_fs, 1),
                "reserved_height": round(legend_fs * 1.8 * __import__('math').ceil(cell_sizing.legend_max_entries / 3), 1) if cell_sizing.legend_max_entries > 0 else 0.0,
                "reserved_width": round(cell_sizing.legend_reserved_width, 1),
                "default_position": legend_default_position if cell_sizing.legend_max_entries > 0 else "none",
                "fallback": legend_fallback or DEFAULT_LEGEND_FALLBACK,
                "deferred": True,
            },
            "data_zone": {
                "x": round(cell_sizing.data_zone[0], 1),
                "y": round(cell_sizing.y + cell_sizing.title_font_size * 1.5 + (legend_fs * 1.8 * __import__('math').ceil(cell_sizing.legend_max_entries / 3) if cell_sizing.legend_max_entries > 0 else 0.0), 1),
                "w": round(cell_sizing.data_zone[2], 1),
                "h": round(cell_sizing.h - cell_sizing.title_font_size * 1.5 - cell_sizing.x_label_height - (legend_fs * 1.8 * __import__('math').ceil(cell_sizing.legend_max_entries / 3) if cell_sizing.legend_max_entries > 0 else 0.0), 1),
            },
        })

    # Every layout mode, including cell-first, uses the actual global canvas.
    for cell in cells_list:
        cell["font_sizes"].update(title=round(figure_cell_title_fs, 1),
                                  axis_label=round(figure_axis_fs, 1),
                                  tick=round(figure_tick_fs, 1),
                                  legend=round(figure_legend_fs, 1))
        cell["legend"]["font_size"] = round(figure_legend_fs, 1)
        title_fs, axis_fs = cell["font_sizes"]["title"], cell["font_sizes"]["axis_label"]
        legend_h = figure_legend_fs * 1.8 * __import__('math').ceil(legend_max_entries / 3)
        cell["label_margins"] = {"x_label_height": round(axis_fs * 1.8, 1),
                                 "y_label_width": round(axis_fs * 5.0, 1)}
        cell["legend"]["reserved_height"] = round(legend_h, 1)
        cell["data_zone"] = {
            "x": round(cell["x"] + axis_fs * 5.0, 1),
            "y": round(cell["y"] + title_fs * 1.5 + legend_h, 1),
            "w": round(cell["w"] - axis_fs * 5.0, 1),
            "h": round(cell["h"] - title_fs * 1.5 - axis_fs * 1.8 - legend_h, 1),
        }

    return {
        "canvas": {
            "width": cw,
            "height": ch,
            "dpi": dpi,
            "aspect": aspect_to_str(resolved_aspect),
            "aspect_ratio": round(resolved_aspect, 3),
        },
        "grid": {
            "rows": rows,
            "cols": cols,
            "gap": round(gap, 1),
        },
        "margins": {
            "top": round(margin_top, 1),
            "bottom": round(margin_bottom, 1),
            "left": round(margin_left, 1),
            "right": round(margin_right, 1),
        },
        "title": {
            "text": title or "",
            "font_size": round(main_title_font, 1),
        },
        "subtitle": {
            "text": subtitle or "",
            "font_size": round(main_title_font * 0.7, 1),
        },
        "cells": cells_list,
        "shared_legend": {
            "enabled": shared_legend,
            "group_column": shared_group_column,
            "font_size": round(figure_legend_fs, 1),
            "reserved_height": round(
                figure_legend_fs * 4.5, 1
            ),
        } if shared_legend else {
            "enabled": False,
            "group_column": "",
            "font_size": 0,
            "reserved_height": 0,
        },
    }


# ── 调试打印 ──────────────────────────────────────────────────

def print_layout(spec: Dict[str, Any]) -> None:
    """将 LayoutSpec 以可读格式打印到控制台（调试用）"""
    canvas = spec["canvas"]
    grid = spec["grid"]
    margins = spec["margins"]
    title = spec["title"]
    cells = spec["cells"]

    print()
    print("=" * 60)
    print(f"  LayoutSpec: {canvas['width']:.0f}×{canvas['height']:.0f} px  "
          f"({canvas.get('aspect', '?')})  @{canvas['dpi']}dpi")
    print(f"  Grid: {grid['rows']}×{grid['cols']}  gap={grid['gap']}px")
    print(f"  Margins: T={margins['top']} B={margins['bottom']} "
          f"L={margins['left']} R={margins['right']}")
    if title["text"]:
        print(f"  Title: \"{title['text']}\" ({title['font_size']}pt)")
    print("-" * 60)
    for c in cells:
        fs = c["font_sizes"]
        lm = c["label_margins"]
        dz = c["data_zone"]
        span = c.get("col_span", 1)
        span_str = f" span={span}" if span > 1 else ""
        print(f"  Cell({c['row']},{c['col']})"
              f"{span_str} "
              f"pos=({c['x']:.0f},{c['y']:.0f}) "
              f"size=({c['w']:.0f}×{c['h']:.0f})")
        print(f"    fonts: title={fs['title']}pt axis={fs['axis_label']}pt "
              f"tick={fs['tick']}pt legend={fs['legend']}pt")
        print(f"    labels: x_h={lm['x_label_height']}px y_w={lm['y_label_width']}px")
        print(f"    data_zone: x={dz['x']:.0f} y={dz['y']:.0f} "
              f"w={dz['w']:.0f} h={dz['h']:.0f}")
        if c["legend"].get("max_entries", c["legend"].get("entries", 0)) > 0:
            lg = c["legend"]
            print(f"    legend: {lg.get('max_entries', lg.get('entries', 0))} slots "
                  f"h={lg.get('reserved_height', '?'):.0f}px "
                  f"@{lg['font_size']}pt "
                  f"[default={lg.get('default_position', '?')}]"
                  f" {'(deferred)' if lg.get('deferred') else ''}")
    print("=" * 60)
    print()
