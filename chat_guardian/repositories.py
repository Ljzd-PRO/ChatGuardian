"""
内存存储实现（用于本地开发与测试）。

该模块提供简单的、非持久化的实现以便在开发阶段快速运行系统。生产环境应替换
为基于数据库的 Repository 实现。
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from chat_guardian.domain import ChatMessage, ChatType, DetectionResult, DetectionRule, Feedback, UserMemoryFact


class InMemoryChatHistoryStore:
    """将消息按 adapter/chat_type/chat_id 分类保存在内存中。

    Methods:
        enqueue_message: 将消息写入未处理队列。
        pop_pending_messages: 从未处理队列头部取消息。
        append_history_messages: 将消息写入滚动历史列表。
        recent_history_messages: 获取指定消息之前的最近若干条历史消息（按时间升序）。
    """

    def __init__(self, pending_queue_limit: int = 200, history_list_limit: int = 1000):
        self.pending_queue_limit = pending_queue_limit
        self.history_list_limit = history_list_limit
        self.pending: dict[str, dict[str, dict[str, deque[ChatMessage]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(deque))
        )
        self.history: dict[str, dict[str, dict[str, deque[ChatMessage]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(deque))
        )

    @staticmethod
    def _chat_type_key(chat_type: ChatType | str) -> str:
        return chat_type.value if isinstance(chat_type, ChatType) else str(chat_type)

    async def enqueue_message(self, platform: str, chat_type: ChatType | str, chat_id: str, message: ChatMessage) -> None:
        bucket = self.pending[platform][self._chat_type_key(chat_type)][chat_id]
        bucket.append(message)
        while len(bucket) > self.pending_queue_limit:
            bucket.popleft()

    async def pending_size(self, platform: str, chat_type: ChatType | str, chat_id: str) -> int:
        return len(self.pending[platform][self._chat_type_key(chat_type)][chat_id])

    async def oldest_pending_timestamp(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
    ) -> datetime | None:
        bucket = self.pending[platform][self._chat_type_key(chat_type)][chat_id]
        if not bucket:
            return None
        return bucket[0].timestamp

    async def pop_pending_messages(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
        max_count: int | None,
    ) -> list[ChatMessage]:
        bucket = self.pending[platform][self._chat_type_key(chat_type)][chat_id]
        if max_count is None:
            max_count = len(bucket)
        items: list[ChatMessage] = []
        while bucket and len(items) < max_count:
            items.append(bucket.popleft())
        return items

    async def append_history_message(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
        message: ChatMessage,
    ) -> None:
        bucket = self.history[platform][self._chat_type_key(chat_type)][chat_id]
        bucket.append(message)
        while len(bucket) > self.history_list_limit:
            bucket.popleft()

    async def append_history_messages(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
        messages: list[ChatMessage],
    ) -> None:
        for message in messages:
            await self.append_history_message(platform, chat_type, chat_id, message)

    async def recent_history_messages(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
        before_message_id: str | None,
        limit: int,
    ) -> list[ChatMessage]:
        bucket = list(self.history[platform][self._chat_type_key(chat_type)][chat_id])
        if before_message_id:
            try:
                idx = next(index for index, message in enumerate(bucket) if message.message_id == before_message_id)
                bucket = bucket[:idx]
            except StopIteration:
                pass
        return bucket[-limit:]

class InMemoryRuleRepository:
    """内存中的规则存储实现，支持上载/列举已启用规则。"""

    def __init__(self):
        self.rules: dict[str, DetectionRule] = {}

    async def list_enabled(self) -> list[DetectionRule]:
        return [rule for rule in self.rules.values() if rule.enabled]

    async def upsert(self, rule: DetectionRule) -> DetectionRule:
        self.rules[rule.rule_id] = rule
        return rule

    async def get(self, rule_id: str) -> DetectionRule | None:
        return self.rules.get(rule_id)


class InMemoryFeedbackRepository:
    """简单的反馈存储（按规则分组）。"""

    def __init__(self):
        self.feedback_by_rule: dict[str, list[Feedback]] = defaultdict(list)

    async def add(self, feedback: Feedback) -> None:
        self.feedback_by_rule[feedback.rule_id].append(feedback)

    async def list_by_rule(self, rule_id: str) -> list[Feedback]:
        return list(self.feedback_by_rule.get(rule_id, []))


class InMemoryMemoryRepository:
    """用户记忆事实的内存实现，用于存储 `UserMemoryFact`。"""

    def __init__(self):
        self.facts_by_user: dict[str, list[UserMemoryFact]] = defaultdict(list)

    async def add_fact(self, fact: UserMemoryFact) -> None:
        self.facts_by_user[fact.user_id].append(fact)

    async def list_user_facts(self, user_id: str) -> list[UserMemoryFact]:
        return list(self.facts_by_user.get(user_id, []))


class InMemoryDetectionResultRepository:
    """将检测结果追加到内存列表中（用于审计和测试）。"""

    def __init__(self):
        self.results: list[DetectionResult] = []

    async def add(self, result: DetectionResult) -> None:
        self.results.append(result)
