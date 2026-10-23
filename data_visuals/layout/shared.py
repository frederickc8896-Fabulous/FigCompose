"""
layout/shared.py
================
共享轴检测 — 识别同行/同列 chart 是否共享 x/y 轴，合并标注以减少冗余。

职责:
    - 给定 LayoutSpec + chart 信息，检测可共享的轴
    - 返回修改后的 cells，缩减共享方向上的 label_margins

设计动机:
    论文中常见 2×2 benchmark 图，4 个子图使用相同 x 轴 (method)。
    当前每个 cell 都预留了独立 x_label_height，导致空间浪费。
    检测到共享后，仅最底行的 cell 保留 x_label，其余行缩减 x_label_height。

检测规则:
    同列: 同一列的所有 cell 若 y 轴变量相同 → 只有最左列保留 y_label_width
    同行: 同一行的所有 cell 若 x 轴变量相同 → 只有最底行保留 x_label_height

不负责:
    - 渲染（由 renderer 根据 shared 标记决定是否绘制重复轴标签）
    - grid 计算
"""

from __future__ import annotations

from typing import Optional, Dict, List, Any, Tuple


def detect_shared_axes(
    layout_spec: Dict[str, Any],
    chart_axes: Optional[List[Dict[str, Optional[str]]]] = None,
) -> Dict[str, Any]:
    """
    检测共享轴并缩减 label_margins。

    取 LayoutSpec 和 chart 轴信息，分析同行/列中可共享的轴标注，
    返回修改后的 LayoutSpec（原地修改 cells 的 label_margins
    和 shared_axes 标记）。

    Parameters
    ----------
    layout_spec : dict
        build_layout() 的输出
    chart_axes : list[dict] | None
        每个 cell 对应的轴变量，按 cell 顺序排列。
        每个 dict 格式: {"x": "variable_name", "y": "variable_name"}
        None 表示跳过检测（保持默认 margin）。
        列表长度应匹配 cells 数量。

    Returns
    -------
    dict — 修改后的 layout_spec，新增字段:
        cells[i]["shared_axes"] = {
            "x_shared": bool,     # x 轴标签可被同行底部 cell 共享
            "y_shared": bool,     # y 轴标签可被同列左侧 cell 共享
            "x_shared_with": int, # 共享给哪个 cell_idx（底部行 col），-1 表示自己
            "y_shared_with": int, # 共享给哪个 cell_idx（左侧 col），-1 表示自己
        }
        cells[i]["label_margins"] 中的 x_label_height / y_label_width
        对共享的 cell 会归零。

    Examples
    --------
    >>> spec = build_layout(rows=2, cols=2, aspect="4:3")
    >>> axes = [
    ...     {"x": "method", "y": "accuracy"},   # cell(0,0)
    ...     {"x": "method", "y": "loss"},       # cell(0,1) — 同 x 轴
    ...     {"x": "method", "y": "accuracy"},   # cell(1,0) — 同 x, y 轴
    ...     {"x": "method", "y": "loss"},       # cell(1,1)
    ... ]
    >>> spec = detect_shared_axes(spec, axes)
    >>> # cell(0,0) and cell(0,1) → x_label_height=0 (同行，x 相同，底行 cell(1,x) 展示)
    >>> # cell(0,0) and cell(1,0) → y_label_width=0 (同列，y 相同，左侧 cell(0,0) 展示)
    """
    if chart_axes is None:
        return layout_spec

    cells = layout_spec["cells"]
    grid = layout_spec["grid"]
    n_rows = grid["rows"]
    n_cols = grid["cols"]

    if len(chart_axes) != len(cells):
        # 图表轴信息数量与 cell 数不匹配，跳过
        return layout_spec

    # 建立 (row, col) → cell_idx 和 chart_axes 索引映射
    cell_by_pos: Dict[Tuple[int, int], int] = {}
    for i, cell in enumerate(cells):
        cell_by_pos[(cell["row"], cell["col"])] = i

    # ── 逐列检测 y 轴共享 ──
    for c in range(n_cols):
        col_cells = []
        for r in range(n_rows):
            idx = cell_by_pos.get((r, c))
            if idx is not None:
                col_cells.append(idx)

        if len(col_cells) > 1:
            y_values = set()
            for idx in col_cells:
                ax = chart_axes[idx]
                y_val = ax.get("y") if ax else None
                if y_val:
                    # Normalize: str → str, list → tuple for hashability
                    y_values.add(tuple(y_val) if isinstance(y_val, list) else y_val)

            if len(y_values) == 1 and len(y_values) > 0:
                # y 轴一致 → 只保留最上面 cell 的 y_label_width，下面归零
                keep_idx = col_cells[0]
                for idx in col_cells[1:]:
                    cells[idx]["label_margins"]["y_label_width"] = 0
                    cells[idx].setdefault("shared_axes", {})
                    cells[idx]["shared_axes"]["y_shared"] = True
                    cells[idx]["shared_axes"]["y_shared_with"] = keep_idx
                    cells[idx]["shared_axes"]["x_shared"] = False
                    cells[idx]["shared_axes"]["x_shared_with"] = -1

    # ── 逐列检测 x 轴跨行共享 ──
    # 检测所有行是否共享同一 x 轴变量 → 只有最底行保留 x_label_height
    all_x_values: Dict[int, set] = {}          # col → set of x values across rows
    col_cells_by_col: Dict[int, List[int]] = {}  # col → list of cell indices

    for r in range(n_rows):
        for c in range(n_cols):
            idx = cell_by_pos.get((r, c))
            if idx is not None:
                ax = chart_axes[idx]
                if ax and ax.get("x"):
                    all_x_values.setdefault(c, set()).add(ax["x"])
                    col_cells_by_col.setdefault(c, []).append(idx)

    # 如果同列所有行 x 值一致 → 只保留该列最底行的 x_label_height
    for c, x_vals in all_x_values.items():
        if len(x_vals) == 1 and len(col_cells_by_col.get(c, [])) > 1:
            cell_indices = sorted(col_cells_by_col[c], key=lambda i: cells[i]["row"])
            bottom_idx = cell_indices[-1]
            for idx in cell_indices[:-1]:
                cells[idx]["label_margins"]["x_label_height"] = 0
                cells[idx].setdefault("shared_axes", {})
                cells[idx]["shared_axes"]["x_shared"] = True
                cells[idx]["shared_axes"]["x_shared_with"] = bottom_idx
                cells[idx]["shared_axes"].setdefault("y_shared", False)
                cells[idx]["shared_axes"].setdefault("y_shared_with", -1)

    # 给未标记的 cell 补默认
    for cell in cells:
        cell.setdefault("shared_axes", {
            "x_shared": False,
            "y_shared": False,
            "x_shared_with": -1,
            "y_shared_with": -1,
        })

    return layout_spec
