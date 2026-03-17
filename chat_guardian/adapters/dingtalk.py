from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from chat_guardian.adapters.base import Adapter, EventHandler
from chat_guardian.adapters.utils import download_image_bytes
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent, UserInfo


@dataclass(slots=True)
class DingTalkAdapterConfig:
    """DingTalk（钉钉）适配器配置

    使用钉钉开放平台的 Stream 模式接收 AI 助手 / 机器人消息，无需公网回调 URL。

    在钉钉开发者后台创建应用，启用"机器人"能力后即可获取 Client ID 与 Client Secret。

    参考文档：
    - https://open.dingtalk.com/document/orgapp/robot-overview
    - https://open.dingtalk.com/document/orgapp/stream
    """

    client_id: str
    """钉钉应用 Client ID（即 AppKey）。"""

    client_secret: str
    """钉钉应用 Client Secret（即 AppSecret）。"""


class DingTalkAdapter(Adapter):
    """DingTalk（钉钉）适配器。

    通过 ``dingtalk-stream`` 库以 Stream（WebSocket）模式接收钉钉机器人消息，
    无需配置公网回调 URL。

    配置步骤：
    1. 在钉钉开发者后台（https://open-dev.dingtalk.com）创建企业内部应用。
    2. 在应用中启用"机器人"能力，获取 Client ID 与 Client Secret。
    3. 在机器人设置中启用"Stream 模式"（无需填写回调地址）。
    4. 将机器人发布到指定部门或群聊。
    """

    name = "dingtalk"

    def __init__(self, config: DingTalkAdapterConfig) -> None:
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._stream_task: asyncio.Task[None] | None = None
        logger.info(
            f"📦 DingTalk 适配器已初始化 | client_id={config.client_id}"
        )

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
        logger.info(f"📝 事件处理器已注册 | 当前处理器数量={len(self._handlers)}")

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 DingTalk 适配器，通过 Stream 模式连接钉钉开放平台"""
        if self._running:
            logger.warning("⚠️ DingTalk 适配器当前已运行，忽略重复启动请求")
            return
        logger.info("🚀 正在启动 DingTalk 适配器（Stream 模式）...")
        try:
            import dingtalk_stream
            from dingtalk_stream.frames import AckMessage, Headers
            from dingtalk_stream.stream import CallbackHandler, CallbackMessage

            adapter_ref = self

            class _ChatbotHandler(CallbackHandler):
                """接收钉钉机器人会话消息的回调处理器"""

                async def process(self, callback: CallbackMessage):  # type: ignore[override]
                    try:
                        msg = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
                        chat_event = await adapter_ref._convert_message(msg)
                        if chat_event is not None:
                            logger.debug(
                                f"💬 收到 DingTalk 消息"
                                f" | sender={chat_event.message.sender_id}"
                                f" | chat={chat_event.chat_id}"
                                f" | type={chat_event.chat_type.value}"
                            )
                            await asyncio.gather(
                                *(handler(chat_event) for handler in adapter_ref._handlers),
                                return_exceptions=True,
                            )
                    except Exception as e:
                        logger.error(f"❌ DingTalk 消息处理异常: {e}")
                    return AckMessage.STATUS_OK, "ok"

            credential = dingtalk_stream.Credential(
                self.config.client_id,
                self.config.client_secret,
            )
            client = dingtalk_stream.DingTalkStreamClient(credential)
            client.register_callback_handler(
                dingtalk_stream.ChatbotMessage.TOPIC,
                _ChatbotHandler(),
            )

            self._running = True

            async def _run() -> None:
                try:
                    await client.start()
                except asyncio.CancelledError:
                    logger.debug("DingTalk Stream 任务已取消")
                except Exception as e:
                    logger.error(f"❌ DingTalk Stream 异常退出: {e}")
                finally:
                    adapter_ref._running = False

            self._stream_task = asyncio.create_task(_run())
            logger.success("✅ DingTalk 适配器已启动（Stream 模式）")
        except Exception as exc:
            logger.error(f"❌ DingTalk 适配器启动失败: {exc}")
            self._running = False
            raise

    async def stop(self) -> None:
        """停止 DingTalk 适配器，断开 Stream 连接"""
        logger.info("🛑 正在停止 DingTalk 适配器...")
        self._running = False
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
            finally:
                self._stream_task = None
        logger.success("✅ DingTalk 适配器已停止")

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    async def _convert_message(self, msg: object) -> ChatEvent | None:
        """将 dingtalk_stream.ChatbotMessage 转换为 ChatEvent"""
        try:
            import dingtalk_stream

            if not isinstance(msg, dingtalk_stream.ChatbotMessage):
                return None

            contents: list[MessageContent] = []
            msg_type: str = getattr(msg, "message_type", "") or ""

            if msg_type == "text":
                text_content = getattr(msg, "text", None)
                text = ""
                if text_content is not None:
                    text = str(getattr(text_content, "content", "") or "")
                if text:
                    # Separate @mentions from plain text
                    at_users: list[object] = getattr(msg, "at_users", []) or []

                    contents.append(MessageContent(type=ContentType.TEXT, text=text))

                    # Add MENTION segments for each @user
                    for u in at_users:
                        uid = str(
                            getattr(u, "staff_id", None)
                            or getattr(u, "dingtalk_id", None)
                            or ""
                        )
                        if uid:
                            contents.append(
                                MessageContent(
                                    type=ContentType.MENTION,
                                    mention_user=UserInfo(user_id=uid, display_name=f"@{uid}"),
                                )
                            )
                            logger.debug(f"  ├ 提及用户: {uid}")

            elif msg_type == "picture":
                image_content = getattr(msg, "image_content", None)
                if image_content is not None:
                    download_code = getattr(image_content, "download_code", "") or ""
                    if download_code:
                        image_data = await download_image_bytes(download_code)
                        if image_data:
                            contents.append(
                                MessageContent(type=ContentType.IMAGE, image_data=image_data)
                            )
                        else:
                            logger.debug("  ├ 提取图片失败，可能需要通过钉钉 API 获取下载链接")

            if not contents:
                logger.info(f"  ├ 消息无可处理内容（类型={msg_type}），已跳过")
                return None

            conversation_id = str(getattr(msg, "conversation_id", "") or "")
            conversation_type = str(getattr(msg, "conversation_type", "1") or "1")
            # conversation_type: "1" = private, "2" = group
            chat_type = ChatType.GROUP if conversation_type == "2" else ChatType.PRIVATE
            chat_id = conversation_id or str(getattr(msg, "sender_id", "") or "")

            sender_id = str(getattr(msg, "sender_id", "") or "")
            sender_name = str(getattr(msg, "sender_nick", "") or "") or None
            message_id = str(getattr(msg, "message_id", "") or "")

            create_at_ms = getattr(msg, "create_at", None)
            if isinstance(create_at_ms, (int, float)):
                timestamp = datetime.fromtimestamp(create_at_ms / 1000.0, tz=timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            chat_message = ChatMessage(
                message_id=message_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                contents=contents,
                reply_from=None,
                timestamp=timestamp,
            )

            return ChatEvent(
                chat_type=chat_type,
                chat_id=chat_id,
                message=chat_message,
                platform=self.name,
            )
        except Exception as exc:
            logger.error(f"❌ DingTalk 消息转换异常: {exc}")
            return None
