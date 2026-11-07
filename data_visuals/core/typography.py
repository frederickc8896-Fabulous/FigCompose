"""Validate reusable physical font-size overrides without changing defaults."""

from collections.abc import Mapping
from math import isfinite
from numbers import Real


FONT_SIZE_ROLES = frozenset({"main_title", "title", "axis_label", "tick", "legend"})


def normalize_font_sizes(value=None):
    """Return detached, explicitly supplied role sizes in typographic points."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("font_sizes must be a mapping of roles to positive sizes in points.")
    unknown = set(value) - FONT_SIZE_ROLES
    if unknown:
        raise ValueError(f"Unknown font_sizes roles: {', '.join(sorted(map(str, unknown)))}")
    result = {}
    for role, size in value.items():
        if isinstance(size, bool) or not isinstance(size, Real):
            raise ValueError(f"font_sizes.{role} must be a finite positive number in points.")
        size = float(size)
        if not isfinite(size) or size <= 0:
            raise ValueError(f"font_sizes.{role} must be a finite positive number in points.")
        result[role] = size
    return result
