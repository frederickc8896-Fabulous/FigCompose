"""Concentric circular scores: complete object/metric cells on a shared scale."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pandas as pd

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.circular import validate_circular_input


@register_chart
@dataclass
class CircularBar(ChartSpec):
    """Map ``x`` objects and ``group`` metrics to independent angular scores.

    Every object must contain every metric. Repeated cells require an explicit
    aggregation, and all values retain the user-declared ``value_range`` scale.
    Optional summaries are statistical requests, not renderer-side guesses.
    """

    chart_type: ClassVar[str] = "circular_bar"
    required_fields: ClassVar[list[str]] = ["x", "y", "group"]
    optional_fields: ClassVar[dict[str, Any]] = {}

    value_range: tuple[float, float] | list[float] = (0, 100)
    summary: str | None = None
    center: str | None = "count"
    aggregate: str | None = None
    order: list[Any] | None = None
    rounded: bool = True
    summary_position: str = "auto"

    def validate(self, df: pd.DataFrame) -> list[str]:
        if not isinstance(self.summary_position, str) or self.summary_position not in {"auto", "inline", "top"}:
            return ["[circular_bar] summary_position must be auto, inline or top"]
        return validate_circular_input(
            df, self.mapping, value_range=self.value_range, summary=self.summary,
            center=self.center, aggregate=self.aggregate, order=self.order,
            rounded=self.rounded,
        )

    def compute_requirements(self) -> dict[str, Any]:
        return {"group_by": [], "columns": {}, "preprocess": [],
                "statistics": ["circular_bar"]}

    def _chart_options(self) -> dict[str, Any]:
        defaults = {"value_range": (0, 100), "summary": None, "center": "count",
                    "aggregate": None, "order": None, "rounded": True, "summary_position": "auto"}
        return {key: _plain_options(getattr(self, key)) for key, default in defaults.items()
                if getattr(self, key) != default}
