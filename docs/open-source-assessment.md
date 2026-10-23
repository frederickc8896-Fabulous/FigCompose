# 开源价值评估

检索与仓库审计日期：2026-10-22。

本报告记录增加简洁 CSV 入口前的仓库快照。此后已增加包级 `plot()`、`modern` 风格、统一配色预设和直接运行的 CSV 示例，并移除旧 HTML/Vega 渲染器及其依赖。
2026-10-23 已贯通 mm/in 物理 canvas、固定 pt 字号与自动高度；当前用法见
[CSV 简洁入口](simple-api.md)、[Matplotlib 后端](matplotlib-backend.md)和 [Canvas 契约](../CANVAS_CONTRACT.md)。
下文的尺寸推算与发布缺口表保留审计当时的状态，不代表当前实现或待办。

结论：**值得开源，适合先作为范围明确的 Alpha 工具；现有证据不足以证明它比已有项目更通用或更稳定。** 建议面向需要反复更新实验结果的科研用户，承诺“数据和字段映射确定后，整张混合 Figure 的视觉规则可以复用”。开源的理由可以是把一个具体工作流做好，不必先证明算法首创。

本报告区分三类证据：本仓库代码与测试、竞品官方文档陈述、基于这些材料的产品判断。没有安装运行竞品做统一对照，因此下文的“支持”指官方文档已有该能力，不能据此判断实际稳定性优劣，也不能把未找到说明视为对方一定不支持。没有用 star 数推断需求或预测本项目的受欢迎程度。

**现有方案已经覆盖到哪里**

| 官方来源 | 文档已覆盖的能力 | 对本项目定位的影响 |
|---|---|---|
| [Matplotlib constrained layout](https://matplotlib.org/stable/users/explain/axes/constrainedlayout_guide.html) | 为轴标签、图例、色条安排空间；支持跨格、嵌套布局；compressed layout 缩小固定纵横比图之间的空隙 | 自动布局已有底层方案。自己测量文字边界不等于已经优于原生布局，需用相同输入比较 |
| [SciencePlots](https://github.com/garrettj403/SciencePlots) | 适合论文和展示的 Matplotlib 样式及组合样式 | 配色、字体、线宽的默认值本身不足以形成强差异 |
| [tueplots](https://tueplots.readthedocs.io/en/latest/docs_api/tueplots.html) | 会议/期刊的画布尺寸、字体、字号和颜色配置，生成 rcParams | 投稿尺寸预设已有先例，可研究兼容而非重复堆叠主题 |
| [UltraPlot 布局](https://ultraplot.readthedocs.io/en/stable/subplots.html)与[图例](https://ultraplot.readthedocs.io/en/stable/colorbars_legends.html) | 自动间距、整图和子图尺寸、物理单位、共享标签、面板编号、整图/局部及语义图例 | 是直接对照之一；“省去手调间距、图例”已经有人系统处理 |
| [seaborn](https://seaborn.pydata.org/tutorial/function_overview.html) | DataFrame 与 x/y/hue 字段映射、统计计算和自动图例；axes 接口可放进自定义 Figure | 顶层只传数据和字段是必要体验，但并非独有能力 |
| [plotnine](https://plotnine.org/guide/plot-composition.html) | 声明式绘图，使用 `|`、`/` 组合不同图，向整个组合应用主题 | 不能把 Python 异种图组合描述成只能手工拼装 |
| [patchworklib](https://github.com/ponnhide/patchworklib) | Matplotlib/Seaborn 图组合、文字边界相关排布、标签对齐、等距堆叠和图例移动 | 用户已有低门槛组合路线；跨图语义与数据更新规则更值得投入 |
| [FigureFlow 教程](https://figureflow.readthedocs.io/en/latest/tutorial.html)与[统计图 API](https://figureflow.readthedocs.io/en/latest/generated/figureflow.figure_panel.FigurePanel.show_data.html) | CSV 数据与字段映射、数据图/图像混合、跨格布局、期刊尺寸和统计标注 | 与“数据输入到完整论文 Figure”直接重叠，不能声称这是尚未有人解决的问题 |
| [cnsplots](https://github.com/faridrashidi/cnsplots) | 论文默认样式、表格数据绘图、多面板、pt/in/mm 尺寸、配色及可编辑 SVG | 同时覆盖易用 API、风格和整图，是优先实测的对照之一 |
| [FigCombo](https://github.com/Tailong-Chen/FigCombo) | ASCII 跨格布局、数据图与图像混合、全局字体/颜色、面板编号、导出前尺寸/DPI/字体校验 | 定位高度接近。其 README 声明需通过实测验证，但足以否定“统一论文绘图 API 没有竞争者” |
| [pubfig](https://github.com/Galaxy-Dawn/pubfig) | 统一科学绘图 API、论文样式、期刊宽度导出、导出时重排、JSON CLI、面板导出后在 Figma 组装 | 连自动化入口和论文导出流程也有直接先例；不应只比较样式库 |
| [Pylustrator](https://pylustrator.readthedocs.io/en/latest/)与[FigureFirst](https://github.com/FlyRanch/figurefirst) | 前者交互调整并写回 Python；后者从 Inkscape SVG 模板生成可复用布局 | 用户还可以选择交互精修或模板工作流。本项目可重点减少常见实验图的这些操作 |

这些工具的输入方式、约束和使用成本不同，不是完全可互换的替代品。尤其不能拿旧 ProPlot 的兼容情况代表现行 UltraPlot，也不能再把 plotnine 当作仅支持单图的库；它已有原生组合接口。上述能力来自各项目官方资料，尚未形成同环境性能或布局质量排名。

**本仓库已经具备的价值**

目前实现已经超出单纯设置 rcParams：

- 数据计算、版式和 Matplotlib 渲染分层；七类图可在一张图中组合，包括不等大小和跨行列面板。参见 [Figure](../data_visuals/core/figure.py)、[布局管理器](../data_visuals/layout/manager.py)和[出版示例](../demo/demo_publication_mixed.py)。
- 同一 Figure 共用字段的完整类别域与颜色映射，子图筛选后保持颜色；通过 `FigureConfig.category_colors` 可固定跨数据文件的类别颜色。**如果新数据改变完整类别域，不能仅凭自动色板保证跨版本同色，必须持久化映射或显式配置。** 参见 [配置](../data_visuals/core/config.py)及[颜色验收](../test/test_mpl_layout.py)。
- 主标题、子标题、轴标签、刻度、全局及局部 legend 共享全局画布字号层级；渲染器按实际文字测量安排空间、图例换行、独立色条，空间不足有明确错误。参见 [字号](../data_visuals/layout/sizing.py)、[渲染布局](../data_visuals/renderer/mpl/canvas.py)和[布局验收](../test/test_mpl_acceptance.py)。
- SVG/PDF/PNG 导出、固定画布、局部 rc_context 和不依赖 Altair 的默认运行路径已有实现与测试。参见 [导出验收](../test/test_mpl_export.py)。
- 示例可自行构造带固定随机种子的数据，不要求先准备外部 CSV；测试检查颜色、数值和装饰边界，而不只是检查“文件生成了”。

这些是当前可核实的工程基础，不代表所有输入、平台或期刊要求均已验证。相同能力在其他库中可能也存在；本项目仍需要以完成同一任务所需的声明量、人工调整次数和异常数据表现证明使用价值。

建议产品表述为：

> 为实验结果编写可复用的整图模板：传入表格数据与字段映射，统一处理不同图种之间的颜色、字号、图例和留白，并在导出时检查版面。

先服务模型对比、消融实验、敏感性分析、分布与错误分析这类重复工作流比较合适。这是定位建议，不是已验证的用户需求。暂时继续维护七类常见图，比扩展大量冷门图种、恢复 HTML 排版、添加 GUI 或 AI 入口更有助于检验核心目标。

**最值得继续补的能力：最终出版尺寸**

全局 canvas 比例能保持整图内部的字号层级，但论文读者看到的是最后插入页面的物理尺寸。Nature 的官方示例要求普通文字 5–7 pt、面板编号 8 pt，并要求文字可编辑与可访问配色；其他出版方应分别核实，不能把这些数值当成通用规范。[Nature figure specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)

当前 Matplotlib canvas 使用 72 DPI 设计坐标，`publication_mixed` 的 1800×1350 对应 25×18.75 英寸。其刻度约 20.2 pt、此次改大的 legend 为 27 pt；若整图等比缩到 180 mm 宽，分别约为 5.73 pt 和 7.65 pt。若缩到 89 mm，刻度约为 2.83 pt。换算式为 `最终字号 = 导出字号 × 最终宽度 / 导出物理宽度`。这些数值是本项目当前设计坐标的推算，不是对所有输出的统一结论。

因此，后续应支持“最终宽度 mm/in + 最终文字 pt + 位图 DPI”三个独立概念，并在目标尺寸下重新排版与检查。当前的比例规则可继续用于选择默认层级，投稿预设则需要允许固定物理字号；只把大图缩小，不能保证可读。物理尺寸和校验也已有竞品覆盖，价值仍要通过完整工作流体现。

**公开 Alpha 前应处理的仓库问题**

以下为审计时的历史记录，CSV 入口、风格、旧后端与测试依赖等条目此后已有变化；发布前需按当前仓库重新核实：

| 优先级 | 审计时证据 | 当时建议 |
|---|---|---|
| 发布前 | [pyproject.toml](../pyproject.toml) 声明 `paperfig = "data_visuals:main"`，但 [包入口](../data_visuals/__init__.py) 没有 `main`；实测 `hasattr(data_visuals, "main")` 为 False | 删除无效命令承诺，或实现并测试真实入口 |
| 发布前 | 元数据和 README 写 MIT，根目录未见 LICENSE | 完成许可文件和版权信息，核对随包分发文件 |
| 发布前 | 项目品牌和命令使用 PaperFig/paperfig；已有同领域 [paperfig](https://sekika.github.io/paperfig/) 提供 JSON 驱动论文图编排并以该名称安装 | 发布时选择易区分的名称；这里是检索与使用混淆问题，不作商标权判断 |
| 发布前 | [README](../README.md) 仍有 Altair 管道描述；[Figure 类文档](../data_visuals/core/figure.py) 展示不存在的 neurips 主题，当前可用主题仅 general | 统一入口说明，提供一个无需 CSV 的复制即运行示例，清楚标识 Alpha 范围 |
| 发布前 | 根目录未见 `.gitignore` 和 `.github`；有测试产物、缓存和旧 HTML 预览 | 明确发布文件范围，验证干净 wheel 安装和最小导出；逐步建立跨平台 CI。本次 `git status` 返回非仓库，无法判断文件跟踪状态 |
| 已处理 | 审计时 [conftest.py](../test/conftest.py) 无条件导入 Altair，完整测试依赖旧后端 | 随旧后端清理移除专用测试与依赖；当前完整测试安装 `.[dev]` 即可 |
| 尽快 | 默认字体优先 Times New Roman，缺失时按本机字体回退；SVG 保留文字 | 报告实际使用字体、提供便携默认值，并验证 Windows/Linux。当前不能承诺跨机器像素一致或查看端字体永不替换 |
| 后续核心 | 顶层尚无明确最终 mm 尺寸入口，画布比例也不能替代最终字号 | 增加物理尺寸、最终字号与溢出诊断，并验证不同格式下的实际输出 |

不需要等任意布局、所有图种和所有期刊都支持才公开源码。先修复安装、命令、许可、示例等直接影响外部用户的问题，再声明有限支持范围，就可以开展 Alpha 验证。

**如何判断后续投入是否值得**

建议先邀请 5–10 位目标用户，选取约 5 张实际混合论文图，用本项目、Matplotlib/Seaborn、UltraPlot，以及 cnsplots 或 FigCombo 中最接近的方案完成同一输入任务。人数和图数是建议实验规模，不是已取得的验证结果。

| 场景 | 应记录的结果 |
|---|---|
| 首次搭建一张多图种 Figure | 从示例到首个可用输出的时间、版式声明量、手工位置/字号调整次数 |
| 更新实验结果 | 不改版式代码时，长标签、增加类别、缺组、子集筛选后的完成情况 |
| 视觉语义 | 同类别颜色是否保持，图例是否误合并，同名但不同字段是否仍能区分 |
| 投稿尺寸 | 单栏/双栏宽度下的最小物理字号、留白、碰撞、固定纵横比图的表现 |
| 复现和失败 | Windows/Linux、实际字体、SVG/PDF/PNG；不可行输入的错误是否能指导修改 |
| 数据含义 | 均值、误差、重复观测、缺失值与归一化的处理是否明确，是否与参照数值一致 |

几何测试只能发现部分排版问题，还需要看图判断信息密度、视觉平衡与可读性。比较应报告失败样本，不能只挑自己的演示数据。若多数真实图仍需频繁进入 renderer 调坐标，说明“顶层只传数据”的承诺尚未成立；若能在有限图种范围内持续减少这些操作，即使没有独创布局算法，也有充分的开源价值。

本次具体变更：全局及局部 legend 默认改为 `clamp(0.02 × min(canvas_width, canvas_height), 8, 40)`；五个出版示例输出已重新生成，36 项字号、图例和布局相关测试通过。开源评估为文档交付，尚未执行公开发布或上述发布准备修复。
