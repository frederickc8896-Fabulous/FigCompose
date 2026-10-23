"""Validate physical Figure dimensions and convert them to design points."""

from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real
from typing import Any


DEFAULT_CANVAS = {"width": 180.0, "height": None, "unit": "mm"}
POINTS_PER_INCH = 72.0
MM_PER_INCH = 25.4


def _positive_dimension(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"canvas.{name} 必须是正的有限数值，不能是布尔值或字符串。")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"canvas.{name} 必须是正的有限数值。") from None
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"canvas.{name} 必须是正的有限数值。")
    return result


def normalize_canvas(
    canvas: Mapping[str, Any] | None,
    *,
    default: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return point dimensions together with the original physical request.

    ``None`` inherits ``default`` (or the package default); an explicitly
    supplied empty mapping is invalid. The returned dictionaries are new
    objects and never alias the caller's configuration.
    """
    source = canvas if canvas is not None else default
    if source is None:
        source = DEFAULT_CANVAS
    if not isinstance(source, Mapping):
        raise TypeError("canvas 必须是包含 width 的字典，或为 None。")
    unknown = set(source) - {"width", "height", "unit"}
    if unknown:
        names = ", ".join(sorted(map(repr, unknown)))
        raise ValueError(f"canvas 包含未知字段: {names}。仅支持 width、height、unit。")
    if "width" not in source:
        raise ValueError("显式 canvas 必须包含 width；空字典或仅提供 height 均不支持。")
    unit = source.get("unit", "mm")
    if not isinstance(unit, str) or unit not in ("mm", "in"):
        raise ValueError("canvas.unit 仅支持 'mm' 或 'in'。")
    width = _positive_dimension(source["width"], "width")
    raw_height = source.get("height")
    height = None if raw_height is None else _positive_dimension(raw_height, "height")
    factor = POINTS_PER_INCH / MM_PER_INCH if unit == "mm" else POINTS_PER_INCH
    width_pt = width * factor
    height_pt = None if height is None else height * factor
    if not math.isfinite(width_pt) or (height_pt is not None and not math.isfinite(height_pt)):
        raise ValueError("canvas 尺寸换算为 pt 后必须为有限数值。")
    return {
        "width": width_pt,
        "height": height_pt,
        "unit": "pt",
        "request": {"width": width, "height": height, "unit": unit},
        "height_auto": height is None,
    }
