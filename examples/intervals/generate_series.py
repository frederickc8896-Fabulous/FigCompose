"""Six complementary views of paired observations, with managed composition.

Run: python examples/intervals/generate_series.py
The original generate.py still plots supplied bounds, including asymmetric ones.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy

import matplotlib
matplotlib.use("Agg")
import pandas as pd

from data_visuals import FigureConfig
from data_visuals.core import Figure

HERE = Path(__file__).resolve().parent
VIEWS = ("boxplot", "raincloud", "ridgeline", "paired", "estimation", "forest")
OVERVIEW_ORDER = ("raincloud", "ridgeline", "paired", "estimation", "boxplot", "forest")
DESCRIPTIONS = {
    "boxplot": "Box plot: spread and outliers",
    "raincloud": "Raincloud: shape and observations",
    "ridgeline": "Ridgeline: conditions in context",
    "paired": "Paired paths: individual changes",
    "estimation": "Paired estimation: effect and precision",
    "forest": "Intervals: uncertainty of the mean",
}
READING = {
    "boxplot": "箱线图：箱体为Q1–Q3，中线为中位数；须延伸至1.5×IQR内的最远观测，须外点仍显示。它总结分布，不是均值的置信区间。",
    "raincloud": "雨云图：半小提琴按各自峰值等高缩放，比较核密度形状；中线段呈现四分位数，散点保留全部配对差值。点的纵向错位只为防重叠，不增加测量维度。",
    "ridgeline": "山脊图：选定数据集的五个条件各成一层。形状来自Scott带宽的Gaussian KDE，宽窄描述样本分布，不表示均值估计的不确定性。",
    "paired": "配对连线图：每条线连接同一个paired_run的A与B原值，较粗线连接两种方法的均值。只有已知对象对应关系时才能使用配对连线。",
    "estimation": "配对估计图：左侧保留选定数据集的A/B原值与配对关系；右侧为个体配对差值的KDE及均值的95%配对t区间。右轴零点对齐A均值，两侧使用明确区分的量尺。",
    "forest": "差值区间图：汇总全部数据集与条件的15个均值和95%配对t区间，直接使用已核对的预计算上下界。区间跨零不等于证明两者等效。",
}


def prepare(data_path=None, paired_path=None, *, condition=4):
    module = runpy.run_path(str(HERE / "series_data.py"))
    return module["prepare_series"](
        HERE / "paired.csv" if paired_path is None else Path(paired_path),
        HERE / "data.csv" if data_path is None else Path(data_path), condition=condition)


def build_figure(data_path=None, profile_path=None, *, paired_path=None,
                 condition=4, view="overview", bundle=None):
    if view not in ("overview", *VIEWS):
        raise ValueError(f"Unknown series view: {view!r}")
    config = FigureConfig.load(HERE / "series_style.yaml" if profile_path is None else profile_path)
    bundle = prepare(data_path, paired_path, condition=condition) if bundle is None else bundle
    support = None  # Kept in panel helper signatures for existing callers.
    overview = view == "overview"
    # This adapter preserves every original ID/value. Native pair charts take
    # an explicit long table; supplied intervals remain the exact CSV values.
    pair_frames = []
    for level, column in (("A", "method_a_pct"), ("B", "method_b_pct")):
        frame = bundle["paired"].copy()
        frame["measurement"] = level
        frame["measurement_value"] = frame[column]
        frame["record_type"] = "paired_observation"
        frame = frame.merge(bundle["summary"][["dataset", "condition", "ci95_lower_pp", "ci95_upper_pp"]],
                            on=["dataset", "condition"], how="left", validate="many_to_one", sort=False)
        pair_frames.append(frame)
    native_frame = pd.concat((bundle["frame"], *pair_frames), ignore_index=True, sort=False)
    # Empty fields belong to other record types. Keep them as JSON null rather
    # than NaN while retaining the dtype of complete measurement columns.
    for column in native_frame:
        if native_frame[column].isna().any():
            native_frame[column] = native_frame[column].astype(object).where(native_frame[column].notna(), None)
    paper = Figure(data=native_frame, config=config,
                   rows=3 if overview else 1, cols=2 if overview else 1,
                   canvas={"width": 250 if overview else 180},
                   title="Six ways to see change" if overview else DESCRIPTIONS[view])
    for index, name in enumerate(OVERVIEW_ORDER if overview else (view,)):
        row, col = divmod(index, 2) if overview else (0, 0)
        if name in ("boxplot", "raincloud", "paired"):
            detail = f"Condition {bundle['condition']}"
        elif name in ("ridgeline", "estimation"):
            detail = bundle["ridge_dataset"]
            if name == "estimation":
                detail += f", condition {bundle['condition']}"
        else:
            detail = "All conditions, mean and 95% CI"
        kind = {"boxplot": "Box plot", "raincloud": "Raincloud", "ridgeline": "Ridgeline",
                "paired": "Paired paths", "estimation": "Paired estimation", "forest": "Intervals"}[name]
        title = (f"{index + 1:02d}  {kind} | {detail}" if overview else detail)
        module = runpy.run_path(str(HERE / "series_panels" / f"{name}.py"))
        module["add_panel"](paper[row, col], bundle, support, title=title)
    return paper


def generate(data_path=None, profile_path=None, *, paired_path=None, condition=4,
             out=None, views=("overview", *VIEWS), write_report=False):
    destination = HERE / "series" if out is None else Path(out)
    destination.mkdir(parents=True, exist_ok=True)
    bundle = prepare(data_path, paired_path, condition=condition)
    config = FigureConfig.load(HERE / "series_style.yaml" if profile_path is None else profile_path)
    export = runpy.run_path(str(HERE.parent / "_export.py"))["export_figure"]
    results = []
    for view in views:
        target = destination if view == "overview" else destination / view
        paper = build_figure(profile_path=profile_path, bundle=bundle, view=view)
        result = export(paper, target, config=config, write_report=write_report)
        result["destination"] = target.relative_to(destination).as_posix()
        result["view"] = view
        results.append(result)
    manifest = {"synthetic": True, "focus_condition": condition,
                "ridge_dataset": bundle["ridge_dataset"], "observations": len(bundle["paired"]),
                "focus_pairs": len(bundle["focus"]), "estimates": len(bundle["summary"]),
                "views": results}
    (destination / "series_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_index(destination, bundle)
    return manifest


def write_index(destination, bundle):
    notes = ["# 差异与不确定性 · 六图系列", "",
             "新版以雨云与山脊开场：饱满轮廓、完整观测点和醒目的效应读数，沿分布→配对→汇总的顺序阅读。",
             "一份模拟配对数据，六种互补视角。整图画布、标题、字体、共享图例和导出由FigCompose管理。",
             "六格全部使用原生图种：raincloud、ridgeline、paired、estimation、box，以及带给定区间的scatter。", "",
             f"共有{len(bundle['paired'])}条配对观测、{len(bundle['summary'])}个原始汇总估计。"
             f"箱线、雨云和配对连线选条件{bundle['condition']}；"
             f"山脊图展示{bundle['ridge_dataset']}的全部条件；配对估计选该数据集与焦点条件；"
             "区间图汇总全部条件。pp表示百分点。", ""]
    if (destination / "figure.png").exists():
        notes += ["[六图总览 PNG](figure.png) · [SVG](figure.svg)", "", "![六图总览](preview.png)", ""]
    notes += ["| 图表 | 读法 | 独立成图 |", "|---|---|---|"]
    for view in VIEWS:
        folder = destination / view
        if not (folder / "figure.png").exists():
            continue
        notes.append(f"| {DESCRIPTIONS[view]} | {READING[view]} | [PNG]({view}/figure.png) · [SVG]({view}/figure.svg) |")
        (folder / "README.md").write_text(
            f"# {DESCRIPTIONS[view]}\n\n{READING[view]}\n\n"
            f"本图来自相同的模拟配对数据，焦点条件为{bundle['condition']}；"
            "具体子集见图中标题。不要合并不同条件的样本后再当成独立重复。\n\n"
            f"![{DESCRIPTIONS[view]}](preview.png)\n\n"
            "[返回系列索引](../README.md)\n", encoding="utf-8")
    notes += ["", "源CSV保持不变：分布形状来自真实配对差值，CI来自同一批配对差值的t区间。"
              "所有数据均为模拟，不代表实验结论。", ""]
    (destination / "README.md").write_text("\n".join(notes), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=HERE / "data.csv", help="Supplied paired-t estimates")
    parser.add_argument("--paired", type=Path, default=HERE / "paired.csv", help="Original paired observations")
    parser.add_argument("--profile", type=Path, default=HERE / "series_style.yaml")
    parser.add_argument("--condition", type=int, default=4)
    parser.add_argument("--view", choices=("all", "overview", *VIEWS), default="all")
    parser.add_argument("--out", type=Path, default=HERE / "series")
    args = parser.parse_args()
    views = ("overview", *VIEWS) if args.view == "all" else (args.view,)
    generate(args.data, args.profile, paired_path=args.paired, condition=args.condition,
             out=args.out, views=views)


if __name__ == "__main__":
    main()
