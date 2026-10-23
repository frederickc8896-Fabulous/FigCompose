"""
compute/aggregation.py
=======================
聚合计算层 — 只做纯统计聚合，不涉及渲染或布局。

职责:
    - groupby + 聚合算子 (mean, std, var, median, count, min, max, sum)
    - 按照图表类型所需的数据结构输出聚合结果

不负责:
    - 颜色 / 字体 / 样式
    - 布局位置
    - 渲染导出
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Any

# ── 聚合算子注册表 ────────────────────────────────────────────

AGGREGATORS: Dict[str, Any] = {
    "mean":    pd.Series.mean,
    "std":     pd.Series.std,
    "var":     pd.Series.var,
    "median":  pd.Series.median,
    "count":   pd.Series.count,
    "min":     pd.Series.min,
    "max":     pd.Series.max,
    "sum":     pd.Series.sum,
    "sem":     pd.Series.sem,               # 标准误 standard error of mean
    "skew":    pd.Series.skew,
    "kurt":    lambda s: s.kurtosis(),
}

# ── 核心聚合函数 ──────────────────────────────────────────────

def mean_repeated_series(
    df: pd.DataFrame,
    *,
    x_col: str,
    value_cols: List[str],
    group_col: Optional[str] = None,
) -> pd.DataFrame:
    """Resolve repeated line observations to one mean per x and series.

    Original value column names are retained for both renderers, including
    an optional secondary-axis value. Sorting happens before plotting.
    """
    keys = [x_col]
    if group_col and group_col not in keys:
        keys.append(group_col)
    values = [value for value in dict.fromkeys(value_cols) if value not in keys]
    result = df.groupby(keys, sort=False, observed=True, dropna=False)[values].mean().reset_index()
    return result.sort_values(keys, kind="stable").reset_index(drop=True)


def aggregate(
    df: pd.DataFrame,
    group_by: Union[str, List[str]],
    columns: Dict[str, List[str]],
    *,
    sort: bool = True,
) -> pd.DataFrame:
    """
    对 DataFrame 按 group_by 分组，对指定 columns 应用聚合算子。

    Parameters
    ----------
    df : pd.DataFrame
        原始数据（通常来自 data/loader.py）
    group_by : str | list of str
        分组列名，例如 "method" 或 ["method", "dataset"]
    columns : dict
        聚合规格，key=列名, value=聚合算子列表。
        例如: {"accuracy": ["mean", "std"], "loss": ["mean"]}
    sort : bool
        是否按分组键排序，默认 True

    Returns
    -------
    pd.DataFrame
        聚合后的 DataFrame，列名为 MultiIndex 或展平列名

    Examples
    --------
    >>> df = pd.read_csv("mock.csv")
    >>> aggregate(df, group_by="variable_a", columns={"variable_b": ["mean", "std"]})
    """
    if isinstance(group_by, str):
        group_by = [group_by]

    # 构建 agg 字典: {列名: [算子列表]}
    agg_map: Dict[str, List[str]] = {}
    for col, funcs in columns.items():
        if col not in df.columns:
            raise KeyError(f"列 '{col}' 不存在于 DataFrame 中，有效列: {list(df.columns)}")
        agg_map[col] = funcs

    # 按分组聚合
    grouped = df.groupby(group_by, sort=sort)
    result = grouped.agg(agg_map)

    # 展平 MultiIndex 列名: ("accuracy", "mean") → "accuracy_mean"
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = [f"{col[0]}_{col[1]}" for col in result.columns]

    result = result.reset_index()
    return result


def describe(
    df: pd.DataFrame,
    columns: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """
    对标 pd.describe()，但输出更直接、适合下游消费。

    对指定（或全部）数值列输出描述统计表。

    Parameters
    ----------
    df : pd.DataFrame
    columns : str | list of str | None
        要描述的列，None 表示所有数值列

    Returns
    -------
    pd.DataFrame — 行是统计量，列是变量

    Examples
    --------
    >>> describe(df, columns=["accuracy", "loss"])
                  accuracy     loss
        count         7.00     7.00
        mean          0.51     0.53
        std           0.28     0.26
        ...
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()
    elif isinstance(columns, str):
        columns = [columns]

    agg_funcs = ["count", "mean", "std", "var", "median", "min", "max", "sum"]
    result = df[columns].agg(agg_funcs)
    result.index.name = "statistic"
    return result


def correlation_matrix(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    method: str = "pearson",
) -> pd.DataFrame:
    """
    计算指定列之间的相关系数矩阵。

    Parameters
    ----------
    df : pd.DataFrame
    columns : list of str | None
    method : "pearson" | "spearman" | "kendall"

    Returns
    -------
    pd.DataFrame — 相关系数矩阵
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    return df[columns].corr(method=method)
