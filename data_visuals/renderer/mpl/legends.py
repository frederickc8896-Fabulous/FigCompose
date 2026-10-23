"""Measured, relocatable legends in physical design points.

Legend rows deliberately use separate Matplotlib legends. This keeps both the
visible and artist label order row-major and lets automatic packing retain the
established independently centered rows. An optional single surrounding frame
belongs to the entire block, rather than putting a border around every row.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Integral, Real

from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch

from data_visuals.layout.placement import LayoutError


_SPACING_DEFAULTS = {
    "columnspacing": 8.0,
    "labelspacing": 3.0,
    "handlelength": 12.0,
    "handletextpad": 4.0,
    "borderpad": 3.0,
}


def _positive_number(value, name, *, zero=False):
    if (isinstance(value, bool) or not isinstance(value, Real)
            or not math.isfinite(value) or (value < 0 if zero else value <= 0)):
        suffix = "nonnegative" if zero else "positive"
        raise ValueError(f"legend {name} must be a finite {suffix} number in points")
    return float(value)


def _wrap(text, width, measure):
    """Wrap words, then long tokens, without dropping any label characters."""
    lines = []
    for paragraph in str(text).split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if current and measure(candidate) > width:
                lines.append(current)
                current = ""
            if measure(word) <= width:
                current = f"{current} {word}" if current else word
                continue
            # Only oversized tokens need character splitting. Binary search
            # their longest fitting prefix rather than remeasuring every
            # character of ordinary prose on every candidate wrap width.
            while word:
                low, high = 1, len(word)
                while low < high:
                    middle = (low + high + 1) // 2
                    if measure(word[:middle]) <= width:
                        low = middle
                    else:
                        high = middle - 1
                part, word = word[:low], word[low:]
                if word:
                    lines.append(part)
                else:
                    current = part
        lines.append(current)
    return "\n".join(lines)


class MeasuredLegend:
    """Measure once and place repeatedly without cloning legend artists.

    ``max_width``, ``max_height``, coordinates, and spacing options are points
    (1/72 inch), independent of the figure's DPI. ``ncols=None`` packs measured
    rows automatically; an explicit positive integer fixes the number of
    entries in each row, with only the final row allowed to be shorter. Labels
    can wrap but columns and font size are never silently reduced.

    ``order`` and ``labels`` mappings are intentionally handled by the caller,
    where original category keys remain available. ``gap`` is likewise an
    external layout reservation and is not part of this block's own extent.
    """

    def __init__(self, fig, handles, labels, options, cfg, *, default_fontsize,
                 max_width, max_height=None, orientation="horizontal"):
        if options is None:
            options = {}
        if not isinstance(options, Mapping):
            raise ValueError("legend options must be a mapping")
        if orientation not in ("horizontal", "vertical"):
            raise ValueError("legend orientation must be horizontal or vertical")
        self.fig, self.cfg = fig, cfg
        self.options = dict(options)
        self.handles, self.labels = list(handles), [str(label) for label in labels]
        if len(self.handles) != len(self.labels):
            raise ValueError("legend handles and labels must have equal lengths")
        fontsize = options.get("fontsize")
        self.fontsize = _positive_number(default_fontsize if fontsize is None else fontsize, "fontsize")
        self.spacing = {
            name: _positive_number(options.get(name, default), name, zero=True)
            for name, default in _SPACING_DEFAULTS.items()
        }
        for name in ("visible", "frameon"):
            if name in options and not isinstance(options[name], bool):
                raise ValueError(f"legend {name} must be a boolean")
        self.visible = options.get("visible", True)
        self.frameon = options.get("frameon", False)
        self.ncols = options.get("ncols")
        if self.ncols is not None and (isinstance(self.ncols, bool)
                                      or not isinstance(self.ncols, Integral) or self.ncols <= 0):
            raise ValueError("legend ncols must be a positive integer or None")
        self.orientation = orientation
        self.artists = []
        self.rows = []
        self.frame = None
        self.width = self.height = 0.0
        self._removed = False
        self._position = None
        self._text_widths = {}
        self.reflow(max_width, max_height=max_height)

    def _measure(self, handles, labels):
        """Return an actual Matplotlib row and its bbox in physical points."""
        legend = self.fig.legend(
            handles, labels, loc="upper left", bbox_to_anchor=(0, 1),
            bbox_transform=self.fig.transFigure, borderaxespad=0,
            ncols=len(handles), frameon=False, borderpad=0,
            handlelength=self.spacing["handlelength"] / self.fontsize,
            handletextpad=self.spacing["handletextpad"] / self.fontsize,
            columnspacing=self.spacing["columnspacing"] / self.fontsize,
            labelspacing=self.spacing["labelspacing"] / self.fontsize,
            prop={"family": self.cfg.font_family, "size": self.fontsize},
            numpoints=1, scatterpoints=1,
        )
        legend.set_in_layout(False)
        for label in legend.get_texts():
            label.set_color(self.cfg.text_color)
        bbox = legend.get_window_extent(self.fig.canvas.get_renderer())
        scale = 72.0 / self.fig.dpi
        return legend, bbox.width * scale, bbox.height * scale

    def _wrapped_row(self, handles, labels, width):
        """Fit a fixed row by wrapping its widest labels, using real bboxes."""
        legend, measured_w, measured_h = self._measure(handles, labels)
        if measured_w <= width + 1e-6:
            return legend, measured_w, measured_h
        renderer = self.fig.canvas.get_renderer()
        prop = FontProperties(family=self.cfg.font_family, size=self.fontsize)
        pixels_per_point = self.fig.dpi / 72.0
        natural = [text.get_window_extent(renderer).width / pixels_per_point
                   for text in legend.get_texts()]
        legend.remove()
        overhead = measured_w - sum(natural)

        def measure(text):
            key = self.fig.dpi, text
            if key not in self._text_widths:
                self._text_widths[key] = renderer.get_text_width_height_descent(text, prop, False)[0]
            return self._text_widths[key]

        minimum = [max((measure(char) / pixels_per_point for char in str(label)
                        if not char.isspace()), default=0.0) for label in labels]
        minimum_width = overhead + sum(minimum)
        available = width - overhead

        def width_error(required):
            return LayoutError(
                "Legend columns cannot fit at the requested font and spacing; "
                "increase canvas width or request fewer legend columns.",
                axis="width", required_width=required + 2 * self.spacing["borderpad"],
            )

        if minimum_width > width + 1e-6:
            raise width_error(minimum_width)
        # Allocate text widths numerically before constructing another Legend.
        # Every entry retains enough room for its widest glyph, and short
        # entries keep their natural width. This is a cheap water-fill search;
        # only the resulting wrapped row needs real artist-bbox validation.
        for _ in range(4):
            low, high = 0.0, max(natural, default=0.0)
            for _ in range(28):
                cap = (low + high) / 2
                total = sum(min(natural_w, max(minimum_w, cap))
                            for natural_w, minimum_w in zip(natural, minimum))
                if total <= available:
                    low = cap
                else:
                    high = cap
            widths = [min(natural_w, max(minimum_w, low)) * pixels_per_point
                      for natural_w, minimum_w in zip(natural, minimum)]
            wrapped = [_wrap(label, label_width, measure)
                       for label, label_width in zip(labels, widths)]
            trial, trial_w, trial_h = self._measure(handles, wrapped)
            if trial_w <= width + 1e-6:
                return trial, trial_w, trial_h
            trial.remove()
            # Font/backend rounding can differ slightly from isolated glyph
            # metrics. Reclaim the observed excess, then validate again.
            available -= trial_w - width + 0.05
            if available < sum(minimum) - 1e-6:
                raise width_error(max(minimum_width, trial_w))
        raise width_error(trial_w)

    def _automatic_rows(self, width):
        result = []
        start = 0
        while start < len(self.handles):
            row = self._wrapped_row(self.handles[start:start + 1], self.labels[start:start + 1], width)
            end = start + 1
            while end < len(self.handles):
                candidate = self._measure(self.handles[start:end + 1], self.labels[start:end + 1])
                if candidate[1] > width + 1e-6:
                    candidate[0].remove()
                    break
                row[0].remove()
                row = candidate
                end += 1
            result.append(row)
            start = end
        return result

    def reflow(self, max_width, max_height=None):
        """Remeasure at a new available size; obsolete artists are removed."""
        previous_position = self._position
        self.remove()
        self._removed = False
        self.max_width = _positive_number(max_width, "max_width")
        self.max_height = (None if max_height is None else
                           _positive_number(max_height, "max_height"))
        if not self.visible or not self.handles:
            return self
        padding = self.spacing["borderpad"]
        inner_width = self.max_width - 2 * padding
        before = set(self.fig.legends)
        try:
            if inner_width <= 0:
                raise LayoutError("Legend padding fills its available width; increase canvas width.",
                                  axis="width", required_width=2 * padding + 1)
            ncols = self.ncols
            if ncols is None and self.orientation == "vertical":
                ncols = 1
            if ncols is None:
                self.rows = self._automatic_rows(inner_width)
            else:
                self.rows = [self._wrapped_row(self.handles[i:i + ncols], self.labels[i:i + ncols],
                                              inner_width)
                             for i in range(0, len(self.handles), ncols)]
            self.width = max(row[1] for row in self.rows) + 2 * padding
            self.height = (sum(row[2] for row in self.rows) + 2 * padding
                           + self.spacing["labelspacing"] * (len(self.rows) - 1))
            if self.max_height is not None and self.height > self.max_height + 1e-6:
                raise LayoutError("Legend rows exceed the available height; increase canvas height "
                                  "or request more legend columns.", axis="height",
                                  required_width=self.width, required_height=self.height)
            self.artists = [row[0] for row in self.rows]
            if self.frameon:
                self.frame = FancyBboxPatch(
                    (0, 0), 0, 0, boxstyle="square,pad=0", transform=self.fig.transFigure,
                    facecolor=self.cfg.background, edgecolor=self.cfg.axis_domain_color,
                    linewidth=0.7, zorder=4.5, clip_on=False,
                )
                self.frame.set_in_layout(False)
                self.fig.add_artist(self.frame)
                self.artists.insert(0, self.frame)
            for artist in self.artists:
                artist.set_visible(False)
            if previous_position is not None:
                self.place(*previous_position)
            return self
        except BaseException:
            for legend in set(self.fig.legends) - before:
                legend.remove()
            self.remove()
            raise

    def place(self, x, y):
        """Set the block's upper-left corner in design points, revealing it."""
        if self._removed:
            raise RuntimeError("Cannot place a removed legend; call reflow first")
        if not all(isinstance(v, Real) and math.isfinite(v) for v in (x, y)):
            raise ValueError("legend placement coordinates must be finite numbers")
        self._position = float(x), float(y)
        fig_w, fig_h = self.fig.get_size_inches() * 72.0
        padding = self.spacing["borderpad"]
        top = y + padding
        for legend, row_w, row_h in self.rows:
            # Side legends and explicitly tabulated rows need a stable handle
            # column. Only automatic horizontal wrapping keeps the historical
            # independently centered rows.
            left = (x + padding if self.orientation == "vertical" or self.ncols is not None
                    else x + (self.width - row_w) / 2)
            legend.set_bbox_to_anchor((left / fig_w, 1 - top / fig_h),
                                      transform=self.fig.transFigure)
            legend.set_visible(True)
            top += row_h + self.spacing["labelspacing"]
        if self.frame is not None:
            self.frame.set_bounds(x / fig_w, 1 - (y + self.height) / fig_h,
                                  self.width / fig_w, self.height / fig_h)
            self.frame.set_visible(True)
        return self.artists

    def remove(self):
        """Remove all owned artists, including the optional enclosing frame."""
        for artist in self.artists:
            if artist.figure is not None:
                artist.remove()
        self.artists = []
        self.rows = []
        self.frame = None
        self.width = self.height = 0.0
        self._removed = True
