"""Measured decorations and equal data rectangles for a small-multiple grid."""

from __future__ import annotations

from matplotlib.font_manager import FontProperties

from data_visuals.core.facets import normalize_facets
from data_visuals.layout.placement import LayoutError


class FacetLayout:
    """Keep shared decorations outside a complete rectangular panel grid.

    Cell widths may differ because only the outside axes display tick labels.
    The *data* rectangles have equal sizes, with all spacing in design points.
    """

    def __init__(self, fig, spec, cfg, renderer, width, height, padding, header, footer=0,
                 left_reserve=0, right_reserve=0):
        self._figure = fig
        self.options = normalize_facets(spec.get("facets", {}))
        self.cfg, self.width, self.height = cfg, width, height
        self.padding, self.gap = padding, cfg.panel_gap
        self.footer = footer
        self.rows, self.cols = spec["grid"]["rows"], spec["grid"]["cols"]
        panels = [sp for sp in spec["subplots"] if sp.get("chart")]
        positions = {(sp["row"], sp["col"]) for sp in panels}
        if (positions != {(r, c) for r in range(self.rows) for c in range(self.cols)}
                or any(sp.get("row_span", 1) != 1 or sp.get("col_span", 1) != 1 for sp in panels)):
            raise ValueError("facets requires a complete rectangular grid without spanning panels")
        for field, count in (("row_labels", self.rows), ("col_labels", self.cols)):
            if field in self.options and len(self.options[field]) != count:
                raise ValueError(f"facets.{field} must contain {count} labels")
        self.font = max(8.0, panels[0]["font_sizes"]["axis_label"])
        self.heading_font = max(9.0, panels[0]["font_sizes"]["title"])
        self.artists = []
        self.label_widths = {}
        self.col_header_width = 0.0
        self.row_header_height = 0.0
        left, bottom, top = padding + left_reserve, padding + footer, header + padding
        for field in ("ylabel", "row_labels"):
            if self.options.get(field):
                values = self.options[field]
                labels = [values] if isinstance(values, str) else values
                extents = [self._extent(renderer, text, rotation=90,
                                        heading=field == "row_labels") for text in labels]
                extent = max(width for width, _ in extents)
                if field == "row_labels":
                    self.row_header_height = max(height for _, height in extents)
                self.label_widths[field] = (left, extent)
                left += extent + 4
        if self.options.get("xlabel"):
            bottom += self._extent(renderer, self.options["xlabel"])[1] + 5
        if self.options.get("col_labels"):
            extents = [self._extent(renderer, text, heading=True)
                       for text in self.options["col_labels"]]
            self.col_header_width = max(width for width, _ in extents)
            top += max(height for _, height in extents) + 5
        self.body = {"x": left, "y": top, "w": width - left - padding - right_reserve,
                     "h": height - top - bottom}
        if min(self.body["w"], self.body["h"]) <= 0:
            raise LayoutError("Shared facet labels fill the canvas; increase its dimensions.",
                              axis="width" if self.body["w"] <= 0 else "height",
                              required_width=width + max(0, 40 - self.body["w"]),
                              required_height=height + max(40, -self.body["h"]))

    def _extent(self, renderer, text, rotation=0, heading=False):
        artist = self._text(0, 0, text, rotation=rotation, heading=heading)
        bbox = artist.get_window_extent(renderer)
        artist.remove()
        return bbox.width, bbox.height

    def _text(self, x, y, text, *, rotation=0, heading=False, **kwargs):
        # Coordinates are design points from the upper-left corner.
        return self.figure.text(
            x / self.width, 1 - y / self.height, text,
            fontproperties=FontProperties(family=self.cfg.font_family,
                                         size=self.heading_font if heading else self.font,
                                         weight="bold" if heading else "normal"),
            color=self.cfg.text_color, ha="center", va="center", rotation=rotation,
            **kwargs)

    @property
    def figure(self):
        return self._figure

    def initial_boxes(self):
        body = self.body
        w = (body["w"] - self.gap * (self.cols - 1)) / self.cols
        h = (body["h"] - self.gap * (self.rows - 1)) / self.rows
        return {(r, c): {"x": body["x"] + c * (w + self.gap),
                         "y": body["y"] + r * (h + self.gap), "w": w, "h": h}
                for r in range(self.rows) for c in range(self.cols)}

    def place(self, records, requirements):
        left = [max(requirements[r, c]["left"] for r in range(self.rows)) for c in range(self.cols)]
        right = [max(requirements[r, c]["right"] for r in range(self.rows)) for c in range(self.cols)]
        top = [max(requirements[r, c]["top"] for c in range(self.cols)) for r in range(self.rows)]
        bottom = [max(requirements[r, c]["bottom"] for c in range(self.cols)) for r in range(self.rows)]
        w = (self.body["w"] - sum(left) - sum(right) - self.gap * (self.cols - 1)) / self.cols
        h = (self.body["h"] - sum(top) - sum(bottom) - self.gap * (self.rows - 1)) / self.rows
        minima = [record["minimum"] if isinstance(record["minimum"], tuple)
                  else (record["minimum"], record["minimum"]) for record in records.values()]
        # Each heading stays within its own data rectangle's extent. Checking
        # only the outer canvas would allow long middle headings to collide
        # with their neighbours while still fitting the export frame.
        min_w = max(self.col_header_width, max(minimum[0] for minimum in minima))
        min_h = max(self.row_header_height, max(minimum[1] for minimum in minima))
        if w < min_w or h < min_h:
            raise LayoutError("Shared facet axes do not fit; increase canvas width or height.",
                              axis="width" if w < min_w else "height",
                              required_width=self.width + max(0, min_w - w) * self.cols,
                              required_height=self.height + max(0, min_h - h) * self.rows)
        for (r, c), record in records.items():
            x = self.body["x"] + sum(left[:c]) + sum(right[:c]) + c * (w + self.gap)
            y = self.body["y"] + sum(top[:r]) + sum(bottom[:r]) + r * (h + self.gap)
            record["box"] = {"x": x, "y": y, "w": w + left[c] + right[c],
                             "h": h + top[r] + bottom[r]}
            record["zone"] = {"x": x + left[c], "y": y + top[r], "w": w, "h": h}

    def decorate(self, records):
        first, last = records[0, 0]["zone"], records[self.rows - 1, self.cols - 1]["zone"]
        center_x = (first["x"] + last["x"] + last["w"]) / 2
        center_y = (first["y"] + last["y"] + last["h"]) / 2
        if self.options.get("xlabel"):
            self.artists.append(self._text(center_x, self.height - self.padding - self.footer - self.font / 2,
                                           self.options["xlabel"]))
        if self.options.get("ylabel"):
            x, extent = self.label_widths["ylabel"]
            self.artists.append(self._text(x + extent / 2, center_y, self.options["ylabel"], rotation=90))
        for r, label in enumerate(self.options.get("row_labels", [])):
            zone = records[r, 0]["zone"]
            x, extent = self.label_widths["row_labels"]
            self.artists.append(self._text(x + extent / 2, zone["y"] + zone["h"] / 2,
                                           label, rotation=90, heading=True))
        for c, label in enumerate(self.options.get("col_labels", [])):
            zone = records[0, c]["zone"]
            self.artists.append(self._text(zone["x"] + zone["w"] / 2,
                                           self.body["y"] - self.heading_font / 2 - 5,
                                           label, heading=True))
        return self.artists
