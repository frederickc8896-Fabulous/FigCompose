"""
utils/ — 公共工具模块
====================

职责:
    - colors.py — 统一调色板系统
    - fonts.py — 跨平台字体管理（未来）
    - validation.py — 用户输入合法性校验（未来）

不负责:
    - 数据计算 (属于 compute/)
    - 图表定义 (属于 charts/)
    - 渲染 (属于 renderer/)
"""

from data_visuals.utils.colors import (
    Palette,
    get_palette,
    get_palette_flat,
    get_ours_color,
    get_bucket_size,
    list_palettes,
    list_styles,
)

__all__ = [
    "Palette",
    "get_palette",
    "get_palette_flat",
    "get_ours_color",
    "get_bucket_size",
    "list_palettes",
    "list_styles",
]
