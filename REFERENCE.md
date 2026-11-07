# FigCompose usage reference

[English overview](README.md) · [中文概览](README.zh-CN.md)

This reference is for advanced use and for supplying precise API context to a coding assistant.
Start with the README for installation and a first figure.
The project is in Alpha; the Python import path is `data_visuals`.
FigCompose 0.1.2 includes `circular_bar` and the `curated-8-rose-blue` palette.
Upgrade older installations with `python -m pip install --upgrade FigCompose`.

[Data and chart behavior](#data-and-chart-behavior) · [Paper configuration](#paper-configuration) · [Canvas and axes](#canvas-and-axes) · [Legends](#legends) · [Circular bars](#circular-bars) · [Figure checks](#figure-checks-and-layout-snapshots) · [Custom panels](#custom-matplotlib-panels)

## Data and chart behavior

`plot(data, x=..., group=..., plots=[...])` accepts a DataFrame or a CSV path with a header row.
Each entry in `plots` describes one panel; `cols=2` allows at most two panels per row.
Figure-level `x` and `group` provide defaults; panels can override them, including `group=None`.
CSV reading options go through `csv_options`, for example `{"encoding": "utf-8-sig", "delimiter": ","}`.
`where` filters observations before aggregation.

| Chart | `kind` | Main fields | Default computation |
|---|---|---|---|
| Bar | `bar` | `x`, `metric`, optional `group/error` | Group means; supports error bars and stacking |
| Line | `line` | `x`, `metric`, optional `group` | Mean of repeated X observations |
| Scatter | `scatter` | `x`, `metric`, optional `group/size` | Retains observations; accepts precomputed intervals |
| Box | `box` | `x`, `metric`, optional `group` | Grouped distributions |
| Histogram | `histogram` | `metric`, optional `group` | Binning; optional density and cumulative curves |
| Heatmap | `heatmap` | `x`, `y`, `metric` | Means grouped along two dimensions |
| Confusion matrix | `confusion` | `x`, `y`, optional `metric` | Counts or sums supplied quantities; optional row normalization |
| Pie / donut | `pie` / `donut` | `group`, optional `metric` | Category sums; counts rows if the value column is omitted |
| Radar | `radar` | `x`, `metric`, optional `group` | Mean of repeated observations; at least three complete metric axes |
| Circular bars | `circular_bar` | `x` object ID, `group` metric, `metric` score | Independent score scales; duplicate pairs require explicit aggregation |

`metric` selects Y values for ordinary charts and radar plots, distribution values for histograms,
and quantities or color values for matrix and pie charts.
Pie shares must be finite and nonnegative, with a positive total.
Radar uses long-form data and does not normalize values or fill missing metrics automatically.
Choose the statistical definition and axis ranges appropriate to the scientific question.

## Paper configuration

Pass a `FigureConfig` through `plot(..., config=paper)` or `Figure(config=paper)`.
Save it with `paper.save("paper.yaml")` and restore it with `FigureConfig.load("paper.yaml")`.
JSON and YAML are supported; unknown fields raise errors. Use YAML for numeric dictionary keys;
JSON export rejects configurations whose key types could change.

### Fields

`fields` is keyed by original column names. Each entry accepts `label`, `unit` and `format`.
The original CSV column names and values remain unchanged.

| Setting | Meaning |
|---|---|
| `label` | Axis labels and automatic panel titles |
| `unit` | Appended to the axis label; does not rescale data |
| `format=".0%"` | Displays 0–1 values as percentages |
| `format="{x:.0f}%"` | Adds a percent sign to values already on a 0–100 scale |

Matrix value formats also apply to colorbars and annotations; a local `fmt` overrides only annotations.
Normalized confusion matrices and percentage-stacked charts do not inherit the original value units.
If several metrics on one axis declare incompatible units or formats, override explicitly or separate the axes.

### Series identity

`series` is keyed by the `group` column, for example
`series={"model": [{"id": "base", "label": "Baseline", "marker": "o", "linestyle": "--"}, ...]}`.
Its list order assigns positions in the original palette; optional `color` fixes an explicit color.
Lines, scatter and radar reuse `marker`; lines and radar reuse `linestyle`.
A series missing from another CSV retains its palette position, while legends show only present series.

Register the complete set for the grouping column. Palette capacity includes absent registered series.
When the grouping column is used, unknown IDs, null values and boolean IDs raise errors.
Original IDs and display names are separate; names such as `ours` do not receive automatic styling.
Unused fields and series do not participate in the current figure's computation.

### Overrides and colors

The precedence is theme defaults → paper configuration → figure call → panel `chart_opts`.
Existing `category_colors` override registered colors; panel `series_styles` can override them further.
`plot()` uses `style`; the corresponding configuration field is `FigureConfig.theme`.
Supported styles are `general` and `modern`; `palette` selects colors independently.

Use a complete preset name, such as `curated-5-warm`; `list_color_presets()` lists all names.
The number in the name indicates category capacity. Preset hex values and order are preserved.
`curated-8-rose-blue` has `#D79AB7` as its third swatch and stored main color;
category assignment still follows the original order rather than automatically assigning this color to a named method.
Matrix plots use a continuous scale paired with the preset; override with
`chart_opts={"color_scheme": "blues"}` when needed.

## Canvas and axes

`canvas` describes the entire figure. Its default width is 180 mm; `unit="in"` selects inches.
Omit `height` to measure content and solve height automatically.
`canvas={"width": 180, "height": 110}` fixes both dimensions; content that cannot fit raises `LayoutError`.
Fixed canvases are not silently enlarged and fonts are not silently reduced.
PNG DPI changes pixel density rather than physical dimensions or layout.

Default physical font sizes are 11 pt for the main title, 9 for panel titles, 8 for axis labels,
7 for ticks and 8 for legends. Times New Roman is requested from the operating system;
missing fonts fall back to other serif fonts. Precise cross-device reproduction requires matching fonts and dependencies.

In the current source version, `FigureConfig(font_sizes={"main_title": 16})` overrides
individual roles in pt; supported keys are `main_title`, `title` (panel title),
`axis_label`, `tick` and `legend`. Unspecified roles retain their defaults, including
the legacy sizing path. Save these settings in the same paper YAML/JSON profile.
`legend.fontsize` and panel legend overrides take precedence over `font_sizes.legend`.
Explicit sizes participate in layout measurement; they do not scale with the canvas or DPI.

Bar, line, scatter, box and histogram share these `chart_opts`:

| Option | Example or meaning |
|---|---|
| `xlabel` / `ylabel` | Display labels; an empty string hides the label |
| `xlim` / `ylim` | `[0, 100]`; fixed or reversed limits |
| `xticks` / `yticks` | `[0, 25, 50, 75, 100]`; fixed positions |
| `xticklabels` / `yticklabels` | Display strings matching the corresponding tick count |
| `xformat` / `yformat` | `".2f"`, `".0%"` or `"{x:.0f}%"`; percentage meanings are as above |
| `xscale` / `yscale` | `"linear"`, `"log"`, `"symlog"`; categorical axes remain linear |

Heatmap and confusion allow axis label and tick display overrides while preserving categorical matrix limits.
Radar retains its radial `ylim`. Inapplicable or conflicting settings raise errors.
For horizontal bar and box plots, X/Y refer to the on-screen axes.

Use `FigureConfig(facets={"sharex": True, "sharey": True})` with a complete rectangular grid
for equal plotting areas and shared ranges. Set either flag to `False` for independent ranges.
Explicit `xlim/ylim` remain authoritative; conflicting shared-axis settings raise errors.
Facets cannot be combined with panels spanning multiple cells.
Mixed figures allow matrix colorbars and round-chart external labels to have their own margins.

## Legends

The figure-level `legend` controls scope, position, columns, font size, frame, order and display labels.
Shared legends default to the center below the main title and above the panels.
Use `legend={"scope": "shared", "ncols": 3}` to request a shared legend explicitly.
Other supported shared positions include `bottom`, `left` and `right`.

Panels inherit the figure settings and override them through `chart_opts={"legend": {...}}`.
For example, `chart_opts={"legend": {"position": "upper right"}}` requests a local legend.
`legend=False` hides legends. Font sizes and spacing options such as `gap` use pt.
`legend.order` and `legend.labels` accept original series IDs.

Repeated grouping columns share a legend automatically by default; ungrouped multi-metric plots
share only when `scope="shared"` is explicit. Conflicting shared settings raise errors.
Local positions include inside corners and outside placements. Advanced anchor settings are available
in [the legend configuration](data_visuals/core/legend.py).

## Circular bars

**Available in FigCompose 0.1.2 and later.**
Each object occupies the same ring in every sector. Filled angle encodes a score on an independent scale,
rather than a share of a total. The chart uses the same white canvas, fonts, palettes and series identities as other charts.

```python
import pandas as pd
from data_visuals import plot

data = pd.DataFrame({
    "participant": ["P01", "P02", "P03"] * 4,
    "subject": ["Math"] * 3 + ["English"] * 3 + ["Physics"] * 3 + ["Geography"] * 3,
    "score": [84, 76, 91, 65, 83, 72, 58, 79, 68, 88, 62, 75],
})
fig = plot(
    data,  # Or a long-form CSV with these columns
    x="participant", group="subject",
    plots=[{"kind": "circular_bar", "metric": "score", "summary": "mean", "title": None}],
    canvas={"width": 180}, style="modern", palette="curated-7-warm",
    title="Four subjects, three participant profiles",
)
fig.render("circular_scores.pdf")
fig.render("circular_scores.png", dpi=300)
```

- `value_range=(0, 100)` sets the scale; use `(0, 1)` for proportions. Values are never silently rescaled.
- Each object/metric pair must be present. Missing pairs are rejected; duplicate pairs require explicit `aggregate="mean"`, `"median"` or `"sum"`.
- `summary="mean"` requests unweighted means over per-object scores, calculated before rendering. The default adds no summary.
- `center="count"` shows the unique object count; `center=None` hides it. `order` sets ring order; `rounded=False` uses flat ends.
- Small figures can show fewer object labels while retaining every score and the original physical text size.

## Figure checks and layout snapshots

`fig.check()` measures final text, fonts and plotting areas without adjusting data, fonts, ranges or canvas.
The optional debug image is separate from normal exports.

```python
from pathlib import Path
import pandas as pd
from data_visuals import plot

fig = plot(
    pd.DataFrame({"epoch": [1, 2, 3], "score": [0.70, 0.81, 0.87]}),
    x="epoch", plots=[{"kind": "line", "metric": "score"}],
    canvas={"width": 90}, title="Training progress",
)
report = fig.check(debug="layout_check.png")
print(report.summary())
report.raise_for_errors()  # Optional; include_warnings=True also requires no warnings

baseline = Path("layout_baseline.json")
if baseline.exists():
    comparison = report.compare(baseline, tolerance=0.5)
    print(comparison.summary())
    comparison.save("layout_changes.json")
    assert comparison.ok, comparison.summary()
else:
    report.save(baseline)  # Establish once; later runs compare the existing file
```

- `min_fontsize=7`, `min_tick_gap=1` and `tolerance=1` use pt and can be overridden in `check()`.
  `report.ok` means no errors. Read `report.errors` and `report.warnings` separately.
  Overflow is an error; small fonts, tick and decoration overlap are warnings; font substitution is informational.
  `check(min_fontsize=8)` reports the default 7 pt ticks as warnings.
- Reports include physical canvas size, panel areas, text bounds, resolved fonts and actual styles.
  Debug images mark cells in blue, plotting areas in green and issues in orange/red. PNG / SVG / PDF are supported.
- `report.compare(baseline, tolerance=0.5)` compares physical positions with 0.5 pt geometric tolerance;
  fonts and colors are compared strictly. DPI is ignored. This is a structural comparison, not a pixel comparison.
  Keep baselines and update them explicitly after review. `FigureReport.load(...)` reads a saved report.
- After native edits to `mpl_fig = fig.render()`, use `from data_visuals import check_figure`,
  then `check_figure(mpl_fig)` and finally `plt.close(mpl_fig)`. `fig.check()` closes its own temporary figure.

Plotting-area fraction is a rectangle-allocation measure, not a whitespace or aesthetic score.
Checks do not assess statistical conclusions or overlap between data artists, and do not guarantee
collision-free custom nodes, connections or projected 3D text. Coverage limits are included in reports.

## Custom Matplotlib panels

The advanced `data_visuals.core.Figure` API supports spanning cells, width/height ratios and drawing callbacks.
A fully custom figure requires no CSV or placeholder DataFrame:

```python
from data_visuals.core import Figure, PanelResult

def draw_module(ax, ctx):
    text = ax.text(
        0.5, 0.5, "Encoder", ha="center", va="center",
        bbox={"boxstyle": "round,pad=0.6", "facecolor": ctx.background},
        **ctx.text_kwargs(),
    )
    return PanelResult(artists=[text])

paper = Figure(rows=1, cols=1, canvas={"width": 90}, legend=False)
paper[0, 0].custom(draw_module, min_size=(120, 70), preferred_aspect=2)
paper.render("model.svg")
```

`.custom()` accepts `projection="polar"`, `"3d"` or a registered Matplotlib projection name.
Use `axes_options` for native axes constructor arguments, and `axes="on"` to show axes.
`min_size` uses pt; `box_aspect` is a hard plotting-area width/height constraint;
`preferred_aspect` is an automatic-height preference.

Use `ctx.text_kwargs()` and `ctx.color()` for shared styling. Return measured artists,
legend handles or a `layout(ax, ctx)` size-update callback through `PanelResult`.
The framework manages the whole figure; the callback arranges its internal nodes and connections.
Automatic-size probes and exports rerun callbacks, so they should rebuild without external side effects.
Custom callbacks are runtime objects; Specs containing them cannot be serialized to JSON.

## Source entry points

- [Declarative API](data_visuals/api.py): `plot()` and CSV input.
- [Paper configuration](data_visuals/core/config.py): `FigureConfig`.
- [Advanced Figure](data_visuals/core/figure.py): panel declarations and composition.
- [Panel context and results](data_visuals/core/panel.py): custom drawing lifecycle.
- [Original palettes](data_visuals/utils/colors.py): curated colors and continuous scales.
- [Quality reports](data_visuals/core/quality.py): inspection results.
- [Layout regression](data_visuals/core/regression.py): snapshot comparisons.
