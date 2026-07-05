from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Any

from chat_guardian.domain import ChatMessage, DetectionResult
from chat_guardian.utils import guess_image_mime_type


def image_placeholder_id(value: str | bytes | None) -> str:
    """Return a short stable ID for image placeholders."""
    if value is None:
        return "UNKNOWN"
    raw = value if isinstance(value, bytes) else value.encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:5].upper()


def estimate_base64_size(value: str) -> int:
    """Estimate decoded byte length without allocating the decoded payload."""
    stripped = "".join(value.split())
    if not stripped:
        return 0
    padding = 2 if stripped.endswith("==") else 1 if stripped.endswith("=") else 0
    return max(0, (len(stripped) * 3 // 4) - padding)


def _sanitize_content_item(item: Any, *, persist_image_data: bool) -> Any:
    if getattr(item, "type", None) is None or getattr(item.type, "value", item.type) != "image":
        return item.model_copy(deep=True) if hasattr(item, "model_copy") else item

    image_data = getattr(item, "image_data", None)
    image_id = getattr(item, "image_id", None)
    image_mime_type = getattr(item, "image_mime_type", None)
    image_byte_size = getattr(item, "image_byte_size", None)

    if image_data:
        image_id = image_id or image_placeholder_id(image_data)
        image_mime_type = image_mime_type or guess_image_mime_type(image_data)
        image_byte_size = image_byte_size or len(image_data)

    stripped = not persist_image_data and (image_data is not None or bool(getattr(item, "image_data_stripped", False)))
    return item.model_copy(
        update={
            "image_data": image_data if persist_image_data else None,
            "image_id": image_id,
            "image_mime_type": image_mime_type,
            "image_byte_size": image_byte_size,
            "image_data_stripped": stripped,
        },
        deep=True,
    )


def sanitize_message_for_storage(message: ChatMessage, *, persist_image_data: bool = False) -> ChatMessage:
    """Copy a message into its persistence-safe shape."""
    contents = [
        _sanitize_content_item(item, persist_image_data=persist_image_data)
        for item in message.contents
    ]
    reply_from = (
        sanitize_message_for_storage(message.reply_from, persist_image_data=persist_image_data)
        if message.reply_from is not None
        else None
    )
    return message.model_copy(update={"contents": contents, "reply_from": reply_from}, deep=True)


def sanitize_messages_for_storage(messages: list[ChatMessage], *, persist_image_data: bool = False) -> list[ChatMessage]:
    return [sanitize_message_for_storage(message, persist_image_data=persist_image_data) for message in messages]


def limit_messages(messages: list[ChatMessage], max_count: int | None) -> list[ChatMessage]:
    if max_count is None or max_count <= 0 or len(messages) <= max_count:
        return list(messages)
    return list(messages[-max_count:])


def sanitize_detection_result_for_storage(
        result: DetectionResult,
        *,
        persist_image_data: bool = False,
        max_context_messages: int | None = None,
) -> DetectionResult:
    context = sanitize_messages_for_storage(
        limit_messages(result.context_messages, max_context_messages),
        persist_image_data=persist_image_data,
    )
    return result.model_copy(update={"context_messages": context}, deep=True)


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def strip_image_data_from_message_payload(payload: dict[str, Any]) -> bool:
    """Remove image_data from a serialized ChatMessage-like dict in place."""
    changed = False
    for item in payload.get("contents") or []:
        if not isinstance(item, dict) or item.get("type") != "image":
            continue
        raw = item.pop("image_data", None)
        if raw is not None:
            item.setdefault("image_id", image_placeholder_id(raw))
            if isinstance(raw, str):
                item.setdefault("image_byte_size", estimate_base64_size(raw))
            item["image_data_stripped"] = True
            changed = True
        elif item.get("image_data_stripped"):
            item.setdefault("image_id", item.get("image_id") or "UNKNOWN")

    reply = payload.get("reply_from")
    if isinstance(reply, dict):
        changed = strip_image_data_from_message_payload(reply) or changed
    return changed


def strip_image_data_from_detection_payload(payload: dict[str, Any]) -> bool:
    changed = False
    for message in payload.get("context_messages") or []:
        if isinstance(message, dict):
            changed = strip_image_data_from_message_payload(message) or changed
    return changed


def json_base64_contains_image_data(raw_json: str) -> bool:
    return '"image_data"' in raw_json


def decode_small_base64(value: str, max_bytes: int = 1024 * 1024) -> bytes | None:
    """Best-effort bounded decode for maintenance scripts that want exact MIME."""
    if estimate_base64_size(value) > max_bytes:
        return None
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None
