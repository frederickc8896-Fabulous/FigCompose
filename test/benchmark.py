"""Full pipeline test: CSV → Figure → SVG.

Reads test/benchmark.csv, builds a 2x2 figure,
renders to SVG and prints a summary.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

# 1. Load data
HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(HERE, "benchmark.csv"))
print(f"Loaded: {len(df)} rows, columns: {list(df.columns)}")
print(df.to_string(), "\n")

# 2. Build figure
fig = Figure(data=df, rows=2, cols=2, theme="general", title="Benchmark Results")
fig[0, 0].bar(x="method", y="accuracy", error="std")
fig[0, 1].bar(x="method", y="accuracy", group="dataset")
fig[1, 0].box(x="method", y="accuracy")
fig[1, 1].bar(x="method", y="f1_score", hline=0.85, hline_label="SOTA")

print(f"Figure: {fig}")

# 3. Build spec
spec = fig.build()
print(f"\nSpec summary:")
print(spec.summary())

# 4. Export SVG
out = os.path.join(HERE, "output_benchmark.svg")
fig.render(out)
print(f"\nSVG exported to {out}")
