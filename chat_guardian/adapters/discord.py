from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import timezone
from typing import Any

import discord
from loguru import logger

from chat_guardian.adapters.base import Adapter, EventHandler
from chat_guardian.adapters.utils import download_image_bytes
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent, UserInfo

# Pattern that matches Discord user mentions: <@USER_ID> or <@!USER_ID>
_MENTION_RE = re.compile(r"<@!?(\d+)>")


@dataclass(slots=True)
class DiscordAdapterConfig:
    """Discord 适配器配置

    使用 Discord Bot Token 通过 Gateway WebSocket 接收消息。
    需要在 Discord Developer Portal 启用 MESSAGE CONTENT Intent 和 SERVER MEMBERS Intent。
    """

    bot_token: str
    guild_ids: list[int] = field(default_factory=list)
    """指定要监听的服务器 ID 列表。留空则监听 Bot 加入的所有服务器。"""


class _DiscordClient(discord.Client):
    """内部使用的 Discord 客户端，负责将事件转发给 DiscordAdapter。"""

    def __init__(self, adapter: DiscordAdapter, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._adapter = adapter

    async def on_ready(self) -> None:
        logger.success(
            f"✅ Discord Bot 已登录 | 用户名={self.user} | 加入服务器数={len(self.guilds)}"
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        guild_ids = self._adapter.config.guild_ids
        if guild_ids and (message.guild is None or message.guild.id not in guild_ids):
            return
        try:
            chat_event = await self._adapter._convert_message(message)
            if chat_event is None:
                return
            logger.debug(
                f"💬 收到 Discord 消息 | sender={chat_event.message.sender_id}"
                f" | chat={chat_event.chat_id} | type={chat_event.chat_type.value}"
            )
            await asyncio.gather(
                *(handler(chat_event) for handler in self._adapter._handlers),
                return_exceptions=True,
            )
        except Exception as exc:
            logger.error(f"❌ Discord 消息处理异常: {exc}")


class DiscordAdapter(Adapter):
    """Discord 适配器。

    通过 discord.py 库以 Bot 身份连接 Discord Gateway，实时接收服务器频道及私信消息。

    配置要求：
    - 在 Discord Developer Portal 创建 Bot，获取 Token。
    - 在 Bot 设置中启用 ``MESSAGE CONTENT INTENT`` 和 ``SERVER MEMBERS INTENT``。
    - 将 Bot 邀请到目标服务器，并授予读取消息的权限。
    """

    name = "discord"

    def __init__(self, config: DiscordAdapterConfig) -> None:
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._client: _DiscordClient | None = None
        self._client_task: asyncio.Task[None] | None = None
        logger.info(
            f"📦 Discord 适配器已初始化 | guild_filter={config.guild_ids or '(全部)'}"
        )

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
        logger.info(f"📝 事件处理器已注册 | 当前处理器数量={len(self._handlers)}")

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 Discord 适配器，连接 Discord Gateway"""
        if self._running:
            logger.warning("⚠️ Discord 适配器当前已运行，忽略重复启动请求")
            return
        logger.info("🚀 正在启动 Discord 适配器...")
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.messages = True
            intents.dm_messages = True
            self._client = _DiscordClient(adapter=self, intents=intents)

            # 先执行登录，以便在 token / intents 配置错误时同步失败
            await self._client.login(self.config.bot_token)

            # 登录成功后再标记为运行中，并启动网关连接任务
            self._running = True
            self._client_task = asyncio.create_task(self._client.connect())
            self._client_task.add_done_callback(self._on_client_task_done)

            logger.success("✅ Discord 适配器已启动（Gateway 模式）")
        except Exception as exc:
            logger.error(f"❌ Discord 适配器启动失败: {exc}")
            self._running = False
            # 确保在启动失败时不保留半初始化的 client
            self._client = None
            raise

    def _on_client_task_done(self, task: asyncio.Task[None]) -> None:
        """Discord 客户端网关任务结束时的回调，用于更新状态并记录异常。"""
        try:
            # 将在此处重新抛出任务中的异常（如果有）
            task.result()
        except asyncio.CancelledError:
            logger.info("🛑 Discord 网关连接任务已取消")
        except Exception as exc:
            logger.error(f"❌ Discord 网关连接任务异常结束: {exc}")
            self._running = False
        else:
            # 正常结束（通常意味着连接被关闭）
            logger.info("ℹ️ Discord 网关连接任务已结束")
            self._running = False
        finally:
            # 仅当当前保存的 task 与回调中的 task 相同时才清理引用
            if self._client_task is task:
                self._client_task = None

    async def stop(self) -> None:
        """停止 Discord 适配器，断开 Gateway 连接"""
        logger.info("🛑 正在停止 Discord 适配器...")
        self._running = False
        if self._client is not None:
            try:
                await self._client.close()
                logger.info("✅ Discord 客户端已关闭")
            except Exception as exc:
                logger.error(f"❌ Discord 客户端关闭时出错: {exc}")
            finally:
                self._client = None
        if self._client_task is not None:
            self._client_task.cancel()
            try:
                await self._client_task
            except (asyncio.CancelledError, Exception):
                pass
            finally:
                self._client_task = None
        logger.success("✅ Discord 适配器已停止")

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    async def _convert_message(self, message: discord.Message, depth: int = 0) -> ChatEvent | None:
        try:
            chat_message = await self._build_message(message, depth=depth)
            if chat_message is None:
                return None

            if message.guild is not None:
                chat_type = ChatType.GROUP
                chat_id = str(message.channel.id)
            else:
                chat_type = ChatType.PRIVATE
                chat_id = str(message.author.id)

            return ChatEvent(
                chat_type=chat_type,
                chat_id=chat_id,
                message=chat_message,
                platform=self.name,
            )
        except Exception as exc:
            logger.error(f"❌ Discord 事件转换异常: {exc}")
            return None

    async def _build_message(self, message: discord.Message, depth: int = 0) -> ChatMessage | None:
        try:
            contents: list[MessageContent] = []
            reply_from: ChatMessage | None = None

            # Build a mapping of user_id -> User for mentions in this message
            mention_map: dict[int, discord.User | discord.Member] = {
                u.id: u for u in message.mentions
            }

            # Parse text content with inline mentions split out
            text = message.content or ""
            if text:
                last_end = 0
                for m in _MENTION_RE.finditer(text):
                    pre = text[last_end:m.start()]
                    if pre:
                        contents.append(MessageContent(type=ContentType.TEXT, text=pre))
                    uid = int(m.group(1))
                    user = mention_map.get(uid)
                    display = user.display_name if user else f"@{uid}"
                    contents.append(
                        MessageContent(
                            type=ContentType.MENTION,
                            mention_user=UserInfo(user_id=str(uid), display_name=display),
                        )
                    )
                    logger.debug(f"  ├ 提及用户: {uid}")
                    last_end = m.end()
                remaining = text[last_end:]
                if remaining:
                    contents.append(MessageContent(type=ContentType.TEXT, text=remaining))

            # Image / file attachments
            for attachment in message.attachments:
                ct = attachment.content_type or ""
                if ct.startswith("image/"):
                    image_data = await download_image_bytes(attachment.url)
                    if image_data:
                        contents.append(
                            MessageContent(type=ContentType.IMAGE, image_data=image_data)
                        )
                        logger.debug(f"  ├ 图片附件已被提取数据")
                    else:
                        logger.debug(f"  ├ 图片附件提取失败: {attachment.url}")

            if not contents:
                logger.info(
                    f"  ├ 消息无可处理内容（贴纸/语音/视频等），已跳过"
                    f" | msg_id={message.id}"
                )
                return None

            # Handle reply
            if depth < 1 and message.reference is not None:
                ref = message.reference.resolved
                if isinstance(ref, discord.Message):
                    try:
                        reply_from = await self._build_message(ref, depth=depth + 1)
                    except Exception as exc:
                        logger.warning(f"  ├ ⚠️ 构建回复消息失败: {exc}")

            author = message.author
            sender_id = str(author.id)
            sender_name = getattr(author, "display_name", None) or author.name

            ts = message.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            # Use the same chat_id convention as events:
            # - DM: author.id (conversation with the user)
            # - Guild/channel: channel.id
            if isinstance(message.channel, discord.DMChannel):
                chat_id = str(author.id)
            else:
                chat_id = str(message.channel.id)

            chat_message = ChatMessage(
                message_id=str(message.id),
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                contents=contents,
                reply_from=reply_from,
                timestamp=ts,
            )
            logger.debug(
                f"✓ 消息已构建 | id={chat_message.message_id}"
                f" | sender={sender_name or sender_id} | segments={len(contents)}"
            )
            return chat_message
        except Exception as exc:
            logger.error(f"❌ Discord 消息构建异常: {exc} | msg_id={message.id}")
            return None
