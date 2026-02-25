"""
多平台消息适配器系统。

说明：
- 本模块采用适配器风格，而非统一的 connect/disconnect 会话接口；
- 支持 onebot、telegram、wechat、feishu 四类适配器；
- 当前仅实现 `OneBotAdapter`，其余适配器为占位。
"""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

from aiocqhttp import CQHttp

from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent
from chat_guardian.settings import Settings

EventHandler = Callable[[ChatEvent], Awaitable[None]]


class Adapter(Protocol):
    """适配器协议。

    适配器需支持启动、停止、健康状态查询和事件处理器注册。
    """

    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def register_handler(self, handler: EventHandler) -> None: ...

    def is_running(self) -> bool: ...


@dataclass(slots=True)
class OneBotAdapterConfig:
    """OneBot 适配器配置。"""

    api_root: str
    access_token: str | None = None
    retry_interval_seconds: float = 5.0
    connect_timeout_seconds: float = 10.0


@dataclass(slots=True)
class VirtualAdapterConfig:
    """VirtualAdapter 配置（用于测试与联调）。"""

    chat_count: int = 3
    members_per_chat: int = 5
    messages_per_chat: int = 10
    interval_min_seconds: float = 0.1
    interval_max_seconds: float = 0.6
    random_seed: int = 42
    scripted_messages: list["VirtualScriptedMessage"] | None = None


@dataclass(slots=True)
class VirtualScriptedMessage:
    """虚拟消息脚本条目。"""

    chat_id: str
    sender_id: str
    text: str
    sender_name: str | None = None
    delay_seconds: float = 0.1
    chat_type: ChatType = ChatType.GROUP
    is_from_self: bool = False


class OneBotAdapter(Adapter):
    """基于 `aiocqhttp` 的 OneBot 适配器。

    行为特征：
    - 可在任意时刻调用 `start()` 开始连接尝试；
    - 若连接失败，会按配置间隔持续重试；
    - 当接收到消息事件时，转换为统一 `ChatEvent` 交给已注册处理器。
    """

    name = "onebot"

    def __init__(self, config: OneBotAdapterConfig):
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._ready = False
        self._retry_task: asyncio.Task[None] | None = None
        self._bot = CQHttp(api_root=config.api_root, access_token=config.access_token or "")
        self._register_bot_callbacks()

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._retry_task = asyncio.create_task(self._retry_connect_loop())

    async def stop(self) -> None:
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
            self._retry_task = None

    def _register_bot_callbacks(self) -> None:
        @self._bot.on_message
        async def _on_message(event: dict[str, Any]) -> None:
            chat_event = await self._convert_event(event)
            if chat_event is None:
                return
            await asyncio.gather(*(handler(chat_event) for handler in self._handlers), return_exceptions=True)

    async def _retry_connect_loop(self) -> None:
        while self._running:
            try:
                await asyncio.wait_for(self._bot.get_login_info(), timeout=self.config.connect_timeout_seconds)
                self._ready = True
                await asyncio.sleep(self.config.retry_interval_seconds)
            except Exception:
                self._ready = False
                await asyncio.sleep(self.config.retry_interval_seconds)

    async def _convert_event(self, event: dict[str, Any]) -> ChatEvent | None:
        message = await self._build_message(event)
        message_type = str(event.get("message_type", "group"))
        chat_type = ChatType.GROUP if message_type == "group" else ChatType.PRIVATE
        chat_id = str(event.get("group_id") or event.get("user_id") or message.chat_id)
        self_id = str(event.get("self_id", ""))
        is_from_self = bool(self_id) and message.sender_id == self_id
        return ChatEvent(
            chat_type=chat_type,
            chat_id=chat_id,
            message=message,
            platform=self.name,
            is_from_self=is_from_self,
        )

    async def _build_message(self, event: dict[str, Any], depth: int = 0) -> ChatMessage:
        raw_segments = event.get("message", [])
        if isinstance(raw_segments, str):
            raw_segments = [{"type": "text", "data": {"text": raw_segments}}]

        contents: list[MessageContent] = []
        reply_from: ChatMessage | None = None

        for segment in raw_segments:
            segment_type = str(segment.get("type", "text"))
            data = segment.get("data", {}) or {}
            if segment_type == "text":
                contents.append(MessageContent(type=ContentType.TEXT, text=str(data.get("text", ""))))
            elif segment_type == "image":
                contents.append(MessageContent(type=ContentType.IMAGE, image_url=str(data.get("url") or data.get("file") or "")))
            elif segment_type == "at":
                contents.append(MessageContent(type=ContentType.MENTION, mention_user_id=str(data.get("qq", ""))))
            elif segment_type == "reply" and depth < 1:
                reply_id = data.get("id")
                if reply_id is not None:
                    try:
                        reply_payload = await self._bot.get_msg(message_id=int(reply_id))
                        if isinstance(reply_payload, dict):
                            reply_from = await self._build_message(reply_payload, depth=depth + 1)
                    except Exception:
                        reply_from = None

        sender = event.get("sender", {}) or {}
        sender_id = str(event.get("user_id") or sender.get("user_id") or "")
        sender_name = sender.get("nickname")
        chat_id = str(event.get("group_id") or event.get("user_id") or "")

        timestamp_raw = event.get("time")
        if isinstance(timestamp_raw, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        return ChatMessage(
            message_id=str(event.get("message_id", "")),
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=(str(sender_name) if sender_name else None),
            contents=contents,
            reply_from=reply_from,
            timestamp=timestamp,
        )


class TelegramAdapter(Adapter):
    """Telegram 适配器占位实现。"""

    name = "telegram"

    def __init__(self):
        self._handlers: list[EventHandler] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return False


class WeChatAdapter(Adapter):
    """WeChat 适配器占位实现。"""

    name = "wechat"

    def __init__(self):
        self._handlers: list[EventHandler] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return False


class FeishuAdapter(Adapter):
    """飞书适配器占位实现。"""

    name = "feishu"

    def __init__(self):
        self._handlers: list[EventHandler] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return False


class VirtualAdapter(Adapter):
    """测试用虚拟适配器。

    默认支持两种模式：
    - 脚本模式：由 `VirtualAdapterConfig.scripted_messages` 提供完整消息序列；
    - 生成模式：若未提供脚本，按配置生成占位消息（不绑定任何具体业务语料）。
    """

    name = "virtual"

    def __init__(self, config: VirtualAdapterConfig):
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._rng = random.Random(config.random_seed)
        self._message_sequences: dict[str, int] = defaultdict(int)

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self.config.scripted_messages:
            self._tasks = [asyncio.create_task(self._run_scripted_messages(self.config.scripted_messages))]
            return
        self._tasks = [
            asyncio.create_task(self._simulate_chat(chat_id=f"virtual-group-{index + 1}"))
            for index in range(max(1, self.config.chat_count))
        ]

    async def stop(self) -> None:
        self._running = False
        if self._tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*self._tasks, return_exceptions=True), timeout=20.0)
            except asyncio.TimeoutError:
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _simulate_chat(self, chat_id: str) -> None:
        member_count = max(2, self.config.members_per_chat)
        members = [f"user-{chat_id}-{idx + 1}" for idx in range(member_count)]

        for _ in range(max(1, self.config.messages_per_chat)):
            if not self._running:
                break

            interval = self._rng.uniform(
                min(self.config.interval_min_seconds, self.config.interval_max_seconds),
                max(self.config.interval_min_seconds, self.config.interval_max_seconds),
            )
            await asyncio.sleep(interval)

            sender_id = self._rng.choice(members)
            sender_name = sender_id.replace("user", "member")
            text = f"message-{self._message_sequences[chat_id] + 1} from {sender_name}"

            self._message_sequences[chat_id] += 1
            message = ChatMessage(
                message_id=f"{chat_id}-m-{self._message_sequences[chat_id]}",
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                timestamp=datetime.now(timezone.utc),
                contents=[MessageContent(type=ContentType.TEXT, text=text)],
            )
            event = ChatEvent(
                chat_type=ChatType.GROUP,
                chat_id=chat_id,
                message=message,
                platform=self.name,
                is_from_self=False,
            )
            await asyncio.gather(*(handler(event) for handler in self._handlers), return_exceptions=True)

    async def _run_scripted_messages(self, scripted_messages: list[VirtualScriptedMessage]) -> None:
        for item in scripted_messages:
            if not self._running:
                break

            await asyncio.sleep(max(0.0, item.delay_seconds))

            self._message_sequences[item.chat_id] += 1
            message = ChatMessage(
                message_id=f"{item.chat_id}-m-{self._message_sequences[item.chat_id]}",
                chat_id=item.chat_id,
                sender_id=item.sender_id,
                sender_name=item.sender_name,
                timestamp=datetime.now(timezone.utc),
                contents=[MessageContent(type=ContentType.TEXT, text=item.text)],
            )
            event = ChatEvent(
                chat_type=item.chat_type,
                chat_id=item.chat_id,
                message=message,
                platform=self.name,
                is_from_self=item.is_from_self,
            )
            await asyncio.gather(*(handler(event) for handler in self._handlers), return_exceptions=True)


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
        adapters.append(
            VirtualAdapter(
                VirtualAdapterConfig(
                    chat_count=app_settings.virtual_adapter_chat_count,
                    members_per_chat=app_settings.virtual_adapter_members_per_chat,
                    messages_per_chat=app_settings.virtual_adapter_messages_per_chat,
                    interval_min_seconds=app_settings.virtual_adapter_interval_min_seconds,
                    interval_max_seconds=app_settings.virtual_adapter_interval_max_seconds,
                )
            )
        )

    return adapters
