"""Native paired trajectories and explicitly specified paired estimation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.paired import compute_paired, validate_paired


@dataclass
class _Paired(ChartSpec):
    required_fields: ClassVar[list[str]] = ["pair", "x", "y"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None, "lower": None, "upper": None}
    order: list[Any] | None = None
    summary: str | None = "mean"
    ci_method: str | None = None
    confidence: float | None = None
    bandwidth: str | float = "scott"
    density_range: list[float] | tuple[float, float] | None = None

    def _parameters(self):
        return {key: _plain_options(getattr(self, key)) for key in
                ("order", "summary", "ci_method", "confidence", "bandwidth")}

    def validate(self, df):
        return validate_paired(df, self.mapping, kind=self.chart_type,
                               density_range=self.density_range, **self._parameters())

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": []}

    def compute_data(self, df):
        return compute_paired(df, self.mapping, kind=self.chart_type,
                              density_range=self.density_range, **self._parameters())

    def _chart_options(self):
        return {**self._parameters(), "density_range": _plain_options(self.density_range)}


@register_chart
@dataclass
class Paired(_Paired):
    """Complete pair trajectories with a labelled descriptive mean overlay."""
    chart_type: ClassVar[str] = "paired"


@register_chart
@dataclass
class Estimation(_Paired):
    """Raw pairs and difference density with supplied/requested mean intervals."""
    chart_type: ClassVar[str] = "estimation"
