"""Native raincloud and ridgeline declarations over unaggregated observations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.distribution import compute_distribution, validate_distribution


@dataclass
class _Distribution(ChartSpec):
    required_fields: ClassVar[list[str]] = ["x", "y"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None}
    order: list[Any] | None = None
    bandwidth: str | float = "scott"
    normalization: str = "peak"
    horizontal: bool = True
    summary: str | None = "median"

    def _parameters(self):
        return {key: _plain_options(getattr(self, key)) for key in
                ("order", "bandwidth", "normalization", "horizontal", "summary")}

    def validate(self, df):
        return validate_distribution(df, self.mapping, **self._parameters())

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": []}

    def compute_data(self, df):
        return compute_distribution(df, self.mapping, kind=self.chart_type, **self._parameters())

    def _chart_options(self):
        # The displayed measurement axis must be explicit for metadata/layout.
        return self._parameters()


@register_chart
@dataclass
class Raincloud(_Distribution):
    """Half Gaussian KDE, every observation and a median/IQR summary."""
    chart_type: ClassVar[str] = "raincloud"


@register_chart
@dataclass
class Ridgeline(_Distribution):
    """Ordered Gaussian KDE layers with complete observation rugs."""
    chart_type: ClassVar[str] = "ridgeline"
