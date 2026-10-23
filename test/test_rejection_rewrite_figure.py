"""Check that the scientific case-study figure preserves points and units."""

from itertools import combinations
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.transforms import Bbox
import numpy as np
import pytest

from data_visuals.core import Figure
from demo.demo_rejection_rewrite import FIGURE_INCHES, STEM, build_paper_figure, build_figure, export_figure
from demo.rejection_rewrite_data import load_and_summarize


SOURCE = Path(__file__).resolve().parents[1] / "rejection_rewrite_plot_data.csv"


@pytest.fixture(scope="module")
def summary():
    return load_and_summarize(SOURCE)


def test_six_panels_preserve_ten_means_and_the_reference_to_mean_direction(summary):
    figure = build_figure(summary)
    try:
        assert len(figure.axes) == 6
        assert tuple(figure.get_size_inches()) == pytest.approx(FIGURE_INCHES)
        axes = figure.axes
        for index, panel in enumerate(figure._rejection_rewrite_panels):
            ax, data = panel["axis"], panel["data"]
            assert ax.get_xlim() == axes[0].get_xlim() == (0, 6.5)
            assert ax.get_ylim() == axes[0].get_ylim() == (0, 100)
            assert axes[0].get_shared_x_axes().joined(ax, axes[0])
            assert axes[0].get_shared_y_axes().joined(ax, axes[0])
            assert [len(marker.get_offsets()) for marker in panel["markers"]] == [1, 8, 1]
            for kind, marker in zip(("reference", "rewrite", "mean"), panel["markers"]):
                expected = data.loc[data["kind"] == kind, ["id_false_reject_pct", "near_leak_pct"]]
                np.testing.assert_allclose(marker.get_offsets(), expected.to_numpy(float))
            reference, mean = panel["reference"], panel["mean"]
            assert panel["arrow"].xy == pytest.approx((mean["id_false_reject_pct"], mean["near_leak_pct"]))
            assert panel["arrow"].xyann == pytest.approx((reference["id_false_reject_pct"], reference["near_leak_pct"]))
            assert len(ax.lines) == 1
            np.testing.assert_allclose(ax.lines[0].get_xdata(), [5, 5])
            assert ax.get_title().startswith(f"({chr(ord('a') + index)})")
            assert not panel["number_labels"]
            assert len(figure._rejection_rewrite_spec.get_subplot(index // 3, index % 3).computed_data) == 10
    finally:
        plt.close(figure)


def test_three_decimal_auroc_headers_match_the_selected_experiment(summary):
    figure = build_figure(summary)
    try:
        assert [axis.get_title().split("AUROC: ")[1] for axis in figure.axes] == [
            "0.937 → 0.931", "0.925 → 0.916", "0.918 → 0.914",
            "0.933 → 0.933", "0.931 → 0.931", "0.919 → 0.930",
        ]
        assert [text.get_text() for text in figure.legends[0].get_texts()] == [
            "Reference description", "Individual rewrites", "Mean over rewrites",
        ]
    finally:
        plt.close(figure)


def test_font_sizes_label_bounds_and_figure_boundary(summary):
    figure = build_figure(summary, number_rewrites=True)
    try:
        renderer = figure.canvas.get_renderer()
        texts = [item for item in figure.findobj(Text) if item.get_visible() and item.get_text()]
        assert all(item.get_fontsize() >= 8 for item in texts)
        assert all(item.get_fontproperties().get_name() == "Times New Roman" for item in texts)
        for text in texts:
            # Annotation's union extent also contains its leader, both of
            # which must remain inside the final physical Figure boundary.
            box = text.get_window_extent(renderer)
            assert box.x0 >= figure.bbox.x0 - 0.5
            assert box.x1 <= figure.bbox.x1 + 0.5
            assert box.y0 >= figure.bbox.y0 - 0.5
            assert box.y1 <= figure.bbox.y1 + 0.5
        for panel in figure._rejection_rewrite_panels:
            assert {label.get_text() for label in panel["number_labels"]} == set("12345678")
            labels = [label.get_bbox_patch().get_window_extent(renderer) for label in panel["number_labels"]]
            for first, second in combinations(labels, 2):
                overlap = Bbox.intersection(first, second)
                assert overlap is None or overlap.width <= 0.1 or overlap.height <= 0.1
    finally:
        plt.close(figure)


def test_exports_are_fixed_size_vectors_and_300_dpi_raster(tmp_path):
    before = plt.get_fignums()
    outputs = export_figure(SOURCE, tmp_path)
    assert all(path.is_file() for path in outputs)
    assert plt.get_fignums() == before
    svg = ET.parse(tmp_path / f"{STEM}.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) == pytest.approx(7 * 72)
    assert float(svg.attrib["height"].removesuffix("pt")) == pytest.approx(FIGURE_INCHES[1] * 72)
    assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
    ids = [element.attrib["id"] for element in svg.iter() if "id" in element.attrib]
    assert len(ids) == len(set(ids))
    pdf = (tmp_path / f"{STEM}.pdf").read_bytes()
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Image" not in pdf
    size = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf)
    assert size and tuple(map(float, size.groups())) == pytest.approx(tuple(value * 72 for value in FIGURE_INCHES))
    png = (tmp_path / f"{STEM}.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == pytest.approx([value * 300 for value in FIGURE_INCHES], abs=1)


def test_case_uses_real_pipeline_and_a_compact_equal_grid(summary):
    paper_figure = build_paper_figure(summary)
    assert isinstance(paper_figure, Figure)
    spec = paper_figure.build()
    assert spec.canvas["physical"] is True
    assert spec.facets["sharex"] is spec.facets["sharey"] is True
    figure = build_figure(summary)
    try:
        zones = [cell["data_zone"] for cell in figure._data_visuals_layout["cells"].values()]
        assert [zone["w"] for zone in zones] == pytest.approx([zones[0]["w"]] * 6)
        assert [zone["h"] for zone in zones] == pytest.approx([zones[0]["h"]] * 6)
        # A 7 x 4.5 in frame retains readable text while devoting >=48% of
        # its area to actual axes (the earlier manually placed draft used 41%).
        occupied = sum(zone["w"] * zone["h"] for zone in zones)
        assert occupied / (spec.canvas["width"] * spec.canvas["height"]) >= 0.48
        assert zones[0]["x"] / spec.canvas["width"] <= 0.10
        assert zones[3]["y"] - zones[0]["y"] - zones[0]["h"] <= 32
        assert all(not axis.get_xlabel() and not axis.get_ylabel() for axis in figure.axes)
    finally:
        plt.close(figure)
