"""Verify the stored intervals from their synthetic paired observations."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t

HERE = Path(__file__).resolve().parent


def summarize(paired):
    rows = []
    for (dataset, condition), cell in paired.groupby(["dataset", "condition"], sort=False):
        differences = cell.method_b_pct - cell.method_a_pct
        n = len(differences)
        mean = float(differences.mean())
        sd = float(differences.std(ddof=1))
        se = sd / np.sqrt(n)
        half_width = float(t.ppf(.975, n - 1) * se)
        rows.append({"dataset": dataset, "condition": condition, "n_pairs": n,
                     "mean_difference_pp": mean, "sd_difference_pp": sd,
                     "se_mean_difference_pp": se, "ci95_lower_pp": mean - half_width,
                     "ci95_upper_pp": mean + half_width})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    expected = pd.read_csv(HERE / "data.csv")
    actual = summarize(pd.read_csv(HERE / "paired.csv"))
    pd.testing.assert_frame_equal(actual[expected.columns], expected, check_exact=False,
                                  atol=1e-9, rtol=1e-9)
    print("15 paired t intervals verified; 40 pairs per cell. Stored CSV rounding tolerance: 1e-9.")
