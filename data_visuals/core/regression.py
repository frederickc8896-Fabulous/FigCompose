"""Compare measured layout snapshots without pixel or raster dependencies.

The baseline contains physical geometry and visible presentation choices, never
source observations or executable callbacks.  Diagnostic solver bookkeeping and
PNG resolution are intentionally outside the comparison.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any


_VERSION = "1.0"
_BOX_KEYS = frozenset(("x", "y", "w", "h"))
_REPORT_KEYS = frozenset((
    "version", "canvas", "panels", "elements", "style", "limitations", "issues",
))
_PANEL_KEYS = frozenset((
    "id", "row", "col", "row_span", "col_span", "chart_type", "cell",
    "data_zone", "minimum", "gutters", "measured_gutters", "decoration_bbox",
    "data_area_fraction",
))
_ELEMENT_KEYS = frozenset((
    "id", "kind", "panel", "text", "bbox", "font_size", "font_family",
))


def _number(value: Any, path: str, *, minimum: float | None = None,
            positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{path} must be a finite real number")
    result = float(value)
    if positive and result <= 0:
        raise ValueError(f"{path} must be positive")
    if minimum is not None and result < minimum:
        raise ValueError(f"{path} must be at least {minimum}")
    return result


def _object(value: Any, path: str, *, allowed: frozenset[str] | None = None,
            required: frozenset[str] = frozenset()) -> dict:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be an object with string keys")
    if allowed is not None:
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown {path} fields: {', '.join(sorted(unknown))}")
    missing = required - set(value)
    if missing:
        raise ValueError(f"Missing {path} fields: {', '.join(sorted(missing))}")
    return dict(value)


def _string(value: Any, path: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ValueError(f"{path} must be {'a' if empty else 'a non-empty'} string")
    return value


def _json_value(value: Any, path: str) -> Any:
    """Validate and detach JSON-shaped values, including diagnostic metadata."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Real):
        _number(value, path)
        return int(value) if isinstance(value, int) else float(value)
    if isinstance(value, Mapping):
        obj = _object(value, path)
        return {key: _json_value(item, f"{path}.{key}") for key, item in obj.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ValueError(f"{path} must contain only JSON values")


def _box(value: Any, path: str) -> dict:
    box = _object(value, path, allowed=_BOX_KEYS, required=_BOX_KEYS)
    return {
        key: _number(box[key], f"{path}.{key}", minimum=0 if key in ("w", "h") else None)
        for key in ("x", "y", "w", "h")
    }


def _coordinate(value: Any, path: str) -> list[int] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value
    ):
        raise ValueError(f"{path} must be a [row, col] pair of non-negative integers or null")
    return list(value)


def _dimensions(value: Any, path: str, keys: frozenset[str]) -> dict:
    obj = _object(value, path, allowed=keys, required=keys)
    return {key: _number(item, f"{path}.{key}", minimum=0) for key, item in obj.items()}


def validate_report_snapshot(value: Any) -> dict:
    """Return a detached, validated version-1 layout report dictionary.

    Invalid or future schemas fail explicitly rather than silently losing
    baseline information.  The validator is also used before writing snapshots.
    """
    report = _object(value, "report", allowed=_REPORT_KEYS, required=_REPORT_KEYS)
    if report["version"] != _VERSION:
        raise ValueError(f"Unsupported layout report version: {report['version']!r}")
    canvas_keys = frozenset(("width_pt", "height_pt", "width_mm", "height_mm"))
    canvas = _object(report["canvas"], "canvas", allowed=canvas_keys, required=canvas_keys)
    report["canvas"] = {
        key: _number(item, f"canvas.{key}", positive=True) for key, item in canvas.items()
    }
    if not isinstance(report["panels"], list):
        raise ValueError("panels must be a list")
    panels = []
    panel_ids: set[str] = set()
    cells: set[tuple[int, int]] = set()
    for index, value in enumerate(report["panels"]):
        path = f"panels[{index}]"
        panel = _object(value, path, allowed=_PANEL_KEYS, required=frozenset((
            "id", "row", "col", "chart_type", "cell", "data_zone",
            "minimum", "gutters", "data_area_fraction",
        )))
        identifier = _string(panel["id"], f"{path}.id")
        if identifier in panel_ids:
            raise ValueError(f"Duplicate panel id: {identifier!r}")
        panel_ids.add(identifier)
        for key in ("row", "col", "row_span", "col_span"):
            if key not in panel:
                continue
            item = panel[key]
            lower = 1 if key.endswith("span") else 0
            if isinstance(item, bool) or not isinstance(item, int) or item < lower:
                raise ValueError(f"{path}.{key} must be an integer at least {lower}")
        cell_key = panel["row"], panel["col"]
        if cell_key in cells:
            raise ValueError(f"Duplicate panel grid position: {cell_key!r}")
        cells.add(cell_key)
        _string(panel["chart_type"], f"{path}.chart_type")
        panel["cell"] = _box(panel["cell"], f"{path}.cell")
        panel["data_zone"] = _box(panel["data_zone"], f"{path}.data_zone")
        panel["minimum"] = _dimensions(panel["minimum"], f"{path}.minimum",
                                       frozenset(("width", "height")))
        for key in ("gutters", "measured_gutters"):
            if key in panel:
                panel[key] = _dimensions(panel[key], f"{path}.{key}",
                                         frozenset(("left", "right", "top", "bottom")))
        if panel.get("decoration_bbox") is not None:
            panel["decoration_bbox"] = _box(panel["decoration_bbox"], f"{path}.decoration_bbox")
        fraction = _number(panel["data_area_fraction"], f"{path}.data_area_fraction", minimum=0)
        # Native edits can move/resize a data rectangle outside its allocated
        # cell. Preserve that measured ratio, including values above one, so
        # the report can describe the overflow instead of failing to load.
        panel["data_area_fraction"] = fraction
        panels.append(panel)
    report["panels"] = panels
    if not isinstance(report["elements"], list):
        raise ValueError("elements must be a list")
    elements = []
    element_ids: set[str] = set()
    for index, value in enumerate(report["elements"]):
        path = f"elements[{index}]"
        element = _object(value, path, allowed=_ELEMENT_KEYS, required=_ELEMENT_KEYS)
        identifier = _string(element["id"], f"{path}.id")
        if identifier in element_ids:
            raise ValueError(f"Duplicate element id: {identifier!r}")
        element_ids.add(identifier)
        _string(element["kind"], f"{path}.kind")
        element["panel"] = _coordinate(element["panel"], f"{path}.panel")
        if element["panel"] is not None and tuple(element["panel"]) not in cells:
            raise ValueError(f"{path}.panel refers to an unknown panel")
        _string(element["text"], f"{path}.text", empty=True)
        element["bbox"] = _box(element["bbox"], f"{path}.bbox")
        element["font_size"] = _number(element["font_size"], f"{path}.font_size", positive=True)
        _string(element["font_family"], f"{path}.font_family")
        elements.append(element)
    report["elements"] = elements
    report["style"] = _json_value(_object(report["style"], "style"), "style")
    if not isinstance(report["limitations"], list):
        raise ValueError("limitations must be a list of strings")
    report["limitations"] = [
        _string(item, f"limitations[{index}]")
        for index, item in enumerate(report["limitations"])
    ]
    if not isinstance(report["issues"], list):
        raise ValueError("issues must be a list")
    issues = []
    issue_keys = frozenset(("code", "severity", "message", "panel", "bounds"))
    for index, value in enumerate(report["issues"]):
        path = f"issues[{index}]"
        issue = _object(value, path, allowed=issue_keys, required=issue_keys)
        for key in ("code", "message"):
            _string(issue[key], f"{path}.{key}")
        if issue["severity"] not in ("info", "warning", "error"):
            raise ValueError(f"{path}.severity must be info, warning or error")
        issue["panel"] = _coordinate(issue["panel"], f"{path}.panel")
        if issue["panel"] is not None and tuple(issue["panel"]) not in cells:
            raise ValueError(f"{path}.panel refers to an unknown panel")
        if not isinstance(issue["bounds"], list):
            raise ValueError(f"{path}.bounds must be a list of bounding boxes")
        issue["bounds"] = [_box(item, f"{path}.bounds[{bound_index}]")
                           for bound_index, item in enumerate(issue["bounds"])]
        issues.append(issue)
    report["issues"] = issues
    return report


@dataclass(frozen=True)
class LayoutChange:
    """One difference between a baseline and the currently measured figure."""

    code: str
    path: str
    before: Any
    after: Any
    message: str

    def to_dict(self) -> dict:
        return {
            "code": self.code, "path": self.path, "before": deepcopy(self.before),
            "after": deepcopy(self.after), "message": self.message,
        }


@dataclass
class LayoutComparison:
    """Presentation differences; ``ok`` means the snapshots agree in tolerance."""

    changes: list[LayoutChange] = field(default_factory=list)
    tolerance: float = 0.5

    def __post_init__(self) -> None:
        self.tolerance = _number(self.tolerance, "tolerance", minimum=0)

    @property
    def ok(self) -> bool:
        return not self.changes

    def to_dict(self) -> dict:
        return {
            "version": _VERSION, "ok": self.ok, "tolerance": self.tolerance,
            "changes": [change.to_dict() for change in self.changes],
        }

    def summary(self) -> str:
        if self.ok:
            return f"Layout matches baseline (tolerance: {self.tolerance:g} pt)."
        return "\n".join([
            f"{len(self.changes)} layout change(s) (tolerance: {self.tolerance:g} pt):",
            *(f"- {change.path}: {change.message}" for change in self.changes),
        ])

    def save(self, path: str | Path) -> Path:
        """Write comparison JSON only after all values have been validated."""
        payload = _json_value(self.to_dict(), "comparison")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        target = Path(path)
        target.write_text(encoded, encoding="utf-8")
        return target


def _snapshot(value: Any) -> dict:
    if isinstance(value, (str, Path)) or hasattr(value, "__fspath__"):
        try:
            with Path(value).open("r", encoding="utf-8-sig") as handle:
                value = json.load(handle, object_pairs_hook=_unique_json_object)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid layout report JSON: {exc.msg}") from exc
    elif not isinstance(value, Mapping):
        # Imported at call time: FigureReport.compare delegates back here.
        from data_visuals.core.quality import FigureReport
        if not isinstance(value, FigureReport):
            raise TypeError("A layout snapshot must be a FigureReport, report dictionary or JSON path")
        value = value.to_dict()
    return validate_report_snapshot(value)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def compare_reports(current: Any, baseline: Any, *, tolerance: float = 0.5) -> LayoutComparison:
    """Compare physical layout, actual text/fonts, and semantic styles.

    ``tolerance`` is an absolute bound in typographic points for geometry only.
    Fonts, content, and series styles must match; raster DPI does not enter the
    comparison.  Element and panel list order does not affect stable identities.
    """
    tolerance = _number(tolerance, "tolerance", minimum=0)
    after, before = _snapshot(current), _snapshot(baseline)
    changes: list[LayoutChange] = []

    def change(code: str, path: str, old: Any, new: Any, message: str) -> None:
        changes.append(LayoutChange(code, path, deepcopy(old), deepcopy(new), message))

    def geometry(path: str, old: Mapping, new: Mapping, keys: tuple[str, ...]) -> None:
        for key in keys:
            if abs(new[key] - old[key]) > tolerance + 1e-9:
                change("geometry_changed", f"{path}.{key}", old[key], new[key],
                       f"{old[key]:g} → {new[key]:g} pt")

    geometry("canvas", before["canvas"], after["canvas"], ("width_pt", "height_pt"))
    for section in ("panels", "elements"):
        old_items = {item["id"]: item for item in before[section]}
        new_items = {item["id"]: item for item in after[section]}
        prefix = "panel" if section == "panels" else "element"
        for identifier in sorted(old_items.keys() - new_items.keys()):
            change(f"{prefix}_removed", f"{section}[{identifier}]", old_items[identifier], None,
                   f"{prefix.capitalize()} removed")
        for identifier in sorted(new_items.keys() - old_items.keys()):
            change(f"{prefix}_added", f"{section}[{identifier}]", None, new_items[identifier],
                   f"{prefix.capitalize()} added")
        for identifier in sorted(old_items.keys() & new_items.keys()):
            old, new = old_items[identifier], new_items[identifier]
            path = f"{section}[{identifier}]"
            if section == "panels":
                for key in ("row", "col", "chart_type", "row_span", "col_span"):
                    default = 1 if key.endswith("span") else None
                    if old.get(key, default) != new.get(key, default):
                        change("panel_changed", f"{path}.{key}", old.get(key, default),
                               new.get(key, default), "Panel topology or chart type changed")
                for key in ("cell", "data_zone"):
                    geometry(f"{path}.{key}", old[key], new[key], ("x", "y", "w", "h"))
            else:
                for key in ("kind", "panel", "text", "font_family"):
                    if old[key] != new[key]:
                        code = "font_changed" if key == "font_family" else "element_changed"
                        change(code, f"{path}.{key}", old[key], new[key], f"Element {key} changed")
                old_size, new_size = old["font_size"], new["font_size"]
                if old_size is None or new_size is None:
                    size_changed = old_size != new_size
                else:
                    size_changed = not math.isclose(old_size, new_size, rel_tol=0, abs_tol=1e-6)
                if size_changed:
                    change("font_changed", f"{path}.font_size", old_size, new_size,
                           "Font size changed")
                geometry(f"{path}.bbox", old["bbox"], new["bbox"], ("x", "y", "w", "h"))

    def styles(old: Any, new: Any, path: str) -> None:
        if isinstance(old, dict) and isinstance(new, dict):
            # Output DPI affects raster sampling, not the physical presentation.
            old_keys, new_keys = set(old) - {"dpi"}, set(new) - {"dpi"}
            for key in sorted(old_keys | new_keys):
                if key not in old_keys or key not in new_keys:
                    change("style_changed", f"{path}.{key}", old.get(key), new.get(key),
                           "Style field added or removed")
                else:
                    styles(old[key], new[key], f"{path}.{key}")
        elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
            for index, (old_item, new_item) in enumerate(zip(old, new)):
                styles(old_item, new_item, f"{path}[{index}]")
        elif type(old) is not type(new) or old != new:
            change("style_changed", path, old, new, "Presentation style changed")

    styles(before["style"], after["style"], "style")
    return LayoutComparison(changes=changes, tolerance=tolerance)


__all__ = ["LayoutChange", "LayoutComparison", "compare_reports", "validate_report_snapshot"]
