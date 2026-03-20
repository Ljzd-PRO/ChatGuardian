from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Callable, Coroutine

from loguru import logger

from chat_guardian.domain import ChatMessage, DetectionRule, RuleDecision
from chat_guardian.llm_client import LangChainLLMClient
from chat_guardian.models import RuleBatchSchedulerDiagnosticsModel, RuleBatchSchedulerMetricsModel


class RuleBatchScheduler:
    """规则批处理调度器。"""

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
        if not rules:
            logger.debug("📋 规则列表为空，跳过批调度")
            return []

        logger.debug(f"📦 开始规则批调度 | 请求ID={request_id} | 规则数={len(rules)} | 批大小={self.batch_size}")
        batches = [rules[i: i + self.batch_size] for i in range(0, len(rules), self.batch_size)]
        self._metrics.total_requests += 1
        self._metrics.total_batches += len(batches)
        logger.info(f"  📊 批分割完成 | 批次数={len(batches)} | 最大并行={self.max_parallel_batches}")

        async def run_batch(index: int, batch_rules: list[DetectionRule]) -> list[RuleDecision]:
            batch_request_id = self._build_batch_request_id(request_id, messages, batch_rules, index)
            logger.debug(f"  🔄 执行批次 {index + 1}/{len(batches)} | 批ID={batch_request_id} | 规则数={len(batch_rules)}")
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
            self._inflight.pop(request_id, None)
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
                    logger.debug(f"🔄 执行第 {attempt + 1}/{self.max_retries + 1} 次 LLM 调用 | 规则数={len(rules)}")
                    decisions = await asyncio.wait_for(
                        self.llm_client.evaluate(messages=messages, rules=rules),
                        timeout=self.batch_timeout_seconds,
                    )
                    self._metrics.successful_batches += 1
                    logger.info(
                        f"✅ LLM 批次执行成功 | 决策数={len(decisions)} | 触发={sum(1 for d in decisions if d.triggered)}"
                    )
                    return decisions
                except asyncio.TimeoutError as e:
                    last_error = e
                    self._metrics.batch_timeouts += 1
                    logger.warning(f"⚠️ 批次超时 (attempt {attempt + 1}): 超时={self.batch_timeout_seconds}s")
                    if attempt < self.max_retries:
                        self._metrics.retry_attempts += 1
                        logger.info("  🔄 将在 100ms 后重试...")
                        await asyncio.sleep(0.1)
                except Exception as e:
                    last_error = e
                    logger.error(f"❌ 批次执行异常 (attempt {attempt + 1}): {e}")
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

    def diagnostics(self) -> RuleBatchSchedulerDiagnosticsModel:
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
