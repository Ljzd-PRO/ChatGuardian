"""
核心服务与基础实现。

此模块包含：
- 服务接口（Repository、LLM 客户端等）的协议定义；
- 开发阶段可用的内置实现（Mock LLM、内存存储、Email 通知、外部 Hook 派发器）；
- 检测引擎、上下文窗口、规则生成、记忆写入与建议服务。

所有对外依赖（如真实 LLM、消息平台、持久化）均通过协议抽象，便于替换。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

import httpx
from aiosmtplib import SMTP

from chat_guardian.domain import (
    ChatEvent,
    ChatMessage,
    ChatType,
    DetectionResult,
    DetectionRule,
    Feedback,
    ParticipantConstraint,
    RuleDecision,
    RuleParameterSpec,
    SessionMatchMode,
    SessionTarget,
    UserMemoryFact,
)
from chat_guardian.settings import settings


class ChatHistoryStore(Protocol):
    """消息缓冲与历史存储协议。

    存储按 adapter/chat_type/chat_id 分类，支持：
    - 未处理消息队列（pending）
    - 已处理滚动历史（history）
    """

    async def enqueue_message(self, platform: str, chat_type: str, chat_id: str, message: ChatMessage) -> None: ...

    async def pending_size(self, platform: str, chat_type: str, chat_id: str) -> int: ...

    async def pop_pending_messages(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        max_count: int | None,
    ) -> list[ChatMessage]: ...

    async def append_history_messages(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        messages: list[ChatMessage],
    ) -> None: ...

    async def recent_history_messages(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        before_message_id: str | None,
        limit: int,
    ) -> list[ChatMessage]: ...


class RuleRepository(Protocol):
    """规则仓储协议，支持列举/上载/查询规则。"""

    async def list_enabled(self) -> list[DetectionRule]: ...

    async def upsert(self, rule: DetectionRule) -> DetectionRule: ...

    async def get(self, rule_id: str) -> DetectionRule | None: ...


class FeedbackRepository(Protocol):
    """用户反馈仓储协议。"""

    async def add(self, feedback: Feedback) -> None: ...

    async def list_by_rule(self, rule_id: str) -> list[Feedback]: ...


class MemoryRepository(Protocol):
    """用户记忆事实仓储协议。"""

    async def add_fact(self, fact: UserMemoryFact) -> None: ...

    async def list_user_facts(self, user_id: str) -> list[UserMemoryFact]: ...


class DetectionResultRepository(Protocol):
    """检测结果持久化（或临时记录）接口。

    在 MVP 中可以是内存实现，生产中应该写入数据库或审计系统。
    """

    async def add(self, result: DetectionResult) -> None: ...


class LLMClient(Protocol):
    """与 LLM 提供者交互的抽象接口。

    - `evaluate`: 对一批消息与一组规则进行判断，返回每个规则的 `RuleDecision`。
    - `extract_self_participation`: 当消息来自用户自身时，提取用户参与相关的记忆事实。
    """

    async def evaluate(self, messages: list[ChatMessage], rules: list[DetectionRule]) -> list[RuleDecision]: ...

    async def extract_self_participation(self, event: ChatEvent, context: list[ChatMessage]) -> list[UserMemoryFact]: ...


class MockLLMClient:
    """用于本地开发的简易 LLM 客户端实现（确定性）。

    该实现通过简单的关键词匹配来估算置信度，旨在支持离线开发与单元测试，
    不应在生产环境中替代真实模型。
    """

    async def evaluate(self, messages: list[ChatMessage], rules: list[DetectionRule]) -> list[RuleDecision]:
        text_blob = "\n".join(message.extract_plain_text() for message in messages).lower()
        results: list[RuleDecision] = []
        for rule in rules:
            match_score = 0.0
            for hint in rule.topic_hints:
                if hint.lower() in text_blob:
                    match_score += 1.0
            denom = max(1, len(rule.topic_hints))
            confidence = min(1.0, match_score / denom)
            triggered = confidence >= rule.score_threshold if rule.topic_hints else False
            extracted_params = {
                param.key: self._extract_param_value(text_blob, param)
                for param in rule.parameters
                if triggered
            }
            results.append(
                RuleDecision(
                    rule_id=rule.rule_id,
                    triggered=triggered,
                    confidence=confidence,
                    reason="Matched topic hints" if triggered else "No sufficient topic overlap",
                    extracted_params=extracted_params,
                )
            )
        return results

    async def extract_self_participation(self, event: ChatEvent, context: list[ChatMessage]) -> list[UserMemoryFact]:
        text = " ".join([message.extract_plain_text() for message in context] + [event.message.extract_plain_text()])
        tokens = [token for token in re.split(r"\W+", text) if len(token) >= 3]
        if not tokens:
            return []
        top_topic = max(set(tokens), key=tokens.count)
        counterparts = sorted({message.sender_id for message in context if message.sender_id != event.message.sender_id})
        fact = UserMemoryFact(
            user_id=event.message.sender_id,
            chat_id=event.chat_id,
            topic=top_topic,
            counterpart_user_ids=counterparts[:5],
            confidence=0.4,
            captured_at=datetime.utcnow(),
        )
        return [fact]

    @staticmethod
    def _extract_param_value(text_blob: str, spec: RuleParameterSpec) -> str:
        if not text_blob:
            return "unknown"
        if spec.key.lower() in text_blob:
            return spec.key
        words = [word for word in re.split(r"\W+", text_blob) if word]
        return words[0] if words else "unknown"


class SessionMatcher:
    """会话匹配器，支持不同匹配模式（Exact / Fuzzy）。"""

    @staticmethod
    def match(target: SessionTarget, event: ChatEvent) -> bool:
        if target.mode == SessionMatchMode.EXACT:
            return target.query == event.chat_id
        normalized_query = target.query.lower().strip()
        return normalized_query in event.chat_id.lower()


class ContextWindowService:
    """上下文窗口服务，用于拉取事件前的若干条消息并与当前消息组合成上下文。

    主要用于在调用 LLM 进行判断时提供必要的上下文信息。
    """

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


@dataclass(slots=True)
class EngineOutput:
    result: DetectionResult
    notified_count: int


@dataclass(slots=True)
class ChannelRuntimeState:
    """单会话运行时状态（用于触发策略控制）。"""

    last_detection_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cooldown_task: asyncio.Task[None] | None = None
    timeout_task: asyncio.Task[None] | None = None


class DetectionEngine:
    """核心检测引擎。

    该引擎负责：
    - 从规则仓库中筛选出适用规则；
    - 调用上下文服务获取消息上下文；
    - 将规则按批次并行提交给 LLMClient 进行判断；
    - 将检测结果写入结果仓储并触发通知/外部 Hook。
    """
    def __init__(
        self,
        rules: RuleRepository,
        context_service: ContextWindowService,
        llm_client: LLMClient,
        result_repository: DetectionResultRepository,
        notifiers: list["Notifier"],
        hook_dispatcher: "ExternalHookDispatcher",
    ):
        self.rules = rules
        self.context_service = context_service
        self.llm_client = llm_client
        self.result_repository = result_repository
        self.notifiers = notifiers
        self.hook_dispatcher = hook_dispatcher
        self._runtime_states: dict[tuple[str, str, str], ChannelRuntimeState] = {}

    @staticmethod
    def _channel_key(platform: str, chat_type: str, chat_id: str) -> tuple[str, str, str]:
        return (platform, chat_type, chat_id)

    def _state_of(self, platform: str, chat_type: str, chat_id: str) -> ChannelRuntimeState:
        key = self._channel_key(platform, chat_type, chat_id)
        if key not in self._runtime_states:
            self._runtime_states[key] = ChannelRuntimeState()
        return self._runtime_states[key]

    async def ingest_event(self, event: ChatEvent) -> EngineOutput | None:
        """接收新消息事件并按策略决定是否触发检测。

        流程：
        1) 先入 pending 队列；
        2) 满足最小新消息数时尝试触发；
        3) 若不足最小数量，依赖等待超时强制触发。
        """
        if settings.detection_min_new_messages > 1 and settings.detection_wait_timeout_seconds <= 0:
            raise ValueError("When detection_min_new_messages > 1, detection_wait_timeout_seconds must be > 0")

        await self.context_service.store.enqueue_message(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            message=event.message,
        )

        state = self._state_of(event.platform, event.chat_type.value, event.chat_id)
        await self._ensure_timeout_task(event.platform, event.chat_type.value, event.chat_id, state)

        min_new = max(1, settings.detection_min_new_messages)
        pending = await self.context_service.store.pending_size(event.platform, event.chat_type.value, event.chat_id)
        if pending < min_new:
            return None

        return await self._try_trigger(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            force_all_pending=False,
        )

    async def _process_event_with_context(self, event: ChatEvent, context_messages: list[ChatMessage]) -> EngineOutput:
        active_rules = [rule for rule in await self.rules.list_enabled() if SessionMatcher.match(rule.target_session, event)]
        decisions = await self._evaluate_rules_in_parallel_batches(context_messages, active_rules)
        result = DetectionResult(
            event_id=f"evt-{event.message.message_id}",
            chat_id=event.chat_id,
            message_id=event.message.message_id,
            decisions=decisions,
            generated_at=datetime.utcnow(),
        )
        await self.result_repository.add(result)

        triggered = [decision for decision in decisions if decision.triggered]
        notify_count = 0
        for decision in triggered:
            for notifier in self.notifiers:
                sent = await notifier.notify(event, decision, context_messages)
                notify_count += 1 if sent else 0
            await self.hook_dispatcher.dispatch(event, decision, context_messages)

        return EngineOutput(result=result, notified_count=notify_count)

    async def _try_trigger(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        force_all_pending: bool,
    ) -> EngineOutput | None:
        state = self._state_of(platform, chat_type, chat_id)
        async with state.lock:
            now = datetime.utcnow()
            cooldown = max(0.0, settings.detection_cooldown_seconds)
            if state.last_detection_at and cooldown > 0:
                due = state.last_detection_at + timedelta(seconds=cooldown)
                if now < due:
                    await self._ensure_cooldown_task(platform, chat_type, chat_id, state, (due - now).total_seconds())
                    return None

            output = await self._drain_pending_and_detect(platform, chat_type, chat_id, force_all_pending)
            if output is None:
                return None

            state.last_detection_at = datetime.utcnow()

            pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
            min_new = max(1, settings.detection_min_new_messages)
            if pending >= min_new and cooldown > 0:
                await self._ensure_cooldown_task(platform, chat_type, chat_id, state, cooldown)
            await self._ensure_timeout_task(platform, chat_type, chat_id, state)
            return output

    async def _drain_pending_and_detect(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        force_all_pending: bool,
    ) -> EngineOutput | None:
        min_new = max(1, settings.detection_min_new_messages)
        max_count = None if force_all_pending else min_new

        pending_messages = await self.context_service.store.pop_pending_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            max_count=max_count,
        )
        if not pending_messages:
            return None

        await self.context_service.store.append_history_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            messages=pending_messages,
        )

        anchor_message = pending_messages[-1]
        event = ChatEvent(
            chat_type=ChatType(chat_type),
            chat_id=chat_id,
            message=anchor_message,
            platform=platform,
            is_from_self=False,
        )
        context_messages = await self.context_service.build_context(event)
        return await self._process_event_with_context(event, context_messages)

    async def _ensure_cooldown_task(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        state: ChannelRuntimeState,
        delay_seconds: float,
    ) -> None:
        if state.cooldown_task and not state.cooldown_task.done():
            return

        async def _run() -> None:
            try:
                await asyncio.sleep(max(0.0, delay_seconds))
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=False)
            finally:
                state.cooldown_task = None

        state.cooldown_task = asyncio.create_task(_run())

    async def _ensure_timeout_task(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        state: ChannelRuntimeState,
    ) -> None:
        pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
        min_new = max(1, settings.detection_min_new_messages)
        timeout_seconds = settings.detection_wait_timeout_seconds

        if pending == 0 or min_new <= 1 or timeout_seconds <= 0:
            if state.timeout_task and not state.timeout_task.done():
                state.timeout_task.cancel()
            state.timeout_task = None
            return

        if state.timeout_task and not state.timeout_task.done():
            return

        async def _run() -> None:
            try:
                await asyncio.sleep(timeout_seconds)
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=True)
            finally:
                state.timeout_task = None

        state.timeout_task = asyncio.create_task(_run())

    async def _evaluate_rules_in_parallel_batches(
        self,
        messages: list[ChatMessage],
        rules: list[DetectionRule],
    ) -> list[RuleDecision]:
        if not rules:
            return []

        batch_size = max(1, settings.llm_rules_per_batch)
        batches = [rules[i : i + batch_size] for i in range(0, len(rules), batch_size)]
        semaphore = asyncio.Semaphore(max(1, settings.llm_max_parallel_batches))

        async def run_batch(rule_batch: list[DetectionRule]) -> list[RuleDecision]:
            async with semaphore:
                return await self.llm_client.evaluate(messages=messages, rules=rule_batch)

        nested_results = await asyncio.gather(*(run_batch(batch) for batch in batches))
        decisions = [decision for sublist in nested_results for decision in sublist]
        return sorted(decisions, key=lambda item: item.rule_id)


class SelfMessageMemoryService:
    """当用户/机器人自身发言时，识别并写入记忆事实的服务。"""

    def __init__(self, llm_client: LLMClient, memory_repository: MemoryRepository, context_service: ContextWindowService):
        self.llm_client = llm_client
        self.memory_repository = memory_repository
        self.context_service = context_service

    async def process_if_self_message(self, event: ChatEvent) -> int:
        """如果事件来自自身，调用 LLM 提取记忆事实并存储。

        Returns:
            写入的事实数量。
        """
        if not event.is_from_self:
            return 0
        context_messages = await self.context_service.build_context(event)
        facts = await self.llm_client.extract_self_participation(event, context_messages)
        for fact in facts:
            await self.memory_repository.add_fact(fact)
        return len(facts)


class SuggestionService:
    """基于用户记忆与反馈生成规则建议的简易服务。

    当前实现为启发式聚合示例，后续可替换为依赖 LLM 的高级建议生成器。
    """

    def __init__(self, memory_repository: MemoryRepository, feedback_repository: FeedbackRepository):
        self.memory_repository = memory_repository
        self.feedback_repository = feedback_repository

    async def suggest_new_rules(self, user_id: str) -> list[str]:
        facts = await self.memory_repository.list_user_facts(user_id)
        if not facts:
            return []

        topic_counts: dict[str, int] = {}
        for fact in facts:
            topic_counts[fact.topic] = topic_counts.get(fact.topic, 0) + 1

        ranked = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
        return [f"为高频主题 '{topic}' 创建提醒规则（出现次数 {count}）" for topic, count in ranked[:5]]

    async def suggest_rule_improvements(self, rule_id: str) -> list[str]:
        feedbacks = await self.feedback_repository.list_by_rule(rule_id)
        if not feedbacks:
            return ["暂无反馈数据，可先补充正负样本描述。"]

        avg_score = sum(feedback.score for feedback in feedbacks) / len(feedbacks)
        suggestions = []
        if avg_score < 3:
            suggestions.append("命中质量偏低：建议补充排除条件并提高触发阈值。")
        if avg_score >= 4:
            suggestions.append("命中质量较好：建议补充参数提取字段以提升自动化价值。")

        text_feedback = [feedback.comment for feedback in feedbacks if feedback.comment]
        if text_feedback:
            suggestions.append(f"可合并 {len(text_feedback)} 条用户意见形成新版规则描述。")
        return suggestions


class RuleGenerationBackend(Protocol):
    """规则生成后端抽象：将一句话或文本转换为 `DetectionRule`。"""

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule: ...


class InternalRuleGenerationBackend:
    """简单的内置规则生成器。

    基于文本拆分与正则规则抽取候选主题、参与者与目标会话，产出一个初步可编辑的规则草案。
    """

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        topics = self._extract_topics(utterance)
        users = self._extract_users(utterance)
        target_text = self._extract_session_query(utterance)
        parameters = [RuleParameterSpec(key="label", description="LLM extracted label", required=False)]
        return DetectionRule(
            rule_id=f"rule-{abs(hash((utterance, override_system_prompt))) % 1000000}",
            name=(utterance[:24] + "...") if len(utterance) > 24 else utterance,
            description=utterance,
            target_session=SessionTarget(mode=SessionMatchMode.FUZZY, query=target_text),
            topic_hints=topics,
            participant_constraint=(None if not users else ParticipantConstraint(participant_ids=set(users))),
            score_threshold=0.6,
            enabled=True,
            parameters=parameters,
        )

    @staticmethod
    def _extract_topics(utterance: str) -> list[str]:
        terms = [term for term in re.split(r"[，,。\s]+", utterance) if term]
        filtered = [term for term in terms if len(term) >= 2 and not term.startswith("@")]
        return filtered[:6]

    @staticmethod
    def _extract_users(utterance: str) -> list[str]:
        return [item[1:] for item in re.findall(r"@[^\s，,。]+", utterance)]

    @staticmethod
    def _extract_session_query(utterance: str) -> str:
        patterns = [r"(?:群|私聊|会话)([^，,。]+)", r"在([^，,。]+)里", r"([^，,。]+)中"]
        for pattern in patterns:
            match = re.search(pattern, utterance)
            if match:
                return match.group(1).strip()
        return "*"


class ExternalPromptRuleGenerationBackend:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        payload = {"utterance": utterance, "system_prompt": override_system_prompt}
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            raw = response.json()

        parameters = [
            RuleParameterSpec(
                key=item["key"],
                description=item.get("description", ""),
                required=item.get("required", True),
            )
            for item in raw.get("parameters", [])
        ]

        return DetectionRule(
            rule_id=raw["rule_id"],
            name=raw["name"],
            description=raw["description"],
            target_session=SessionTarget(mode=SessionMatchMode(raw.get("session_mode", "fuzzy")), query=raw["session_query"]),
            topic_hints=raw.get("topic_hints", []),
            score_threshold=raw.get("score_threshold", 0.6),
            enabled=raw.get("enabled", True),
            parameters=parameters,
        )


class RuleAuthoringService:
    def __init__(self, internal_backend: RuleGenerationBackend, external_backend: RuleGenerationBackend | None):
        self.internal_backend = internal_backend
        self.external_backend = external_backend

    async def generate_rule(
        self,
        utterance: str,
        use_external: bool,
        override_system_prompt: str | None = None,
    ) -> DetectionRule:
        if use_external:
            if self.external_backend is None:
                raise ValueError("External generation backend is not configured")
            return await self.external_backend.generate(utterance, override_system_prompt)
        return await self.internal_backend.generate(utterance, override_system_prompt)


class Notifier(Protocol):
    """通知器协议，表示一种能够发送通知（邮件/短信/第三方 API 等）的实现。"""

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool: ...


@dataclass(slots=True)
class NotificationConfig:
    """通知配置（目前仅包含邮件接收方）。"""

    to_email: str | None


class EmailNotifier:
    """基于 SMTP 的邮件通知实现。"""

    def __init__(self, config: NotificationConfig):
        self.config = config

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool:
        """发送邮件通知。

        在未配置 SMTP 或接收邮箱时，返回 False 表示未发送。
        """
        if not self.config.to_email or not settings.smtp_host or not settings.smtp_sender:
            return False

        subject = f"[ChatGuardian] Rule Triggered: {decision.rule_id}"
        content = {
            "chat_id": event.chat_id,
            "message_id": event.message.message_id,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "params": decision.extracted_params,
        }
        body = json.dumps(content, ensure_ascii=False, indent=2)

        smtp = SMTP(hostname=settings.smtp_host, port=settings.smtp_port, use_tls=False)
        await smtp.connect()
        if settings.smtp_username and settings.smtp_password:
            await smtp.login(settings.smtp_username, settings.smtp_password)
        await smtp.sendmail(
            sender=settings.smtp_sender,
            recipients=[self.config.to_email],
            message=(
                f"From: {settings.smtp_sender}\r\n"
                f"To: {self.config.to_email}\r\n"
                f"Subject: {subject}\r\n\r\n"
                f"{body}"
            ),
        )
        await smtp.quit()
        return True


class ExternalHookDispatcher:
    """外部 Hook 派发器。

    当规则触发时，将检测结果与上下文通过 POST 方式异步发送到配置好的外部端点。
    """

    def __init__(self, hook_endpoints: list[str]):
        self.hook_endpoints = hook_endpoints

    async def dispatch(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> None:
        """异步将 payload 派发到所有配置的 endpoint，忽略单点失败。"""
        if not self.hook_endpoints:
            return

        payload = {
            "chat_id": event.chat_id,
            "message_id": event.message.message_id,
            "rule_id": decision.rule_id,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "parameters": decision.extracted_params,
            "context": [
                {
                    "message_id": message.message_id,
                    "sender_id": message.sender_id,
                    "text": message.extract_plain_text(),
                    "contents": [
                        {
                            "type": item.type.value,
                            "text": item.text,
                            "image_url": item.image_url,
                            "mention_user_id": item.mention_user_id,
                        }
                        for item in message.contents
                    ],
                    "timestamp": message.timestamp.isoformat(),
                }
                for message in context_messages
            ],
        }

        async with httpx.AsyncClient(timeout=settings.hook_timeout_seconds) as client:
            await asyncio.gather(*(client.post(endpoint, json=payload) for endpoint in self.hook_endpoints), return_exceptions=True)
