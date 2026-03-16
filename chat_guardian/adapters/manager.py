from __future__ import annotations

import asyncio

from chat_guardian.settings import Settings
from .base import Adapter
from .dingtalk import DingTalkAdapter, DingTalkAdapterConfig
from .discord import DiscordAdapter, DiscordAdapterConfig
from .feishu import FeishuAdapter
from .onebot import OneBotAdapter, OneBotAdapterConfig
from .telegram import TelegramAdapter, TelegramAdapterConfig
from .virtual import VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage, load_virtual_scripted_messages
from .wechat import WeChatAdapter, WeChatAdapterConfig


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
    if "discord" in enabled:
        if not app_settings.discord_bot_token:
            raise ValueError("Discord 适配器已启用，但 discord_bot_token 未配置")
        adapters.append(
            DiscordAdapter(
                DiscordAdapterConfig(
                    bot_token=app_settings.discord_bot_token,
                    guild_ids=list(app_settings.discord_guild_ids),
                )
            )
        )
    if "wechat" in enabled:
        if not (app_settings.wechat_token and app_settings.wechat_encoding_aes_key and app_settings.wechat_corp_id):
            raise ValueError(
                "WeChat Work 适配器已启用，但 wechat_token / wechat_encoding_aes_key / wechat_corp_id 未完整配置"
            )
        adapters.append(
            WeChatAdapter(
                WeChatAdapterConfig(
                    token=app_settings.wechat_token,
                    encoding_aes_key=app_settings.wechat_encoding_aes_key,
                    corp_id=app_settings.wechat_corp_id,
                    host=app_settings.wechat_host,
                    port=app_settings.wechat_port,
                )
            )
        )
    if "dingtalk" in enabled:
        if not (app_settings.dingtalk_client_id and app_settings.dingtalk_client_secret):
            raise ValueError(
                "DingTalk 适配器已启用，但 dingtalk_client_id / dingtalk_client_secret 未配置"
            )
        adapters.append(
            DingTalkAdapter(
                DingTalkAdapterConfig(
                    client_id=app_settings.dingtalk_client_id,
                    client_secret=app_settings.dingtalk_client_secret,
                )
            )
        )
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
