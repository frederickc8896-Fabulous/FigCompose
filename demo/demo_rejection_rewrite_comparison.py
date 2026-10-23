"""Readable before/after projections of the fixed-threshold rewrite study.

The original joint operating-point figure remains in demo_rejection_rewrite.py.
This view separates the two consequences so readers can compare actual rates
and signed changes directly. All geometry and marks use the PaperFig pipeline.
Default output directory: ``demo_outputs/rejection_rewrite/comparison``.
"""
from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from data_visuals.core import Figure, FigureConfig
from demo.demo_rejection_rewrite import BLUE, ORANGE, BACKBONE_LABELS
from demo.rejection_rewrite_data import BACKBONE_ORDER, TRAINING_ORDER, load_and_summarize


STEM = "rejection_rewrite_comparison"
FIGURE_INCHES = (7.0, 4.5)
METRICS = ("id_false_reject_pct", "near_leak_pct")
TRAINING_POSITIONS = {"Single-phrase": 1.0, "Multi-phrase": 0.0}
REWRITE_LANE_OFFSET = -0.16
Y_LIMITS = (-0.5, 1.5)


def comparison_data(summary):
    """Project each unchanged scientific point onto both consequence axes.

    Y encodes training condition only. The small lower lane separates the
    individual descriptions from the reference-to-mean connector, and carries
    no additional numeric meaning or uncertainty estimate.
    """
    frames = []
    for metric in METRICS:
        frame = summary["points"].copy()
        frame["metric"] = metric
        frame["rate_pct"] = frame[metric]
        frame["training_position"] = frame["training"].map(TRAINING_POSITIONS)
        frame.loc[frame["kind"] == "rewrite", "training_position"] += REWRITE_LANE_OFFSET
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def comparison_changes(summary):
    """Retain absolute reference/mean rates as well as their signed deltas."""
    rows = []
    for backbone in BACKBONE_ORDER:
        for training in TRAINING_ORDER:
            panel = summary["points"].loc[
                (summary["points"]["backbone"] == backbone)
                & (summary["points"]["training"] == training)
            ]
            reference = panel.loc[panel["kind"] == "reference"].iloc[0]
            mean = panel.loc[panel["kind"] == "mean"].iloc[0]
            row = {"backbone": backbone, "training": training}
            for metric in (*METRICS, "near_auroc"):
                row[f"{metric}_reference"] = float(reference[metric])
                row[f"{metric}_rewrite_mean"] = float(mean[metric])
                row[f"{metric}_change"] = float(mean[metric] - reference[metric])
            rows.append(row)
    return pd.DataFrame(rows)


def _display_number(value, digits, *, signed=False):
    # Remove arithmetic noise before decimal display rounding, e.g. the
    # five-seed rate 5.175 may be represented as 5.174999999999999.
    number = Decimal(str(round(float(value), 10))).quantize(
        Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return format(number, f"{'+' if signed else ''}.{digits}f").replace("-", "−")


def _rate_annotation(reference, mean, metric):
    digits = 2 if metric == "id_false_reject_pct" else 1
    delta = mean - reference
    return (f"{_display_number(reference, digits)} → {_display_number(mean, digits)}  "
            f"({_display_number(delta, digits, signed=True)} pp)")


def build_comparison(summary):
    """Declare two consequence columns and one row per backbone."""
    display = comparison_data(summary)
    changes = comparison_changes(summary)
    x_upper = math.ceil(max(5.0, float(summary["points"][METRICS[0]].max())) * 1.12 * 2) / 2
    config = FigureConfig(
        category_colors={"kind": {"reference": BLUE, "rewrite": ORANGE, "mean": ORANGE}},
        facets={
            "row_labels": [BACKBONE_LABELS[key] for key in BACKBONE_ORDER],
            "col_labels": ["In-domain inputs rejected", "Near-OOD inputs accepted"],
            "xlabel": "Actual rate (%) · lower is better in both columns",
            "ylabel": "Training",
            "note": "Fixed per-checkpoint threshold · 8 rewrites · 5 seeds · dashed line: 5% reference ID budget",
            "sharex": False, "sharey": True,
        },
    )
    figure = Figure(
        data=display, rows=3, cols=2, theme="modern", palette="curated-5-default", config=config,
        title="Changing the rejection wording shifts acceptance decisions",
        canvas={"width": FIGURE_INCHES[0], "height": FIGURE_INCHES[1], "unit": "in"},
    )
    styles = {
        "reference": {"marker": "*", "size": 70, "color": BLUE, "edgecolor": "white",
                      "linewidth": 0.5, "zorder": 5, "label": "Reference description"},
        "rewrite": {"marker": "o", "size": 9, "color": ORANGE, "facecolor": "none",
                    "edgecolor": ORANGE, "linewidth": 0.6, "zorder": 3, "label": "Individual rewrites"},
        "mean": {"marker": "D", "size": 30, "color": ORANGE, "facecolor": "none",
                 "edgecolor": ORANGE, "linewidth": 1.0, "zorder": 5, "label": "Mean over rewrites"},
    }
    for row, backbone in enumerate(BACKBONE_ORDER):
        for col, metric in enumerate(METRICS):
            arrows, annotations = [], []
            for training, level in TRAINING_POSITIONS.items():
                values = changes.loc[(changes["backbone"] == backbone) & (changes["training"] == training)].iloc[0]
                reference = float(values[f"{metric}_reference"])
                mean = float(values[f"{metric}_rewrite_mean"])
                arrows.append({"start": [reference, level], "end": [mean, level],
                               "color": ORANGE, "linewidth": 1.0, "mutation_scale": 8,
                               "shrinkA": 5, "shrinkB": 3.5})
                annotations.append({"text": _rate_annotation(reference, mean, metric),
                                    "xy": [0.5, (level + 0.31 - Y_LIMITS[0]) / (Y_LIMITS[1] - Y_LIMITS[0])],
                                    "coords": "axes fraction", "fontsize": 8})
            opts = {
                "opacity": 1.0, "series_styles": styles,
                "xlim": [0, x_upper if col == 0 else 100], "ylim": list(Y_LIMITS),
                "xticks": [0, 2, 4, 6] if col == 0 else [0, 25, 50, 75, 100],
                "yticks": [0, 1], "yticklabels": ["Multi-phrase", "Single-phrase"],
                "arrows": arrows, "annotations": annotations,
            }
            if col == 0:
                opts["guides"] = [{"axis": "x", "value": 5, "color": "#b9bec5",
                                   "linestyle": "--", "linewidth": 0.7}]
            figure[row, col].scatter(
                x="rate_pct", y="training_position", group="kind",
                where={"backbone": backbone, "metric": metric}, chart_opts=opts,
            )
    return figure


def _caption(summary, changes):
    lines = [
        "# Reading view: rejection-description changes at a fixed reference threshold", "",
        "**Figure caption.** Columns separate the two consequences of changing rejection wording: "
        "in-domain false rejections (left) and near-OOD leakage, i.e. inputs accepted (right). "
        "Both horizontal axes show actual percentages, with lower values preferred; their ranges differ "
        "between metrics but are fixed across backbones. Rows are backbones; within each panel the "
        "upper track is Single-phrase training and the lower track is Multi-phrase training. "
        "Blue stars are reference descriptions; open orange diamonds are means over eight rewrites. "
        "Arrows and printed values read reference → rewrite mean. Signed changes are in percentage points (pp), "
        "not relative percent changes. Small open orange circles just below each track show all eight "
        "individual rewrite means; coinciding rates may overlap. Their vertical offset distinguishes marker "
        "roles and does not encode another metric or uncertainty. "
        "Each description mean uses five shared seeds; rewrite means first average eight rewrites within "
        "each seed and then average the five seeds. All 270 selected source rows participate. "
        "For each checkpoint, rewrites use its reference-calibrated threshold without recalibration. "
        "The 5% dashed guide appears only in the ID column and denotes the reference calibration budget. "
        "Uncertainty is addressed by paired intervals in the main text and appendix, not by these eight points. "
        "This figure describes operating-point shifts; it does not establish benefits at equal ID false rejection. "
        "Those comparisons remain the separate diagnostic in §4.2.", "",
        "## Observed mean changes", "",
        "Across these backbones, rewrites reduce ID false rejection while increasing near-OOD leakage. "
        "The leakage increases are +34.0–36.4 pp for Single-phrase and +4.2–9.2 pp for Multi-phrase. "
        "Multi-phrase has smaller mean shifts in these data, with residual variation; this statement does "
        "not compare the methods at matched actual false-rejection rates.", "",
        "## Numeric audit and ranking quality", "",
        "AUROC is retained here and in the original joint operating-point figure so it does not compete "
        "with the main reading of decision consequences.", "",
        "| Backbone | Training | ID reference → mean (%) | Δ ID (pp) | Near-OOD reference → mean (%) | Δ Near-OOD (pp) | AUROC reference → mean |",
        "|---|---|---|---|---|---|---|",
    ]
    for values in changes.to_dict(orient="records"):
        lines.append(
            f"| {BACKBONE_LABELS[values['backbone']]} | {values['training']} | "
            f"{_display_number(values['id_false_reject_pct_reference'], 2)} → {_display_number(values['id_false_reject_pct_rewrite_mean'], 2)} | "
            f"{_display_number(values['id_false_reject_pct_change'], 2, signed=True)} | "
            f"{_display_number(values['near_leak_pct_reference'], 1)} → {_display_number(values['near_leak_pct_rewrite_mean'], 1)} | "
            f"{_display_number(values['near_leak_pct_change'], 1, signed=True)} | "
            f"{values['near_auroc_reference']:.3f} → {values['near_auroc_rewrite_mean']:.3f} |")
    lines.extend([
        "", "## Reproduction", "",
        "- `python demo/demo_rejection_rewrite_comparison.py`.",
        "- Full `Figure → compute → physical layout → renderer → export` pipeline; 7 × 4.5 in; "
        "Times New Roman; minimum visible type 8 pt; vector PDF/SVG and 300 DPI PNG.",
        "- 120 displayed markers are two projections of the same 60 scientific points, not additional samples.",
        "- Original joint view: [PDF](../working_points/rejection_rewrite_working_points.pdf); "
        "original wording map: "
        "[CSV](../working_points/rejection_rewrite_working_points_rewrite_mapping.csv).",
        f"- Source SHA-256: `{summary['metadata']['source_sha256']}`.", "",
    ])
    return "\n".join(lines)


def export_comparison(csv_path, output_dir):
    summary = load_and_summarize(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure = build_comparison(summary)
    outputs = []
    for extension in ("pdf", "png", "svg"):
        path = output_dir / f"{STEM}.{extension}"
        figure.render(str(path), dpi=300)
        outputs.append(path)
    changes = comparison_changes(summary)
    path = output_dir / f"{STEM}_changes.csv"
    changes.to_csv(path, index=False)
    outputs.append(path)
    path = output_dir / f"{STEM}_caption.md"
    path.write_text(_caption(summary, changes), encoding="utf-8")
    outputs.append(path)
    path = output_dir / f"{STEM}_manifest.json"
    manifest = {**summary["metadata"], "figure_inches": list(FIGURE_INCHES), "png_dpi": 300,
                "view": "paired actual-rate projections", "scientific_points": 60,
                "displayed_projections": 120, "change_unit": "percentage points",
                "y_encodes": "training condition; rewrite-only lane offset for role separation",
                "rewrite_lane_offset": REWRITE_LANE_OFFSET, "minimum_font_pt": 8,
                "pipeline": "Figure -> compute -> physical layout -> renderer -> export"}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    outputs.append(path)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=PROJECT_ROOT / "rejection_rewrite_plot_data.csv")
    parser.add_argument("--out", type=Path,
                        default=PROJECT_ROOT / "demo_outputs" / "rejection_rewrite" / "comparison")
    args = parser.parse_args()
    for path in export_comparison(args.csv, args.out):
        print(path)


if __name__ == "__main__":
    main()
