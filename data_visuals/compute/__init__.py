"""
compute/ — 统计计算层
=====================
纯统计计算，不涉及任何渲染或布局逻辑。

模块:
    aggregation  : groupby + 聚合算子 (mean, std, var, median, count, min, max, sum)
    statistics   : 细粒度统计量 (Q1, Q3, IQR, P95, 异常值, 置信区间)
    preprocess   : 数据预处理 (标准化, 百分比, 排序)
"""

from data_visuals.compute.aggregation import (
    AGGREGATORS,
    aggregate,
    describe,
    correlation_matrix,
)

from data_visuals.compute.statistics import (
    percentile,
    quartiles,
    iqr,
    five_number_summary,
    detect_outliers,
    outlier_bounds,
    confidence_interval,
    summarize,
    summarize_grouped,
)

from data_visuals.compute.preprocess import (
    normalize_minmax,
    normalize_zscore,
    to_percentage,
    sort_by_column,
)

__all__ = [
    # aggregation
    "AGGREGATORS",
    "aggregate",
    "describe",
    "correlation_matrix",
    # statistics
    "percentile",
    "quartiles",
    "iqr",
    "five_number_summary",
    "detect_outliers",
    "outlier_bounds",
    "confidence_interval",
    "summarize",
    "summarize_grouped",
    # preprocess
    "normalize_minmax",
    "normalize_zscore",
    "to_percentage",
    "sort_by_column",
]
