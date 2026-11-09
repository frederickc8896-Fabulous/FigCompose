"""Draw a numerical matrix with the native clustered_heatmap chart."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
import runpy

import pandas as pd
from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent


def build_figure(data_path=None, profile_path=None):
    source = Path(data_path or HERE / "data.csv")
    with source.open(encoding="utf-8-sig", newline="") as stream:
        columns = next(csv.reader(stream), [])
    if len(columns) < 4 or len(set(columns)) != len(columns) or any(not name.strip() for name in columns):
        raise ValueError("Supply a named sample ID column and at least three unique, named numeric traits.")
    frame = pd.read_csv(source,
                        keep_default_na=False, float_precision="round_trip")
    if len(frame) < 8 or frame.shape[1] < 4:
        raise ValueError("Supply at least eight samples and three numeric traits.")
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    paper = Figure(frame, config=config, canvas={"width": 170, "height": 176}, rows=1, cols=1,
                   title="Circular clustered heatmap")
    paper[0, 0].clustered_heatmap(sample=frame.columns[0], traits=frame.columns[1:].tolist(),
                                 value_range=(-1, 1), n_clusters=4, label_every=2)
    return paper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv")
    parser.add_argument("--profile", type=Path, default=HERE / "style.yaml")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    export(build_figure(args.data, args.profile), args.out,
           config=FigureConfig.load(args.profile))


if __name__ == "__main__":
    main()
