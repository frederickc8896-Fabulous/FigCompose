# 图例布局示例

同一份合成数据、110 × 125 mm 画布、字号、配色和点形，仅改变 `legend` 配置。
所有版本通过 PaperFig 的数据、布局与渲染管线生成；脚本不直接操作 Matplotlib axes。

```bash
python demo/demo_legend.py
```

| 配置 | 预览 | 矢量文件 |
|---|---|---|
| 共享顶部，3 列 | [PNG](legend_top.png) | [PDF](legend_top.pdf) · [SVG](legend_top.svg) |
| 共享底部，3 列 | [PNG](legend_bottom.png) | [PDF](legend_bottom.pdf) · [SVG](legend_bottom.svg) |
| 共享左侧，1 列 | [PNG](legend_left.png) | [PDF](legend_left.pdf) · [SVG](legend_left.svg) |
| 共享右侧，1 列 | [PNG](legend_right.png) | [PDF](legend_right.pdf) · [SVG](legend_right.svg) |
| 局部四角，上图右上、下图右下 | [PNG](legend_local.png) | [PDF](legend_local.pdf) · [SVG](legend_local.svg) |
| 隐藏并回收空间 | [PNG](legend_hidden.png) | [PDF](legend_hidden.pdf) · [SVG](legend_hidden.svg) |

共享侧边图例预留装饰带；局部四角不缩小绘图区，必要时由调用者选择不遮挡数据的位置。
局部示例的下图仅覆盖 `position`，继续继承全局字号、边框、顺序与文字映射。

[生成脚本](../../demo/demo_legend.py) · [字段契约](../../docs/matplotlib-backend.md#图例配置)
