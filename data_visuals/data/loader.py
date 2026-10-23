"""
data/loader.py
==============
数据加载层 — 负责将外部文件读入为 pandas DataFrame。

职责:
    - CSV / Excel / JSON 文件读取
    - 自动按扩展名选择解析器
    - 统一返回 pandas DataFrame

不负责:
    - 列类型识别 (属于 schema.py)
    - 数据变换 (属于 transform.py)
    - 统计计算 (属于 compute/)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import pandas as pd


def load_csv(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    delimiter: str = ",",
    **kwargs,
) -> pd.DataFrame:
    """
    读取 CSV 文件为 DataFrame。

    Parameters
    ----------
    path : str | Path
        CSV 文件路径
    encoding : str
        文件编码，默认 utf-8
    delimiter : str
        分隔符，默认逗号
    **kwargs
        透传给 pd.read_csv 的其他参数

    Returns
    -------
    pd.DataFrame
    """
    return pd.read_csv(path, encoding=encoding, delimiter=delimiter, **kwargs)


def load_excel(
    path: Union[str, Path],
    *,
    sheet_name: Union[str, int] = 0,
    **kwargs,
) -> pd.DataFrame:
    """
    读取 Excel 文件（.xlsx / .xls）为 DataFrame。

    Parameters
    ----------
    path : str | Path
    sheet_name : str | int
        sheet 名称或索引，默认第一个 sheet
    **kwargs
        透传给 pd.read_excel

    Returns
    -------
    pd.DataFrame
    """
    return pd.read_excel(path, sheet_name=sheet_name, **kwargs)


def load_json(
    path: Union[str, Path],
    *,
    orient: Optional[str] = None,
    **kwargs,
) -> pd.DataFrame:
    """
    读取 JSON 文件为 DataFrame。

    Parameters
    ----------
    path : str | Path
    orient : str | None
        JSON 结构方向（records / columns / index / values）
        None 时自动推断
    **kwargs
        透传给 pd.read_json

    Returns
    -------
    pd.DataFrame
    """
    return pd.read_json(path, orient=orient, **kwargs)


def load(
    path: Union[str, Path],
    **kwargs,
) -> pd.DataFrame:
    """
    自动按文件扩展名选择合适的解析器。

    支持格式:
        .csv   → load_csv
        .xlsx  → load_excel
        .xls   → load_excel
        .json  → load_json

    Parameters
    ----------
    path : str | Path
        文件路径
    **kwargs
        透传给具体解析器

    Returns
    -------
    pd.DataFrame
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".csv":
        return load_csv(path, **kwargs)
    elif ext in (".xlsx", ".xls"):
        return load_excel(path, **kwargs)
    elif ext == ".json":
        return load_json(path, **kwargs)
    else:
        raise ValueError(
            f"不支持的文件格式 '{ext}'。支持的格式: .csv, .xlsx, .xls, .json"
        )
