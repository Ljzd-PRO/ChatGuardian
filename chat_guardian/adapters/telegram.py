from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger
from telegram import Chat, Message, MessageEntity, Update
from telegram.ext import Application, CallbackContext, MessageHandler, filters

from chat_guardian.adapters.base import Adapter, EventHandler
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent, UserInfo


@dataclass(slots=True)
class TelegramAdapterConfig:
    """Telegram 适配器配置

    使用 Telegram Bot API 长轮询方式接收消息。
    """

    bot_token: str
    polling_timeout: int = 10
    drop_pending_updates: bool = False


class TelegramAdapter(Adapter):
    name = "telegram"

    def __init__(self, config: TelegramAdapterConfig):
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._app: Application | None = None
        logger.info(
            f"📦 Telegram 适配器已初始化 | polling_timeout={config.polling_timeout}s"
        )

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
        logger.info(f"📝 事件处理器已注册 | 当前处理器数量={len(self._handlers)}")

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 Telegram 适配器，开启长轮询以接收消息"""
        if self._running:
            logger.warning("⚠️ Telegram 适配器当前已运行，忽略重复启动请求")
            return
        logger.info("🚀 正在启动 Telegram 适配器...")
        try:
            self._app = Application.builder().token(self.config.bot_token).build()
            self._app.add_handler(
                MessageHandler(filters.ALL, self._on_update)
            )
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(  # type: ignore[union-attr]
                timeout=self.config.polling_timeout,
                drop_pending_updates=self.config.drop_pending_updates,
            )
            self._running = True
            logger.success("✅ Telegram 适配器已启动（长轮询模式）")
        except Exception as e:
            logger.error(f"❌ Telegram 适配器启动失败: {e}")
            self._running = False
            raise

    async def stop(self) -> None:
        """停止 Telegram 适配器，关闭长轮询"""
        logger.info("🛑 正在停止 Telegram 适配器...")
        self._running = False
        if self._app is not None:
            try:
                if self._app.updater is not None and self._app.updater.running:
                    await self._app.updater.stop()
                if self._app.running:
                    await self._app.stop()
                await self._app.shutdown()
                logger.success("✅ Telegram 适配器已停止")
            except Exception as e:
                logger.error(f"❌ Telegram 适配器停止时出错: {e}")
            finally:
                self._app = None

    async def _on_update(self, update: Update, context: CallbackContext) -> None:
        """Telegram 消息更新回调"""
        if update.message is None and update.channel_post is None:
            return
        raw_message: Message = update.effective_message  # type: ignore[assignment]
        try:
            chat_event = await self._convert_message(raw_message)
            if chat_event is None:
                logger.debug(
                    f"💬 Telegram 消息转换失败，已忽略 | msg_id={raw_message.message_id}"
                )
                return
            logger.debug(
                f"💬 收到 Telegram 消息 | sender={chat_event.message.sender_id} "
                f"| chat={chat_event.chat_id} | type={chat_event.chat_type.value}"
            )
            await asyncio.gather(
                *(handler(chat_event) for handler in self._handlers),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error(f"❌ Telegram 消息处理异常: {e} | msg_id={raw_message.message_id}")

    async def _convert_message(self, message: Message, depth: int = 0) -> ChatEvent | None:
        """将 Telegram Message 转换为 ChatEvent"""
        try:
            chat_message = await self._build_message(message, depth=depth)
            if chat_message is None:
                return None

            chat_type_raw = message.chat.type
            if chat_type_raw in (Chat.GROUP, Chat.SUPERGROUP):
                chat_type = ChatType.GROUP
            else:
                chat_type = ChatType.PRIVATE

            chat_id = str(message.chat.id)
            bot_id = str(self._app.bot.id) if self._app is not None else ""
            is_from_self = bool(bot_id) and chat_message.sender_id == bot_id

            chat_event = ChatEvent(
                chat_type=chat_type,
                chat_id=chat_id,
                message=chat_message,
                platform=self.name,
                is_from_self=is_from_self,
            )
            logger.debug(
                f"✓ Telegram 事件已转换 | msg_id={chat_message.message_id} "
                f"| sender={chat_message.sender_id} | from_self={is_from_self}"
            )
            return chat_event
        except Exception as e:
            logger.error(f"❌ Telegram 事件转换异常: {e}")
            return None

    async def _build_message(self, message: Message, depth: int = 0) -> ChatMessage | None:
        """将 Telegram Message 构建为 ChatMessage"""
        try:
            contents: list[MessageContent] = []
            reply_from: ChatMessage | None = None

            # 处理文本内容
            text = message.text or message.caption or ""
            entities = list(message.entities or []) + list(message.caption_entities or [])

            if text:
                # Telegram entity offsets are counted in UTF-16 code units.
                # Encode to UTF-16-LE so that each code unit is exactly 2 bytes,
                # which makes slicing by entity.offset/entity.length correct even
                # for non-BMP characters (e.g., emoji represented as surrogate pairs).
                text_utf16 = text.encode("utf-16-le")
                last_end = 0
                sorted_mention_entities = sorted(
                    (e for e in entities if e.type in (MessageEntity.MENTION, MessageEntity.TEXT_MENTION)),
                    key=lambda e: e.offset,
                )
                for entity in sorted_mention_entities:
                    pre_text = text_utf16[last_end * 2: entity.offset * 2].decode("utf-16-le")
                    if pre_text:
                        contents.append(MessageContent(type=ContentType.TEXT, text=pre_text))
                    # 添加 mention 片段
                    if entity.type == MessageEntity.TEXT_MENTION and entity.user is not None:
                        user_id = str(entity.user.id)
                        display_name = entity.user.full_name or None
                        contents.append(
                            MessageContent(
                                type=ContentType.MENTION,
                                mention_user=UserInfo(user_id=user_id, display_name=display_name),
                            )
                        )
                        logger.debug(f"  ├ 提及用户 (text_mention): {user_id}")
                    elif entity.type == MessageEntity.MENTION:
                        # 使用 parse_entity() 以正确处理 UTF-16 偏移（包含 emoji 等非 BMP 字符）
                        mention_text = message.parse_entity(entity)
                        username = mention_text.lstrip("@")
                        contents.append(
                            MessageContent(
                                type=ContentType.MENTION,
                                mention_user=UserInfo(user_id=username, display_name=mention_text),
                            )
                        )
                        logger.debug(f"  ├ 提及用户 (mention): {username}")
                    last_end = entity.offset + entity.length

                # 剩余文本
                remaining = text_utf16[last_end * 2:].decode("utf-16-le")
                if remaining:
                    contents.append(MessageContent(type=ContentType.TEXT, text=remaining))

            # 处理图片
            if message.photo:
                largest_photo = message.photo[-1]
                image_url = largest_photo.file_id
                if self._app is not None:
                    try:
                        file = await self._app.bot.get_file(largest_photo.file_id)
                        if file.file_path:
                            image_url = file.file_path
                    except Exception as e:
                        logger.warning(f"  ├ ⚠️ 获取图片文件路径失败: {e}")
                contents.append(MessageContent(type=ContentType.IMAGE, image_url=image_url))
                logger.debug(f"  ├ 图片片段: {image_url}")

            # 无可处理内容（贴纸、语音、视频等），跳过此消息
            if not contents:
                logger.info(
                    f"  ├ 消息无可处理内容（贴纸/语音/视频等），已跳过 | msg_id={message.message_id}"
                )
                return None

            # 处理回复消息
            if message.reply_to_message is not None and depth < 1:
                logger.debug(f"  ├ 正在构建回复消息: {message.reply_to_message.message_id}")
                try:
                    replied_chat_message = await self._build_message(
                        message.reply_to_message, depth=depth + 1
                    )
                    if replied_chat_message is not None:
                        reply_from = replied_chat_message
                        logger.debug(f"  ├ 回复消息已构建: {reply_from.message_id}")
                except Exception as e:
                    logger.warning(f"  ├ ⚠️ 构建回复消息失败: {e}")

            from_user = message.from_user
            sender_id = str(from_user.id) if from_user is not None else str(message.chat.id)
            sender_name: str | None = None
            if from_user is not None:
                sender_name = from_user.full_name or from_user.username or None

            timestamp = message.date
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            elif timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            chat_message = ChatMessage(
                message_id=str(message.message_id),
                chat_id=str(message.chat.id),
                sender_id=sender_id,
                sender_name=sender_name,
                contents=contents,
                reply_from=reply_from,
                timestamp=timestamp,
            )
            logger.debug(
                f"✓ 消息已构建 | id={chat_message.message_id} "
                f"| sender={sender_name or sender_id} | segments={len(contents)}"
            )
            return chat_message
        except Exception as e:
            logger.error(f"❌ Telegram 消息构建异常: {e} | msg_id={message.message_id}")
            return None
