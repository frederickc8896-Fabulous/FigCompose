# Canvas 与绘图入口字段契约

状态：已实现，持续校准。设计记录：2026-10-22；实现更新：2026-10-23。

本文规定 Matplotlib 后端的物理尺寸接口与行为，作为后续维护与验收参照。
`plot()`、`Figure` 和 `FigureConfig` 已贯通 canvas；文中示例可用于当前版本。

目标：用户声明数据、字段映射、子图内容、风格和整图尺寸，底层稳定处理单图与多子图的字号、配色、图例和排版。

## 1. 单位与画布边界

| 对象 | 契约单位 | 职责 |
|---|---|---|
| 用户指定的 canvas | 默认 mm，可选 in | 最终输出 Figure 的物理宽高 |
| 内部布局、文字边界测量 | pt | 统一几何计算与渲染坐标 |
| 字号、线宽 | pt | 最终印刷尺寸下的文字和笔画大小 |
| PNG 像素数 | px | 根据物理尺寸与导出 DPI 计算 |
| 导出分辨率 | DPI | 控制栅格清晰度，不参与排版求解 |

换算关系：

```text
1 in = 25.4 mm = 72 pt
内部宽度 pt = width_mm × 72 / 25.4
PNG 宽度 px ≈ width_mm × dpi / 25.4
```

例如：180 mm 宽的 Figure 在 300 DPI 下约为 2126 px，在 600 DPI 下约为 4252 px。物理尺寸、实际字号和版式保持不变。像素取整允许后端产生至多约 1 px 的差异。

`canvas` 始终表示整张导出 Figure 的外框，包含：

- 整图主标题、共享图例。
- 所有子图的标题、局部图例、坐标轴标签和刻度。
- 绘图区、色条、子图间距和外边距。

单图与多子图使用相同定义。`width=180, height=110, unit="mm"` 始终表示整张 Figure 为 180 × 110 mm，不表示某个子图或纯绘图区的尺寸。

## 2. 顶层入口字段

简洁入口包含以下字段；`legend` 为可选的精细覆盖，日常使用可以省略：

| 字段 | 含义 | 必填与默认行为 |
|---|---|---|
| `data` | CSV 路径或 DataFrame | 必填 |
| `plots` | 每个子图的图种、指标、字段映射和选项 | 必填；列表长度决定子图数量，顺序决定阅读顺序 |
| `x` | 普通图的默认横轴字段 | 按图种需要，可在子图内提供或覆盖 |
| `group` | 默认分组字段 | 可省略；子图内 `group=None` 关闭该子图分组 |
| `canvas` | 整图物理尺寸约束 | 可省略；详见下节 |
| `cols` | 每行最大子图数 | 可省略，由布局器选择 |
| `style` | 字体、实际字号层级、线宽与间距规则 | 可省略，沿用全局默认风格 |
| `palette` | 分类色、连续色阶及辅助颜色 | 可省略，沿用当前颜色预设规则 |
| `title` | 整图主标题 | 可省略，沿用现有元信息规则 |
| `legend` | 共享或局部图例的位置、列数、字号和间距等覆盖 | 可省略，默认按数据分组自动共享与测量；`False` 隐藏 |
| `csv_options` | CSV 编码、分隔符等读取设置 | 可省略 |

数据映射和统计语义沿用 [CSV 调用说明](docs/simple-api.md)，本次尺寸改造不改变聚合、误差、归一化或颜色映射行为。

日常入口不增加独立的子图数量、行数或单个子图尺寸参数。高级 `Figure` 的复杂布局能力另行保留。
图例统一使用 `legend={...}`，支持整图四侧预留、子图四角定位、显式字号、间距、顺序与锚点；
各子图通过 `chart_opts.legend` 逐字段覆盖，其他角色字号仍沿用风格层级。
图例字号与距离使用 pt，锚点使用归一化坐标；覆盖项参与测量，隐藏后回收预留空间。
详见 [图例字段契约](docs/matplotlib-backend.md#图例配置)。

## 3. `canvas` 字段结构与校验

公共写法统一使用具名字典：

```python
canvas={"width": 180, "height": 110, "unit": "mm"}
```

| 子字段 | 类型 | 契约 |
|---|---|---|
| `width` | 正的有限数值 | 显式传入 canvas 时必填 |
| `height` | 正的有限数值或 `None` | 省略或 `None` 表示自动高度；提供数值表示固定高度 |
| `unit` | `"mm"` 或 `"in"` | 可省略，默认 `"mm"`；同时作用于宽和高 |

校验要求：

- 拒绝布尔值、零、负数、NaN、无穷大和字符串尺寸。
- 显式 canvas 必须有 `width`；不支持只给高度。
- 拒绝未知键与未知单位，避免拼写错误被静默忽略。
- 空字典不是自动模式；省略 canvas 或传 `None` 才表示使用全局默认。
- 第一版不提供 tuple、标量或 `"180mm"` 等平行语法，也不把 px 作为论文画布单位。

示例：

```python
canvas={"width": 90, "height": 65}      # 固定 90 × 65 mm
canvas={"width": 180}                  # 固定 180 mm 宽，高度自动
canvas={"width": 180, "height": None}  # 同上
canvas={"width": 7, "unit": "in"}     # 固定 7 in 宽，高度自动
```

## 4. 尺寸约束与默认行为

| 输入 | 固定的约束 | 布局器可以决定的内容 |
|---|---|---|
| 提供宽、高 | 整图物理宽高 | 网格、装饰换行与内部空间分配 |
| 只提供宽度 | 整图物理宽度 | 网格、内部空间分配和所需高度 |
| 省略 canvas 或传 `None` | 全局配置中的默认物理宽度 | 按自动高度模式求解 |

全局默认配置为 `canvas={"width": 180, "height": None, "unit": "mm"}`。
同一份论文配置下，增加子图不自动改变栏宽。可通过 `FigureConfig.canvas` 配合
`set_default_config()` 统一设置论文的栏宽与自动高度；显式 canvas 优先。

```python
from data_visuals.core import FigureConfig, set_default_config

set_default_config(FigureConfig(canvas={"width": 90}))
```

省略 canvas 时继承这份完整配置；若全局配置显式给出固定 height，则沿用该固定尺寸。

### 固定宽高

- 指定尺寸是硬约束，导出的外框必须保持一致。
- 先保持风格规定的实际字号，再选择网格和分配空间。
- 排版可以换行、调整内部位置或使用更合适的网格，但不能改变数据含义。
- 空间不足时给出布局错误，指出拥挤面板或装饰，并提供可行的调整建议。
- 不通过静默扩大画布、裁剪文字、tight 裁切或自动缩小字号满足约束。

### 自动高度

- 宽度仍是硬约束。
- 高度根据子图数量、图种、网格、字号和装饰实际占用推导，包含整图标题与图例。
- 推导过程必须可终止、结果可复现；不能只按子图数量套固定宽高比。
- 如果单个面板在指定宽度下也无法满足可读性，应报告宽度不足，增加高度不能掩盖横向空间问题。

## 5. 单图、多子图与 `cols`

两种情况共用同一条布局与渲染管线，单图视为只有一个面板的 Figure。

- 子图数量始终来自 `len(plots)`，不新增数量字段。
- 单图使用一个面板容器；增加子图只改变内部划分，不改变 canvas 的含义。
- `cols=None` 时，网格选择同时考虑画布宽度、可用高度、图种和实际装饰空间。
- `cols=N` 表示每行最多 N 个面板，不要求一定排满 N 列；布局器可选择更少的列。
- `cols` 大于子图数量时不创建空白面板。默认末行继续铺满可用宽度。
- 保留阅读顺序、共享颜色和共享图例规则；单图不自动添加 `(a)`，多图沿用子图编号规则。

[layout/physical.py](data_visuals/layout/physical.py) 对候选列数分别生成完整网格，
使用实际字号渲染测量后比较绘图区尺寸偏好与紧凑程度。
[plan_panels()](data_visuals/layout/panels.py) 负责每个候选的顺序与末行跨格权重。
高级 `Figure` 的显式网格、跨行跨列和比例权重保持拓扑，不自动改为另一套网格。

## 6. 字号、线宽、配色与导出职责

`style` 统一定义实际 pt 字号层级。当前 `general` 和 `modern` 的物理尺寸默认值如下；
它们是工具默认值，不代表期刊的投稿字号要求。

两个内置风格均默认使用 Times New Roman，字体可通过 `FigureConfig.font_family` 显式覆盖。
单图与多子图的标题、图例、轴标签、刻度和矩阵注释共用所选字体；缺少字体时沿用本机回退机制。

| 角色 | 实际字号 |
|---|---|
| 主标题 | 11 pt |
| 子标题 | 9 pt |
| X/Y 轴标签 | 8 pt |
| 刻度与色条文字 | 7 pt |
| 全局与局部图例 | 8 pt |

配置集中在主题 JSON 的 `publication` 节点，包括字体、线宽、标记、绘图区最小尺寸、
外边距和面板间距。物理路径默认外边距 6 pt、面板间距 8 pt。

- 同一风格配置下，单图、多子图和不同 canvas 尺寸复用相同的实际字号层级。
- 全局与局部图例复用同一图例字号；相同角色在不同子图中保持一致。
- 线宽和标记尺寸也以最终可读性校准，不能在毫米迁移时直接沿用旧大画布的数值。
- 间距由风格与文字测量统一处理，包含子标题到图例、图例到绘图区等可见距离。
- 原有基于 canvas 短边的百分比字号仅在显式旧尺寸路径继续使用；物理路径固定使用上述 pt 层级。
- `palette` 继续独立管理整套颜色，本次契约不重新设计配色。

导出示例：

```python
fig.render("figure.svg")
fig.render("figure.pdf")
fig.render("figure.png", dpi=300)
```

DPI 留在导出层。改变 DPI 不重新选择网格，不改变物理外框、实际字号与线宽；对 PNG 及矢量文件中的栅格部分，它影响输出分辨率。

## 7. 当前调用示例

以下调用均使用物理尺寸路径。

单图：

```python
from data_visuals import plot

fig = plot(
    "results.csv",
    x="dataset",
    group="model",
    plots=[{"kind": "bar", "metric": "accuracy"}],
    canvas={"width": 90, "height": 65},
    style="modern",
    palette="curated-5-default",
)
fig.render("single.svg")
```

多子图，固定栏宽、自动高度：

```python
fig = plot(
    "results.csv",
    x="dataset",
    group="model",
    plots=[
        {"kind": "bar", "metric": "accuracy"},
        {"kind": "line", "x": "epoch", "metric": "f1"},
        {"kind": "box", "metric": "latency"},
    ],
    canvas={"width": 180},
    cols=2,
    style="modern",
    palette="curated-5-default",
)
fig.render("combined.pdf")
```

例中的尺寸仅用于说明字段含义，不是已经验证的最佳尺寸，也不代表期刊规范。CSV 需提供相应列，类别数需符合所选配色容量。

## 8. 内部流程与旧尺寸兼容

物理路径的执行顺序：

1. `core/canvas.py` 校验请求，转为 pt，保存原始 mm/in 请求与自动高度标记。
2. `Figure` 完成数据计算与语义颜色域，生成布局模板。
3. `layout/physical.py` 读取固定 pt 字号，枚举允许的网格，求解固定或自动高度。
4. 每个候选使用 Matplotlib 的实际文字边界测量标题、图例、双轴与色条；合格候选按紧凑度与图种偏好选择。
5. 已测量几何写回 FigureSpec，记录 `physical=True`、`unit="pt"`、`request`、`height_auto`、`width_mm/height_mm`。
6. 导出复用已选网格与物理尺寸，DPI 只影响栅格分辨率。

主要施工位置：

- [api.py](data_visuals/api.py)、[core/config.py](data_visuals/core/config.py)、[core/figure.py](data_visuals/core/figure.py)：公共字段、配置和贯通。
- [core/spec.py](data_visuals/core/spec.py)：请求与求解后的尺寸表达。
- [core/canvas.py](data_visuals/core/canvas.py)：请求校验与单位换算。
- [layout/physical.py](data_visuals/layout/physical.py)、[layout/panels.py](data_visuals/layout/panels.py)：物理约束求解、候选网格与评分。
- [themes/general.json](data_visuals/themes/general.json)、[themes/modern.json](data_visuals/themes/modern.json)：物理尺寸的 publication 风格数值。
- [renderer/mpl/canvas.py](data_visuals/renderer/mpl/canvas.py)、[renderer/mpl/export.py](data_visuals/renderer/mpl/export.py)：文字测量、实际尺寸和导出。

兼容行为：高级入口显式使用 `aspect/base/cell_base` 时进入旧尺寸路径，保留其大画布与比例字号。
原先的宽度 1800 实际是 1800 pt，即 635 mm，不能解释为 1800 px 或 1800 mm。
显式 canvas 与显式旧尺寸参数同时出现时报错，包含 Figure/config 间的冲突。
仅继承的旧默认值不构成冲突，也不覆盖用户明确指定的 canvas。
`FigureConfig.to_dict()` 只序列化当前有效的尺寸来源，保证恢复配置时不会制造新旧来源冲突。

## 9. 验收边界与当前限制

至少覆盖以下验收场景：

- 单图与多子图均可使用固定宽高、自动高度两种模式。
- 同一风格下，90 mm 单图和 180 mm 多子图相同角色的实际字号一致。
- mm 与等价 in 输入生成相同物理尺寸与版式。
- SVG/PDF 外框符合指定宽高；PNG 尺寸符合物理尺寸与 DPI 换算。
- 300/600 DPI 导出保持相同布局、字号和线宽，像素密度按比例变化。
- 长主标题、长刻度、共享和局部图例、双轴、色条均计入空间占用，无越界或碰撞。
- 固定尺寸装不下时产生可理解的布局错误，失败后释放 Matplotlib Figure。
- 非法字段、非法尺寸、未知单位和冲突尺寸来源在入口得到明确错误。
- 数据计算、原始配色、类别颜色稳定性与现有统计语义通过回归验证。

当前求解按可读性、图种形状偏好与紧凑程度选择可行布局，使用有限候选搜索与真实文字测量：
自动高度每个候选最多 8 次调整，失败时抛出
`LayoutError` 并释放 Matplotlib Figure。自动布局不保证找到所有可能人工布局中的最优解。
图种尺寸偏好与最小绘图区尺寸用于可读性校准，不构成任意长文本都能排下的承诺。
标题、类别数量或图例过多时仍可能需要增加画布、减少每行面板或简化文字。

具体字号和间距允许后续基于真实论文尺寸校准，但修改时必须保持同一角色跨单图、多图的一致性。
可运行 `python demo/demo_canvas.py` 对照 90 × 65 mm 单图、180 × 110 mm 组合图和 180 mm 自动高度图。
