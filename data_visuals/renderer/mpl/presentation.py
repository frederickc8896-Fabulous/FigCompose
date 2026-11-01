"""Shared presentation primitives derived from the resolved paper palette.

Data colours are never reassigned here. These helpers derive quiet supporting
marks and readable text without adding another categorical colour system.
"""
from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgb


def blend(color, background, fraction):
    """Mix a colour towards a background; ``fraction`` is the background share."""
    if not np.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError("A blend fraction must be finite and between zero and one.")
    return tuple((1 - fraction) * np.asarray(to_rgb(color))
                 + fraction * np.asarray(to_rgb(background)))


def luminance(color):
    """Relative sRGB luminance used for annotation contrast."""
    rgb = np.asarray(to_rgb(color))
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    return float(linear @ (.2126, .7152, .0722))


def contrast_ratio(foreground, background):
    first, second = luminance(foreground), luminance(background)
    return (max(first, second) + .05) / (min(first, second) + .05)


def best_text_color(background, candidates):
    """Choose the most readable original candidate without changing its value."""
    return max(candidates, key=lambda color: contrast_ratio(color, background))


def readable_text_color(color, background="white", *, fallback="#26313f", minimum=4.5):
    """Retain a legible accent or blend its text towards a readable ink colour.

    This only affects annotation foregrounds. The corresponding data glyph and
    legend keep the original categorical colour, including its semantic slot.
    """
    if contrast_ratio(color, background) >= minimum:
        return to_rgb(color)
    target = fallback
    if contrast_ratio(target, background) < minimum:
        target = best_text_color(background, (fallback, "black", "white"))
    low, high = 0.0, 1.0
    for _ in range(24):
        middle = (low + high) / 2
        if contrast_ratio(blend(color, target, middle), background) >= minimum:
            high = middle
        else:
            low = middle
    return blend(color, target, high)
