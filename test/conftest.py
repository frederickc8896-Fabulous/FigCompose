"""Shared fixtures for the data and Matplotlib test suite."""

import pandas as pd
import pytest


@pytest.fixture
def sample_df():
    """Small benchmark-like DataFrame."""
    return pd.DataFrame({
        "method": ["A", "A", "B", "B"],
        "dataset": ["D1", "D2", "D1", "D2"],
        "accuracy": [0.81, 0.83, 0.84, 0.86],
        "std": [0.02, 0.01, 0.01, 0.02],
    })
