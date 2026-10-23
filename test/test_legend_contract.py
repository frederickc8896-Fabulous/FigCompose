"""Legend overrides keep their scope and survive the public spec pipeline."""

import json

import pandas as pd
import pytest

from data_visuals import plot
from data_visuals.core import Figure
from data_visuals.core.config import FigureConfig
from data_visuals.core.legend import merge_legend, normalize_legend
from data_visuals.core.spec import FigureSpec


_FRAME = pd.DataFrame({"x": [1, 2, 3, 4], "y": [2, 4, 3, 5], "method": ["A", "A", "B", "B"]})


def _paper(*, legend=None, config=None, panels=2, **kwargs):
    paper = Figure(data=_FRAME, rows=1, cols=panels, aspect="4:3", legend=legend,
                   config=config, **kwargs)
    for col in range(panels):
        paper[0, col].scatter(x="x", y="y", group="method")
    return paper


def test_partial_overrides_do_not_fill_defaults_or_mutate_callers():
    source = {"order": ["B", "A"], "labels": {"A": "Alpha"}, "anchor": (0.5, 0.9)}
    normalized = normalize_legend(source)
    assert normalized == {"order": ["B", "A"], "labels": {"A": "Alpha"}, "anchor": [0.5, 0.9]}
    normalized["order"].append("C")
    normalized["labels"]["B"] = "Beta"
    assert source["order"] == ["B", "A"]
    assert source["labels"] == {"A": "Alpha"}
    assert normalize_legend() == normalize_legend(True) == {}
    assert normalize_legend(False) == {"visible": False}


@pytest.mark.parametrize("value", [
    "bottom", [], 1, {"unknown": 1}, {"visible": 1}, {"frameon": None},
    {"scope": "global"}, {"scope": []}, {"position": "center"}, {"position": []},
    {"ncols": 0}, {"ncols": True}, {"ncols": 1.5},
    {"fontsize": 0}, {"fontsize": -1}, {"fontsize": float("inf")}, {"fontsize": True},
    {"gap": -0.1}, {"gap": float("nan")}, {"columnspacing": -1},
    {"labelspacing": None}, {"handlelength": "12"}, {"handletextpad": False},
    {"borderpad": float("inf")}, {"anchor": [0]}, {"anchor": [0, 0, 0]},
    {"anchor": "ab"}, {"anchor": [-0.1, 0.5]}, {"anchor": [0.5, 1.1]},
    {"anchor": [True, 0.5]}, {"order": "AB"}, {"order": ["A", "A"]},
    {"order": [["A"]]}, {"order": [float("nan")]},
    {"labels": ["A"]}, {"labels": {"A": 1}}, {"labels": {float("nan"): "A"}},
])
def test_invalid_fields_fail_at_the_contract_boundary(value):
    with pytest.raises(ValueError, match="legend"):
        normalize_legend(value)


@pytest.mark.parametrize("alias,position", [
    ("top-left", "upper left"), ("top_right", "upper right"),
    ("bottom-left", "lower left"), ("LOWER RIGHT", "lower right"),
    ("top", "top"), ("right", "right"),
])
def test_position_aliases_normalize_before_rendering(alias, position):
    assert normalize_legend({"position": alias}) == {"position": position}


def test_all_contract_fields_survive_configuration_json_roundtrip():
    fields = {
        "visible": True, "scope": "local", "position": "lower right", "ncols": 2,
        "fontsize": 9, "gap": 0, "columnspacing": 8, "labelspacing": 3,
        "handlelength": 12, "handletextpad": 4, "borderpad": 3, "frameon": True,
        "anchor": (0.9, 0.1), "order": ["B", "A"], "labels": {"A": "Alpha", "B": "Beta"},
    }
    config = FigureConfig(legend=fields)
    restored = FigureConfig.from_dict(json.loads(json.dumps(config.to_dict())))
    assert restored.legend == normalize_legend(fields)
    assert FigureSpec(legend=fields).to_dict()["legend"] == restored.legend


def test_null_reset_fields_are_distinct_from_omitted_fields():
    assert merge_legend({"fontsize": 9, "ncols": 3}, {"fontsize": None}) == {
        "fontsize": None, "ncols": 3,
    }


def test_global_constructor_overrides_config_per_field_and_spec_preserves_it():
    config = FigureConfig(legend={"position": "bottom", "fontsize": 9, "frameon": True})
    paper = _paper(config=config, legend={"fontsize": 10, "ncols": 2})
    spec = paper.build()
    assert spec.legend == {"position": "bottom", "fontsize": 10, "frameon": True, "ncols": 2}
    assert spec.shared_legend["enabled"] is True
    assert spec.shared_legend["position"] == "bottom"
    assert all(panel.legend["fontsize"] == 10 for panel in spec.subplots)
    assert all("legend" not in panel.chart_options for panel in spec.subplots)
    assert config.legend["fontsize"] == 9


def test_panel_override_is_local_and_inherits_independent_fields():
    paper = _paper(legend={"scope": "shared", "position": "bottom", "fontsize": 9})
    options = {"legend": {"position": "upper right", "frameon": True}}
    paper[0, 0].scatter(x="x", y="y", group="method", chart_opts=options)
    first, second = paper.build().subplots
    assert first.legend["scope"] == "local"
    assert first.legend["position"] == "upper right"
    assert first.legend["fontsize"] == 9
    assert first.legend["frameon"] is True
    assert first.chart_options["legend"] == {"position": "upper right", "frameon": True}
    assert second.legend["scope"] == "shared"
    assert paper.build().shared_legend["enabled"] is True
    assert "scope" not in options["legend"]


def test_empty_panel_override_is_explicitly_local_unless_scope_is_given():
    paper = _paper(legend={"scope": "shared"})
    paper[0, 0].scatter(x="x", y="y", group="method", chart_opts={"legend": None})
    paper[0, 1].scatter(x="x", y="y", group="method", chart_opts={"legend": {"scope": "auto"}})
    spec = paper.build()
    assert spec.subplots[0].chart_options["legend"] == {}
    assert spec.subplots[0].legend["scope"] == "local"
    assert spec.subplots[1].legend["scope"] == "auto"
    assert spec.shared_legend["enabled"] is False


@pytest.mark.parametrize("legend", [False, {"scope": "local"}])
def test_hidden_or_local_legends_do_not_reserve_a_shared_group(legend):
    spec = _paper(legend=legend).build()
    assert spec.shared_legend["enabled"] is False


def test_one_panel_can_request_a_shared_legend():
    assert _paper(legend={"scope": "shared"}, panels=1).build().shared_legend["enabled"] is True
    assert _paper(panels=1).build().shared_legend["enabled"] is False


def test_panel_can_be_reenabled_under_a_global_hidden_setting():
    paper = _paper(legend=False)
    paper[0, 0].scatter(x="x", y="y", group="method", chart_opts={"legend": {"visible": True}})
    first, second = paper.build().subplots
    assert first.legend["visible"] is True
    assert first.legend["scope"] == "local"
    assert second.legend["visible"] is False


def test_new_legend_position_has_priority_over_legacy_field():
    assert _paper(legend_position="bottom").build().shared_legend["position"] == "bottom"
    spec = _paper(legend_position="bottom", legend={"position": "left"}).build()
    assert spec.shared_legend["position"] == "left"
    assert _paper(legend_position="top-left").build().shared_legend["position"] == "top"


def test_invalid_panel_legend_fails_when_declared():
    paper = _paper()
    with pytest.raises(ValueError, match="legend.ncols"):
        paper[0, 0].scatter(x="x", y="y", chart_opts={"legend": {"ncols": 0}})


def test_simple_api_passes_global_and_panel_legend_to_the_same_pipeline():
    paper = plot(
        _FRAME, x="x", group="method", legend={"position": "bottom", "fontsize": 9},
        plots=[{"kind": "scatter", "metric": "y", "chart_opts": {"legend": False}}],
    )
    spec = paper.build()
    assert spec.legend == {"position": "bottom", "fontsize": 9}
    assert spec.subplots[0].chart_options["legend"] == {"visible": False}
    assert spec.subplots[0].legend["scope"] == "local"
    assert spec.subplots[0].legend["visible"] is False

