"""
layout/grid.py
==============
纯几何网格计算 — 给定画布尺寸和行列数，计算每个 cell 的坐标和尺寸。

职责:
    - 解析用户的行列声明 → 网格划分
    - 计算每个 cell 的 (x, y, w, h) 绝对坐标
    - 输出单元格列表供下游消费

边界:
    - 不管字体/字号 → sizing.py
    - 不管图表类型 → charts/
    - 不管渲染 → renderer/

设计参考: CSS Grid / LaTeX subfigure / matplotlib gridspec
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union, List, Tuple, Dict, Any


@dataclass
class Cell:
    """网格中的一个单元格"""

    row: int
    col: int
    x: float           # 相对于画布左上角的 x 坐标 (px)
    y: float           # 相对于画布左上角的 y 坐标 (px)
    w: float           # 宽度 (px)
    h: float           # 高度 (px)

    # 跨格 (暂未实现，预留)
    row_span: int = 1
    col_span: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row": self.row,
            "col": self.col,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "row_span": self.row_span,
            "col_span": self.col_span,
        }

    def __repr__(self) -> str:
        return (
            f"Cell(r{self.row},c{self.col}) "
            f"[x={self.x:.0f} y={self.y:.0f} w={self.w:.0f} h={self.h:.0f}]"
        )


@dataclass
class GridSpec:
    """完整的网格布局规格"""

    rows: int
    cols: int

    # 画布
    canvas_width: float
    canvas_height: float

    # 边距
    margin_top: float
    margin_bottom: float
    margin_left: float
    margin_right: float

    # 间距
    gap: float

    # 单元格列表
    cells: List[Cell] = field(default_factory=list)

    @property
    def usable_width(self) -> float:
        """去掉左右边距后的可用宽度"""
        return self.canvas_width - self.margin_left - self.margin_right

    @property
    def usable_height(self) -> float:
        """去掉上下边距后的可用高度"""
        return self.canvas_height - self.margin_top - self.margin_bottom

    def get_cell(self, row: int, col: int) -> Optional[Cell]:
        """按行列坐标查找 Cell"""
        for c in self.cells:
            if c.row == row and c.col == col:
                return c
        return None

    def iter_cells(self):
        """按行优先遍历所有 cell"""
        return iter(self.cells)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "gap": self.gap,
            "cells": [c.to_dict() for c in self.cells],
        }

    def __repr__(self) -> str:
        lines = [
            f"GridSpec({self.rows}×{self.cols}) "
            f"canvas=({self.canvas_width:.0f}×{self.canvas_height:.0f}) "
            f"gap={self.gap:.0f} "
            f"margin=({self.margin_top:.0f},{self.margin_right:.0f},{self.margin_bottom:.0f},{self.margin_left:.0f})"
        ]
        for c in self.cells:
            lines.append(f"  {c}")
        return "\n".join(lines)


def compute_grid(
    rows: int,
    cols: int,
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    margin_top: float = 50,
    margin_bottom: float = 40,
    margin_left: float = 60,
    margin_right: float = 30,
    gap: float = 14,
) -> GridSpec:
    """
    计算网格布局。

    Parameters
    ----------
    rows : int
        行数
    cols : int
        列数
    canvas_width : float
        画布总宽度 (px)，默认 960
    canvas_height : float
        画布总高度 (px)，默认 640
    margin_top / margin_bottom / margin_left / margin_right : float
        四条边的外边距 (px)
    gap : float
        cell 之间的间距 (px)

    Returns
    -------
    GridSpec — 包含所有 cell 的坐标和尺寸

    Examples
    --------
    >>> gs = compute_grid(rows=2, cols=2, canvas_width=900, canvas_height=600)
    >>> for cell in gs.iter_cells():
    ...     print(cell)
    Cell(r0,c0) [x=60 y=50 w=395 h=240]
    Cell(r0,c1) [x=469 y=50 w=395 h=240]
    Cell(r1,c0) [x=60 y=304 w=395 h=240]
    Cell(r1,c1) [x=469 y=304 w=395 h=240]
    """
    if rows < 1 or cols < 1:
        raise ValueError(f"rows 和 cols 必须 ≥ 1，当前: rows={rows}, cols={cols}")

    # 计算每个 cell 的尺寸
    usable_w = canvas_width - margin_left - margin_right - (cols - 1) * gap
    usable_h = canvas_height - margin_top - margin_bottom - (rows - 1) * gap

    cell_w = usable_w / cols
    cell_h = usable_h / rows

    # 生成所有 cell
    cells: List[Cell] = []
    for r in range(rows):
        for c in range(cols):
            x = margin_left + c * (cell_w + gap)
            y = margin_top + r * (cell_h + gap)
            cells.append(Cell(row=r, col=c, x=x, y=y, w=cell_w, h=cell_h))

    return GridSpec(
        rows=rows,
        cols=cols,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_right=margin_right,
        gap=gap,
        cells=cells,
    )


def compute_grid_auto_margins(
    rows: int,
    cols: int,
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    gap: Optional[float] = None,
    margin_ratio: float = 0.04,
) -> GridSpec:
    """
    自动按比例计算边距的网格布局。

    边距 = min(canvas_width, canvas_height) × margin_ratio
    间距 = 边距 × 0.35，且 ≥ 8

    Parameters
    ----------
    rows, cols : int
    canvas_width, canvas_height : float
    gap : float | None
        间距，None 则按比例自动计算
    margin_ratio : float
        边距占画布较短边的比例，默认 4%

    Returns
    -------
    GridSpec
    """
    min_canvas = min(canvas_width, canvas_height)

    margin = max(20.0, min_canvas * margin_ratio)

    if gap is None:
        gap = max(8.0, min_canvas * margin_ratio * 0.35)

    return compute_grid(
        rows=rows,
        cols=cols,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin,
        margin_bottom=margin,
        margin_left=margin,
        margin_right=margin,
        gap=gap,
    )


def _normalize_ratios(ratios: Optional[List[float]], n: int, name: str) -> List[float]:
    """Normalize ratio vectors for width/height allocation."""
    if ratios is None:
        return [1.0] * n
    if len(ratios) != n:
        raise ValueError(f"{name} 长度必须等于 {n}，当前为 {len(ratios)}")
    if any(r <= 0 for r in ratios):
        raise ValueError(f"{name} 中所有值必须 > 0，当前: {ratios}")
    total = float(sum(ratios))
    return [float(r) / total for r in ratios]


def compute_grid_ratios(
    rows: int,
    cols: int,
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    margin_top: float = 50,
    margin_bottom: float = 40,
    margin_left: float = 60,
    margin_right: float = 30,
    gap: float = 14,
    width_ratios: Optional[List[float]] = None,
    height_ratios: Optional[List[float]] = None,
) -> GridSpec:
    """Compute a ratio-based grid that fills the full figure canvas.

    Unlike uniform grids, each column/row can take a custom fraction of the
    available width/height. This matches seaborn/matplotlib-style figure-first
    layout while preserving the existing absolute geometry contract.
    """
    if rows < 1 or cols < 1:
        raise ValueError(f"rows 和 cols 必须 ≥ 1，当前: rows={rows}, cols={cols}")

    normalized_w = _normalize_ratios(width_ratios, cols, "width_ratios")
    normalized_h = _normalize_ratios(height_ratios, rows, "height_ratios")

    usable_w = canvas_width - margin_left - margin_right - (cols - 1) * gap
    usable_h = canvas_height - margin_top - margin_bottom - (rows - 1) * gap

    col_widths = [usable_w * ratio for ratio in normalized_w]
    row_heights = [usable_h * ratio for ratio in normalized_h]

    x_positions: List[float] = []
    x_cursor = margin_left
    for width in col_widths:
        x_positions.append(x_cursor)
        x_cursor += width + gap

    y_positions: List[float] = []
    y_cursor = margin_top
    for height in row_heights:
        y_positions.append(y_cursor)
        y_cursor += height + gap

    cells: List[Cell] = []
    for r in range(rows):
        for c in range(cols):
            cells.append(
                Cell(
                    row=r,
                    col=c,
                    x=x_positions[c],
                    y=y_positions[r],
                    w=col_widths[c],
                    h=row_heights[r],
                )
            )

    return GridSpec(
        rows=rows,
        cols=cols,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_right=margin_right,
        gap=gap,
        cells=cells,
    )


def compute_grid_ratios_auto_margins(
    rows: int,
    cols: int,
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    gap: Optional[float] = None,
    margin_ratio: float = 0.04,
    width_ratios: Optional[List[float]] = None,
    height_ratios: Optional[List[float]] = None,
) -> GridSpec:
    """Auto-margin wrapper for ratio-based grid allocation."""
    min_canvas = min(canvas_width, canvas_height)

    margin = max(20.0, min_canvas * margin_ratio)

    if gap is None:
        gap = max(8.0, min_canvas * margin_ratio * 0.35)

    return compute_grid_ratios(
        rows=rows,
        cols=cols,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin,
        margin_bottom=margin,
        margin_left=margin,
        margin_right=margin,
        gap=gap,
        width_ratios=width_ratios,
        height_ratios=height_ratios,
    )


# ── 混合布局（不等宽 + 跨行） ────────────────────────────────

# 布局单元格值类型: int=col_span, (int,int)=(col_span, row_span), None=占位（被上方跨行占用）
CellWeight = Union[int, Tuple[int, int], None]


def parse_layout_weights(
    layout: List[List[Union[int, Tuple[int, int], None]]],
) -> Tuple[int, int]:
    """
    解析 layout 权重矩阵 → (physical_rows, total_cols)。

    每个单元格可以是:
        int         → col_span, row_span = 1
        (int, int)  → (col_span, row_span)
        None / 0    → 占位符，被上方跨行 cell 占用

    Examples
    --------
    >>> parse_layout_weights([[3, 1], [4]])
    (2, 4)
    >>> parse_layout_weights([[(2, 2), 1, 1], [None, 2, 0]])
    (2, 4)
    """
    rows = len(layout)
    cols = 0
    for row in layout:
        row_total = 0
        for val in row:
            if val is None or val == 0:
                continue  # 占位符不计入宽度
            if isinstance(val, tuple):
                row_total += val[0]
            else:
                row_total += val
        cols = max(cols, row_total)
    return rows, cols


def _resolve_cell_weight(val: Union[int, Tuple[int, int], None]) -> Tuple[int, int, bool]:
    """
    解析单个单元格值为 (col_span, row_span, is_placeholder)。

    >>> _resolve_cell_weight(3)       → (3, 1, False)
    >>> _resolve_cell_weight((2, 2))  → (2, 2, False)
    >>> _resolve_cell_weight(None)    → (0, 0, True)
    >>> _resolve_cell_weight(0)       → (0, 0, True)
    """
    if val is None or val == 0:
        return 0, 0, True
    if isinstance(val, tuple):
        return val[0], val[1], False
    return int(val), 1, False


def compute_grid_mixed(
    layout: List[List[Union[int, Tuple[int, int], None]]],
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    margin_top: float = 50,
    margin_bottom: float = 40,
    margin_left: float = 60,
    margin_right: float = 30,
    gap_x: float = 14,
    gap_y: float = 14,
) -> GridSpec:
    """
    混合布局 — 支持 col_span（跨列）和 row_span（跨行）。

    每个单元格可以是:
        int          → col_span 权重, row_span=1
        (int, int)   → (col_span, row_span)
        None / 0     → 占位符 (被上方跨行 cell 占用)

    Parameters
    ----------
    layout : list[list[int | (int,int) | None]]
        例如: [[(2, 2), 1, 1], [None, 2, 0]] 表示:
            Row 0: 大图 col_span=2 row_span=2, 再 2 个小图
            Row 1: 中间 2 个小图，两头被上面占

    Returns
    -------
    GridSpec

    Examples
    --------
    >>> gs = compute_grid_mixed(layout=[[3, 1], [4]], canvas_width=1200, canvas_height=675)
    >>> gs = compute_grid_mixed(layout=[[(2,2),1,1],[None,2,1]])
    """
    rows, cols = parse_layout_weights(layout)

    if rows < 1:
        raise ValueError(f"layout 至少需要 1 行，当前: {layout}")

    usable_w = canvas_width - margin_left - margin_right
    usable_h = canvas_height - margin_top - margin_bottom

    base_col_w = (usable_w - (cols - 1) * gap_x) / cols
    base_row_h = (usable_h - (rows - 1) * gap_y) / rows

    # 追踪哪些 (row,col) 网格格已占用
    occupied: Dict[Tuple[int, int], bool] = {}

    cells: List[Cell] = []
    for r, row_data in enumerate(layout):
        col_idx = 0

        for val in row_data:
            col_span, row_span, is_placeholder = _resolve_cell_weight(val)

            # 跳过已被占用的 grid 列
            while occupied.get((r, col_idx)):
                col_idx += 1

            x_cursor = margin_left + col_idx * (base_col_w + gap_x)

            if is_placeholder:
                # 占位符不创建 cell；下一个 entry 会从当前 col_idx 对应位置继续。
                continue

            # cell 宽度
            cell_w = base_col_w * col_span + (col_span - 1) * gap_x
            # cell 高度
            cell_h = base_row_h * row_span + (row_span - 1) * gap_y

            y = margin_top + r * (base_row_h + gap_y)

            # 标记占用的 grid cells
            for dr in range(row_span):
                for dc in range(col_span):
                    occupied[(r + dr, col_idx + dc)] = True

            cells.append(Cell(
                row=r,
                col=col_idx,
                x=x_cursor,
                y=y,
                w=cell_w,
                h=cell_h,
                col_span=col_span,
                row_span=row_span,
            ))

            col_idx += col_span

            # 跳过被占用的位置
            while occupied.get((r, col_idx)):
                col_idx += 1

    return GridSpec(
        rows=rows,
        cols=cols,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_right=margin_right,
        gap=gap_x,
        cells=cells,
    )


def compute_grid_mixed_auto(
    layout: List[List[Union[int, Tuple[int, int], None]]],
    *,
    canvas_width: float = 960,
    canvas_height: float = 640,
    gap: Optional[float] = None,
    margin_ratio: float = 0.04,
) -> GridSpec:
    """自动边距版本的混合布局网格（支持 row_span）。"""
    min_canvas = min(canvas_width, canvas_height)

    margin = max(20.0, min_canvas * margin_ratio)

    if gap is None:
        gap = max(8.0, min_canvas * margin_ratio * 0.35)

    return compute_grid_mixed(
        layout=layout,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        margin_top=margin,
        margin_bottom=margin,
        margin_left=margin,
        margin_right=margin,
        gap_x=gap,
        gap_y=gap,
    )
