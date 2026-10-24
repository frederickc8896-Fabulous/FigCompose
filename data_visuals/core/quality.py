"""Portable, measured figure checks; no data or drawing callbacks are stored."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QualityIssue:
    """One measured issue, located in top-left-origin design points."""

    code: str
    severity: str
    message: str
    panel: tuple[int, int] | None = None
    bounds: list[dict[str, float]] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.code, str) or not self.code:
            raise ValueError("QualityIssue.code must be a nonempty string")
        if self.severity not in {"info", "warning", "error"}:
            raise ValueError("QualityIssue.severity must be info, warning or error")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("QualityIssue.message must be a nonempty string")
        if self.panel is not None:
            if (not isinstance(self.panel, (list, tuple)) or len(self.panel) != 2
                    or any(isinstance(item, bool) or not isinstance(item, int) or item < 0
                           for item in self.panel)):
                raise ValueError("QualityIssue.panel must be a row/column pair or None")
            object.__setattr__(self, "panel", tuple(self.panel))
        object.__setattr__(self, "bounds", deepcopy(self.bounds))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "message": self.message,
                "panel": list(self.panel) if self.panel is not None else None,
                "bounds": deepcopy(self.bounds)}


class FigureQualityError(ValueError):
    """An explicitly requested quality gate rejected a measured report."""

    def __init__(self, report: "FigureReport"):
        self.report = report
        super().__init__(report.summary())


@dataclass
class FigureReport:
    """A JSON-safe snapshot of final geometry, typography and checked issues.

    All geometry uses points with the origin at the upper left. ``ok`` means
    no measured errors; warnings remain visible and can be enforced using
    ``raise_for_errors(include_warnings=True)``. Plot-area fractions describe
    allocated rectangles, not unused pixels or scientific/aesthetic quality.
    """

    canvas: dict[str, Any]
    panels: list[dict[str, Any]] = field(default_factory=list)
    elements: list[dict[str, Any]] = field(default_factory=list)
    issues: list[QualityIssue] = field(default_factory=list)
    style: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    version: str = "1.0"

    def __post_init__(self):
        self.canvas = deepcopy(self.canvas)
        self.panels = deepcopy(self.panels)
        self.elements = deepcopy(self.elements)
        self.style = deepcopy(self.style)
        self.limitations = deepcopy(self.limitations)
        self.issues = [item if isinstance(item, QualityIssue) else QualityIssue(**item)
                       for item in self.issues]
        self.to_dict()  # Reject malformed/nonportable snapshots immediately.

    @property
    def errors(self) -> list[QualityIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[QualityIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        from data_visuals.core.regression import validate_report_snapshot
        return validate_report_snapshot({
            "version": self.version, "canvas": self.canvas, "panels": self.panels,
            "elements": self.elements, "style": self.style,
            "issues": [issue.to_dict() for issue in self.issues], "limitations": self.limitations,
        })

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FigureReport":
        from data_visuals.core.regression import validate_report_snapshot
        return cls(**validate_report_snapshot(value))

    def save(self, path: str | Path) -> Path:
        """Save a portable layout snapshot; the parent directory must exist."""
        target = _json_path(path)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2,
                                     allow_nan=False) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "FigureReport":
        source = _json_path(path)
        from data_visuals.core.regression import _unique_json_object
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"),
                                 object_pairs_hook=_unique_json_object)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid figure report in {source}: {exc.msg}") from exc
        return cls.from_dict(payload)

    def compare(self, baseline: "FigureReport | Mapping[str, Any] | str | Path", *,
                tolerance: float = .5):
        """Compare measured geometry/text/fonts/styles, allowing pt tolerance.

        This is a structural layout comparison, not a pixel image comparison.
        It does not evaluate data correctness or diagram node placement.
        """
        from data_visuals.core.regression import compare_reports
        return compare_reports(self, baseline, tolerance=tolerance)

    def raise_for_errors(self, *, include_warnings: bool = False) -> None:
        if not isinstance(include_warnings, bool):
            raise ValueError("include_warnings must be bool")
        if self.errors or (include_warnings and self.warnings):
            raise FigureQualityError(self)

    def summary(self) -> str:
        width = self.canvas["width_mm"]
        height = self.canvas["height_mm"]
        area = self.canvas["width_pt"] * self.canvas["height_pt"]
        allocated = sum(panel["data_zone"]["w"] * panel["data_zone"]["h"] for panel in self.panels)
        minimum = min((element["font_size"] for element in self.elements), default=None)
        lines = [f"Figure check: {'passed' if self.ok else 'failed'} "
                 f"({len(self.errors)} errors, {len(self.warnings)} warnings)",
                 f"Canvas: {width:.2f} × {height:.2f} mm; {len(self.panels)} panels; "
                 f"data rectangles: {allocated / area:.1%}"]
        if minimum is not None:
            lines.append(f"Minimum measured text: {minimum:g} pt")
        for issue in self.issues:
            where = f" panel {issue.panel}" if issue.panel is not None else ""
            lines.append(f"[{issue.severity}:{issue.code}]{where} {issue.message}")
        return "\n".join(lines)


def _json_path(path: str | Path) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".json":
        raise ValueError("Figure reports use .json files")
    return target


def _validate_check_options(min_fontsize, min_tick_gap, tolerance, debug=None) -> None:
    for name, value, positive in (("min_fontsize", min_fontsize, True),
                                   ("min_tick_gap", min_tick_gap, False),
                                   ("tolerance", tolerance, False)):
        if (isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)
                or (value <= 0 if positive else value < 0)):
            raise ValueError(f"{name} must be a finite {'positive' if positive else 'nonnegative'} number")
    if debug is not None and Path(debug).suffix.lower() not in {".png", ".svg", ".pdf"}:
        raise ValueError("debug output must use .png, .svg, or .pdf")


def check_figure(rendered, *, min_fontsize: float = 7.0, min_tick_gap: float = 1.0,
                 tolerance: float = 1.0, debug: str | Path | None = None) -> FigureReport:
    """Check an already rendered Matplotlib figure, including native edits.

    The caller retains ownership. Checks do not alter fonts, data or limits;
    optional debug output draws temporary overlays and restores the figure.
    FigCompose provides allocated cells; unmanaged axes only provide viewports.
    """
    _validate_check_options(min_fontsize, min_tick_gap, tolerance, debug)
    from data_visuals.renderer.mpl.quality import analyze_figure, write_debug
    report = analyze_figure(rendered, min_fontsize=min_fontsize,
                            min_tick_gap=min_tick_gap, tolerance=tolerance)
    if debug is not None:
        write_debug(rendered, report, debug)
    return report
