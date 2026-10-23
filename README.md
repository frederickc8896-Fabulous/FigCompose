# PaperFig

指定 CSV、指标、图种和风格，生成排版与配色统一的论文 Figure。
底层使用 Matplotlib，统一处理物理尺寸、字号、共享图例与留白，导出 PDF / SVG / PNG。
当前为 Alpha，接口仍在迭代。

## 安装

需要 Python 3.10+。克隆仓库后运行：

```bash
python -m pip install -e .
```

默认字体为 **Times New Roman**，需由操作系统提供；缺少时回退其他衬线字体。
跨设备精确复现版式需要一致的字体与依赖版本。当前通过 Python API 调用。

## 快速开始

下面的示例可直接运行；也可以把 DataFrame 替换为带表头的 CSV 路径。

```python
import pandas as pd
from data_visuals import plot

data = pd.DataFrame({
    "dataset": ["A", "A", "B", "B"],
    "model": ["Base", "Ours", "Base", "Ours"],
    "accuracy": [0.78, 0.86, 0.81, 0.89],
    "latency": [14.0, 10.0, 15.0, 11.0],
})

fig = plot(
    data,  # 或 "results.csv"
    x="dataset", group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "line", "metric": "latency"},
    ],
    canvas={"width": 180},
    style="modern", palette="curated-5-warm",
    legend={"scope": "shared", "position": "bottom", "ncols": 2},
)
fig.render("figure.pdf")
fig.render("figure.png", dpi=300)
```

- `plots` 每项对应一个子图；`cols=2` 可限制每行最多两个子图。
- `x/group` 为全局默认列，子图可以覆盖；`group=None` 关闭该子图分组。
- `canvas` 默认单位为 mm；只给宽度时测量后自动求高，也可指定 `unit="in"`。
  `{"width": 180, "height": 110}` 固定整图尺寸，装不下时报告布局错误。
- `style` 支持 `general`、`modern`；`palette` 独立选择配色。
  `from data_visuals import list_color_presets` 可查询全部 12 套精选配色。
- 导出支持 `.pdf`、`.svg`、`.png`。DPI 只改变 PNG 像素密度，不改变物理尺寸与版式。

## 图种与统计口径

| `kind` | 主要字段 | 默认行为 |
|---|---|---|
| `bar` | `x`, `metric`, 可选 `group/error` | 按组取均值，可带误差线或堆叠 |
| `line` | `x`, `metric`, 可选 `group` | 重复 X 观测取均值 |
| `scatter` | `x`, `metric`, 可选 `group/size` | 保留观测，可使用预计算区间 |
| `box` | `x`, `metric`, 可选 `group` | 箱线图 |
| `histogram` | `metric`, 可选 `group` | 数值分布 |
| `heatmap` | `x`, `y`, `metric` | 按两维分组取均值 |
| `confusion` | `x`, `y`, 可选 `metric` | 计数或汇总给定数量 |
| `pie` / `donut` | `group`, 可选 `metric` | 按类别求和；省略份额列时计数 |
| `radar` | `x`, `metric`, 可选 `group` | 重复观测取均值，至少三个完整指标轴 |

`metric` 对普通图和雷达图表示 Y 值，对直方图表示分布值，对矩阵图和饼图表示数量或颜色值。
饼图要求份额有限、非负且总和为正。雷达图使用长表，不自动归一化或补齐缺失指标。

图例可设置位置、列数、字号、边框、顺序和显示名；子图通过 `chart_opts={"legend": {...}}` 覆盖。
默认物理字号：主标题 11、子标题 9、轴标签 8、刻度 7、图例 8 pt，单图与多图保持一致。

## 自定义 Matplotlib 面板

高级入口 `data_visuals.core.Figure` 支持跨格布局、宽高权重与原生绘制函数。
纯自定义 Figure 不需要 CSV 或占位 DataFrame：

```python
from data_visuals.core import Figure, PanelResult

def draw_module(ax, ctx):
    text = ax.text(
        0.5, 0.5, "Encoder", ha="center", va="center",
        bbox={"boxstyle": "round,pad=0.6", "facecolor": ctx.background},
        **ctx.text_kwargs(),
    )
    return PanelResult(artists=[text])

paper = Figure(rows=1, cols=1, canvas={"width": 90}, legend=False)
paper[0, 0].custom(draw_module, min_size=(120, 70), preferred_aspect=2)
paper.render("model.svg")
```

`.custom()` 接受 `projection="polar"`、`"3d"` 或已注册的 Matplotlib 投影名，
`axes_options` 传入原生轴构造参数。需要显示坐标轴时指定 `axes="on"`。
`min_size` 使用 pt；`box_aspect` 表示面板绘图区的宽/高。

通过 `ctx.text_kwargs()`、`ctx.color()` 使用统一样式；通过 `PanelResult` 返回测量对象、
图例句柄或 `layout(ax, ctx)` 尺寸更新函数。框架管理整图，回调负责内部节点与连线。
自动尺寸试绘和正式导出会重新执行回调，回调应可重复构建且不产生外部副作用。
自定义回调属于运行时对象，含回调的 Spec 不能序列化为 JSON。

Git 仅维护绘图库及运行所需配置。演示、输出、测试、详细文档和实验数据留在本地，均已忽略。
