"""The readable view changes the presentation, not the experiment."""
from pathlib import Path
import json
import struct
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.text import Text
import numpy as np
import pandas as pd
import pytest

from demo.demo_rejection_rewrite_comparison import (
    FIGURE_INCHES, METRICS, STEM, TRAINING_POSITIONS, REWRITE_LANE_OFFSET,
    build_comparison, comparison_changes, comparison_data, export_comparison,
)
from demo.rejection_rewrite_data import BACKBONE_ORDER, TRAINING_ORDER, load_and_summarize

SOURCE = Path(__file__).resolve().parents[1] / "rejection_rewrite_plot_data.csv"


@pytest.fixture(scope="module")
def summary():
    return load_and_summarize(SOURCE)


def test_projections_preserve_actual_rates_and_all_eight_rewrites(summary):
    original = summary["points"].copy(deep=True)
    display = comparison_data(summary)
    assert len(display) == 120
    for metric in METRICS:
        projected = display.loc[display["metric"] == metric]
        np.testing.assert_allclose(projected["rate_pct"], original[metric])
        levels = original["training"].map(TRAINING_POSITIONS).to_numpy()
        levels[original["kind"].to_numpy() == "rewrite"] += REWRITE_LANE_OFFSET
        np.testing.assert_allclose(projected["training_position"], levels)
        assert projected.groupby(["backbone", "training", "kind"]).size().to_list() == [1, 1, 8] * 6
    pd.testing.assert_frame_equal(summary["points"], original)
    changes = comparison_changes(summary)
    assert (changes["id_false_reject_pct_change"] < 0).all()
    assert (changes["near_leak_pct_change"] > 0).all()
    np.testing.assert_allclose(changes["near_leak_pct_change"], [36.39375, 9.16875, 34.703125, 9.034375, 33.98125, 4.159375])


def test_before_after_arrows_keep_absolute_values_and_per_metric_scales(summary):
    paper = build_comparison(summary)
    spec = paper.build()
    figure = paper.render()
    try:
        assert spec.grid["rows"] == 3 and spec.grid["cols"] == 2
        assert tuple(figure.get_size_inches()) == pytest.approx(FIGURE_INCHES)
        changes = comparison_changes(summary)
        for (row, col), cell in figure._data_visuals_layout["cells"].items():
            ax = cell["axes"]
            assert ax.get_xlim() == ((0, 6.5) if col == 0 else (0, 100))
            assert len(ax.lines) == (1 if col == 0 else 0)
            if col == 0:
                np.testing.assert_allclose(ax.lines[0].get_xdata(), [5, 5])
                assert [text.get_text() for text in ax.get_yticklabels()] == ["Multi-phrase", "Single-phrase"]
            else:
                assert not ax.get_yticklabels()
            points = spec.get_subplot(row, col).computed_data
            assert len(points) == 20
            markers = {marker._data_visuals_series_key: marker for marker in ax.collections}
            for kind, count in (("reference", 2), ("rewrite", 16), ("mean", 2)):
                expected = points.loc[points["kind"] == kind, ["rate_pct", "training_position"]]
                assert len(markers[kind].get_offsets()) == count
                np.testing.assert_allclose(markers[kind].get_offsets(), expected.to_numpy(float))
            for arrow, training in zip(ax._data_visuals_scatter_arrows, TRAINING_ORDER):
                values = changes.loc[(changes["backbone"] == BACKBONE_ORDER[row]) & (changes["training"] == training)].iloc[0]
                assert arrow.xyann == pytest.approx((values[f"{METRICS[col]}_reference"], TRAINING_POSITIONS[training]))
                assert arrow.xy == pytest.approx((values[f"{METRICS[col]}_rewrite_mean"], TRAINING_POSITIONS[training]))
    finally:
        plt.close(figure)


def test_direct_reading_labels_units_and_bounds(summary):
    figure = build_comparison(summary).render()
    try:
        renderer = figure.canvas.get_renderer()
        texts = [artist for artist in figure.findobj(Text) if artist.get_visible() and artist.get_text()]
        labels = [artist.get_text() for artist in texts]
        assert not any("training_position" in label or "rate_pct" in label or "AUROC" in label for label in labels)
        assert "Training" in labels
        assert "5.35 → 1.22  (−4.13 pp)" in labels
        assert "5.18 → 3.53  (−1.65 pp)" in labels
        assert "27.3 → 63.7  (+36.4 pp)" in labels
        assert sum(len(ax._data_visuals_text_annotations) for ax in figure.axes) == 12
        assert all(artist.get_fontsize() >= 8 for artist in texts)
        for artist in texts:
            box = artist.get_window_extent(renderer)
            assert box.x0 >= figure.bbox.x0 - 0.5 and box.y0 >= figure.bbox.y0 - 0.5
            assert box.x1 <= figure.bbox.x1 + 0.5 and box.y1 <= figure.bbox.y1 + 0.5
        for ax in figure.axes:
            positions = np.concatenate([marker.get_offsets() for marker in ax.collections])
            display_xy = ax.transData.transform(positions)
            for artist in ax._data_visuals_text_annotations:
                box = artist.get_window_extent(renderer).padded(1)
                assert not any(box.contains(*point) for point in display_xy)
    finally:
        plt.close(figure)


def test_exports_keep_vectors_units_and_ranking_audit(tmp_path):
    before = plt.get_fignums()
    outputs = export_comparison(SOURCE, tmp_path)
    assert all(path.is_file() for path in outputs)
    assert plt.get_fignums() == before
    svg = ET.parse(tmp_path / f"{STEM}.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) == pytest.approx(504)
    assert float(svg.attrib["height"].removesuffix("pt")) == pytest.approx(324)
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    pdf = (tmp_path / f"{STEM}.pdf").read_bytes()
    assert b"/Subtype /Image" not in pdf
    png = (tmp_path / f"{STEM}.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == pytest.approx([2100, 1350], abs=1)
    manifest = json.loads((tmp_path / f"{STEM}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scientific_points"] == 60 and manifest["displayed_projections"] == 120
    caption = (tmp_path / f"{STEM}_caption.md").read_text(encoding="utf-8")
    assert "0.937 → 0.931" in caption
    assert "percentage points (pp)" in caption and "not relative percent changes" in caption
    assert "not establish benefits at equal ID false rejection" in caption
