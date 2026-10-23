"""Runtime contracts for Matplotlib content drawn inside a managed panel.

The framework owns the Figure, axes allocation, typography and export. Drawing
callbacks own their artists; an optional layout callback updates those same
artists as the measured panel changes size. Callbacks are rebuilt for sizing
trials and exports, so they must not rely on invocation counts or mutate data.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, TYPE_CHECKING

from pandas import isna
from pandas.api.types import is_scalar

if TYPE_CHECKING:
    from matplotlib.artist import Artist
    from matplotlib.axes import Axes


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite positive number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a finite positive number") from None
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


@dataclass(frozen=True)
class CustomPanel:
    """Validated runtime-only drawing declaration; dimensions are in points.

    ``box_aspect`` is content width / height, not Matplotlib's reciprocal
    ``set_box_aspect`` argument. ``preferred_aspect`` is only a soft preference
    for automatic canvas sizing. Payloads and callables retain their identity.
    """

    draw: Callable
    payload: Any = None
    min_size: tuple[float, float] = (72.0, 48.0)
    preferred_aspect: float = 1.75
    box_aspect: float | None = None
    axes: str = "off"
    limits: tuple[tuple[float, float], ...] | None = None
    projection: str | None = None
    axes_options: Mapping[str, Any] | None = None
    color_group: str | None = None
    categories: Sequence[Any] | None = None

    def __post_init__(self) -> None:
        if not callable(self.draw):
            raise TypeError("custom draw must be callable: draw(ax, context)")
        try:
            sizes = tuple(self.min_size)
        except TypeError:
            raise ValueError("custom min_size must be (width_pt, height_pt)") from None
        if len(sizes) != 2:
            raise ValueError("custom min_size must be (width_pt, height_pt)")
        object.__setattr__(self, "min_size", tuple(_positive(v, "custom min_size") for v in sizes))
        object.__setattr__(self, "preferred_aspect", _positive(self.preferred_aspect, "custom preferred_aspect"))
        if self.box_aspect is not None:
            object.__setattr__(self, "box_aspect", _positive(self.box_aspect, "custom box_aspect"))
        if self.axes not in ("on", "off"):
            raise ValueError("custom axes must be 'on' or 'off'")
        if self.projection is not None and (not isinstance(self.projection, str) or not self.projection):
            raise ValueError("custom projection must be a registered Matplotlib projection name or None")
        from matplotlib.projections import get_projection_class
        try:
            projection_class = get_projection_class(self.projection)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Unknown custom Matplotlib projection: {self.projection!r}") from error
        is_3d = projection_class.name == "3d"
        options = self.axes_options
        if options is not None and not isinstance(options, Mapping):
            raise ValueError("custom axes_options must be a mapping of native Axes constructor options")
        options = dict(options or {})
        if any(not isinstance(key, str) for key in options):
            raise ValueError("custom axes_options keys must be strings")
        if "polar" in options:
            raise ValueError("Use custom projection='polar' instead of axes_options['polar']")
        reserved = {"rect", "position", "label", "figure", "projection", "axes_class", "axes_locator",
                    "sharex", "sharey", "sharez", "shareview", "subplot_spec"}
        invalid = reserved.intersection(options)
        if invalid:
            raise ValueError(f"custom axes_options cannot override managed Axes ownership: {sorted(invalid)}")
        if "zlim" in options and not is_3d:
            raise ValueError("custom axes_options zlim requires projection='3d'")
        object.__setattr__(self, "axes_options", MappingProxyType(options))
        limits = self.limits
        if limits is not None:
            try:
                limits = tuple(tuple(float(v) for v in pair) for pair in limits)
                valid = (len(limits) in ((2, 3) if is_3d else (2,)) and all(len(pair) == 2 and
                         all(math.isfinite(v) for v in pair) and pair[0] != pair[1] for pair in limits))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                count = "two or three" if is_3d else "two"
                raise ValueError(f"custom limits must be {count} finite, nondegenerate (low, high) pairs")
        object.__setattr__(self, "limits", limits)
        if self.color_group is not None and (not isinstance(self.color_group, str) or not self.color_group):
            raise ValueError("custom color_group must be a nonempty string")
        if self.categories is not None:
            if self.color_group is None:
                raise ValueError("custom categories require color_group")
            if isinstance(self.categories, (str, bytes)):
                raise ValueError("custom categories must be a sequence of unique scalar keys")
            try:
                categories = tuple(self.categories)
                valid = (all(is_scalar(key) and not isna(key) for key in categories)
                         and len(set(categories)) == len(categories))
            except TypeError:
                valid = False
            if not valid:
                raise ValueError("custom categories must be a sequence of unique non-null scalar keys")
            object.__setattr__(self, "categories", categories)

    def __deepcopy__(self, memo):
        # Drawing functions may be bound methods, and payloads may own native
        # handles. Layout trials copy geometry, never these external objects.
        return self


@dataclass(frozen=True)
class PanelContext:
    """Resolved style and current physical viewport passed to custom content.

    Use ``text_kwargs()`` for node text; native ``ax.text`` alone only inherits
    Matplotlib defaults. ``color`` uses the same category maps as data charts.
    The payload is supplied unchanged and should be treated as read-only.
    """

    payload: Any
    font_family: str
    font_sizes: Mapping[str, float]
    text_color: str
    background: str
    palette: tuple[str, ...]
    color_map: Mapping[Any, str]
    color_maps: Mapping[str, Mapping[Any, str]]
    width_pt: float
    height_pt: float
    line_width: float = 0.8

    def __post_init__(self) -> None:
        object.__setattr__(self, "font_sizes", MappingProxyType(dict(self.font_sizes)))
        object.__setattr__(self, "color_map", MappingProxyType(dict(self.color_map)))
        object.__setattr__(self, "color_maps", MappingProxyType({
            group: MappingProxyType(dict(colors)) for group, colors in self.color_maps.items()
        }))
        object.__setattr__(self, "palette", tuple(self.palette))

    def text_kwargs(self, role: str = "body", **overrides: Any) -> dict[str, Any]:
        """Matplotlib text keywords in physical points, with optional overrides."""
        if role not in self.font_sizes:
            raise ValueError(f"Unknown panel text role {role!r}; choose from {list(self.font_sizes)}")
        return {"fontfamily": self.font_family, "fontsize": self.font_sizes[role],
                "color": self.text_color, **overrides}

    def color(self, value: Any, *, group: str | None = None) -> str:
        """Look up a semantic category; undeclared categories fail explicitly."""
        colors = self.color_map if group is None else self.color_maps.get(group, {})
        if value not in colors:
            raise KeyError(f"Undeclared custom panel category {value!r} in {group or 'color_group'}")
        return colors[value]


@dataclass
class PanelResult:
    """Artists to measure, legend handles, and an optional resize callback.

    ``layout(ax, context)`` updates existing artists after panel positioning,
    before each measurement. Do not create additional artists there. Artists
    explicitly listed here participate in bounds checks even when they would
    otherwise be excluded from Axes tight-bbox discovery.
    """

    artists: Sequence[Artist] = field(default_factory=tuple)
    legend_handles: Sequence[Artist] = field(default_factory=tuple)
    layout: Callable[[Axes, PanelContext], None] | None = None

    def __post_init__(self) -> None:
        self.artists = tuple(self.artists)
        self.legend_handles = tuple(self.legend_handles)
        if any(not callable(getattr(artist, "get_window_extent", None)) for artist in self.artists):
            raise TypeError("PanelResult.artists must contain Matplotlib artists")
        if any(not callable(getattr(handle, "get_label", None)) for handle in self.legend_handles):
            raise TypeError("PanelResult.legend_handles must contain labeled Matplotlib artists")
        if self.layout is not None and not callable(self.layout):
            raise TypeError("PanelResult.layout must be callable or None")
