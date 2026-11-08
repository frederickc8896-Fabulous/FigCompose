"""Shared layout and axis capabilities of built-in chart kinds."""

ROUND_CHARTS = frozenset({"pie", "donut", "radar", "circular_bar", "chord"})
AXISLESS_CHARTS = ROUND_CHARTS - {"radar"}
THREE_D_CHARTS = frozenset({"scatter3d", "waterfall3d", "bar3d"})
DISTRIBUTION_CHARTS = frozenset({"raincloud", "ridgeline"})
PAIRED_CHARTS = frozenset({"paired", "estimation"})
CARTESIAN_CHARTS = frozenset({"bar", "line", "scatter", "box", "histogram"}) | DISTRIBUTION_CHARTS | PAIRED_CHARTS
