"""Release-gate smoke for the installed package's 22 native chart kinds.

Run outside the checkout with python -I; data and outputs are self-contained.
"""
from __future__ import annotations

import argparse
from importlib import resources
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import to_hex
import pandas as pd
import numpy as np
import scipy

import data_visuals
from data_visuals import FigureConfig, plot, check_figure
from data_visuals.charts import list_chart_types
from data_visuals.renderer.mpl.config import MplConfig

EXPECTED = {"bar", "line", "scatter", "box", "histogram", "heatmap", "confusion",
            "pie", "donut", "radar", "circular_bar", "chord", "raincloud", "ridgeline",
            "paired", "estimation", "scatter3d", "waterfall3d", "bar3d",
            "alluvial", "participant_tracks", "clustered_heatmap"}


def declarations():
    ordinary = pd.DataFrame([(category, group, value) for category in ("A", "B")
                             for group in ("M1", "M2") for value in (1.2, 2.4, 3.1, 4.6)],
                            columns=["x", "group", "value"])
    result = []
    for kind in ("bar", "line", "scatter", "box"):
        result.append((kind, ordinary, {"kind": kind, "x": "x", "y": "value", "group": "group"}))
    result.append(("histogram", ordinary, {"kind": "histogram", "x": "value", "group": "group"}))
    matrix = pd.DataFrame({"x": ["A", "A", "B", "B"], "y": ["C", "D", "C", "D"], "value": [1, 2, 3, 4]})
    result.append(("heatmap", matrix, {"kind": "heatmap", "x": "x", "y": "y", "value": "value"}))
    result.append(("confusion", matrix, {"kind": "confusion", "x": "x", "y": "y", "value": "value"}))
    pie = pd.DataFrame({"group": ["A", "B", "C"], "value": [2, 3, 5]})
    for kind in ("pie", "donut"):
        result.append((kind, pie, {"kind": kind, "group": "group", "value": "value"}))
    radar = pd.DataFrame([(axis, group, value) for group in ("M1", "M2")
                          for axis, value in zip(("A", "B", "C"), (30, 60, 90))],
                         columns=["x", "group", "value"])
    result.append(("radar", radar, {"kind": "radar", "x": "x", "y": "value", "group": "group"}))
    result.append(("circular_bar", radar, {"kind": "circular_bar", "x": "x", "y": "value", "group": "group", "summary": "mean"}))
    edges = pd.DataFrame({"source": ["A", "A", "B"], "target": ["B", "C", "C"], "value": [2, 3, 4]})
    result.append(("chord", edges, {"kind": "chord", "source": "source", "target": "target", "value": "value", "summary": True}))
    for kind in ("raincloud", "ridgeline"):
        result.append((kind, ordinary, {"kind": kind, "x": "x", "y": "value", "group": "group"}))
    pairs = pd.DataFrame([(index, level, a if level == "A" else b)
                          for index, (a, b) in enumerate(((2., 3.), (2.5, 4.), (3., 4.3), (4., 4.8), (5., 6.7)))
                          for level in ("A", "B")], columns=["pair", "level", "value"])
    result.append(("paired", pairs, {"kind": "paired", "pair": "pair", "x": "level", "y": "value", "order": ["A", "B"]}))
    result.append(("estimation", pairs, {"kind": "estimation", "pair": "pair", "x": "level", "y": "value", "order": ["A", "B"], "ci_method": "paired_t", "confidence": .95}))
    points = pd.DataFrame({"x": [1, 2, 3, 4], "y": [2, 1, 4, 3], "z": [3, 4, 2, 1], "group": ["A", "A", "B", "B"]})
    result.append(("scatter3d", points, {"kind": "scatter3d", "x": "x", "y": "y", "z": "z", "group": "group"}))
    curves = pd.DataFrame([(x, group, value) for group in ("A", "B")
                           for x, value in ((0, 1), (1, 3), (2, 2))], columns=["x", "group", "value"])
    result.append(("waterfall3d", curves, {"kind": "waterfall3d", "x": "x", "y": "value", "group": "group", "baseline": 0}))
    bars = pd.DataFrame([(x, y, group, value) for x in ("A", "B") for y in ("C", "D")
                         for group, value in (("Part 1", 2), ("Part 2", 3))], columns=["x", "y", "group", "value"])
    result.append(("bar3d", bars, {"kind": "bar3d", "x": "x", "y": "y", "value": "value", "group": "group", "stacked": True}))
    paths = pd.DataFrame({"start": ["A", "B"], "end": ["B", "A"], "weight": [4, 6]})
    result.append(("alluvial", paths, {"kind": "alluvial", "stages": ["start", "end"], "metric": "weight"}))
    cohort = pd.DataFrame({"id": ["P1", "P2", "P3", "P4"], "sex": ["F", "M", "M", "F"],
                           "age": [22, 30, 35, 46]})
    result.append(("participant_tracks", cohort, {"kind": "participant_tracks", "id": "id",
                   "categorical": ["sex"], "numeric": ["age"], "numeric_ranges": {"age": [18, 80]}}))
    traits = pd.DataFrame({"sample": ["A", "B", "C", "D"], "T1": [-.8, -.6, .5, .9],
                           "T2": [-.5, -.8, .9, .5]})
    result.append(("clustered_heatmap", traits, {"kind": "clustered_heatmap", "sample": "sample",
                   "traits": ["T1", "T2"], "n_clusters": 2}))
    return result


def run_native_smoke(output, *, checkout=None, only_kinds=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    installed = Path(data_visuals.__file__).resolve()
    if checkout is not None:
        assert not installed.is_relative_to(Path(checkout).resolve()), installed
    assert set(list_chart_types()) == EXPECTED, list_chart_types()
    for name in ("general", "modern", "showcase"):
        theme = resources.files("data_visuals.themes").joinpath(name + ".json")
        assert json.loads(theme.read_text(encoding="utf-8"))["name"] == name
    # Exercise files from the installed distribution, including every face.
    # This keeps release verification independent of system Times/Tinos fonts.
    assert MplConfig._resolve_font("Tinos") == "Tinos"
    font_root = resources.files("data_visuals").joinpath("assets", "fonts", "tinos")
    assert "SIL OPEN FONT LICENSE Version 1.1" in font_root.joinpath("OFL.txt").read_text(encoding="utf-8")
    tinos_faces = {}
    for style, weight, filename in (
        ("normal", "normal", "Tinos-Regular.ttf"),
        ("normal", "bold", "Tinos-Bold.ttf"),
        ("italic", "normal", "Tinos-Italic.ttf"),
        ("italic", "bold", "Tinos-BoldItalic.ttf"),
    ):
        actual = Path(font_manager.findfont(
            font_manager.FontProperties(family="Tinos", style=style, weight=weight),
            fallback_to_default=False,
        )).resolve()
        expected = Path(str(font_root.joinpath(filename))).resolve()
        assert actual == expected, (actual, expected)
        tinos_faces[filename] = actual.name
    resolved = MplConfig("showcase", physical=True, font_sizes={"main_title": 17, "tick": 9.5})
    assert resolved.showcase and resolved.font_sizes["main_title"] == 17 and resolved.font_sizes["tick"] == 9.5
    config = FigureConfig(font_family="Tinos", legend={"visible": False})
    results = []
    for kind, data, declaration in declarations():
        if only_kinds is not None and kind not in only_kinds:
            continue
        chart_config = config
        chord_colors = {"A": "#112233", "B": "#445566", "C": "#778899"}
        if kind == "chord":
            declaration = {**declaration, "labels": {"A": "Alpha", "B": "Beta", "C": "Gamma"}}
            chart_config = FigureConfig(font_family="Tinos", legend={"visible": False},
                                        category_colors={"source": chord_colors})
        paper = plot(data, plots=[{**declaration, "title": None}], config=chart_config,
                     canvas={"width": 180}, style="showcase", palette="curated-10-vibrant")
        spec = paper.build()
        assert all(panel.custom_panel is None for panel in spec.subplots)
        json.dumps(spec.to_dict(), allow_nan=False)
        rendered = paper.render()
        try:
            report = check_figure(rendered)
            report.raise_for_errors(include_warnings=True)
            if kind == "chord":
                ribbons = [patch for patch in rendered.axes[0].patches
                           if hasattr(patch, "_figcompose_chord_edge")]
                assert len(ribbons) == 3
                for patch in ribbons:
                    source_id = patch._figcompose_chord_edge[0]
                    assert source_id in chord_colors, "Display aliases must not replace raw edge identities"
                    assert to_hex(patch.get_facecolor()) == chord_colors[source_id]
            if kind == "circular_bar":
                means = spec.subplots[0].derived_data["circular_bar"]["summaries"]
                ax = rendered.axes[0]
                large_numbers = [artist for artist in ax.texts
                                 if artist.get_fontsize() > 2 * spec.subplots[0].font_sizes["axis_label"]
                                 and artist.get_position()[1] > 1.44]
                assert len(large_numbers) == len(means), "Mean summaries must be above the native tracks"
                assert len(rendered.axes) == 1, "Top summaries must stay within the native panel"
            report.save(output / (kind + "_report.json"))
            rendered.savefig(output / (kind + ".png"), dpi=120)
            results.append({"kind": kind, "errors": len(report.errors), "warnings": len(report.warnings),
                            "canvas_mm": [report.canvas["width_mm"], report.canvas["height_mm"]]})
            print("Verified native " + kind, flush=True)
        finally:
            plt.close(rendered)
    result = {"installed": str(installed), "native_count": len(results), "native": results,
              "versions": {"python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
                           "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__},
              "strict_figure_spec_json": True, "showcase_resources_and_explicit_fonts": True,
              "bundled_tinos_faces": tinos_faces,
              "circular_top_summary_is_native": any(item["kind"] == "circular_bar" for item in results),
              "chord_alias_actual_colors_checked": any(item["kind"] == "chord" for item in results)}
    (output / "native_smoke.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--only-kind", action="append", choices=sorted(EXPECTED))
    args = parser.parse_args()
    run_native_smoke(args.output, checkout=args.checkout, only_kinds=args.only_kind)


if __name__ == "__main__":
    main()
