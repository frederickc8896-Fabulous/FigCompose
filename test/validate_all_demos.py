"""Quick validation: build all three *_all demos + backward compat."""
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

OK = []

# === backward: old demo without cell_base ===
fig = Figure(data=df, rows=1, cols=1, title="Old Demo")
fig[0, 0].bar(x="case", y="metric1", group="model")
spec = fig.build()
OK.append(f"backward (no cell_base):  canvas={spec.canvas['width']:.0f}x{spec.canvas['height']:.0f}  1x1")

# === BAR 3x3 ===
fig = Figure(data=df, rows=3, cols=3, title="Bar All", cell_base="large")
fig[0, 0].bar(x="case", y="metric1", group="model", title="Grouped Bar")
fig[0, 1].bar(x="case", y="metric1", group="model", title="Horizontal Bar", chart_opts={"horizontal": True})
fig[0, 2].bar(x="case", y="metric1", group="model", title="Stacked Bar", chart_opts={"stacked": True})
fig[1, 0].bar(x="case", y="metric1", group="model", title="Percent Stacked", chart_opts={"stacked": "percent"})
fig[1, 1].bar(x="case", y="metric1", group="model", title="HLine+Mean", chart_opts={"hline": 0.78, "hline_label": "BL", "mean_line": True})
fig[1, 2].bar(x="case", y="metric1", group="model", y2="metric5", title="Dual Y")
fig[2, 0].bar(x="case", y="metric1", group="model", error="metric1", title="Error Bar")
fig[2, 1].bar(x="case", y="metric1", group="model", title="Value Labels", chart_opts={"show_value": True})
fig[2, 2].bar(x="case", y=["metric1", "metric2"], title="Multi-Y Stack", chart_opts={"stacked": True})
spec = fig.build()
cell0 = spec.subplots[0]
fs = cell0.font_sizes
OK.append(f"bar_all  ({spec.n_subplots} subplots)  cell={cell0.w:.0f}x{cell0.h:.0f}  fonts: title={fs['title']:.0f} axis={fs['axis_label']:.0f} tick={fs['tick']:.0f}")

# === LINE 3×3 ===
fig = Figure(data=df, rows=3, cols=3, title="Line All", cell_base="large")
fig[0, 0].line(x="case", y="metric1", group="model", title="Grouped Line")
fig[0, 1].line(x="case", y="metric1", group="model", title="Smooth", chart_opts={"smooth": True})
fig[0, 2].line(x="case", y="metric1", group="model", title="Step", chart_opts={"step": True})
fig[1, 0].line(x="case", y="metric1", group="model", title="Area", chart_opts={"area": True})
fig[1, 1].line(x="case", y="metric1", group="model", y2="metric5", title="Dual Y")
fig[1, 2].line(x="case", y="metric1", group="model", title="No Markers", chart_opts={"markers": False})
fig[2, 0].line(x="case", y="metric1", title="Single Line")
fig[2, 1].line(x="case", y="metric1", group="model", title="Smooth+Area", chart_opts={"smooth": True, "area": True})
fig[2, 2].line(x="model", y="metric1", group="case", title="8 Groups")
spec = fig.build()
cell0 = spec.subplots[0]
fs = cell0.font_sizes
OK.append(f"line_all ({spec.n_subplots} subplots)  cell={cell0.w:.0f}x{cell0.h:.0f}  fonts: title={fs['title']:.0f} axis={fs['axis_label']:.0f} tick={fs['tick']:.0f}")

# === SCATTER 2×3 ===
fig = Figure(data=df, rows=2, cols=3, title="Scatter All", cell_base="large")
fig[0, 0].scatter(x="metric1", y="metric2", group="model", title="Grouped Scatter")
fig[0, 1].scatter(x="metric1", y="metric2", group="model", title="Trend", chart_opts={"trend": True})
fig[0, 2].scatter(x="metric1", y="metric2", group="model", size="score", title="Bubble")
fig[1, 0].scatter(x="metric1", y="metric2", group="model", y2="metric5", title="Dual Y")
fig[1, 1].scatter(x="metric1", y="metric2", group="model", size="score", title="Trend+Bubble", chart_opts={"trend": True})
fig[1, 2].scatter(x="metric1", y="metric2", title="Plain Scatter")
spec = fig.build()
cell0 = spec.subplots[0]
fs = cell0.font_sizes
OK.append(f"scatter_all ({spec.n_subplots} subplots)  cell={cell0.w:.0f}x{cell0.h:.0f}  fonts: title={fs['title']:.0f} axis={fs['axis_label']:.0f} tick={fs['tick']:.0f}")

print("ALL 3 DEMOS BUILD OK:")
for s in OK:
    print(f"  [OK] {s}")
print("\n(Build-only validation; run python demo/run_all.py for Matplotlib exports.)")
