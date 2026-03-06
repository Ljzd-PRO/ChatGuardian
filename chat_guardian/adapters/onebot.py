from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aiocqhttp import CQHttp
from aiocqhttp.exceptions import Error as OneBotError  # noqa: F401
from loguru import logger

from chat_guardian.adapters.base import Adapter, EventHandler
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent, UserInfo


@dataclass(slots=True)
class OneBotAdapterConfig:
    """OneBot 适配器配置 - 使用反向 WebSocket 连接方式
    
    OneBot 实例需要配置连接到此服务的 WebSocket 地址，例如：
    ws://host:port/ws/event/
    """
    host: str = "127.0.0.1"
    port: int = 8081
    access_token: str | None = None


class OneBotAdapter(Adapter):
    name = "onebot"

    def __init__(self, config: OneBotAdapterConfig):
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._ready = False
        self._server_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._bot = CQHttp(access_token=config.access_token or "")
        logger.info(
            f"📦 OneBot 适配器已初始化 | host={config.host} | port={config.port} | token_configured={bool(config.access_token)}")
        self._register_bot_callbacks()

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
        logger.info(f"📝 事件处理器已注册 | 当前处理器数量={len(self._handlers)}")

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 OneBot 适配器，开启 WebSocket 服务器用于反向连接"""
        if self._running:
            logger.warning(f"⚠️ OneBot 适配器当前已运行，忽略重复启动请求")
            return
        self._running = True
        self._shutdown_event = asyncio.Event()
        logger.info(f"🚀 正在启动 OneBot 适配器 | 监听地址={self.config.host}:{self.config.port}")
        try:
            # 启动内置的 Quart/Hypercorn 服务器，等待 OneBot 实例连接。
            # 显式传入 shutdown_trigger 以防止 Hypercorn 覆盖 uvicorn 的信号处理器。
            self._server_task = asyncio.create_task(
                self._bot.run_task(
                    host=self.config.host,
                    port=self.config.port,
                    shutdown_trigger=self._shutdown_event.wait,
                )
            )
            logger.success(
                f"✅ OneBot WebSocket 服务器已启动 | 反向连接地址: ws://{self.config.host}:{self.config.port}/ws")
        except Exception as e:
            logger.error(f"❌ OneBot 适配器启动失败: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """停止 OneBot 适配器和 WebSocket 服务器"""
        logger.info(f"🛑 正在停止 OneBot 适配器...")
        self._running = False
        self._ready = False
        if self._shutdown_event:
            self._shutdown_event.set()
            self._shutdown_event = None
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
                logger.info(f"✅ OneBot 服务器任务已关闭")
            except asyncio.CancelledError:
                logger.debug(f"OneBot 服务器任务已取消")
            finally:
                self._server_task = None
        logger.success(f"✅ OneBot 适配器已停止")

    def _register_bot_callbacks(self) -> None:
        """注册事件处理的回调函数"""

        @self._bot.on_message
        async def _on_message(event: dict[str, Any]) -> None:
            try:
                chat_event = await self._convert_event(event)
                if chat_event is None:
                    logger.debug(f"💬 OneBot 消息事件转换失败，已忽略 | msg_id={event.get('message_id')}")
                    return
                logger.debug(
                    f"💬 收到 OneBot 消息 | sender={chat_event.message.sender_id} | chat={chat_event.chat_id} | type={chat_event.chat_type.value}")
                await asyncio.gather(*(handler(chat_event) for handler in self._handlers), return_exceptions=True)
            except Exception as e:
                logger.error(f"❌ OneBot 消息处理异常: {e} | event={event}")

        @self._bot.on_websocket_connection
        async def _on_websocket_connection(event: dict[str, Any]) -> None:
            """OneBot WebSocket 连接成功时的回调"""
            self_id = event.get('self_id')
            self._ready = True
            logger.success(f"🟢 OneBot WebSocket 连接已建立 | self_id={self_id}")

        logger.info(f"📡 OneBot 事件回调已注册 (message, connection)")

    async def _convert_event(self, event: dict[str, Any]) -> ChatEvent | None:
        try:
            message = await self._build_message(event)
            if message is None:
                logger.warning(f"⚠️ OneBot 消息构建失败 | msg_id={event.get('message_id')}")
                return None

            message_type = str(event.get("message_type", "group"))
            chat_type = ChatType.GROUP if message_type == "group" else ChatType.PRIVATE
            chat_id = str(event.get("group_id") or event.get("user_id") or message.chat_id)
            self_id = str(event.get("self_id", ""))
            is_from_self = bool(self_id) and message.sender_id == self_id

            chat_event = ChatEvent(
                chat_type=chat_type,
                chat_id=chat_id,
                message=message,
                platform=self.name,
                is_from_self=is_from_self,
            )
            logger.debug(
                f"✓ OneBot 事件已转换 | msg_id={message.message_id} | sender={message.sender_id} | from_self={is_from_self}")
            return chat_event
        except Exception as e:
            logger.error(f"❌ OneBot 事件转换异常: {e}")
            return None

    async def _build_message(self, event: dict[str, Any], depth: int = 0) -> ChatMessage | None:
        try:
            raw_segments = event.get("message", [])
            if isinstance(raw_segments, str):
                raw_segments = [{"type": "text", "data": {"text": raw_segments}}]

            contents: list[MessageContent] = []
            reply_from: ChatMessage | None = None
            segment_count = 0

            for segment in raw_segments:
                segment_type = str(segment.get("type", "text"))
                data = segment.get("data", {}) or {}

                if segment_type == "text":
                    text = str(data.get("text", ""))
                    contents.append(MessageContent(type=ContentType.TEXT, text=text))
                    logger.debug(f"  ├ 文本片段: {text[:50]}...")
                    segment_count += 1
                elif segment_type == "image":
                    image_url = str(data.get("url") or data.get("file") or "")
                    contents.append(MessageContent(type=ContentType.IMAGE, image_url=image_url))
                    logger.debug(f"  ├ 图片片段: {image_url}")
                    segment_count += 1
                elif segment_type == "at":
                    mention_id = str(data.get("qq", ""))
                    contents.append(
                        MessageContent(
                            type=ContentType.MENTION,
                            mention_user=UserInfo(user_id=mention_id, display_name=f"@{mention_id}"),
                        )
                    )
                    logger.debug(f"  ├ 提及用户: {mention_id}")
                    segment_count += 1
                elif segment_type == "reply" and depth < 1:
                    reply_id = data.get("id")
                    if reply_id is not None:
                        try:
                            logger.debug(f"  ├ 正在获取回复消息: {reply_id}")
                            reply_payload = await self._bot.get_msg(message_id=int(reply_id))
                            if isinstance(reply_payload, dict):
                                reply_from = await self._build_message(reply_payload, depth=depth + 1)
                                if reply_from:
                                    logger.debug(f"  ├ 回复消息已获取: {reply_from.message_id}")
                        except (ValueError, KeyError, OneBotError, OSError) as e:
                            logger.warning(f"  ├ ⚠️ 获取回复消息失败 (msg_id={reply_id}): {e}")
                            reply_from = None
                else:
                    logger.debug(f"  ├ 未知片段类型: {segment_type}")

            sender = event.get("sender", {}) or {}
            sender_id = str(event.get("user_id") or sender.get("user_id") or "")
            sender_name = sender.get("nickname")
            chat_id = str(event.get("group_id") or event.get("user_id") or "")

            timestamp_raw = event.get("time")
            if isinstance(timestamp_raw, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            msg = ChatMessage(
                message_id=str(event.get("message_id", "")),
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=(str(sender_name) if sender_name else None),
                contents=contents,
                reply_from=reply_from,
                timestamp=timestamp,
            )

            logger.debug(
                f"✓ 消息已构建 | id={msg.message_id} | sender={sender_name or sender_id} | segments={segment_count}")
            return msg

        except Exception as e:
            logger.error(f"❌ OneBot 消息构建异常: {e} | event={event}")
            return None
