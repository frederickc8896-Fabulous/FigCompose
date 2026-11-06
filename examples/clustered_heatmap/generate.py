"""Read a bounded numerical matrix and draw a circular Ward-clustered heatmap."""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent


def build_figure(data_path=None, profile_path=None):
    frame = pd.read_csv(data_path or HERE / "data.csv", index_col=0,
                        keep_default_na=False, float_precision="round_trip")
    if len(frame) < 8 or frame.shape[1] < 3:
        raise ValueError("Supply at least eight samples and three numeric traits.")
    if frame.index.duplicated().any() or not all(str(value) for value in frame.index):
        raise ValueError("Sample IDs must be nonempty and unique.")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.any(np.abs(values) > 1):
        raise ValueError("This signed-value template expects finite traits within [-1, 1].")
    tree = linkage(values, method="ward", optimal_ordering=True)
    if float(tree[:, 2].max()) <= 0:
        raise ValueError("At least two distinct profiles are needed for the radial Ward tree.")
    payload = {"matrix": values, "tree": tree, "identifiers": frame.index.tolist(),
               "traits": frame.columns.tolist()}
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    panel = runpy.run_path(str(HERE / "panel.py"))
    paper = Figure(config=config, canvas={"width": 170, "height": 176}, rows=1, cols=1,
                   title="Circular clustered heatmap")
    paper[0, 0].custom(panel["draw_clustered_heatmap"], payload=payload,
                       limits=panel["CIRCULAR_LIMITS"], min_size=(220, 220),
                       preferred_aspect=1, box_aspect=1)
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
