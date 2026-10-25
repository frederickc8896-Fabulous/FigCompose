# FigCompose

<p>
  <img src="https://raw.githubusercontent.com/frederickc8896-Fabulous/FigCompose/main/assets/branding/figcompose-logo-v1.png" alt="FigCompose logo" width="460">
</p>

**English** | [简体中文](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/README.zh-CN.md)

[![PyPI version](https://img.shields.io/pypi/v/FigCompose.svg)](https://pypi.org/project/FigCompose/)
[![Python versions](https://img.shields.io/pypi/pyversions/FigCompose.svg)](https://pypi.org/project/FigCompose/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/LICENSE)

Compose publication figures with Matplotlib.

Choose a CSV, metrics, chart types and a style to produce a figure with consistent layout and colors.
FigCompose manages physical dimensions, font sizes, categorical colors, shared legends and spacing
for the whole figure, reducing repeated style and spacing adjustments when combining chart types.

- **Describe a complete figure**: use a CSV or DataFrame, select metrics, chart types and a style, and arrange one or several panels automatically.
- **Consistent physical layout**: mm / in canvases, fixed font sizes in pt, shared legends and measured margins, with PDF / SVG / PNG export.
- **Reuse settings across a paper**: save fonts, a choice of 12 curated palettes, field display metadata and series identities. When a model is absent from another CSV, the remaining models retain their colors and markers.
- **Measure and compare**: locate overflowing text, tick collisions and font-size issues, then save layout snapshots to check later changes.
- **Extend with native Matplotlib**: 10 built-in chart types can share a figure with custom diagrams, polar plots and 3D plots.

This project is in Alpha; interfaces are still evolving. The project and distribution are named **FigCompose**;
the Python import path remains `data_visuals` for compatibility.

[Quick start](#quick-start) · [Paper configuration](#one-configuration-for-an-entire-paper) · [Chart types](#chart-types-and-aggregation) · [Figure checks](#figure-checks-and-layout-snapshots) · [Custom panels](#custom-matplotlib-panels) · [Color catalog](#color-catalog)

## Gallery

![Common publication charts in FigCompose: grouped bars with standard deviation, lines, scatter, boxes, histogram, heatmap, confusion matrix, donut and radar](https://raw.githubusercontent.com/frederickc8896-Fabulous/FigCompose/main/assets/readme/traditional_charts.png)

All nine panels use FigCompose's declarative API, sharing fonts, method colors and a figure-level legend.
The data are synthetic, generated with a fixed random seed. Pie charts and the variants listed below are also supported.
[Vector image](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/assets/readme/traditional_charts.svg) · [Generation script](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/assets/readme/generate.py)

## Installation

Install the published package from [PyPI](https://pypi.org/project/FigCompose/). Requires Python 3.10+.

```bash
python -m pip install FigCompose
```

The distribution name is `FigCompose`; import it with `from data_visuals import plot`.
Upgrade an existing PyPI installation:

```bash
python -m pip install --upgrade FigCompose
```

To pin the current release for reproducible environments, use `python -m pip install "FigCompose==0.1.1"`.

### Source development

For source development, clone the repository and use an editable install:

```bash
git clone https://github.com/frederickc8896-Fabulous/FigCompose.git
cd FigCompose
python -m pip install -e .
```

To update an existing editable checkout, run these commands from the repository root:

```bash
git pull --ff-only
python -m pip install -e .
```

The default font is **Times New Roman**, supplied by your operating system; other serif fonts are used as fallbacks.
Matching fonts and dependency versions are needed to reproduce layouts precisely across devices.
The current interface is a Python API.

## Quick start

This example runs as written. To use your own data, replace `data` with a CSV path such as
`"results.csv"`; the file should have a header row. Then select the corresponding column names.

```python
import pandas as pd
from data_visuals import plot

data = pd.DataFrame({
    "dataset": ["A", "A", "B", "B"],
    "model": ["Base", "Ours", "Base", "Ours"],
    "accuracy": [0.78, 0.86, 0.81, 0.89],
    "latency": [14.0, 10.0, 15.0, 11.0],
})

fig = plot(
    data,  # Or "results.csv"
    x="dataset", group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy", "title": "(a) Accuracy",
         "chart_opts": {"ylabel": "Accuracy (%)", "yformat": ".0%"}},
        {"kind": "line", "metric": "latency", "title": "(b) Latency",
         "chart_opts": {"ylabel": "Latency (ms)", "yformat": ".0f"}},
    ],
    canvas={"width": 180},
    style="modern", palette="curated-5-warm",
    title="Model comparison",
    legend={"scope": "shared", "ncols": 2},
)
fig.render("figure.pdf")
fig.render("figure.png", dpi=300)
```

- Each entry in `plots` describes one panel; the list length determines the panel count. Use `cols=2` to allow at most two panels per row.
- `x/group` provide default columns that individual panels can override. Set `group=None` in a panel to disable its grouping.
- `canvas` sets the physical size of the entire figure. The default width is 180 mm; omit height to measure the content and solve for height automatically. Use `unit="in"` for inches.
  `{"width": 180, "height": 110}` fixes both dimensions; a layout error is reported if the content cannot fit.
- `style` supports `general` and `modern`; `palette` selects colors independently.
  Import `list_color_presets` from `data_visuals` to list all 12 curated palettes.
- Export to `.pdf`, `.svg` or `.png`. DPI changes PNG pixel density without changing physical dimensions or layout.
- Pass CSV reading settings through `csv_options`, for example `{"encoding": "utf-8-sig", "delimiter": ","}`.

The main entry points are `plot()` to declare content, `FigureConfig` to reuse paper settings,
`fig.render()` to export and `fig.check()` to inspect.
Use `data_visuals.core.Figure` for panels spanning multiple cells, shared-axis grids or native drawing callbacks.

## One configuration for an entire paper

Use the same `FigureConfig` with `plot(..., config=paper)` and the advanced `Figure(config=paper)` API.
Declare fonts, palette, canvas, legends, field display metadata and series identities once;
individual figures can still override the defaults.

```python
import pandas as pd
from data_visuals import FigureConfig, plot

paper = FigureConfig(
    canvas={"width": 180},  # Default unit: mm; height is solved from content
    theme="modern", palette="curated-5-warm",
    font_family="Times New Roman",
    legend={"scope": "shared", "ncols": 3},
    fields={
        "epoch": {"label": "Training epoch", "format": ".0f"},
        "f1": {"label": "F1 score", "unit": "%", "format": ".0%"},
    },
    series={"model": [
        {"id": "base", "label": "Baseline", "marker": "o", "linestyle": "--"},
        {"id": "large", "label": "Large model", "marker": "s", "linestyle": "-."},
        {"id": "ours", "label": "Our method", "marker": "D", "linestyle": "-"},
    ]},
)

data = pd.DataFrame({
    "epoch": [1, 2, 1, 2, 1, 2],
    "model": ["base", "base", "large", "large", "ours", "ours"],
    "f1": [0.70, 0.76, 0.78, 0.83, 0.82, 0.89],
})
for name, frame in [("all", data), ("subset", data[data.model != "base"])]:
    plot(frame, config=paper, x="epoch", group="model",
         plots=[{"kind": "line", "metric": "f1",
                 "chart_opts": {"xticks": [1, 2]}}],
         title="Training comparison").render(f"{name}.pdf")

paper.save("paper.yaml")  # Also supports .yml / .json
restored = FigureConfig.load("paper.yaml")
```

- **Field metadata**: `fields` is keyed by original column names. `label` supplies axis labels and automatic panel titles, `unit` is appended to the axis label, and `format` controls numeric display. CSV column names and values remain unchanged.
  `".0%"` displays 0–1 values as percentages; `"{x:.0f}%"` adds a percent sign to values already on a 0–100 scale. The unit alone does not rescale data.
  Matrix value formats also apply to colorbars and annotations; a local `fmt` overrides only matrix annotations. Normalized confusion matrices and percentage-stacked charts do not inherit the original value units.
- **Series identity**: `series` is keyed by the `group` column. Its list order assigns positions in the original palette; optional `color` fixes an explicit color.
  Lines, scatter and radar plots reuse `marker`; lines and radar plots reuse `linestyle`. A series missing from another CSV keeps its palette position, while legends show only the series present.
  Palette capacity is checked against the complete registered set, including absent series.
  Register the complete set for that column. When the group column is used, unknown IDs, null values and boolean IDs raise errors. Original IDs and display names are stored separately; names such as `ours` do not receive automatic styling.
- **Override order**: theme defaults → paper configuration → figure call → panel `chart_opts`. Existing `category_colors` override registered colors; panel `series_styles` can override them further.
  Legends remain adjustable in position, columns, order and labels. `legend.order/labels` accept original series IDs.
- **Configuration files**: JSON / YAML files are validated on loading; unknown fields raise errors. Use YAML for numeric dictionary keys. JSON export rejects configurations whose key types could change.

A configuration may describe more fields and series than the current CSV contains. Columns unused by the figure do not take part in computation.
If several metrics on one axis declare incompatible units or formats, provide an explicit override or separate axes.
`plot()` selects a style with `style`; the corresponding configuration field is `FigureConfig.theme`.

## Chart types and aggregation

| Chart | `kind` | Main fields | Default behavior and variants |
|---|---|---|---|
| Bar | `bar` | `x`, `metric`, optional `group/error` | Group means; error bars, horizontal bars, stacking and percentage stacking |
| Line | `line` | `x`, `metric`, optional `group` | Mean of repeated X observations; markers, step lines and area fill |
| Scatter | `scatter` | `x`, `metric`, optional `group/size` | Retains observations; bubble sizes and precomputed intervals |
| Box | `box` | `x`, `metric`, optional `group` | Grouped distributions; horizontal boxes and outlier points |
| Histogram | `histogram` | `metric`, optional `group` | Binning, density curves and cumulative distributions |
| Heatmap | `heatmap` | `x`, `y`, `metric` | Means grouped along two dimensions; optional value annotations |
| Confusion matrix | `confusion` | `x`, `y`, optional `metric` | Counts or sums supplied quantities; optional row normalization |
| Pie / donut | `pie` / `donut` | `group`, optional `metric` | Category sums; counts rows when the value column is omitted |
| Radar | `radar` | `x`, `metric`, optional `group` | Mean of repeated observations; at least three complete metric axes |

`metric` selects Y values for ordinary charts and radar plots, distribution values for histograms,
and quantities or color values for matrix and pie charts.
Pie shares must be finite and nonnegative, with a positive total. Radar plots use long-form data;
they do not normalize values or fill missing metrics automatically.

The figure-level `legend` controls shared or local legends, position, columns, font size, frame, order and display labels.
Panels override it through `chart_opts={"legend": {...}}`; `legend=False` hides legends.
Shared legends default to the center below the main title and above the panels; an explicit setting such as `position="bottom"` changes the position.
For example, use `legend={"scope": "shared", "position": "bottom", "ncols": 3, "fontsize": 8}`;
`chart_opts={"legend": {"position": "upper right"}}` gives an individual panel a local legend.
Legend font sizes and spacing options such as `gap` use pt.
Default physical font sizes are 11 pt for the main title, 9 for panel titles, 8 for axis labels,
7 for ticks and 8 for legends, consistent across single-panel and multi-panel figures.

## Axes and compact layout

Bar, line, scatter, box and histogram plots share axis settings in `chart_opts`.
Display labels can differ from CSV column names:

| Option | Example and meaning |
|---|---|
| `xlabel` / `ylabel` | `"Accuracy (%)"`; an empty string hides the axis label |
| `xlim` / `ylim` | `[0, 100]`; fixed limits, including reversed limits |
| `xticks` / `yticks` | `[0, 25, 50, 75, 100]`; fixed tick positions |
| `xticklabels` / `yticklabels` | Display strings matching the number of corresponding ticks |
| `xformat` / `yformat` | `".2f"` for two decimal places; `".0%"` to display 0–1 as percentages; `"{x:.0f}%"` to append a percent sign to 0–100 values |
| `xscale` / `yscale` | `"linear"`, `"log"`, `"symlog"`; categorical axes remain linear |

Heatmaps and confusion matrices allow axis label and tick display overrides while preserving categorical matrix limits.
Radar plots retain their radial `ylim` option. Inapplicable or conflicting axis settings raise errors.
For horizontal bar and box plots, these options refer to the on-screen X/Y axes.

With physical canvases, charts in the same family align their plotting areas. Matrix colorbars and round-chart external labels
use separate margins in mixed figures; `FigureConfig.facets` preserves strictly equal plotting areas for comparison grids.
The layout measures decorations and attempts to reclaim excess margins, falling back to the conservative layout if reclamation fails.
Automatic height considers the actual plotting-area width and height.
Rendering isolates visual settings from external Matplotlib configuration; native callbacks can still explicitly style their own artists.
For comparison grids, use `FigureConfig(facets={"sharex": True, "sharey": True})` with a complete rectangular grid.
Set these options to `False` for independent panel ranges. Explicit `xlim/ylim` remain authoritative;
conflicting settings on shared axes raise errors.

## Figure checks and layout snapshots

`fig.check()` measures final text, fonts and plotting areas without adjusting data, font sizes, axis ranges or canvas size.
It can produce a separate inspection image to locate text overflow, tick overlap, small fonts and related issues:

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
    assert comparison.ok, comparison.summary()  # Optional: stop on layout changes
else:
    report.save(baseline)  # Establish once; later runs compare the existing file
```

- `min_fontsize=7`, `min_tick_gap=1` and `tolerance=1` all use **pt** and can be overridden in `check()`.
  `report.ok` means there are no errors; `report.errors` and `report.warnings` expose errors and warnings separately.
  Overflow is an error; small fonts, tick overlap and decoration overlap are warnings; font substitution is informational.
  To check for a minimum font size of 8 pt, use `check(min_fontsize=8)`; the default 7 pt ticks will then be reported as warnings.
- Reports include the actual canvas, panel plotting areas, text bounds, resolved fonts and colors. Debug images mark cells with blue dashed outlines, plotting areas in green, and issues with orange/red boxes. PNG / SVG / PDF are supported; normal exports have no debug overlays.
- `.compare()` checks recorded physical positions, text, fonts and actual artist styles. The default geometric tolerance is **0.5 pt**; font sizes and colors are compared strictly. DPI is ignored. These are structural layout snapshots rather than pixel screenshot comparisons.
- After native Matplotlib edits using `mpl_fig = fig.render()`, import `check_figure` from `data_visuals` and call `check_figure(mpl_fig)` to inspect the current result. The caller must then close it with `plt.close(mpl_fig)`. `fig.check()` manages and closes its own temporary figure.

Keep baseline files and update them explicitly after review. Check `comparison.ok` to stop subsequent steps when a regression is found.
Use `FigureReport.load("layout_baseline.json")` to read a saved report.

The plotting-area fraction measures allocated rectangles; it is not a whitespace or aesthetic score.
Checks do not assess statistical conclusions or overlap between data artists, and do not guarantee collision-free
diagram nodes, connections or projected 3D text. Coverage limits are recorded in the report.
If the content cannot fit a fixed canvas, a `LayoutError` still reports the size constraints.

## Custom Matplotlib panels

The advanced `data_visuals.core.Figure` API supports panels spanning cells, width/height ratios and native drawing callbacks.
A fully custom figure needs no CSV or placeholder DataFrame:

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
`min_size` uses pt; `box_aspect` is the width/height ratio of the panel's plotting area.

Use `ctx.text_kwargs()` and `ctx.color()` for consistent styling. Return measured artists,
legend handles or a `layout(ax, ctx)` size-update callback through `PanelResult`.
The framework manages the whole figure; the callback arranges its internal nodes and connections.
Automatic-size probes and final exports rerun callbacks, so callbacks should rebuild cleanly without external side effects.
Custom callbacks are runtime objects; Specs containing them cannot be serialized to JSON.

## Project scope

FigCompose manages reusable styles and figure-level layout. Callers choose data columns, statistical definitions,
axis ranges and scientific presentation. Custom drawing callbacks also arrange their internal nodes and connections.

The repository includes library source, themes, installation metadata, Chinese and English READMEs and their gallery assets.
Local demos, outputs, tests, detailed documentation and experimental data are ignored.
The examples above include their own data and run after installing FigCompose.
Regenerate the README images with `python assets/readme/generate.py`.

## License

FigCompose is licensed under the [Apache License 2.0](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/LICENSE).

## Color catalog

### Categorical colors and figure presets

These **12 presets** reference the original combinations in `data_visuals/utils/colors.py`, preserving their hex values and order.
Pass a full name to `plot()`, such as `palette="curated-5-warm"`; `style` controls typography and layout independently.
The numbers 2 / 5 / 7 / 10 indicate category capacity: smaller category sets use the first colors;
choose a larger preset when you exceed the capacity.
Names such as `cool` and `warm` come from the original configuration; refer to the swatches for the actual color balance.

![All 12 FigCompose curated categorical palettes, with preset names and hexadecimal colors](https://raw.githubusercontent.com/frederickc8896-Fabulous/FigCompose/main/assets/readme/color_presets.png)

[Vector catalog](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/assets/readme/color_presets.svg). List every preset name with `list_color_presets()`:

```python
from data_visuals import list_color_presets

print(list_color_presets())
```

### Continuous color scales

Heatmaps and confusion matrices default to the continuous scale paired with the figure's palette.
Override it per panel, for example with `chart_opts={"color_scheme": "blues"}`.
All **5 original scales** appear below; gradients correspond to the original color stops.

![FigCompose continuous scales: warm-cool, coastal, blues, amber and rose, with their original hexadecimal colors](https://raw.githubusercontent.com/frederickc8896-Fabulous/FigCompose/main/assets/readme/color_schemes.png)

[Vector catalog](https://github.com/frederickc8896-Fabulous/FigCompose/blob/main/assets/readme/color_schemes.svg)
