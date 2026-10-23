# Matplotlib 论文绘图后端

当前唯一渲染链路为 `Figure → compute → layout → FigureSpec → Matplotlib → SVG/PDF/PNG`。
用户声明数据、字段和布局；字号、配色、图例与装饰空间在底层统一处理。

简单使用可从包级 `plot(csv, plots=[...], style=...)` 进入，数量、网格与子标题自动安排，
参见 [CSV 简洁入口](simple-api.md)。它继续委托上述管线，不增加另一套渲染规则。

## 固定画布与布局

- `canvas={"width": 180, "height": 110}` 固定最终整图 180 × 110 mm，包含主标题、图例、轴标注和色条。
- 只给 `width` 时自动测量所需高度；省略 canvas 使用全局默认 180 mm 宽、自动高度。
- `unit` 支持 mm（默认）或 in，内部统一转换为 pt。单图和多图使用相同尺寸定义。
- CSV 入口根据宽高、图种和真实装饰空间选择网格；`cols` 为每行面板数上限。
- 高级 Figure 保留显式网格、跨格和宽高权重。显式 `aspect/base/cell_base` 则进入旧尺寸路径，
  保留原大画布及比例字号；不得与显式 canvas 混用。
- 普通网格、宽高权重、跨行跨列共用 FigureSpec 几何；同图子标题、轴标签、刻度使用统一字号。
- Matplotlib 对真实文字边界进行有限次数测量，将装饰留在 cell 内，并对齐列边缘。
  上下留白仅在装饰高度接近时对齐，长刻度标签或独立图例不会压缩邻图的绘图区。
- 子标题使用独立的可见间距；有局部图例时分别预留标题到图例、图例到图面的距离。
  默认比例集中在主题的 `layout` 字段，按字号缩放，导出 DPI 不改变间距。
- 双轴保持与主轴相同的绘图区；色条使用单独预留的 cax，不会改变热力图的宽度。
- 不使用 `tight_layout`、`constrained_layout` 或导出时的 tight 裁切。
- 空间不足时抛出 `LayoutError`，建议增大尺寸或改变布局，不会靠裁掉文字完成导出。

`layout/placement.py` 负责纯数值的 cell 映射和边缘留白对齐；
`renderer/mpl/canvas.py` 测量装饰、构造轴与图例，并将实际布局放在返回 Figure 的
`_data_visuals_layout` 中供诊断。输入 FigureSpec 在绘制过程中不会被修改。

## 字体、颜色与图例

物理路径的字号来自主题 JSON 的 `publication` 与 FigureSpec，
类别色板来自 `utils/colors.py`。`FigureConfig.font_family/background` 可覆盖字体与背景。
两个内置主题均默认使用 Times New Roman，覆盖标题、图例、轴标签、刻度与矩阵注释。
`palette="curated-5-default"` 等 12 套精选预设选择整套配色，普通 Figure、CSV 入口与
`FigureConfig.palette` 均支持；不指定时沿用主题，两个内置主题默认 `curated-10-default`。
有/无分组、多指标和连续数量图共用解析后的颜色配置，参见 [配色预设](color-presets.md)。
`general` 和 `modern` 的物理路径均固定使用主标题 11 pt、子标题 9 pt、轴标签 8 pt、
刻度及色条文字 7 pt、全局和局部图例 8 pt。改变 canvas 或子图数量不缩放这些字号。
线宽、标记尺寸与间距也按物理尺寸校准，配置集中于 `publication`。
只有显式旧尺寸路径继续使用 `layout/sizing.py::compute_figure_font_sizes()` 的短边比例规则。
按声明的物理尺寸插入论文时，文字即保持上述字号；插入后再次缩放整张图仍会缩放文字。
渲染和导出使用局部 rc_context，不改变其它 Matplotlib 图的全局样式。
SVG 保留文字，PDF 使用 TrueType 字体，且输出尺寸不会受调用者 savefig.bbox 的影响。

每个 group 字段拥有完整类别域和统一颜色映射。子图筛选不会改变类别颜色；
`FigureConfig(category_colors={"model": {"Ours": "#e63946"}})` 可固定跨数据文件颜色。
精选预设保留原始色号和顺序，类别超出容量时报告错误，提示选择更大的色板；不循环用色或自动扩色。

默认情况下，重复使用的 group 生成全图共享图例，其它 group 使用局部图例。
多 y 指标、参考线和次轴指标拥有独立图例，不混入模型类别。
顶部与底部的自动图例按文字实际宽度换行，每行居中；长标题与分类标签会换行或旋转。
分组双轴折线同模型同色，以实线/虚线和圆点/菱形区分两个指标。

相同指标和配色方案的热力图共享连续色阶范围；归一化混淆矩阵固定 `[0, 1]`。
跨 Figure 可通过 `chart_opts={"color_domain": [0, 1]}` 固定颜色范围。

## 图例配置

`plot(..., legend={...})`、高级 `Figure(..., legend={...})` 与 `FigureConfig(legend={...})` 使用相同字段。
省略配置继续使用自动共享、主题字号与按文字宽度换行。
全局 `legend` 按字段覆盖 `FigureConfig.legend`；子图的 `chart_opts["legend"]` 再按字段继承全局值。
显式提供子图配置时，未指定的 `scope` 默认为 `"local"`，其余未指定字段继续继承。
图例字号、线段长度和间距均为物理 pt，改变导出 DPI 不改变版式。
无分组的多指标图在自动模式下保留局部图例，显式 `scope="shared"` 可共享指标图例。
多个子图显式加入同一共享图例时，其图例设置必须一致；冲突会报错，可改为整图统一配置或局部图例。

| 字段 | 取值与作用 |
|---|---|
| `visible` | 布尔值，默认 `True`；`False` 隐藏图例并回收对应预留空间 |
| `scope` | `"auto"`（默认）、`"shared"` 或 `"local"`；自动模式按分组字段是否跨子图复用选择，共享模式也适用于单个子图 |
| `position` | 共享图例支持 `"top" / "bottom" / "left" / "right"`；局部图例另支持 `"upper left" / "upper right" / "lower left" / "lower right"` |
| `ncols` | 正整数指定每行列数，最后一行可不足；`None` 根据可用宽度自动安排，左右侧默认单列 |
| `fontsize` | 正数 pt；`None` 使用主题的图例字号 |
| `gap` | 图例与其相邻装饰之间的非负间距，单位 pt |
| `columnspacing` | 列间距，默认 8 pt |
| `labelspacing` | 行间距，默认 3 pt |
| `handlelength` | 图例标记区域长度，默认 12 pt |
| `handletextpad` | 标记与文字间距，默认 4 pt |
| `borderpad` | 图例内容到边框的内边距，默认 3 pt；无边框时同样参与测量 |
| `frameon` | 布尔值，控制边框 |
| `anchor` | `None` 自动定位，或 `[x, y]` 且两值均为 0–1；共享图例使用整图比例坐标，局部图例使用所属 axes 的比例坐标 |
| `order` | 原始类别值列表，调整图例条目顺序 |
| `labels` | `{原始类别值: "显示文字"}` 映射，只改变图例文字，保留数据分组和颜色、点形 |

共享图例位于整图的外侧装饰带，布局器会同时测量主标题、共享轴标题与图例，
在固定尺寸内重新分配绘图区；自动高度模式将所需高度计入求解。
局部 `top/bottom/left/right` 位于对应子图的轴装饰外侧，并预留空间。
侧栏单列的标记与文字纵向对齐；显式列数的各行保持相同起点。
局部四角位置位于 axes 内部，不缩小绘图区；它可能覆盖数据，适合明确知道空白区域的情况。
固定尺寸无法容纳文字、图例或最小绘图区时报告 `LayoutError`，不会缩小字号或裁切导出。

```python
from data_visuals.core import Figure, FigureConfig

fig = Figure(
    data=df, rows=2, cols=1, canvas={"width": 90, "height": 125},
    legend={
        "scope": "shared", "position": "bottom", "ncols": 3,
        "fontsize": 8, "gap": 6, "frameon": False,
        "order": ["xsmall", "small", "roberta"],
        "labels": {"roberta": "RoBERTa"},
    },
    config=FigureConfig(facets={
        "sharex": True, "sharey": True,
        "xlabel": "Actual ID false rejection (%)", "ylabel": "Leakage difference (pp)",
    }),
)
for row, panel in enumerate(("near_ood", "far_ood")):
    fig[row, 0].scatter(x="actual_id_false_reject_pct", y="delta_leakage_pp",
                        group="backbone", where={"panel": panel})
fig.render("training.pdf")
```

需要单独修改一个子图时，在该子图声明中增加 `chart_opts={"legend": {...}}`。
例如 `{"legend": {"position": "upper right", "ncols": 1}}` 会沿用全局字号、文字和顺序，
将该子图的图例独立放在右上角；`{"legend": {"visible": False}}` 关闭该子图的图例。

显式 `anchor` 的坐标原点在左下角。共享 `top/bottom/left/right` 分别以图例的
上边中点、下边中点、左边中点、右边中点作为锚点，例如
`legend={"scope": "shared", "position": "bottom", "anchor": [0.5, 0.03]}`
把图例下边中点放在整图 `(50%, 3%)`，布局器仍会为它保留空间。
局部外侧图例以靠近坐标轴的边为锚点：`top` 为下边中点，`bottom` 为上边中点，
`left` 为右边中点，`right` 为左边中点；局部四角图例则以同名角作为锚点。
显式位置若导致越界或无法保留足够的绘图区，会报告布局错误；自动定位更适合批量复用。
局部四角图例占用绘图区内部，调用者应选取不遮挡数据的角落；自动点编号会避开该图例。

旧 `legend_position="top" / "bottom"` 调用保留兼容；新代码推荐统一使用 `legend`。
共享与局部图例的可运行示例见 [demo_legend.py](../demo/demo_legend.py)。

## 重复网格与散点装饰

相同坐标含义的小多图可使用高级 `Figure` 的 `FigureConfig.facets`，
不需要手调 axes 位置或 `subplots_adjust`。例如六格中每格按条件取数：

```python
from data_visuals.core import Figure, FigureConfig

fig = Figure(
    data=df, rows=2, cols=3,
    canvas={"width": 7, "height": 4.5, "unit": "in"},
    config=FigureConfig(facets={
        "row_labels": ["Single-phrase", "Multi-phrase"],
        "col_labels": ["xsmall", "small", "RoBERTa"],
        "xlabel": "Actual ID false rejection (%)",
        "ylabel": "Near-OOD leakage (%)",
        "sharex": True, "sharey": True,
    }),
)
# 对六格分别声明；每格使用相应的 backbone/training 条件。
fig[0, 0].scatter(
    x="id_false_reject_pct", y="near_leak_pct", group="kind",
    where={"backbone": "xsmall", "training": "Single-phrase"},
    chart_opts={"xlim": [0, 6.5], "ylim": [0, 100]},
)
```

`where` 适用于所有图种，在聚合和派生统计前筛选；值为列表时表示任选，多个条件取交集。
源数据不变，分类色仍使用完整数据域。空结果、缺失列和错误条件会报错。
`facets` 支持 `row_labels/col_labels/xlabel/ylabel/note/sharex/sharey`，
要求完整矩形网格；行列标题数须匹配网格，不与跨格布局混用。
共享方向只在外侧显示刻度，所有绘图区保持等大；自动范围取各格并集，显式范围必须一致。
该模式的文字至少 8 pt，默认关闭时保留普通混合图的布局规则。

散点 `chart_opts` 提供以下可复用装饰，尺寸以 pt 计，与导出 DPI 无关：

| 字段 | 含义 |
|---|---|
| `series_styles` | 按 group 值设置 `marker/size/color/facecolor/edgecolor/linewidth/zorder/label`；`size` 为面积 pt²；声明顺序决定共享图例顺序，图例复用标记形状 |
| `xlim/ylim`、`xticks/yticks` | 固定数值范围与刻度 |
| `xticklabels/yticklabels` | 用自定义文字显示数值刻度；须与对应 ticks 同时提供、长度相等 |
| `guides` | 如 `[{"axis": "x", "value": 5}]`；可设 `color/linestyle/linewidth` |
| `arrows` | 如 `[{"start": [5, 25], "end": [2, 60]}]`；坐标直接使用数据单位，可设线色、线宽、箭头大小与两端退让 |
| `point_labels` | 如 `{"column": "rewrite_number", "fontsize": 8}`；忽略空值，最终排版后避让标记与文字，只移动标签 |
| `annotations` | 如 `[{"text": "5.35 → 1.22 (−4.13 pp)", "xy": [0.5, 0.9], "ha": "center"}]`；默认使用 axes fraction，可切为 `coords="data"`，使用主题字体并参与边界测量 |
| `errorbar` | 如 `{"lower": "ci_lower", "upper": "ci_upper", "capsize": 1.5, "linewidth": 0.8, "alpha": 0.85}`；使用输入的绝对 Y 区间上下界，要求包含点估计，不重新估计或对称化 |
| `x_offsets` | 如 `{"xsmall": -4, "small": 0, "roberta": 4}`；按物理 pt 同步平移一组点和区间，不改原始 X，适合相同节点的多组对照；非零偏移暂不与 `point_labels/trend/y2` 同用 |

完整可运行案例见 [demo_rejection_rewrite.py](../demo/demo_rejection_rewrite.py)。
科学汇总单独校验，主图保持六格统一的 0–100% 纵轴；`--numbered` 另存编号版。

更侧重阅读的 [配对对照版](../demo/demo_rejection_rewrite_comparison.py) 将 ID 误拒和近 OOD 漏放
分列，按基座分行，每格对照两种训练方式并直接标注参考值、改写均值及百分点变化。
两列坐标范围不同，各自在基座之间保持一致；按数值比较，不跨列比较箭头长度。

`Figure(..., legend={"position": "bottom"})` 将共享图例放在整图底部，
为共享 X 标题和图例分别留出空间；固定画布与自动高度均使用同一套测量。
见 [单栏差值与区间案例](../demo/demo_matched_training.py)。

## 数据语义

- 柱图按 x/group 聚合均值，支持多 y、正负堆叠、百分比、水平图、参考线及双轴。
- `error=y` 或原数据没有 std 列时的 `error="std"` 请求样本标准差。
  其它显式误差列保留用户提供的误差值，同组重复记录取误差均值。
- 折线按 `(x, group)` 对重复观测取均值，无 group 时按 x；数值 x 使用真实坐标。
- 箱线摘要、LOWESS、KDE 与混淆矩阵归一化在 compute 中完成。
- 混淆矩阵可输入原始预测样本，或通过 `value` 输入已计数数据（重复组合求和）。

## 验收与示例

```bash
python demo/demo_publication_mixed.py
python demo/demo_canvas.py
python -m pytest -q
```

示例不依赖外部数据，提供确定性 DataFrame 与返回未渲染 Figure 的构造函数：

- `build_publication_mixed()`：180 × 150 mm；七种图、跨行跨列、共享模型颜色、独立 cohort 图例与两条色条。
- `build_publication_stress()`：180 × 140 mm；比例网格、十个长模型名、长分类标签、多 y、双轴、参考线及百分比。
- `demo_canvas.py`：90 × 65 mm 单图、180 × 110 mm 组合图及自动高度，均导出 SVG/PDF/PNG。

混排与压力示例输出至 `demo_outputs/publication/`，画布示例输出至 `demo_outputs/canvas/`；
文件格式与目录导航见 [示例输出索引](../demo_outputs/README.md)。
测试检查统计数值、实际绘图颜色、装饰边界与碰撞、对齐、字体一致性、导出尺寸、DPI、
异常资源释放，以及静态工作流的依赖隔离。

开发环境安装 `pip install -e ".[dev]"` 后即可运行完整测试。
旧 HTML/Vega 渲染器、HTML 和 Vega-Lite JSON 导出已移除。
`FigureSpec` 仍作为数据、计算、布局与渲染之间的中间表示保留；它不是 Vega-Lite 规范。
需要网页展示时，可直接嵌入导出的 SVG，以复用同一版式与文字。

物理路径的请求、求解流程和限制见根目录 [Canvas 字段契约](../CANVAS_CONTRACT.md)。
