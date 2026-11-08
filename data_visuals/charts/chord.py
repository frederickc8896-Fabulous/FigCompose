"""An undirected weighted graph, with one common endpoint-width scale."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.chord import compute_chord, validate_chord_input


@register_chart
@dataclass
class Chord(ChartSpec):
    chart_type: ClassVar[str] = "chord"
    required_fields: ClassVar[list[str]] = ["source", "target", "value"]
    optional_fields: ClassVar[dict[str, Any]] = {}

    order: list[Any] | None = None
    aggregate: str | None = None
    summary: bool = False
    ticks: bool = True

    def validate(self, df):
        return validate_chord_input(df, self.mapping, order=self.order,
                                    aggregate=self.aggregate, summary=self.summary, ticks=self.ticks)

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": ["chord"]}

    def compute_data(self, df):
        return compute_chord(df, self.mapping, order=self.order,
                             aggregate=self.aggregate, summary=self.summary, ticks=self.ticks)

    def _chart_options(self):
        defaults = {"order": None, "aggregate": None, "summary": False, "ticks": True}
        return {name: _plain_options(getattr(self, name)) for name, default in defaults.items()
                if getattr(self, name) != default}
