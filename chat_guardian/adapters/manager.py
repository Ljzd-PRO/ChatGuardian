from __future__ import annotations

import asyncio

from chat_guardian.settings import Settings

from .base import Adapter
from .feishu import FeishuAdapter
from .onebot import OneBotAdapter, OneBotAdapterConfig
from .telegram import TelegramAdapter, TelegramAdapterConfig
from .virtual import VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage, load_virtual_scripted_messages
from .wechat import WeChatAdapter


class AdapterManager:
    """适配器管理器。根据配置启用多个适配器，并可统一启动/停止。"""

    def __init__(self, adapters: list[Adapter]):
        self.adapters = adapters

    async def start_all(self) -> None:
        await asyncio.gather(*(adapter.start() for adapter in self.adapters))

    async def stop_all(self) -> None:
        await asyncio.gather(*(adapter.stop() for adapter in self.adapters))


def build_adapters_from_settings(app_settings: Settings) -> list[Adapter]:
    """根据配置创建启用的适配器列表。"""
    enabled = {name.strip().lower() for name in app_settings.enabled_adapters}
    adapters: list[Adapter] = []

    if "onebot" in enabled:
        adapters.append(
            OneBotAdapter(
                OneBotAdapterConfig(
                    host=app_settings.onebot_host,
                    port=app_settings.onebot_port,
                    access_token=app_settings.onebot_access_token,
                )
            )
        )
    if "telegram" in enabled:
        if not app_settings.telegram_bot_token:
            raise ValueError("Telegram 适配器已启用，但 CHAT_GUARDIAN_TELEGRAM_BOT_TOKEN 未配置")
        adapters.append(
            TelegramAdapter(
                TelegramAdapterConfig(
                    bot_token=app_settings.telegram_bot_token,
                    polling_timeout=app_settings.telegram_polling_timeout,
                    drop_pending_updates=app_settings.telegram_drop_pending_updates,
                )
            )
        )
    if "wechat" in enabled:
        adapters.append(WeChatAdapter())
    if "feishu" in enabled:
        adapters.append(FeishuAdapter())
    if "virtual" in enabled:
        scripted_messages: list[VirtualScriptedMessage] | None = None
        if app_settings.virtual_adapter_script_path:
            scripted_messages = load_virtual_scripted_messages(app_settings.virtual_adapter_script_path)
        adapters.append(
            VirtualAdapter(
                VirtualAdapterConfig(
                    chat_count=app_settings.virtual_adapter_chat_count,
                    members_per_chat=app_settings.virtual_adapter_members_per_chat,
                    messages_per_chat=app_settings.virtual_adapter_messages_per_chat,
                    interval_min_seconds=app_settings.virtual_adapter_interval_min_seconds,
                    interval_max_seconds=app_settings.virtual_adapter_interval_max_seconds,
                    scripted_messages=scripted_messages,
                )
            )
        )
    return adapters
