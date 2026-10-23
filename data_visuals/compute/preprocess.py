"""
compute/preprocess.py
=====================
数据预处理 — 绘图前的数据变换操作。

职责:
    - 标准化 / 归一化
    - 百分比转换
    - 排序 / 筛选

不负责:
    - 统计聚合 (属于 aggregation.py)
    - 列类型识别 (属于 data/schema.py)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Union, List


def normalize_minmax(
    series: pd.Series,
    feature_range: tuple = (0, 1),
) -> pd.Series:
    """
    Min-Max 归一化到 [a, b]。

    X' = a + (X - X_min) * (b - a) / (X_max - X_min)
    """
    a, b = feature_range
    min_val, max_val = series.min(), series.max()
    if max_val == min_val:
        return pd.Series(np.full(len(series), a), index=series.index)
    return a + (series - min_val) * (b - a) / (max_val - min_val)


def normalize_zscore(series: pd.Series) -> pd.Series:
    """Z-score 标准化: (X - mean) / std"""
    return (series - series.mean()) / series.std(ddof=0)


def to_percentage(series: pd.Series, decimals: int = 1) -> pd.Series:
    """将 [0, 1] 区间的数值转换为百分比数值 (0.91 → 91.0)"""
    return (series * 100).round(decimals)


def sort_by_column(
    df: pd.DataFrame,
    by: Union[str, List[str]],
    ascending: bool = True,
) -> pd.DataFrame:
    """按指定列排序并返回新 DataFrame"""
    return df.sort_values(by=by, ascending=ascending).reset_index(drop=True)


def normalize_percent_frame(
    df: pd.DataFrame,
    value_columns: List[str],
    *,
    group_keys: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Normalize numeric columns to percentages in [0, 1].

    - With ``group_keys``: normalize each value column within groups.
    - Without ``group_keys``: normalize row-wise across ``value_columns``.
    """
    result = df.copy()
    if not value_columns:
        return result

    if group_keys:
        denominators = result.groupby(group_keys, sort=False)[value_columns].transform("sum")
        denominators = denominators.replace(0, np.nan)
        result[value_columns] = result[value_columns].div(denominators).fillna(0.0)
        return result

    row_sums = result[value_columns].sum(axis=1).replace(0, np.nan)
    result[value_columns] = result[value_columns].div(row_sums, axis=0).fillna(0.0)
    return result


def complete_cartesian_grid(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    value_col: str,
    *,
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Fill missing (x, y) category pairs with a default value."""
    x_vals = sorted(df[x_col].dropna().unique())
    y_vals = sorted(df[y_col].dropna().unique())
    full_idx = pd.MultiIndex.from_product([x_vals, y_vals], names=[x_col, y_col])
    return (
        df.set_index([x_col, y_col])
        .reindex(full_idx, fill_value=fill_value)
        .reset_index()
    )


def normalize_group_sum(
    df: pd.DataFrame,
    *,
    group_col: str,
    value_col: str,
) -> pd.DataFrame:
    """Normalize ``value_col`` by the sum within each ``group_col`` group."""
    result = df.copy()
    denominators = result.groupby(group_col, sort=False)[value_col].transform("sum").replace(0, np.nan)
    result[value_col] = result[value_col].div(denominators).fillna(0.0)
    return result
