"""Read a cohort CSV and draw aligned circular tracks with FigCompose.

python examples/participant_tracks/generate.py [--data cohort.csv] [--out output]
"""
from __future__ import annotations
import argparse
from pathlib import Path
import runpy

import pandas as pd
from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent


def build_figure(data_path=None, profile_path=None):
    frame = pd.read_csv(data_path or HERE / "data.csv", keep_default_na=False)
    config = FigureConfig.load(profile_path or HERE / "style.yaml")
    paper = Figure(frame, rows=1, cols=1, canvas={"width": 230, "height": 250}, config=config,
                   title="Participant metadata | Aligned circular tracks")
    paper[0, 0].participant_tracks(
        id="participant", categorical=["sex", "ethnicity", "response"], numeric=["bmi", "age"],
        group="metadata", numeric_ranges={"bmi": [15, 42], "age": [18, 80]},
        numeric_ticks={"bmi": [15, 28, 42], "age": [18, 49, 80]}, order_by="age",
        category_orders={"sex": ["Female", "Male"],
                         "ethnicity": ["Asian", "Black", "Caucasian", "Hispanic"],
                         "response": ["Sensitive", "Intermediate", "Resistant"]},
        track_labels={"sex": "Sex", "ethnicity": "Ethnicity", "response": "Response",
                      "bmi": "BMI", "age": "Age\n(years)"},
        numeric_colors={"bmi": "Male", "age": "Black"}, center_color="Intermediate", accent_color="Black",
        center_note="Synthetic cohort", order_label="Ordered by age",
        note="Inside → out: sex, ethnicity, response, BMI and age.\n"
             "The open sector summarises the same cohort; all values are simulated.",
        chart_opts={"series_styles": {
            category: {"label": f"{heading}: {category}"}
            for heading, categories in (("Sex", ("Female", "Male")),
                                        ("Ethnicity", ("Asian", "Black", "Caucasian", "Hispanic")),
                                        ("Response", ("Sensitive", "Intermediate", "Resistant")))
            for category in categories}},
    )
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
