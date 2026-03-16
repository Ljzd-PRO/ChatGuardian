"""
多平台消息适配器系统（统一入口）。

说明：
- 本文件仅做适配器导出。
- 具体适配器实现见 adapters 子包。
"""

from __future__ import annotations

from .base import Adapter, EventHandler
from .dingtalk import DingTalkAdapter, DingTalkAdapterConfig
from .discord import DiscordAdapter, DiscordAdapterConfig
from .feishu import FeishuAdapter
from .manager import AdapterManager, build_adapters_from_settings
from .onebot import OneBotAdapter, OneBotAdapterConfig
from .telegram import TelegramAdapter
from .virtual import VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage, load_virtual_scripted_messages
from .wechat import WeChatAdapter, WeChatAdapterConfig

__all__ = [
    "Adapter",
    "EventHandler",
    "AdapterManager",
    "build_adapters_from_settings",
    "OneBotAdapter",
    "OneBotAdapterConfig",
    "TelegramAdapter",
    "DiscordAdapter",
    "DiscordAdapterConfig",
    "WeChatAdapter",
    "WeChatAdapterConfig",
    "DingTalkAdapter",
    "DingTalkAdapterConfig",
    "FeishuAdapter",
    "VirtualAdapter",
    "VirtualAdapterConfig",
    "VirtualScriptedMessage",
    "load_virtual_scripted_messages",
]
