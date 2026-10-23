"""Physical-canvas examples: a single panel, a fixed combination and auto height.

Run ``python demo/demo_canvas.py`` from any working directory. Each example
exports SVG, PDF and a 300 DPI PNG to ``demo_outputs/canvas``.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_visuals import plot


CSV = PROJECT_ROOT / "demo" / "data" / "benchmark.csv"


def build_canvas_single():
    return plot(
        CSV, x="dataset", group="model",
        plots=[{"kind": "bar", "metric": "accuracy"}],
        canvas={"width": 90, "height": 65},
        style="modern", palette="curated-5-default",
    )


def _combined(canvas):
    return plot(
        CSV, x="dataset", group="model",
        plots=[
            {"kind": "bar", "metric": "accuracy"},
            {"kind": "line", "x": "epoch", "metric": "f1"},
            {"kind": "heatmap", "x": "dataset", "y": "model", "metric": "accuracy"},
            {"kind": "histogram", "metric": "latency", "group": None},
        ],
        canvas=canvas, cols=2,
        style="modern", palette="curated-5-default",
        title="Benchmark results",
    )


def build_canvas_mixed():
    return _combined({"width": 180, "height": 110})


def build_canvas_auto():
    return _combined({"width": 180})


def export_canvas_figures(output_dir: str | Path, *, dpi: int = 300) -> list[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, builder in (
        ("canvas_single", build_canvas_single),
        ("canvas_mixed", build_canvas_mixed),
        ("canvas_auto", build_canvas_auto),
    ):
        figure = builder()
        for extension in ("svg", "pdf", "png"):
            output = output_dir / f"{name}.{extension}"
            figure.render(output, dpi=dpi)
            outputs.append(output)
    return outputs


if __name__ == "__main__":
    for path in export_canvas_figures(PROJECT_ROOT / "demo_outputs" / "canvas"):
        print(path)
