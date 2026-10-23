"""The original curated combinations remain exact, reusable Figure presets."""

from copy import deepcopy

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import pandas as pd
import pytest

from data_visuals import plot
from data_visuals.renderer.mpl.config import MplConfig
from data_visuals.themes import get_color_palette, load_theme
from data_visuals.utils.colors import (
    SEQUENTIAL_SCHEMES,
    get_color_preset,
    get_palette,
    get_palette_flat,
    list_color_presets,
)


CURATED = [
    (size, style)
    for size, styles in (
        (2, ("default", "cool", "warm")),
        (5, ("default", "cool", "warm")),
        (7, ("default", "cool", "warm")),
        (10, ("default", "muted", "vibrant")),
    )
    for style in styles
]


# The selected hex values and their order are user-owned palette data.
ORIGINAL_COLOURS = {
    "curated-2-default": ["#e74c3c", "#3992ca"],
    "curated-2-cool": ["#1e96fc", "#0353a4"],
    "curated-2-warm": ["#e67e22", "#539ecd"],
    "curated-5-default": ["#e63946", "#fedfd4", "#94d2bd", "#0077b6", "#1d3557"],
    "curated-5-cool": ["#ff6b35", "#f7c59f", "#efefd0", "#1976d2", "#0d47a1"],
    "curated-5-warm": ["#e76f51", "#f4a261", "#e9c46a", "#2a9d8f", "#264653"],
    "curated-7-default": ["#d81159", "#e05400", "#fd8021", "#ffd373", "#00a6fb", "#4361ee", "#2c497f"],
    "curated-7-cool": ["#fb8500", "#fcab64", "#a0ced9", "#6db2c4", "#489fb5", "#37718e", "#457b9d"],
    "curated-7-warm": ["#eb5e28", "#f9a03f", "#f6b049", "#f3c053", "#a1c349", "#94b33d", "#6a8532"],
    "curated-10-default": ["#f94144", "#f3722c", "#f8961e", "#f9844a", "#f9c74f", "#90be6d", "#43aa8b", "#4d908e", "#577590", "#277da1"],
    "curated-10-muted": ["#65010c", "#cb1b16", "#ef3c2d", "#f26a4f", "#f29479", "#fedfd4", "#9dcee2", "#4091c9", "#1368aa", "#033270"],
    "curated-10-vibrant": ["#fb9017", "#fb8500", "#fd9e02", "#ffb703", "#023047", "#126782", "#219ebc", "#58b4d1", "#73bfdc", "#8ecae6"],
}


@pytest.mark.parametrize("name,expected", ORIGINAL_COLOURS.items())
def test_original_selected_hex_values_and_order_are_unchanged(name, expected):
    assert get_palette_flat(1, name) == expected


@pytest.mark.parametrize("size,style", CURATED)
def test_original_combination_is_fixed_across_smaller_domains(size, style):
    name = f"curated-{size}-{style}"
    original = get_palette(size, style).colors
    assert name in list_color_presets()
    theme = {"color": {"preset": name}}
    for count in (0, 1, size):
        assert get_color_palette(theme, count) == original
        assert MplConfig("modern", count, palette=name).categorical_palette == original
    assert get_palette_flat(1, name) == original
    assert get_palette_flat(size, name) == original
    for resolve in (
        lambda: get_palette_flat(size + 1, name),
        lambda: get_color_palette(theme, size + 1),
        lambda: MplConfig("general", size + 1, palette=name),
    ):
        with pytest.raises(ValueError, match="curated"):
            resolve()


def _data():
    return pd.DataFrame({
        "task": ["A", "A", "B", "B"],
        "model": ["Base", "Ours", "Base", "Ours"],
        "score": [0.6, 0.8, 0.7, 0.9],
    })


def test_public_plot_uses_curated_colours_for_mixed_charts_without_mutating_source():
    original = deepcopy(get_palette(5, "default"))
    original_theme = deepcopy(load_theme("modern"))
    preset = get_color_preset("curated-5-default")
    figure = plot(_data(), x="task", group="model", style="modern",
                  palette="curated-5-default", cols=2, plots=[
                      {"kind": "bar", "metric": "score"},
                      {"kind": "line", "metric": "score"},
                      {"kind": "histogram", "metric": "score", "group": None},
                      {"kind": "heatmap", "x": "task", "y": "model", "metric": "score"},
                  ])
    rendered = figure.render()
    try:
        bar, line, histogram, heatmap = [
            cell["axes"] for cell in rendered._data_visuals_layout["cells"].values()
        ]
        expected = [to_rgba(color) for color in original.colors]
        assert bar.patches[0].get_facecolor() == pytest.approx(expected[0])
        assert bar.patches[2].get_facecolor() == pytest.approx(expected[1])
        assert [to_rgba(item.get_color()) for item in line.lines] == expected[:2]
        assert histogram.patches[0].get_facecolor()[:3] == pytest.approx(expected[0][:3])
        ramp = SEQUENTIAL_SCHEMES[preset["sequential"]]
        assert heatmap.images[0].cmap(0.0) == to_rgba(ramp[0])
        assert heatmap.images[0].cmap(1.0) == to_rgba(ramp[-1])
    finally:
        plt.close(rendered)
    assert get_palette(5, "default") == original
    assert load_theme("modern") == original_theme


def test_filtered_panel_keeps_its_position_in_the_full_original_colour_domain():
    data = pd.DataFrame({"epoch": [1, 1, 1, 2, 2, 2],
                         "model": ["A", "B", "C"] * 2,
                         "score": [0.5, 0.6, 0.7, 0.6, 0.7, 0.8]})
    figure = plot(data, x="epoch", group="model", palette="curated-5-default", plots=[
        {"kind": "bar", "metric": "score"},
        {"kind": "line", "metric": "score", "y_columns": ["C"]},
    ])
    rendered = figure.render()
    try:
        original = get_palette(5, "default").colors
        assert list(rendered._data_visuals_layout["color_maps"]["model"].values()) == original[:3]
        line = list(rendered._data_visuals_layout["cells"].values())[1]["axes"]
        assert to_rgba(line.lines[0].get_color()) == to_rgba(original[2])
    finally:
        plt.close(rendered)


def test_over_capacity_render_fails_without_leaving_a_matplotlib_figure():
    data = pd.DataFrame({"task": ["A"] * 3, "model": ["A", "B", "C"],
                         "score": [0.5, 0.6, 0.7]})
    before = plt.get_fignums()
    with pytest.raises(ValueError, match="curated"):
        figure = plot(data, x="task", group="model", palette="curated-2-default",
                      plots=[{"kind": "bar", "metric": "score"}])
        figure.render()
    assert plt.get_fignums() == before


def test_curated_preset_resolves_the_original_source_instead_of_a_hex_copy(monkeypatch):
    source = get_palette(5, "default")
    changed = ["#123456", *source.colors[1:]]
    monkeypatch.setattr(source, "colors", changed)
    cfg = MplConfig("general", palette="curated-5-default")
    assert cfg.categorical_palette == changed
    assert cfg.trend_line_color == changed[0]
    cfg.categorical_palette[0] = "#654321"
    assert source.colors == changed


@pytest.mark.parametrize("name", [
    "cool", "warm", "mixed", "modern", "paper-cool", "paper-warm", "paper-mixed",
    "curated-10-modern",
])
def test_removed_colour_families_are_rejected_as_whole_figure_presets(name):
    with pytest.raises(ValueError, match="未知颜色预设"):
        get_color_preset(name)
    with pytest.raises(ValueError, match="未知颜色预设"):
        MplConfig("general", palette=name)


def test_only_original_selected_combinations_and_sequential_schemes_are_registered():
    assert list_color_presets() == [f"curated-{size}-{style}" for size, style in CURATED]
    assert set(SEQUENTIAL_SCHEMES) == {"warm-cool", "coastal", "blues", "amber", "rose"}


@pytest.mark.parametrize("theme", ["general", "modern"])
def test_default_theme_keeps_original_ten_colour_combination(theme):
    assert load_theme(theme)["color"]["preset"] == "curated-10-default"
    assert MplConfig(theme).categorical_palette == get_palette(10, "default").colors


@pytest.mark.parametrize("size", [2, 5, 7, 10])
def test_removed_modern_palette_cannot_be_resolved_through_legacy_lookup(size):
    with pytest.raises(ValueError, match="modern"):
        get_palette(size, "modern")
