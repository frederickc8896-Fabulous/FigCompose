"""Print measured Matplotlib font and layout diagnostics without writing files.

Run ``python test/trace_fonts.py`` from any directory.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from matplotlib.font_manager import findfont
from matplotlib.text import Text

from data_visuals.core import Figure
from data_visuals.renderer.mpl import figure_to_matplotlib
import matplotlib.pyplot as plt


def describe_text(role, artist):
    """Report properties of the actual rendered text, including font fallback."""
    if artist is None or not artist.get_text():
        return
    props = artist.get_fontproperties()
    print(f"  {role}: {artist.get_text()!r}")
    print(f"    size={props.get_size_in_points():.2f} pt, "
          f"family={props.get_family()}, weight={props.get_weight()}")
    print(f"    resolved font: {findfont(props)}")


def main():
    data = pd.read_csv(PROJECT_ROOT / "demo" / "data" / "benchmark.csv")
    figure = Figure(data=data, rows=1, cols=2, base="large",
                    title="Matplotlib font and layout diagnostics")
    figure[0, 0].bar(x="dataset", y="accuracy", group="model",
                     title="(a) Benchmark accuracy")
    figure[0, 1].line(x="epoch", y="f1", group="model",
                      title="(b) Learning curves")
    spec = figure.build()
    rendered = figure_to_matplotlib(spec)
    try:
        rendered.canvas.draw()
        diagnostics = rendered._data_visuals_layout
        print(f"Canvas (design points): {diagnostics['canvas']}")
        print(f"Canvas (inches): {tuple(rendered.get_size_inches())}")
        print(f"Measurement iterations: {diagnostics['iterations']}")
        print(f"Header height: {diagnostics['header_height']:.2f} pt")
        for artist in diagnostics["header_artists"]:
            if isinstance(artist, Text):
                describe_text("main title", artist)
            else:
                for text in artist.get_texts():
                    describe_text("shared legend", text)
        for subplot in spec.subplots:
            key = (subplot.row, subplot.col)
            cell = diagnostics["cells"][key]
            axes = cell["axes"]
            print(f"\nSubplot {key}")
            print(f"  Layout font sizes (pt): {subplot.font_sizes}")
            print(f"  Cell: {cell['cell']}")
            print(f"  Data zone: {cell['data_zone']}")
            print(f"  Decoration bounds (bottom-left origin): {cell['decoration_bbox']}")
            describe_text("subplot title", axes.title)
            describe_text("x label", axes.xaxis.label)
            describe_text("y label", axes.yaxis.label)
            for role, ticks in (("x tick", axes.get_xticklabels()),
                                ("y tick", axes.get_yticklabels())):
                describe_text(role, next((text for text in ticks if text.get_text()), None))
            for legend in cell["legends"]:
                for text in legend.get_texts():
                    describe_text("local legend", text)
    finally:
        plt.close(rendered)


if __name__ == "__main__":
    main()
