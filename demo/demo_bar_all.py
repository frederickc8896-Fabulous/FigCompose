"""Demo: bar-chart variants in a 3x3 grid.

Cases covered:
  (0,0) grouped bar
  (0,1) horizontal bar
  (0,2) stacked bar
  (1,0) percent stacked bar
  (1,1) reference line plus mean line
  (1,2) dual y-axis
  (2,0) error bars
  (2,1) value labels
  (2,2) multi-y stacked bar

Outputs demo_outputs/charts/bar/demo_bar_all.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "bar")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

fig = Figure(data=df, rows=3, cols=3, title="Bar Chart - All Variants", cell_base="large")

fig[0, 0].bar(x="case", y="metric1", group="model", title="Grouped Bar")
fig[0, 1].bar(x="case", y="metric1", group="model", title="Horizontal Bar", chart_opts={"horizontal": True})
fig[0, 2].bar(x="case", y="metric1", group="model", title="Stacked Bar", chart_opts={"stacked": True})

fig[1, 0].bar(x="case", y="metric1", group="model", title="Percent Stacked", chart_opts={"stacked": "percent"})
fig[1, 1].bar(x="case", y="metric1", group="model", title="HLine + Mean Line", chart_opts={"hline": 0.78, "mean_line": True, "mean_line_label": "Mean"})
fig[1, 2].bar(x="case", y="metric1", group="model", y2="metric5", title="Dual Y-Axis (y2)")

fig[2, 0].bar(x="case", y="metric1", group="model", error="metric1", title="Error Bars (std)")
fig[2, 1].bar(x="case", y="metric1", group="model", title="Value Labels", chart_opts={"show_value": True, "value_format": ".2f"})
fig[2, 2].bar(x="case", y=["metric1", "metric2"], title="Multi-Y Stacked", chart_opts={"stacked": True})

fig.render(os.path.join(OUT, "demo_bar_all.svg"))
print("Done -> demo_outputs/charts/bar/demo_bar_all.svg")

