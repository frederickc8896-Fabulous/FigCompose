"""Demo: grouped bar chart for case vs metric1 by model.

Outputs demo_outputs/charts/bar/demo_plot.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "bar")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_1.csv"))

fig = Figure(data=df, rows=1, cols=1, title="Demo Plot")
fig[0, 0].bar(x="case", y="metric1", group="model", chart_opts={"show_value": True})

fig.render(os.path.join(OUT, "demo_plot.svg"))
print("Done -> demo_outputs/charts/bar/demo_plot.svg")

