"""One dataset and canvas, with reusable shared and local legend policies."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_visuals.core import Figure, FigureConfig


LEGEND_VARIANTS = {
    "top": {"scope": "shared", "position": "top", "ncols": 3},
    "bottom": {"scope": "shared", "position": "bottom", "ncols": 3},
    "left": {"scope": "shared", "position": "left", "ncols": 1},
    "right": {"scope": "shared", "position": "right", "ncols": 1},
    "local": {"scope": "local", "position": "upper right", "ncols": 1,
              "frameon": True},
    "hidden": {"visible": False},
}
_ORDER = ["xsmall", "small", "roberta"]
_STYLES = {
    "xsmall": {"marker": "o", "size": 15},
    "small": {"marker": "s", "size": 15},
    "roberta": {"marker": "^", "size": 18},
}


def build_legend_demo(variant="bottom"):
    """Return an unrendered Figure; only the legend policy changes by variant."""
    if variant not in LEGEND_VARIANTS:
        raise ValueError(f"Unknown legend variant {variant!r}; choose {list(LEGEND_VARIANTS)}")
    data = pd.DataFrame([
        {"panel": panel, "model": model, "id_rejection": node,
         "leakage_difference": -10 + group * 2 + node * 0.32 + panel}
        for panel in range(2)
        for group, model in enumerate(_ORDER)
        for node in (1, 2, 5, 10)
    ])
    legend = {
        "fontsize": 8, "gap": 6, "order": _ORDER,
        "labels": {"roberta": "RoBERTa"},
        **deepcopy(LEGEND_VARIANTS[variant]),
    }
    paper = Figure(
        data=data, rows=2, cols=1, theme="modern", palette="curated-5-warm",
        title="Training gains at matched ID rejection",
        canvas={"width": 110, "height": 125}, legend=legend,
        config=FigureConfig(facets={
            "sharex": True, "sharey": True,
            "xlabel": "Actual ID false rejection (%)",
            "ylabel": "Leakage difference (pp)",
            "note": "Synthetic data · same data, canvas, fonts and series styles",
        }),
    )
    for row in range(2):
        options = {
            "series_styles": deepcopy(_STYLES), "opacity": 1,
            "xlim": (0, 11), "ylim": (-11, 2),
            "xticks": [1, 2, 5, 10], "yticks": [-10, -5, 0],
            "guides": [{"axis": "y", "value": 0,
                        "color": "#9ca3af", "linestyle": "--", "linewidth": 0.7}],
        }
        if variant == "local" and row == 1:
            # Every other field, including fontsize/frame/labels, is inherited.
            options["legend"] = {"position": "lower right"}
        paper[row, 0].scatter(
            x="id_rejection", y="leakage_difference", group="model",
            where={"panel": row}, title=f"({chr(97 + row)}) {'Near' if row == 0 else 'Far'}-OOD",
            chart_opts=options,
        )
    return paper


def export_legend_demo(output_dir):
    """Write identical-content variants as PNG and vector PDF/SVG."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for variant in LEGEND_VARIANTS:
        paper = build_legend_demo(variant)
        for extension in ("png", "pdf", "svg"):
            path = output_dir / f"legend_{variant}.{extension}"
            paper.render(str(path), **({"dpi": 300} if extension == "png" else {}))
            outputs.append(path)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "demo_outputs" / "legends")
    args = parser.parse_args()
    for path in export_legend_demo(args.out):
        print(path)


if __name__ == "__main__":
    main()
