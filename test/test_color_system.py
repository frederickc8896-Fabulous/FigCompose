"""Colour contracts across standalone, grouped and continuous chart paths."""

from copy import deepcopy

from matplotlib.colors import to_rgba
import pytest

from data_visuals.renderer.mpl.canvas import _colour_maps
from data_visuals.renderer.mpl.charts.helpers import color_scheme
from data_visuals.renderer.mpl.config import MplConfig
from data_visuals.themes import get_color_palette, load_theme
from data_visuals.utils.colors import get_color_preset, SEQUENTIAL_SCHEMES


@pytest.mark.parametrize("theme", ["general", "modern"])
def test_standalone_series_and_grouped_series_share_theme_colours(theme):
    cfg = MplConfig(theme)
    spec = {"subplots": [], "color_domains": {"model": ["B", "A"]}}
    colours = _colour_maps(spec, cfg)["model"]

    assert cfg.get_color(0) == colours["A"]
    assert cfg.get_color(1) == colours["B"]
    assert MplConfig(theme, 2).categorical_palette[:2] == list(colours.values())


@pytest.mark.parametrize("palette", ["curated-5-default", "curated-7-warm", "curated-10-muted"])
def test_whole_figure_preset_controls_series_and_continuous_colours(palette):
    cfg = MplConfig("general", palette=palette)
    preset = get_color_preset(palette)
    endpoints = SEQUENTIAL_SCHEMES[preset["sequential"]]

    assert cfg.get_palette(2) == cfg.categorical_palette
    assert cfg.sequential_cmap(0.0) == to_rgba(endpoints[0])
    assert cfg.sequential_cmap(1.0) == to_rgba(endpoints[-1])
    assert cfg.mean_line_color == preset["mean_line"]


def test_preset_resolution_preserves_cached_theme_and_explicit_category_colours():
    original = deepcopy(load_theme("general"))
    cfg = MplConfig("general", palette="curated-5-warm")
    spec = {"subplots": [], "color_domains": {"model": ["A", "B"]},
            "category_colors": {"model": {"A": "#010203"}}}

    assert _colour_maps(spec, cfg)["model"]["A"] == "#010203"
    assert load_theme("general") == original


def test_legacy_custom_theme_explicit_palette_is_shared_by_grouped_charts(monkeypatch):
    theme = {"color": {"categorical": ["#234567", "#765432"]}}
    monkeypatch.setattr("data_visuals.renderer.mpl.config.load_theme", lambda _: theme)
    cfg = MplConfig("custom")
    spec = {"subplots": [], "color_domains": {"model": ["A", "B"]}}

    assert get_color_palette(theme, 2) == theme["color"]["categorical"]
    assert list(_colour_maps(spec, cfg)["model"].values()) == cfg.categorical_palette


def test_theme_default_preset_respects_explicit_theme_colour_values(monkeypatch):
    theme = {"color": {"preset": "curated-5-cool", "mean_line": "#123456"}}
    monkeypatch.setattr("data_visuals.renderer.mpl.config.load_theme", lambda _: theme)

    assert MplConfig("custom").mean_line_color == "#123456"
    assert MplConfig("custom", palette="curated-5-warm").mean_line_color == get_color_preset("curated-5-warm")["mean_line"]
    assert get_color_palette(theme, 2) == MplConfig("custom", 2).categorical_palette


@pytest.mark.parametrize("scheme", ["viridis", ["#ffffff", "#111111"]])
def test_explicit_heatmap_colour_scheme_still_overrides_whole_figure_preset(scheme):
    cfg = MplConfig("general", palette="curated-5-warm")
    cmap = color_scheme({"options": {"color_scheme": scheme}}, cfg)

    if isinstance(scheme, str):
        assert cmap.name == scheme
    else:
        assert cmap(0.0) == to_rgba(scheme[0])
        assert cmap(1.0) == to_rgba(scheme[-1])
    assert cmap(1.0) != cfg.sequential_cmap(1.0)


@pytest.mark.parametrize("palette", ["curated-5-default", "curated-7-warm", "curated-10-muted"])
def test_public_plot_palette_reaches_grouped_ungrouped_and_matrix_charts(palette):
    import matplotlib.pyplot as plt
    import pandas as pd
    from data_visuals import plot

    data = pd.DataFrame({
        "task": ["A", "A", "B", "B"],
        "model": ["Base", "Ours", "Base", "Ours"],
        "score": [0.6, 0.8, 0.7, 0.9],
    })
    figure = plot(data, x="task", group="model", palette=palette, plots=[
        {"kind": "bar", "metric": "score"},
        {"kind": "histogram", "metric": "score", "group": None},
        {"kind": "heatmap", "x": "task", "y": "model", "metric": "score"},
    ])
    assert figure.build().to_dict()["palette"] == palette
    rendered = figure.render()
    try:
        grouped, standalone, matrix = [
            cell["axes"] for cell in rendered._data_visuals_layout["cells"].values()
        ]
        expected = to_rgba(MplConfig("general", palette=palette).get_color(0))[:3]
        assert grouped.patches[0].get_facecolor()[:3] == pytest.approx(expected)
        assert standalone.patches[0].get_facecolor()[:3] == pytest.approx(expected)
        ramp = SEQUENTIAL_SCHEMES[get_color_preset(palette)["sequential"]]
        assert matrix.images[0].cmap(1.0) == to_rgba(ramp[-1])
    finally:
        plt.close(rendered)
