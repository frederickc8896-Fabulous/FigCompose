"""Demo: grouped box plot with an overall mean line.

Outputs demo_outputs/charts/box/demo_box_meanline.svg.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "box")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_1.csv"))

METRIC_COLS = ["metric1", "metric2", "metric3", "metric4"]
df_long = df.melt(
    id_vars=["case", "model", "metric5"],
    value_vars=METRIC_COLS,
    var_name="metric_name",
    value_name="metric_value",
)

fig = Figure(data=df_long, rows=1, cols=1, title="Box with Mean Line")
fig[0, 0].box(x="case", y="metric_value", group="model", chart_opts={"mean_line": True, "mean_line_label": "Overall Mean"})

fig.render(os.path.join(OUT, "demo_box_meanline.svg"))
print("Done -> demo_outputs/charts/box/demo_box_meanline.svg")

