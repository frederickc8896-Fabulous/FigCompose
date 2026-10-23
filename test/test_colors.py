"""Test utils/colors.py — palette lookup and bucket logic."""
import pytest
from data_visuals.utils.colors import (
    get_palette, get_palette_flat,
    get_ours_color, list_palettes,
    list_styles, Palette,
)


class TestPaletteBucketLookup:
    def test_2_groups_uses_2_bucket(self):
        p = get_palette(2, "default")
        assert len(p.colors) == 2

    def test_3_groups_bumps_to_5_bucket(self):
        p = get_palette(3, "default")
        assert len(p.colors) == 5

    def test_5_groups_uses_5_bucket(self):
        p = get_palette(5, "default")
        assert len(p.colors) == 5

    def test_6_groups_bumps_to_7_bucket(self):
        p = get_palette(6, "default")
        assert len(p.colors) == 7

    def test_8_groups_bumps_to_10_bucket(self):
        p = get_palette(8, "default")
        assert len(p.colors) == 10

    def test_15_groups_uses_10_bucket(self):
        p = get_palette(15, "default")
        assert len(p.colors) == 10


class TestPaletteStyles:
    def test_cool_style_for_5_groups(self):
        p = get_palette(5, "cool")
        assert p.colors[0] == "#ff6b35"

    def test_warm_style_for_5_groups(self):
        p = get_palette(5, "warm")
        assert p.colors[0] == "#e76f51"

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="没有风格"):
            get_palette(5, "unicorn")

    def test_nonpositive_groups_raises(self):
        with pytest.raises(ValueError, match="> 0"):
            get_palette(0)


class TestPaletteDataClass:
    def test_ours_color_must_be_in_colors(self):
        with pytest.raises(ValueError, match="不在 colors"):
            Palette(colors=["#aaa", "#bbb"], ours_color="#ccc")

    def test_regular_colors_excludes_ours(self):
        p = Palette(colors=["#e74c3c", "#3992ca"], ours_color="#e74c3c")
        assert p.regular_colors == ["#3992ca"]

    def test_to_flat_returns_all(self):
        p = Palette(colors=["#e74c3c", "#3992ca"], ours_color="#e74c3c")
        assert len(p.to_flat()) == 2


class TestPublicApi:
    def test_get_palette_flat_returns_list(self):
        flat = get_palette_flat(4, "cool")
        assert isinstance(flat, list)
        assert len(flat) == 5

    def test_list_palettes_covers_all_buckets(self):
        result = list_palettes()
        assert 2 in result
        assert 5 in result
        assert 7 in result
        assert 10 in result

    def test_list_styles_for_5_groups(self):
        styles = list_styles(5)
        assert "default" in styles
        assert "cool" in styles
        assert "warm" in styles

    def test_get_ours_color(self):
        color = get_ours_color(5, "cool")
        assert color == "#ff6b35"

    def test_legacy_palette_catalogue_excludes_removed_modern_master(self):
        assert list_palettes().keys() == {2, 5, 7, 10}
        assert list_styles(10) == ["default", "muted", "vibrant"]
        assert all("modern" not in styles for styles in list_palettes().values())
