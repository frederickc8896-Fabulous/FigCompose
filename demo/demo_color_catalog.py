"""Export the complete curated colour catalogue without altering its colours.

Run ``python demo/demo_color_catalog.py`` from any working directory. The
categorical sheet preserves all twelve original combinations, their bucket,
style and colour order.
The sequential sheet shows both interpolated ramps and every original stop.
An additional four-panel CSV figure previews ``palette="curated-5-default"``
through the public API, with the original categorical colours unchanged.
Outputs are written to ``demo_outputs/colors``.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from data_visuals import plot
from data_visuals.utils.colors import (
    SEQUENTIAL_SCHEMES,
    get_palette,
    get_palette_flat,
    list_palettes,
)


INK = "#263341"
MUTED = "#657381"
RULE = "#dfe5ea"
WIDTH = 1800
LEFT = 70
SWATCH_LEFT = 440
SWATCH_WIDTH = 113
SWATCH_STEP = 126


def _page(height: int, title: str, subtitle: str):
    figure = plt.figure(figsize=(WIDTH / 100, height / 100), dpi=100,
                         facecolor="white")
    axes = figure.add_axes((0, 0, 1, 1))
    axes.set(xlim=(0, WIDTH), ylim=(height, 0))
    axes.set_axis_off()
    axes.text(LEFT, 55, title, fontsize=25, weight="bold", color=INK, va="top")
    axes.text(LEFT, 112, subtitle, fontsize=12, color=MUTED, va="top")
    return figure, axes


def _section(axes, y: float, title: str, note: str = "") -> float:
    axes.plot((LEFT, WIDTH - LEFT), (y, y), color=RULE, linewidth=1)
    axes.text(LEFT, y + 17, title, fontsize=15, weight="bold", color=INK, va="top")
    if note:
        axes.text(SWATCH_LEFT, y + 20, note, fontsize=11, color=MUTED, va="top")
    return y + 61


def _categorical_row(axes, y: float, label: str, preset_id: str,
                     colors: list[str], ours_color: str) -> float:
    axes.text(LEFT, y + 4, label, fontsize=14, weight="bold", color=INK, va="top")
    axes.text(LEFT, y + 35, preset_id, fontsize=11, color=MUTED,
              va="top", family="DejaVu Sans Mono")
    for index, color in enumerate(colors):
        x = SWATCH_LEFT + index * SWATCH_STEP
        axes.add_patch(Rectangle((x, y), SWATCH_WIDTH, 49,
                                 facecolor=color, edgecolor="none"))
        axes.text(x + SWATCH_WIDTH / 2, y + 60, color.upper(), fontsize=10.5,
                  family="DejaVu Sans Mono", ha="center", va="top", color=INK)
        if color.lower() == ours_color.lower():
            axes.text(x + SWATCH_WIDTH / 2, y + 82, "highlight", fontsize=8,
                      ha="center", va="top", color=MUTED)
    return y + 116


def build_categorical_catalog():
    """Show the twelve original curated colour combinations."""
    registry = list_palettes()
    original_rows = list(registry.items())
    row_count = sum(len(styles) for _, styles in original_rows)
    height = 210 + len(original_rows) * 61 + row_count * 116 + 115
    figure, axes = _page(
        height, "Complete colour catalogue | categorical",
        "Exact registry colours and order. Original style names are retained; "
        "highlight marks the configured ours_color.",
    )
    try:
        y = 180
        for size, names in original_rows:
            y = _section(axes, y, f"ORIGINAL / {size} COLOURS",
                         "Each row is a separately curated combination.")
            for name in names:
                palette = get_palette(size, style=name)
                y = _categorical_row(
                    axes, y, f"{name} / {size} colours", f"curated-{size}-{name}",
                    get_palette_flat(size, style=name), palette.ours_color,
                )
        axes.text(LEFT, y + 15,
                  "Original names such as cool/warm describe the original combinations; "
                  "they do not imply the entire row is exclusively cool or warm.",
                  fontsize=11, color=MUTED, va="top")
        return figure
    except Exception:
        plt.close(figure)
        raise


def build_sequential_catalog():
    """Show every continuous scheme and its exact original colour stops."""
    height = 210 + len(SEQUENTIAL_SCHEMES) * 192 + 80
    figure, axes = _page(
        height, "Complete colour catalogue | continuous ramps",
        "Registry order and stop order are unchanged. Each ramp runs from its "
        "first stop (left) to its last stop (right).",
    )
    try:
        y = 185
        for name, colors in SEQUENTIAL_SCHEMES.items():
            axes.plot((LEFT, WIDTH - LEFT), (y - 17, y - 17), color=RULE, linewidth=1)
            axes.text(LEFT, y + 2, name, fontsize=16, weight="bold", color=INK, va="top")
            axes.text(LEFT, y + 35, f"{len(colors)} original stops", fontsize=11,
                      color=MUTED, va="top")
            cmap = LinearSegmentedColormap.from_list(f"catalog-{name}", colors)
            ramp_right = SWATCH_LEFT + 9 * SWATCH_STEP + SWATCH_WIDTH
            axes.imshow(
                [[value / 255 for value in range(256)]], cmap=cmap,
                extent=(SWATCH_LEFT, ramp_right, y + 46, y), aspect="auto", vmin=0, vmax=1,
            )
            for index, color in enumerate(colors):
                x = SWATCH_LEFT + index * SWATCH_STEP
                axes.add_patch(Rectangle((x, y + 69), SWATCH_WIDTH, 36,
                                         facecolor=color, edgecolor="none"))
                axes.text(x + SWATCH_WIDTH / 2, y + 116, color.upper(), fontsize=10.5,
                          family="DejaVu Sans Mono", ha="center", va="top", color=INK)
            y += 192
        axes.text(LEFT, y + 5,
                  "These are the stored ramps, including multihue schemes. "
                  "Choosing a ramp should follow the quantity being encoded.",
                  fontsize=11, color=MUTED, va="top")
        return figure
    except Exception:
        plt.close(figure)
        raise


def build_curated_figure():
    """Preview one original curated palette through the public CSV API."""
    return plot(
        PROJECT_ROOT / "demo" / "data" / "benchmark.csv",
        x="dataset",
        group="model",
        canvas={"width": 180},
        style="modern",
        palette="curated-5-default",
        title="Original curated palette / 5 colours",
        plots=[
            {"kind": "bar", "metric": "accuracy"},
            {"kind": "line", "x": "epoch", "metric": "f1"},
            {"kind": "heatmap", "x": "dataset", "y": "model", "metric": "accuracy"},
            {"kind": "histogram", "metric": "latency", "group": None},
        ],
    )


def main() -> None:
    output_dir = PROJECT_ROOT / "demo_outputs" / "colors"
    output_dir.mkdir(parents=True, exist_ok=True)
    with matplotlib.rc_context({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                                "savefig.bbox": None}):
        for name, builder in (("color_catalog_categorical", build_categorical_catalog),
                              ("color_catalog_sequential", build_sequential_catalog)):
            figure = builder()
            try:
                for extension in ("png", "svg"):
                    output = output_dir / f"{name}.{extension}"
                    figure.savefig(output, dpi=100, facecolor="white", bbox_inches=None)
                    print(output)
            finally:
                plt.close(figure)
    for extension in ("png", "svg"):
        output = output_dir / f"curated_5_default.{extension}"
        build_curated_figure().render(output, dpi=100)
        print(output)


if __name__ == "__main__":
    main()
