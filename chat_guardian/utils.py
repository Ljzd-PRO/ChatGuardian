from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger

from chat_guardian.adapters.utils import compress_image
from chat_guardian.domain import ChatMessage
from chat_guardian.settings import settings


def extract_json_payload(raw_text: str) -> dict:
    """从模型输出文本中提取 JSON 对象。"""
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*}", raw_text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def resolve_llm_display_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.llm_display_timezone)
    except ZoneInfoNotFoundError:
        logger.warning(f"⚠️ 无效时区配置: {settings.llm_display_timezone}，回退为 UTC")
        return ZoneInfo("UTC")


def format_human_timestamp(value: datetime, tz: ZoneInfo) -> str:
    normalized = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
    localized = normalized.astimezone(tz)
    return localized.strftime("%Y-%m-%d %H:%M:%S %Z")


def messages_to_markdown(messages: list[ChatMessage]) -> str:
    tz = resolve_llm_display_timezone()
    lines: list[str] = []
    for message in messages:
        display_name = message.sender_name or "无名称"
        human_time = format_human_timestamp(message.timestamp, tz)
        lines.append("- [{time}] ({name}|{sender_id}): {message}".format(
            time=human_time,
            name=display_name,
            sender_id=message.sender_id,
            message=str(message),
        ))
    return "\n".join(lines)


def guess_image_mime_type(image_bytes: bytes) -> str:
    """根据常见文件头猜测图片 MIME，无法识别时回退为 image/jpeg。"""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes.startswith(b"BM"):
        return "image/bmp"
    return "image/jpeg"


async def build_image_content_blocks(messages: list[ChatMessage]) -> tuple[list[dict[str, Any]], int]:
    """从消息列表中提取图片并转换为可通过 LLM 的 base64 image blocks。"""
    if not settings.enable_image_parsing:
        return [], 0

    image_blocks: list[dict[str, Any]] = []

    for message in messages:
        for item in message.contents:
            if item.type.value != "image" or not item.image_data:
                continue

            if len(image_blocks) >= settings.max_images:
                break

            image_bytes = item.image_data

            if settings.enable_image_compression:
                compressed_bytes = compress_image(
                    image_bytes,
                    max_width=settings.image_compression_max_width,
                    max_height=settings.image_compression_max_height,
                    quality=85,
                )
                if compressed_bytes is not None:
                    image_bytes = compressed_bytes

            encoded = base64.b64encode(image_bytes).decode("ascii")
            mime_type = guess_image_mime_type(image_bytes)

            image_blocks.append(
                {
                    "type": "image",
                    "id": item.generate_short_id(image_bytes),
                    "base64": encoded,
                    "mime_type": mime_type,
                }
            )

        if len(image_blocks) >= settings.max_images:
            break

    return image_blocks, len(image_blocks)


async def build_rule_detection_content_blocks(
    messages: list[ChatMessage],
    rules_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, int]:
    """构建规则检测用的多模态 HumanMessage content blocks。"""
    messages_payload = messages_to_markdown(messages)
    text_payload = """
## 聊天消息
{messages_payload}

## 规则列表
{rules_payload}
""".format(
        messages_payload=messages_payload,
        rules_payload=json.dumps(rules_payload, ensure_ascii=False, indent=4),
    )

    image_blocks, image_block_count = await build_image_content_blocks(messages)
    content_blocks: list[dict[str, Any]] = [{"type": "text", "text": text_payload}, *image_blocks]

    return content_blocks, text_payload, image_block_count
