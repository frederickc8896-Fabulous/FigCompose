"""Read a cohort CSV and draw aligned circular tracks with FigCompose.

python examples/participant_tracks/generate.py [--data cohort.csv] [--out output]
"""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy

import numpy as np
import pandas as pd
from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent


def build_figure(data_path=None, profile_path=None):
    frame = pd.read_csv(data_path or HERE / "data.csv", keep_default_na=False)
    panel = runpy.run_path(str(HERE / "panel.py"))
    required = {"participant", "age", "bmi", "sex", "ethnicity", "response"}
    if not required.issubset(frame) or len(frame) < 3:
        raise ValueError("Supply at least three participants and the six documented columns.")
    if frame.participant.duplicated().any() or (frame.participant.astype(str).str.len() == 0).any():
        raise ValueError("Participant IDs must be nonempty and unique.")
    for name, low, high in (("age", 18, 80), ("bmi", 15, 42)):
        values = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(values).all() or not values.between(low, high).all():
            raise ValueError(f"{name} must be finite and within [{low}, {high}].")
        frame[name] = values
    for column, categories in (("sex", panel["SEX"]), ("ethnicity", panel["ETHNICITY"]),
                               ("response", panel["RESPONSE"])):
        if not frame[column].isin(categories).all():
            raise ValueError(f"Unknown {column} categories; see this example's README.")
    frame = frame.sort_values(["age", "participant"], kind="stable").reset_index(drop=True)
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    paper = Figure(rows=1, cols=1, canvas={"width": 230, "height": 250}, config=config,
                   title="Participant metadata | Aligned circular tracks")
    paper[0, 0].custom(panel["draw_participant_ring"], payload=frame,
                       color_group="metadata", categories=panel["CATEGORIES"],
                       limits=((-1.36, 1.36), (-1.44, 1.28)), min_size=(490, 490),
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
