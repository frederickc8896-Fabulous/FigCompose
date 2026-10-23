"""Demo: grouped line chart for metric1 by case and model.

Outputs demo_outputs/charts/line/demo_line.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "line")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_1.csv"))

fig = Figure(data=df, rows=1, cols=1, title="Demo Line Plot (metric1 by case)")
fig[0, 0].line(x="case", y="metric1", group="model")

fig.render(os.path.join(OUT, "demo_line.svg"))
print("Done -> demo_outputs/charts/line/demo_line.svg")

