# 整篇论文的配色预设

提供 12 套原始精选搭配，每套包含分类色、热力图/混淆矩阵的配套连续色阶，
以及参考线、趋势线、误差线与双轴颜色。原始分类色号与顺序保持不变。

[全部分类色卡](../demo_outputs/colors/color_catalog_categorical.png) · [SVG](../demo_outputs/colors/color_catalog_categorical.svg)

每行色卡是一套独立组合。直接使用其预设名即可应用到整张 Figure：

```python
from data_visuals import plot

fig = plot(
    "demo/data/benchmark.csv",
    x="dataset", group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "line", "x": "epoch", "metric": "f1"},
        {"kind": "heatmap", "x": "dataset", "y": "model", "metric": "accuracy"},
    ],
    canvas={"width": 180},
    style="modern",
    palette="curated-5-default",
)
fig.render("figure.svg")
```

| 原表容量 | 整图预设名 |
|---|---|
| 2 色 | `curated-2-default`、`curated-2-cool`、`curated-2-warm` |
| 5 色 | `curated-5-default`、`curated-5-cool`、`curated-5-warm` |
| 7 色 | `curated-7-default`、`curated-7-cool`、`curated-7-warm` |
| 10 色 | `curated-10-default`、`curated-10-muted`、`curated-10-vibrant` |

`general` 和 `modern` 两种排版风格均默认使用 `curated-10-default`。
更换 `palette` 保持原字体与排版；`style="modern"` 是排版风格，不是颜色预设。
`list_color_presets()` 可列出全部 12 套预设。高级入口也支持
`Figure(..., palette="curated-5-default")` 或 `FigureConfig(palette="curated-5-default")`。

预设仅保存原色表的引用与配套关系，没有再硬编码一份分类色号。
少于容量时按原顺序取前面的颜色；超过容量会报错，提示换更大容量预设。
容量按同一字段的完整类别域计算，包含子图筛选前的类别，以保留跨子图颜色一致性。
这些固定搭配不会自动换桶或生成新色。

原名 `cool/warm` 保留历史命名，不代表这一行全是纯冷色或纯暖色。
`ours_color` 仅保留原表的强调色元信息，色卡标注为 highlight；它不会自动绑定名为 Ours 的方法。
分类颜色不能直接等同于数量渐变：固定预设为矩阵图匹配现有的连续色阶，
逐图 `color_scheme` 仍可显式覆盖。预设的颜色映射继续以类别域的排序为准。

[精选整图示例](../demo_outputs/colors/curated_5_default.png) 使用原 5 色 default、同一 CSV 和正式 `plot()` 入口。
箱线填充、直方图与散点使用透明度，所以同一基础色在不同图种中会有自然明暗变化。
颜色不同并不保证大量曲线易于区分；图例、线型、标记和拆分面板仍有作用。

同一 Figure 的完整类别域继续保证筛选子图颜色不变。若多份 CSV 的类别集合不同，
需要长期锁定具体模型颜色，可通过 `FigureConfig.category_colors` 记录显式映射。
预设不会猜测不同文件之间的类别对应关系，也没有期刊合规或无障碍认证含义。

配色定义集中于 [utils/colors.py](../data_visuals/utils/colors.py)，主题 JSON 用
`color.preset` 引用默认预设，避免为同一排版复制多份主题文件。
底层 `get_palette(size, style)` 仍可访问表格中的原始搭配，例如 `get_palette(5, "cool")`。

运行 `python demo/demo_color_catalog.py` 生成完整分类色卡、[连续色阶与原始节点](../demo_outputs/colors/color_catalog_sequential.png)
及精选整图示例，均含 PNG/SVG。色卡直接读取同一注册表，后续修改颜色后可重新生成。
