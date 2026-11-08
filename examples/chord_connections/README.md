# Weighted chord diagram / 加权弦图

This example uses FigCompose's native **`kind="chord"`** with the `showcase` style.
The synthetic example connects six research domains. Each CSV row is one undirected pair.

```bash
# Install FigCompose and run the example from the repository root:
python -m pip install "FigCompose>=0.2.0"
python examples/chord_connections/generate.py
```

Use your CSV without editing geometry:

```bash
python examples/chord_connections/generate.py --data connections.csv --out my_figure
```

| Column | Meaning |
|---|---|
| `source`, `target` | Group names; each undirected pair occurs once |
| `value` | Finite positive connection weight |

The same chart can be declared directly:

```python
from data_visuals import plot

figure = plot("connections.csv", plots=[{
    "kind": "chord", "source": "source", "target": "target", "value": "value",
    "summary": True,
}], style="showcase", canvas={"width": 210})
figure.render("connections.png")
```

`summary=False` is the default; `True` adds group count, unique undirected-pair
count and total weight. `ticks=True` chooses a bounded number of nice weight
ticks according to the rendered physical size. `order` may explicitly declare
every observed node. Without it, node and edge order are stable across CSV row
permutations and reversing the two endpoints.

The angular width of **both** ribbon endpoints is proportional to `value`, using one scale throughout.
Each group's outer arc equals the sum of its incident connections, so all group totals sum to twice the edge total.
The edge total is a sum of pair weights, not necessarily a count of unique individuals or records.
The line through a ribbon does not encode geographical distance, direction or causality.
Colors help trace one endpoint; they do not establish a flow direction.
At least two distinct nodes are required. Self-links are rejected. Duplicate
undirected pairs are rejected unless `aggregate="sum"` explicitly adds them.
Totals must remain finite; changing the weight unit explicitly is required if
their sum exceeds floating-point range.
The diagram uses direct group labels instead of repeating the same names in a legend.
The 21 pt headline, 13 pt group labels and 29 pt summary figures create a clear reading
order at social-media sizes. Each outer arc has a narrow inner band split into the
original endpoint spans, while short outer ticks use an automatic common weight
interval. These marks use the same value-to-angle scale as the ribbons.
The three summary figures report group count, undirected pair count and total pair
weight; the group incident totals still sum to twice that last quantity.
Ribbons retain their original endpoint geometry and category colors. Stronger fill
and white boundaries make their crossings easier to trace without covering the center.
FigCompose measures the height at a fixed width of 210 mm, with equal coordinate
scales. Labels use measured radial placement or two spaced columns for dense
domains and long names; fonts are not shrunk to make them fit.
The native chord and `showcase` style are available in FigCompose 0.2.0 and later.

中文：修改 `data.csv` 中的对象对及权重即可复用。外侧弧长表示该组关联权重之和，弦两端的角宽共同表示同一权重。
这是原生 `chord` 无向关联图，不能把弦的颜色或空间位置当作因果或流向。外侧刻度间隔按数据和物理尺寸自动选择，内侧细环分片对应原连接端点。
新版以直标、大字号总量和更清晰的交叠弦带突出阅读层级；6组、15对、总权重308，关联总量616的口径保持不变。所有数据均为模拟数据。

普通调用只需字段映射；`style="showcase"` 选择展示风格，`summary=True` 显式增加数据摘要。
标签按最终物理尺寸测量，长标签和较多节点使用分列布局；不剔除小节点或改写端点宽度。
重复无向对象对默认拒绝，只有显式 `aggregate="sum"` 才合并。

`style.yaml` uses `showcase`, Times New Roman and `curated-10-vibrant`. Its `series.source`
registers the original node order and six exact colors across both endpoint columns.
Times New Roman must be installed locally; otherwise a serif fallback is used.
The script reads paths relative to its own directory, works from another current directory, and exports `figure.png` (300 dpi), `figure.svg` and `preview.png`.
Keep `examples/_export.py` when copying this example. [All examples](../README.md).

![Weighted chord diagram](preview.png)
