# CSV 到论文 Figure

用户选择 CSV、指标、图种和风格；底层负责字号、配色、图例、刻度与留白。
入口为 `from data_visuals import plot`，返回现有 `Figure` 对象。

```python
from data_visuals import plot

fig = plot(
    "demo/data/benchmark.csv",
    x="dataset",
    group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "line", "x": "epoch", "metric": "f1"},
        {"kind": "box", "metric": "latency"},
        {"kind": "histogram", "metric": "accuracy", "group": None},
    ],
    canvas={"width": 180},
    style="modern",
    palette="curated-10-default",
)
fig.render("figure.svg")
fig.render("figure.pdf")
fig.render("figure.png", dpi=300)
```

示例 CSV 随仓库提供；替换路径和字段即可使用自己的数据。也可以直接传入 DataFrame。
用 `python demo/demo_simple_csv.py` 可生成 `demo_outputs/quickstart/simple_csv.svg/.png`。

一项 `plots` 声明就是一个子图，按列表顺序排列。同一个指标可以出现在不同子图中。
根据画布宽高、图种和实测装饰空间选择网格；可用 `cols=2` 等指定上限。
`cols` 是最多列数，布局器可能使用更少列。末行自动等分铺满宽度。
子图标题默认使用指标列名，多子图自动加 `(a)`、`(b)` 等编号；可用每项的 `title` 覆盖，
或用 `title=None` 省略该子图标题。顶层 `title` 设置整图标题，不传则不预留主标题。

| 图种 `kind` | 指标 `metric` 的含义 | 还需要的字段 |
|---|---|---|
| `bar` | 柱高；可传指标列表叠绘 | `x`，可选 `group/error` |
| `line` | 折线 Y；可传指标列表叠绘 | `x`，可选 `group` |
| `scatter` | 散点 Y | `x`，可选 `group/size` |
| `box` | 分布观测值 | `x`，可选 `group` |
| `histogram` | 统计分布的观测值 | 可选 `group` |
| `heatmap` | 颜色值 | 显式指定 `x/y` |
| `confusion` | 可选：已统计的计数列；不传则统计样本数 | 显式指定 `x/y` |

普通图继承全局 `x/group`，每项显式设置的值优先。直方图只继承 `group`，
不会把全局分类横轴当作分布值；矩阵图需要明确两条坐标轴，不继承全局 `x/group`。
如果某个子图只要总体分布，设置 `group=None`。

```python
fig = plot(
    "results.csv",
    plots=[
        {"kind": "scatter", "x": "latency", "metric": "accuracy", "group": "model"},
        {"kind": "heatmap", "x": "dataset", "y": "model", "metric": "accuracy"},
        {"kind": "confusion", "x": "prediction", "y": "truth", "normalize": True},
    ],
    style="general",
)
```

此例要求 CSV 含 `prediction/truth` 等字段；自带的 benchmark.csv 仅用于前面的四图示例。
混淆矩阵的 `x` 是横轴、`y` 是纵轴，归一化语义沿用现有行归一化规则。

每项仍可使用已有图种的数据映射和选项，例如 `error="std"`、`bins=12`、
`horizontal=True`、`y_columns=["Baseline", "Ours"]`。`y_columns` 筛选的是分组取值；
挑选指标用 `metric`。同一项中不同时指定 `metric` 与其对应的 `y/x/value`。

```python
fig = plot(
    "results.csv",
    x="dataset",
    group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy", "error": "std"},
        {"kind": "bar", "metric": ["precision", "recall"]},
    ],
    csv_options={"encoding": "utf-8-sig", "delimiter": ","},
)
```

普通柱图按组取均值；折线的重复观测按 `(x, group)` 取均值。误差、归一化和缺失值
处理沿用 [Matplotlib 后端规则](matplotlib-backend.md)，不会根据列名自动选择统计方法。

`canvas={"width": 180, "height": 110}` 固定最终整图 180 × 110 mm，包含标题、图例、
轴标签和外边距。`canvas={"width": 90}` 固定宽 90 mm，自动测量所需高度。
省略 canvas 或传 None 时继承 `FigureConfig.canvas`，默认 180 mm 宽、自动高度。
支持 `unit="in"`；拒绝 px、空字典、未知键、布尔值和非正/非有限尺寸。
固定宽高装不下时抛出 `LayoutError`；自动高度不会通过增加高度掩盖宽度不足。

可选风格为 `general` 与 `modern`，默认字体均为 Times New Roman；相同角色默认使用实际 pt 字号：主标题 11、
子标题 9、轴标签 8、刻度及色条 7、全局和局部图例 8。改变 canvas 或子图数量不缩放字体。
导出 DPI 不参与布局；180 mm 宽在 300 DPI 下约为 2126 px，在 600 DPI 下约为 4252 px。
配色独立通过 `palette` 选择，共 12 套原始精选搭配；内置风格默认 `curated-10-default`。
例如 `palette="curated-5-default"` 固定保留原 5 色组合，类别超出容量时提示选择更大色板。
每套同时提供分类色、顺序色阶和辅助线颜色，原始分类色号及顺序保持不变，
详见 [配色预设](color-presets.md)。它们没有期刊合规或无障碍认证含义。
同一 Figure 的共享分组复用颜色与图例，筛选后的子图保持颜色。跨文件长期固定某类别颜色，
仍需使用高级 `FigureConfig.category_colors`；CSV 入口不猜测跨文件的类别全集。

需要覆盖图例时，直接给 `plot()` 增加 `legend={"position": "bottom", "ncols": 3, "fontsize": 8}`；
`legend=False` 隐藏图例并回收空间。每个 `plots` 项也可用
`chart_opts={"legend": {"position": "upper right"}}` 单独覆盖。
无分组的多指标图默认保留局部图例，显式 `legend={"scope": "shared"}` 可让它们共用整图图例。
全部位置、间距、锚点和继承规则见 [图例配置](matplotlib-backend.md#图例配置)。

`plot()` 读取并校验数据，返回后可 `build()`、`render()` 或 `show()`；不会自动写文件。
高级跨行跨列模板、宽高权重和自定义颜色可使用 `data_visuals.core.Figure` 与 `FigureConfig`。
两种入口共用计算、版式与渲染管线。
高级入口显式使用 `aspect/base/cell_base` 时沿用旧尺寸路径；与显式 canvas 同时提供会报错。
详细约束见 [Canvas 字段契约](../CANVAS_CONTRACT.md)。
