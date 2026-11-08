"""Explicit native three-dimensional charts with validated compute contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pandas as pd

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.three_d import (compute_bar3d, compute_scatter3d,
                                        compute_waterfall3d)


@dataclass
class _ThreeD(ChartSpec):
    projection: ClassVar[str] = "3d"
    elev: float = 25
    azim: float = -58
    box_aspect: tuple[float, float, float] | list[float] = (1, 1, 1)
    zoom: float = 1
    proj_type: str = "ortho"

    def _view(self):
        return {name: getattr(self, name) for name in
                ("elev", "azim", "box_aspect", "zoom", "proj_type")}

    def validate(self, df: pd.DataFrame) -> list[str]:
        try:
            self.compute_data(df)
        except (TypeError, ValueError, OverflowError) as error:
            return [f"[{self.chart_type}] {error}"]
        return []

    def compute_requirements(self) -> dict[str, Any]:
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": []}

    def _chart_options(self) -> dict[str, Any]:
        # Export all explicit defaults as well, keeping native snapshot replay
        # independent of later changes to camera or chart presentation defaults.
        from dataclasses import fields
        return {field.name: _plain_options(getattr(self, field.name))
                for field in fields(self) if field.name not in {"mapping", "title"}}


@register_chart
@dataclass
class Scatter3D(_ThreeD):
    """Measured x/y/z points; optional walls require explicit coordinates."""

    chart_type: ClassVar[str] = "scatter3d"
    required_fields: ClassVar[list[str]] = ["x", "y", "z"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None}

    projections: dict[str, float] | None = None
    projection_lines: list[str] | None = None
    point_size: float | None = None
    opacity: float = .95

    def compute_data(self, df: pd.DataFrame):
        return compute_scatter3d(df, self.mapping, projections=self.projections,
                                 projection_lines=self.projection_lines,
                                 point_size=self.point_size, opacity=self.opacity,
                                 **self._view())


@register_chart
@dataclass
class Waterfall3D(_ThreeD):
    """Ordered series in depth, with an explicitly declared fill baseline."""

    chart_type: ClassVar[str] = "waterfall3d"
    required_fields: ClassVar[list[str]] = ["x", "y", "group"]
    optional_fields: ClassVar[dict[str, Any]] = {}

    baseline: float | None = None
    aggregate: str | None = None
    order: list[Any] | None = None
    depth_spacing: float = 1
    fill: bool = True
    fill_alpha: float = .82
    linewidth: float | None = None
    markers: bool = False

    def compute_data(self, df: pd.DataFrame):
        return compute_waterfall3d(df, self.mapping, baseline=self.baseline,
                                   aggregate=self.aggregate, order=self.order,
                                   depth_spacing=self.depth_spacing, fill=self.fill,
                                   fill_alpha=self.fill_alpha, linewidth=self.linewidth,
                                   markers=self.markers,
                                   **self._view())


@register_chart
@dataclass
class Bar3D(_ThreeD):
    """One nonnegative amount, or an explicit stack, at every x/y category cell."""

    chart_type: ClassVar[str] = "bar3d"
    required_fields: ClassVar[list[str]] = ["x", "y", "value"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None}

    stacked: bool = False
    aggregate: str | None = None
    x_order: list[Any] | None = None
    y_order: list[Any] | None = None
    group_order: list[Any] | None = None
    baseline: float = 0
    width: tuple[float, float] | list[float] = (.68, .68)
    label_totals: bool = False
    total_format: str | None = None

    def compute_data(self, df: pd.DataFrame):
        return compute_bar3d(df, self.mapping, stacked=self.stacked,
                             aggregate=self.aggregate, x_order=self.x_order,
                             y_order=self.y_order, group_order=self.group_order,
                             baseline=self.baseline, width=self.width,
                             label_totals=self.label_totals,
                             total_format=self.total_format, **self._view())
