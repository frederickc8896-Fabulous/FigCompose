"""Validate the opt-in facet contract and its serialization boundaries."""

from __future__ import annotations

import json

import pytest

from data_visuals.core.config import FigureConfig
from data_visuals.core.spec import FigureSpec


@pytest.fixture
def facet_metadata():
    return {
        "row_labels": ["Single-phrase", "Multi-phrase"],
        "col_labels": ["xsmall", "small", "RoBERTa"],
        "xlabel": "Actual ID false rejection (%)",
        "ylabel": "Near-OOD leakage (%)",
        "note": "Reference ID budget: 5%",
        "sharex": True,
        "sharey": True,
    }


def test_facets_default_is_disabled_and_independent():
    first, second = FigureConfig(), FigureConfig()
    assert first.facets == second.facets == {}
    first.facets["sharex"] = True
    assert second.facets == {}
    assert FigureSpec().to_dict()["facets"] == {}


def test_config_roundtrip_keeps_facets_and_physical_canvas(facet_metadata):
    config = FigureConfig(facets=facet_metadata, canvas={"width": 7, "height": 4.5, "unit": "in"})
    serialized = json.loads(json.dumps(config.to_dict()))
    restored = FigureConfig.from_dict(serialized)
    assert restored.facets == facet_metadata
    assert restored.canvas == {"width": 7.0, "height": 4.5, "unit": "in"}
    assert not restored.legacy_size_fields()


@pytest.mark.parametrize("container", [FigureConfig, FigureSpec])
def test_facet_input_and_export_do_not_alias_lists(container, facet_metadata):
    expected_rows = list(facet_metadata["row_labels"])
    instance = container(facets=facet_metadata)
    facet_metadata["row_labels"].append("External mutation")
    assert instance.facets["row_labels"] == expected_rows
    exported = instance.to_dict()
    exported["facets"]["row_labels"].clear()
    assert instance.facets["row_labels"] == expected_rows


def test_spec_serializes_facet_metadata_as_json(facet_metadata):
    original = FigureSpec(facets=facet_metadata)
    serialized = json.loads(json.dumps(original.to_dict()))
    restored = FigureSpec(facets=serialized["facets"])
    assert restored.facets == facet_metadata
    assert restored.to_dict()["facets"] == original.to_dict()["facets"]


@pytest.mark.parametrize("facets", [None, [], "shared"])
def test_non_mapping_facets_are_rejected(facets):
    with pytest.raises(TypeError, match="facets"):
        FigureConfig(facets=facets)


@pytest.mark.parametrize("facets,field", [
    ({"row_labels": "one row"}, "row_labels"),
    ({"col_labels": ("xsmall", "small")}, "col_labels"),
    ({"row_labels": ["one", 2]}, "row_labels"),
    ({"xlabel": None}, "xlabel"),
    ({"ylabel": ["Leakage"]}, "ylabel"),
    ({"note": False}, "note"),
    ({"sharex": 1}, "sharex"),
    ({"sharey": "true"}, "sharey"),
])
def test_invalid_facet_field_types_are_rejected(facets, field):
    with pytest.raises(TypeError, match=field):
        FigureConfig.from_dict({"facets": facets})


@pytest.mark.parametrize("container", [FigureConfig, FigureSpec])
def test_unknown_facet_fields_are_rejected(container):
    with pytest.raises(ValueError, match="share_x"):
        container(facets={"share_x": True})


def test_invalid_facet_mutations_cannot_silently_serialize():
    config = FigureConfig()
    config.facets["xlabels"] = "typo"
    with pytest.raises(ValueError, match="xlabels"):
        config.to_dict()
