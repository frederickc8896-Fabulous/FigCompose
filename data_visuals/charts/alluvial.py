"""A weighted complete-path alluvial diagram with conserved stage marginals."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.alluvial import compute_alluvial, validate_alluvial_input


@register_chart
@dataclass
class Alluvial(ChartSpec):
    chart_type: ClassVar[str] = "alluvial"
    required_fields: ClassVar[list[str]] = ["stages", "value"]
    optional_fields: ClassVar[dict[str, Any]] = {}
    stage_titles: list[str] | None = None
    note: str | None = None
    order: list[Any] | None = None

    def validate(self, df):
        return validate_alluvial_input(df, self.mapping, stage_titles=self.stage_titles, note=self.note, order=self.order)

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": ["alluvial"]}

    def compute_data(self, df):
        return compute_alluvial(df, self.mapping, stage_titles=self.stage_titles, note=self.note, order=self.order)

    def _chart_options(self):
        return {key: _plain_options(getattr(self, key)) for key in ("stage_titles", "note", "order")
                if getattr(self, key) is not None}
