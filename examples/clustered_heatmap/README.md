# Circular clustered heatmap / 环形聚类热图

![Circular Ward clustering](preview.png)

A native `clustered_heatmap` chart: the same sample order connects a genuine
Ward dendrogram, nine signed-value tracks and a four-cluster annotation ring.
The opening explains the scale; every second sample label is shown at readable size.

```bash
python -m pip install "FigCompose>=0.3.0"
python examples/clustered_heatmap/generate.py
python examples/clustered_heatmap/generate.py --data my_matrix.csv --out output/clusters
```

Download/clone the repository first. Keep `examples/_export.py` when copying the example.
The script resolves its default inputs beside itself and works from any working directory.

`data.csv` has a first column `sample` containing unique IDs; every other column is
a numerical trait. The supplied data are 32 × 9 simulated signed scores in [-1, 1].
At least eight rows, three traits and two distinct profiles are required. Missing and nonfinite values are rejected.
Use meaningful, comparable scales first; the chart preserves raw input values.

Clustering is recomputed from the CSV using SciPy Ward linkage with Euclidean distances
and optimal leaf ordering. Merge distances are preserved radially. The thin outer track
shows clusters cut from that same tree with `n_clusters=4` as the maximum requested count.
This annotation has its own categorical scale.

The native entry point is `figure[0, 0].clustered_heatmap(sample="sample",
traits=["V1", "V2", "V3"], value_range=(-1, 1), n_clusters=4, label_every=2)`.
`traits` fixes the inner-to-outer order; `value_range` fixes the colour scale;
`label_every` controls sample-label density. The complete matrix is always retained.
`chart_opts={"cluster_colors": ["#123456", "#56789a", "#9abcde", "#cdef01"]}`
overrides the cluster annotation and tree colours; `chart_opts.color_scheme` overrides
the continuous trait scale independently.
The chart computes Ward linkage with Euclidean distances and optimal leaf ordering,
without z-score transformation or imputation. Its FigureSpec supports strict JSON.
This native entry point is included in FigCompose 0.3.0 and later.

`style.yaml` reuses `curated-10-muted`; categorical cluster accents and the signed
continuous scale are derived from it. A preview, 300 dpi PNG and SVG are exported on white.
Times New Roman is requested from the system, with a serif fallback when unavailable.

中文：这是可直接换 CSV 的原生图种。沿角度读样本、沿半径读指标；中央是真实聚类树。
颜色的零点具有数据含义，不能仅为好看任意移动。相似的样本相邻并不自动构成统计结论。

[All examples](../README.md) · [FigCompose](../../README.md)
