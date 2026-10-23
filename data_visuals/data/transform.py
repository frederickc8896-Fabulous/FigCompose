"""
data/transform.py
=================
数据预处理变换 — 绘图前的数据结构调整操作。

职责:
    - 透视表 (pivot / melt)
    - 行列筛选 (filter / select)
    - 缺失值处理 (drop_na / fill_na)
    - 重命名 / 排序

与 compute/ 的边界:
    transform 做的是结构变换，不做统计聚合 (mean/std 等)。
    例如: wide→long 是 transform，groupby+mean 是 compute。

不负责:
    - 统计聚合 (属于 compute/)
    - 列类型识别 (属于 schema.py)
    - 文件读取 (属于 loader.py)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Any, Callable


# ── 结构变换 ──────────────────────────────────────────────────

def pivot(
    df: pd.DataFrame,
    *,
    index: Union[str, List[str]],
    columns: str,
    values: Union[str, List[str]],
    aggfunc: str = "first",
) -> pd.DataFrame:
    """
    长表 → 宽表 (pivot / pivot_table)。

    内部使用 pivot_table 以支持重复 index-column 组合。

    Parameters
    ----------
    df : pd.DataFrame
    index : str | list of str
        保留为行索引的列
    columns : str
        展开为列头的列
    values : str | list of str
        填充值的列
    aggfunc : str
        重复值聚合方式: "first" / "mean" / "sum" / "last" 等
        默认 "first"（取第一个出现的值）

    Returns
    -------
    pd.DataFrame

    Examples
    --------
    >>> # 输入 (long format):
    >>> # method  metric  value
    >>> # A       acc     0.81
    >>> # A       f1      0.75
    >>> # B       acc     0.84
    >>> pivot(df, index="method", columns="metric", values="value")
    >>> # 输出 (wide format):
    >>> # method  acc    f1
    >>> # A       0.81   0.75
    >>> # B       0.84   0.87
    """
    return (
        df.pivot_table(
            index=index, columns=columns, values=values, aggfunc=aggfunc
        )
        .reset_index()
    )


def melt(
    df: pd.DataFrame,
    *,
    id_vars: Union[str, List[str]],
    value_vars: Optional[Union[str, List[str]]] = None,
    var_name: str = "variable",
    value_name: str = "value",
) -> pd.DataFrame:
    """
    宽表 → 长表 (melt)。

    Parameters
    ----------
    df : pd.DataFrame
    id_vars : str | list of str
        保留为标识列的列
    value_vars : str | list of str | None
        要熔化的列，None 表示除 id_vars 外的所有列
    var_name : str
        熔化后变量名列的名称
    value_name : str
        熔化后值列的名称

    Returns
    -------
    pd.DataFrame

    Examples
    --------
    >>> melt(df, id_vars="method", value_vars=["acc", "f1"])
    """
    return df.melt(
        id_vars=id_vars if isinstance(id_vars, list) else [id_vars],
        value_vars=value_vars,
        var_name=var_name,
        value_name=value_name,
    )


# ── 行列筛选 ──────────────────────────────────────────────────

def select_columns(
    df: pd.DataFrame,
    columns: Union[str, List[str]],
) -> pd.DataFrame:
    """只保留指定列，返回新 DataFrame"""
    if isinstance(columns, str):
        columns = [columns]
    return df[columns].copy()


def drop_columns(
    df: pd.DataFrame,
    columns: Union[str, List[str]],
) -> pd.DataFrame:
    """删除指定列，返回新 DataFrame"""
    if isinstance(columns, str):
        columns = [columns]
    return df.drop(columns=columns)


def filter_rows(
    df: pd.DataFrame,
    query: Optional[str] = None,
    *,
    mask: Optional[pd.Series] = None,
    fn: Optional[Callable[[pd.DataFrame], pd.Series]] = None,
) -> pd.DataFrame:
    """
    按条件筛选行。

    三种使用方式（互斥，按优先级）:
        1. query: 字符串表达式，如 "accuracy > 0.8"
        2. mask: 布尔 Series
        3. fn: 接受 DataFrame 返回布尔 Series 的函数

    Parameters
    ----------
    df : pd.DataFrame
    query : str | None
        pandas query 表达式
    mask : pd.Series | None
        布尔掩码
    fn : callable | None
        筛选函数

    Returns
    -------
    pd.DataFrame

    Examples
    --------
    >>> filter_rows(df, query="accuracy > 0.8 and method == 'Ours'")
    >>> filter_rows(df, mask=df["accuracy"] > 0.8)
    >>> filter_rows(df, fn=lambda d: d["method"].isin(["A", "B"]))
    """
    if query is not None:
        return df.query(query).reset_index(drop=True)
    elif mask is not None:
        return df[mask].reset_index(drop=True)
    elif fn is not None:
        return df[fn(df)].reset_index(drop=True)
    else:
        raise ValueError("必须提供 query / mask / fn 之一作为筛选条件")


# ── 缺失值处理 ────────────────────────────────────────────────

def drop_na(
    df: pd.DataFrame,
    *,
    columns: Optional[Union[str, List[str]]] = None,
    how: str = "any",
) -> pd.DataFrame:
    """
    删除含有缺失值的行。

    Parameters
    ----------
    df : pd.DataFrame
    columns : str | list of str | None
        限定检查列，None 表示所有列
    how : "any" | "all"
        any: 任一列缺失即删除; all: 全部缺失才删除
    """
    subset = None if columns is None else ([columns] if isinstance(columns, str) else columns)
    return df.dropna(subset=subset, how=how).reset_index(drop=True)


def fill_na(
    df: pd.DataFrame,
    value: Any = 0,
    *,
    columns: Optional[Union[str, List[str]]] = None,
    method: Optional[str] = None,
) -> pd.DataFrame:
    """
    填充缺失值。

    Parameters
    ----------
    df : pd.DataFrame
    value : any
        填充值（method 不为 None 时无效）
    columns : str | list of str | None
        限定填充列
    method : "mean" | "median" | "ffill" | "bfill" | None
        填充策略
    """
    result = df.copy()
    if columns is None:
        columns = list(df.columns)
    elif isinstance(columns, str):
        columns = [columns]

    for col in columns:
        if method == "mean":
            result[col] = result[col].fillna(result[col].mean())
        elif method == "median":
            result[col] = result[col].fillna(result[col].median())
        elif method in ("ffill", "bfill"):
            result[col] = result[col].fillna(method=method)
        else:
            result[col] = result[col].fillna(value)

    return result


# ── 重命名 / 排序 ────────────────────────────────────────────

def rename_columns(
    df: pd.DataFrame,
    mapping: Dict[str, str],
) -> pd.DataFrame:
    """按映射字典重命名列"""
    return df.rename(columns=mapping)


def sort_values(
    df: pd.DataFrame,
    by: Union[str, List[str]],
    *,
    ascending: bool = True,
) -> pd.DataFrame:
    """按指定列排序"""
    return df.sort_values(by=by, ascending=ascending).reset_index(drop=True)


# ── 类型转换 ──────────────────────────────────────────────────

def cast_column(
    df: pd.DataFrame,
    dtype_map: Dict[str, Any],
) -> pd.DataFrame:
    """
    将指定列转换为目标类型。

    Examples
    --------
    >>> cast_column(df, {"method": "category", "year": int})
    """
    result = df.copy()
    for col, dtype in dtype_map.items():
        result[col] = result[col].astype(dtype)
    return result
