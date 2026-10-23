"""Behavioral coverage for Matplotlib exports and their compute inputs."""

from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure as MatplotlibFigure
import pandas as pd
import pytest

from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.renderer import export


def _figure(sample_df, **kwargs):
    figure = Figure(data=sample_df, rows=1, cols=1, **kwargs)
    figure[0, 0].bar(x="method", y="accuracy", group="dataset")
    return figure


def _png_size(path):
    return struct.unpack(">II", path.read_bytes()[16:24])


@pytest.mark.parametrize("options", [{}, {"backend": "matplotlib"}])
def test_render_returns_a_matplotlib_figure(sample_df, options):
    figure = _figure(sample_df)
    rendered = figure.render(**options)
    try:
        assert isinstance(rendered, MatplotlibFigure)
        assert len(rendered.axes) == 1
    finally:
        plt.close(rendered)


@pytest.mark.parametrize("backend", ["vega", "matplotib"])
@pytest.mark.parametrize("operation", ["render", "show", "figure_display", "save", "to_svg", "to_png", "to_pdf", "display"])
def test_removed_or_unknown_backend_is_rejected(operation, backend, sample_df, tmp_path):
    figure = _figure(sample_df)
    with pytest.raises(ValueError, match="Unknown backend"):
        if operation in {"render", "show", "figure_display"}:
            method = "display" if operation == "figure_display" else operation
            getattr(figure, method)(backend=backend)
        elif operation == "display":
            export.display(figure.build(), backend=backend)
        else:
            getattr(export, operation)(figure.build(), tmp_path / "test.svg", backend=backend)


def test_png_uses_spec_dpi_override_and_multiplicative_scale(sample_df, tmp_path):
    figure = _figure(sample_df, dpi=100, title="Fixed complete canvas")
    spec = figure.build()
    rendered = figure.render()
    physical_size = rendered.get_size_inches()
    plt.close(rendered)
    before = plt.get_fignums()
    with matplotlib.rc_context({"savefig.bbox": "tight", "savefig.pad_inches": 2}):
        export.save(spec, tmp_path / "default.png")
        export.save(spec, tmp_path / "override.png", dpi=200)
        export.save(spec, tmp_path / "scaled.png", dpi=100, scale=2)
        export.save(spec, tmp_path / "combined.png", dpi=200, scale=1.5)
    assert _png_size(tmp_path / "default.png") == pytest.approx(physical_size * 100, abs=1)
    assert _png_size(tmp_path / "override.png") == pytest.approx(physical_size * 200, abs=1)
    assert _png_size(tmp_path / "scaled.png") == _png_size(tmp_path / "override.png")
    assert _png_size(tmp_path / "combined.png") == pytest.approx(physical_size * 300, abs=1)
    assert plt.get_fignums() == before


@pytest.mark.parametrize("kwargs", [{"dpi": 0}, {"dpi": -1}, {"scale": 0}, {"scale": float("nan")}])
def test_invalid_raster_resolution_is_rejected(sample_df, tmp_path, kwargs):
    with pytest.raises(ValueError, match="positive finite"):
        export.save(_figure(sample_df).build(), tmp_path / "bad.png", **kwargs)


def test_svg_and_pdf_export_the_complete_canvas(sample_df, tmp_path):
    figure = _figure(sample_df, title="Static exports")
    rendered = figure.render()
    expected_points = rendered.get_size_inches() * 72
    plt.close(rendered)
    with matplotlib.rc_context({"savefig.bbox": "tight"}):
        figure.render(tmp_path / "figure.svg")
        figure.render(tmp_path / "figure.pdf")
    svg = ET.parse(tmp_path / "figure.svg").getroot()
    assert float(svg.attrib["width"].removesuffix("pt")) == pytest.approx(expected_points[0])
    assert float(svg.attrib["height"].removesuffix("pt")) == pytest.approx(expected_points[1])
    assert (tmp_path / "figure.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("suffix", [".svg", ".png", ".pdf"])
def test_failed_saves_close_the_created_figure(sample_df, tmp_path, suffix):
    before = plt.get_fignums()
    with pytest.raises(OSError):
        export.save(_figure(sample_df).build(), tmp_path / "missing" / f"figure{suffix}")
    assert plt.get_fignums() == before


def test_show_and_display_default_to_inline_matplotlib(sample_df, monkeypatch):
    import IPython.display
    seen = []
    monkeypatch.setattr(IPython.display, "display", seen.append)
    before = plt.get_fignums()
    figure = _figure(sample_df)
    figure.show()
    figure.display()
    export.display(figure.build())
    assert len(seen) == 3
    assert all(isinstance(item, MatplotlibFigure) for item in seen)
    assert plt.get_fignums() == before


def test_inline_display_failure_also_closes_figure(sample_df, monkeypatch):
    import IPython.display
    def fail(_figure):
        raise RuntimeError("display failed")
    monkeypatch.setattr(IPython.display, "display", fail)
    before = plt.get_fignums()
    with pytest.raises(RuntimeError, match="display failed"):
        _figure(sample_df).show()
    assert plt.get_fignums() == before


def test_csv_plot_and_all_exports_work_without_removed_dependencies(tmp_path):
    script = """
import importlib.abc
import pathlib
import sys
class NoRemovedDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'altair', 'vl_convert'}:
            raise AssertionError('Unexpected removed dependency: ' + fullname)
sys.meta_path.insert(0, NoRemovedDependencies())
import pandas as pd
from data_visuals import plot
import matplotlib.pyplot as plt
output = pathlib.Path(sys.argv[1])
source = output / 'data.csv'
pd.DataFrame({'x': ['a', 'b'], 'y': [1, 2]}).to_csv(source, index=False)
figure = plot(source, x='x', plots=[{'kind': 'bar', 'metric': 'y'}])
rendered = figure.render()
plt.close(rendered)
for extension in ['svg', 'png', 'pdf']:
    destination = output / ('figure.' + extension)
    figure.render(destination)
    assert destination.stat().st_size > 0
assert 'altair' not in sys.modules
assert 'vl_convert' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_chart_opts_trigger_compute_before_rendering():
    data = pd.DataFrame({
        "x": list(range(8)), "value": [1, 2, 4, 3, 5, 8, 7, 9],
        "group": ["a"] * 4 + ["b"] * 4,
        "truth": ["a", "a", "a", "b", "b", "b", "a", "b"],
        "pred": ["a", "b", "a", "b", "a", "b", "a", "a"],
    })
    figure = Figure(data=data, rows=2, cols=3)
    figure[0, 0].scatter(x="x", y="value", chart_opts={"trend": True})
    figure[0, 1].histogram(x="value", chart_opts={"density": True})
    figure[0, 2].confusion(x="pred", y="truth", chart_opts={"normalize": True})
    figure[1, 0].bar(x="truth", y="value", group="group", chart_opts={"stacked": "percent", "mean_line": True})
    figure[1, 1].box(x="group", y="value", chart_opts={"mean_line": True})
    subplots = {(sp.row, sp.col): sp for sp in figure.build().subplots}
    assert not subplots[0, 0].derived_data["trend_data"].empty
    assert not subplots[0, 1].derived_data["density_data"].empty
    confusion = subplots[0, 2].derived_data["confusion_matrix"]
    assert confusion.groupby("truth")["pred_count"].sum().tolist() == pytest.approx([1, 1])
    stacked = subplots[1, 0].computed_data
    assert stacked.groupby("truth")["value_mean"].sum().tolist() == pytest.approx([1, 1])
    assert "overall_mean" in subplots[1, 0].derived_data
    assert "overall_mean" in subplots[1, 1].derived_data


def test_explicit_error_values_are_preserved_not_recomputed():
    figure = Figure(data=pd.DataFrame({
        "method": ["a", "a", "b", "b"], "score": [1, 3, 2, 4],
        "uncertainty": [0.2, 0.4, 0.6, 0.8],
    }), rows=1, cols=1)
    figure[0, 0].bar(x="method", y="score", error="uncertainty")
    payload = figure.build().subplots[0].computed_data
    assert payload["uncertainty"].tolist() == pytest.approx([0.3, 0.7])


@pytest.mark.parametrize("error", ["score", "std"])
def test_error_using_y_or_std_requests_sample_standard_deviation(error):
    figure = Figure(data=pd.DataFrame({
        "method": ["a", "a", "b", "b"], "score": [0.60, 0.62, 0.70, 0.72],
    }), rows=1, cols=1)
    figure[0, 0].bar(x="method", y="score", error=error)
    payload = figure.build().subplots[0].computed_data
    assert payload["score_std"].tolist() == pytest.approx([0.02 / 2 ** 0.5] * 2)
    assert "score" not in payload.columns
    assert "std" not in payload.columns


def test_line_repeated_x_is_averaged_with_group_and_secondary_axis():
    data = pd.DataFrame({
        "epoch": [2, 1, 1, 2, 1, 1], "model": ["a", "a", "a", "b", "b", "b"],
        "score": [6, 1, 3, 12, 5, 9], "latency": [8, 2, 4, 16, 6, 10],
    })
    figure = Figure(data=data, rows=1, cols=1)
    figure[0, 0].line(x="epoch", y="score", group="model", y2="latency")
    payload = figure.build().subplots[0].computed_data
    assert not payload.duplicated(["epoch", "model"]).any()
    actual = payload.set_index(["epoch", "model"])
    assert actual.loc[(1, "a"), "score"] == pytest.approx(2)
    assert actual.loc[(1, "b"), "score"] == pytest.approx(7)
    assert actual.loc[(1, "a"), "latency"] == pytest.approx(3)
    assert actual.loc[(1, "b"), "latency"] == pytest.approx(8)


def test_multi_y_line_averages_repeated_observations_without_group():
    figure = Figure(data=pd.DataFrame({
        "epoch": [2, 1, 1, 2], "precision": [0.8, 0.6, 0.8, 1.0],
        "recall": [0.6, 0.4, 0.6, 0.8],
    }), rows=1, cols=1)
    figure[0, 0].line(x="epoch", y=["precision", "recall"])
    payload = figure.build().subplots[0].computed_data
    assert payload["epoch"].tolist() == [1, 2]
    assert payload["precision"].tolist() == pytest.approx([0.7, 0.9])
    assert payload["recall"].tolist() == pytest.approx([0.5, 0.7])


@pytest.mark.parametrize("normalize, expected", [(False, [4, 3, 2, 6]), (True, [4 / 7, 3 / 7, 0.25, 0.75])])
def test_confusion_explicit_counts_are_summed_and_optionally_normalized(normalize, expected):
    figure = Figure(data=pd.DataFrame({
        "truth": ["a", "a", "a", "b", "b"],
        "pred": ["a", "a", "b", "a", "b"],
        "count": [1, 3, 3, 2, 6],
    }), rows=1, cols=1)
    figure[0, 0].confusion(x="pred", y="truth", value="count", chart_opts={"normalize": normalize})
    payload = figure.build().subplots[0].computed_data.sort_values(["truth", "pred"])
    assert payload["count"].tolist() == pytest.approx(expected)


def test_style_overrides_and_full_group_domains_reach_spec(sample_df):
    config = FigureConfig(font_family="DejaVu Sans", background="#eeeeee", category_colors={"dataset": {"D2": "#123456"}})
    figure = Figure(data=sample_df, rows=1, cols=1, config=config)
    figure[0, 0].bar(x="method", y="accuracy", group="dataset", y_columns=["D2"], labels={"D1": "First", "D2": "Second"})
    spec = figure.build()
    assert spec.font_family == "DejaVu Sans"
    assert spec.background == "#eeeeee"
    assert spec.color_domains == {"dataset": ["First", "Second"]}
    assert spec.category_colors == {"dataset": {"Second": "#123456"}}
    assert spec.subplots[0].computed_data["dataset"].unique().tolist() == ["Second"]


@pytest.mark.parametrize("suffix", [".html", ".htm", ".json"])
@pytest.mark.parametrize("operation", ["render", "save"])
def test_removed_export_formats_are_rejected(operation, suffix, sample_df, tmp_path):
    figure = _figure(sample_df)
    path = tmp_path / f"figure{suffix}"
    before = plt.get_fignums()
    with pytest.raises(ValueError, match="Unsupported export format"):
        if operation == "render":
            figure.render(path)
        else:
            export.save(figure.build(), path)
    assert not path.exists()
    assert plt.get_fignums() == before


def test_removed_html_and_json_export_helpers_are_not_public():
    import data_visuals.renderer as renderer

    for module in (renderer, export):
        assert not hasattr(module, "to_html")
        assert not hasattr(module, "to_json")


def test_packaging_discovers_nested_renderer_and_theme_data():
    from setuptools.config.pyprojecttoml import read_configuration
    config = read_configuration(str(Path(__file__).resolve().parents[1] / "pyproject.toml"))
    packages = config["tool"]["setuptools"]["packages"]
    assert {"data_visuals.renderer.mpl", "data_visuals.renderer.mpl.charts", "data_visuals.charts", "data_visuals.themes"}.issubset(packages)
    dependencies = config["project"]["dependencies"]
    assert any(item.startswith("matplotlib") for item in dependencies)
    optional_dependencies = config["project"].get("optional-dependencies", {})
    all_dependencies = dependencies + [
        item for extra in optional_dependencies.values() for item in extra
    ]
    assert not any(item.lower().replace("-", "_").startswith(("altair", "vl_convert"))
                   for item in all_dependencies)
    assert "vega" not in optional_dependencies
    assert "data_visuals.renderer.vega_charts" not in packages
