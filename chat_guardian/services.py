from __future__ import annotations

from chat_guardian.models import RuleBatchSchedulerMetricsModel

"""
核心服务与基础实现。

此模块包含：
- 服务接口（Repository、LLM 客户端等）的协议定义；
- 开发阶段可用的内置实现（LangChain LLM、内存存储、Email 通知、外部 Hook 派发器）；
- 检测引擎、上下文窗口、规则生成、记忆写入与建议服务。

所有对外依赖（如真实 LLM、消息平台、持久化）均通过协议抽象，便于替换。
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol, Coroutine, Any, Union

import httpx
from aiosmtplib import SMTP
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

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
from chat_guardian.models import RuleBatchSchedulerDiagnosticsModel, DiagnosticsModel
from chat_guardian.settings import settings


def _extract_json_payload(raw_text: str) -> dict:
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

    async def list_by_rule(self, rule_id: str) -> list[DetectionResult]: ...

    async def contains_message_in_last_triggered(self, rule_id: str, message_id: str) -> bool: ...

    async def merge_into_last_triggered(self, rule_id: str, new_context_messages: list[ChatMessage]) -> DetectionResult | None: ...




class LangChainLLMClient:
    """基于 LangChain 的 LLM 客户端实现。

    说明：
    - 底层使用 `langchain_openai.ChatOpenAI`（兼容 OpenAI API 及同协议网关）；
    - 通过 JSON 协议返回规则判断与记忆提取结果；
    - 当模型输出异常时，回退为安全默认值（不触发）。
    """

    def __init__(
        self,
        chat_model: Union[ChatOpenAI | ChatOllama],
        backend: str,
        model_name: str,
        api_base: str | None,
        api_key_configured: bool,
        ollama_base_url: str | None,
    ):
        self.model = chat_model
        self.backend = backend
        self.model_name = model_name
        self.api_base = api_base
        self.api_key_configured = api_key_configured
        self.ollama_base_url = ollama_base_url
        logger.info(f"🤖 LLM 客户端已初始化 | backend={backend} | model={model_name} | api_key_configured={api_key_configured}")

    async def evaluate(self, messages: list[ChatMessage], rules: list[DetectionRule]) -> list[RuleDecision]:
        if not rules:
            logger.debug(f"📋 规则列表为空，返回空决策")
            return []

        logger.debug(f"🔍 LLM 评估开始 | 消息数={len(messages)} | 规则数={len(rules)}")
        payload = {
            "messages": [
                {
                    "message_id": message.message_id,
                    "sender_id": message.sender_id,
                    "text": message.extract_plain_text(),
                    "timestamp": message.timestamp.isoformat(),
                }
                for message in messages
            ],
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "description": rule.description,
                    "topic_hints": rule.topic_hints,
                    "score_threshold": rule.score_threshold,
                    "parameters": [
                        {
                            "key": parameter.key,
                            "description": parameter.description,
                            "required": parameter.required,
                        }
                        for parameter in rule.parameters
                    ],
                }
                for rule in rules
            ],
        }

        try:
            response = await self.model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "你是聊天规则检测模型。请根据输入消息和规则进行判断，并严格输出 JSON。"
                            "输出结构："
                            '{"decisions":[{"rule_id":"...","triggered":true|false,'
                            '"confidence":0~1,"reason":"...","extracted_params":{}}]}'
                        )
                    ),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            content = self._response_text(response.content)
            parsed = _extract_json_payload(content)
            decisions = self._parse_decisions(parsed, rules)
            triggered_count = sum(1 for d in decisions if d.triggered)
            logger.info(f"✅ LLM 评估完成 | 触发规则数={triggered_count} | 总规则数={len(rules)}")
            return decisions
        except Exception as e:
            logger.error(f"❌ LLM 评估异常: {e}")
            return self._fallback_decisions(rules, e)

    async def extract_self_participation(self, event: ChatEvent, context: list[ChatMessage]) -> list[UserMemoryFact]:
        logger.debug(f"💬 开始提取用户 {event.message.sender_id} 的内存事实 | 上下文消息数={len(context)}")
        payload = {
            "event": {
                "chat_id": event.chat_id,
                "sender_id": event.message.sender_id,
                "message": event.message.extract_plain_text(),
            },
            "context": [message.extract_plain_text() for message in context],
        }
        try:
            response = await self.model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "请从用户本人发言与上下文中提取可记忆事实，严格输出 JSON。"
                            '输出结构：{"facts":[{"topic":"...","counterpart_user_ids":["u1"],"confidence":0~1}]}'
                        )
                    ),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            )
            content = self._response_text(response.content)
            parsed = _extract_json_payload(content)

            raw_facts = parsed.get("facts", [])
            if not isinstance(raw_facts, list):
                logger.warning(f"⚠️ 内存事实格式异常: 非列表类型")
                return []

            results: list[UserMemoryFact] = []
            for item in raw_facts:
                if not isinstance(item, dict):
                    continue
                topic = str(item.get("topic", "")).strip()
                if not topic:
                    continue
                counterparts_raw = item.get("counterpart_user_ids", [])
                if not isinstance(counterparts_raw, list):
                    counterparts_raw = []
                counterparts = [str(value) for value in counterparts_raw if str(value).strip()]
                try:
                    confidence = float(item.get("confidence", 0.3))
                except (TypeError, ValueError):
                    confidence = 0.3
                confidence = min(1.0, max(0.0, confidence))

                fact = UserMemoryFact(
                    user_id=event.message.sender_id,
                    chat_id=event.chat_id,
                    topic=topic,
                    counterpart_user_ids=counterparts[:5],
                    confidence=confidence,
                    captured_at=datetime.utcnow(),
                )
                results.append(fact)
                logger.debug(f"  ✓ 提取事实: topic={topic} | confidence={confidence:.2f}")
            
            logger.info(f"✅ 内存事实提取完成 | 提取数量={len(results)}")
            return results
        except Exception as e:
            logger.error(f"❌ 内存事实提取异常: {e}")
            return []

    @staticmethod
    def _response_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            return "\n".join(text_parts)
        return str(content)

    @staticmethod
    def _parse_decisions(payload: dict, rules: list[DetectionRule]) -> list[RuleDecision]:
        raw_decisions = payload.get("decisions", [])
        indexed: dict[str, RuleDecision] = {}
        if isinstance(raw_decisions, list):
            for item in raw_decisions:
                if not isinstance(item, dict):
                    continue
                rule_id = str(item.get("rule_id", "")).strip()
                if not rule_id:
                    continue
                triggered = bool(item.get("triggered", False))
                try:
                    confidence = float(item.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                confidence = min(1.0, max(0.0, confidence))
                reason = str(item.get("reason", "LLM response"))
                raw_params = item.get("extracted_params", {})
                extracted_params = raw_params if isinstance(raw_params, dict) else {}
                indexed[rule_id] = RuleDecision(
                    rule_id=rule_id,
                    triggered=triggered,
                    confidence=confidence,
                    reason=reason,
                    extracted_params={str(key): str(value) for key, value in extracted_params.items()},
                )

        decisions: list[RuleDecision] = []
        for rule in rules:
            decisions.append(
                indexed.get(
                    rule.rule_id,
                    RuleDecision(
                        rule_id=rule.rule_id,
                        triggered=False,
                        confidence=0.0,
                        reason="LLM response missing this rule",
                        extracted_params={},
                    ),
                )
            )
        return decisions

    def diagnostics(self) -> "DiagnosticsModel":
        """返回当前 LLM 运行时诊断信息。"""
        return DiagnosticsModel(
            backend=self.backend,
            model=self.model_name,
            client_class=self.model.__class__.__name__,
            api_base=self.api_base,
            api_key_configured=self.api_key_configured,
            ollama_base_url=self.ollama_base_url,
        )

    async def ping(self) -> tuple[bool, str | None, float]:
        """执行最小模型调用探活。

        Returns:
            (是否成功, 失败原因, 延迟毫秒)
        """
        logger.debug(f"🔔 LLM ping 开始...")
        start = datetime.utcnow()
        try:
            await asyncio.wait_for(self.model.ainvoke([HumanMessage(content="ping")]), timeout=2.0)
            elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000
            logger.success(f"✅ LLM ping 成功 | 延迟={elapsed_ms:.2f}ms")
            return True, None, elapsed_ms
        except Exception as exc:
            elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000
            logger.warning(f"⚠️ LLM ping 失败: {exc} | 延迟={elapsed_ms:.2f}ms")
            return False, str(exc), elapsed_ms


def build_llm_client() -> LangChainLLMClient:
    """创建 LangChain LLM 客户端实例。支持 OpenAI 兼容与 Ollama 后端。"""
    backend = settings.llm_langchain_backend.strip().lower()
    logger.info(f"🔧 正在构建 LLM 客户端 | backend={backend}")

    if backend == "openai_compatible":
        api_key = settings.llm_langchain_api_key or "chat-guardian-dev-placeholder-key"
        logger.info(f"  📡 OpenAI 兼容后端 | endpoint={settings.llm_langchain_api_base}")
        chat_model = ChatOpenAI(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            base_url=settings.llm_langchain_api_base,
            api_key=api_key,
        )
        logger.success(f"✅ OpenAI LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="openai_compatible",
            model_name=settings.llm_langchain_model,
            api_base=settings.llm_langchain_api_base,
            api_key_configured=bool(settings.llm_langchain_api_key),
            ollama_base_url=None,
        )

    elif backend == "ollama":
        logger.info(f"  🦙 Ollama 后端 | base_url={settings.llm_ollama_base_url}")
        chat_model = ChatOllama(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            base_url=settings.llm_ollama_base_url,
        )
        logger.success(f"✅ Ollama LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="ollama",
            model_name=settings.llm_langchain_model,
            api_base=None,
            api_key_configured=False,
            ollama_base_url=settings.llm_ollama_base_url,
        )

    logger.error(f"❌ 不支持的 LLM 后端: {settings.llm_langchain_backend}")
    raise ValueError(f"Unsupported llm_langchain_backend: {settings.llm_langchain_backend}")


class SessionMatcher:
    """会话匹配器，支持不同匹配模式（Exact / Fuzzy）。"""

    @staticmethod
    def match(target: SessionTarget, event: ChatEvent) -> bool:
        if not target.query or target.query.strip() == "*":
            return True
            
        if target.mode == SessionMatchMode.EXACT:
            return target.query == event.chat_id
        normalized_query = target.query.lower().strip()
        return normalized_query in event.chat_id.lower()


class RuleBatchScheduler:
    """规则批处理调度器。

    能力：
    - 按批大小切分规则并并发调度；
    - 单批超时控制与失败重试；
    - 全局速率限制（每秒最大批次数）；
    - 幂等请求 ID（相同请求复用结果，避免重复调用 LLM）。
    """

    def __init__(
        self,
        llm_client: LangChainLLMClient,
        batch_size: int,
        max_parallel_batches: int,
        batch_timeout_seconds: float,
        max_retries: int,
        rate_limit_per_second: float,
        idempotency_cache_size: int,
    ):
        self.llm_client = llm_client
        self.batch_size = max(1, batch_size)
        self.max_parallel_batches = max(1, max_parallel_batches)
        self.batch_timeout_seconds = max(0.1, batch_timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.rate_limit_per_second = max(0.0, rate_limit_per_second)
        self.idempotency_cache_size = max(16, idempotency_cache_size)

        self._parallel_semaphore = asyncio.Semaphore(self.max_parallel_batches)
        self._idempotency_lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Task[list[RuleDecision]]] = {}
        self._completed: dict[str, list[RuleDecision]] = {}

        self._rate_lock = asyncio.Lock()
        self._next_available_time = 0.0
        self._metrics = RuleBatchSchedulerMetricsModel(
            total_requests=0,
            total_batches=0,
            total_llm_calls=0,
            successful_batches=0,
            fallback_batches=0,
            retry_attempts=0,
            batch_timeouts=0,
            idempotency_completed_hits=0,
            idempotency_inflight_hits=0,
            rate_limit_wait_count=0,
            rate_limit_wait_ms=0.0,
        )

    async def evaluate_rules(
        self,
        messages: list[ChatMessage],
        rules: list[DetectionRule],
        request_id: str,
    ) -> list[RuleDecision]:
        """执行规则批调度并返回合并后的决策结果。"""
        if not rules:
            logger.debug(f"📋 规则列表为空，跳过批调度")
            return []

        logger.debug(f"📦 开始规则批调度 | 请求ID={request_id} | 规则数={len(rules)} | 批大小={self.batch_size}")
        batches = [rules[i : i + self.batch_size] for i in range(0, len(rules), self.batch_size)]
        self._metrics.total_requests += 1
        self._metrics.total_batches += len(batches)
        logger.info(f"  📊 批分割完成 | 批次数={len(batches)} | 最大并行={self.max_parallel_batches}")

        async def run_batch(index: int, batch_rules: list[DetectionRule]) -> list[RuleDecision]:
            batch_request_id = self._build_batch_request_id(request_id, messages, batch_rules, index)
            logger.debug(f"  🔄 执行批次 {index+1}/{len(batches)} | 批ID={batch_request_id} | 规则数={len(batch_rules)}")
            return await self._run_idempotent(batch_request_id, lambda: self._execute_batch(messages, batch_rules))

        nested_results = await asyncio.gather(*(run_batch(index, batch) for index, batch in enumerate(batches)))
        decisions = [decision for sublist in nested_results for decision in sublist]
        logger.success(f"✅ 批调度完成 | 总决策数={len(decisions)} | 触发={sum(1 for d in decisions if d.triggered)}")
        return sorted(decisions, key=lambda item: item.rule_id)

    @staticmethod
    def _build_batch_request_id(
        request_id: str,
        messages: list[ChatMessage],
        rules: list[DetectionRule],
        batch_index: int,
    ) -> str:
        message_part = "|".join(message.message_id for message in messages)
        rule_part = "|".join(rule.rule_id for rule in rules)
        digest = hashlib.sha1(f"{request_id}:{batch_index}:{message_part}:{rule_part}".encode("utf-8")).hexdigest()
        return f"rb:{digest}"

    async def _run_idempotent(
        self,
        request_id: str,
        executor: Callable[[], Coroutine[Any, Any, list[RuleDecision]]],
    ) -> list[RuleDecision]:
        async with self._idempotency_lock:
            cached = self._completed.get(request_id)
            if cached is not None:
                self._metrics.idempotency_completed_hits += 1
                logger.debug(f"♻️ 幂等缓存命中 (已完成) | request_id={request_id} | 缓存大小={len(self._completed)}")
                return cached

            task = self._inflight.get(request_id)
            if task is None:
                logger.debug(f"🌀 创建新任务 | request_id={request_id}")
                task = asyncio.create_task(executor())
                self._inflight[request_id] = task
            else:
                self._metrics.idempotency_inflight_hits += 1
                logger.debug(f"♻️ 幂等缓存命中 (飞行中) | request_id={request_id}")

        result = await task

        async with self._idempotency_lock:
            await self._inflight.pop(request_id, None)
            self._completed[request_id] = result
            while len(self._completed) > self.idempotency_cache_size:
                first_key = next(iter(self._completed))
                self._completed.pop(first_key, None)
                logger.debug(f"🗑️ 缓存溢出，移除旧项: {first_key}")

        return result

    async def _execute_batch(
        self,
        messages: list[ChatMessage],
        rules: list[DetectionRule],
    ) -> list[RuleDecision]:
        async with self._parallel_semaphore:
            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    await self._acquire_rate_limit_slot()
                    self._metrics.total_llm_calls += 1
                    logger.debug(f"🔄 执行第 {attempt+1}/{self.max_retries+1} 次 LLM 调用 | 规则数={len(rules)}")
                    decisions = await asyncio.wait_for(
                        self.llm_client.evaluate(messages=messages, rules=rules),
                        timeout=self.batch_timeout_seconds,
                    )
                    self._metrics.successful_batches += 1
                    logger.info(f"✅ LLM 批次执行成功 | 决策数={len(decisions)} | 触发={sum(1 for d in decisions if d.triggered)}")
                    return decisions
                except asyncio.TimeoutError as e:
                    last_error = e
                    self._metrics.batch_timeouts += 1
                    logger.warning(f"⚠️ 批次超时 (attempt {attempt+1}): 超时={self.batch_timeout_seconds}s")
                    if attempt < self.max_retries:
                        self._metrics.retry_attempts += 1
                        logger.info(f"  🔄 将在 100ms 后重试...")
                        await asyncio.sleep(0.1)
                except Exception as e:
                    last_error = e
                    logger.error(f"❌ 批次执行异常 (attempt {attempt+1}): {e}")
                    if attempt < self.max_retries:
                        self._metrics.retry_attempts += 1
                        await asyncio.sleep(0.1)
            
            self._metrics.fallback_batches += 1
            logger.error(f"❌ 批次执行失败，使用备用决策 | 最后错误={last_error}")
            return self._fallback_decisions(rules, last_error)

    async def _acquire_rate_limit_slot(self) -> None:
        if self.rate_limit_per_second <= 0:
            return

        interval = 1.0 / self.rate_limit_per_second
        async with self._rate_lock:
            now = time.monotonic()
            if now < self._next_available_time:
                wait_seconds = self._next_available_time - now
                self._metrics.rate_limit_wait_count += 1
                self._metrics.rate_limit_wait_ms += wait_seconds * 1000
                await asyncio.sleep(wait_seconds)
            now2 = time.monotonic()
            self._next_available_time = now2 + interval

    def diagnostics(self) -> "RuleBatchSchedulerDiagnosticsModel":
        """返回批调度器的运行配置与统计信息。"""
        # 已在文件顶部导入，无需重复
        return RuleBatchSchedulerDiagnosticsModel(
            batch_size=self.batch_size,
            max_parallel_batches=self.max_parallel_batches,
            batch_timeout_seconds=self.batch_timeout_seconds,
            max_retries=self.max_retries,
            rate_limit_per_second=self.rate_limit_per_second,
            idempotency_cache_size=self.idempotency_cache_size,
            idempotency_completed_cache_entries=len(self._completed),
            idempotency_inflight_entries=len(self._inflight),
            metrics=self._metrics,
        )

    @staticmethod
    def _fallback_decisions(rules: list[DetectionRule], error: Exception | None) -> list[RuleDecision]:
        reason = f"LLM batch failed: {error}" if error else "LLM batch failed"
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.0,
                reason=reason,
                extracted_params={},
            )
            for rule in rules
        ]


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
    event_id: str
    results: list[DetectionResult]
    triggered_rule_ids: list[str]
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
        llm_client: LangChainLLMClient,
        result_repository: DetectionResultRepository,
        notifiers: list["Notifier"],
        hook_dispatcher: "ExternalHookDispatcher",
        batch_scheduler: RuleBatchScheduler | None = None,
    ):
        self.rules = rules
        self.context_service = context_service
        self.llm_client = llm_client
        self.result_repository = result_repository
        self.notifiers = notifiers
        self.hook_dispatcher = hook_dispatcher
        self.batch_scheduler = batch_scheduler or RuleBatchScheduler(
            llm_client=llm_client,
            batch_size=settings.llm_rules_per_batch,
            max_parallel_batches=settings.llm_max_parallel_batches,
            batch_timeout_seconds=settings.llm_batch_timeout_seconds,
            max_retries=settings.llm_batch_max_retries,
            rate_limit_per_second=settings.llm_batch_rate_limit_per_second,
            idempotency_cache_size=settings.llm_batch_idempotency_cache_size,
        )
        self._runtime_states: dict[tuple[str, str, str], ChannelRuntimeState] = {}

    @staticmethod
    def _channel_key(platform: str, chat_type: str, chat_id: str) -> tuple[str, str, str]:
        return platform, chat_type, chat_id

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

        logger.debug(f"📥 接收事件 | 平台={event.platform} | 会话={event.chat_id} | 消息ID={event.message.message_id}")
        
        await self.context_service.store.enqueue_message(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            message=event.message,
        )
        logger.debug(f"  ✓ 消息已入队")

        state = self._state_of(event.platform, event.chat_type.value, event.chat_id)
        await self._ensure_timeout_task(event.platform, event.chat_type.value, event.chat_id, state)

        min_new = max(1, settings.detection_min_new_messages)
        pending = await self.context_service.store.pending_size(event.platform, event.chat_type.value, event.chat_id)
        logger.info(f"📊 队列状态 | 待处理={pending} | 最小触发={min_new}")
        
        if pending < min_new:
            logger.debug(f"⏳ 消息不足，等待更多消息或超时触发...")
            return None

        logger.info(f"🚀 满足最小条件，触发检测...")
        return await self._try_trigger(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            force_all_pending=False,
        )

    async def _process_event_with_context(self, event: ChatEvent, context_messages: list[ChatMessage]) -> EngineOutput:
        logger.debug(f"🔍 开始处理事件 | 会话={event.chat_id} | 消息ID={event.message.message_id} | 上下文数={len(context_messages)}")
        
        active_rules = [rule for rule in await self.rules.list_enabled() if SessionMatcher.match(rule.target_session, event)]
        logger.info(f"📋 适用规则 | 总数={len(active_rules)}")
        
        scheduler_request_id = f"{event.platform}:{event.chat_id}:{event.message.message_id}"
        decisions = await self.batch_scheduler.evaluate_rules(
            messages=context_messages,
            rules=active_rules,
            request_id=scheduler_request_id,
        )

        event_id = f"evt-{event.message.message_id}"
        all_results: list[DetectionResult] = []
        triggered_rule_ids: list[str] = []
        notify_count = 0

        for decision in decisions:
            suppressed = False
            suppression_reason: str | None = None

            if decision.triggered and context_messages:
                earliest_message_id = context_messages[0].message_id
                is_in_last = await self.result_repository.contains_message_in_last_triggered(decision.rule_id, earliest_message_id)
                if is_in_last:
                    logger.warning(f"⚠️ 规则 {decision.rule_id} 抑制: 上下文与最后触发重叠")
                    await self.result_repository.merge_into_last_triggered(decision.rule_id, context_messages)
                    suppressed = True
                    suppression_reason = "context overlaps with last triggered result"

            result = DetectionResult(
                result_id=f"{event_id}:{decision.rule_id}:{len(all_results)}",
                event_id=event_id,
                rule_id=decision.rule_id,
                chat_id=event.chat_id,
                message_id=event.message.message_id,
                decision=decision,
                context_messages=list(context_messages),
                generated_at=datetime.utcnow(),
                trigger_suppressed=suppressed,
                suppression_reason=suppression_reason,
            )
            await self.result_repository.add(result)
            all_results.append(result)
            logger.debug(f"  📍 生成结果 | rule_id={decision.rule_id} | triggered={decision.triggered} | suppressed={suppressed}")

            if not decision.triggered or suppressed:
                continue

            triggered_rule_ids.append(decision.rule_id)
            logger.success(f"🎯 规则触发! | rule_id={decision.rule_id} | confidence={decision.confidence:.2f}")
            
            for notifier in self.notifiers:
                sent = await notifier.notify(event, decision, context_messages)
                notify_count += 1 if sent else 0
                logger.debug(f"  📢 通知器 {notifier.__class__.__name__} 已派发")
            
            await self.hook_dispatcher.dispatch(event, decision, context_messages)
            logger.debug(f"  🔗 Hook 已派发")

        logger.info(f"✅ 事件处理完成 | 事件ID={event_id} | 结果数={len(all_results)} | 触发数={len(triggered_rule_ids)} | 通知数={notify_count}")
        return EngineOutput(
            event_id=event_id,
            results=all_results,
            triggered_rule_ids=triggered_rule_ids,
            notified_count=notify_count,
        )

    async def _try_trigger(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        force_all_pending: bool,
    ) -> EngineOutput | None:
        """尝试触发一次检测。

        行为：在会话锁内检查冷却期；若处于冷却则安排冷却完成后的重试；
        否则从 pending 中取出消息并执行检测。

        Args:
            platform: 平台标识。
            chat_type: 聊天类型字符串。
            chat_id: 会话 ID。
            force_all_pending: 是否强制将 pending 中全部消息取出（用于超时触发）。

        Returns:
            若执行了检测返回 `EngineOutput`，否则返回 None（表示未触发）。
        """
        state = self._state_of(platform, chat_type, chat_id)
        async with state.lock:
            now = datetime.utcnow()
            cooldown = max(0.0, settings.detection_cooldown_seconds)
            
            logger.debug(f"🔒 获取会话锁 | 会话={chat_id} | force_all={force_all_pending}")
            
            if state.last_detection_at and cooldown > 0:
                due = state.last_detection_at + timedelta(seconds=cooldown)
                if now < due:
                    remaining = (due - now).total_seconds()
                    logger.info(f"⏸️ 处于冷却期 | 剩余时间={remaining:.2f}s | 安排延迟触发")
                    await self._ensure_cooldown_task(platform, chat_type, chat_id, state, remaining)
                    return None

            logger.debug(f"🎯 检查冷却期通过，开始处理待选消息...")
            output = await self._drain_pending_and_detect(platform, chat_type, chat_id, force_all_pending)
            if output is None:
                logger.debug(f"⏭️ 无消息可处理，返回")
                return None

            state.last_detection_at = datetime.utcnow()
            logger.success(f"✅ 检测完成 | 事件ID={output.event_id} | 触发规则数={len(output.triggered_rule_ids)}")

            pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
            min_new = max(1, settings.detection_min_new_messages)
            if pending >= min_new and cooldown > 0:
                logger.debug(f"📅 安排冷却期 | 冷却秒数={cooldown}s")
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
        """从 pending 中取出一批消息写入历史并以最后一条为锚触发检测。

        当 `force_all_pending` 为 False 时，最多只取 `detection_min_new_messages` 条；
        否则取出队列内所有消息。

        返回与 `process_event` 相同的 `EngineOutput`，或在没有消息可处理时返回 None。
        """
        min_new = max(1, settings.detection_min_new_messages)
        max_count = None if force_all_pending else min_new
        
        logger.debug(f"📤 开始从队列中取出消息 | max_count={max_count} | force_all={force_all_pending}")

        pending_messages = await self.context_service.store.pop_pending_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            max_count=max_count,
        )
        if not pending_messages:
            logger.debug(f"⏭️ 无待处理消息")
            return None

        logger.info(f"📋 取出消息 | 数量={len(pending_messages)}")

        await self.context_service.store.append_history_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            messages=pending_messages,
        )
        logger.debug(f"  ✓ 消息已追加到历史记录")

        anchor_message = pending_messages[-1]
        event = ChatEvent(
            chat_type=ChatType(chat_type),
            chat_id=chat_id,
            message=anchor_message,
            platform=platform,
            is_from_self=False,
        )
        context_messages = await self.context_service.build_context(event)
        logger.debug(f"  ✓ 构建上下文 | 上下文消息数={len(context_messages)}")
        
        return await self._process_event_with_context(event, context_messages)

    async def _ensure_cooldown_task(
        self,
        platform: str,
        chat_type: str,
        chat_id: str,
        state: ChannelRuntimeState,
        delay_seconds: float,
    ) -> None:
        """安排一个冷却到期后的重试任务。

        若已有未完成的冷却任务则不重复创建。
        """
        if state.cooldown_task and not state.cooldown_task.done():
            logger.debug(f"⏳ 冷却任务已存在，跳过创建")
            return

        logger.debug(f"⏲️ 创建冷却任务 | 延迟={delay_seconds:.2f}s | 会话={chat_id}")

        async def _run() -> None:
            try:
                await asyncio.sleep(max(0.0, delay_seconds))
                logger.info(f"🕐 冷却期已到期，触发重试 | 会话={chat_id}")
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=False)
            except Exception as e:
                logger.error(f"❌ 冷却任务异常: {e}")
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
        """根据当前 pending 状态与配置，安排或取消等待超时强制触发的任务。

        - 若 pending==0 或 最小新消息 <=1 或 超时时间 <=0，则取消已有超时任务。
        - 否则创建一个在 `detection_wait_timeout_seconds` 后执行的任务（若尚未存在）。
        """
        pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
        min_new = max(1, settings.detection_min_new_messages)
        timeout_seconds = settings.detection_wait_timeout_seconds

        if pending == 0 or min_new <= 1 or timeout_seconds <= 0:
            if state.timeout_task and not state.timeout_task.done():
                logger.debug(f"❌ 取消超时任务 | 原因: pending={pending}, min_new={min_new}, timeout={timeout_seconds}")
                state.timeout_task.cancel()
            state.timeout_task = None
            return

        if state.timeout_task and not state.timeout_task.done():
            logger.debug(f"⏰ 超时任务已存在，跳过创建")
            return

        logger.debug(f"⏲️ 创建超时任务 | 超时秒数={timeout_seconds}s | pending={pending} | 会话={chat_id}")

        async def _run() -> None:
            try:
                await asyncio.sleep(timeout_seconds)
                logger.info(f"🕒 等待超时，强制触发 | 会话={chat_id}")
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=True)
            except Exception as e:
                logger.error(f"❌ 超时任务异常: {e}")
            finally:
                state.timeout_task = None

        state.timeout_task = asyncio.create_task(_run())

class SelfMessageMemoryService:
    """当用户/机器人自身发言时，识别并写入记忆事实的服务。"""

    def __init__(self, llm_client: LangChainLLMClient, memory_repository: MemoryRepository, context_service: ContextWindowService):
        self.llm_client = llm_client
        self.memory_repository = memory_repository
        self.context_service = context_service

    async def process_if_self_message(self, event: ChatEvent) -> int:
        """如果事件来自自身，调用 LLM 提取记忆事实并存储。

        Returns:
            写入的事实数量。
        """
        if not event.is_from_self:
            logger.debug(f"ℹ️ 非自身消息，跳过内存处理 | 发送者={event.message.sender_id}")
            return 0
        
        logger.debug(f"💾 自身消息检测 | 发送者={event.message.sender_id} | 消息ID={event.message.message_id}")
        context_messages = await self.context_service.build_context(event)
        logger.debug(f"  ✓ 构建上下文 | 消息数={len(context_messages)}")
        
        facts = await self.llm_client.extract_self_participation(event, context_messages)
        logger.debug(f"  ✓ LLM 提取完成 | 事实数={len(facts)}")
        
        for fact in facts:
            await self.memory_repository.add_fact(fact)
            logger.debug(f"    ✓ 保存事实: topic={fact.topic}")
        
        if facts:
            logger.success(f"✅ 内存事实已保存 | 数量={len(facts)}")
        return len(facts)


class SuggestionService:
    """基于用户记忆与反馈生成规则建议的简易服务。

    当前实现为启发式聚合示例，后续可替换为依赖 LLM 的高级建议生成器。
    """

    def __init__(self, memory_repository: MemoryRepository, feedback_repository: FeedbackRepository):
        self.memory_repository = memory_repository
        self.feedback_repository = feedback_repository

    async def suggest_new_rules(self, user_id: str) -> list[str]:
        logger.debug(f"🔍 为用户 {user_id} 查找可建议的规则")
        facts = await self.memory_repository.list_user_facts(user_id)
        logger.debug(f"  ✓ 查询用户事实 | 事实数={len(facts)}")
        
        if not facts:
            logger.info(f"ℹ️ 用户 {user_id} 无记忆事实，无法生成建议")
            return []

        topic_counts: dict[str, int] = {}
        for fact in facts:
            topic_counts[fact.topic] = topic_counts.get(fact.topic, 0) + 1

        ranked = sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)
        suggestions = [f"为高频主题 '{topic}' 创建提醒规则（出现次数 {count}）" for topic, count in ranked[:5]]
        logger.success(f"✅ 规则建议生成完成 | 数量={len(suggestions)}")
        return suggestions

    async def suggest_rule_improvements(self, rule_id: str) -> list[str]:
        logger.debug(f"📊 为规则 {rule_id} 生成改进建议")
        feedbacks = await self.feedback_repository.list_by_rule(rule_id)
        logger.debug(f"  ✓ 查询反馈 | 反馈数={len(feedbacks)}")
        
        if not feedbacks:
            logger.info(f"ℹ️ 规则 {rule_id} 无反馈，无法生成建议")
            return ["暂无反馈数据，可先补充正负样本描述。"]

        avg_score = sum(feedback.score for feedback in feedbacks) / len(feedbacks)
        logger.debug(f"  📈 平均反馈评分={avg_score:.2f}")
        
        suggestions = []
        if avg_score < 3:
            suggestions.append("命中质量偏低：建议补充排除条件并提高触发阈值。")
        if avg_score >= 4:
            suggestions.append("命中质量较好：建议补充参数提取字段以提升自动化价值。")

        text_feedback = [feedback.comment for feedback in feedbacks if feedback.comment]
        if text_feedback:
            suggestions.append(f"可合并 {len(text_feedback)} 条用户意见形成新版规则描述。")
        
        logger.success(f"✅ 改进建议生成完成 | 建议数={len(suggestions)}")
        return suggestions


class RuleGenerationBackend(Protocol):
    """规则生成后端抽象：将一句话或文本转换为 `DetectionRule`。"""

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule: ...


class InternalRuleGenerationBackend(RuleGenerationBackend):
    """简单的内置规则生成器。

    基于文本拆分与正则规则抽取候选主题、参与者与目标会话，产出一个初步可编辑的规则草案。
    """

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        logger.debug(f"🔧 内部规则生成器处理 | 文本长度={len(utterance)}")
        
        topics = self._extract_topics(utterance)
        logger.debug(f"  ✓ 提取主题 | 数量={len(topics)} | {topics[:3]}")
        
        users = self._extract_users(utterance)
        logger.debug(f"  ✓ 提取用户 | 数量={len(users)} | {users}")
        
        target_text = self._extract_session_query(utterance)
        logger.debug(f"  ✓ 提取会话 | 目标={target_text}")
        
        parameters = [RuleParameterSpec(key="label", description="LLM extracted label", required=False)]
        rule_id = f"rule-{abs(hash((utterance, override_system_prompt))) % 1000000}"
        rule_name = (utterance[:24] + "...") if len(utterance) > 24 else utterance
        
        rule = DetectionRule(
            rule_id=rule_id,
            name=rule_name,
            description=utterance,
            target_session=SessionTarget(mode=SessionMatchMode.FUZZY, query=target_text),
            topic_hints=topics,
            participant_constraint=(None if not users else ParticipantConstraint(participant_ids=set(users))),
            score_threshold=0.6,
            enabled=True,
            parameters=parameters,
        )
        logger.success(f"✅ 内部规则已生成 | rule_id={rule_id}")
        return rule

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


class ExternalPromptRuleGenerationBackend(RuleGenerationBackend):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        logger.debug(f"🌐 外部规则生成器: 向 {self.endpoint} 发起请求 | 文本长度={len(utterance)}")
        
        payload = {"utterance": utterance, "system_prompt": override_system_prompt}
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                logger.debug(f"  ✓ 外部服务响应 | status={response.status_code}")
                
                raw = response.json()

            parameters = [
                RuleParameterSpec(
                    key=item["key"],
                    description=item.get("description", ""),
                    required=item.get("required", True),
                )
                for item in raw.get("parameters", [])
            ]

            rule = DetectionRule(
                rule_id=raw["rule_id"],
                name=raw["name"],
                description=raw["description"],
                target_session=SessionTarget(mode=SessionMatchMode(raw.get("session_mode", "fuzzy")), query=raw["session_query"]),
                topic_hints=raw.get("topic_hints", []),
                score_threshold=raw.get("score_threshold", 0.6),
                enabled=raw.get("enabled", True),
                parameters=parameters,
            )
            logger.success(f"✅ 外部规则已生成 | rule_id={rule.rule_id}")
            return rule
        except Exception as e:
            logger.error(f"❌ 外部规则生成失败: {e}")
            raise


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
        logger.debug(f"📝 开始规则生成 | use_external={use_external} | 文本长度={len(utterance)}")
        
        if use_external:
            if self.external_backend is None:
                logger.error(f"❌ 外部生成后端未配置")
                raise ValueError("External generation backend is not configured")
            logger.info(f"🌐 使用外部后端生成规则...")
            rule = await self.external_backend.generate(utterance, override_system_prompt)
        else:
            logger.info(f"⚙️ 使用内部后端生成规则...")
            rule = await self.internal_backend.generate(utterance, override_system_prompt)
        
        logger.success(f"✅ 规则生成完成 | rule_id={rule.rule_id} | name={rule.name}")
        return rule


class Notifier(Protocol):
    """通知器协议，表示一种能够发送通知（邮件/短信/第三方 API 等）的实现。"""

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool: ...


@dataclass(slots=True)
class NotificationConfig:
    """通知配置（目前仅包含邮件接收方）。"""

    to_email: str | None


class EmailNotifier(Notifier):
    """基于 SMTP 的邮件通知实现。"""

    def __init__(self, config: NotificationConfig):
        self.config = config

    async def notify(self, event: ChatEvent, decision: RuleDecision, _context_messages: list[ChatMessage]) -> bool:
        """发送邮件通知。

        在未配置 SMTP 或接收邮箱时，返回 False 表示未发送。
        """
        if not self.config.to_email or not settings.smtp_host or not settings.smtp_sender:
            logger.warning(f"⚠️ 邮件通知未配置 | to_email={bool(self.config.to_email)} | smtp_host={bool(settings.smtp_host)}")
            return False

        logger.debug(f"📧 准备发送邮件通知 | 收件人={self.config.to_email} | 规则={decision.rule_id}")
        
        subject = f"[ChatGuardian] Rule Triggered: {decision.rule_id}"
        content = {
            "chat_id": event.chat_id,
            "message_id": event.message.message_id,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "params": decision.extracted_params,
        }
        body = json.dumps(content, ensure_ascii=False, indent=2)

        try:
            smtp = SMTP(hostname=settings.smtp_host, port=settings.smtp_port, use_tls=False)
            await smtp.connect()
            logger.debug(f"  ✓ SMTP 连接成功")
            
            if settings.smtp_username and settings.smtp_password:
                await smtp.login(settings.smtp_username, settings.smtp_password)
                logger.debug(f"  ✓ SMTP 认证成功")
            
            await smtp.sendmail(
                settings.smtp_sender,
                [self.config.to_email],
                (
                    f"From: {settings.smtp_sender}\r\n"
                    f"To: {self.config.to_email}\r\n"
                    f"Subject: {subject}\r\n\r\n"
                    f"{body}"
                ),
            )
            await smtp.quit()
            logger.success(f"✅ 邮件已发送 | 收件人={self.config.to_email} | 规则={decision.rule_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False


class ExternalHookDispatcher:
    """外部 Hook 派发器。

    当规则触发时，将检测结果与上下文通过 POST 方式异步发送到配置好的外部端点。
    """

    def __init__(self, hook_endpoints: list[str]):
        self.hook_endpoints = hook_endpoints

    async def dispatch(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> None:
        """异步将 payload 派发到所有配置的 endpoint，忽略单点失败。"""
        if not self.hook_endpoints:
            logger.debug(f"ℹ️ 无外部 Hook 端点配置，跳过派发")
            return

        logger.debug(f"🔗 准备派发 Hook | 规则={decision.rule_id} | 端点数={len(self.hook_endpoints)}")

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

        async def send_to_endpoint(endpoint: str) -> str | Exception:
            try:
                async with httpx.AsyncClient(timeout=settings.hook_timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload)
                    logger.debug(f"  ✓ Hook 已派发 | endpoint={endpoint} | status={response.status_code}")
                    return endpoint
            except Exception as e:
                logger.warning(f"  ⚠️ Hook 派发失败 | endpoint={endpoint} | 错误={e}")
                return e

        results = await asyncio.gather(*(send_to_endpoint(ep) for ep in self.hook_endpoints), return_exceptions=True)
        success_count = sum(1 for r in results if isinstance(r, str))
        logger.info(f"✅ Hook 派发完成 | 成功={success_count}/{len(self.hook_endpoints)}")
