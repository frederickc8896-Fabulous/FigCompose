"""Native undirected weighted chords with the FigCompose showcase profile.

Run: python examples/chord_connections/generate.py
Replace data.csv with source,target,value; one row per undirected pair.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import runpy

import pandas as pd

from data_visuals import FigureConfig, plot
from data_visuals.compute.chord import node_order

HERE = Path(__file__).resolve().parent


def build_figure(data_path=None, profile_path=None):
    data = pd.read_csv(HERE / "data.csv" if data_path is None else data_path,
                       keep_default_na=False)
    config = FigureConfig.load(HERE / "style.yaml" if profile_path is None else profile_path)
    domain = node_order(data["source"].tolist() + data["target"].tolist())
    registered = [item["id"] for item in config.series.get("source", [])]
    order = [item for item in registered if item in domain]
    order.extend(item for item in domain if item not in order)
    return plot(data, plots=[{"kind": "chord", "source": "source", "target": "target",
                              "value": "value", "order": order, "summary": True}],
                config=config, canvas={"width": 210},
                title=f"{len(domain)} groups. Every connection counts.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    export(build_figure(args.data, args.profile), args.out)


if __name__ == "__main__":
    main()
