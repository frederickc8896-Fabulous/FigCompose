# PaperFig 开发与排查指南

当前实现统一使用 Matplotlib。用户入口是 `plot(csv, plots=[...], style=..., palette=...)`；
高级布局使用 `Figure`。两者共享计算、版式和渲染管线。
使用说明见 [CSV 简洁入口](simple-api.md)、[Matplotlib 后端](matplotlib-backend.md)和[配色预设](color-presets.md)。

## 职责与入口

| 层 | 位置 | 职责 |
|---|---|---|
| 简洁入口 | `data_visuals/api.py`、`layout/panels.py` | 规范化 CSV/指标/图种声明，生成网格候选与面板顺序 |
| 图种声明 | `data_visuals/charts/` | 字段校验、选项与统计计算需求 |
| 编排与中间表示 | `data_visuals/core/figure.py`、`core/spec.py` | 组织数据、计算和布局，生成 FigureSpec |
| 物理尺寸 | `data_visuals/core/canvas.py`、`layout/physical.py` | 校验 mm/in、转为 pt、按实测文字选择网格并求解高度 |
| 计算 | `data_visuals/compute/` | 均值、误差、平滑、密度、箱线摘要与预处理 |
| 几何与字号 | `data_visuals/layout/` | 网格、跨格、画布、全图字体层级和边缘对齐 |
| 视觉配置 | `data_visuals/themes/`、`utils/colors.py` | 主题及完整配色系统 |
| 配置解析 | `data_visuals/renderer/mpl/config.py` | 将主题与配色解析为 MplConfig |
| 渲染与测量 | `data_visuals/renderer/mpl/canvas.py` | 创建轴、绘制、图例换行、文字测量与空间分配 |
| 图种绘制 | `data_visuals/renderer/mpl/charts/` | 将已计算数据绘制到传入的轴 |
| 导出 | `data_visuals/renderer/export.py`、`renderer/mpl/export.py` | SVG/PDF/PNG、DPI、保存与资源释放 |

FigureSpec 继续保留为内部中间表示。它能转成字典供诊断，不代表一种浏览器渲染规范；
`.json` 和 `.html` 不再作为图表导出格式。

## 字号与间距

新物理路径使用主题 JSON 的 `publication.font_sizes`：主标题 11 pt、子标题 9 pt、
轴标签 8 pt、刻度及色条 7 pt、图例 8 pt。默认 180 mm 宽、自动高度。
相同角色跨单图、多图和不同 canvas 尺寸保持同一字号；DPI 不参与布局或字体计算。
`publication` 同时集中线宽、标记尺寸、外边距、面板间距与最小绘图区尺寸。

`layout/sizing.py::compute_figure_font_sizes()` 的整图短边比例保留用于旧尺寸路径。
只有显式提供 `aspect/base/cell_base` 才使用该路径；与显式 canvas 冲突时报错。
新增功能优先使用 canvas 物理路径，兼容行为通过旧路径测试覆盖。

子标题、图例与绘图区域之间的间距由主题的 `layout` 字段控制，并随相应字号缩放。
不要为单个 demo 在 builder 里写固定位置或补偿距离；应先确定问题来自全局几何、
实际文字测量还是某个图种遗漏了装饰。

布局由物理画布内的真实文字边界驱动；`layout/physical.py` 枚举候选列数，自动高度每个候选
至多调整 8 次，再按图种尺寸偏好与紧凑度选择。高级显式布局保持跨格与比例权重。
不使用 `tight_layout` 或导出裁切补救。宽度不足应停止高度扩展并给出 `LayoutError`。

## 颜色和图例

`MplConfig` 负责解析完整主题；图种 builder 接收解析后的配置，避免各自读取主题文件。
`palette="curated-5-default"` 等原始精选预设同时选择分类色、配套连续色阶与辅助线。
不同图种应复用 `renderer/mpl/charts/helpers.py` 的颜色、标签、参考线和双轴辅助函数。

同一个分组字段使用完整数据域的颜色映射，子图筛选不应重新编号颜色。
跨文件需要固定颜色时使用 `FigureConfig.category_colors`；自动颜色不能保证新增类别后的历史映射。
连续色条的共享依据是指标与色阶语义，不应仅因两个图都是 heatmap 就合并。

builder 返回图例句柄列表，由 canvas 统一生成、合并与放置图例。
不要在某一个 builder 内自行增加与全图规则冲突的 figure legend。
双轴、色条和局部图例必须被实际装饰测量覆盖。

## 数值与几何诊断

先检查 `figure.build()` 返回的 FigureSpec：

```python
spec = figure.build()
for panel in spec.subplots:
    print(panel.chart_type, panel.font_sizes)
    print(panel.computed_data)
```

渲染后可检查私有诊断属性，避免从截图猜测问题：

```python
import matplotlib.pyplot as plt

rendered = figure.render()
try:
    report = rendered._data_visuals_layout
    print(report["canvas"], report["header_height"], report["iterations"])
    for key, panel in report["cells"].items():
        print(key, panel["cell"], panel["data_zone"], panel["decoration_bbox"])
finally:
    plt.close(rendered)
```

物理路径的 `spec.canvas` 包含 `request`、`height_auto`、`width_mm/height_mm` 和 pt 尺寸。
`cell` 与 `data_zone` 使用左上原点 pt 坐标，`decoration_bbox` 来自 Matplotlib 的底部原点；
比较前先统一坐标。该诊断属性是测试与开发入口，不承诺稳定的公开序列化接口。

| 问题 | 优先检查 |
|---|---|
| 数值或误差不正确 | 图种 `compute_requirements()`、`core/figure.py` 的编排、`compute/` 的计算结果 |
| 子图筛选后换色 | FigureSpec 的完整类别域、canvas 的 color maps、`series_color()` |
| 热力图范围不同 | 指标映射、`color_scheme`、`color_domain` 与 canvas 色阶共享 |
| 字号不一致 | 主题 `publication.font_sizes`、各面板 `font_sizes` 与 physical 标记，避免 builder 单独设置字号 |
| 自动高度或网格异常 | `layout/physical.py` 候选、失败的宽高方向与 FigureSpec 请求元数据 |
| 子标题/图例/轴标签碰撞 | `canvas.py` 的测量和主题 `layout` 间距 |
| 长标签挤压相邻图 | `layout/placement.py` 的边缘对齐及 canvas 的标签换行/旋转 |
| SVG/PDF 与 PNG 布局不同 | 导出设计单位、DPI 和局部 rc_context，避免保存时裁切 |

## 添加图种

新增图种需要声明与绘制两处注册；有新统计需求时还要补计算与编排。

1. 在 `charts/newtype.py` 定义 `ChartSpec` 子类，用 `@register_chart` 注册。
   指定 `chart_type`、`required_fields`、`optional_fields`，用 `_chart_options()` 导出图种选项，
   用 `compute_requirements()` 声明计算需求。
2. 在 `charts/__init__.py` 导入新类，让注册在包加载时执行。
3. 在 `renderer/mpl/charts/newtype.py` 实现 `_draw_newtype(ax, sp, cfg, color_map)`。
   `sp` 是序列化后的子图字典，包含 `data`、`options`、`font_sizes` 与 `computed_data`。
   按现有 helpers 解析数据与标签，绘制到传入轴，返回图例句柄列表；空数据返回空列表。
4. 在 `renderer/mpl/charts/registry.py` 的 `_populate()` 中将名称映射到绘制函数。
5. 检查 `core/figure.py` 中按图种分支的计算逻辑；新统计在 `compute/` 实现，builder 消费结果。
6. 如需支持简洁 CSV 入口，明确 `api.py` 中 `metric` 对应的字段与默认标题，避免错误沿用普通 Y 指标。

例如，仅作为绘制函数接口示意：

```python
from .helpers import axis_labels, frame


def _draw_newtype(ax, sp, cfg, color_map):
    data = frame(sp.get("computed_data", []))
    if data.empty:
        return []
    # 在 ax 上绘制，并复用统一颜色、标签和字号。
    axis_labels(ax, sp)
    return []
```

这不是完整图种实现。新类型还需验证数值含义、缺失数据、分组与多子图组合，
不能只检查能否生成文件。

## 验证

```bash
pip install -e ".[dev]"
python -m pytest -q
python demo/demo_simple_csv.py
python demo/demo_publication_mixed.py
python demo/demo_color_catalog.py
python demo/demo_canvas.py
```

| 验证文件 | 重点 |
|---|---|
| `test/test_simple_api.py` | CSV 入口、字段映射、自动网格与声明校验 |
| `test/test_canvas_contract.py` | 物理尺寸校验、单图/多图、自动高度、单位与固定字号 |
| `test/test_compute_pipeline.py` | 统计与数据编排 |
| `test/test_typography.py` | 旧路径全局字号比例与布局模式一致性 |
| `test/test_color_system.py` | 统一配色预设与颜色语义 |
| `test/test_mpl_charts.py` | 图种绘制、计算值、双轴和图例 |
| `test/test_mpl_layout.py` | 混合布局、颜色与装饰边界 |
| `test/test_mpl_acceptance.py` | 出版混合图与压力场景的几何和语义 |
| `test/test_mpl_export.py` | 导出格式、DPI、资源释放与依赖隔离 |
| `test/validate_all_demos.py` | 只构建多图声明及 canvas-first 兼容检查 |
| `test/font_calibration.py` | 可选的静态字号标定图 |

几何验收后仍需看图确认视觉平衡。涉及导出尺寸或字体时，检查 SVG/PDF/PNG，
并明确实际字体与最终插入论文时的尺寸。
