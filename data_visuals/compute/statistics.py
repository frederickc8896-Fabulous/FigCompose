"""
compute/statistics.py
=====================
统计指标计算 — 提供细粒度的统计量。

职责:
    - 百分位数 (Q1, Q3, P95 等任意分位数)
    - 四分位距 (IQR)
    - 异常值检测
    - 置信区间
    - 单列/多列汇总统计

不负责:
    - groupby 聚合 (属于 aggregation.py)
    - 布局 / 渲染
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Dict, Any, Tuple


# ── 百分位数 / 分位数 ────────────────────────────────────────

def percentile(
    series: pd.Series,
    q: Union[float, List[float]],
) -> Union[float, Dict[str, float], pd.Series]:
    """
    计算单个或多个分位数。

    Parameters
    ----------
    series : pd.Series
    q : float | list of float
        分位点，范围 [0, 1]。例如 0.5=中位数, 0.95=95%分位数

    Returns
    -------
    float | pd.Series

    Examples
    --------
    >>> percentile(df["accuracy"], 0.95)
    >>> percentile(df["accuracy"], [0.25, 0.5, 0.75, 0.95])
    """
    return series.quantile(q)


def quartiles(
    series: pd.Series,
) -> Dict[str, float]:
    """
    返回 Q1(25%), Q2(50%, median), Q3(75%)。

    Returns
    -------
    dict: {"Q1": ..., "Q2": ..., "Q3": ..., "IQR": ...}
    """
    q1 = float(series.quantile(0.25))
    q2 = float(series.quantile(0.50))
    q3 = float(series.quantile(0.75))
    return {
        "Q1": q1,
        "Q2": q2,
        "Q3": q3,
        "IQR": q3 - q1,
    }


def iqr(series: pd.Series) -> float:
    """计算四分位距 IQR = Q3 - Q1"""
    return float(series.quantile(0.75) - series.quantile(0.25))


def five_number_summary(series: pd.Series) -> Dict[str, float]:
    """五数概括: min, Q1, median, Q3, max"""
    return {
        "min": float(series.min()),
        "Q1": float(series.quantile(0.25)),
        "median": float(series.median()),
        "Q3": float(series.quantile(0.75)),
        "max": float(series.max()),
    }


# ── 异常值检测 ───────────────────────────────────────────────

def detect_outliers(
    series: pd.Series,
    method: str = "iqr",
    multiplier: float = 1.5,
) -> pd.Series:
    """
    返回异常值掩码（True = 异常值）。

    Parameters
    ----------
    series : pd.Series
    method : "iqr" | "zscore"
        iqr: Q1 - multiplier*IQR 到 Q3 + multiplier*IQR
        zscore: |z| > multiplier
    multiplier : float
        iqr 方法默认 1.5; zscore 方法默认 3.0

    Returns
    -------
    pd.Series(bool)
    """
    if method == "iqr":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr_val = q3 - q1
        lower = q1 - multiplier * iqr_val
        upper = q3 + multiplier * iqr_val
        return (series < lower) | (series > upper)

    elif method == "zscore":
        z = (series - series.mean()) / series.std(ddof=0)
        return z.abs() > multiplier

    else:
        raise ValueError(f"不支持的异常值检测方法: {method}，可选 'iqr' | 'zscore'")


def outlier_bounds(
    series: pd.Series,
    multiplier: float = 1.5,
) -> Dict[str, float]:
    """
    返回箱线图异常值的上下界（whisker 端点）。

    Returns
    -------
    dict: {"lower": ..., "upper": ...}
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr_val = q3 - q1
    return {
        "lower": float(q1 - multiplier * iqr_val),
        "upper": float(q3 + multiplier * iqr_val),
    }


# ── 置信区间 ──────────────────────────────────────────────────

def confidence_interval(
    series: pd.Series,
    confidence: float = 0.95,
) -> Dict[str, float]:
    """
    计算均值的置信区间（基于 t 分布）。

    Parameters
    ----------
    series : pd.Series
    confidence : float
        置信水平，默认 0.95

    Returns
    -------
    dict: {"mean": ..., "ci_lower": ..., "ci_upper": ..., "confidence": ...}
    """
    from scipy import stats

    n = series.count()
    mean = series.mean()
    sem = series.sem()
    ci_range = sem * stats.t.ppf((1 + confidence) / 2.0, df=n - 1)

    return {
        "mean": float(mean),
        "ci_lower": float(mean - ci_range),
        "ci_upper": float(mean + ci_range),
        "confidence": confidence,
        "n": int(n),
    }


# ── 单列汇总统计 (适用于 box plot 所需全部统计量) ──────────

def summarize(
    series: pd.Series,
    percentiles: Optional[List[float]] = None,
) -> Dict[str, float]:
    """
    对单列输出一份完整统计摘要，方便下游 chart 直接消费。

    包含:
        count, min, max, mean, median, var, std,
        Q1, Q3, IQR, P95, skewness, kurtosis

    Parameters
    ----------
    series : pd.Series
    percentiles : list of float | None
        额外分位数，默认附加 P95(0.95)

    Returns
    -------
    dict

    Examples
    --------
    >>> summarize(df["accuracy"])
    {
        "count": 7, "min": 0.12, "max": 0.90,
        "mean": 0.51, "median": 0.46, "var": 0.08, "std": 0.28,
        "Q1": 0.23, "Q3": 0.79, "IQR": 0.56, "P95": 0.89,
        "skewness": 0.12, "kurtosis": -1.07
    }
    """
    if percentiles is None:
        percentiles = [0.95]

    stats_dict: Dict[str, float] = {
        "count": int(series.count()),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "var": float(series.var(ddof=0)),
        "std": float(series.std(ddof=0)),
        "Q1": float(series.quantile(0.25)),
        "Q3": float(series.quantile(0.75)),
        "IQR": float(series.quantile(0.75) - series.quantile(0.25)),
        "skewness": float(series.skew()),
        "kurtosis": float(series.kurtosis()),
    }

    # 附加用户指定的分位数
    for p in percentiles:
        label = f"P{int(p * 100)}"
        stats_dict[label] = float(series.quantile(p))

    return stats_dict


def summarize_grouped(
    df: pd.DataFrame,
    group_by: Union[str, List[str]],
    value_col: str,
    percentiles: Optional[List[float]] = None,
) -> pd.DataFrame:
    """
    分组后对每组输出完整统计摘要 — 特别适合 box plot 数据准备。

    Parameters
    ----------
    df : pd.DataFrame
    group_by : str | list of str
    value_col : str
        需要统计的数值列
    percentiles : list of float | None

    Returns
    -------
    pd.DataFrame — 每行一个分组，列为各统计量

    Examples
    --------
    >>> summarize_grouped(df, group_by="method", value_col="score")
          method  count  mean   std   Q1  median   Q3  IQR  P95
    0        A      5  0.81  0.01  0.80    0.81  0.82  0.02  0.83
    1        B      5  0.86  0.02  0.85    0.87  0.88  0.03  0.89
    """
    if isinstance(group_by, str):
        group_by = [group_by]

    results = []
    for keys, group in df.groupby(group_by, sort=True):
        # 处理单分组键/多分组键
        if isinstance(keys, tuple):
            row = dict(zip(group_by, keys))
        else:
            row = {group_by[0]: keys}

        row.update(summarize(group[value_col], percentiles=percentiles))
        results.append(row)

    return pd.DataFrame(results)


def overall_mean(df: pd.DataFrame, value_columns: List[str]) -> Dict[str, float]:
    """Compute overall means for one or more numeric columns."""
    result: Dict[str, float] = {}
    for col in value_columns:
        if col in df.columns:
            result[col] = float(df[col].mean())
    return result


def loess_smooth(
    df: pd.DataFrame,
    *,
    x_col: str,
    y_col: str,
    group_col: Optional[str] = None,
    frac: float = 0.6,
) -> pd.DataFrame:
    """Compute trend lines using LOWESS and return a drawable DataFrame."""
    from statsmodels.nonparametric.smoothers_lowess import lowess

    frames: List[pd.DataFrame] = []
    grouped = [(None, df)] if not group_col or group_col not in df.columns else df.groupby(group_col, sort=True)
    for group_value, group_df in grouped:
        work = group_df[[x_col, y_col] + ([group_col] if group_col and group_col in group_df.columns else [])].dropna().copy()
        if work.empty:
            continue
        work = work.sort_values(x_col)
        smoothed = lowess(work[y_col].to_numpy(), work[x_col].to_numpy(), frac=frac, return_sorted=True)
        trend_df = pd.DataFrame({x_col: smoothed[:, 0], y_col: smoothed[:, 1]})
        if group_col and group_value is not None:
            trend_df[group_col] = group_value
        frames.append(trend_df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=[x_col, y_col] + ([group_col] if group_col else []))


def density_curve(
    df: pd.DataFrame,
    *,
    value_col: str,
    group_col: Optional[str] = None,
    points: int = 200,
) -> pd.DataFrame:
    """Compute Gaussian KDE curves for histogram density rendering."""
    from scipy.stats import gaussian_kde

    frames: List[pd.DataFrame] = []
    grouped = [(None, df)] if not group_col or group_col not in df.columns else df.groupby(group_col, sort=True)
    for group_value, group_df in grouped:
        series = group_df[value_col].dropna()
        if len(series) < 2 or series.nunique() < 2:
            continue
        kde = gaussian_kde(series.to_numpy())
        x_min = float(series.min())
        x_max = float(series.max())
        x_values = np.linspace(x_min, x_max, points)
        density = kde(x_values)
        density_df = pd.DataFrame({value_col: x_values, "density": density})
        if group_col and group_value is not None:
            density_df[group_col] = group_value
        frames.append(density_df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=[value_col, "density"] + ([group_col] if group_col else []))


def boxplot_payload(
    df: pd.DataFrame,
    *,
    group_by: Union[str, List[str]],
    value_col: str,
    multiplier: float = 1.5,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return box-summary rows and outlier rows for grouped boxplots."""
    if isinstance(group_by, str):
        group_by = [group_by]

    summaries: List[Dict[str, Any]] = []
    outlier_rows: List[pd.DataFrame] = []
    for keys, group in df.groupby(group_by, sort=True):
        if isinstance(keys, tuple):
            base = dict(zip(group_by, keys))
        else:
            base = {group_by[0]: keys}

        series = group[value_col].dropna()
        if series.empty:
            continue
        q = quartiles(series)
        bounds = outlier_bounds(series, multiplier=multiplier)
        inlier_series = series[(series >= bounds["lower"]) & (series <= bounds["upper"])]
        summary = {
            **base,
            value_col: float(series.mean()),
            "min": float(inlier_series.min() if not inlier_series.empty else series.min()),
            "max": float(inlier_series.max() if not inlier_series.empty else series.max()),
            "Q1": q["Q1"],
            "median": q["Q2"],
            "Q3": q["Q3"],
            "IQR": q["IQR"],
            "lower": bounds["lower"],
            "upper": bounds["upper"],
        }
        summaries.append(summary)

        mask = detect_outliers(series, method="iqr", multiplier=multiplier)
        if mask.any():
            outlier_df = group.loc[series.index[mask], group_by + [value_col]].copy()
            outlier_rows.append(outlier_df)

    summary_df = pd.DataFrame(summaries)
    outliers_df = pd.concat(outlier_rows, ignore_index=True) if outlier_rows else pd.DataFrame(columns=group_by + [value_col])
    return summary_df, outliers_df
