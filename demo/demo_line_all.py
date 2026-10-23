"""Demo: line-chart variants in a 3x3 grid.

Cases covered:
  (0,0) grouped line
  (0,1) smooth line
  (0,2) step line
  (1,0) area fill
  (1,1) dual y-axis
  (1,2) markers disabled
  (2,0) single line
  (2,1) smooth plus area
  (2,2) many groups

Outputs demo_outputs/charts/line/demo_line_all.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "line")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

fig = Figure(data=df, rows=3, cols=3, title="Line Chart - All Variants", cell_base="large")

fig[0, 0].line(x="case", y="metric1", group="model", title="Grouped Line")
fig[0, 1].line(x="case", y="metric1", group="model", title="Smooth Line", chart_opts={"smooth": True})
fig[0, 2].line(x="case", y="metric1", group="model", title="Step Line", chart_opts={"step": True})

fig[1, 0].line(x="case", y="metric1", group="model", title="Area Fill", chart_opts={"area": True})
fig[1, 1].line(x="case", y="metric1", group="model", y2="metric5", title="Dual Y-Axis (y2)")
fig[1, 2].line(x="case", y="metric1", group="model", title="No Markers", chart_opts={"markers": False})

fig[2, 0].line(x="case", y="metric1", title="Single Line")
fig[2, 1].line(x="case", y="metric1", group="model", title="Smooth + Area", chart_opts={"smooth": True, "area": True})
fig[2, 2].line(x="model", y="metric1", group="case", title="8 Groups (case)")

fig.render(os.path.join(OUT, "demo_line_all.svg"))
print("Done -> demo_outputs/charts/line/demo_line_all.svg")

