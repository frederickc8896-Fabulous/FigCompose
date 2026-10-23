"""Test layout/manager.py — parse_aspect and ratio-based layout."""
import pytest
from data_visuals.layout.manager import parse_aspect, build_layout


class TestParseAspect:
    def test_colon_format(self):
        assert parse_aspect("16:9") == pytest.approx(16 / 9)

    def test_slash_format(self):
        assert parse_aspect("4/3") == pytest.approx(4 / 3)

    def test_float_input(self):
        assert parse_aspect(1.5) == 1.5

    def test_tuple_input(self):
        assert parse_aspect((4, 3)) == pytest.approx(4 / 3)

    def test_wide_aspect(self):
        """4:1 wide aspect — width/height = 4."""
        assert parse_aspect("4:1") == 4.0

    def test_tall_aspect(self):
        """1:4 tall aspect — width/height = 0.25."""
        assert parse_aspect("1:4") == 0.25

    def test_one_to_one(self):
        assert parse_aspect("1:1") == 1.0

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="解析宽高比"):
            parse_aspect("invalid")

    def test_non_positive_raises(self):
        with pytest.raises(ValueError):
            parse_aspect("-1:2")


class TestRatioLayout:
    def test_width_and_height_ratios_fill_canvas(self):
        spec = build_layout(
            rows=2,
            cols=3,
            aspect="16:10",
            base="medium",
            width_ratios=[3, 1, 2],
            height_ratios=[2, 1],
        )

        cells = {(cell["row"], cell["col"]): cell for cell in spec["cells"]}

        left = spec["margins"]["left"]
        right = spec["margins"]["right"]
        top = spec["margins"]["top"]
        bottom = spec["margins"]["bottom"]
        gap = spec["grid"]["gap"]
        canvas_w = spec["canvas"]["width"]
        canvas_h = spec["canvas"]["height"]

        usable_w = canvas_w - left - right - 2 * gap
        usable_h = canvas_h - top - bottom - gap

        assert cells[(0, 0)]["w"] == pytest.approx(usable_w * 3 / 6, abs=1.0)
        assert cells[(0, 1)]["w"] == pytest.approx(usable_w * 1 / 6, abs=1.0)
        assert cells[(0, 2)]["w"] == pytest.approx(usable_w * 2 / 6, abs=1.0)
        assert cells[(0, 0)]["h"] == pytest.approx(usable_h * 2 / 3, abs=1.0)
        assert cells[(1, 0)]["h"] == pytest.approx(usable_h * 1 / 3, abs=1.0)

    def test_invalid_width_ratio_length_raises(self):
        with pytest.raises(ValueError, match="width_ratios"):
            build_layout(rows=1, cols=2, width_ratios=[1, 2, 3])

    def test_mixed_layout_uses_uniform_subplot_title_size(self):
        spec = build_layout(
            layout=[[(3, 1), None, None], [(2, 2), None, 1], [None, None, 1]],
            aspect="1:1",
            base="large",
        )

        title_sizes = {cell["font_sizes"]["title"] for cell in spec["cells"]}
        assert len(title_sizes) == 1

        axis_sizes = {cell["font_sizes"]["axis_label"] for cell in spec["cells"]}
        tick_sizes = {cell["font_sizes"]["tick"] for cell in spec["cells"]}
        assert len(axis_sizes) == 1
        assert len(tick_sizes) == 1

    def test_mixed_layout_placeholder_keeps_later_cells_in_correct_column(self):
        spec = build_layout(
            layout=[[(3, 1), None, None], [(2, 2), None, 1], [None, None, 1]],
            aspect="1:1",
            base="large",
        )

        cells = {(cell["row"], cell["col"]): cell for cell in spec["cells"]}
        assert cells[(2, 2)]["x"] == pytest.approx(cells[(1, 2)]["x"], abs=0.1)
        assert cells[(2, 2)]["x"] > cells[(1, 0)]["x"]
