"""
多平台消息适配器系统（统一入口）。

说明：
- 本文件仅做适配器导出。
- 具体适配器实现见 adapters 子包。
"""

from __future__ import annotations

from .base import Adapter, EventHandler
from .manager import AdapterManager, build_adapters_from_settings
from .onebot import OneBotAdapter, OneBotAdapterConfig
from .telegram import TelegramAdapter
from .wechat import WeChatAdapter
from .feishu import FeishuAdapter
from .virtual import VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage, load_virtual_scripted_messages

__all__ = [
    "Adapter",
    "EventHandler",
    "AdapterManager",
    "build_adapters_from_settings",
    "OneBotAdapter",
    "OneBotAdapterConfig",
    "TelegramAdapter",
    "WeChatAdapter",
    "FeishuAdapter",
    "VirtualAdapter",
    "VirtualAdapterConfig",
    "VirtualScriptedMessage",
    "load_virtual_scripted_messages",
]
