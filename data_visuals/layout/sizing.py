"""
layout/sizing.py
================
旧尺寸路径的兼容引擎 — 字号按全局画布短边推导。
物理 canvas 路径由 layout/physical.py 使用主题 publication 中的固定 pt 字号。

核心原则:
    ┌──────────────────────────────────────────┐
    │  所有尺寸 = clamp(比例基准, 下限, 上限)     │
    │                                        │
    │  同一 Figure 共用字号层级 — 比例驱动        │
    │  禁止硬编码 10pt / 12pt 等绝对值            │
    └──────────────────────────────────────────┘

设计参考:
    - CSS em / rem 相对单位思想
    - LaTeX 模板自动字号系统
    - 印刷排版中正文/标题/脚注的比例关系
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any


# ── 工具函数 ──────────────────────────────────────────────────

def clamp(value: float, lo: float, hi: float) -> float:
    """将 value 限制在 [lo, hi] 区间"""
    return max(lo, min(value, hi))


# ── 字号比例基准 ──────────────────────────────────────────────

# All figure typography uses S = min(canvas_width, canvas_height).
# Legacy cell-ratio keys remain accepted in old calibration tools; the
# figure_* roles below define the typography consumed by every subplot.

DEFAULT_FONT_RATIOS = {
    "main_title":  0.045,    # 主标题 / S
    "cell_title":  0.065,    # 子图标题 / cell_h
    "figure_cell_title": 0.028,  # 子图标题 / S — all layouts
    "figure_axis_label": 0.018,  # 轴标签 / S — all layouts
    "figure_tick_label": 0.015,  # 刻度标签 / S — all layouts
    "axis_label":  0.060,    # 轴标签 / min(cell_w, cell_h)
    "tick_label":  0.050,    # 刻度标签 / min(cell_w, cell_h)
    "legend":      0.040,    # legend / min(cell_w, cell_h) — per-cell legend
    "figure_legend": 0.020,  # legend / min(canvas_w, canvas_h) — all legends
}

# 下限：保证极小 cell 可读；上限：poster(3600px)级别仍纯比例驱动
# poster 单 cell ~2100px → 上限取 ceil(2100×ratio)
DEFAULT_LIMITS = {
    "main_title":  (12, 102),
    "cell_title":  (10,  80),
    "figure_cell_title": (10, 40),
    "figure_axis_label": (8, 46),
    "figure_tick_label": (7, 39),
    "axis_label":  ( 8,  68),
    "tick_label":  ( 7,  54),
    "legend":      ( 7,  20),
    "figure_legend": ( 8,  40),
}

# 间距基准比例
DEFAULT_SPACING_RATIOS = {
    "margin":    0.04,      # 边距 / min(canvas_w, canvas_h)
    "gap":       0.015,     # cell 间距 / min(canvas_w, canvas_h)
}

# ── cell-first 参考尺寸 ──────────────────────────────────────
# 每种 base 对应的参考 cell 尺寸 (w, h)。
# 值为 2×2 grid + auto_margins 在对应 base 下的 cell 尺寸，
# 保证 cell-first 与 canvas-first 在 2×2 时完全向后兼容。
#   base       canvas       cell (w×h)
#   small      800×500      376×226
#   medium     1200×750     564×339
#   large      1800×1125    847×509
#   poster     3600×2250    1703×1028

CELL_SIZE_PRESETS: Dict[str, Tuple[float, float]] = {
    "small":  (376, 226),
    "medium": (564, 339),
    "large":  (847, 509),
    "poster": (1703, 1028),
}


@dataclass
class CellSizing:
    """单个 cell 的尺寸规格"""

    row: int
    col: int

    # 几何 (来自 grid)
    x: float
    y: float
    w: float
    h: float

    # 字号 (pt)
    title_font_size: float
    axis_label_font_size: float
    tick_label_font_size: float
    legend_font_size: float

    # 轴标签预留空间 (px, 估算)
    x_label_height: float       # x 轴标签所需高度
    y_label_width: float        # y 轴标签所需宽度

    # legend 占位估算（延迟决策：只预留空间，不定位置）
    legend_max_entries: int = 0
    legend_reserved_height: float = 0   # 预留高度 (水平排列，3列/行)
    legend_reserved_width: float = 0    # 预留宽度 (垂直排列时用)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "col": self.col,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "title_font_size": self.title_font_size,
            "axis_label_font_size": self.axis_label_font_size,
            "tick_label_font_size": self.tick_label_font_size,
            "legend_font_size": self.legend_font_size,
            "x_label_height": self.x_label_height,
            "y_label_width": self.y_label_width,
            "legend_max_entries": self.legend_max_entries,
            "legend_reserved_height": self.legend_reserved_height,
            "legend_reserved_width": self.legend_reserved_width,
        }

    @property
    def data_zone(self) -> Tuple[float, float, float, float]:
        """
        数据绘图区的有效区域 (x, y, w, h)，排除轴标注和 legend 后。
        近似估算，实际使用由 renderer 精算。
        """
        return (
            self.x + self.y_label_width,
            self.y + self.title_font_size * 1.5 + self.legend_reserved_height,
            self.w - self.y_label_width,
            self.h - self.title_font_size * 1.5 - self.x_label_height - self.legend_reserved_height,
        )


@dataclass
class SizingSpec:
    """完整的尺寸规格"""

    # 画布级
    canvas_width: float
    canvas_height: float

    # 主标题
    main_title_font_size: float

    # 边距/间距
    margin_top: float
    margin_bottom: float
    margin_left: float
    margin_right: float
    gap: float

    # 每个 cell 的 sizing
    cells: Dict[Tuple[int, int], CellSizing] = field(default_factory=dict)

    def get_cell(self, row: int, col: int) -> CellSizing:
        return self.cells[(row, col)]

    def iter_cells(self):
        """按行优先遍历"""
        keys = sorted(self.cells.keys(), key=lambda k: (k[0], k[1]))
        for k in keys:
            yield self.cells[k]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "main_title_font_size": self.main_title_font_size,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "gap": self.gap,
            "cells": [c.to_dict() for c in self.iter_cells()],
        }


def compute_figure_font_sizes(
    canvas_width: float,
    canvas_height: float,
    *,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
) -> Dict[str, float]:
    """Resolve every text role from one global, DPI-independent design scale."""
    ratios = {**DEFAULT_FONT_RATIOS, **(font_ratios or {})}
    limits = {**DEFAULT_LIMITS, **(font_limits or {})}
    scale = min(canvas_width, canvas_height)
    roles = {
        "main_title": "main_title",
        "title": "figure_cell_title",
        "axis_label": "figure_axis_label",
        "tick": "figure_tick_label",
        "legend": "figure_legend",
    }
    return {role: clamp(scale * ratios[key], *limits[key]) for role, key in roles.items()}


def compute_sizing(
    rows: int,
    cols: int,
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    legend_max_entries_per_cell: int = 0,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
    spacing_ratios: Dict[str, float] | None = None,
) -> SizingSpec:
    """
    根据画布和网格计算所有字号与间距。

    核心逻辑:
        1. 按比例推算边距与间距
        2. 按 formula(基准, 比例) 计算 cell 尺寸
        3. 按全局 canvas 短边推算统一字号
        4. 估算轴标签/legend 占用空间

    Parameters
    ----------
    rows, cols : int
        网格行列数
    canvas_width, canvas_height : float
        画布尺寸 (px)，默认 960×640
    legend_max_entries_per_cell : int
        每个 cell 的 legend 最大条目数（预留空间上限），0 表示无 legend
    font_ratios : dict | None
        字号比例覆盖，key ∈ {"main_title", "figure_cell_title",
        "figure_axis_label", "figure_tick_label", "figure_legend"}
    font_limits : dict | None
        字号上下限覆盖
    spacing_ratios : dict | None
        间距比例覆盖，key ∈ {"margin","gap"}

    Returns
    -------
    SizingSpec

    Examples
    --------
    >>> spec = compute_sizing(rows=2, cols=2, canvas_width=960, canvas_height=640)
    >>> for cell in spec.iter_cells():
    ...     print(f"Cell({cell.row},{cell.col}) title={cell.title_font_size:.0f}pt")
    Cell(0,0) title=18pt
    Cell(0,1) title=18pt
    Cell(1,0) title=18pt
    Cell(1,1) title=18pt
    """
    # 合并比例和限制
    fr = {**DEFAULT_FONT_RATIOS, **(font_ratios or {})}
    fl = {**DEFAULT_LIMITS, **(font_limits or {})}
    sr = {**DEFAULT_SPACING_RATIOS, **(spacing_ratios or {})}

    min_canvas = min(canvas_width, canvas_height)

    # ── 1. 间距计算 ──
    margin = clamp(min_canvas * sr["margin"], 20, 80)
    gap = clamp(min_canvas * sr["gap"], 8, 40)

    # ── 2. cell 几何计算 ──
    usable_w = canvas_width - 2 * margin - (cols - 1) * gap
    usable_h = canvas_height - 2 * margin - (rows - 1) * gap

    cell_w = usable_w / cols
    cell_h = usable_h / rows

    # ── 3. 主标题字号 ──
    figure_fonts = compute_figure_font_sizes(
        canvas_width, canvas_height, font_ratios=fr, font_limits=fl,
    )
    main_title_font = figure_fonts["main_title"]

    # ── 4. 每个 cell 的字号 ──
    cells_dict: Dict[Tuple[int, int], CellSizing] = {}
    for r in range(rows):
        for c in range(cols):
            x = margin + c * (cell_w + gap)
            y = margin + r * (cell_h + gap)

            title_fs = figure_fonts["title"]
            axis_fs = figure_fonts["axis_label"]
            tick_fs = figure_fonts["tick"]
            legend_fs = figure_fonts["legend"]

            # 标签占位估算: 字号 + 行距
            x_label_h = axis_fs * 1.8
            y_label_w = axis_fs * 5.0   # 粗略按 5 个字符宽估算

            # legend 预留: 水平排列，每行 3 列，行数 = ceil(n/3)
            # 高度 = 行数 × 字号 × 1.8; 宽度 = 预留 cell_w 的 70%
            if legend_max_entries_per_cell > 0:
                import math
                n_rows_legend = math.ceil(legend_max_entries_per_cell / 3)
                legend_reserved_h = legend_fs * 1.8 * n_rows_legend
                legend_reserved_w = cell_w * 0.7
            else:
                legend_reserved_h = 0.0
                legend_reserved_w = 0.0

            cells_dict[(r, c)] = CellSizing(
                row=r,
                col=c,
                x=x,
                y=y,
                w=cell_w,
                h=cell_h,
                title_font_size=title_fs,
                axis_label_font_size=axis_fs,
                tick_label_font_size=tick_fs,
                legend_font_size=legend_fs,
                x_label_height=x_label_h,
                y_label_width=y_label_w,
                legend_max_entries=legend_max_entries_per_cell,
                legend_reserved_height=legend_reserved_h,
                legend_reserved_width=legend_reserved_w,
            )

    return SizingSpec(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        main_title_font_size=main_title_font,
        margin_top=margin,
        margin_bottom=margin,
        margin_left=margin,
        margin_right=margin,
        gap=gap,
        cells=cells_dict,
    )


def compute_figure_legend_font_size(
    canvas_width: float,
    canvas_height: float,
    *,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
) -> float:
    """Compute a figure-level legend font size shared by all legend modes.

    Shared legends and per-cell legends both use the whole figure as the
    proportional baseline so legend scale stays stable across 1×1 and multi-cell
    compositions.
    """
    return compute_figure_font_sizes(
        canvas_width, canvas_height, font_ratios=font_ratios, font_limits=font_limits,
    )["legend"]


def compute_figure_cell_title_font_size(
    canvas_width: float,
    canvas_height: float,
    *,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
) -> float:
    """Compute the shared subplot title size for every layout mode."""
    return compute_figure_font_sizes(
        canvas_width, canvas_height, font_ratios=font_ratios, font_limits=font_limits,
    )["title"]


def compute_figure_axis_label_font_size(
    canvas_width: float,
    canvas_height: float,
    *,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
) -> float:
    """Compute a shared axis-label size for mixed/ratio layouts."""
    return compute_figure_font_sizes(
        canvas_width, canvas_height, font_ratios=font_ratios, font_limits=font_limits,
    )["axis_label"]


def compute_figure_tick_label_font_size(
    canvas_width: float,
    canvas_height: float,
    *,
    font_ratios: Dict[str, float] | None = None,
    font_limits: Dict[str, Tuple[float, float]] | None = None,
) -> float:
    """Compute a shared tick-label size for mixed/ratio layouts."""
    return compute_figure_font_sizes(
        canvas_width, canvas_height, font_ratios=font_ratios, font_limits=font_limits,
    )["tick"]
