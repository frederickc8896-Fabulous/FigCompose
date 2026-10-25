"""
utils/colors.py
===============
统一调色板系统 — 分类色板、连续色阶与整图颜色预设。

设计原则:
    - 按需取色: 传入 group 数量，自动选择匹配的色板桶
    - 保留精选搭配的色号与顺序，整图预设直接引用原色表
    - ours_color 是原色表的强调色元信息，不自动绑定方法名称
    - 整图预设协调分类色、连续色阶和辅助标记，渲染层统一消费

不负责:
    - 渲染颜色（属于 renderer/）
    - 字体、排版等非颜色主题设置（属于 themes/*.json）
"""

from __future__ import annotations

from copy import deepcopy
from typing import Optional, Dict, List
from dataclasses import dataclass, field


# ── 数据结构 ──────────────────────────────────────────────────

@dataclass
class Palette:
    """一组完整色板。

    Attributes
    ----------
    colors : list[str]
        完整颜色列表，长度 = 该桶的模型数量
    ours_color : str
        Ours 专属色，必须是 colors 中的一员
    description : str
        人类可读的描述
    """
    colors: List[str]
    ours_color: str
    description: str = ""

    def __post_init__(self):
        if self.ours_color not in self.colors:
            raise ValueError(
                f"ours_color '{self.ours_color}' 不在 colors 列表中"
            )

    @property
    def regular_colors(self) -> List[str]:
        """排除 ours_color 的普通颜色列表。"""
        return [c for c in self.colors if c != self.ours_color]

    def to_flat(self) -> List[str]:
        """返回可直接用于数据系列的扁平颜色列表。"""
        return list(self.colors)


# ═══════════════════════════════════════════════════════════════
# 色板库 — 按模型数量分桶
# ═══════════════════════════════════════════════════════════════

_PALETTES: Dict[int, Dict[str, Palette]] = {

    # ── 2 个模型: Ours vs Baseline ────────────────────────────
    2: {
        "default": Palette(
            colors=["#e74c3c", "#3992ca"],
            ours_color="#e74c3c",
            description="珊瑚红 Ours + 蓝 baseline — 暖→冷",
        ),
        "cool": Palette(
            colors=["#1e96fc", "#0353a4"],
            ours_color="#1e96fc",
            description="亮蓝 Ours + 深蓝 baseline — 冷调",
        ),
        "warm": Palette(
            colors=["#e67e22", "#539ecd"],
            ours_color="#e67e22",
            description="橙色 Ours + 蓝 baseline — 暖→冷",
        ),
    },

    # ── 5 个模型: 典型 benchmark 对比 ─────────────────────────
    5: {
        "default": Palette(
            colors=["#e63946", "#fedfd4", "#94d2bd", "#0077b6", "#1d3557"],
            ours_color="#e63946",
            description="红 Ours → 浅青 → 深蓝 — 暖→冷渐变",
        ),
        "cool": Palette(
            colors=["#ff6b35", "#f7c59f", "#efefd0", "#1976d2", "#0d47a1"],
            ours_color="#ff6b35",
            description="橙 Ours → 暖米 → 深蓝 — 暖→冷渐变",
        ),
        "warm": Palette(
            colors=["#e76f51", "#f4a261", "#e9c46a", "#2a9d8f", "#264653"],
            ours_color="#e76f51",
            description="珊瑚 Ours → 金 → 绿 — 暖→冷渐变",
        ),
    },

    # ── 7 个模型: 较多方法对比 ─────────────────────────────────
    7: {
        "default": Palette(
            colors=["#d81159", "#e05400", "#fd8021", "#ffd373",
                    "#00a6fb", "#4361ee", "#2c497f"],
            ours_color="#d81159",
            description="亮红 Ours → 橙 → 天蓝 → 深蓝 — 暖→冷渐变",
        ),
        "cool": Palette(
            colors=["#fb8500", "#fcab64", "#a0ced9", "#6db2c4",
                    "#489fb5", "#37718e", "#457b9d"],
            ours_color="#fb8500",
            description="橙 Ours → 暖肤 → 蓝绿渐变 — 暖→冷渐变",
        ),
        "warm": Palette(
            colors=["#eb5e28", "#f9a03f", "#f6b049", "#f3c053",
                    "#a1c349", "#94b33d", "#6a8532"],
            ours_color="#eb5e28",
            description="深橙 Ours → 金 → 草绿 — 暖→冷渐变",
        ),
    },

    # Explicit eight-colour preset; legacy automatic lookup still uses ten.
    8: {
        "rose-blue": Palette(
            colors=["#FCE7EC", "#E8B3C6", "#D79AB7", "#D8D4EA",
                    "#D4E4F2", "#9CC6E6", "#5B7FAF", "#0F2855"],
            ours_color="#D79AB7",
            description="柔粉 → 薰衣草 → 雾蓝 → 深海蓝；主色 #D79AB7",
        ),
    },

    # ── 8+ 个模型: 大型对比 (10 色) ───────────────────────────
    10: {
        "default": Palette(
            colors=["#f94144", "#f3722c", "#f8961e", "#f9844a", "#f9c74f",
                    "#90be6d", "#43aa8b", "#4d908e", "#577590", "#277da1"],
            ours_color="#f94144",
            description="红 Ours → 橙/金 → 绿/青/蓝 — 暖→冷全色谱",
        ),
        "muted": Palette(
            colors=["#65010c", "#cb1b16", "#ef3c2d", "#f26a4f", "#f29479",
                    "#fedfd4", "#9dcee2", "#4091c9", "#1368aa", "#033270"],
            ours_color="#65010c",
            description="深红 Ours → 暖肤 → 天蓝 → 深蓝 — 暖→冷渐变",
        ),
        "vibrant": Palette(
            colors=["#fb9017", "#fb8500", "#fd9e02", "#ffb703", "#023047",
                    "#126782", "#219ebc", "#58b4d1", "#73bfdc", "#8ecae6"],
            ours_color="#fb9017",
            description="亮橙 Ours → 金 → 深蓝 → 天蓝 — 暖→冷鲜艳",
        ),
    },
}

# Whole-figure presets reference only the original selected combinations.
# Supporting marks use neutrals, not an additional categorical palette.
COLOR_PRESETS: Dict[str, Dict[str, str]] = {}
_AUXILIARY_COLORS = {
    "reference_line": "#888888",
    "mean_line": "#555555",
    "error_bar": "#444444",
}

# Fixed, original combinations reference the existing tables rather than
# storing another copy of the selected hex colours. A capacity is explicit:
# smaller domains use a prefix; larger ones must select another combination.
_CURATED_SCHEMES = {
    2: {"default": "blues", "cool": "blues", "warm": "amber"},
    5: {"default": "blues", "cool": "blues", "warm": "amber"},
    7: {"default": "blues", "cool": "blues", "warm": "amber"},
    8: {"rose-blue": "blues"},
    10: {"default": "blues", "muted": "blues", "vibrant": "blues"},
}
for _size, _schemes in _CURATED_SCHEMES.items():
    for _style, _scheme in _schemes.items():
        COLOR_PRESETS[f"curated-{_size}-{_style}"] = {
            "description": _PALETTES[_size][_style].description,
            "palette_bucket": str(_size),
            "palette_style": _style,
            "sequential": _scheme,
            "primary_index": str(_PALETTES[_size][_style].colors.index(
                _PALETTES[_size][_style].ours_color)),
        }

# 风格名 → 显示名
_STYLE_LABELS: Dict[str, str] = {
    "default": "默认",
    "cool": "冷调",
    "warm": "暖调",
    "muted": "柔和",
    "vibrant": "鲜艳",
}

# Only buckets with a default participate in legacy automatic selection.
# Explicit curated presets may have other capacities without changing it.
_BUCKET_SIZES = sorted(size for size, styles in _PALETTES.items() if "default" in styles)


# ═══════════════════════════════════════════════════════════════
# 连续色板注册 — heatmap 等 sequential encoding 使用
# ═══════════════════════════════════════════════════════════════

SEQUENTIAL_SCHEMES: Dict[str, List[str]] = {
    # 暖色更显著（低值 → 蓝色背景，高值 → 暗红突出；light-first）
    "warm-cool": [
        "#6090c1", "#acd2e5", "#fef9b7", "#fee395", "#f2724d", "#d7312d",
    ],
    "coastal": [
        "#1d4e89", "#00b2ca", "#7dcfb6", "#fbd1a2", "#f79256",
    ],
    # 深蓝更显著（低值 → 浅蓝，高值 → 深蓝）
    "blues": [
        "#e3f2fd", "#bbdefb", "#90caf9", "#64b5f6", "#42a5f5",
        "#2196f3", "#1e88e5", "#1976d2", "#1565c0", "#0d47a1",
    ],
    # 橙色更显著（低值 → 黄，高值 → 橙）
    "amber": [
        "#ffea00", "#ffdd00", "#ffd000", "#ffc300", "#ffb700",
        "#ffaa00", "#ffa200", "#ff9500", "#ff8800", "#ff7b00",
    ],
    # 红色更显著（低值 → 青蓝，高值 → 柔红）
    "rose": [
        "#4281a4", "#9cafb7", "#ead2ac", "#e6b89c", "#fe938c",
    ],
}
"""自定义连续色阶注册表。

key → 颜色列表（渲染器生成连续颜色映射）。
用户可通过 chart_opts={'color_scheme': 'warm-cool'} 使用。
列表形式也支持直接内联传入: chart_opts={'color_scheme': ['#f00', '#0f0', '#00f']}
"""


# ── 公共 API ──────────────────────────────────────────────────

def get_color_preset(name: str) -> Dict[str, str]:
    """Return a color system, including original fixed curated combinations.

    Presets affect colours only; they can accompany any typography/layout
    theme. Mutating the returned dictionary never changes the registry.
    """
    if not isinstance(name, str) or name not in COLOR_PRESETS:
        raise ValueError(
            f"未知颜色预设 {name!r}。可用: {', '.join(list_color_presets())}"
        )
    preset = deepcopy(COLOR_PRESETS[name])
    if "palette_bucket" in preset:
        source = get_palette(int(preset["palette_bucket"]), name)
        preset = {**_AUXILIARY_COLORS, **preset}
        preset["trend_line"] = source.colors[int(preset.get("primary_index", "0"))]
        preset["y2_axis"] = source.colors[-1]
    return preset


def list_color_presets() -> List[str]:
    """List the available whole-figure colour presets in display order."""
    return list(COLOR_PRESETS)


def _curated_palette(n_groups: int, bucket: int, style: str, name: str) -> Palette:
    """Use one original combination without switching buckets or extending."""
    source = _PALETTES[bucket][style]
    if n_groups > len(source.colors):
        raise ValueError(
            f"颜色预设 {name!r} 最多支持 {len(source.colors)} 个类别，"
            f"当前完整类别域有 {n_groups} 个。请选择更大容量的 curated 预设，"
            "或减少类别数量。"
        )
    return source


def get_palette(
    n_groups: int,
    style: str = "default",
) -> Palette:
    """按模型组数获取匹配的色板。

    自动向上查找最近的色板桶:
        n_groups ≤ 2  →  2-group bucket
        n_groups ≤ 5  →  5-group bucket
        n_groups ≤ 7  →  7-group bucket
        n_groups > 7  →  10-group bucket

    Parameters
    ----------
    n_groups : int
        数据中的 group 唯一值数量
    style : str
        色板风格: "default" / "cool" / "warm" / "muted" / "vibrant"，
        或固定原始搭配，例如 "curated-5-default"。
        不同桶支持的风格不同，详见 _PALETTES

    Returns
    -------
    Palette — 包含 colors / ours_color / description

    Raises
    ------
    ValueError — n_groups ≤ 0 或 style 不存在

    Examples
    --------
    >>> p = get_palette(5, "default")
    >>> p.colors
    ['#e63946', '#fedfd4', '#94d2bd', '#0077b6', '#1d3557']
    >>> p.ours_color
    '#e63946'
    >>> p.regular_colors
    ['#fedfd4', '#94d2bd', '#0077b6', '#1d3557']
    """
    if n_groups <= 0:
        raise ValueError(f"n_groups 必须 > 0，当前值: {n_groups}")

    fixed = COLOR_PRESETS.get(style, {})
    if "palette_bucket" in fixed:
        return _curated_palette(n_groups, int(fixed["palette_bucket"]), fixed["palette_style"], style)

    # 向上查找最近的桶
    for bucket in _BUCKET_SIZES:
        if n_groups <= bucket:
            n_bucket = bucket
            break
    else:
        n_bucket = _BUCKET_SIZES[-1]  # 超过最大桶 → 用 10

    bucket_palettes = _PALETTES.get(n_bucket, {})
    if style not in bucket_palettes:
        available = sorted(bucket_palettes.keys())
        raise ValueError(
            f"色板桶 {n_bucket} 没有风格 '{style}'。可用: {available}"
        )

    return bucket_palettes[style]


def get_palette_flat(
    n_groups: int,
    style: str = "default",
) -> List[str]:
    """get_palette() 的快捷版本，直接返回扁平颜色列表。

    用于分类映射和系列样式等需要纯列表的场景。
    """
    colors = get_palette(n_groups, style).to_flat()
    if n_groups > len(colors):
        # Preserve curated colours; extend deterministically instead of silently
        # assigning the same colour to unrelated categories above ten groups.
        candidates = _extension_candidates()
        rgb = [tuple(int(c[j:j + 2], 16) / 255 for j in (1, 3, 5)) for c in colors]
        while len(colors) < n_groups:
            if not candidates:
                raise ValueError("At most 138 distinct category colours are supported")
            choice = max(candidates, key=lambda c: min(
                sum((a - b) ** 2 for a, b in zip(c, old)) for old in rgb))
            candidates.remove(choice)
            rgb.append(choice)
            colors.append("#" + "".join(f"{round(channel * 255):02x}" for channel in choice))
    return colors


def _extension_candidates() -> List[tuple]:
    """Candidates for the legacy low-level palette lookup above ten groups.

    There are 128 candidates, preserving the existing 138-colour limit.
    Distinct RGB values alone do not guarantee distinguishable series.
    """
    from colorsys import hls_to_rgb

    return [hls_to_rgb(i / 64, lightness, 0.65)
            for lightness in (0.42, 0.62) for i in range(64)]


def list_palettes() -> Dict[int, Dict[str, str]]:
    """列出所有可用的色板桶及其风格。

    Returns
    -------
    dict: {bucket_size: {style_name: description}}
    """
    result: Dict[int, Dict[str, str]] = {}
    for bucket, styles in _PALETTES.items():
        result[bucket] = {
            name: p.description for name, p in styles.items()
        }
    return result


def list_styles(n_groups: int) -> List[str]:
    """列出指定组数桶下可用的风格名。"""
    bucket = None
    for b in _BUCKET_SIZES:
        if n_groups <= b:
            bucket = b
            break
    if bucket is None:
        bucket = _BUCKET_SIZES[-1]
    return sorted(_PALETTES.get(bucket, {}).keys())


def get_ours_color(
    n_groups: int,
    style: str = "default",
) -> str:
    """只取 ours_color，快捷方法。"""
    return get_palette(n_groups, style).ours_color


def get_bucket_size(n_groups: int) -> int:
    """返回 n_groups 对应的色板桶大小。"""
    for bucket in _BUCKET_SIZES:
        if n_groups <= bucket:
            return bucket
    return _BUCKET_SIZES[-1]
