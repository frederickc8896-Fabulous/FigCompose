"""Aligned categorical and numerical cohort tracks, one angle per participant."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from data_visuals.charts import ChartSpec, register_chart
from data_visuals.charts.pie import _plain_options
from data_visuals.compute.participant_tracks import compute_participant_tracks, validate_participant_tracks


@register_chart
@dataclass
class ParticipantTracks(ChartSpec):
    chart_type: ClassVar[str] = "participant_tracks"
    required_fields: ClassVar[list[str]] = ["id", "categorical", "numeric"]
    optional_fields: ClassVar[dict[str, Any]] = {"group": None}

    numeric_ranges: dict | None = None
    numeric_ticks: dict | None = None
    category_orders: dict | None = None
    order_by: str | None = None
    track_labels: dict | None = None
    numeric_colors: dict | None = None
    note: str | None = None
    center_label: str = "participants"
    center_note: str | None = None
    order_label: str | None = None
    center_color: str | None = None
    accent_color: str | None = None

    def _parameters(self):
        return {key: _plain_options(getattr(self, key)) for key in (
            "numeric_ranges", "numeric_ticks", "category_orders", "order_by", "track_labels", "numeric_colors",
            "note", "center_label", "center_note", "order_label", "center_color", "accent_color")}

    def validate(self, df):
        return validate_participant_tracks(df, self.mapping, **self._parameters())

    def compute_requirements(self):
        return {"group_by": [], "columns": {}, "preprocess": [], "statistics": []}

    def compute_data(self, df):
        return compute_participant_tracks(df, self.mapping, **self._parameters())

    def _chart_options(self):
        return self._parameters()
