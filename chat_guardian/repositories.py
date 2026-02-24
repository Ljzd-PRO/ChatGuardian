"""
内存存储实现（用于本地开发与测试）。

该模块提供简单的、非持久化的实现以便在开发阶段快速运行系统。生产环境应替换
为基于数据库的 Repository 实现。
"""

from __future__ import annotations

from collections import defaultdict, deque

from chat_guardian.domain import ChatMessage, DetectionResult, DetectionRule, Feedback, UserMemoryFact


class InMemoryChatHistoryStore:
    """将消息按会话保存在内存的环形队列中。

    Methods:
        append_message: 将消息追加到会话历史。
        recent_messages: 获取指定消息之前的最近若干条消息（按时间升序）。
    """

    def __init__(self, per_chat_limit: int = 1000):
        self.per_chat_limit = per_chat_limit
        self.data: dict[str, deque[ChatMessage]] = defaultdict(deque)

    async def append_message(self, message: ChatMessage) -> None:
        bucket = self.data[message.chat_id]
        bucket.append(message)
        while len(bucket) > self.per_chat_limit:
            bucket.popleft()

    async def recent_messages(self, chat_id: str, before_message_id: str | None, limit: int) -> list[ChatMessage]:
        bucket = list(self.data.get(chat_id, []))
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
