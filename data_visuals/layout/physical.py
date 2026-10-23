"""Solve physical Figure constraints using the renderer's measured decorations.

Data is computed once by Figure. Candidate layouts share those results and are
measured at 72 points per inch, independent of export resolution. A successful
candidate is committed to FigureSpec; no Matplotlib Figure is kept alive.
"""

from __future__ import annotations

from dataclasses import replace
import math

from data_visuals.layout.grid import compute_grid_mixed
from data_visuals.layout.panels import plan_panels
from data_visuals.layout.placement import LayoutError


_PT_TO_MM = 25.4 / 72
_MAX_HEIGHT_PASSES = 8


def _preferred_aspect(panel):
    """A soft data-region preference, never a change to the data coordinate axes."""
    if panel.custom_panel is not None:
        custom = panel.custom_panel
        return custom.box_aspect or custom.preferred_aspect
    if panel.chart_type in {"heatmap", "confusion"}:
        data = panel.computed_data
        x, y = panel.data_mapping.get("x"), panel.data_mapping.get("y")
        if data is not None and x in data and y in data:
            return min(2.0, max(0.85, data[x].nunique() / max(1, data[y].nunique())))
        return 1.15
    return {"scatter": 1.25, "box": 1.5}.get(panel.chart_type, 1.75)


def _axis_cuts(panels, count, start, extent, index, span):
    """Recover weighted topology edges from an advanced layout's geometry."""
    left, right = {}, {}
    for panel in panels:
        begin = getattr(panel, index)
        end = begin + getattr(panel, span)
        low, high = getattr(panel, start), getattr(panel, start) + getattr(panel, extent)
        left[begin] = min(left.get(begin, low), low)
        right[end] = max(right.get(end, high), high)
    cuts = {0: min(left.values()), count: max(right.values())}
    for edge in range(1, count):
        values = [mapping[edge] for mapping in (left, right) if edge in mapping]
        if values:
            cuts[edge] = sum(values) / len(values)
    for edge in range(1, count):
        if edge not in cuts:
            before = max(value for value in cuts if value < edge)
            after = min(value for value in cuts if value > edge)
            cuts[edge] = cuts[before] + (cuts[after] - cuts[before]) * (edge - before) / (after - before)
    length = cuts[count] - cuts[0]
    return [(cuts[edge] - cuts[0]) / length for edge in range(count + 1)]


def _geometry(spec, width, height, cfg, columns):
    padding, gap = cfg.canvas_padding, cfg.panel_gap
    if columns is not False:
        panels = [panel for panel in spec.subplots if panel.chart_type]
        layout, positions, _ = plan_panels(len(panels), columns)
        grid = compute_grid_mixed(
            layout=layout, canvas_width=width, canvas_height=height,
            margin_top=padding, margin_bottom=padding,
            margin_left=padding, margin_right=padding, gap_x=gap, gap_y=gap,
        )
        cells = list(grid.cells)
        for panel, (row, col), cell in zip(panels, positions, cells):
            panel.row, panel.col = row, col
            panel.row_span, panel.col_span = cell.row_span, cell.col_span
            panel.x, panel.y, panel.w, panel.h = cell.x, cell.y, cell.w, cell.h
        spec.subplots = panels
        spec.grid.update(rows=grid.rows, cols=grid.cols, panel_columns=columns, gap=gap)
    else:
        rows, cols = spec.grid["rows"], spec.grid["cols"]
        xcuts = _axis_cuts(spec.subplots, cols, "x", "w", "col", "col_span")
        ycuts = _axis_cuts(spec.subplots, rows, "y", "h", "row", "row_span")
        usable_w, usable_h = width - padding * 2, height - padding * 2
        for panel in spec.subplots:
            r, c = panel.row, panel.col
            er, ec = r + panel.row_span, c + panel.col_span
            panel.x = padding + xcuts[c] * usable_w + (gap / 2 if c else 0)
            panel.y = padding + ycuts[r] * usable_h + (gap / 2 if r else 0)
            right = padding + xcuts[ec] * usable_w - (gap / 2 if ec < cols else 0)
            bottom = padding + ycuts[er] * usable_h - (gap / 2 if er < rows else 0)
            panel.w, panel.h = right - panel.x, bottom - panel.y
        spec.grid["gap"] = gap


def _candidate(template, request, height, cfg, columns):
    # Only layout fields change between trials. Keep potentially large computed
    # DataFrames shared; the renderer consumes a detached serialization.
    spec = replace(template, grid=dict(template.grid),
                   subplots=[replace(panel) for panel in template.subplots])
    width = request["width"]
    spec.canvas = {
        **template.canvas, "width": width, "height": height,
        "unit": "pt", "physical": True, "height_auto": request["height_auto"],
        "request": dict(request["request"]),
        "width_mm": width * _PT_TO_MM, "height_mm": height * _PT_TO_MM,
        "aspect_ratio": width / height, "aspect": f"{width / height:.6g}",
        "panel_gap": cfg.panel_gap,
    }
    _geometry(spec, width, height, cfg, columns)
    spec.margins = dict.fromkeys(("top", "bottom", "left", "right"), cfg.canvas_padding)
    spec.title = {**spec.title, "font_size": cfg.font_sizes["main_title"]}
    spec.subtitle = {**spec.subtitle, "font_size": cfg.font_sizes["title"]}
    legend_options = getattr(template, "legend", {})
    legend_size = legend_options.get("fontsize") or cfg.font_sizes["legend"]
    spec.shared_legend = {**spec.shared_legend, "font_size": legend_size}
    fonts = {key: value for key, value in cfg.font_sizes.items() if key != "main_title"}
    for panel in spec.subplots:
        panel.font_sizes = dict(fonts)
        local_options = panel.chart_options.get("legend", {})
        local_size = local_options.get("fontsize", legend_options.get("fontsize")) or fonts["legend"]
        panel.font_sizes["legend"] = local_size
        panel.legend = {**panel.legend, "font_size": local_size, "reserved_height": 0}
        panel.label_margins = {}
        panel.data_zone = {"x": panel.x, "y": panel.y, "w": panel.w, "h": panel.h}
    return spec


def _initial_height(template, request, cfg, columns):
    if request["height"] is not None:
        return request["height"]
    active = [panel for panel in template.subplots if panel.chart_type]
    rows = template.grid["rows"] if columns is False else math.ceil(len(active) / columns)
    cols = template.grid["cols"] if columns is False else columns
    cell_width = max(cfg.min_plot_width, (request["width"] - 2 * cfg.canvas_padding) / cols)
    aspect = sum(_preferred_aspect(panel) for panel in active) / len(active)
    row_height = max(cfg.min_plot_height, (cell_width - 42) / aspect) + 50
    return rows * row_height + 2 * cfg.canvas_padding + (20 if template.title.get("text") else 0)


def _commit_measured_geometry(spec, measured):
    for panel in spec.subplots:
        record = measured["cells"].get((panel.row, panel.col))
        if record is None:
            continue
        cell, zone = record["cell"], record["data_zone"]
        panel.x, panel.y, panel.w, panel.h = (cell[key] for key in ("x", "y", "w", "h"))
        panel.data_zone = dict(zone)
        panel.label_margins = {
            "x_label_height": cell["h"] - zone["h"] - (zone["y"] - cell["y"]),
            "y_label_width": zone["x"] - cell["x"],
        }
    spec.canvas["header_height"] = measured["header_height"]
    spec.canvas["footer_height"] = measured.get("footer_height", 0)
    spec.canvas["left_legend_width"] = measured.get("left_legend_width", 0)
    spec.canvas["right_legend_width"] = measured.get("right_legend_width", 0)


def _score(spec, measured):
    aspects, narrow = [], []
    for panel in spec.subplots:
        record = measured["cells"].get((panel.row, panel.col))
        if record is None:
            continue
        zone = record["data_zone"]
        aspects.append(abs(math.log(zone["w"] / zone["h"] / _preferred_aspect(panel))))
        narrow.append(max(0, 115 / zone["w"] - 1) ** 2)
    count = max(1, len(aspects))
    return (0.65 * sum(aspects) / count + 0.8 * sum(narrow) / count
            + (0.45 * spec.canvas["height"] / spec.canvas["width"] if spec.canvas["height_auto"] else 0))


def _comfortable_height(spec, measured, cfg, columns):
    """Include measured headers/gutters in the preferred readable panel height.

    A full-width final panel may be wider than the others without forcing every
    row to be tall. Advanced spans retain their own geometry preferences.
    """
    width, height = spec.canvas["width"], spec.canvas["height"]
    available = height - measured["header_height"] - measured.get("footer_height", 0) - 2 * cfg.canvas_padding
    requested = height
    for panel in spec.subplots:
        record = measured["cells"].get((panel.row, panel.col))
        if record is None:
            continue
        cell, zone = record["cell"], record["data_zone"]
        preferred_width = zone["w"]
        if columns is not False:
            gutter_w = cell["w"] - zone["w"]
            side_width = measured.get("left_legend_width", 0) + measured.get("right_legend_width", 0)
            regular_width = (width - 2 * cfg.canvas_padding - side_width - (columns - 1) * cfg.panel_gap) / columns
            preferred_width = min(preferred_width, max(cfg.min_plot_width, regular_width - gutter_w))
        desired = max(cfg.min_plot_height, preferred_width / _preferred_aspect(panel))
        fraction = cell["h"] / max(1, available)
        requested = max(requested, height + (desired - zone["h"]) / max(0.01, fraction))
    return requested


def resolve_canvas_spec(spec, canvas_request, *, auto_cols=False):
    """Return one measured, reproducible physical layout or a useful LayoutError.

    ``False`` preserves an advanced Figure's spans/weights. ``None`` searches
    all plausible column counts; an integer is an upper bound on that search.
    Explicit height is never changed. Width never changes in either mode.
    """
    import matplotlib.pyplot as plt
    from data_visuals.renderer.mpl.canvas import figure_to_matplotlib
    from data_visuals.renderer.mpl.config import MplConfig

    cfg = MplConfig(spec.theme, palette=spec.palette, physical=True)
    active = [panel for panel in spec.subplots if panel.chart_type]
    if not active:
        raise LayoutError("At least one subplot is required for a physical canvas.")
    width = canvas_request["width"]
    if auto_cols is False:
        column_counts = [False]
    else:
        maximum = min(len(active), auto_cols if auto_cols is not None else len(active))
        column_counts = list(range(1, maximum + 1))
    successes, failures = [], []
    for columns in column_counts:
        # A preliminary lower bound avoids expensive trials that cannot fit
        # even a readable data region and minimal axis decorations.
        if columns is not False and (width - 2 * cfg.canvas_padding) / columns < cfg.min_plot_width + 28:
            continue
        height = _initial_height(spec, canvas_request, cfg, columns)
        passes = 1 if canvas_request["height"] is not None else _MAX_HEIGHT_PASSES
        fitted = False
        probes = []
        for attempt in range(passes):
            candidate = _candidate(spec, canvas_request, height, cfg, columns)
            rendered = None
            try:
                rendered = figure_to_matplotlib(candidate)
                measured = rendered._data_visuals_layout
                score = _score(candidate, measured)
                if canvas_request["height_auto"] and not fitted:
                    # Data aspect preferences are soft. A square matrix in one
                    # row must not force all the other rows to become tall.
                    # Compare a compact and a more spacious measured candidate
                    # instead of silently treating that preference as a bound.
                    comfortable = _comfortable_height(candidate, measured, cfg, columns)
                    probes = [height * 0.85]
                    if comfortable > height + 2:
                        probes.append(comfortable + 1)
                _commit_measured_geometry(candidate, measured)
                successes.append((score, candidate))
                fitted = True
                if probes and attempt < passes - 1:
                    height = probes.pop(0)
                    continue
                break
            except LayoutError as error:
                failures.append(error)
                if error.axis == "width" or canvas_request["height"] is not None:
                    break
                if fitted:
                    if probes:
                        height = probes.pop(0)
                        continue
                    break
                needed = error.required_height or 0
                height = max(height * 1.18, needed + 3)
            finally:
                if rendered is not None:
                    plt.close(rendered)
    if successes:
        return min(successes, key=lambda item: item[0])[1]
    last = failures[-1] if failures else None
    requested = canvas_request["request"]
    fixed = canvas_request["height"] is not None
    size = f"{requested['width']:g}" + (f" × {requested['height']:g}" if fixed else " wide")
    detail = f" {last}" if last else " The available width cannot hold readable axes and labels."
    raise LayoutError(
        f"Canvas {size} {requested['unit']} cannot fit the requested panels at the style's fixed pt sizes."
        + detail + " Increase canvas width/height, reduce cols, or simplify labels/legends.",
        axis=getattr(last, "axis", "width"),
        required_width=getattr(last, "required_width", None),
        required_height=getattr(last, "required_height", None),
        subplot=getattr(last, "subplot", None),
    )
