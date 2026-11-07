"""Quiet native styling shared by the distribution templates."""

from matplotlib.patches import Patch


def handles(context, bundle):
    return tuple(Patch(facecolor=context.color(name), edgecolor="none", label=name)
                 for name in bundle["names"])


def style_axes(ax, context, *, xlabel=None, ylabel=None):
    fonts = context.font_sizes
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    ax.grid(False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color("#a3acb7")
        ax.spines[side].set_linewidth(.65)
    ax.tick_params(axis="both", which="major", labelsize=fonts["tick"], length=2.5,
                   width=.6, color="#a3acb7", labelcolor="#465363", pad=3)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(context.font_family)
    if xlabel is not None:
        ax.set_xlabel(xlabel, fontsize=fonts["axis_label"], fontfamily=context.font_family,
                      color="#465363", labelpad=4)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=fonts["axis_label"], fontfamily=context.font_family,
                      color="#465363", labelpad=4)
