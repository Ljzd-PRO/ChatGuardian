"""
多平台消息适配器系统（统一入口）。

说明：
- 本文件仅做适配器协议、管理器定义及各适配器导入。
- 具体适配器实现见 adapters 子包。
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Protocol

from chat_guardian.settings import Settings
from chat_guardian.domain import ChatEvent

EventHandler = Callable[[ChatEvent], Awaitable[None]]


class Adapter(Protocol):
	name: str
	async def start(self) -> None: ...
	async def stop(self) -> None: ...
	def register_handler(self, handler: EventHandler) -> None: ...
	def is_running(self) -> bool: ...


from .onebot import OneBotAdapter, OneBotAdapterConfig
from .telegram import TelegramAdapter
from .wechat import WeChatAdapter
from .feishu import FeishuAdapter
from .virtual import VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage, load_virtual_scripted_messages


class AdapterManager:
	"""适配器管理器。
	根据配置启用多个适配器，并可统一启动/停止。
	"""
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
		if not app_settings.onebot_api_root:
			raise ValueError("Adapter 'onebot' is enabled but onebot_api_root is not configured")
		adapters.append(
			OneBotAdapter(
				OneBotAdapterConfig(
					api_root=app_settings.onebot_api_root,
					access_token=app_settings.onebot_access_token,
					retry_interval_seconds=app_settings.onebot_retry_interval_seconds,
					connect_timeout_seconds=app_settings.onebot_connect_timeout_seconds,
				)
			)
		)
	if "telegram" in enabled:
		adapters.append(TelegramAdapter())
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
