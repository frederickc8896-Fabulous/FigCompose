"""
Demo: 混淆矩阵全功能测试 — 1x2 网格，10×10 分类

测试点:
  (0,0) 原始计数混淆矩阵    (blues)
  (0,1) 行归一化混淆矩阵    (blues)

数据: 人工构造 10×10 分类结果，对角占优
输出到 demo_outputs/charts/confusion/
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data_visuals.core import Figure

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "demo_outputs", "charts", "confusion")
os.makedirs(OUT, exist_ok=True)

# 人工构造 10 类分类结果，对角占优
import numpy as np
np.random.seed(42)
classes = [f"C{i+1}" for i in range(10)]
rows = []
for _ in range(500):
    true_idx = np.random.randint(0, 10)
    # ~70% 正确，~30% 偏向相邻类别（混淆）
    if np.random.random() < 0.7:
        pred_idx = true_idx
    else:
        offset = np.random.choice([-2, -1, 1, 2], p=[0.15, 0.35, 0.35, 0.15])
        pred_idx = min(max(true_idx + offset, 0), 9)
    rows.append({"true_label": classes[true_idx], "pred_label": classes[pred_idx]})
df10 = pd.DataFrame(rows)

fig = Figure(data=df10, rows=1, cols=2,
             title="Confusion Matrix — 10-class",
             aspect="2:1",
             cell_base="large")

fig[0, 0].confusion(x="true_label", y="pred_label",
                    title="Count (raw)",
                    chart_opts={"color_scheme": "blues"})

fig[0, 1].confusion(x="true_label", y="pred_label",
                    title="Row-Normalized",
                    normalize=True, fmt=".2f",
                    chart_opts={"color_scheme": "blues"})

fig.render(os.path.join(OUT, "demo_confusion_all.svg"))
print("Done -> demo_outputs/charts/confusion/demo_confusion_all.svg")
