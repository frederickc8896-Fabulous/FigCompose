"""
core/config.py
==============
全局默认配置 — 为 FigureSpec 和 Figure 提供可全局覆盖的默认值。

设计原则:
    - 只进行字段校验与归一化，不执行数据计算或 I/O
    - 用户可通过 Figure(config=...) 局部覆盖

参考: 论文视觉规范 (Helvetica, minimal axis, 2pt line, no grid)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

from data_visuals.core.canvas import DEFAULT_CANVAS, normalize_canvas
from data_visuals.core.facets import normalize_facets
from data_visuals.core.legend import normalize_legend


_UNSET = object()
_LEGACY_SIZE_DEFAULTS = {"aspect": "16:10", "base": "large", "cell_base": None}


@dataclass
class FigureConfig:
    """Figure 级别的全局默认配置。

    所有字段可被用户在 Figure() 构造时按需覆盖。
    """

    # ── 画布 ──
    aspect: str = _UNSET            # 旧尺寸路径默认宽高比：16:10
    base: str = _UNSET              # 旧尺寸档位默认 large
    cell_base: Optional[str] = _UNSET  # cell-first 档位（优先级高于 base）
    dpi: int = 150                  # 输出 DPI

    # ── 主题 ──
    theme: str = "general"          # 内置主题: general / modern
    palette: Optional[str] = None   # None = theme default; curated combinations

    # ── 全局标题 ──
    title: Optional[str] = None
    # ── Legend ──
    legend_max_entries: int = 0     # 0 = 自动推断
    legend_position: str = "top-right"
    legend: Dict[str, Any] = field(default_factory=dict)

    # ── 全局样式覆盖 ──
    font_family: Optional[str] = None  # None = use theme font
    background: str = "#ffffff"
    category_colors: Dict[str, Dict[str, str]] = field(default_factory=dict)
    facets: Dict[str, Any] = field(default_factory=dict)

    # ── 高级 ──
    auto_margins: bool = True
    autosize: bool = True           # layout 自动推导最优网格
    canvas: Optional[Dict[str, Any]] = _UNSET  # 默认 180 mm 栏宽，自动高度
    _explicit_size_fields: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.facets = normalize_facets(self.facets)
        self.legend = normalize_legend(self.legend)
        explicit = set()
        for key, default in _LEGACY_SIZE_DEFAULTS.items():
            value = getattr(self, key)
            if value is _UNSET:
                setattr(self, key, default)
            elif value is not None:
                explicit.add(key)
        if self.canvas is _UNSET:
            self.canvas = dict(DEFAULT_CANVAS)
        elif self.canvas is not None:
            explicit.add("canvas")
            self.canvas = normalize_canvas(self.canvas)["request"]
        self._explicit_size_fields = frozenset(explicit)
        if "canvas" in explicit and explicit - {"canvas"}:
            raise ValueError("显式 canvas 不能与显式旧尺寸参数 aspect/base/cell_base 同时使用。")

    def legacy_size_fields(self) -> frozenset[str]:
        """Identify explicitly configured legacy sizing, including mutations."""
        explicit = set(self._explicit_size_fields) - {"canvas"}
        for key, default in _LEGACY_SIZE_DEFAULTS.items():
            value = getattr(self, key)
            if value is not None and value != default:
                explicit.add(key)
        return frozenset(explicit)

    def has_explicit_canvas(self) -> bool:
        return self.canvas is not None and (
            "canvas" in self._explicit_size_fields or self.canvas != DEFAULT_CANVAS
        )

    def to_dict(self) -> Dict[str, Any]:
        """导出当前有效尺寸路径与其余配置，支持无冲突的 JSON 往返。"""
        result = {
            "aspect": self.aspect,
            "base": self.base,
            "cell_base": self.cell_base,
            "dpi": self.dpi,
            "theme": self.theme,
            "palette": self.palette,
            "title": self.title,
            "legend_max_entries": self.legend_max_entries,
            "legend_position": self.legend_position,
            "legend": normalize_legend(self.legend),
            "font_family": self.font_family,
            "background": self.background,
            "category_colors": self.category_colors,
            "facets": normalize_facets(self.facets),
            "auto_margins": self.auto_margins,
            "autosize": self.autosize,
        }
        # Serialize the active size path only. Restoring inherited legacy
        # defaults must not turn a physical canvas into a conflicting request.
        if not self.legacy_size_fields():
            for key in _LEGACY_SIZE_DEFAULTS:
                result.pop(key)
            result["canvas"] = None if self.canvas is None else dict(self.canvas)
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FigureConfig":
        """从 dict 构建配置（用户覆盖用）。"""
        valid_keys = {
            "aspect", "base", "cell_base", "canvas", "dpi", "theme", "palette", "title",
            "legend_max_entries", "legend_position", "legend",
            "font_family", "background", "category_colors", "auto_margins", "autosize",
            "facets",
        }
        return cls(**{k: v for k, v in d.items() if k in valid_keys})


# ── 全局单例 ──────────────────────────────────────────────────

_default_config: Optional[FigureConfig] = None


def get_default_config() -> FigureConfig:
    """获取全局默认配置单例。"""
    global _default_config
    if _default_config is None:
        _default_config = FigureConfig()
    return _default_config


def set_default_config(config: FigureConfig) -> None:
    """设置全局默认配置（模块级生效）。"""
    global _default_config
    _default_config = config
