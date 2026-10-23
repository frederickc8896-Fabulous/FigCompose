"""
Demo: 直方图 & 密度曲线全功能测试 — 2x3 网格

测试点:
  (0,0) 基础直方图           bins=20
  (0,1) 密度曲线              density=True
  (0,2) 分组密度曲线          density=True + group=model
  (1,0) 直方图指定 bins       bins=10
  (1,1) 累积分布图            cumulative=True
  (1,2) 不同列                x=metric2

输出到 demo_outputs/charts/histogram/
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "histogram")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(os.path.join(PROJ, "mock_data", "mock_2.csv"))

fig = Figure(data=df, rows=2, cols=3,
             title="Histogram & Density — All Variants",
             cell_base="large")

fig[0, 0].histogram(x="metric1",
                    title="Histogram (bins=20)")
fig[0, 1].histogram(x="metric1",
                    title="Density (KDE)",
                    density=True)
fig[0, 2].histogram(x="metric1", group="model",
                    title="Density by Model",
                    density=True)
fig[1, 0].histogram(x="metric1",
                    title="Histogram (bins=10)",
                    bins=10)
fig[1, 1].histogram(x="metric1",
                    title="Cumulative",
                    cumulative=True)
fig[1, 2].histogram(x="metric2",
                    title="metric2 Histogram")

fig.render(os.path.join(OUT, "demo_histogram_all.svg"))
print("Done -> demo_outputs/charts/histogram/demo_histogram_all.svg")
