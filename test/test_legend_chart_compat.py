"""Legend customization applies to existing bars and curves without data edits."""

import matplotlib.pyplot as plt
from matplotlib.container import BarContainer
from matplotlib.legend import Legend
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import pytest

from data_visuals.core import Figure


@pytest.fixture(autouse=True)
def close_test_figures():
    before = set(plt.get_fignums())
    yield
    for number in set(plt.get_fignums()) - before:
        plt.close(number)


def _legends(figure):
    candidates = list(figure.legends)
    for cell in figure._data_visuals_layout["cells"].values():
        candidates.extend(cell["legends"])
    return list({id(legend): legend for legend in candidates if isinstance(legend, Legend)}.values())


def _series(ax, kind):
    if kind == "line":
        return {line.get_label(): (line.get_xdata(), line.get_ydata(), line.get_color())
                for line in ax.lines if not line.get_label().startswith("_")}
    return {container.get_label(): (
        [bar.get_x() + bar.get_width() / 2 for bar in container.patches],
        [bar.get_height() for bar in container.patches],
        container.patches[0].get_facecolor(),
    ) for container in ax.containers if isinstance(container, BarContainer)}


@pytest.mark.parametrize("kind", ["bar", "line"])
def test_multi_metric_order_and_display_labels_preserve_every_value_and_color(kind):
    source = pd.DataFrame({"epoch": [1, 2, 3], "precision": [0.6, 0.7, 0.8],
                           "recall": [0.5, 0.65, 0.75]})
    untouched = source.copy(deep=True)
    papers, rendered = [], []
    for options in ({"scope": "local", "position": "top"},
                    {"scope": "local", "position": "bottom", "ncols": 2,
                     "order": ["recall", "precision"],
                     "labels": {"precision": "Precision", "recall": "Sensitivity"}}):
        paper = Figure(data=source, rows=1, cols=1, legend=options,
                       canvas={"width": 110, "height": 80})
        paper[0, 0].set(kind, x="epoch", y=["precision", "recall"])
        papers.append(paper)
        rendered.append(paper.render())
    legends = _legends(rendered[1])
    assert len(legends) == 1
    assert [text.get_text() for text in legends[0].get_texts()] == ["Sensitivity", "Precision"]
    before, after = (_series(figure.axes[0], kind) for figure in rendered)
    assert set(before) == set(after) == {"precision", "recall"}
    for key in before:
        for original, customized in zip(before[key][:2], after[key][:2]):
            np.testing.assert_allclose(original, customized)
        assert before[key][2] == after[key][2]
        np.testing.assert_allclose(after[key][1], source[key])
    pd.testing.assert_frame_equal(papers[0].build().subplots[0].computed_data,
                                  papers[1].build().subplots[0].computed_data)
    pd.testing.assert_frame_equal(source, untouched)


@pytest.mark.parametrize("kind", ["bar", "line"])
def test_forced_local_and_hidden_grouped_legends_preserve_chart_values(kind):
    source = pd.DataFrame({"x": [1, 2, 1, 2], "y": [2.0, 3.0, 5.0, 7.0],
                           "method": ["A", "A", "B", "B"]})
    figures = []
    for legend in ({"scope": "local", "position": "bottom"}, False):
        paper = Figure(data=source, rows=1, cols=2, legend=legend,
                       canvas={"width": 160, "height": 90})
        for col in range(2):
            paper[0, col].set(kind, x="x", y="y", group="method")
        assert paper.build().shared_legend["enabled"] is False
        figures.append(paper.render())
    assert len(_legends(figures[0])) == 2
    assert not _legends(figures[1])
    for shown, hidden in zip(figures[0].axes, figures[1].axes):
        shown_series, hidden_series = _series(shown, kind), _series(hidden, kind)
        assert set(shown_series) == set(hidden_series) == {"A", "B"}
        for key in shown_series:
            np.testing.assert_allclose(shown_series[key][1], hidden_series[key][1])
            assert shown_series[key][2] == hidden_series[key][2]


@pytest.mark.parametrize("kind", ["bar", "line"])
def test_explicit_null_panel_fontsize_restores_theme_default(kind):
    source = pd.DataFrame({"x": [1, 2, 1, 2], "y": [2.0, 3.0, 5.0, 7.0],
                           "method": ["A", "A", "B", "B"]})
    paper = Figure(data=source, rows=1, cols=2, theme="modern",
                   legend={"scope": "shared", "fontsize": 11, "position": "top"},
                   canvas={"width": 160, "height": 90})
    paper[0, 0].set(kind, x="x", y="y", group="method")
    paper[0, 1].set(kind, x="x", y="y", group="method",
                    chart_opts={"legend": {"fontsize": None}})
    figure = paper.render()
    legends = _legends(figure)
    assert len(legends) == 2
    assert sorted({text.get_fontsize() for legend in legends for text in legend.get_texts()}) == [8, 11]
    assert paper.build().subplots[1].font_sizes["legend"] == 8


@pytest.mark.parametrize("kind", ["bar", "line"])
def test_explicit_shared_multi_metric_legend_is_reused_by_both_panels(kind):
    source = pd.DataFrame({"epoch": [1, 2, 3], "precision": [0.6, 0.7, 0.8],
                           "recall": [0.5, 0.65, 0.75]})
    paper = Figure(data=source, rows=1, cols=2,
                   legend={"scope": "shared", "position": "bottom", "ncols": 2,
                           "order": ["recall", "precision"],
                           "labels": {"precision": "Precision", "recall": "Sensitivity"}},
                   canvas={"width": 160, "height": 90})
    for col in range(2):
        paper[0, col].set(kind, x="epoch", y=["precision", "recall"])
    spec = paper.build()
    assert spec.shared_legend["enabled"] is True
    assert spec.shared_legend["group_column"] == "__measures__"
    figure = paper.render()
    legends = _legends(figure)
    assert len(legends) == 1
    assert all(not cell["legends"] for cell in figure._data_visuals_layout["cells"].values())
    legend = legends[0]
    assert [text.get_text() for text in legend.get_texts()] == ["Sensitivity", "Precision"]
    assert all(isinstance(handle, Line2D if kind == "line" else Patch)
               for handle in legend.legend_handles)
    for ax in figure.axes:
        series = _series(ax, kind)
        assert set(series) == {"precision", "recall"}
        for key in series:
            np.testing.assert_allclose(series[key][1], source[key])

