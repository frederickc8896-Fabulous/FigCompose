"""
data/labels.py
==============
显示名映射 — 将 CSV 中的原始列值映射为用户友好的显示名。

设计原则:
    - y_columns 筛选优先：仅当前图实际使用的取值才需要映射
    - API 参数 > sidecar YAML > 原始值 fallback
    - 不负责渲染（属于 renderer/），仅做数据语义标注

映射优先级:
    1. 用户通过 labels= 参数显式传入  (API 参数)
    2. <csv_name>.labels.yaml 同目录文件  (sidecar YAML)
    3. 原始值原样显示                     (fallback)

不负责:
    - 渲染颜色/字体 (属于 renderer/ 和 themes/)
    - 列类型识别 (属于 schema.py)
"""

from __future__ import annotations

import os
from typing import Optional, Dict, List, Any
import warnings

import yaml
import pandas as pd


def _parse_value(
    value: Any,
) -> str:
    """确保 label 值是字符串，trim 空白。"""
    return str(value).strip() if value is not None else ""


def load_labels_from_yaml(path: str) -> Dict[str, str]:
    """从 YAML 文件加载显示名映射。

    YAML 格式:
        variable_a: "MSFlow (Passive)"
        variable_b: "RD++ (Passive)"
        model_a: "Our Model"

    Parameters
    ----------
    path : str
        YAML 文件路径

    Returns
    -------
    dict[str, str] — {raw_value: display_name}

    Raises
    ------
    FileNotFoundError — 文件不存在
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"labels 文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return {}

    if not isinstance(raw, dict):
        warnings.warn(f"labels 文件 {path} 内容不是字典格式，已忽略。")
        return {}

    return {_parse_value(k): _parse_value(v) for k, v in raw.items()}


def resolve_labels(
    *,
    user_labels: Optional[Dict[str, str]] = None,
    yaml_path: Optional[str] = None,
    y_columns: Optional[List[str]] = None,
) -> Dict[str, str]:
    """解析显示名映射，按优先级合并。

    Parameters
    ----------
    user_labels : dict | None
        用户通过 API 传入的显式映射（最高优先级）
    yaml_path : str | None
        sidecar YAML 文件路径（中等优先级）。为 None 时跳过。
    y_columns : list[str] | None
        当前图实际使用的 group 取值列表。仅对这些 key 返回映射。
        None 表示不过滤（返回全部）。

    Returns
    -------
    dict[str, str] — {raw_value: display_name}
        仅包含 y_columns 中存在的 key（y_columns 为 None 时返回全部）。
        未提供映射的 key 返回原始值作为 fallback。
    """
    merged: Dict[str, str] = {}

    # 1) YAML base
    if yaml_path is not None:
        try:
            merged.update(load_labels_from_yaml(yaml_path))
        except FileNotFoundError:
            warnings.warn(
                f"labels YAML 文件 '{yaml_path}' 不存在，跳过。"
                f"将使用原始值作为显示名。"
            )

    # 2) User API override (highest priority)
    if user_labels:
        merged.update(user_labels)

    # 3) Filter to y_columns
    if y_columns is not None:
        result: Dict[str, str] = {}
        for key in y_columns:
            display = merged.get(key)
            if display:
                result[key] = display
            else:
                result[key] = key  # fallback: raw value
        return result

    return merged
