"""Typography contracts for a figure-wide canvas scale."""

import matplotlib.pyplot as plt
from matplotlib.text import Text
import pytest

from data_visuals.core import Figure
from data_visuals.layout.manager import build_layout
from data_visuals.layout.sizing import (
    DEFAULT_FONT_RATIOS,
    DEFAULT_LIMITS,
    compute_figure_font_sizes,
    compute_sizing,
)


ROLE_KEYS = [
    ("main_title", "main_title"),
    ("figure_cell_title", "title"),
    ("figure_axis_label", "axis_label"),
    ("figure_tick_label", "tick"),
    ("figure_legend", "legend"),
]
UNBOUNDED_LIMITS = {key: (0, 10000) for key in DEFAULT_LIMITS}


def _layout_fonts(layout):
    """Read the public layout result, checking every subplot agrees."""
    cell_fonts = layout["cells"][0]["font_sizes"]
    for cell in layout["cells"]:
        assert cell["font_sizes"] == cell_fonts
        assert cell["legend"]["font_size"] == cell_fonts["legend"]
    if layout["shared_legend"]["enabled"]:
        assert layout["shared_legend"]["font_size"] == cell_fonts["legend"]
    return {"main_title": layout["title"]["font_size"], **cell_fonts}


@pytest.mark.parametrize("width,height", [(1200, 900), (1800, 600), (500, 400)])
def test_rotating_canvas_preserves_every_text_role(width, height):
    assert compute_figure_font_sizes(width, height) == compute_figure_font_sizes(height, width)


def test_extending_only_canvas_long_side_preserves_typography():
    assert compute_figure_font_sizes(900, 600) == compute_figure_font_sizes(1800, 600)


def test_rescaling_canvas_rescales_all_roles_together_without_clamps():
    initial = compute_figure_font_sizes(900, 600, font_limits=UNBOUNDED_LIMITS)
    enlarged = compute_figure_font_sizes(1800, 1200, font_limits=UNBOUNDED_LIMITS)

    assert enlarged == pytest.approx({role: size * 2 for role, size in initial.items()})


@pytest.mark.parametrize("grid", [
    {"rows": 1, "cols": 1},
    {"rows": 3, "cols": 4},
    {"rows": 2, "cols": 2, "width_ratios": [3, 1], "height_ratios": [1, 2]},
    {"layout": [[(3, 1), None, None], [(2, 2), None, 1], [None, None, 1]]},
])
def test_grid_and_span_topology_do_not_change_figure_typography(grid):
    canvas = {"canvas_width": 1600, "canvas_height": 1200, "shared_legend": True}
    reference = build_layout(rows=1, cols=1, **canvas)
    actual = build_layout(**grid, **canvas)

    assert _layout_fonts(actual) == _layout_fonts(reference)


def test_low_level_sizing_shares_the_same_figure_typography_for_all_cells():
    reference = _layout_fonts(build_layout(rows=1, cols=1, canvas_width=1200, canvas_height=900))
    sizing = compute_sizing(rows=3, cols=4, canvas_width=1200, canvas_height=900)

    assert sizing.main_title_font_size == pytest.approx(reference["main_title"], abs=0.05)
    for cell in sizing.cells.values():
        assert {
            "title": cell.title_font_size,
            "axis_label": cell.axis_label_font_size,
            "tick": cell.tick_label_font_size,
            "legend": cell.legend_font_size,
        } == pytest.approx({role: size for role, size in reference.items()
                            if role != "main_title"}, abs=0.05)


def test_cell_first_typography_follows_actual_canvas_instead_of_reference_grid():
    snapshots = []
    for count in (1, 2, 3):
        cell_first = build_layout(rows=count, cols=count, cell_base="small", shared_legend=True)
        canvas = cell_first["canvas"]
        explicit_canvas = build_layout(rows=count, cols=count,
                                       canvas_width=canvas["width"],
                                       canvas_height=canvas["height"], shared_legend=True)
        actual = _layout_fonts(cell_first)
        assert actual == _layout_fonts(explicit_canvas)
        snapshots.append(actual)

    for smaller, larger in zip(snapshots, snapshots[1:]):
        # Lower bounds can briefly keep the smallest legend/tick sizes equal.
        assert all(larger[role] >= smaller[role] for role in smaller)
    assert all(snapshots[-1][role] > snapshots[0][role] for role in snapshots[0])


def test_output_dpi_preserves_spec_and_rendered_text_sizes(sample_df):
    snapshots = []
    rendered = []
    try:
        for dpi in (72, 300):
            figure = Figure(data=sample_df, rows=1, cols=1, dpi=dpi, title="Overview")
            figure[0, 0].bar(x="method", y="accuracy", group="dataset", title="Accuracy")
            spec = figure.build().to_dict()
            image = figure.render()
            rendered.append(image)
            assert image.legends
            snapshots.append((spec["title"]["font_size"],
                              spec["subplots"][0]["font_sizes"],
                              sorted((text.get_text(), text.get_fontsize())
                                     for text in image.findobj(Text) if text.get_text())))

        assert snapshots[0] == snapshots[1]
    finally:
        for image in rendered:
            plt.close(image)


@pytest.mark.parametrize("config_key,role", ROLE_KEYS)
def test_role_ratio_and_limits_are_independent_and_flow_into_layout(config_key, role):
    canvas = {"canvas_width": 1600, "canvas_height": 1000}
    initial = compute_figure_font_sizes(**canvas, font_limits=UNBOUNDED_LIMITS)
    ratios = {config_key: DEFAULT_FONT_RATIOS[config_key] * 1.5}
    enlarged = compute_figure_font_sizes(**canvas, font_ratios=ratios, font_limits=UNBOUNDED_LIMITS)
    assert enlarged[role] == pytest.approx(initial[role] * 1.5)
    assert {key: size for key, size in enlarged.items() if key != role} == {
        key: size for key, size in initial.items() if key != role}

    configured = build_layout(rows=2, cols=2, font_ratios=ratios,
                              font_limits=UNBOUNDED_LIMITS, **canvas)
    assert _layout_fonts(configured) == pytest.approx(enlarged, abs=0.05)

    for limits, expected in [
        ((0, initial[role] * 0.75), initial[role] * 0.75),
        ((initial[role] * 1.25, initial[role] * 2), initial[role] * 1.25),
    ]:
        bounds = {**UNBOUNDED_LIMITS, config_key: limits}
        limited = compute_figure_font_sizes(**canvas, font_limits=bounds)
        assert limited[role] == pytest.approx(expected)
        assert {key: size for key, size in limited.items() if key != role} == {
            key: size for key, size in initial.items() if key != role}
        layout = build_layout(rows=2, cols=2, font_limits=bounds, **canvas)
        assert _layout_fonts(layout) == pytest.approx(limited, abs=0.051)
