# Reproducible FigCompose examples / 可复现示例

Install **`FigCompose>=0.2.0`**, download or clone the example folders, then run a generator.
Each example includes its actual CSV, a reusable `style.yaml`, the complete script and a preview.
FigCompose 0.2.0 includes 19 native kinds, the `showcase` style and circular summary placement.
The updated [2D/3D comparison](three_dimensional_views/README.md), [circular scores](circular_scores/README.md),
[native chord](chord_connections/README.md) and [six-view distribution series](intervals/README.md)
use native declarations and reusable presentation rules.

安装 **`FigCompose>=0.2.0`**，下载或克隆示例目录后运行脚本。FigCompose 0.2.0包含19种原生图、`showcase`及环条摘要位置。
每个示例包含实际 CSV、统一风格配置、完整代码和预期效果；无需本地 demo 或开发目录。

```bash
python -m pip install "FigCompose>=0.2.0"
python examples/mixed_figure/generate.py
python examples/intervals/generate.py
python examples/intervals/generate_series.py
python examples/circular_scores/generate.py
```

| Example / 示例 | What it demonstrates / 展示内容 | Preview / 预览 |
|---|---|---|
| [Mixed figure / 四图组合](mixed_figure/README.md) | Four native charts; the absent method retains its identity slot / 四类原生图、缺席方法保留颜色位置 | ![Mixed figure](mixed_figure/preview.png) |
| [Differences and distributions / 差异与分布](intervals/README.md) | Six native views, explicit paired estimates and supplied asymmetric bounds / 六种原生统计视角、显式配对估计与预计算非对称区间 | ![Six statistical views](intervals/series/preview.png) |
| [Circular scores / 同心环条](circular_scores/README.md) | Native circular scores with a large-number summary strip / 原生环条与大数字均值摘要 | ![Circular scores](circular_scores/preview.png) |
| [Participant tracks / 环形多轨](participant_tracks/README.md) | Five aligned tracks and a summary of the same cohort / 同一队列五轨对齐与总体摘要 | ![Participant tracks](participant_tracks/preview.png) |
| [Circular clustering / 环形聚类](clustered_heatmap/README.md) | Actual Ward tree, signed values and cluster annotations / 真实聚类树、数值轨与分组注释 | ![Circular clustering](clustered_heatmap/preview.png) |
| [2D / 3D comparison / 二维三维对照](three_dimensional_views/README.md) | Six native panels, overview and enlarged carousel panels / 六格原生同源对照、总览与放大轮播图 | ![Paired views](three_dimensional_views/preview.png) |
| [Chord connections / 弦图](chord_connections/README.md) | Native weighted undirected relationships / 原生弦图按真实权重分配两端与节点弧长 | ![Chord connections](chord_connections/preview.png) |
| [Alluvial flows / 桑基流图](alluvial_flows/README.md) | Conserved participant counts over three stages / 三阶段、同一批人的类别流向 | ![Alluvial flows](alluvial_flows/preview.png) |

Mixed figure, circular scores, the six-view interval series, 2D/3D comparison and
chords now use native chart declarations throughout. Their defaults remain reusable
through the ordinary `style`, `palette` and chart options. Participant tracks,
circular clustering and alluvial flows still provide complete `Figure.custom`
templates; these three are not additional native `kind` values. The original
supplied-bound interval generator remains available alongside the six-view series.

四图组合、环条、六图统计系列、二维三维对照和弦图均全部使用原生声明，通过既有 `style`、`palette` 和图种选项复用呈现规则。
环形多轨、环形聚类和桑基流图仍提供完整的 `Figure.custom` 模板，可读取新 CSV 复用，这三类没有注册为额外原生图种。
原有给定边界的区间入口继续保留。复制示例时请一并保留公共导出文件 `examples/_export.py`。

All observations are synthetic. Default typography requests Times New Roman from the operating system;
Matplotlib falls back to another serif font if it is unavailable. Matching fonts and dependency versions
are needed for exact layout reproduction. Exports contain no manual axes placement or image assembly.

全部数据为模拟数据。默认请求系统的 Times New Roman，缺少时回退其他衬线字体；跨设备精确复现需保持字体与依赖一致。
导出由 FigCompose 管理整图布局，生成器不手动拼接图片。
