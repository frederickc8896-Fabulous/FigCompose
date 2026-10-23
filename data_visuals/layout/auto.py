"""
layout/auto.py
==============
内容驱动的全自动 Layout — 给定 subfigure 列表 + 可选数据源，
自动推断最优网格、宽高比、共享轴配置。

核心思想:
    用户声明"我要画这些图"，系统自动决定"怎么排列最合理"。
    就像 flex-wrap / CSS Grid auto-fill，但针对数据可视化场景优化。

算法流程:
    subfigures[]
        │
        ▼
    1. 计数 n + 检测共享轴
        │
        ▼
    2. 按图表类型分配 cell 宽高比
        bar/line → 4:3, box → 3:4, scatter → 1:1, heatmap → 数据驱动
        │
        ▼
    3. 因子分解 n → (rows, cols) 候选
        选 overall_aspect 最接近目标 (默认 4:3 = 1.333) 的候选
        │
        ▼
    4. 计算 canvas aspect = overall_aspect
        │
        ▼
    5. 调用 build_layout(layout=weights, aspect=computed)
        │
        ▼
    6. 应用 detect_shared_axes → LayoutSpec
"""

from __future__ import annotations

import math
from typing import Optional, Dict, List, Any, Tuple

import pandas as pd

from data_visuals.layout.manager import build_layout, print_layout
from data_visuals.layout.shared import detect_shared_axes

# ── 图表类型 → 默认 cell 宽高比 ──────────────────────────────

CHART_CELL_RATIO: Dict[str, float] = {
    "bar":     4.0 / 3.0,    # 1.333  偏宽，适合柱状图
    "line":    4.0 / 3.0,    # 1.333
    "box":     3.0 / 4.0,    # 0.75   偏窄，适合箱线图
    "scatter": 1.0,          # 1.0    方形
    "heatmap": 1.0,          # 1.0    (实际由数据维度决定，这里先守恒)
}

# 宽高比目标偏好 — 总画布越接近这个越优先
TARGET_CANVAS_RATIO = 4.0 / 3.0   # 经典 4:3


# ── 网格因子分解 ──────────────────────────────────────────────

def _factorize(n: int) -> List[Tuple[int, int]]:
    """
    将 n 分解为 (rows, cols) 候选，rows × cols ≥ n。

    Preference: 近似正方形优先 → 扁平优先。

    Examples
    --------
    >>> _factorize(7)
    [(3, 3), (2, 4), (4, 2), (1, 7), (7, 1)]
    """
    candidates: List[Tuple[int, int]] = []
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        candidates.append((rows, cols))

    # 去重 + 按优选排序: 先用完程度 (少空格优先), 再按接近正方形
    seen = set()
    unique = []
    for r, c in candidates:
        if (r, c) not in seen:
            seen.add((r, c))
            unique.append((r, c))

    # 排序: (空格数, |r-c|, c) — 空格少优先，正方形优先，宽行优先
    unique.sort(key=lambda rc: (rc[0] * rc[1] - n, abs(rc[0] - rc[1]), -rc[1]))
    return unique


def _score_grid(
    rows: int,
    cols: int,
    cell_ratio: float,
    target_ratio: float = TARGET_CANVAS_RATIO,
) -> float:
    """
    评估 (rows, cols) 的总画布宽高比与目标的接近度。

    overall = (cols × cell_w_ratio) / (rows × cell_h_ratio)
            = (cols / rows) × cell_ratio

    分数 = abs(overall - target)，越小越好。
    """
    overall = (cols / rows) * cell_ratio
    return abs(overall - target_ratio)


def _pick_best_grid(
    n: int,
    cell_ratio: float,
    target_ratio: float = TARGET_CANVAS_RATIO,
) -> Tuple[int, int]:
    """
    为 n 个 cell 选出最佳 (rows, cols)。

    Returns
    -------
    (rows, cols)
    """
    candidates = _factorize(n)
    best = min(candidates, key=lambda rc: _score_grid(rc[0], rc[1], cell_ratio, target_ratio))
    return best


# ── 主 API ───────────────────────────────────────────────────

def auto_layout(
    subfigures: List[Dict[str, Any]],
    *,
    data: Optional[pd.DataFrame] = None,
    base: str = "medium",
    cell_base: Optional[str] = None,
    title: Optional[str] = None,
    target_ratio: float = TARGET_CANVAS_RATIO,
    legend_max_entries: Optional[int] = None,
    **layout_kwargs,
) -> Dict[str, Any]:
    """
    全自动 Layout — 从 subfigure 列表自动推导最优网格、宽高比、共享轴。

    Parameters
    ----------
    subfigures : list[dict]
        每个 dict 描述一个子图:
            {
                "chart": "bar" | "line" | "box" | "scatter" | "heatmap",
                "x": "column_name",
                "y": "column_name",
                "group": "column_name"  (可选)
            }

    data : pd.DataFrame | None
        原始数据。传入后可自动:
            - 推断每个 x 轴有多少个分类值 (用于微调 cell 宽高比)
            - 推断 legend 条目数 (若使用 group)
            - 推断 category name 最大长度 (用于 margin 预算)

    base : str
        基准尺寸: "small" | "medium" | "large" | "poster"

    title : str | None
        全局标题

    target_ratio : float
        期望的总画布宽高比，默认 4:3 = 1.333

    legend_max_entries : int | None
        legend 最大条目数。None 时自动从 data / group 推断

    **layout_kwargs
        透传给 build_layout 的其他参数

    Returns
    -------
    dict — LayoutSpec，与 build_layout 输出格式完全一致

    Examples
    --------
    >>> import pandas as pd
    >>> from data_visuals.layout import auto_layout
    >>>
    >>> df = pd.read_csv("mock_copy.csv")
    >>>
    >>> # 7 个 bar chart，x=model_name, y=各 variable
    >>> subfigures = [
    ...     {"chart": "bar", "x": "model_name", "y": f"variable_{c}"}
    ...     for c in "abcdefg"
    ... ]
    >>>
    >>> spec = auto_layout(subfigures, data=df, title="Model Comparison")
    """
    n = len(subfigures)
    if n == 0:
        raise ValueError("subfigures 不能为空")

    # ── 1. 推断每个子图的 cell 宽高比 ──
    chart_ratios = []
    chart_types_set = set()
    for sf in subfigures:
        ct = sf.get("chart", "bar")
        chart_types_set.add(ct)
        ratio = CHART_CELL_RATIO.get(ct, 4.0 / 3.0)

        # 如果传了 data 且是 bar/line，根据 x 轴分类数微调
        if data is not None and ct in ("bar", "line"):
            x_col = sf.get("x", "")
            if x_col and x_col in data.columns:
                n_cats = data[x_col].nunique()
                # 类别多 → 需要更宽的 cell
                if n_cats > 10:
                    ratio *= 1.3   # 宽 30%
                elif n_cats > 5:
                    ratio *= 1.15  # 宽 15%

        chart_ratios.append(ratio)

    # 使用平均或众数的 cell ratio
    cell_ratio = sum(chart_ratios) / len(chart_ratios) if chart_ratios else 4.0 / 3.0

    # ── 2. 选最佳 grid ──
    rows, cols = _pick_best_grid(n, cell_ratio, target_ratio)
    total_cells = rows * cols

    # ── 3. 计算 canvas aspect ──
    overall_aspect = (cols / rows) * cell_ratio
    # 限制在合理范围 [0.5, 3.0]
    overall_aspect = max(0.5, min(overall_aspect, 3.0))

    # ── 4. infer legend max entries ──
    if legend_max_entries is None and data is not None:
        # 尝试从 group 字段推断
        for sf in subfigures:
            group_col = sf.get("group")
            if group_col and group_col in data.columns:
                legend_max_entries = data[group_col].nunique()
                break
    if legend_max_entries is None:
        legend_max_entries = 0

    # ── 5. 构建 layout weights ──
    # 如果 n 不是 total_cells 的整数倍，最后一行可能不满
    layout_weights = []
    sf_idx = 0
    for r in range(rows):
        remaining = cols
        row_weights = []
        while sf_idx < n and remaining > 0:
            ct = subfigures[sf_idx].get("chart", "bar")
            r_cell = CHART_CELL_RATIO.get(ct, 4.0 / 3.0)
            # 归一化：按 cell ratio 分配列宽
            # 简化：所有 cell 等宽（weight=1），除非以后需要按 chart type 调
            col_weight = 1
            remaining -= col_weight
            row_weights.append(col_weight)
            sf_idx += 1

        # 如果一行空白（n < rows*cols，最后一行无内容），不添加
        if row_weights:
            layout_weights.append(row_weights)

    # ── 6. 调 build_layout ──
    spec = build_layout(
        layout=layout_weights,
        aspect=overall_aspect,
        base=base,
        cell_base=cell_base,
        title=title,
        legend_max_entries=legend_max_entries,
        **layout_kwargs,
    )

    # ── 7. 共享轴检测 ──
    # 构建 chart_axes 列表（长度 = total_cells，空的放 None）
    chart_axes: List[Optional[Dict[str, Optional[str]]]] = []
    for i in range(total_cells):
        if i < n:
            sf = subfigures[i]
            chart_axes.append({"x": sf.get("x"), "y": sf.get("y")})
        else:
            chart_axes.append(None)

    spec = detect_shared_axes(spec, chart_axes)

    # 附加元信息
    spec["auto"] = {
        "n_subfigures": n,
        "total_cells": total_cells,
        "rows": rows,
        "cols": cols,
        "cell_ratio": round(cell_ratio, 3),
        "overall_aspect": round(overall_aspect, 3),
        "chart_types": sorted(chart_types_set),
    }

    return spec
