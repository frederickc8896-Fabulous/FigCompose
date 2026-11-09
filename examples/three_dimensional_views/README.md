# Three paired views / 二维与三维，放在一起看

![Same data in two and three dimensions](preview.png)

Three pairs combine the earlier waterfall, projection-scatter and stacked-bar
introductions into one comparison. Each pair reads the same rows of `data.csv`:

- Profiles: overlay the four continuous signals, then separate them in depth.
- Points: compare their XY projection with three coordinates and wall projections.
- Stacks: flatten nine stacks, then arrange their exact values on a 3 × 3 grid.

The portrait uses a 2:3 width split: compact 2D references on the left and larger
3D views on the right. Filled signal profiles, fine projection stems and the
nine exact stack totals make the relationships visible at a glance. Every stem
runs from a point `(x, y, z)` to `(x, y, 0)`; the other two wall projections repeat
the same observations. The 22 pt heading, 11 pt panel headings and at least 8 pt
ticks are set in the reusable profile, on a 245 × 345 mm white canvas.
Three 245 × 160 mm pairwise slides are exported alongside the six-panel overview:
[signals](profiles/preview.png), [projections](projections/preview.png) and
[stacks](stacks/preview.png). Each slide preserves its exact source rows and domains.

```bash
python -m pip install "FigCompose>=0.3.0"
python examples/three_dimensional_views/generate.py
python examples/three_dimensional_views/generate.py --view projections --out output/projections
```

Use FigCompose 0.3.0 or later for this native 2D/3D comparison.
All six panels now use native FigCompose declarations: `line`, `scatter`, `bar`,
`waterfall3d`, `scatter3d` and `bar3d`. They share one canvas, fonts and preset
colors through the reusable `showcase` style. No callbacks, manual Axes or
Matplotlib drawing code are required by this template.
Copy `examples/_export.py` along with the example; default files are resolved beside
the script, so an absolute script path works from another directory.

The 391 rows are simulated: `view=profile` uses series/x/signal, `view=points`
uses series/x/y/z, and `view=stacks` uses component/group_id/sample/amount/stack.
`style.yaml` fixes series identities using `curated-7-cool`.

The template intentionally fixes common domains for each pair: profiles X 0–8,
signal 0–32; point coordinates 0–10; stack amounts 0–150. It rejects out-of-domain
values rather than silently clipping them. The provided three stack parts must be
present at every grid position.
Stack labels must map one-to-one to group/sample positions. Each of the four
profiles needs exactly one observation per supplied series/position pair.

The native 3D stack renderer submits all 27 cuboids in one `bar3d` call so Matplotlib can
sort their faces together. Splitting the three components into separate collections
can produce incorrect cross-layer occlusion even when the heights are correct.
Original 3D scatter points also share one collection, including per-point marker
shapes and colours, so groups do not receive independent depth orderings.

The native interfaces work with other category counts and numeric domains:

```python
import pandas as pd
from data_visuals import plot

data = pd.read_csv("examples/three_dimensional_views/data.csv")
points = data.loc[data["view"] == "points"]
figure = plot(points, style="showcase", plots=[{
    "kind": "scatter3d", "x": "x", "y": "y", "z": "z", "group": "series",
    "projections": {"z": 0}, "projection_lines": ["z"],
}])
```

Projection planes are always explicit; remove `projections` for measured points
alone. `waterfall3d` requires an explicit `baseline`, uses `x/y/group` and places
series in categorical depth. `bar3d` uses `x/y` category positions and `value`
height; add `group` and `stacked=True` for components. Repeated cells need an
explicit `aggregate`; negative heights and missing grid/components are rejected.
Camera settings are `elev`, `azim`, `box_aspect`, `zoom` and `proj_type`.
All three kinds initially use linear coordinates; field labels, units and numeric
formats follow the same `FigureConfig.fields` and `chart_opts` rules as other kinds.
Optional bar totals are computed in the data layer and attached to the actual
projected tops with physical text offsets, rather than changing their heights.

中文：三维不是额外的数据。瀑布图的纵深只表示系列顺序，墙上的“影子”仍是同一批点，
三维柱图还可能遮住后排。每对图共用原始数值，帮助根据问题选择表达方式。
新版把左侧二维参考与右侧三维主体按2∶3编排；40条投影细线连接原点与其XY投影，
九个柱顶数字是对应三分项的真实总和，填充轮廓与留白只改变呈现。
默认同时导出六格总览与三张独立对照，便于社交平台分图查看细节；`--view`可单独选择。
本例已全部迁为原生声明，三维点的颜色/点形与柱块的深度排序由库统一处理。
导出PNG、SVG和预览；三维深度排序与内部遮挡仍需要人工检查。

[All examples](../README.md) · [FigCompose](../../README.md)
