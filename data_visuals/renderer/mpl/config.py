"""
renderer/mpl/config.py
======================
Theme-to-matplotlib translation layer.

Consumes themes/general.json and utils/colors.py; outputs matplotlib-compatible
values (rcParams dicts, colour lists, Line2D style fragments).

This is the ONLY module in renderer/mpl/ that reads the theme dict.  Every other
mpl module receives resolved values — NEVER a raw theme dict.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any, List, Optional

import matplotlib
from cycler import cycler
from matplotlib.colors import LinearSegmentedColormap

from data_visuals.themes import load_theme, get_color_palette
from data_visuals.utils.colors import get_color_preset, SEQUENTIAL_SCHEMES


# Only visual defaults belong to the renderer. In particular, do not reset a
# caller's backend, interactive behaviour, figure DPI/size, or output paths.
# Starting from Matplotlib's defaults (rather than the current rcParams) keeps
# notebook/seaborn styles from silently changing the same figure declaration.
_VISUAL_RC_PREFIXES = (
    "axes.", "axes3d.", "boxplot.", "contour.", "errorbar.", "font.",
    "grid.", "hatch.", "hist.", "image.", "legend.", "lines.", "mathtext.",
    "patch.", "path.", "scatter.", "text.", "xtick.", "ytick.",
)
_VISUAL_RC_KEYS = ("polaraxes.grid", "pcolor.shading", "pcolormesh.snap")


# ═══════════════════════════════════════════════════════════════
# MPL config — resolved once per figure, passed to all builders
# ═══════════════════════════════════════════════════════════════

class MplConfig:
    """Theme resolved for matplotlib consumption.

    All values are plain Python types (str, float, bool, list, dict).
    Created once at the start of
    ``figure_to_matplotlib()`` and passed down to every chart builder.
    """

    def __init__(self, theme_name: str, n_groups: int = 0, *, palette: Optional[str] = None,
                 physical: bool = False):
        theme = deepcopy(load_theme(theme_name))
        self.physical = physical
        self.publication = deepcopy(theme.get("publication", {}))
        self.font_sizes = {
            "main_title": 11.0, "title": 9.0, "axis_label": 8.0,
            "tick": 7.0, "legend": 8.0,
            **self.publication.get("font_sizes", {}),
        }
        self.canvas_padding = float(self.publication.get("canvas_padding", 6.0))
        self.panel_gap = float(self.publication.get("panel_gap", 8.0))
        self.min_plot_width = float(self.publication.get("min_plot_width", 45.0))
        self.min_plot_height = float(self.publication.get("min_plot_height", 40.0))
        if physical:
            for section, overrides in self.publication.items():
                if isinstance(overrides, dict) and section != "font_sizes":
                    theme[section] = {**theme.get(section, {}), **overrides}

        # ── font ──
        font = theme.get("font", {})
        raw_family = font.get("family", "Times New Roman, serif")
        self.font_requested = raw_family
        # theme stores CSS-style "Times New Roman, serif"; split and resolve
        self.font_family = self._resolve_font(raw_family)
        self.title_weight = font.get("title_weight", "bold")
        self.cell_title_weight = font.get("cell_title_weight", "bold")
        self.axis_label_weight = font.get("axis_label_weight", "bold")
        self.tick_label_weight = font.get("tick_label_weight", "normal")
        self.legend_title_weight = font.get("legend_title_weight", "bold")

        # Spacing is relative to the resolved title/tick sizes, independent of DPI.
        layout = theme.get("layout", {})
        self.subplot_title_gap = float(layout.get("subplot_title_gap", 0.6))
        self.title_legend_gap = float(layout.get("title_legend_gap", 0.4))
        self.legend_axes_gap = float(layout.get("legend_axes_gap", 0.5))
        self.panel_padding = float(layout.get("panel_padding", 0.25))
        self.vertical_alignment_tolerance = float(layout.get("vertical_alignment_tolerance", 0.5))

        # ── colour ──
        color = dict(theme.get("color", {}))
        if palette is not None:
            color.update(get_color_preset(palette))
        elif color.get("preset"):
            color = {**get_color_preset(color["preset"]), **color}
        # The selected palette is fully resolved here; downstream lookups must
        # not reapply the theme's original preset over an explicit override.
        color.pop("preset", None)
        self._palette_theme = {"color": color}
        self.background = color.get("background", "#ffffff")
        self.text_color = color.get("text", "#1a1a1a")
        self.axis_color = color.get("axis", "#333333")
        self.grid_color = color.get("grid", "#e0e0e0")
        self.grid_opacity = color.get("grid_opacity", 0.3)
        self.ref_line_color = color.get("reference_line", "#999999")
        self.mean_line_color = color.get("mean_line", "#c0392b")
        self.trend_line_color = color.get("trend_line", "#c0392b")
        self.error_bar_color = color.get("error_bar", "#333333")
        self.y2_color = color.get("y2_axis", "#c0392b")
        self.palette_style = color.get("palette_style", "default")
        self.sequential = color.get("sequential", "viridis")

        # ── categorical palette (via colors.py) ──
        self.categorical_palette: List[str] = self.get_palette(n_groups)

        # ── sequential colormap ──
        self.sequential_cmap: Any = self._resolve_sequential()

        # ── line ──
        line = theme.get("line", {})
        self.line_stroke_width = float(line.get("stroke_width", 2.5))
        self.error_bar_width = float(line.get("error_bar_width", 1.8))
        self.marker_size = float(line.get("marker_size", 60))
        self.scatter_point_size = float(line.get("scatter_point_size", 80))
        self.ref_dash = self._dash_to_mpl(line.get("reference_dash", [5, 3]))
        self.mean_line_dash = self._dash_to_mpl(line.get("mean_line_dash", [5, 3]))

        # ── axis ──
        axis = theme.get("axis", {})
        self.axis_grid = axis.get("grid", False)
        self.axis_grid_color = axis.get("grid_color", "#c0c0c0")
        self.axis_tick_size = float(axis.get("tick_size", 5))
        self.axis_tick_width = float(axis.get("tick_width", 1))
        self.axis_domain_width = float(axis.get("domain_width", 1))
        self.axis_domain_color = axis.get("domain_color", "#333333")
        self.axis_label_padding = float(axis.get("label_padding", 5))
        self.axis_title_padding = float(axis.get("title_padding", 10))

        # ── bar ──
        bar = theme.get("bar", {})
        self.bar_stroke = bar.get("stroke", "#000000")
        self.bar_stroke_width = float(bar.get("stroke_width", 0.5))
        self.bar_width_ratio = float(bar.get("width_ratio", 0.6))

        # ── boxplot ──
        box = theme.get("boxplot", {})
        self.box_stroke = box.get("stroke", "#000000")
        self.box_stroke_width = float(box.get("stroke_width", 2.0))
        self.box_median_stroke_width = float(box.get("median_stroke_width", 2.0))
        self.box_size = float(box.get("size", 30))

        # ── heatmap ──
        hm = theme.get("heatmap", {})
        self.heatmap_cell_stroke = hm.get("cell_stroke", "#000000")
        self.heatmap_cell_stroke_width = float(hm.get("cell_stroke_width", 0.8))

        # ── legend ──
        legend = theme.get("legend", {})
        self.legend_symbol_size = float(legend.get("symbol_size", 80))
        self.legend_padding = float(legend.get("padding", 8))

        # ── y2_axis ──
        y2 = theme.get("y2_axis", {})
        self.y2_dash = self._dash_to_mpl(y2.get("line_dash", [4, 2]))

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _resolve_font(raw_family: str) -> str:
        """Resolve CSS-style 'Times New Roman, serif' → first available font."""
        import matplotlib.font_manager as fm
        available = {f.name for f in fm.fontManager.ttflist}
        for name in raw_family.split(","):
            name = name.strip().strip("'").strip('"')
            if name in available:
                return name
        # Fallback: return the generic category (last part) or 'serif'
        generic = raw_family.split(",")[-1].strip()
        return generic if generic in ("serif", "sans-serif", "monospace") else "serif"

    def _resolve_sequential(self) -> Any:
        """Build matplotlib colormap from SEQUENTIAL_SCHEMES."""
        if self.sequential in SEQUENTIAL_SCHEMES:
            return LinearSegmentedColormap.from_list(
                self.sequential, SEQUENTIAL_SCHEMES[self.sequential]
            )
        # fallback: let matplotlib resolve named colormap
        import matplotlib.pyplot as plt
        try:
            return plt.get_cmap(self.sequential)
        except ValueError:
            return plt.get_cmap("viridis")

    def get_palette(self, n_groups: int = 0) -> List[str]:
        """Return the same theme palette for standalone and grouped series."""
        return get_color_palette(self._palette_theme, n_groups)

    def get_color(self, idx: int) -> str:
        """Safe indexed access to categorical palette."""
        return self.categorical_palette[idx % len(self.categorical_palette)]

    @staticmethod
    def _dash_to_mpl(dash_spec):
        """Convert [dash, gap] list → matplotlib (offset, (dash, gap)) tuple."""
        if not dash_spec or len(dash_spec) < 2:
            return (0, (5, 3))
        return (0, (int(dash_spec[0]), int(dash_spec[1])))

    def grid_alpha_color(self) -> tuple:
        """Return (r, g, b, alpha) tuple for grid lines."""
        hex_str = self.axis_grid_color.lstrip("#")
        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        return (r / 255, g / 255, b / 255, self.grid_opacity)

    def rcparams(self) -> Dict[str, Any]:
        """Resolve a complete visual style for a temporary ``rc_context``.

        Defaults are independent of the ambient Matplotlib style; theme values
        then take precedence. The rendering/export contexts restore all caller
        settings on exit, including when a callback or layout check fails.
        """
        values = {
            key: deepcopy(value) for key, value in matplotlib.rcParamsDefault.items()
            if key.startswith(_VISUAL_RC_PREFIXES) or key in _VISUAL_RC_KEYS
        }
        family = self.font_family.casefold()
        sans = "sans" in family or family in ("arial", "helvetica", "verdana")
        values.update({
            "font.family": [self.font_family],
            "font.size": self.font_sizes["axis_label"] if self.physical else 10.0,
            "mathtext.fontset": "dejavusans" if sans else "stix",
            "text.usetex": False,
            "pdf.fonttype": 42,
            "pdf.use14corefonts": False,
            "ps.fonttype": 42,
            "ps.useafm": False,
            "svg.fonttype": "none",
            "svg.hashsalt": "data_visuals",
            "text.color": self.text_color,
            "figure.facecolor": self.background,
            "figure.edgecolor": self.background,
            "figure.frameon": True,
            "figure.autolayout": False,
            "figure.constrained_layout.use": False,
            "savefig.transparent": False,
            "savefig.edgecolor": "auto",
            "savefig.facecolor": "auto",
            "axes.facecolor": self.background,
            "axes.edgecolor": self.axis_domain_color,
            "axes.linewidth": self.axis_domain_width,
            "axes.labelcolor": self.text_color,
            "axes.labelweight": self.axis_label_weight,
            "axes.labelpad": self.axis_title_padding,
            "axes.titleweight": self.cell_title_weight,
            "axes.titlecolor": self.text_color,
            "axes.prop_cycle": cycler(color=self.categorical_palette),
            "axes.axisbelow": True,
            # Grids are selected by chart semantics in style_axis: matrices
            # need cell boundaries, while radar keeps its polar value rings.
            "axes.grid": False,
            "axes.autolimit_mode": "data",
            "axes.xmargin": 0.05,
            "axes.ymargin": 0.05,
            "axes.zmargin": 0.05,
            "lines.linewidth": self.line_stroke_width,
            "lines.markersize": self.marker_size ** 0.5,
            "lines.markeredgewidth": max(0.5, self.axis_domain_width),
            "patch.edgecolor": self.axis_domain_color,
            "patch.linewidth": self.axis_domain_width,
            "grid.color": self.axis_grid_color,
            "grid.alpha": self.grid_opacity,
            "grid.linewidth": 0.5,
            "xtick.color": self.text_color,
            "ytick.color": self.text_color,
            "xtick.major.size": self.axis_tick_size,
            "ytick.major.size": self.axis_tick_size,
            "xtick.major.width": self.axis_tick_width,
            "ytick.major.width": self.axis_tick_width,
            "xtick.major.pad": self.axis_label_padding,
            "ytick.major.pad": self.axis_label_padding,
        })
        return values
