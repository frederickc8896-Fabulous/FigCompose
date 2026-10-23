# 示例输出

按用途归档；同一示例的 PNG、SVG、PDF、图注和数据表放在一起。
生成命令在仓库根目录运行，显式指定 `--out` 时仍使用指定目录。

| 目录 | 内容与入口 | 生成命令 |
|---|---|---|
| `quickstart/` | [CSV 快速入门](quickstart/simple_csv.png) | `python demo/demo_simple_csv.py` |
| `canvas/` | [单图](canvas/canvas_single.png)、[组合图](canvas/canvas_mixed.png)、[自动高度](canvas/canvas_auto.png) | `python demo/demo_canvas.py` |
| `colors/` | [分类色卡](colors/color_catalog_categorical.png)、[连续色阶](colors/color_catalog_sequential.png)、[整图配色](colors/curated_5_default.png) | `python demo/demo_color_catalog.py` |
| `publication/` | [七类图混排](publication/publication_mixed.png)、[布局压力示例](publication/publication_stress.png) | `python demo/demo_publication_mixed.py` |
| `legends/` | [共享四侧、局部四角与隐藏图例](legends/README.md) | `python demo/demo_legend.py` |
| `matched_training/` | [单栏 2×1 差值与区间](matched_training/matched_training_single_column.png)、[同尺寸对照](matched_training/matched_training_single_column_vs_reference.png)、[对照说明](matched_training/matched_training_single_column_comparison.md) | `python demo/demo_matched_training.py` |
| `rejection_rewrite/comparison/` | [后果对照图](rejection_rewrite/comparison/rejection_rewrite_comparison.png)、[PDF](rejection_rewrite/comparison/rejection_rewrite_comparison.pdf)、[图注与数值表](rejection_rewrite/comparison/rejection_rewrite_comparison_caption.md) | `python demo/demo_rejection_rewrite_comparison.py` |
| `rejection_rewrite/working_points/` | [联合工作点](rejection_rewrite/working_points/rejection_rewrite_working_points.png)、[编号版](rejection_rewrite/working_points/rejection_rewrite_working_points_numbered.png)、[图注与原句对应](rejection_rewrite/working_points/rejection_rewrite_working_points_caption.md) | `python demo/demo_rejection_rewrite.py --numbered` |

图种细分示例 `demo/demo_*_all.py`、`demo/demo_clustered_*.py` 等默认输出至
`charts/<图种>/`，运行时按需创建目录。

拒收改写案例中的 `*_changes.csv` / `*_summary.csv` 等为数值汇总，
`*_manifest.json` 记录原始数据来源、筛选条件与输出规格。
