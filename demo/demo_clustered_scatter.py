"""Demo: grouped scatter chart for metric1 vs metric2 by model.

Outputs demo_outputs/charts/scatter/demo_scatter.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "scatter")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_1.csv"))

fig = Figure(data=df, rows=1, cols=1, title="Demo Scatter Plot (metric1 vs metric2)")
fig[0, 0].scatter(x="metric1", y="metric2", group="model")

fig.render(os.path.join(OUT, "demo_scatter.svg"))
print("Done -> demo_outputs/charts/scatter/demo_scatter.svg")

