"""Declarative headers and shared axes for repeated-panel figures."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


_FACET_FIELDS = frozenset({
    "row_labels", "col_labels", "xlabel", "ylabel", "note", "sharex", "sharey",
})


def normalize_facets(facets: Mapping[str, Any]) -> dict[str, Any]:
    """Validate optional facet metadata without adding implicit features.

    An empty mapping preserves ordinary subplot behavior. Headers and shared
    axes are enabled only by the supplied fields; physical spacing remains the
    renderer's responsibility. Returned lists never alias the input mapping.
    """
    if not isinstance(facets, Mapping):
        raise TypeError("facets must be a mapping; use {} to disable facets.")
    unknown = set(facets) - _FACET_FIELDS
    if unknown:
        names = ", ".join(sorted(map(repr, unknown)))
        raise ValueError(f"facets contains unknown fields: {names}.")
    for key, value in facets.items():
        if key in {"row_labels", "col_labels"}:
            if not isinstance(value, list) or not all(isinstance(label, str) for label in value):
                raise TypeError(f"facets.{key} must be a list of strings.")
        elif key in {"sharex", "sharey"}:
            if not isinstance(value, bool):
                raise TypeError(f"facets.{key} must be a boolean.")
        elif not isinstance(value, str):
            raise TypeError(f"facets.{key} must be a string.")
    return deepcopy(dict(facets))
