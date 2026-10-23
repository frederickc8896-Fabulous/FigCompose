"""Small, data-first entry point backed by the existing Figure pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from os import PathLike
from typing import Any

import pandas as pd

from data_visuals.charts import get_chart
from data_visuals.core import Figure
from data_visuals.core.canvas import normalize_canvas
from data_visuals.core.config import get_default_config
from data_visuals.data.loader import load_csv
from data_visuals.layout.panels import plan_panels
from data_visuals.themes import load_theme
from data_visuals.utils.colors import get_color_preset


def _default_title(kind: str, declaration: dict[str, Any], index: int, count: int) -> str:
    if kind == "histogram":
        metric = declaration.get("x", "")
    elif kind == "heatmap":
        metric = declaration.get("value", "")
    elif kind == "confusion":
        metric = f"{declaration.get('y', '')} × {declaration.get('x', '')}"
    else:
        metric = declaration.get("y", "")
    text = ", ".join(map(str, metric)) if isinstance(metric, (list, tuple)) else str(metric)
    if count == 1:
        return text
    label = chr(ord("a") + index) if count <= 26 else str(index + 1)
    return f"({label}) {text}"


def plot(
    data: str | PathLike[str] | pd.DataFrame,
    *,
    plots: Sequence[Mapping[str, Any]],
    x: str | None = None,
    group: str | None = None,
    canvas: Mapping[str, Any] | None = None,
    cols: int | None = None,
    style: str | None = None,
    palette: str | None = None,
    title: str | None = None,
    legend: Mapping[str, Any] | bool | None = None,
    csv_options: Mapping[str, Any] | None = None,
) -> Figure:
    """Describe a complete Figure with a CSV, metrics, plot kinds and a style.

    Each entry in ``plots`` is one panel, in reading order. ``kind`` selects
    an existing chart type; ``metric`` selects its measured column (``y`` for
    bar/line/box/scatter, ``x`` for histogram, ``value`` for heatmap/confusion).
    Native chart mappings and options are also accepted in the entry.
    ``palette`` optionally selects an original curated combination, such as
    ``curated-5-default``, independently of typography and layout style.
    ``legend`` optionally overrides shared/local placement, columns, labels,
    order, and spacing in points; ``False`` hides legends. Individual entries
    can override these fields through ``chart_opts={'legend': {...}}``.

    Global ``x`` and ``group`` are defaults for bar/line/box/scatter. Histogram
    inherits only ``group``; matrix plots require explicit axes. An entry can
    override a default, including ``group=None`` to turn grouping off.

    ``canvas`` sets final physical dimensions, e.g. ``{'width': 180,
    'height': 110}`` in mm (or ``unit='in'``). Omit height for measured automatic
    height; omit canvas to inherit the global default physical width.

    Panel count, row count, panel titles, fonts, colors,
    legends and decoration spacing are automatic. ``cols`` optionally limits
    panels per row; an incomplete last row fills the width. No columns or
    statistical meanings are guessed from their names.

    Returns the regular :class:`Figure`, ready for ``.render('figure.svg')``,
    ``.render('figure.pdf')`` or ``.show()``. CSV reading options such as
    ``encoding`` and ``delimiter`` can be passed in ``csv_options``.
    """
    if not isinstance(plots, Sequence) or isinstance(plots, (str, bytes)):
        raise TypeError("plots 必须是子图声明列表，例如 [{'kind': 'bar', 'metric': 'accuracy'}]。")
    layout, positions, _ = plan_panels(len(plots), cols)
    if canvas is not None:
        normalize_canvas(canvas)
    if csv_options is not None and not isinstance(csv_options, Mapping):
        raise TypeError("csv_options 必须是字典。")
    for name, column in (("x", x), ("group", group)):
        if column is not None and (not isinstance(column, str) or not column):
            raise TypeError(f"{name} 必须是列名字符串或 None。")

    # Normalize declarations without modifying the caller's dictionaries.
    declarations = []
    for index, panel in enumerate(plots):
        if not isinstance(panel, Mapping):
            raise TypeError(f"plots[{index}] 必须是字典。")
        declaration = dict(panel)
        kind = declaration.pop("kind", None)
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"plots[{index}] 需要 kind，例如 'bar'、'line' 或 'box'。")
        try:
            chart = get_chart(kind)
        except ValueError as error:
            raise ValueError(f"plots[{index}]: {error}") from error

        if "metric" in declaration:
            target = "x" if kind == "histogram" else "value" if kind in {"heatmap", "confusion"} else "y"
            if target in declaration:
                raise ValueError(f"plots[{index}] 的 metric 与 {target} 重复，请只指定其中一个。")
            declaration[target] = declaration.pop("metric")
        if kind in {"bar", "line", "box", "scatter"} and x is not None:
            declaration.setdefault("x", x)
        if "group" in chart.optional_fields and group is not None:
            declaration.setdefault("group", group)
        if "title" not in declaration:
            declaration["title"] = _default_title(kind, declaration, index, len(plots))
        declarations.append((kind, declaration))

    selected_style = style if style is not None else get_default_config().theme
    if not isinstance(selected_style, str) or not selected_style:
        raise TypeError("style 必须是风格名称，例如 'general' 或 'modern'。")
    load_theme(selected_style)
    if palette is not None:
        get_color_preset(palette)
    if isinstance(data, pd.DataFrame):
        if csv_options:
            raise ValueError("csv_options 仅适用于 CSV 文件输入。")
        frame = data
    elif isinstance(data, (str, PathLike)):
        frame = load_csv(data, **dict(csv_options or {}))
    else:
        raise TypeError("data 必须是 CSV 路径或 pandas DataFrame。")

    figure = Figure(data=frame, layout=layout, canvas=canvas, theme=selected_style,
                    palette=palette, title=title, legend=legend)
    figure._auto_cols = cols
    for (row, col), (kind, declaration) in zip(positions, declarations):
        figure[row, col].set(kind, **declaration)
    # Validate data mappings now, before a notebook user starts exporting files.
    figure.build()
    return figure
