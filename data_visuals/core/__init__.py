"""
core/ — 系统抽象核心
====================

核心层负责:
    - FigureSpec:  系统统一中间表示（AST），所有模块的解耦契约
    - Figure:      顶层用户 API 入口，编排 data→compute→layout→spec 全链路
    - FigureConfig: 全局默认配置

设计原则（来自架构文档）:
    FigureSpec 是整个系统解耦的关键——
    上游模块只产出 Spec，下游模块只消费 Spec。
"""

from __future__ import annotations

from data_visuals.core.config import FigureConfig, get_default_config, set_default_config
from data_visuals.core.spec import FigureSpec, SubplotSpec
from data_visuals.core.figure import Figure, SubplotBuilder
from data_visuals.core.panel import PanelContext, PanelResult

__all__ = [
    "Figure",
    "SubplotBuilder",
    "FigureSpec",
    "SubplotSpec",
    "FigureConfig",
    "get_default_config",
    "set_default_config",
    "PanelContext",
    "PanelResult",
]
