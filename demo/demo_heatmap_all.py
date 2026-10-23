"""Demo: heatmap variants in two canvases.

Figure 1 uses a 2x2 horizontal layout.
Figure 2 flips the axes in a tall layout.
Outputs demo_heatmap_horizontal.svg and demo_heatmap_flipped.svg
under demo_outputs/charts/heatmap/.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from data_visuals.core import Figure


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "heatmap")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

fig1 = Figure(data=df, rows=2, cols=2, title="Heatmap - Horizontal (aspect 16:9)", cell_base="large", aspect="16:9")
fig1[0, 0].heatmap(x="case", y="model", value="metric5", title="blues Scheme", chart_opts={"color_scheme": "blues"})
fig1[0, 1].heatmap(x="case", y="model", value="metric1", title="amber Scheme", chart_opts={"color_scheme": "amber"})
fig1[1, 0].heatmap(x="case", y="model", value="score", title="warm-cool Scheme", chart_opts={"color_scheme": "warm-cool"})
fig1[1, 1].heatmap(x="case", y="model", value="metric2", title="No Annotations (rose)", chart_opts={"annotate": False, "color_scheme": "rose"})
fig1.render(os.path.join(OUT, "demo_heatmap_horizontal.svg"))
print("Done -> demo_outputs/charts/heatmap/demo_heatmap_horizontal.svg")

fig2 = Figure(data=df, rows=1, cols=1, title="Heatmap - Flipped (aspect 9:16)", cell_base="large", aspect="9:16")
fig2[0, 0].heatmap(x="model", y="case", value="metric5", title="Flipped Axes + coastal", chart_opts={"color_scheme": "coastal"})
fig2.render(os.path.join(OUT, "demo_heatmap_flipped.svg"))
print("Done -> demo_outputs/charts/heatmap/demo_heatmap_flipped.svg")

