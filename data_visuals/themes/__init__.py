"""
themes/ — 论文风格库
====================

职责:
    - 定义字体/字号/色板/网格/legend 位置等所有视觉属性
    - 以 JSON 文件存储，用户可创建新主题 (neurips.json, acl.json, ...)
    - load_theme(name) 返回规范化 dict, 供 core → renderer 消费

不负责:
    - 数据计算 (属于 compute/)
    - 图表类型定义 (属于 charts/)
    - 渲染 (属于 renderer/)
    - 配色方案运行时生成 (属于 utils/colors.py, 未来)

设计原则（来自架构文档）:
    换一次论文 (CVPR → ACL → IEEE) 只改 theme="acl",
    renderer 从 theme dict 中读取所有视觉参数，不自产一行颜色。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


# ── 内置主题注册 ─────────────────────────────────────────────

_BUILTIN_THEMES: Dict[str, Dict[str, Any]] = {}

THEME_DIR = Path(__file__).parent


def load_theme(name: str) -> Dict[str, Any]:
    """加载指定名称的主题，返回规范化 dict。

    Parameters
    ----------
    name : str
        主题名，如 "general" / "acl" / "neurips"

    Returns
    -------
    dict — 完整主题配置

    Raises
    ------
    FileNotFoundError — 主题文件不存在
    """
    # 检查缓存
    if name in _BUILTIN_THEMES:
        return _BUILTIN_THEMES[name]

    path = THEME_DIR / f"{name}.json"
    if not path.exists():
        available = [
            f.stem for f in THEME_DIR.glob("*.json") if f.stem != "__init__"
        ]
        raise FileNotFoundError(
            f"主题 '{name}' 不存在。"
            f"可用主题: {available}"
        )

    with open(path, "r", encoding="utf-8") as f:
        theme = json.load(f)

    _BUILTIN_THEMES[name] = theme
    return theme


def list_themes() -> list[str]:
    """列出所有可用的主题名称。"""
    themes = []
    for f in THEME_DIR.glob("*.json"):
        name = f.stem
        # 快速验证是合法的主题文件
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "name" in data:
                themes.append(name)
        except (json.JSONDecodeError, KeyError):
            pass
    return sorted(themes)


def get_default_theme() -> str:
    """返回默认主题名称。"""
    available = list_themes()
    if "general" in available:
        return "general"
    return available[0] if available else "general"


# ── 便捷访问函数 ──────────────────────────────────────────────

def get_font_family(theme: Dict[str, Any]) -> str:
    """提取字体族名。"""
    return theme.get("font", {}).get("family", "Times New Roman, serif")


def get_color_palette(theme: Dict[str, Any], n_groups: int = 0) -> list[str]:
    """Resolve grouped and ungrouped charts through the same theme palette.

    ``n_groups=0`` requests the master palette. Older custom themes
    without ``palette_style`` retain their explicit ``categorical`` colours.
    Theme colour values override defaults supplied by a named ``preset``.
    """
    from data_visuals.utils.colors import get_color_preset, get_palette_flat, get_palette

    color = theme.get("color", {})
    if color.get("preset"):
        color = {**get_color_preset(color["preset"]), **color}
    if "palette_bucket" in color:
        bucket = int(color["palette_bucket"])
        style = color.get("palette_style", "default")
        name = f"curated-{bucket}-{style}"
        return get_palette(n_groups or bucket, name).to_flat()
    style = color.get("palette_style")
    if style:
        return get_palette_flat(n_groups or 10, style)
    categorical = color.get("categorical")
    if categorical:
        return list(categorical)
    return get_palette_flat(n_groups or 10)


def get_background(theme: Dict[str, Any]) -> str:
    return theme.get("color", {}).get("background", "#ffffff")
