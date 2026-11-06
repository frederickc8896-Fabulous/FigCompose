"""Reusable multi-track cohort panel, driven only by context.payload."""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Patch, Rectangle, Wedge
from data_visuals.core import PanelContext, PanelResult


SEX = ("Female", "Male")
ETHNICITY = ("Asian", "Black", "Caucasian", "Hispanic")
RESPONSE = ("Sensitive", "Intermediate", "Resistant")
CATEGORIES = (*SEX, *ETHNICITY, *RESPONSE)
N_PARTICIPANTS = 72


def _xy(theta, radius):
    return radius * np.cos(theta), radius * np.sin(theta)


def draw_participant_ring(ax, ctx: PanelContext) -> PanelResult:
    frame = ctx.payload
    n = len(frame)
    step = 270.0 / n
    angles = np.deg2rad(180 + (np.arange(n) + 0.5) * step)
    texts = []
    ink = ctx.text_color
    muted = "#77828f"
    grid = "#e0e5ec"
    outline = "#c4cdd8"

    def tint(color, amount=0.92):
        """Use a quiet tint of the resolved paper palette for track surfaces."""
        foreground = np.asarray(to_rgb(color))
        background = np.asarray(to_rgb(ctx.background))
        return foreground * (1 - amount) + background * amount

    def text(x, y, label, **kwargs):
        artist = ax.text(x, y, label, **ctx.text_kwargs("body", **kwargs))
        texts.append(artist)
        return artist

    def arc(radius, color=grid, linewidth=0.4, **kwargs):
        theta = np.linspace(np.pi, 2.5 * np.pi, 400)
        ax.plot(*_xy(theta, radius), color=color, linewidth=linewidth, **kwargs)

    tracks = (
        ("sex", SEX, 0.265, 0.355),
        ("ethnicity", ETHNICITY, 0.375, 0.495),
        ("response", RESPONSE, 0.515, 0.625),
    )
    for column, _categories, inner, outer in tracks:
        for index, value in enumerate(frame[column]):
            patch = Wedge((0, 0), outer,
                          180 + index * step + 0.045,
                          180 + (index + 1) * step - 0.045,
                          width=outer - inner, facecolor=ctx.color(value),
                          edgecolor=ctx.background, linewidth=0.45)
            ax.add_patch(patch)
        arc(inner, color=outline, linewidth=0.35)
        arc(outer, color=outline, linewidth=0.35)

    numeric = (
        ("bmi", 0.655, 0.855, (15, 42), (15, 28, 42), ctx.color("Male")),
        ("age", 0.89, 1.13, (18, 80), (18, 49, 80), ctx.color("Black")),
    )
    for column, inner, outer, limits, ticks, color in numeric:
        ax.add_patch(Wedge((0, 0), outer, 180, 450, width=outer - inner,
                           facecolor=tint(color, .965), edgecolor="none", zorder=0))
        for tick in ticks:
            radius = inner + (tick - limits[0]) / (limits[1] - limits[0]) * (outer - inner)
            arc(radius, linewidth=0.4, linestyle=(0, (1.5, 2.5)), zorder=1)
            text(-radius, 0.035, f"{tick:g}", ha="center", va="bottom", fontsize=8,
                 color=muted, rotation=90)
        # True radial cell boundaries, with numerical scales independent by track.
        theta = np.deg2rad(180 + np.arange(n + 1) * step)
        boundaries = [[_xy(angle, inner), _xy(angle, outer)] for angle in theta]
        ax.add_collection(LineCollection(boundaries, colors=grid, linewidths=.25, zorder=1))
        radii = inner + (frame[column].to_numpy() - limits[0]) / (limits[1] - limits[0]) * (outer - inner)
        stems = [[_xy(angle, inner), _xy(angle, radius)] for angle, radius in zip(angles, radii)]
        ax.add_collection(LineCollection(stems, colors=[tint(color, .62)],
                                         linewidths=.65, zorder=2))
        ax.scatter(*_xy(angles, radii), s=13, color=color, linewidths=0.35,
                   edgecolors=ctx.background, zorder=4)
        arc(inner, color=outline, linewidth=.45, zorder=2)
        arc(outer, color=outline, linewidth=.45, zorder=2)

    # Tangential labels remain upright on both halves of the circle.
    for angle, identifier in zip(angles, frame["participant"]):
        degrees = np.rad2deg(angle) % 360
        rotation = degrees - 90
        if 90 < rotation <= 270:
            rotation -= 180
        text(*_xy(angle, 1.19), identifier, rotation=rotation,
             rotation_mode="anchor", ha="center", va="center", fontsize=8, color=muted)

    # The centre explains the unit of observation, rather than adding a second key.
    ax.add_patch(Circle((0, 0), .235, facecolor=tint(ctx.color("Intermediate"), .87),
                        edgecolor="none", zorder=0))
    text(0, .065, f"{n}", ha="center", va="center", fontsize=23,
         color=ctx.color("Black"))
    text(0, -.025, "participants", ha="center", va="center", fontsize=9)
    text(0, -.105, "Synthetic cohort", ha="center", va="center", fontsize=8, color=muted)

    def distribution(column, x, low, high, color, heading):
        values = frame[column].to_numpy()
        y = 0.26 + (values - low) / (high - low) * 0.70
        # Fixed jitter, never dependent on sizing-trial invocation counts.
        jitter = np.random.default_rng(419 if column == "age" else 420).uniform(-0.035, 0.035, n)
        for tick in (low, (low + high) / 2, high):
            ty = .26 + (tick - low) / (high - low) * .70
            ax.plot([x - .085, x + .085], [ty, ty], color=grid, linewidth=.4, zorder=0)
        q1, median, q3 = np.quantile(y, (0.25, 0.5, 0.75))
        ax.add_patch(Rectangle((x - 0.065, q1), 0.13, q3 - q1,
                               facecolor=tint(color, .93), edgecolor=color,
                               linewidth=0.65, zorder=1))
        ax.plot([x, x], [y.min(), q1], color=color, linewidth=0.65)
        ax.plot([x, x], [q3, y.max()], color=color, linewidth=0.65)
        ax.plot([x - .025, x + .025], [y.min(), y.min()], color=color, linewidth=0.65)
        ax.plot([x - .025, x + .025], [y.max(), y.max()], color=color, linewidth=0.65)
        ax.scatter(x + jitter, y, s=10, color=color, alpha=0.72,
                   edgecolors=ctx.background, linewidths=.25, zorder=3)
        ax.plot([x - 0.065, x + 0.065], [median, median], color=color, linewidth=1.2, zorder=5)
        text(x, 1.035, heading, ha="center", va="bottom", fontsize=9, fontweight="bold")
        text(x, 0.185, f"{np.median(values):.1f}", ha="center", va="center", fontsize=10,
             color=color, fontweight="bold")

    distribution("age", -1.025, 18, 80, numeric[1][-1], "Age\n(years)")
    distribution("bmi", -0.765, 15, 42, numeric[0][-1], "BMI")

    def stacked_summary(column, categories, x, heading):
        y = 0.265
        height = 0.70
        for category in categories:
            proportion = float((frame[column] == category).mean())
            color = ctx.color(category)
            ax.add_patch(Rectangle((x - 0.05, y), 0.10, height * proportion,
                                   facecolor=color, edgecolor=ctx.background, linewidth=0.5))
            if proportion >= 0.14:
                r, g, b = to_rgb(color)
                foreground = ink if 0.2126*r + 0.7152*g + 0.0722*b > 0.61 else "white"
                text(x, y + height * proportion / 2, f"{100 * proportion:.1f}%",
                     ha="center", va="center", fontsize=8, rotation=90, color=foreground)
            y += height * proportion
        ax.add_patch(Rectangle((x - 0.05, 0.265), 0.10, height,
                               facecolor="none", edgecolor=outline, linewidth=0.5))
        text(x, 1.0, heading, rotation=58, ha="left", va="bottom", fontsize=8.5,
             fontweight="bold")

    stacked_summary("response", RESPONSE, -0.57, "Response")
    stacked_summary("ethnicity", ETHNICITY, -0.435, "Ethnicity")
    stacked_summary("sex", SEX, -0.31, "Sex")
    text(-1.025, 0.11, "median", ha="center", va="center", fontsize=8, color=muted)
    text(-0.765, 0.11, "median", ha="center", va="center", fontsize=8, color=muted)
    text(-.69, 1.225, "COHORT PROFILE", ha="center", va="center", fontsize=8,
         color=muted)
    text(0.70, 1.23, "One participant per angle  /  Ordered by age", ha="center", fontsize=8,
         color=muted)
    text(0, -1.34, "Inside → out: sex, ethnicity, response, BMI and age.\n"
         "The open sector summarises the same cohort; all values are simulated.",
         ha="center", va="center", fontsize=8, color=muted, linespacing=1.5)
    ax.set_aspect("equal", adjustable="box")
    prefixes = {category: heading for heading, categories in
                (("Sex", SEX), ("Ethnicity", ETHNICITY), ("Response", RESPONSE))
                for category in categories}
    handles = []
    for category in CATEGORIES:
        handle = Patch(facecolor=ctx.color(category), edgecolor="none",
                       label=f"{prefixes[category]}: {category}")
        handle._figcompose_legend_key = category
        handles.append(handle)
    return PanelResult(artists=texts, legend_handles=handles)
