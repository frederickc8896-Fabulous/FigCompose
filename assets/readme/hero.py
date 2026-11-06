"""Generate the README's 3-column x 5-row figure with public FigCompose APIs.

Run: python assets/readme/hero.py
All inputs are explicit synthetic observations. No demo modules, custom drawing
callbacks, manual axes placement or post-render artist adjustments are needed.
Requires FigCompose 0.1.2 or later for circular_bar and curated-8-rose-blue.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_visuals import FigureConfig, check_figure, list_color_presets, plot
from data_visuals.utils.colors import get_color_preset, get_palette

OUTPUT = Path(__file__).resolve().parent
METHODS = ("Method A", "Method B")
PALETTE = "curated-8-rose-blue"
CANVAS = {"width": 255, "height": 420}


def hero_data() -> pd.DataFrame:
    """Generate raw repeats, score profiles and demonstration intervals."""
    rng = np.random.default_rng(20261105)
    records = []

    def add(view, method=METHODS[0], **values):
        records.append({"view": view, "method": method, **values})

    for index, method in enumerate(METHODS):
        for column, dataset in enumerate(("D1", "D2", "D3", "D4", "D5")):
            for _ in range(20):
                add("benchmark", method, dataset=dataset,
                    score=65 + 4.2 * column + 6.5 * index + rng.normal(0, 3.2))
            add("stacked", method, dataset=dataset, amount=24 + 5 * column + 14 * index)
        for epoch in range(1, 41):
            add("learning", method, epoch=epoch,
                loss=.085 + .95 * np.exp(-epoch / (13 - 3 * index)) + rng.normal(0, .004))
        for _ in range(65):
            latency = rng.uniform(8, 32)
            add("tradeoff", method, latency=latency,
                score=61 + 5.5 * index + .72 * latency + rng.normal(0, 2.3),
                size=rng.uniform(14, 105))
        for _ in range(180):
            add("distribution", method, response=rng.normal(.5 + .95 * index, .62 + .1 * index))
        for criterion, score in zip(
            ("Quality", "Speed", "Robustness", "Stability", "Efficiency"),
            ((83, 62, 88, 70, 77), (91, 87, 74, 90, 84))[index],
        ):
            add("profile", method, criterion=criterion, score=score)
        for node in range(6):
            estimate = -1.4 - .85 * node - 1.25 * index + .4 * np.sin(node)
            add("interval", method, budget=2 + 2 * node, difference=estimate,
                lower=estimate - .9 - .13 * node, upper=estimate + 1.25 + .06 * node)
        for time in np.linspace(0, 12, 49):
            response = (1.2 + .35 * index) * np.exp(-((time - 3.5 - 3 * index) / 1.9) ** 2)
            response += .65 * np.exp(-((time - 9 + index) / 1.7) ** 2)
            add("signal", method, time=time, signal=response)
        add("composition", method, amount=(61, 39)[index])

    # Each circular sector is an independent score scale, not a total share.
    for subject_index, subject in enumerate(("Math", "Language", "Science", "Arts")):
        for participant in range(1, 7):
            score = 65 + 18 * np.sin(participant * .7 + subject_index * .8)
            score += 6 * np.cos(subject_index + participant * .3)
            add("circular", subject=subject, participant=f"P{participant:02d}",
                score=float(np.clip(score + rng.normal(0, 1.5), 28, 97)))

    tasks = ("T1", "T2", "T3", "T4", "T5", "T6")
    for row, task in enumerate(tasks):
        for column, dataset in enumerate(("D1", "D2", "D3", "D4", "D5")):
            value = 56 + 4 * row + 4.5 * column + 5 * np.sin(.8 * row + column)
            add("matrix", task=task, dataset=dataset, score=value)
    counts = ((86, 7, 4, 3), (5, 88, 5, 2), (4, 6, 85, 5), (3, 2, 7, 88))
    for row, truth in enumerate(("C1", "C2", "C3", "C4")):
        for column, prediction in enumerate(("C1", "C2", "C3", "C4")):
            add("classification", truth=truth, prediction=prediction, count=counts[row][column])
    return pd.DataFrame.from_records(records)


def hero_profile(palette=PALETTE) -> FigureConfig:
    """Reuse the preset's exact main and final colors for the two methods."""
    preset = get_color_preset(palette)
    colors = get_palette(2, palette).colors
    if len(colors) < 4:
        raise ValueError("This gallery needs at least four colors for its circular-score panel.")
    primary = int(preset.get("primary_index", 0))
    subject_indices = np.linspace(primary, len(colors) - 1, 4).round().astype(int)
    return FigureConfig(
        theme="modern", palette=palette, font_family="Times New Roman",
        legend={"scope": "shared", "ncols": 2, "order": list(METHODS)},
        series={"method": [
            {"id": METHODS[0], "color": colors[primary], "marker": "o", "linestyle": "-"},
            {"id": METHODS[1], "color": colors[-1], "marker": "s", "linestyle": "--"},
        ]},
        category_colors={"subject": dict(zip(
            ("Math", "Language", "Science", "Arts"),
            (colors[index] for index in subject_indices),
        ))},
    )


def build_hero(data=None, palette=PALETTE):
    """Fifteen native declarations; FigCompose controls the whole layout."""
    # A light-to-dark ramp from the same rose-blue swatches as the methods.
    # Skip the lighter middle swatches so increasing values stay darker.
    colors = get_palette(2, palette).colors
    matrix_scheme = ([colors[index] for index in (0, 1, 2, 6, 7)]
                     if palette == "curated-8-rose-blue"
                     else get_color_preset(palette)["sequential"])
    return plot(
        hero_data() if data is None else data,
        config=hero_profile(palette), group="method", cols=3, canvas=CANVAS,
        title="FigCompose | One figure. A consistent visual language.",
        plots=[
            {"kind": "bar", "x": "dataset", "metric": "score", "error": "std",
             "where": {"view": "benchmark"}, "title": "(a) Grouped bars + SD",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Score (%)", "ylim": [0, 100]}},
            {"kind": "line", "x": "epoch", "metric": "loss", "markers": False,
             "where": {"view": "learning"}, "title": "(b) Learning curves",
             "chart_opts": {"xlabel": "Epoch", "ylabel": "Loss", "xticks": [1, 10, 20, 30, 40]}},
            {"kind": "scatter", "x": "latency", "metric": "score", "opacity": .7,
             "where": {"view": "tradeoff"}, "title": "(c) Scatter plots",
             "chart_opts": {"xlabel": "Latency (ms)", "ylabel": "Score (%)"}},
            {"kind": "box", "x": "dataset", "metric": "score",
             "where": {"view": "benchmark"}, "title": "(d) Distributions",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Score (%)"}},
            {"kind": "histogram", "metric": "response", "density": True,
             "where": {"view": "distribution"}, "title": "(e) Density curves",
             "chart_opts": {"xlabel": "Response", "ylabel": "Density"}},
            {"kind": "heatmap", "x": "dataset", "y": "task", "metric": "score",
             "where": {"view": "matrix"}, "title": "(f) Heatmaps", "fmt": ".0f",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Task",
                            "color_scheme": matrix_scheme}},
            {"kind": "confusion", "x": "prediction", "y": "truth", "metric": "count",
             "where": {"view": "classification"}, "normalize": True, "fmt": ".2f",
             "title": "(g) Confusion matrices",
             "chart_opts": {"xlabel": "Predicted class", "ylabel": "True class",
                            "color_scheme": matrix_scheme}},
            {"kind": "pie", "metric": "amount", "where": {"view": "composition"},
             "title": "(h) Composition"},
            {"kind": "scatter", "x": "latency", "metric": "score", "size": "size",
             "trend": True, "opacity": .5, "where": {"view": "tradeoff"},
             "title": "(i) Bubbles + fitted trends",
             "chart_opts": {"xlabel": "Latency (ms)", "ylabel": "Score (%)"}},
            {"kind": "bar", "x": "dataset", "metric": "amount", "stacked": True,
             "where": {"view": "stacked"}, "title": "(j) Stacked bars",
             "chart_opts": {"xlabel": "Dataset", "ylabel": "Amount"}},
            {"kind": "scatter", "x": "budget", "metric": "difference",
             "where": {"view": "interval"}, "title": "(k) Asymmetric intervals",
             "chart_opts": {"xlabel": "Reference budget (%)", "ylabel": "Difference (pp)",
                            "errorbar": {"lower": "lower", "upper": "upper", "capsize": 2},
                            "x_offsets": {METHODS[0]: -3, METHODS[1]: 3},
                            "guides": [{"axis": "y", "value": 0}],
                            "xticks": [2, 4, 6, 8, 10, 12]}},
            {"kind": "line", "x": "time", "metric": "signal", "area": True,
             "markers": False, "where": {"view": "signal"}, "title": "(l) Filled signal curves",
             "chart_opts": {"xlabel": "Time (s)", "ylabel": "Response", "ylim": [0, 2]}},
            {"kind": "circular_bar", "x": "participant", "group": "subject", "metric": "score",
             "summary": "mean", "where": {"view": "circular"}, "title": "(m) Concentric scores",
             "chart_opts": {"legend": False}},
            {"kind": "radar", "x": "criterion", "metric": "score", "ylim": (0, 100),
             "where": {"view": "profile"}, "title": "(n) Radar profiles",
             "order": ["Quality", "Speed", "Robustness", "Stability", "Efficiency"],
             "chart_opts": {"legend": False}},
            {"kind": "donut", "metric": "amount", "width": .42,
             "where": {"view": "composition"}, "title": "(o) Donut charts"},
        ],
    )


def generate(output=OUTPUT, palette=PALETTE):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    data = hero_data()
    paper = build_hero(data, palette)
    rendered = paper.render()
    try:
        report = check_figure(rendered)
        report.raise_for_errors(include_warnings=True)
        settings = dict(getattr(rendered, "_data_visuals_rcparams", {}))
        settings.update({"savefig.bbox": None, "savefig.pad_inches": 0,
                         "svg.hashsalt": "figcompose-hero"})
        with matplotlib.rc_context(settings):
            for suffix, dpi in (("png", 180), ("svg", 72)):
                target = output / f"hero_gallery.{suffix}"
                rendered.savefig(target, dpi=dpi, bbox_inches=None,
                                 facecolor="white", metadata={"Date": None} if suffix == "svg" else None)
                if suffix == "svg":
                    source = target.read_text(encoding="utf-8")
                    target.write_text("\n".join(line.rstrip() for line in source.splitlines()) + "\n",
                                      encoding="utf-8", newline="\n")
        # The build record is intentionally small; full reports belong to local validation.
        summary = {"synthetic": True, "seed": 20261105, "observations": len(data),
                   "rows": 5, "columns": 3, "panels": 15, "palette": palette,
                   "canvas_mm": CANVAS, "errors": len(report.errors),
                   "warnings": len(report.warnings), "native_chart_kinds": 11}
        print(json.dumps(summary, indent=2), flush=True)
        print(report.summary(), flush=True)
        return summary
    finally:
        plt.close(rendered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--palette", default=PALETTE,
                        choices=[name for name in list_color_presets() if int(name.split("-")[1]) >= 4],
                        help="Use a curated preset with at least four colors.")
    args = parser.parse_args()
    generate(args.out, args.palette)
