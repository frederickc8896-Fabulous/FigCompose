"""Validated, explicit legend overrides shared by both public entry points.

Distances and font sizes use typographic points. Defaults are resolved by
the renderer, so normalizing a partial override never erases inherited fields.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Integral, Real
from typing import Any


LEGEND_FIELDS = frozenset({
    "visible", "scope", "position", "ncols", "fontsize", "gap",
    "columnspacing", "labelspacing", "handlelength", "handletextpad",
    "borderpad", "frameon", "anchor", "order", "labels",
})
LEGEND_INSIDE_POSITIONS = frozenset({
    "upper left", "upper right", "lower left", "lower right",
})
LEGEND_OUTSIDE_POSITIONS = frozenset({"top", "bottom", "left", "right"})


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"legend.{name} must be a finite number in points.")
    result = float(value)
    if not isfinite(result) or (result <= 0 if positive else result < 0):
        relation = "positive" if positive else "non-negative"
        raise ValueError(f"legend.{name} must be finite and {relation}.")
    return result


def _scalar(value: Any, name: str) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real) and isfinite(float(value)):
        return float(value)
    raise ValueError(f"legend.{name} entries must be finite JSON scalars.")


def normalize_legend(value: Any = None) -> dict[str, Any]:
    """Copy and validate only explicitly supplied fields.

    ``False`` hides a legend; ``None`` and ``True`` use inherited/default
    settings. An explicit ``{'visible': True}`` re-enables a hidden default.
    Corner names describe legends inside a panel; whether they can become
    shared is checked after the panel groups have been resolved.
    """
    if value is None or value is True:
        return {}
    if value is False:
        return {"visible": False}
    if not isinstance(value, Mapping):
        raise ValueError("legend must be a mapping, bool, or None.")
    unknown = set(value) - LEGEND_FIELDS
    if unknown:
        raise ValueError(f"Unknown legend fields: {', '.join(sorted(map(str, unknown)))}")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"visible", "frameon"}:
            if not isinstance(item, bool):
                raise ValueError(f"legend.{key} must be a bool.")
            result[key] = item
        elif key == "scope":
            if not isinstance(item, str) or item not in {"auto", "shared", "local"}:
                raise ValueError("legend.scope must be 'auto', 'shared', or 'local'.")
            result[key] = item
        elif key == "position":
            if not isinstance(item, str):
                raise ValueError("legend.position must be a supported position name.")
            position = " ".join(item.lower().replace("-", " ").replace("_", " ").split())
            aliases = {"top left": "upper left", "top right": "upper right",
                       "bottom left": "lower left", "bottom right": "lower right"}
            position = aliases.get(position, position)
            if position not in LEGEND_INSIDE_POSITIONS | LEGEND_OUTSIDE_POSITIONS:
                raise ValueError(f"Unsupported legend.position: {item!r}.")
            result[key] = position
        elif key == "ncols":
            if item is not None and (
                isinstance(item, bool) or not isinstance(item, Integral) or item < 1
            ):
                raise ValueError("legend.ncols must be a positive integer or None.")
            result[key] = None if item is None else int(item)
        elif key in {"fontsize", "gap"}:
            result[key] = None if item is None else _number(item, key, positive=key == "fontsize")
        elif key in {"columnspacing", "labelspacing", "handlelength", "handletextpad", "borderpad"}:
            result[key] = _number(item, key)
        elif key == "anchor":
            if item is None:
                result[key] = None
            else:
                if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or len(item) != 2:
                    raise ValueError("legend.anchor must be two fractions in [0, 1] or None.")
                anchor = [_number(coordinate, key) for coordinate in item]
                if any(coordinate > 1 for coordinate in anchor):
                    raise ValueError("legend.anchor fractions must be in [0, 1].")
                result[key] = anchor
        elif key == "order":
            if item is None:
                result[key] = None
            else:
                if not isinstance(item, Sequence) or isinstance(item, (str, bytes)):
                    raise ValueError("legend.order must be a list of unique scalars or None.")
                order = [_scalar(entry, key) for entry in item]
                if len(set(order)) != len(order):
                    raise ValueError("legend.order must not contain duplicate entries.")
                result[key] = order
        elif key == "labels":
            if item is None:
                result[key] = None
            else:
                if not isinstance(item, Mapping) or any(not isinstance(label, str) for label in item.values()):
                    raise ValueError("legend.labels must map scalar keys to strings or be None.")
                result[key] = {_scalar(entry, key): label for entry, label in item.items()}
    return result


def merge_legend(global_options: Any = None, panel_options: Any = None, *, panel_explicit: bool = False) -> dict[str, Any]:
    """Merge a panel override without resetting unrelated global choices."""
    result = normalize_legend(global_options)
    panel = normalize_legend(panel_options)
    result.update(panel)
    if panel_explicit and "scope" not in panel:
        result["scope"] = "local"
    return result
