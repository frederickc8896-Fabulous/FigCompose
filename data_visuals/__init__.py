"""
data_visuals — 规则驱动的数据可视化工具
=========================================

一个完全基于规则运行的声明式数据可视化引擎。
核心设计原则：Chart 决定"画什么"，Compute 决定"怎么算"，
Layout 决定"放哪里"，Theme 决定"长什么样"。
"""

__version__ = "0.1.0"

from data_visuals.api import plot
from data_visuals.core.config import FigureConfig
from data_visuals.utils.colors import list_color_presets

__all__ = ["plot", "FigureConfig", "list_color_presets", "__version__"]
