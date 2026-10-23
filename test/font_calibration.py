"""Font calibration chart — all text elements in one figure.

Generates a single bar chart with:
  - main title
  - subplot title 自动
  - x/y axis labels
  - x/y tick labels
  - legend title + legend labels
  - error bar annotations
  - hline label

Usage: python test/font_calibration.py
Output: test/font_calibration.svg
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

HERE = os.path.dirname(os.path.abspath(__file__))

# Data with enough groups to force legend
df = pd.DataFrame({
    'method':  ['A', 'A', 'A', 'B', 'B', 'B', 'C', 'C', 'C'],
    'dataset': ['ETTh1', 'ETTh2', 'ETTm1'] * 3,
    'accuracy': [0.81, 0.83, 0.79, 0.84, 0.86, 0.82, 0.89, 0.91, 0.87],
    'std':     [0.02, 0.01, 0.03, 0.01, 0.02, 0.02, 0.01, 0.01, 0.01],
})

fig = Figure(
    data=df,
    rows=1, cols=1,
    title="Font Calibration — Main Title (主标题)",

    aspect="16:10",
    base="medium",
)

fig[0, 0].bar(
    x="method",
    y="accuracy",
    error="std",
    group="dataset",
    hline=0.85,
    hline_label="SOTA=0.85",
    title="Table 1",
)

spec = fig.build()

# Print layout-derived font sizes
print("========== Layout Font Sizes (pt) ==========")
fs = spec.subplots[0].font_sizes
print(f"  Subplot title (cell_title) : {fs.get('title', '?')} pt")
print(f"  Axis label  (axis_label)  : {fs.get('axis_label', '?')} pt")
print(f"  Tick label  (tick_label)  : {fs.get('tick', '?')} pt")
print(f"  Legend      (legend)      : {fs.get('legend', '?')} pt")
print(f"  Main title  (main_title)  : {spec.title.get('font_size', '?')} pt")

# Font ratios & limits used
from data_visuals.layout.sizing import DEFAULT_FONT_RATIOS, DEFAULT_LIMITS
print("\n========== Font Ratios ==========")
for k, v in DEFAULT_FONT_RATIOS.items():
    lo, hi = DEFAULT_LIMITS[k]
    print(f"  {k:14s}  ratio={v:.3f}  limits=[{lo}, {hi}]")

print("\n========== Cell Geometry ==========")
sp = spec.subplots[0]
print(f"  Canvas  : {spec.canvas['width']} x {spec.canvas['height']} px")
print(f"  Cell    : {sp.w:.0f} x {sp.h:.0f} px")
print(f"  Gap     : {spec.grid.get('gap', '?')} px")
print(f"  Margins : t={spec.margins['top']:.0f} b={spec.margins['bottom']:.0f} l={spec.margins['left']:.0f} r={spec.margins['right']:.0f}")

# Export
out = os.path.join(HERE, "font_calibration.svg")
fig.render(out)
print(f"\nSVG exported to: {out}")
print("Open this file in a browser or vector editor to inspect font sizes visually.")
