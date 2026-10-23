"""Rotated categorical labels must remain outside the plotting region."""

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from data_visuals import plot


@pytest.mark.parametrize("kind", ["bar", "box"])
def test_vertical_x_tick_labels_stay_below_the_axis(kind):
    data = pd.DataFrame([
        {"category": f"Task {category:02}", "value": category + repeat / 10}
        for category in range(14) for repeat in range(3)
    ])
    figure = plot(
        data, x="category", plots=[{"kind": kind, "metric": "value"}],
        canvas={"width": 90, "height": 75}, style="modern",
    )
    rendered = figure.render()
    try:
        ax = rendered.axes[0]
        renderer = rendered.canvas.get_renderer()
        ticks = ax.get_xticklabels()
        assert all(tick.get_rotation() == 90 for tick in ticks)
        assert all(tick.get_window_extent(renderer).y1 <= ax.bbox.y0 - 2 for tick in ticks)
    finally:
        plt.close(rendered)
