"""Plot a checked-in CSV with one declaration and no styling adjustments.

Run ``python demo/demo_simple_csv.py`` from any working directory.
Outputs are written to ``demo_outputs/quickstart/simple_csv.svg`` and ``simple_csv.png``.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_visuals import plot


def build_simple_csv(style: str = "modern"):
    """Return a reusable four-panel figure from the included benchmark CSV."""
    return plot(
        PROJECT_ROOT / "demo" / "data" / "benchmark.csv",
        plots=[
            {"kind": "bar", "metric": "accuracy"},
            {"kind": "line", "x": "epoch", "metric": "f1"},
            {"kind": "box", "metric": "latency"},
            {"kind": "histogram", "metric": "accuracy", "group": None},
        ],
        x="dataset",
        group="model",
        canvas={"width": 180},
        cols=2,
        style=style,
        palette="curated-10-default",
        title="Benchmark results",
    )


def main() -> None:
    output_dir = PROJECT_ROOT / "demo_outputs" / "quickstart"
    output_dir.mkdir(parents=True, exist_ok=True)
    figure = build_simple_csv()
    for extension in ("svg", "png"):
        output = output_dir / f"simple_csv.{extension}"
        figure.render(output, dpi=120)
        print(output)


if __name__ == "__main__":
    main()
