"""
data/ — 数据层
==============
负责将外部数据源转换为内部可用结构。

模块:
    loader    : CSV / Excel / JSON 文件读取
    schema    : 列类型识别 (categorical / numerical) + 校验
    transform : 结构变换 (pivot / melt / filter / rename)
    labels    : 显示名映射 (raw value → display name)
"""

from data_visuals.data.loader import (
    load,
    load_csv,
    load_excel,
    load_json,
)

from data_visuals.data.schema import (
    ColumnType,
    infer_column_types,
    get_columns,
    get_numerical_columns,
    get_categorical_columns,
    validate_columns,
    schema_summary,
    validate_header,
    check_numeric_columns,
)

from data_visuals.data.transform import (
    pivot,
    melt,
    select_columns,
    drop_columns,
    filter_rows,
    drop_na,
    fill_na,
    rename_columns,
    sort_values,
    cast_column,
)

from data_visuals.data.labels import (
    load_labels_from_yaml,
    resolve_labels,
)

__all__ = [
    # loader
    "load",
    "load_csv",
    "load_excel",
    "load_json",
    # schema
    "ColumnType",
    "infer_column_types",
    "get_columns",
    "get_numerical_columns",
    "get_categorical_columns",
    "validate_columns",
    "schema_summary",
    "validate_header",
    "check_numeric_columns",
    # transform
    "pivot",
    "melt",
    "select_columns",
    "drop_columns",
    "filter_rows",
    "drop_na",
    "fill_na",
    "rename_columns",
    "sort_values",
    "cast_column",
    # labels
    "load_labels_from_yaml",
    "resolve_labels",
]
