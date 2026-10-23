"""Scientific coordinates, intervals and single-column typography stay intact."""
from pathlib import Path
import json
import struct
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.text import Text
import numpy as np
import pytest

from demo.demo_matched_training import (
    FIGURE_INCHES, STEM, X_LIMITS, Y_LIMITS, COLORS, MARKERS, OFFSETS_PT,
    build_matched_training, export_matched_training,
)
from demo.matched_training_data import PANEL_ORDER, BACKBONE_ORDER, load_matched_training_data

SOURCE = Path(__file__).resolve().parents[1] / "matched_id_training_gains_plot_data.csv"


@pytest.fixture(scope="module")
def study():
    return load_matched_training_data(SOURCE)


def test_two_panels_preserve_all_24_means_and_asymmetric_intervals(study):
    paper = build_matched_training(study)
    figure = paper.render()
    try:
        assert len(figure.axes) == 2
        assert tuple(figure.get_size_inches()) == pytest.approx(FIGURE_INCHES)
        assert paper.build().shared_legend["position"] == "bottom"
        for row, ax in enumerate(figure.axes):
            expected_panel = study["data"].loc[study["data"]["panel"] == PANEL_ORDER[row]]
            markers = {artist._data_visuals_series_key: artist for artist in ax.collections
                       if hasattr(artist, "_data_visuals_series_key")}
            assert set(markers) == set(BACKBONE_ORDER)
            assert sum(len(marker.get_offsets()) for marker in markers.values()) == 12
            assert ax.get_xlim() == X_LIMITS and ax.get_ylim() == Y_LIMITS
            assert ax.get_title() == ("(a) Near-OOD" if row == 0 else "(b) Far-OOD")
            for backbone, marker in markers.items():
                expected = expected_panel.loc[expected_panel["backbone"] == backbone]
                xy = expected[["actual_id_false_reject_pct", "delta_leakage_pp"]].to_numpy(float)
                np.testing.assert_allclose(marker.get_offsets(), xy)
                container = ax._data_visuals_errorbars[backbone]
                _, caps, (lines,) = container.lines
                expected_segments = np.array([
                    [[record.actual_id_false_reject_pct, record.ci95_lower_pp],
                     [record.actual_id_false_reject_pct, record.ci95_upper_pp]]
                    for record in expected.itertuples(index=False)])
                np.testing.assert_allclose(lines.get_segments(), expected_segments)
                visible = marker.get_offset_transform().transform(xy)
                np.testing.assert_allclose(visible - ax.transData.transform(xy),
                                           [[OFFSETS_PT[backbone], 0]] * 4, atol=1e-10)
                assert len(caps) == 2
            guides = [line for line in ax.lines if line.get_label() == "_guide"]
            assert len(guides) == 1
            np.testing.assert_allclose(guides[0].get_ydata(), [0, 0])
        assert figure.axes[0].get_shared_x_axes().joined(*figure.axes)
        assert figure.axes[0].get_shared_y_axes().joined(*figure.axes)
    finally:
        plt.close(figure)


def test_actual_numeric_spacing_legible_ticks_and_bottom_legend(study):
    figure = build_matched_training(study).render()
    try:
        renderer = figure.canvas.get_renderer()
        top, bottom = figure.axes
        assert not top.get_xticklabels()
        labels = bottom.get_xticklabels()
        assert [label.get_text() for label in labels] == ["0.88", "1.88", "4.88", "9.88"]
        np.testing.assert_allclose(bottom.get_xticks(), study["nodes"])
        x_positions = bottom.transData.transform(np.column_stack((bottom.get_xticks(), [0] * 4)))[:, 0]
        gaps = np.diff(x_positions)
        np.testing.assert_allclose(gaps / gaps[0], [1, 3, 5])
        boxes = [label.get_window_extent(renderer) for label in labels]
        assert all(right.x0 - left.x1 >= 2 for left, right in zip(boxes, boxes[1:]))
        assert len(figure.legends) == 1
        legend = figure.legends[0]
        assert [text.get_text() for text in legend.get_texts()] == ["xsmall", "small", "RoBERTa"]
        assert [handle.get_marker() for handle in legend.legend_handles] == [MARKERS[name] for name in BACKBONE_ORDER]
        assert [handle.get_color() for handle in legend.legend_handles] == [COLORS[name] for name in BACKBONE_ORDER]
        xlabel = next(text for text in figure.texts if text.get_text() == "Actual ID false rejection (%)")
        assert legend.get_window_extent(renderer).y1 < xlabel.get_window_extent(renderer).y0
        assert xlabel.get_window_extent(renderer).y1 < boxes[0].y0
    finally:
        plt.close(figure)


def test_all_visible_text_is_eight_point_or_larger_and_inside_canvas(study):
    figure = build_matched_training(study).render()
    try:
        renderer = figure.canvas.get_renderer()
        texts = [artist for artist in figure.findobj(Text) if artist.get_visible() and artist.get_text()]
        assert all(artist.get_fontsize() >= 8 for artist in texts)
        assert all(artist.get_fontproperties().get_name() == "Times New Roman" for artist in texts)
        assert not any("actual_id_false" in artist.get_text() or "delta_leakage" in artist.get_text() for artist in texts)
        for artist in texts:
            box = artist.get_window_extent(renderer)
            assert box.x0 >= -0.5 and box.y0 >= -0.5
            assert box.x1 <= figure.bbox.width + 0.5 and box.y1 <= figure.bbox.height + 0.5
        layout = figure._data_visuals_layout
        zones = [cell["data_zone"] for cell in layout["cells"].values()]
        assert zones[0]["w"] == pytest.approx(zones[1]["w"])
        assert zones[0]["h"] == pytest.approx(zones[1]["h"])
        assert layout["footer_height"] > 0
    finally:
        plt.close(figure)


def test_exports_are_exact_size_vectors_and_keep_ci_provenance(tmp_path):
    before = plt.get_fignums()
    outputs = export_matched_training(SOURCE, tmp_path)
    assert all(path.is_file() for path in outputs)
    assert plt.get_fignums() == before
    svg = ET.parse(tmp_path / f"{STEM}.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) == pytest.approx(3.4 * 72)
    assert float(svg.attrib["height"].removesuffix("pt")) == pytest.approx(4.45 * 72)
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    assert b"/Subtype /Image" not in (tmp_path / f"{STEM}.pdf").read_bytes()
    png = (tmp_path / f"{STEM}.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == (1020, 1335)
    manifest = json.loads((tmp_path / f"{STEM}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["plot_rows"] == 24 and manifest["bootstrap_replicates"] == 5000
    assert manifest["legend_position"] == "bottom"
    caption = (tmp_path / f"{STEM}_caption.md").read_text(encoding="utf-8")
    assert "two near-OOD intervals and one far-OOD interval contain zero" in caption
    assert "without recalculation" in caption
