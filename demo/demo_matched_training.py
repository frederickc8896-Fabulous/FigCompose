"""Single-column matched-ID training differences using reusable components.

Defaults to demo_outputs/matched_training/. The input CSV already supplies
paired-seed bootstrap intervals; this script never recomputes them.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from PIL import Image

from data_visuals.core import Figure, FigureConfig
from data_visuals.utils.colors import get_palette
from demo.matched_training_data import BACKBONE_ORDER, PANEL_ORDER, load_matched_training_data


STEM = "matched_training_single_column"
TITLE = "Training gains at matched ID rejection"
# Match the provided 1020 x 1335, 300-DPI reference exactly for visual comparison.
FIGURE_INCHES = (3.4, 4.45)
Y_LIMITS = (-15.5, 3.0)
X_LIMITS = (0.0, 10.5)
BASE_LABELS = {"xsmall": "xsmall", "small": "small", "roberta": "RoBERTa"}
_CURATED = get_palette(5, "warm").colors
COLORS = dict(zip(BACKBONE_ORDER, (_CURATED[4], _CURATED[0], _CURATED[3])))
MARKERS = dict(zip(BACKBONE_ORDER, ("o", "s", "^")))
OFFSETS_PT = dict(zip(BACKBONE_ORDER, (-4.0, 0.0, 4.0)))
LEGEND = {"position": "bottom", "ncols": 3, "fontsize": 8, "gap": 6}


def _node_label(value):
    return str(Decimal(str(round(value, 10))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_matched_training(study):
    """Declare two panels, three series, and the supplied absolute CI bounds."""
    styles = {
        name: {"marker": MARKERS[name], "size": 18 if name == "roberta" else 15,
               "color": COLORS[name], "edgecolor": "white", "linewidth": 0.4,
               "label": BASE_LABELS[name], "zorder": 4}
        for name in BACKBONE_ORDER
    }
    figure = Figure(
        data=study["data"], rows=2, cols=1, theme="modern", palette="curated-5-warm",
        title=TITLE,
        canvas={"width": FIGURE_INCHES[0], "height": FIGURE_INCHES[1], "unit": "in"},
        legend=LEGEND,
        config=FigureConfig(
            category_colors={"backbone": COLORS},
            facets={
                "sharex": True, "sharey": True,
                "xlabel": "Actual ID false rejection (%)",
                "ylabel": "Leakage difference (pp)",
                "note": "Multi-phrase − Single-phrase; negative favors Multi\n"
                        "Test-ID diagnostic · 5 paired seeds · 95% bootstrap CIs",
            },
        ),
    )
    for row, panel in enumerate(PANEL_ORDER):
        figure[row, 0].scatter(
            x="actual_id_false_reject_pct", y="delta_leakage_pp", group="backbone",
            where={"panel": panel}, title="(a) Near-OOD" if row == 0 else "(b) Far-OOD",
            chart_opts={
                "opacity": 1.0, "series_styles": styles, "x_offsets": OFFSETS_PT,
                "errorbar": {"lower": "ci95_lower_pp", "upper": "ci95_upper_pp",
                             "capsize": 1.5, "linewidth": 0.8, "alpha": 0.85},
                "xlim": list(X_LIMITS), "ylim": list(Y_LIMITS),
                "xticks": study["nodes"], "xticklabels": [_node_label(node) for node in study["nodes"]],
                "yticks": [-15, -10, -5, 0],
                "guides": [{"axis": "y", "value": 0, "linestyle": "--",
                            "color": "#737d87", "linewidth": 0.85}],
            },
        )
    return figure


def _caption(study):
    return "\n".join([
        "# Matched-ID training differences", "",
        "**Figure caption.** Leakage differences between Multi-phrase and Single-phrase training "
        "at matched actual ID false-rejection rates, for (a) near-OOD and (b) far-OOD. "
        "Negative values favor Multi-phrase. Each panel shows three backbones at four matched nodes "
        "(0.875%, 1.875%, 4.875%, and 9.875%), for 12 estimates and intervals per panel. "
        "Colors and marker shapes identify the same backbone in both panels. "
        "Intervals are the supplied 95% paired-seed bootstrap CIs, based on five paired seeds "
        "and 5,000 replicates, for the eight OUT descriptions with score=p_none and policy=test_id_oracle. "
        "All 24 source rows and their asymmetric interval endpoints are retained without recalculation. "
        "The Test-ID oracle diagnostic is separate from the fixed-reference-threshold rewrite experiment. "
        "All point estimates are negative, but two near-OOD intervals and one far-OOD interval contain zero; "
        "the figure therefore does not establish a nonzero effect in every condition.", "",
        "## Axis and rendering choices", "",
        "- The two panels share actual numeric X positions and identical Y limits, with a zero guide.",
        "- The four nodes are not equally spaced. Groups are offset by −4, 0, and +4 physical points "
        "only for legibility; markers and intervals use the same transform, and numeric source X values are unchanged.",
        "- Tick text is rounded to two decimals to keep the nearby first two nodes legible; tick coordinates "
        "and the exact three-decimal node values stated above remain unchanged.",
        "- Only the lower panel shows the shared X-axis labels; a single legend appears below them.",
        "- The canvas matches the supplied reference: 3.4 × 4.45 inches (86.36 × 113.03 mm), "
        "1020 × 1335 pixels at 300 DPI. Text uses Times New Roman at 8 pt or larger.",
        "- Uses the existing Figure/scatter/facets/style/guide/export pipeline, with reusable asymmetric "
        "scatter intervals and a measured bottom shared legend. No axes positions are set in this demo.", "",
        "## Reproduction and provenance", "",
        "`python demo/demo_matched_training.py`", "",
        f"Input CSV SHA-256: `{study['metadata']['source_sha256']}`.", "",
        "The original JSON path and checksum are provenance declarations in the CSV. "
        "The original JSON and paired seed observations were not supplied, so the bootstrap procedure "
        "is not independently reconstructed here.", "",
    ])


def export_visual_comparison(reference, generated, output):
    """Review sheet only: place both unchanged PNGs at the same displayed size."""
    with matplotlib.rc_context({"font.family": "Times New Roman", "savefig.bbox": None}):
        figure, axes = plt.subplots(1, 2, figsize=(6.8, 4.75), dpi=180)
        try:
            figure.subplots_adjust(left=0, right=1, bottom=0, top=4.45 / 4.75, wspace=0)
            for ax, path in zip(axes, (reference, generated)):
                ax.imshow(mpimg.imread(path))
                ax.set_axis_off()
            figure.text(0.25, 0.97, "Provided reference", ha="center", va="top", fontsize=10)
            figure.text(0.75, 0.97, "PaperFig · same canvas size", ha="center", va="top", fontsize=10)
            figure.savefig(output, dpi=180, bbox_inches=None, facecolor="white")
        finally:
            plt.close(figure)


def _reference_axes_fraction(reference):
    """Estimate only axes area from the supplied raster's two black spines.

    This is a geometric review measurement, not a score for aesthetic quality.
    If a different reference has no detectable paired spines, omit the estimate.
    """
    with Image.open(reference) as source:
        pixels = np.asarray(source.convert("RGB"))
    height, width = pixels.shape[:2]
    dark = (pixels < 80).all(axis=2)

    def runs(mask):
        indices = np.flatnonzero(mask)
        return [(int(part[0]), int(part[-1])) for part in
                np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1) if len(part)]

    baselines = []
    for y, row in enumerate(dark):
        for left, right in runs(row):
            if right - left > width * 0.6:
                if baselines and y <= baselines[-1][0] + 3:
                    continue
                baselines.append((y, left, right))
    if len(baselines) != 2:
        return None
    rectangles = []
    for bottom, left, right in baselines:
        candidates = [(end - start, x, start, end)
                      for x in range(max(0, left - 2), min(width, left + 3))
                      for start, end in runs(dark[:, x])
                      if abs(end - bottom) <= 5 and end - start > height * 0.15]
        if not candidates:
            return None
        _, x, top, end = max(candidates)
        rectangles.append({"x": x, "y": top, "width": right - x, "height": end - top})
    return {"axes_fraction": sum(rect["width"] * rect["height"] for rect in rectangles) / (width * height),
            "method": "estimated from the two long black axes spines in the supplied PNG",
            "axes_rectangles_px": rectangles, "image_pixels": [width, height]}


def _comparison_metrics(paper, reference):
    figure = paper.render()
    try:
        layout = figure._data_visuals_layout
        width, height = layout["canvas"]
        fraction = sum(cell["data_zone"]["w"] * cell["data_zone"]["h"]
                       for cell in layout["cells"].values()) / (width * height)
        return {"paperfig_axes_fraction": fraction, "reference": _reference_axes_fraction(reference)}
    finally:
        plt.close(figure)


def _comparison_notes(metrics):
    reference = metrics["reference"]
    occupancy = (f"参考图约 {reference['axes_fraction']:.1%}，新版约 {metrics['paperfig_axes_fraction']:.1%}。"
                 if reference else f"新版约 {metrics['paperfig_axes_fraction']:.1%}；参考图未提取到可比较的轴框。")
    return "\n".join([
        "# 与参考图的同尺寸对照", "",
        "两图均按 3.4 × 4.45 英寸、300 dpi 比较。并排预览没有分别裁切或放大某一幅。", "",
        f"- 绘图区占画布面积：{occupancy}",
        "- 新版占比来自渲染器的真实 data_zone；参考图占比从 PNG 的两组黑色轴脊估算。"
        "该指标只衡量空间利用，不能解释为专业程度提升百分比。",
        "- 新版使用 Times New Roman，所有可见文字至少 8 pt；原 PNG 无法提供源字号与排版参数。",
        "- 参考图的四个节点近似等距展示；新版按实际数值间距展示，三基座仅作 −4/0/+4 pt 的显示偏移。",
        "- 新版采用原精选配色中的深蓝、赭橙、青绿，并用圆形、方形、三角形冗余区分。",
        "- 24 个估计值和不对称区间端点逐项对照 CSV；没有把区间改成对称误差，也没有重新做 bootstrap。",
        "- 案例声明不含 axes 坐标和手动 subplots_adjust；底部图例、共享轴、字号和导出由同一管线处理。",
        "- 这次复用了散点、分组样式、分面、参考线及导出；不对称区间和底部图例是补齐后可继续复用的组件。", "",
        "两幅图的底层都是 Matplotlib。对照体现的是封装、版式规则和信息组织的区别，"
        "并不说明 Matplotlib 本身无法画出同样的效果。", "",
    ])


def export_matched_training(csv_path, output_dir, *, reference=None):
    study = load_matched_training_data(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paper = build_matched_training(study)
    outputs = []
    for extension in ("pdf", "png", "svg"):
        path = output_dir / f"{STEM}.{extension}"
        paper.render(path, dpi=300)
        outputs.append(path)
    path = output_dir / f"{STEM}_data.csv"
    study["data"].to_csv(path, index=False)
    outputs.append(path)
    path = output_dir / f"{STEM}_caption.md"
    path.write_text(_caption(study), encoding="utf-8")
    outputs.append(path)
    path = output_dir / f"{STEM}_manifest.json"
    manifest = {**study["metadata"], "title": TITLE,
                "figure_inches": list(FIGURE_INCHES), "png_dpi": 300,
                "minimum_font_pt": 8, "x_limits": list(X_LIMITS), "y_limits": list(Y_LIMITS),
                "palette": "curated-5-warm", "category_colors": COLORS,
                "markers": MARKERS, "x_offsets_pt": OFFSETS_PT,
                "legend_position": "bottom", "x_spacing": "actual numeric values",
                "legend": LEGEND,
                "pipeline": "Figure -> compute -> physical layout -> Matplotlib renderer -> export"}
    if reference is not None:
        manifest["visual_comparison"] = _comparison_metrics(paper, Path(reference))
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    outputs.append(path)
    if reference is not None:
        path = output_dir / f"{STEM}_vs_reference.png"
        export_visual_comparison(Path(reference), output_dir / f"{STEM}.png", path)
        outputs.append(path)
        path = output_dir / f"{STEM}_comparison.md"
        path.write_text(_comparison_notes(manifest["visual_comparison"]), encoding="utf-8")
        outputs.append(path)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=PROJECT_ROOT / "matched_id_training_gains_plot_data.csv")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "demo_outputs" / "matched_training")
    parser.add_argument("--reference", type=Path, default=PROJECT_ROOT / "demo_matched_training_single_column.png")
    args = parser.parse_args()
    for path in export_matched_training(args.csv, args.out, reference=args.reference):
        print(path)


if __name__ == "__main__":
    main()
