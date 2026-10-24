"""Regenerate the README illustrations: python assets/readme/generate.py.

All chart data are synthetic. The chart gallery uses FigCompose's public
declarative API; the swatch sheets read the live color registry directly.
"""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_visuals import plot
from data_visuals.utils.colors import (
    SEQUENTIAL_SCHEMES,
    get_palette_flat,
    list_palettes,
)

OUTPUT = Path(__file__).resolve().parent
METHODS = ("Method A", "Method B")
INK, MUTED, RULE = "#26313f", "#657381", "#e1e6eb"
PAGE_WIDTH, LEFT, SWATCH_LEFT, RIGHT = 1680, 54, 410, 1626


def gallery_data() -> pd.DataFrame:
    """Keep observations, matrix counts and composition data explicitly apart."""
    rng = np.random.default_rng(23)
    records = []
    for index, method in enumerate(METHODS):
        for dataset_index, dataset in enumerate(("A", "B", "C", "D")):
            for _ in range(8):
                records.append({
                    "view": "benchmark", "method": method, "dataset": dataset,
                    "score": 72 + 6 * index + 3 * dataset_index + rng.normal(0, 1.8),
                })
        for epoch in range(1, 21):
            records.append({
                "view": "learning", "method": method, "epoch": epoch,
                "loss": 0.14 + 0.9 * np.exp(-epoch / (7 - 2 * index))
                + rng.normal(0, 0.008),
            })
        for _ in range(36):
            latency = rng.uniform(8, 28)
            records.append({
                "view": "tradeoff", "method": method, "latency": latency,
                "score": 65 + 4 * index + 0.65 * latency + rng.normal(0, 2),
            })
        for split in ("Clean", "Shifted"):
            for _ in range(45):
                records.append({
                    "view": "distribution", "method": method, "split": split,
                    "error": rng.normal(12 - 3 * index + 4 * (split == "Shifted"), 2.5),
                    "response": rng.normal(0.8 * index, 0.65),
                })
        records.append({
            "view": "composition", "method": method, "count": (58, 42)[index],
        })
        profiles = ((78, 65, 87, 72), (89, 82, 73, 88))
        for criterion, score in zip(
            ("Accuracy", "Robustness", "Efficiency", "Stability"), profiles[index],
        ):
            records.append({
                "view": "profile", "method": method, "criterion": criterion,
                "score": score,
            })
    counts = ((86, 7, 4, 3), (5, 88, 5, 2), (4, 6, 85, 5), (3, 2, 7, 88))
    for row, truth in enumerate(("A", "B", "C", "D")):
        for col, prediction in enumerate(("A", "B", "C", "D")):
            records.append({
                "view": "classification", "truth": truth, "prediction": prediction,
                "count": counts[row][col],
            })
    return pd.DataFrame.from_records(records)


def build_gallery():
    """One declaration per panel; Figure owns axes allocation and decoration."""
    return plot(
        gallery_data(), group="method", cols=3,
        canvas={"width": 225}, style="modern", palette="curated-2-default",
        title="FigCompose | Common scientific charts",
        legend={"scope": "shared", "ncols": 2,
                "order": list(METHODS)},
        plots=[
            {"kind": "bar", "x": "dataset", "metric": "score", "error": "std",
             "where": {"view": "benchmark"}, "title": "(a) Grouped bars + SD",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Score (%)"}},
            {"kind": "line", "x": "epoch", "metric": "loss", "markers": False,
             "where": {"view": "learning"}, "title": "(b) Learning curves",
             "chart_opts": {"xlabel": "Epoch", "ylabel": "Loss"}},
            {"kind": "scatter", "x": "latency", "metric": "score", "opacity": 0.7,
             "where": {"view": "tradeoff"}, "title": "(c) Scatter plots",
             "chart_opts": {"xlabel": "Latency (ms)", "ylabel": "Score (%)"}},
            {"kind": "box", "x": "split", "metric": "error",
             "where": {"view": "distribution"}, "title": "(d) Box plots",
             "chart_opts": {"xlabel": "Evaluation split", "ylabel": "Error (%)"}},
            {"kind": "histogram", "metric": "response", "bins": 16,
             "where": {"view": "distribution"}, "title": "(e) Histograms",
             "chart_opts": {"xlabel": "Response", "ylabel": "Count"}},
            {"kind": "heatmap", "x": "dataset", "y": "method", "metric": "score",
             "where": {"view": "benchmark"}, "title": "(f) Heatmaps", "fmt": ".1f",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Method"}},
            {"kind": "confusion", "x": "prediction", "y": "truth", "metric": "count",
             "where": {"view": "classification"}, "title": "(g) Confusion matrices",
             "normalize": True, "fmt": ".2f",
             "chart_opts": {"xlabel": "Predicted class", "ylabel": "True class"}},
            {"kind": "donut", "metric": "count", "width": 0.38,
             "where": {"view": "composition"}, "title": "(h) Composition / donut"},
            {"kind": "radar", "x": "criterion", "metric": "score", "ylim": (0, 100),
             "order": ["Accuracy", "Robustness", "Efficiency", "Stability"],
             "where": {"view": "profile"}, "title": "(i) Radar profiles"},
        ],
    )


def page(height, title, subtitle):
    figure = plt.figure(figsize=(PAGE_WIDTH / 100, height / 100), dpi=100,
                         facecolor="white")
    ax = figure.add_axes((0, 0, 1, 1))
    ax.set(xlim=(0, PAGE_WIDTH), ylim=(height, 0))
    ax.set_axis_off()
    ax.text(LEFT, 38, title, fontsize=24, weight="bold", color=INK, va="top")
    ax.text(LEFT, 94, subtitle, fontsize=12, color=MUTED, va="top")
    return figure, ax


def build_categorical_catalog():
    registry = list_palettes()
    height = 160 + 48 * len(registry) + 96 * sum(map(len, registry.values())) + 48
    figure, ax = page(
        height, "FigCompose | Curated color presets",
        "12 original combinations. Exact colors and order from the registry; "
        "use the preset name as the palette argument.",
    )
    y = 156
    for size, styles in registry.items():
        ax.plot((LEFT, RIGHT), (y, y), color=RULE, linewidth=0.8)
        ax.text(LEFT, y + 12, f"{size} COLORS", fontsize=14, weight="bold", color=INK, va="top")
        y += 48
        for style in styles:
            ax.text(LEFT, y + 12, f"curated-{size}-{style}", fontsize=15, color=INK, va="top")
            colors = get_palette_flat(size, style=style)
            step = (RIGHT - SWATCH_LEFT + 6) / len(colors)
            for index, color in enumerate(colors):
                x = SWATCH_LEFT + index * step
                ax.add_patch(Rectangle((x, y), step - 6, 43, facecolor=color, edgecolor="none"))
                ax.text(x + (step - 6) / 2, y + 53, color.upper(), fontsize=10.5,
                        family="DejaVu Sans Mono", color=INK, ha="center", va="top")
            y += 96
    return figure


def build_sequential_catalog():
    figure, ax = page(
        160 + 156 * len(SEQUENTIAL_SCHEMES) + 30,
        "FigCompose | Continuous color schemes",
        "Interpolated ramps and original stops. Left to right follows the stored "
        "order; names alone do not define the data semantics.",
    )
    y = 166
    for name, colors in SEQUENTIAL_SCHEMES.items():
        ax.plot((LEFT, RIGHT), (y - 15, y - 15), color=RULE, linewidth=0.8)
        ax.text(LEFT, y + 2, name, fontsize=17, color=INK, weight="bold", va="top")
        cmap = LinearSegmentedColormap.from_list(name, colors)
        ax.imshow(np.linspace(0, 1, 512)[None, :], cmap=cmap, vmin=0, vmax=1,
                  extent=(SWATCH_LEFT, RIGHT, y + 34, y), aspect="auto")
        step = (RIGHT - SWATCH_LEFT + 6) / len(colors)
        for index, color in enumerate(colors):
            x = SWATCH_LEFT + index * step
            ax.add_patch(Rectangle((x, y + 47), step - 6, 27, facecolor=color, edgecolor="none"))
            ax.text(x + (step - 6) / 2, y + 85, color.upper(), fontsize=10.5,
                    family="DejaVu Sans Mono", color=INK, ha="center", va="top")
        y += 156
    return figure


def clean_svg(path):
    """Keep generated SVG source friendly to Git's whitespace checks."""
    content = "\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    gallery = build_gallery()
    for extension in ("svg", "png"):
        output = OUTPUT / f"traditional_charts.{extension}"
        gallery.render(output, dpi=200)
        if extension == "svg":
            clean_svg(output)
        print(output.relative_to(ROOT))
    with plt.rc_context({"font.family": "Times New Roman", "svg.fonttype": "path",
                         "svg.hashsalt": "figcompose-readme", "savefig.bbox": None}):
        for name, builder in (("color_presets", build_categorical_catalog),
                              ("color_schemes", build_sequential_catalog)):
            figure = builder()
            try:
                for extension in ("svg", "png"):
                    output = OUTPUT / f"{name}.{extension}"
                    figure.savefig(output, dpi=100, facecolor="white", bbox_inches=None)
                    if extension == "svg":
                        clean_svg(output)
                    print(output.relative_to(ROOT))
            finally:
                plt.close(figure)


if __name__ == "__main__":
    main()
