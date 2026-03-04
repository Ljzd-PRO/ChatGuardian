"""
内存存储实现（用于本地开发与测试）。

该模块提供简单的、非持久化的实现以便在开发阶段快速运行系统。生产环境应替换
为基于数据库的 Repository 实现。
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime

from chat_guardian.domain import ChatMessage, ChatType, DetectionResult, DetectionRule, Feedback, UserMemoryFact

class ChatHistoryStore:
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
        """将新消息追加到未处理队列（按 platform/chat_type/chat_id 分类）。

        如果队列超过 `pending_queue_limit`，会从最旧处丢弃消息以保证容量上限。

        Args:
            platform: 消息来源平台标识（如 onebot）。
            chat_type: 聊天类型（'group' 或 'private'）。
            chat_id: 会话/群组 ID。
            message: 要入队的 `ChatMessage` 实例。
        """
        bucket = self.pending[platform][self._chat_type_key(chat_type)][chat_id]
        bucket.append(message)
        while len(bucket) > self.pending_queue_limit:
            bucket.popleft()

    async def pending_size(self, platform: str, chat_type: ChatType | str, chat_id: str) -> int:
        """返回指定队列当前的未处理消息数量。"""
        return len(self.pending[platform][self._chat_type_key(chat_type)][chat_id])

    async def oldest_pending_timestamp(
        self,
        platform: str,
        chat_type: ChatType | str,
        chat_id: str,
    ) -> datetime | None:
        """返回队列中最早一条未处理消息的时间戳，如果队列为空返回 None。"""
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
        """从未处理队列头部弹出最多 `max_count` 条消息并返回。

        如果 `max_count` 为 None，则弹出全部消息。
        返回值为按时间顺序（从旧到新）的消息列表。
        """
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
        """将单条消息追加到已处理滚动历史中，超过上限会从旧端丢弃。"""
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
        """将多条消息按顺序追加到已处理滚动历史中。"""
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
        """获取指定会话在 `before_message_id` 之前的最近若干条历史消息。

        Args:
            platform: 平台标识。
            chat_type: 聊天类型。
            chat_id: 会话 ID。
            before_message_id: 以该消息为分界（不包含该消息），如果为 None 则取最新。
            limit: 返回的最大条数。
        """
        bucket = list(self.history[platform][self._chat_type_key(chat_type)][chat_id])
        if before_message_id:
            try:
                idx = next(index for index, message in enumerate(bucket) if message.message_id == before_message_id)
                bucket = bucket[:idx]
            except StopIteration:
                pass
        return bucket[-limit:]

class RuleRepository:
    """内存中的规则存储实现，支持上载/列举已启用规则。"""

    def __init__(self):
        self.rules: dict[str, DetectionRule] = {}

    async def list_enabled(self) -> list[DetectionRule]:
        return [rule for rule in self.rules.values() if rule.enabled]

    async def list_all(self) -> list[DetectionRule]:
        return list(self.rules.values())

    async def upsert(self, rule: DetectionRule) -> DetectionRule:
        self.rules[rule.rule_id] = rule
        return rule

    async def get(self, rule_id: str) -> DetectionRule | None:
        return self.rules.get(rule_id)

    async def delete(self, rule_id: str) -> bool:
        if rule_id not in self.rules:
            return False
        del self.rules[rule_id]
        return True


class FeedbackRepository:
    """简单的反馈存储（按规则分组）。"""

    def __init__(self):
        self.feedback_by_rule: dict[str, list[Feedback]] = defaultdict(list)

    async def add(self, feedback: Feedback) -> None:
        self.feedback_by_rule[feedback.rule_id].append(feedback)

    async def list_by_rule(self, rule_id: str) -> list[Feedback]:
        return list(self.feedback_by_rule.get(rule_id, []))


class MemoryRepository:
    """用户记忆事实的内存实现，用于存储 `UserMemoryFact`。"""

    def __init__(self):
        self.facts_by_user: dict[str, list[UserMemoryFact]] = defaultdict(list)

    async def add_fact(self, fact: UserMemoryFact) -> None:
        self.facts_by_user[fact.user_id].append(fact)

    async def list_user_facts(self, user_id: str) -> list[UserMemoryFact]:
        return list(self.facts_by_user.get(user_id, []))


class DetectionResultRepository:
    """按规则索引检测结果，并维护最近触发结果的 O(1) 查询结构。"""

    def __init__(self):
        self.results: list[DetectionResult] = []
        self.results_by_rule: dict[str, list[DetectionResult]] = defaultdict(list)
        self.last_triggered_by_rule: dict[str, DetectionResult] = {}
        self.last_triggered_message_ids: dict[str, set[str]] = {}

    async def add(self, result: DetectionResult) -> None:
        """新增一条检测结果，并同步更新按规则索引。"""
        self.results.append(result)
        self.results_by_rule[result.rule_id].append(result)

        if result.decision.triggered and not result.trigger_suppressed:
            self.last_triggered_by_rule[result.rule_id] = result
            self.last_triggered_message_ids[result.rule_id] = {message.message_id for message in result.context_messages}

    async def list_by_rule(self, rule_id: str) -> list[DetectionResult]:
        """返回指定规则的全部检测结果。"""
        return list(self.results_by_rule.get(rule_id, []))

    async def contains_message_in_last_triggered(self, rule_id: str, message_id: str) -> bool:
        """O(1) 判断某消息是否在该规则最近一次“已触发且未抑制”的结果里。"""
        return message_id in self.last_triggered_message_ids.get(rule_id, set())

    async def merge_into_last_triggered(self, rule_id: str, new_context_messages: list[ChatMessage]) -> DetectionResult | None:
        """将新增上下文消息并入该规则最近一次触发结果，避免重复触发。"""
        last = self.last_triggered_by_rule.get(rule_id)
        if last is None:
            return None

        known_ids = self.last_triggered_message_ids.setdefault(rule_id, set())
        merged = list(last.context_messages)
        for message in new_context_messages:
            if message.message_id in known_ids:
                continue
            merged.append(message)
            known_ids.add(message.message_id)

        last.context_messages = merged
        return last
