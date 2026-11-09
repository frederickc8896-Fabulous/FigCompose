# FigCompose reference

[English overview](README.md) · [中文概览](README.zh-CN.md) · [Runnable examples](examples/README.md)

Import from `data_visuals`. **FigCompose 0.3.0** provides **22 native kinds**, 13 curated
palettes and the `general`, `modern` and `showcase` styles. Install or upgrade with
`python -m pip install --upgrade "FigCompose>=0.3.0"`.

[Customization](#defaults-and-customization) · [Charts](#data-and-chart-behavior) · [Configuration](#paper-configuration) · [Canvas](#canvas-and-axes) · [Legends](#legends) · [Advanced charts](#advanced-chart-options) · [Checks](#figure-checks-and-layout-snapshots)

## Defaults and customization

The 13 delivered figures are example compositions, not locked appearances.
Native kinds provide drawing and measurement rules; configuration supplies editable defaults.

| Control | Setting |
|---|---|
| Overall style | `plot(style=...)`: `general`, `modern`, `showcase`; config uses `theme` |
| Palette | `palette="curated-5-warm"`; `list_color_presets()` lists presets |
| Individual series colors | `series[group][...].color`, `category_colors`, panel `series_styles` |
| Font and physical sizes | `FigureConfig.font_family` and `font_sizes` |
| Size and composition | `canvas`, `cols`; advanced `Figure` layout and width/height ratios |
| Axes and legends | `chart_opts`, figure `legend` and panel legend overrides |
| Chart-specific appearance | Supported options such as orientation, summaries, markers or 3D camera |

Explicit settings override applicable defaults. Category color precedence is
**palette → `series.color` → `category_colors` → panel `series_styles`**.
All four example profiles pin colors: changing only `palette` will not replace them.
Edit or remove the explicit color entries; for the interval series, check both
`series` and `category_colors`. Explicit fonts, sizes and panel legend settings also override themes.
Some builders specify canvas/layout directly (03, 05, 06); edit those declarations for a different
composition. Internal geometry is governed by each kind's supported options.

## Data and chart behavior

`plot(data, plots=[...], x=..., group=..., cols=2)` accepts a DataFrame or headed CSV.
Each declaration is one panel. Panel fields override figure defaults; `group=None` disables grouping.
`where={"condition": 4}` filters before computation. CSV options go through `csv_options`.

| `kind` | Fields in a plot declaration | Computation / meaning |
|---|---|---|
| `bar` | `x`, `metric`, optional `group/error` | Group means; stacking and error bars |
| `line` | `x`, `metric`, optional `group` | Mean of repeated X observations |
| `scatter` | `x`, `metric`, optional `group/size` | Raw observations; supplied intervals supported |
| `box` | `x`, `metric`, optional `group` | Quartiles, whiskers and outliers |
| `histogram` | `metric`, optional `group` | Bins; optional density/cumulative curves |
| `heatmap` | `x`, `y`, `metric` | Cell means |
| `confusion` | `x`, `y`, optional `metric` | Counts or sums; optional row normalization |
| `pie` / `donut` | `group`, optional `metric` | Sums; counts rows when value is omitted |
| `radar` | `x` metric name, `metric` score, optional `group` | Means; at least three complete axes |
| `circular_bar` | `x` object ID, `group` metric, `metric` score | Independent score scales |
| `chord` | `source`, `target`, `metric` weight | Undirected weighted pairs |
| `raincloud` / `ridgeline` | `x` category, `metric`, optional `group` | KDE and complete observations |
| `paired` / `estimation` | `pair` ID, `x` level, `metric`, optional `group` | Matched observations; see CI contract below |
| `scatter3d` | Explicit `x`, `y`, `z`, optional `group` | Three measured coordinates |
| `waterfall3d` | `x` position, `metric`, `group`, `baseline` | Series index supplies depth |
| `bar3d` | `x`, `y` categories, `metric` amount, optional `group` | Complete grid; explicit stacks |
| `participant_tracks` | `id`, `categorical=[...]`, `numeric=[...]`, `numeric_ranges={...}` | Unique people; 1–3 categorical and 1–2 numeric tracks; descriptive summaries |
| `clustered_heatmap` | `sample`, `traits=[...]`, optional `value_range/n_clusters` | Raw wide matrix; Ward/Euclidean with optimal leaf ordering |
| `alluvial` | `stages=[...]`, `metric` weight | Positive finite complete-path weights; identical paths summed; 2–8 stages |

`metric` maps to `y` for ordinary/value charts, `x` for histograms, and `value` for
matrix, pie, chord, alluvial and 3D-bar charts. Map all three `scatter3d` coordinates explicitly.
Pie values must be finite, nonnegative and have a positive total. Radar does not normalize
scores or fill missing axes. Units, pairing and statistical definitions are never inferred.
Participant numeric ranges are explicit, with optional `numeric_ticks`, `category_orders`,
`order_by` and `track_labels`; `group` names the combined category color domain (default `metadata`).
Clustering uses the supplied traits without standardization or imputation; `value_range` defaults
to `[-1,1]`, `n_clusters=4`, `label_every=2`; `cluster_colors` and `chart_opts.color_scheme` override colors.
Alluvial colors follow the first stage, node percentages divide by total path weight,
`order` sets initial category order (registered `series` supplies the default),
and `stage_titles`/`note` customize annotations. Small weighted nodes that cannot fit
their labels raise `LayoutError`.

## Paper configuration

Save/load a `FigureConfig` as YAML or JSON and reuse it across figures. Register the complete series
domain, including IDs absent from a particular CSV, to preserve colors, markers, line styles and order.

```python
from data_visuals import FigureConfig, plot

paper = FigureConfig(
    theme="showcase", palette="curated-5-warm",
    font_family="Times New Roman", font_sizes={"main_title": 18, "tick": 8},
    canvas={"width": 180},
    series={"method": [
        {"id": "A", "label": "Method A", "color": "#eb5e28", "marker": "o"},
        {"id": "B", "label": "Method B", "color": "#37718e", "marker": "D"},
    ]},
)
paper.save("paper.yaml")  # Restore with FigureConfig.load("paper.yaml")
fig = plot("scores.csv", config=paper, x="dataset", group="method",
           plots=[{"kind": "bar", "metric": "score"}])
fig.render("figure.svg")
```

`fields={"score": {"label": "Accuracy", "unit": "%", "format": ".0%"}}` supplies
display metadata without renaming or rescaling columns. `.0%` multiplies fractions by 100;
`{x:.0f}%` only appends `%`. Conflicting units/formats on a shared axis need an explicit override.
Normalized confusion matrices and percent stacks do not inherit raw value units.

Series palette slots include absent registered IDs. Unknown IDs, nulls and boolean IDs are rejected.
Preset hex values/order are preserved; method names receive no special treatment.
Use YAML for numeric dictionary keys; JSON configuration export rejects ambiguous key conversion.

## Canvas and axes

`canvas` is the whole figure, in mm by default (`unit="in"` is supported).
Default width is 180 mm; omitted height is measured and solved. Fixed width/height cannot silently
grow or shrink fonts: insufficient space raises `LayoutError`. PNG DPI only changes pixel density.

Physical defaults in pt are main title/panel title/axis label/tick/legend:
**11/9/8/7/8** for paper styles, **22/11/9/8/10** for `showcase`.
Override roles through `font_sizes`; explicit legend sizes take priority for legends.
The default font is Times New Roman, with a serif fallback when unavailable.

| Axis option in `chart_opts` | Purpose |
|---|---|
| `xlabel`, `ylabel` | Display titles; `""` hides a title |
| `xlim`, `ylim` | Fixed or reversed ranges |
| `xticks`, `yticks` | Fixed tick positions |
| `xticklabels`, `yticklabels` | Strings matching explicit ticks |
| `xformat`, `yformat` | Numeric formats, including the percentage rules above |
| `xscale`, `yscale` | `linear`, `log`, `symlog` on supported numeric axes |

Options refer to displayed axes, including horizontal plots. Matrix axes allow label/tick overrides;
radar retains radial `ylim`. Native 3D also accepts Z options but requires linear scales.
Unsupported combinations raise errors. Matrix value colors can use `chart_opts.color_scheme`.

`facets` supports complete rectangular grids and shared ranges, not spanning layouts.
Round and native 3D facets require `sharex=False, sharey=False`.
Use advanced `Figure` for spanning cells and explicit composition ratios.

## Legends

`legend={"scope": "shared", "position": "top", "ncols": 3}` requests a shared legend.
The default shared position is below the main title; `bottom/left/right` are also supported.
Repeated grouping fields share automatically; ungrouped multi-metric panels need explicit shared scope.
Panel overrides use `chart_opts={"legend": {...}}`; an explicit panel override defaults to local scope.
`legend=False` hides legends. `fontsize`, `gap` and spacing use pt; `order/labels` accept raw IDs.
Conflicting shared settings raise errors. [All legend fields](data_visuals/core/legend.py).

## Circular bars

The same object occupies the same ring in each sector; filled angle encodes an independent score,
not a share or a radius-comparable arc length. Every object/metric cell is required.
Duplicates need explicit `aggregate="mean"`, `"median"` or `"sum"`.

`value_range=(0,100)` sets the scale without rescaling values. `summary="mean"` explicitly requests
equal-object means; default `None` adds none. `summary_position="auto"` selects top under `showcase`,
inline otherwise; `top/inline` override it. `center=None` hides the count, `order` sets rings,
and `rounded=False` uses flat ends. Small panels may sample ID labels while retaining all scores.
[Native example](examples/circular_scores/README.md).

## Advanced chart options

**Chord.** Weights must be finite and positive; self-links are rejected. Duplicate/reversed pairs
require `aggregate="sum"`. `order` lists all observed nodes; `summary=True` adds counts/total,
and `ticks=False` hides automatic weight ticks. Both endpoints share one angular scale;
incident totals sum to twice the edge total. Register the union of source/target IDs under
the mapped **source column**. [Example](examples/chord_connections/README.md).

**Raincloud/ridgeline.** Defaults: `horizontal=True`, `bandwidth="scott"`,
`normalization="peak"`, `summary="median"`. `order` controls categories; a positive numeric bandwidth
is accepted. `area` normalization uses a common density scale. Each cell needs two varying finite
values. Raincloud offsets are perpendicular to the measured axis; rugs retain every observation.
KDE, quartiles and whiskers are not mean confidence intervals. [Series](examples/intervals/README.md).

**Paired/estimation.** Require an explicit two-level `order`; differences are `order[1]-order[0]`.
Each pair needs one observation at both levels; duplicates/missing pairs are rejected.
Paired paths default to a mean overlay (`summary=None` disables it).
Estimation accepts one group per panel and requires either `lower/upper` columns or
`ci_method="paired_t"` plus explicit `confidence`. Supplied bounds must be constant per group,
contain the mean difference and cannot be combined with computed CI options.
There is no implicit 95% interval. The right axis is `delta = Y - mean(first level)`;
its density describes individual differences and requires variation. Optional `density_range`
must contain all differences and zero. [Original supplied-bound entry](examples/intervals/generate.py).

**3D.** `scatter3d` projection planes are explicit: `projections={"z": 0}` with optional
`projection_lines=["z"]`. `waterfall3d` needs a baseline and at least two X positions per series;
depth is series order, not another measurement. `bar3d` requires nonnegative complete cells;
grouped components require `stacked=True`. Missing cells are not filled with zero.
Duplicates require explicit aggregation. Bar ordering uses `x_order/y_order/group_order`;
`label_totals` and `total_format` control totals. Camera options are `elev/azim/box_aspect/zoom`
and `proj_type="ortho" / "persp"`. [Six-panel and carousel examples](examples/three_dimensional_views/README.md).

## Figure checks and layout snapshots

`report = fig.check(debug="layout.png")` measures final text/layout/style without changing the figure.
Use `report.raise_for_errors(include_warnings=True)` for strict checks and `report.save("layout.json")`
to save evidence. `FigureReport.load(...)` restores it; `report.compare(baseline, tolerance=.5)`
compares structure in pt, not pixels. Establish baselines once and review intentional changes.
After editing a rendered Matplotlib figure, use `check_figure(rendered)` and close it yourself.
Checks do not assess scientific meaning, arbitrary node collisions or 3D occlusion.

## Custom Matplotlib panels

`Figure[row,col].custom(draw, ...)` manages an axes for `draw(ax, context)`; pure custom figures need no data.
Use `context.text_kwargs()` and `context.color()` for consistent styling. Return artists/legend handles
and an optional resize callback through `PanelResult`. `min_size` is pt; `box_aspect` is width/height.
`projection` selects native axes; `axes_options` supplies constructor options.
Sizing/export can rebuild callbacks, so keep them free of external side effects.
Custom callbacks are runtime objects and cannot be serialized as a JSON FigureSpec.

## Source entry points

[API](data_visuals/api.py) · [Configuration](data_visuals/core/config.py) · [Figure](data_visuals/core/figure.py) · [Panel context](data_visuals/core/panel.py) · [Palettes](data_visuals/utils/colors.py) · [Reports](data_visuals/core/quality.py)
