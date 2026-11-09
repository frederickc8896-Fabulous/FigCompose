# Five-stage alluvial paths / 五阶段复杂平行流图

**1,200 simulated participants · 5 stages · 5 categories · 60 complete paths.**
The single flow panel contains 25 nodes and 240 ribbons between adjacent stages.
FigCompose manages the canvas, physical typography, top shared legend and export.
FigCompose 0.3.0 provides the native `alluvial` kind with serializable computed
paths and stage marginals.

```bash
python -m pip install "FigCompose>=0.3.0"
python examples/alluvial_flows/generate.py
python examples/alluvial_flows/generate.py --data paths.csv --out my_figure
```

The default CSV has the following columns. Each row gives an entire observed route
and the number of simulated participants following it.

| Column | Stage |
|---|---|
| `entry` | Initial choice |
| `explore` | Exploration |
| `trial` | First trial |
| `decision` | Reassessment |
| `outcome` | Final choice |
| `count` | Positive integer participant count |

The generator reads 2–8 stage columns followed by `count`.
Stage order follows the CSV header. Repeated identical complete paths are
summed before drawing. All path labels must be nonempty strings.

Node heights and ribbon widths share **one people-to-height scale** across all stages.
Each path occupies exactly the same height at every stage. The five columns each total
1,200 people. Node labels show the current category, its count and its share of the cohort.
Colors identify the initial category throughout the entire path; both edges of each
node show the initial-category composition in its actual path slots.

At each node, paths are ordered by initial category, neighboring category and the full
route. Thin white boundaries separate individual routes. The existing
`curated-5-default` colors remain in their original order:
`#e63946 / #fedfd4 / #94d2bd / #0077b6 / #1d3557`.

The white canvas is 320 × 220 mm, with Times New Roman, a 23 pt main title and
text of at least 9.5 pt. `figure.png` is 300 dpi; `figure.svg` is vector;
`preview.png` is 120 dpi. Keep `examples/_export.py` when copying the example.
The native declaration is `figure[0, 0].alluvial(stages=[...], value="count")`;
`plot()` also accepts `kind="alluvial"`, `stages=[...]`, `metric="count"`.
The native kind supports positive real weights and finite string/numeric category IDs;
this participant-count example requires positive integer counts and string labels.

## Rebuild the synthetic data

```bash
python examples/alluvial_flows/simulate.py
python examples/alluvial_flows/simulate.py --participants 1800 --seed 20261109 --out paths.csv
```

`simulate.py` uses the Python standard library and seed `20261109`. Twelve route motifs
per initial category cover stable choices, gradual switches, returns and multi-step
exploration. Weighted integer counts allocate exactly 1,200 people across 60 routes;
individual route counts range from 8 to 53. Re-running the default command reproduces
the same CSV bytes.

The original 300-person, 17-path input is retained in `data_three_stage.csv`:

```bash
python examples/alluvial_flows/generate.py --data examples/alluvial_flows/data_three_stage.csv --out three_stage
```

中文：默认图把五个阶段排在同一幅流图中，60条完整路径在相邻阶段间形成240段流带。
每阶段合计1200人，颜色全程追踪初始类别；节点旁的比例以全队列人数为分母。
适合队列分组变化、偏好迁移和多阶段用户路径。全部数据可由固定种子重新生成。

[All examples](../README.md)

![Five-stage conserved alluvial paths](preview.png)
