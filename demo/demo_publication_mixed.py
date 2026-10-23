"""Reproducible Matplotlib acceptance figures built from top-level declarations.

Run ``python demo/demo_publication_mixed.py`` from any directory.  The demo
exports mixed SVG/PDF/PNG and stress SVG/PNG figures to ``demo_outputs/publication``.
The build functions return an unrendered Figure for notebooks and tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_visuals.core import Figure


def publication_data(*, many_models: bool = False) -> pd.DataFrame:
    """Create repeatable benchmark data without files or global random state."""
    rng = np.random.default_rng(20261022)
    models = (
        [f"Architecture {i + 1:02d} with adaptation" for i in range(10)]
        if many_models
        else ["Baseline", "Residual Net", "Transformer", "Ours"]
    )
    benchmarks = [
        "Long document question answering",
        "Cross domain image classification",
        "Low resource sequence prediction",
        "Out of distribution robustness",
    ]
    partitions = ["Train", "Validation", "Test", "Shift"]
    classes = ["Class A", "Class B", "Class C", "Class D"]
    records = []
    for model_index, model in enumerate(models):
        for epoch in range(1, 25):
            task = (epoch - 1) // 6
            accuracy = np.clip(
                0.62 + 0.018 * model_index + 0.004 * epoch
                - 0.016 * task + rng.normal(0, 0.018), 0, 1,
            )
            truth = (epoch + model_index) % len(classes)
            prediction = truth if rng.random() < accuracy else (truth + 1) % len(classes)
            records.append({
                "model": model,
                "benchmark": benchmarks[task],
                "partition": partitions[task],
                "cohort": "Clean input" if epoch % 2 else "Shifted input",
                "epoch": epoch,
                "accuracy": float(accuracy),
                "precision": float(np.clip(accuracy + rng.normal(0.025, 0.008), 0, 1)),
                "recall": float(np.clip(accuracy - rng.normal(0.025, 0.008), 0, 1)),
                "latency": float(7 + 1.1 * model_index + 0.2 * epoch + rng.uniform(0, 1)),
                "truth": classes[truth],
                "prediction": classes[prediction],
            })
    return pd.DataFrame.from_records(records)


def build_publication_mixed(data: pd.DataFrame | None = None) -> Figure:
    """Seven chart types; spans, shared model colors and a local cohort legend."""
    fig = Figure(
        data=publication_data() if data is None else data,
        layout=[[(2, 2), 1, 1], [None, 1, 1], [2, 2]],
        canvas={"width": 180, "height": 150}, dpi=120,
        palette="curated-10-default",
        title="Benchmark study: performance, reliability and errors",
    )
    fig[0, 0].bar(
        x="benchmark", y="accuracy", group="model", error="accuracy",
        title="(a) Benchmark accuracy with variability",
    )
    fig[0, 2].line(
        x="epoch", y="accuracy", group="model", title="(b) Learning curves",
    )
    fig[0, 3].scatter(
        x="latency", y="accuracy", group="cohort", title="(c) Accuracy and latency",
    )
    fig[1, 2].box(
        x="partition", y="accuracy", group="model", title="(d) Robustness by split",
    )
    fig[1, 3].histogram(
        x="accuracy", group="model", bins=12, title="(e) Score distributions",
    )
    fig[2, 0].heatmap(
        x="partition", y="model", value="accuracy", title="(f) Aggregate performance",
        chart_opts={"annotate": True, "fmt": ".2f"},
    )
    fig[2, 2].confusion(
        x="prediction", y="truth", normalize=True, fmt=".2f",
        title="(g) Row-normalized classification errors",
    )
    return fig


def build_publication_stress(data: pd.DataFrame | None = None) -> Figure:
    """Ratios, long legends/labels, multi-y, secondary axes and reference lines."""
    fig = Figure(
        data=publication_data(many_models=True) if data is None else data,
        rows=2, cols=2, width_ratios=[1.4, 1], height_ratios=[1, 1.15],
        canvas={"width": 180, "height": 140}, dpi=120,
        palette="curated-10-default",
        title="Layout stress study: reusable typography and legends",
    )
    fig[0, 0].line(
        x="epoch", y="accuracy", y2="latency", group="model",
        title="(a) Ten models with a secondary latency axis",
    )
    fig[0, 1].line(
        x="epoch", y=["precision", "recall"], title="(b) Multiple response metrics",
    )
    fig[1, 0].bar(
        x="benchmark", y="accuracy", group="model",
        y_columns=["Architecture 01 with adaptation", "Architecture 10 with adaptation"],
        title="(c) Long labels, model subset and reference lines",
        chart_opts={
            "horizontal": True, "hline": 0.8, "hline_label": "Target accuracy",
            "mean_line": True, "mean_line_label": "Observed mean",
        },
    )
    fig[1, 1].bar(
        x="partition", y=["precision", "recall"],
        title="(d) Multiple metrics as percentage stacks",
        chart_opts={"stacked": "percent"},
    )
    return fig


def export_publication_figures(output_dir: str | Path, *, dpi: int = 120) -> list[Path]:
    """Export bounded-size review artifacts through the Matplotlib backend."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, build, formats in (
        ("publication_mixed", build_publication_mixed, ("svg", "pdf", "png")),
        ("publication_stress", build_publication_stress, ("svg", "png")),
    ):
        figure = build()
        for extension in formats:
            path = output_dir / f"{name}.{extension}"
            figure.render(path, backend="matplotlib", dpi=dpi)
            outputs.append(path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "demo_outputs" / "publication")
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    for output in export_publication_figures(args.out, dpi=args.dpi):
        print(output)


if __name__ == "__main__":
    main()
