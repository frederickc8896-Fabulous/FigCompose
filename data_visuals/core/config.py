"""
core/config.py
==============
全局默认配置 — 为 FigureSpec 和 Figure 提供可全局覆盖的默认值。

设计原则:
    - 字段校验与归一化不执行数据计算；save/load 显式读写论文配置
    - 用户可通过 Figure(config=...) 局部覆盖

参考: 论文视觉规范 (Helvetica, minimal axis, 2pt line, no grid)
"""

from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields as dataclass_fields
import json
from pathlib import Path
from typing import Optional, Dict, Any

from data_visuals.core.canvas import DEFAULT_CANVAS, normalize_canvas
from data_visuals.core.facets import normalize_facets
from data_visuals.core.legend import normalize_legend
from data_visuals.core.identity import normalize_fields, normalize_series


_UNSET = object()
_LEGACY_SIZE_DEFAULTS = {"aspect": "16:10", "base": "large", "cell_base": None}


@dataclass
class FigureConfig:
    """可复用于整篇论文的 Figure 默认配置。

    ``plot(..., config=paper)`` 与 ``Figure(config=paper)`` 共用此配置。
    ``fields`` 按原始列名声明 label/unit/format，仅控制显示。
    ``series`` 按分组列登记有序的 id/label/color/marker/linestyle，
    在不同 CSV 子集间保留颜色位置与系列身份。单图参数和子图选项可继续覆盖。
    ``save/load`` 显式保存、加载 JSON 或 YAML，不含数据和运行时绘图回调。
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
    fields: Dict[str, Dict[str, str]] = field(default_factory=dict)
    series: Dict[str, list[Dict[str, Any]]] = field(default_factory=dict)

    # ── 高级 ──
    auto_margins: bool = True
    autosize: bool = True           # layout 自动推导最优网格
    canvas: Optional[Dict[str, Any]] = _UNSET  # 默认 180 mm 栏宽，自动高度
    _explicit_size_fields: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.facets = normalize_facets(self.facets)
        self.legend = normalize_legend(self.legend)
        self.fields = normalize_fields(self.fields)
        self.series = normalize_series(self.series)
        self.category_colors = deepcopy(self.category_colors)
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
            "fields": normalize_fields(self.fields),
            "series": normalize_series(self.series),
            "auto_margins": self.auto_margins,
            "autosize": self.autosize,
        }
        # Serialize the active size path only. Restoring inherited legacy
        # defaults must not turn a physical canvas into a conflicting request.
        if not self.legacy_size_fields():
            for key in _LEGACY_SIZE_DEFAULTS:
                result.pop(key)
            result["canvas"] = None if self.canvas is None else dict(self.canvas)
        return deepcopy(result)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "FigureConfig":
        """从字典创建独立配置；未知字段报错，避免拼写错误被静默忽略。"""
        if not isinstance(d, Mapping):
            raise ValueError("FigureConfig must be a mapping.")
        valid_keys = {item.name for item in dataclass_fields(cls) if item.init}
        unknown = set(d) - valid_keys
        if unknown:
            raise ValueError(f"Unknown FigureConfig fields: {', '.join(sorted(map(str, unknown)))}")
        return cls(**deepcopy(dict(d)))

    def save(self, path: str | Path) -> Path:
        """Save reusable configuration as UTF-8 JSON or safe YAML.

        The filename must end in .json, .yaml or .yml. Parent directories must
        already exist; this method never exports data or figure artists.
        """
        target = _config_path(path)
        payload = self.to_dict()
        if target.suffix.lower() == ".json":
            _check_json_keys(payload)
            content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        else:
            import yaml
            content = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        target.write_text(content, encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "FigureConfig":
        """Load a validated JSON/YAML paper configuration without global effects."""
        source = _config_path(path)
        content = source.read_text(encoding="utf-8-sig")
        if source.suffix.lower() == ".json":
            try:
                payload = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON FigureConfig in {source}: {exc.msg}") from exc
        else:
            import yaml
            try:
                payload = yaml.safe_load(content)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML FigureConfig in {source}: {exc}") from exc
        return cls.from_dict(payload)


def _config_path(path: str | Path) -> Path:
    try:
        result = Path(path)
    except TypeError as exc:
        raise ValueError("FigureConfig path must be a .json, .yaml or .yml filename.") from exc
    if result.suffix.lower() not in {".json", ".yaml", ".yml"}:
        raise ValueError("FigureConfig files must use .json, .yaml or .yml.")
    return result


def _check_json_keys(value: Any, context: str = "FigureConfig") -> None:
    """Avoid JSON silently changing numeric/bool lookup keys into strings."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(
                f"{context} contains non-string mapping keys; JSON would change their identity. "
                "Save as .yaml/.yml to preserve keys, or use string IDs/keys."
            )
        for key, item in value.items():
            _check_json_keys(item, f"{context}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_json_keys(item, f"{context}[{index}]")


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
