"""Per-chart-type smoke test.

Exports one SVG per chart type to test/ output folder.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(HERE, exist_ok=True)

# ── Data ──
df = pd.read_csv(os.path.join(HERE, "benchmark.csv"))

# ── Bar ──
fig = Figure(data=df, rows=1, cols=1, title="Bar Chart")
fig[0, 0].bar(x="method", y="accuracy", error="std")
fig.render(os.path.join(HERE, "chart_bar.svg"))
print("bar OK")

# ── Grouped Bar ──
fig = Figure(data=df, rows=1, cols=1, title="Grouped Bar")
fig[0, 0].bar(x="method", y="accuracy", group="dataset")
fig.render(os.path.join(HERE, "chart_grouped_bar.svg"))
print("grouped bar OK")

# ── Stacked Bar ──
fig = Figure(data=df, rows=1, cols=1, title="Stacked Bar")
fig[0, 0].bar(x="method", y="accuracy", group="dataset", stacked=True)
fig.render(os.path.join(HERE, "chart_stacked_bar.svg"))
print("stacked bar OK")

# ── Bar with hline ──
fig = Figure(data=df, rows=1, cols=1, title="Bar + Baseline")
fig[0, 0].bar(x="method", y="accuracy", error="std", hline=0.85, hline_label="SOTA")
fig.render(os.path.join(HERE, "chart_bar_hline.svg"))
print("bar + hline OK")

# ── Line ──
df2 = pd.DataFrame({
    "epoch": list(range(1, 11)),
    "loss": [0.50, 0.42, 0.38, 0.33, 0.30, 0.27, 0.25, 0.23, 0.21, 0.20],
    "model": ["X"] * 10,
})
fig = Figure(data=df2, rows=1, cols=1, title="Line Chart")
fig[0, 0].line(x="epoch", y="loss")
fig.render(os.path.join(HERE, "chart_line.svg"))
print("line OK")

# ── Line with smooth ──
fig = Figure(data=df2, rows=1, cols=1, title="Smooth Line")
fig[0, 0].line(x="epoch", y="loss", smooth=True)
fig.render(os.path.join(HERE, "chart_line_smooth.svg"))
print("smooth line OK")

# ── Scatter ──
fig = Figure(data=df2, rows=1, cols=1, title="Scatter Chart")
fig[0, 0].scatter(x="epoch", y="loss")
fig.render(os.path.join(HERE, "chart_scatter.svg"))
print("scatter OK")

# ── Box ──
fig = Figure(data=df, rows=1, cols=1, title="Box Plot")
fig[0, 0].box(x="method", y="accuracy")
fig.render(os.path.join(HERE, "chart_box.svg"))
print("box OK")

# ── Heatmap ──
df3 = pd.DataFrame({
    "method_a": ["A", "A", "A", "B", "B", "B", "C", "C", "C"],
    "method_b": ["A", "B", "C", "A", "B", "C", "A", "B", "C"],
    "correlation": [1.0, 0.72, 0.65, 0.72, 1.0, 0.58, 0.65, 0.58, 1.0],
})
fig = Figure(data=df3, rows=1, cols=1, title="Heatmap")
fig[0, 0].heatmap(x="method_a", y="method_b", value="correlation")
fig.render(os.path.join(HERE, "chart_heatmap.svg"))
print("heatmap OK")

print(f"\nAll SVGs in test/ folder: {[f for f in os.listdir(HERE) if f.endswith('.svg')]}")
print("Done.")
