"""Demo: scatter-chart variants in a 2x3 grid.

Cases covered:
  (0,0) grouped scatter
  (0,1) grouped scatter with trend line
  (0,2) grouped scatter repeat
  (1,0) dual y-axis
  (1,1) grouped scatter with trend line
  (1,2) plain scatter

Outputs demo_outputs/charts/scatter/demo_scatter_all.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "scatter")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

fig = Figure(data=df, rows=2, cols=3, title="Scatter Chart - All Variants", cell_base="large")

fig[0, 0].scatter(x="metric1", y="metric2", group="model", title="Grouped Scatter")
fig[0, 1].scatter(x="metric1", y="metric2", group="model", title="Trend Line", chart_opts={"trend": True})
fig[0, 2].scatter(x="metric1", y="metric2", group="model", title="Grouped Scatter (Repeat)")

fig[1, 0].scatter(x="metric1", y="metric2", group="model", y2="metric5", title="Dual Y-Axis (y2)")
fig[1, 1].scatter(x="metric1", y="metric2", group="model", title="Trend + Group", chart_opts={"trend": True})
fig[1, 2].scatter(x="metric1", y="metric2", title="Plain Scatter")

fig.render(os.path.join(OUT, "demo_scatter_all.svg"))
print("Done -> demo_outputs/charts/scatter/demo_scatter_all.svg")

