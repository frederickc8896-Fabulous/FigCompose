"""Six-panel fixed-threshold study using the PaperFig pipeline.

Run ``python demo/demo_rejection_rewrite.py``. Data aggregation lives in
rejection_rewrite_data.py; all layout, legends, glyphs and annotations are
rendered by the reusable Figure -> layout -> Matplotlib renderer pipeline.
Default output directory: ``demo_outputs/rejection_rewrite/working_points``.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt

from data_visuals.core import Figure, FigureConfig
from data_visuals.renderer.mpl.canvas import figure_to_matplotlib
from data_visuals.utils.colors import get_palette
from demo.rejection_rewrite_data import BACKBONE_ORDER, TRAINING_ORDER, load_and_summarize

STEM = "rejection_rewrite_working_points"
BACKBONE_LABELS = {"xsmall": "xsmall", "small": "small", "roberta": "RoBERTa"}
ORANGE, BLUE = get_palette(2, "warm").colors
FIGURE_INCHES = (7.0, 4.5)


def build_paper_figure(summary, *, number_rewrites=False):
    """Declare data and scientific marks; the library solves the geometry."""
    points = summary["points"].copy()
    points["rewrite_number"] = points["rewrite_number"].astype(object).where(
        points["rewrite_number"].notna(), None)
    x_upper = math.ceil(max(5.0, float(points["id_false_reject_pct"].max())) * 1.12 * 2) / 2
    config = FigureConfig(
        category_colors={"kind": {"reference": BLUE, "rewrite": ORANGE, "mean": ORANGE}},
        facets={
            "row_labels": list(TRAINING_ORDER),
            "col_labels": [BACKBONE_LABELS[key] for key in BACKBONE_ORDER],
            "xlabel": "Actual ID false rejection (%)",
            "ylabel": "Near-OOD leakage (%)",
            "note": "Reference ID budget: 5% (vertical dashed line)",
            "sharex": True, "sharey": True,
        },
    )
    figure = Figure(
        data=points, rows=2, cols=3, theme="modern", palette="curated-5-default",
        config=config, canvas={"width": FIGURE_INCHES[0], "height": FIGURE_INCHES[1], "unit": "in"},
    )
    styles = {
        "reference": {"marker": "*", "size": 100, "color": BLUE, "edgecolor": "white",
                      "linewidth": 0.5, "zorder": 5, "label": "Reference description"},
        "rewrite": {"marker": "o", "size": 18, "color": ORANGE, "edgecolor": "white",
                    "linewidth": 0.4, "zorder": 4, "label": "Individual rewrites"},
        "mean": {"marker": "D", "size": 35, "color": ORANGE, "facecolor": "none",
                 "edgecolor": ORANGE, "linewidth": 1.1, "zorder": 5, "label": "Mean over rewrites"},
    }
    for row, training in enumerate(TRAINING_ORDER):
        for col, backbone in enumerate(BACKBONE_ORDER):
            panel = points[(points["training"] == training) & (points["backbone"] == backbone)]
            reference = panel[panel["kind"] == "reference"].iloc[0]
            mean = panel[panel["kind"] == "mean"].iloc[0]
            opts = {
                "opacity": 1.0, "series_styles": styles,
                "xlim": [0, x_upper], "ylim": [0, 100],
                "xticks": [0, 2, 4, 6], "yticks": [0, 25, 50, 75, 100],
                "guides": [{"axis": "x", "value": 5, "color": "#b9bec5",
                            "linestyle": "--", "linewidth": 0.7}],
                "arrows": [{"start": [float(reference["id_false_reject_pct"]), float(reference["near_leak_pct"])],
                            "end": [float(mean["id_false_reject_pct"]), float(mean["near_leak_pct"])],
                            "color": ORANGE, "linewidth": 1.0, "mutation_scale": 9,
                            "shrinkA": 6, "shrinkB": 4}],
            }
            if number_rewrites:
                opts["point_labels"] = {"column": "rewrite_number", "fontsize": 8}
            letter = chr(ord("a") + row * 3 + col)
            figure[row, col].scatter(
                x="id_false_reject_pct", y="near_leak_pct", group="kind",
                where={"backbone": backbone, "training": training},
                title=f"({letter})  AUROC: {reference['near_auroc']:.3f} \u2192 {mean['near_auroc']:.3f}",
                chart_opts=opts,
            )
    return figure


def build_figure(summary, *, number_rewrites=False):
    """Return the actual library-rendered figure, with case audit metadata."""
    paper_figure = build_paper_figure(summary, number_rewrites=number_rewrites)
    spec = paper_figure.build()
    figure = figure_to_matplotlib(spec)
    try:
        panels = []
        for key, cell in sorted(figure._data_visuals_layout["cells"].items()):
            ax = cell["axes"]
            data = spec.get_subplot(*key).computed_data
            markers = {artist._data_visuals_series_key: artist for artist in ax.collections
                       if hasattr(artist, "_data_visuals_series_key")}
            panels.append({"axis": ax, "data": data,
                           "reference": data[data["kind"] == "reference"].iloc[0],
                           "mean": data[data["kind"] == "mean"].iloc[0],
                           "markers": [markers[kind] for kind in ("reference", "rewrite", "mean")],
                           "arrow": ax._data_visuals_scatter_arrows[0],
                           "number_labels": cell["point_labels"]["texts"],
                           "number_boxes": cell["point_labels"]["boxes"]})
        figure._rejection_rewrite_panels = panels
        figure._rejection_rewrite_spec = spec
        figure._rejection_rewrite_xlim = figure.axes[0].get_xlim()
        figure.canvas.draw()
        return figure
    except BaseException:
        plt.close(figure)
        raise


def _caption(summary):
    mapping = summary["mapping"]
    reference = summary["points"].loc[summary["points"]["kind"] == "reference"].iloc[0]
    seed_text = ", ".join(str(seed) for seed in summary["metadata"]["seeds"])
    lines = [
        "# Fixed-reference-threshold operating-point shifts",
        "",
        "**Figure caption.** Actual operating points under rejection-description rewrites at a fixed reference threshold. "
        "Columns show xsmall, small, and RoBERTa; rows show Single-phrase and Multi-phrase training. "
        f"Each description marker is the mean over five seeds ({seed_text}). "
        "The eight rewrites share these same trained models. Each rewrite uses the threshold calibrated "
        "under the reference description for the same checkpoint; thresholds are not recalibrated for the rewrites. "
        "The blue star denotes the reference description, orange circles the eight individual rewrites, "
        "and the open orange diamond their overall mean. The mean is calculated by averaging the eight rewrites "
        "within each seed, then averaging over the five seeds. Arrows point from the reference point to this mean. "
        "All panels share the same axis limits. The dashed line marks the 5% reference ID calibration budget; "
        "it does not imply that the actual ID false-rejection rate is 5% in every condition. "
        "The AUROC annotations report the reference mean and the equally weighted rewrite mean to three decimal places. "
        "The main figure omits rewrite numbers to reduce annotation clutter; an optional numbered companion "
        "identifies the same rewrite in all six panels. Only labels are displaced; marker coordinates are never jittered. "
        "Seed uncertainty is reported by paired confidence intervals "
        "in the main text and supplementary appendix, rather than error bars here. "
        "This figure supports inspection of operating-point shifts, description heterogeneity, and residual changes "
        "after training. Actual false-rejection rates can differ between rows; equal-false-rejection comparisons "
        "are supported by the independent diagnostic in §4.2.",
        "",
        "## Rewrite numbering",
        "",
        f"Reference: `{reference['description_id']}` — {reference['description_text']}",
        "",
        "| Number | Description ID | Original wording |",
        "|---|---|---|",
    ]
    for row in mapping.itertuples(index=False):
        lines.append(f"| {int(row.rewrite_number)} | `{row.description_id}` | {row.description_text} |")
    lines.extend([
        "", "## Data and reproduction", "",
        f"- Source: `{Path(summary['metadata']['source_path']).name}`; the manifest records its full path and SHA-256.",
        "- Filter: `score=p_none`, `policy=fixed`, `reference_budget=0.05`, `pool in {REF, OUT}`.",
        "- All 270 selected rows participate: 6 conditions × 5 seeds × (1 reference + 8 rewrites).",
        "- There are 60 plotted markers: 6 × (1 reference + 8 rewrites + 1 derived mean).",
        "- Axes display the supplied percentage columns directly; no additional multiplication by 100.",
        "- The selected CSV values are checked for a common `tau_reference` within each model/seed condition.",
        "- Figure: 7 × 4.5 inches; Times New Roman; all visible text at least 8 pt; editable vector PDF/SVG and 300 DPI PNG.",
        "- Run: `python demo/demo_rejection_rewrite.py`.",
        "- Add `--numbered` to also export the numbered PDF/SVG/PNG companion.",
        "- Uses `Figure → compute → physical layout → Matplotlib renderer → export`. "
        "Per-panel `where`, grouped marker styles, guides, arrows, optional point labels, "
        "and shared facet decorations are reusable library features; this script declares no axes coordinates or margins.",
        "",
    ])
    return "\n".join(lines)


def export_figure(csv_path, output_dir, *, numbered=False):
    summary = load_and_summarize(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_figure = build_paper_figure(summary)
    spec = paper_figure.build()
    x_limits = spec.subplots[0].chart_options["xlim"]
    outputs = []
    for extension in ("pdf", "png", "svg"):
        path = output_dir / f"{STEM}.{extension}"
        paper_figure.render(str(path), dpi=300)
        outputs.append(path)
    if numbered:
        numbered_figure = build_paper_figure(summary, number_rewrites=True)
        for extension in ("pdf", "png", "svg"):
            path = output_dir / f"{STEM}_numbered.{extension}"
            numbered_figure.render(str(path), dpi=300)
            outputs.append(path)
    for key, suffix in (("points", "summary"), ("seed_means", "seed_rewrite_means"), ("mapping", "rewrite_mapping")):
        path = output_dir / f"{STEM}_{suffix}.csv"
        summary[key].to_csv(path, index=False)
        outputs.append(path)
    caption_path = output_dir / f"{STEM}_caption.md"
    caption_path.write_text(_caption(summary), encoding="utf-8")
    outputs.append(caption_path)
    manifest_path = output_dir / f"{STEM}_manifest.json"
    manifest = {**summary["metadata"], "figure_inches": list(FIGURE_INCHES), "png_dpi": 300,
                "font_family": "Times New Roman", "minimum_font_pt": 8,
                "x_limits_pct": list(x_limits), "y_limits_pct": [0, 100],
                "palette": {"reference": BLUE, "rewrites": ORANGE},
                "mean_order": "eight rewrites within each seed, then five seeds",
                "pipeline": "Figure -> compute -> physical layout -> Matplotlib renderer -> export",
                "case_specific_matplotlib_layout": False,
                "numbered_companion": numbered}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    outputs.append(manifest_path)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=PROJECT_ROOT / "rejection_rewrite_plot_data.csv")
    parser.add_argument("--out", type=Path,
                        default=PROJECT_ROOT / "demo_outputs" / "rejection_rewrite" / "working_points")
    parser.add_argument("--numbered", action="store_true", help="Also export a companion with rewrite numbers 1-8")
    args = parser.parse_args()
    for path in export_figure(args.csv, args.out, numbered=args.numbered):
        print(path)


if __name__ == "__main__":
    main()
