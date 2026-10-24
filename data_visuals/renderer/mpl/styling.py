"""Consistent decorations for native axes, selected by chart semantics."""

from __future__ import annotations


def style_axis(ax, fs, cfg, secondary=False, chart_type=None):
    """Apply physical typography without undoing chart-specific decorations.

    Spine visibility is deliberately left alone: its initial value comes from
    the isolated rc defaults, and a native callback can explicitly hide spines.
    Secondary axes retain their own metric colour. Matrix builders own their
    minor grids at cell boundaries; ordinary theme grids must not cross cells.
    """
    ax.set_facecolor(cfg.background)
    for spine in ax.spines.values():
        if not secondary:
            spine.set_color(cfg.axis_domain_color)
        spine.set_linewidth(cfg.axis_domain_width)
    ax.tick_params(labelsize=fs["tick"], width=cfg.axis_tick_width, length=cfg.axis_tick_size,
                   pad=cfg.axis_label_padding,
                   **({} if secondary else {"colors": cfg.text_color}))
    if ax.name == "3d":
        # Axes3D.grid does not accept the Cartesian grid styling contract.
        ax.grid(cfg.axis_grid and not secondary)
        for axis in ax._axis_map.values():
            axis.line.set_color(cfg.axis_domain_color)
            axis.line.set_linewidth(cfg.axis_domain_width)
    elif secondary:
        ax.grid(False, which="both")
    elif chart_type in ("heatmap", "confusion"):
        ax.set_axisbelow(True)
        ax.grid(False, which="major")
        # Cell strokes are borders rather than faint quantitative guides.
        # Keep their opacity independent from the ordinary theme grid.
        for axis in (ax.xaxis, ax.yaxis):
            for tick in axis.get_minor_ticks():
                tick.gridline.set_alpha(1.0)
                tick.gridline.set_linestyle("-")
    else:
        ax.set_axisbelow(True)
        ax.grid(cfg.axis_grid, which="major",
                **({"color": cfg.axis_grid_color, "alpha": cfg.grid_opacity,
                    "linewidth": 0.5} if cfg.axis_grid else {}))
    axes = list(ax._axis_map.values())
    for label in [label for axis in axes for label in axis.get_ticklabels()]:
        label.set_fontfamily(cfg.font_family)
        label.set_fontweight(cfg.tick_label_weight)
    for label in (axis.label for axis in axes):
        label.set_fontsize(fs["axis_label"])
        label.set_fontfamily(cfg.font_family)
        label.set_fontweight(cfg.axis_label_weight)
        if not secondary:
            label.set_color(cfg.text_color)
    for text in (axis.get_offset_text() for axis in axes):
        text.set_fontsize(fs["tick"])
        text.set_fontfamily(cfg.font_family)
