from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from chat_guardian.adapters.base import Adapter, EventHandler
from chat_guardian.adapters.utils import download_image_bytes
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent


@dataclass(slots=True)
class WeChatAdapterConfig:
    """WeChat Work（企业微信）适配器配置

    企业微信应用需要在管理后台配置"接收消息"回调 URL，指向本适配器启动的 HTTP 服务。

    回调 URL 格式（示例）：
        http://<your_public_host>:<port>/wechat

    验证 Token、EncodingAESKey 及 CorpID 均在企业微信管理后台获取。
    """

    token: str
    """企业微信应用回调配置中的 Token，用于签名验证。"""

    encoding_aes_key: str
    """企业微信应用回调配置中的 EncodingAESKey，用于消息体加解密（43 个字符）。"""

    corp_id: str
    """企业微信的 CorpID（企业 ID）。"""

    host: str = "0.0.0.0"
    """HTTP 回调服务器监听地址。"""

    port: int = 8082
    """HTTP 回调服务器监听端口。"""


class WeChatAdapter(Adapter):
    """WeChat Work（企业微信）适配器。

    通过 aiohttp HTTP 服务器接收企业微信应用回调，解密后将消息转换为 ChatEvent。

    需要：
    - 在企业微信管理后台创建自建应用并配置"接收消息"回调 URL。
    - 将本服务的 ``<host>:<port>/wechat`` 填写为回调地址。
    - 依赖 ``wechatpy`` 和 ``aiohttp`` 库。
    """

    name = "wechat"

    def __init__(self, config: WeChatAdapterConfig) -> None:
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._runner: object | None = None  # aiohttp.web.AppRunner
        logger.info(
            f"📦 WeChat Work 适配器已初始化"
            f" | host={config.host} | port={config.port}"
            f" | corp_id={config.corp_id}"
        )

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
        logger.info(f"📝 事件处理器已注册 | 当前处理器数量={len(self._handlers)}")

    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 WeChat Work 适配器，开启 HTTP 回调服务器"""
        if self._running:
            logger.warning("⚠️ WeChat Work 适配器当前已运行，忽略重复启动请求")
            return
        try:
            from aiohttp import web
            from wechatpy.enterprise.crypto import WeChatCrypto
            from wechatpy.enterprise.parser import parse_message

            crypto = WeChatCrypto(
                self.config.token,
                self.config.encoding_aes_key,
                self.config.corp_id,
            )

            async def handle_verify(request: web.Request) -> web.Response:
                """处理企业微信回调 URL 验证（GET 请求）"""
                try:
                    signature = request.rel_url.query.get("msg_signature", "")
                    timestamp = request.rel_url.query.get("timestamp", "")
                    nonce = request.rel_url.query.get("nonce", "")
                    echostr = request.rel_url.query.get("echostr", "")
                    plain = crypto.check_signature(signature, timestamp, nonce, echostr)
                    logger.info("✅ WeChat Work 回调 URL 验证成功")
                    return web.Response(text=plain)
                except Exception as exc:
                    logger.error(f"❌ WeChat Work 回调 URL 验证失败: {exc}")
                    return web.Response(status=403, text="forbidden")

            async def handle_message(request: web.Request) -> web.Response:
                """处理企业微信推送的加密消息（POST 请求）"""
                try:
                    signature = request.rel_url.query.get("msg_signature", "")
                    timestamp = request.rel_url.query.get("timestamp", "")
                    nonce = request.rel_url.query.get("nonce", "")
                    body = await request.read()
                    xml = crypto.decrypt_message(body.decode("utf-8"), signature, timestamp, nonce)
                    msg = parse_message(xml)
                    chat_event = await self._convert_message(msg)
                    if chat_event is not None:
                        logger.debug(
                            f"💬 收到 WeChat Work 消息"
                            f" | sender={chat_event.message.sender_id}"
                            f" | chat={chat_event.chat_id}"
                        )
                        await asyncio.gather(
                            *(handler(chat_event) for handler in self._handlers),
                            return_exceptions=True,
                        )
                except Exception as exc:
                    logger.error(f"❌ WeChat Work 消息处理异常: {exc}")
                return web.Response(text="success")

            app = web.Application()
            app.router.add_get("/wechat", handle_verify)
            app.router.add_post("/wechat", handle_message)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, self.config.host, self.config.port)
            await site.start()
            self._runner = runner
            self._running = True
            logger.success(
                f"✅ WeChat Work HTTP 回调服务器已启动"
                f" | 监听地址: http://{self.config.host}:{self.config.port}/wechat"
            )
        except Exception as exc:
            logger.error(f"❌ WeChat Work 适配器启动失败: {exc}")
            self._running = False
            raise

    async def stop(self) -> None:
        """停止 WeChat Work 适配器，关闭 HTTP 服务器"""
        logger.info("🛑 正在停止 WeChat Work 适配器...")
        self._running = False
        if self._runner is not None:
            try:
                from aiohttp import web

                runner: web.AppRunner = self._runner  # type: ignore[assignment]
                await runner.cleanup()
                logger.success("✅ WeChat Work HTTP 服务器已停止")
            except Exception as exc:
                logger.error(f"❌ WeChat Work 适配器停止时出错: {exc}")
            finally:
                self._runner = None
        logger.success("✅ WeChat Work 适配器已停止")

    # ------------------------------------------------------------------
    # Message conversion
    # ------------------------------------------------------------------

    async def _convert_message(self, msg: object) -> ChatEvent | None:
        """将 wechatpy 企业微信消息对象转换为 ChatEvent"""
        try:
            msg_type: str = getattr(msg, "type", "unknown")

            # Only handle text and image messages; skip events/voice/video
            if msg_type not in ("text", "image"):
                logger.debug(f"  ├ 忽略非文本/图片消息类型: {msg_type}")
                return None

            contents: list[MessageContent] = []

            if msg_type == "text":
                text = str(getattr(msg, "content", "") or "")
                if text:
                    contents.append(MessageContent(type=ContentType.TEXT, text=text))
            elif msg_type == "image":
                pic_url = str(getattr(msg, "image", "") or "")
                media_id = str(getattr(msg, "media_id", "") or "")
                image_url = pic_url or media_id
                if image_url:
                    image_data = await download_image_bytes(image_url)
                    if image_data:
                        contents.append(MessageContent(type=ContentType.IMAGE, image_data=image_data))
                        logger.debug("  ├ 图片片段已被提取数据")
                    else:
                        logger.debug(f"  ├ 提取图片数据失败: {image_url}")

            if not contents:
                return None

            msg_id = str(getattr(msg, "id", "") or "")
            sender_id = str(getattr(msg, "source", "") or "")
            chat_id = sender_id  # 企业微信单聊以发送者 OpenID 作为 chat_id

            # 企业微信应用消息均为一对一或应用通知，视为私聊
            chat_type = ChatType.PRIVATE

            create_time = getattr(msg, "create_time", None)
            if isinstance(create_time, datetime):
                timestamp = create_time
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                timestamp = datetime.now(timezone.utc)

            chat_message = ChatMessage(
                message_id=msg_id,
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=None,
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
            logger.error(f"❌ WeChat Work 消息转换异常: {exc}")
            return None
