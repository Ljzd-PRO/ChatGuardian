from __future__ import annotations
import asyncio
from typing import Any
from aiocqhttp import CQHttp
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent
from dataclasses import dataclass
from datetime import datetime, timezone
from chat_guardian.adapters import Adapter, EventHandler

@dataclass(slots=True)
class OneBotAdapterConfig:
    api_root: str
    access_token: str | None = None
    retry_interval_seconds: float = 5.0
    connect_timeout_seconds: float = 10.0

class OneBotAdapter(Adapter):
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
