"""A wide numerical matrix, a genuine Ward tree and a categorical cluster ring."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.clustered_heatmap import (
    compute_clustered_heatmap, validate_clustered_heatmap_input,
)


@register_chart
@dataclass
class ClusteredHeatmap(ChartSpec):
    chart_type: ClassVar[str] = "clustered_heatmap"
    required_fields: ClassVar[list[str]] = ["sample", "traits"]
    optional_fields: ClassVar[dict[str, Any]] = {}

    value_range: tuple[float, float] | list[float] = (-1, 1)
    n_clusters: int = 4
    label_every: int = 2

    def validate(self, df):
        return validate_clustered_heatmap_input(df, self.mapping, value_range=self.value_range,
                                                n_clusters=self.n_clusters, label_every=self.label_every)

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": ["clustered_heatmap"]}

    def compute_data(self, df):
        return compute_clustered_heatmap(df, self.mapping, value_range=self.value_range,
                                         n_clusters=self.n_clusters, label_every=self.label_every)

    def _chart_options(self):
        defaults = {"value_range": (-1, 1), "n_clusters": 4, "label_every": 2}
        return {name: _plain_options(getattr(self, name)) for name, default in defaults.items()
                if getattr(self, name) != default}
