"""Shared layout and axis capabilities of built-in chart kinds."""

ROUND_CHARTS = frozenset({"pie", "donut", "radar", "circular_bar", "chord", "clustered_heatmap", "participant_tracks"})
AXISLESS_CHARTS = ROUND_CHARTS - {"radar"}
DIAGRAM_CHARTS = frozenset({"alluvial"})
AXISLESS_CHARTS = AXISLESS_CHARTS | DIAGRAM_CHARTS
THREE_D_CHARTS = frozenset({"scatter3d", "waterfall3d", "bar3d"})
DISTRIBUTION_CHARTS = frozenset({"raincloud", "ridgeline"})
PAIRED_CHARTS = frozenset({"paired", "estimation"})
CARTESIAN_CHARTS = frozenset({"bar", "line", "scatter", "box", "histogram"}) | DISTRIBUTION_CHARTS | PAIRED_CHARTS
