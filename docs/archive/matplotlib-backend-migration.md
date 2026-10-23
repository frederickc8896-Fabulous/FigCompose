# Matplotlib 后端迁移规划

> 状态（2026-10-22）：Matplotlib 已成为默认后端，七类图种、固定画布排版、共享配色和图例已接入。
> 本文归档迁移时的分析与规划；当前实现及验收以 [Matplotlib 后端说明](../matplotlib-backend.md) 为准。
> 2026-10-22：旧 HTML/Vega 后端与根目录迁移实验脚本已移除。下文脚本名、旧接口与阶段清单仅为历史记录；当前示例见 [出版组合图](../../demo/demo_publication_mixed.py)。

---

## 一、为什么要考虑换后端

当前渲染后端是 Vega-Lite/Altair(`data_visuals/renderer/`)。在实现"mixed layout 组合图"(多个不同类型图表混排、共享统一比例、避免互相干涉)的过程中,反复遇到同一类问题:

- 子图之间互相干涉、位置错位
- 顶层子图与下方子图的坐标轴 gutter 对不齐
- 子图标题字号不统一(大 cell 标题被放大,小 cell 标题被压小)
- 共享 legend 换行后垂直高度过大,或宽度利用率低
- 窄列图表的 x 轴分类标签挤在一起

这些问题不是零散 bug,而是同一个根因反复发作:**Vega-Lite 的 `concat`(`hconcat`/`vconcat`)模型是"每个 view 各自 autosize,再拼接",不是"共享坐标系的网格"**。为了在这套模型上强行做到"全局比例统一 + 不干涉",项目里已经补了：

- `layout/sizing.py` 里的 `figure_cell_title` / `figure_axis_label` / `figure_tick_label` / `figure_legend` 系列 figure-level 字号求解
- `renderer/vega.py` 里的递归 span-aware `_compose_grid()`,用来替代最初的 spacer 近似
- `renderer/legend.py` 整套手绘 marks-based legend,用来绕开 Vega-Lite 原生 legend 的定位限制
- `data_zone` / `label_margins` 驱动的 axis `minExtent`/`maxExtent` 强制对齐

每一层补丁都是必要的,但也说明:**我们已经在用 Python 手工模拟 matplotlib 内置的能力**(`GridSpec`、`constrained_layout`、`fig.legend()`)。

---

## 二、为什么当初放弃 matplotlib,而这次判断可以回去

项目文档(`docs/构建结构.md`)明确批评过"matplotlib 一行代码混合四层逻辑"的问题,当初弃用 matplotlib 也是真实踩过坑:元素干涉、比例随 `figsize` 变化而跑偏、`tight_layout`/`bbox_inches="tight"` 结果不可预测、难以调试。

关键分析结论:**这些痛苦的根源是"让 matplotlib 自己的启发式布局引擎(`tight_layout`/`constrained_layout`/手动 `subplots_adjust`)现场决策"**,而不是 matplotlib 坐标系本身的问题。具体原因:

1. matplotlib 默认字号是绝对磅值(`rcParams['font.size']`),与 `figsize` 无关,不会随画布比例缩放 —— 这是"比例奇怪"的直接来源。
2. `tight_layout()`/`constrained_layout()` 是黑盒迭代求解器,依赖绘制时刻的真实文字度量,换字体/换 DPI/加图例都可能导致结果不同 —— 这是"难调试"的来源。
3. `savefig(bbox_inches="tight")` 在导出时重新计算一次 bbox,经常与屏幕预览时调好的比例不一致。

**这个项目现在已经不缺这套东西了**:`data_visuals/layout/`(`sizing.py` + `grid.py` + `manager.py`)在任何绘图动作发生之前,就已经算出了每个 cell 的绝对坐标(`x/y/w/h`)、按比例推导的字号、以及排除标题/轴标签后的真实绘图区(`data_zone`)。

如果换成 matplotlib,方案是:**完全不调用 `tight_layout()`/`constrained_layout()`/`bbox_inches="tight()"`,只用 `fig.add_axes([x, y, w, h])` 吃 `layout/` 已经算好的绝对几何**。matplotlib 在这个方案里只是一块画布,版式决策权仍然在我们自己的确定性求解器手里 —— 和现在 Vega-Lite 渲染器的关系是同构的:`FigureSpec` 是唯一真相源,渲染器只是执行者。

---

## 三、已完成的最小可行性验证

历史脚本：`experiment_mpl_mixed.py`（已移除；当时用于独立验证绝对画布模式，未修改 `data_visuals/` 包本身）。相关逻辑现已收编至 `data_visuals/renderer/mpl/`。

**验证方法**:
1. 复用现有 `Figure.build()` 全部管线(`data/` → `compute/` → `layout/` → `FigureSpec`),不改一行上游代码。
2. 拿 `FigureSpec.to_dict()` 里每个 subplot 的 `data_zone`(绘图区绝对坐标)和 `font_sizes`(已按比例算好的字号),直接喂给 `fig.add_axes()`。
3. 三种图表类型(`bar`/`heatmap`/`line`)各写一个几十行的绘制函数,对应 `ax.bar`/`ax.imshow`/`ax.plot`。
4. 主标题用 `fig.text()`,共享 legend 用 `fig.legend()`,均为显式坐标/字号,不依赖 matplotlib 自动定位。
5. 导出固定 `dpi=72`(使 1 pt = 1 设计像素,避免磅值/像素单位换算引入的额外误差),`savefig()` 不传 `bbox_inches="tight"`。

**验证场景**:与反复出问题的 `mixed_base`(`layout=[[(3,1),None,None],[(2,2),None,1],[None,None,1]]`,bar + heatmap + 两个 line)完全一致的拓扑。

**结果对照**:

| 问题 | Vega-Lite 后端表现 | matplotlib 绝对画布实验 |
|---|---|---|
| 子图互相干涉 | 反复出现 | 未出现 |
| 顶部大图与下方子图对不齐 | 需要手动同步 `minExtent`/`maxExtent` | 自动对齐(共享同一份 `data_zone.x`) |
| 子图标题字号不统一 | 需要专门写 figure-level 字号求解器 | 直接读同一个 `font_sizes['title']` 字段,天然一致 |
| 窄列 line 图 x 轴标签拥挤 | 需要按宽度/字号动态判断是否旋转 | 固定旋转 30°,清晰可读 |
| 共享 legend 变形/过高 | 需要整套手绘 marks-based legend | `fig.legend()` 一行代码,天然紧凑 |

第一版实验里主标题与网格之间有明显留白,原因是 `legend_band`/`title_band` 常量抄用了 Vega-Lite 手绘 legend 的预留高度,和 matplotlib 原生 legend 的实际紧凑高度不匹配。按字号比例重新标定后(改用 `title_fs * 1.1` 与 `legend_fs * 2.2`)问题消失。这说明**残留的都是"具体常量需要针对新后端重新标定"这类可控工作,不是结构性问题**。

---

## 四、具体迁移方法

### 4.1 架构边界:哪些不变,哪些要动

**完全不变**(已验证是渲染器无关的):

- `data_visuals/data/`(CSV 加载、schema 校验)
- `data_visuals/compute/`(聚合、预处理、统计,含 `derived_data` 产出:`trend_data`/`density_data`/`box_summary`/`box_outliers`/`confusion_matrix`)
- `data_visuals/charts/`(图表类型声明,`ChartSpec`)
- `data_visuals/layout/`(网格划分、字号/间距求解、共享轴检测)
- `data_visuals/core/`(`Figure` API、`FigureSpec`/`SubplotSpec` 中间表示)

依据:检索确认 `alt`/`altair` 只出现在 `data_visuals/renderer/` 目录下,`core/spec.py` 的 `FigureSpec` 本身是纯数据容器(geometry、data_zone、font_sizes 全是数字,不含任何 Vega-Lite 语义)。

**需要新增/替换**:

- 新增 `data_visuals/renderer/mpl/` 作为并列的可选后端,结构对应现有 `renderer/vega_charts/`:
  ```
  renderer/
  ├── vega.py, vega_charts/, legend.py, axis.py, config.py, export.py   # 现有,不动
  └── mpl/                          # 新增
      ├── canvas.py                 # FigureSpec -> matplotlib Figure 的顶层编排
      ├── axis.py                   # 字号/gutter 注入(对应现有 axis.py 的职责)
      ├── legend.py                 # fig.legend() 封装(对应现有 legend.py 的职责)
      ├── export.py                 # savefig 封装(对应现有 export.py 的职责)
      └── charts/
          ├── bar.py, line.py, scatter.py, box.py
          ├── heatmap.py, histogram.py, confusion.py
          └── registry.py
  ```
- `Figure.render()` / `renderer/export.py` 的 `save()` 增加一个 `backend="vega" | "matplotlib"` 参数(默认仍为 `"vega"`,不改变现有行为)。

### 4.2 硬性规则(不可违反,否则会重蹈覆辙)

1. **禁止调用** `fig.tight_layout()`、`plt.tight_layout()`、`layout="constrained"`/`constrained_layout=True`。
2. **禁止使用** `savefig(..., bbox_inches="tight")`。所有导出必须用固定 `figsize` + 固定 `dpi`,让最终像素尺寸和 `FigureSpec.canvas` 完全对应,不允许 matplotlib 在导出时重新计算 bbox。
3. **每个 subplot 必须用** `fig.add_axes([left, bottom, width, height])`(figure-fraction 坐标),坐标来自 `SubplotSpec.data_zone`,不使用 `fig.add_subplot()` 或 `plt.subplots()` 的隐式网格。
4. **legend 位置必须显式指定**(`fig.legend(..., loc=..., bbox_to_anchor=...)`),禁止 `loc="best"` 自动摆放。
5. **字号一律从 `FigureSpec.font_sizes` / `shared_legend.font_size` / `title.font_size` 读取**,不允许在 `renderer/mpl/` 里写任何独立于 `layout/` 的字号计算逻辑。

### 4.3 坐标系换算

Vega-Lite/SVG 坐标原点在左上角,y 向下增长;matplotlib figure-fraction 坐标原点在左下角,y 向上增长。统一按以下公式换算(已在 `experiment_mpl_mixed.py` 的 `_frac_box()` 中验证):

```python
def frac_box(box, total_w, total_h, y_offset):
    left = box["x"] / total_w
    width = box["w"] / total_w
    top = (box["y"] + y_offset) / total_h
    height = box["h"] / total_h
    bottom = 1.0 - top - height
    return (left, bottom, width, height)
```

其中 `y_offset` 用于补偿主标题带(`title_band`)和共享 legend 带(`legend_band`),因为 `FigureSpec.canvas.height` 只覆盖网格区域,标题和共享 legend 是在网格区域上方追加的(与现有 `renderer/vega.py` 的 `vconcat(legend_strip, vconcat(title, grid))` 语义一致)。

### 4.4 字号单位换算

matplotlib `fontsize` 单位是磅(point,1pt=1/72 inch),而 `layout/sizing.py` 里的字号是按画布像素比例算出来的"设计像素值"。两者不能直接相等使用,否则在非 72 dpi 下会有约 2 倍的比例误差。

**推荐做法**:固定 `DPI = 72` 作为 matplotlib 渲染基准(此时 1pt = 1px,`FigureSpec` 里的字号数值可以直接当 `fontsize` 使用,无需换算)。若后续需要更高分辨率的 PNG 导出,应在 `savefig(dpi=target_dpi)` 时单独指定,不改变 `figsize`(inch),这样最终像素尺寸按比例放大,而字号/线宽等"设计尺寸"保持相对画布比例不变。

### 4.5 每种图表类型的映射

| chart_type | matplotlib 原语 | 数据来源 |
|---|---|---|
| `bar` | `ax.bar()`,按 `group` 分组手动算偏移 | `computed_data`(`{y}_mean` 列) |
| `line` | `ax.plot()`,按 `group` 分组循环绘制 | `computed_data`(原始值,无聚合) |
| `scatter` | `ax.scatter()` | `computed_data`;`trend=True` 时叠加 `ax.plot(derived_data['trend_data'])` |
| `box` | 手动用 `ax.bar`(箱体)+ `ax.vlines`/`ax.hlines`(须)+ `ax.scatter`(outlier)组合,而不是 `ax.boxplot()`(后者自己重新计算统计量,应改为消费 `compute/` 已产出的结果) | `derived_data['box_summary']` / `derived_data['box_outliers']` |
| `heatmap` | `ax.imshow()` 或 `ax.pcolormesh()` + `fig.colorbar()` | `computed_data`(`{value}_mean` 列,pivot 成二维矩阵) |
| `histogram` | `ax.hist()`(基础直方图)或 `ax.plot()`(`density=True` 时) | 基础直方图用 `computed_data`;密度曲线用 `derived_data['density_data']` |
| `confusion` | `ax.imshow()` + `ax.text()` 逐格标注 | `derived_data['confusion_matrix']` |

这张表里最重要的一点:**凡是 `compute/` 已经预计算好的统计量(`box_summary`、`density_data`、`trend_data`、`confusion_matrix`),matplotlib 版本一律直接消费这些结果,不重新调用 `ax.boxplot()`/`scipy` 之类会重新计算统计量的接口**。这既保持了"数据处理只在 `compute/` 一层完成"的架构原则,也避免了统计逻辑在两个后端里各算一遍导致结果不一致。

### 4.6 输出格式

matplotlib 原生支持 SVG/PDF/PNG 矢量与栅格导出,不依赖 `vl-convert`(Node/Chromium),因此需要更新的部分只是 `renderer/export.py` 里按 `backend` 分派到 `renderer/mpl/export.py`。DPI 语义保持不变:SVG/PDF 仍是比例优先,PNG 通过 `dpi=` 显式控制像素密度。

---

## 五、分阶段实施计划

1. **阶段一(已完成)**:最小可行性验证。三种图表类型、单一 mixed layout 场景,证明"绝对画布模式"能消除干涉/错位/字号不一致问题。产出:`experiment_mpl_mixed.py`。
2. **阶段二**:补齐剩余 4 种图表类型(`scatter`/`box`/`histogram`/`confusion`)的绘制函数,仍在独立实验脚本里验证,覆盖 `demo/demo_*_all.py` 的全部分支。
3. **阶段三**:把验证过的绘制逻辑正式收编进 `data_visuals/renderer/mpl/`,遵循与现有 `renderer/vega_charts/` 一致的目录结构和 `registry.py` 分发模式;`Figure.render(backend=...)` 增加后端选择,默认仍为 `"vega"`。
4. **阶段四**:用 `test/validate_all_demos.py` 同款用例跑双后端对比,确认两者在同一份 `FigureSpec` 下产出一致的子图数量、字号比例、无干涉现象。
5. **阶段五(决策点)**:根据阶段四结果决定是否把默认后端切换为 matplotlib,或长期保持双后端并存(Vega-Lite 面向需要 HTML/交互场景,matplotlib 面向论文级静态图)。

---

## 六、残留风险(需要显式跟踪,不能假装不存在)

1. **文字度量是估算值,不是实测值**。`layout/sizing.py` 里 y 轴标签宽度等是经验公式(如 `axis_fs * 5.0`),不是基于真实字体的精确度量。数据里出现异常长的分类标签时,仍可能出现估算偏差。后续可考虑加一层"基于 matplotlib 实际 `get_window_extent()` 的校验/微调",但应作为**事后校验层**,不能让它成为主要布局决策路径(否则会重新引入当年 `tight_layout` 式的不可预测性)。
2. **`title_band`/`legend_band` 等新增的间距常量需要独立标定**,不能照搬 Vega-Lite 版本里的 `reserved_height`(已在实验中验证两者不通用)。
3. **`box`/`confusion` 复杂度更高**,前者涉及须线/离群点的手工绘制,后者涉及色条 + 逐格文字标注 + 暗底白字判断,尚未验证。
4. **双后端并存会增加维护面**:任何新增图表类型或选项(如 `chart_opts`),未来都需要同时在 `vega_charts/` 和 `mpl/charts/` 各实现一遍,直到彻底决定弃用其中一个。

---

## 七、验收标准

在阶段四完成时,以下条件全部满足才认为"matplotlib 后端"达到可用状态:

- [ ] 7 种图表类型(`bar`/`line`/`scatter`/`box`/`heatmap`/`histogram`/`confusion`)在 `renderer/mpl/` 下全部实现
- [ ] `demo/demo_*_all.py` 全部脚本可以用 `backend="matplotlib"` 无报错跑通
- [ ] `demo_mixed_layout.py` 的 mixed 场景在 matplotlib 后端下无子图干涉、无标题/字号不一致
- [ ] SVG/PDF/PNG 三种格式导出均可用,PNG 的 `dpi` 参数行为与 Vega-Lite 后端语义一致
- [ ] 关键回归测试(`test/test_layout.py`、`test/test_compute_pipeline.py`)在两个后端下共享同一套 `FigureSpec` 断言,无需为 matplotlib 后端重写独立测试逻辑
