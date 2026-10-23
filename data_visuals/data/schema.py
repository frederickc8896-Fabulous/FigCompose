"""
data/schema.py
==============
数据结构描述 — 列类型识别、校验、列信息查询。

职责:
    - 自动推断列类型: categorical / numerical
    - 校验用户指定的列是否存在
    - 输出列信息摘要供下游消费

不负责:
    - 数据读取 (属于 loader.py)
    - 数据变换 (属于 transform.py)
    - 统计计算 (属于 compute/)
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Literal

# 列类型枚举
ColumnType = Literal["categorical", "numerical"]


def infer_column_types(
    df: pd.DataFrame,
    *,
    max_categorical_ratio: float = 0.3,
    max_unique_for_categorical: int = 20,
) -> Dict[str, ColumnType]:
    """
    自动推断每列的类型。

    判断规则 (优先级递减):
        1. 非数值列 → 强制 categorical
        2. 数值列但唯一值 ≤ max_unique_for_categorical 且
           唯一值占比 < max_categorical_ratio → categorical
        3. 其余数值列 → numerical

    Parameters
    ----------
    df : pd.DataFrame
    max_categorical_ratio : float
        唯一值/总行数 超过此比例视为 numerical
    max_unique_for_categorical : int
        超过此数量的唯一值视为 numerical

    Returns
    -------
    dict: {列名: "categorical" | "numerical"}

    Examples
    --------
    >>> infer_column_types(df)
    {'method': 'categorical', 'dataset': 'categorical', 'accuracy': 'numerical'}
    """
    result: Dict[str, ColumnType] = {}
    n_rows = len(df)

    for col in df.columns:
        series = df[col]

        # 非数值类型 → 直接判为 categorical
        if not pd.api.types.is_numeric_dtype(series):
            result[col] = "categorical"
            continue

        # 数值类型但可能是编码的分类变量
        n_unique = series.nunique()
        unique_ratio = n_unique / n_rows if n_rows > 0 else 0

        if n_unique <= max_unique_for_categorical and unique_ratio < max_categorical_ratio:
            result[col] = "categorical"
        else:
            result[col] = "numerical"

    return result


def get_columns(df: pd.DataFrame) -> List[str]:
    """返回所有列名"""
    return list(df.columns)


def get_numerical_columns(
    df: pd.DataFrame,
    *,
    infer: bool = True,
) -> List[str]:
    """
    返回所有数值列名。

    Parameters
    ----------
    df : pd.DataFrame
    infer : bool
        True: 使用 infer_column_types 判断
        False: 使用 pd.select_dtypes(include='number')
    """
    if infer:
        types = infer_column_types(df)
        return [col for col, t in types.items() if t == "numerical"]
    else:
        return list(df.select_dtypes(include=[np.number]).columns)


def get_categorical_columns(
    df: pd.DataFrame,
    *,
    infer: bool = True,
) -> List[str]:
    """
    返回所有分类列名。

    Parameters
    ----------
    df : pd.DataFrame
    infer : bool
        True: 使用 infer_column_types 判断
        False: 使用 pd.select_dtypes(exclude='number')
    """
    if infer:
        types = infer_column_types(df)
        return [col for col, t in types.items() if t == "categorical"]
    else:
        return list(df.select_dtypes(exclude=[np.number]).columns)


def validate_columns(
    df: pd.DataFrame,
    required: Union[str, List[str]],
) -> List[str]:
    """
    校验指定列是否存在于 DataFrame 中，不存在则抛出 KeyError。

    Parameters
    ----------
    df : pd.DataFrame
    required : str | list of str
        需要校验的列名

    Returns
    -------
    list of str — 校验通过的列名列表

    Raises
    ------
    KeyError — 如果某些列不存在
    """
    if isinstance(required, str):
        required = [required]

    existing = list(df.columns)
    missing = [c for c in required if c not in existing]

    if missing:
        raise KeyError(
            f"以下列不存在: {missing}。DataFrame 中的列为: {existing}"
        )

    return required


def schema_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    输出 DataFrame 的结构摘要，类似 R 的 str()。

    Returns
    -------
    pd.DataFrame — 行是列，列是属性:
        dtype, type, non_null, n_unique, unique_ratio, sample_values
    """
    rows = []
    n_total = len(df)

    for col in df.columns:
        series = df[col]
        n_unique = series.nunique()
        sample = series.dropna().head(3).tolist()

        rows.append({
            "column": col,
            "dtype": str(series.dtype),
            "type": infer_column_types(df[col].to_frame())[col],
            "non_null": int(series.notna().sum()),
            "n_unique": n_unique,
            "unique_ratio": round(n_unique / n_total, 4) if n_total > 0 else 0,
            "sample_values": sample,
        })

    return pd.DataFrame(rows)


# ── 数据完整性校验 ────────────────────────────────────────────

def validate_header(df: pd.DataFrame, source_hint: str = "") -> List[str]:
    """校验 DataFrame 的列名是否合法。

    检查:
        1. 列名不能是 pandas 自动生成的整数列名（即 CSV 缺少 header 行）
        2. 列名不能为空字符串
        3. 列名不能包含制表符或换行符
        4. 列名不能重复

    Parameters
    ----------
    df : pd.DataFrame
    source_hint : str
        文件路径或来源描述，用于错误消息

    Returns
    -------
    list[str] — 所有警告消息，空列表表示通过
    """
    warnings_list: List[str] = []
    prefix = f" [{source_hint}]" if source_hint else ""

    cols = list(df.columns)

    # 1) 自动生成的整数列名 → CSV 可能缺少 header
    if cols and all(isinstance(c, int) for c in cols):
        warnings_list.append(
            f"DataFrame{prefix} 的列名全部为整数 ({cols[:3]}{'...' if len(cols)>3 else ''})。"
            f"请检查 CSV 文件第一行是否为列名 (header)。"
        )

    # 2) 空列名
    empty_cols = [c for c in cols if isinstance(c, str) and c.strip() == ""]
    if empty_cols:
        warnings_list.append(
            f"DataFrame{prefix} 有 {len(empty_cols)} 个空列名"
            f" (位置: {[cols.index(c) for c in empty_cols]})。"
        )

    # 3) 含特殊字符的列名
    bad_chars = {"\t", "\n", "\r"}
    bad_cols = [
        c for c in cols
        if isinstance(c, str) and any(ch in c for ch in bad_chars)
    ]
    if bad_cols:
        warnings_list.append(
            f"DataFrame{prefix} 有 {len(bad_cols)} 个列名包含制表符或换行符: {bad_cols}。"
            f"建议运行 df.columns = [c.strip() for c in df.columns]。"
        )

    # 4) 重复列名
    seen: set[str] = set()
    dupes: set[str] = set()
    for c in cols:
        key = str(c).strip().lower()
        if key in seen:
            dupes.add(str(c))
        seen.add(key)
    if dupes:
        warnings_list.append(
            f"DataFrame{prefix} 有重复列名: {sorted(dupes)}。"
            f"重复会导致后续处理结果不确定。"
        )

    return warnings_list


def check_numeric_columns(
    df: pd.DataFrame,
    columns: List[str],
    source_hint: str = "",
) -> List[str]:
    """检查数值列是否为有效数值（非全 NaN / Inf）。

    Parameters
    ----------
    df : pd.DataFrame
    columns : list[str]
        需要检查的列名列表
    source_hint : str

    Returns
    -------
    list[str] — 警告消息列表
    """
    warnings_list: List[str] = []
    prefix = f" [{source_hint}]" if source_hint else ""

    for col in columns:
        if col not in df.columns:
            continue
        series = df[col]
        total = len(series)
        if total == 0:
            warnings_list.append(f"DataFrame{prefix} 列为空: '{col}'")
            continue
        nan_count = int(series.isna().sum())
        if nan_count == total:
            warnings_list.append(
                f"列 '{col}'{prefix} 全部 {total} 行为 NaN，将导致图表空白。"
            )
        elif nan_count > 0:
            warnings_list.append(
                f"列 '{col}'{prefix} 有 {nan_count}/{total} 行 NaN"
                f" ({nan_count / total * 100:.1f}%)。"
            )
    return warnings_list
