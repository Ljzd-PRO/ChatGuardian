from __future__ import annotations

from chat_guardian.domain import ChatEvent, ChatMessage
from chat_guardian.repositories import ChatHistoryStore
from chat_guardian.settings import settings


class ContextWindowService:
    """上下文窗口服务，用于拉取事件前的若干条消息并与当前消息组合成上下文。"""

    def __init__(self, store: ChatHistoryStore):
        self.store = store

    async def build_context(self, event: ChatEvent) -> list[ChatMessage]:
        previous = await self.store.recent_history_messages(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            before_message_id=event.message.message_id,
            limit=settings.context_message_limit,
        )
        return [*previous, event.message]
