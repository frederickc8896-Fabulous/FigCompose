"""
FigCompose — 规则驱动的论文数据可视化工具
=========================================

一个完全基于规则运行的声明式数据可视化引擎。
核心设计原则：Chart 决定"画什么"，Compute 决定"怎么算"，
Layout 决定"放哪里"，Theme 决定"长什么样"。
"""

__version__ = "0.1.1"

from data_visuals.api import plot
from data_visuals.core.config import FigureConfig
from data_visuals.core.quality import FigureReport, FigureQualityError, QualityIssue, check_figure
from data_visuals.utils.colors import list_color_presets

__all__ = ["plot", "FigureConfig", "FigureReport", "FigureQualityError", "QualityIssue",
           "check_figure", "list_color_presets", "__version__"]
