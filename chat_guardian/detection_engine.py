from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from chat_guardian.context_window_service import ContextWindowService
from chat_guardian.domain import (
    ChannelRuntimeState,
    ChatEvent,
    ChatMessage,
    ChatType,
    DetectionResult,
    EngineOutput,
)
from chat_guardian.external_hook_dispatcher import ExternalHookDispatcher
from chat_guardian.llm_client import LangChainLLMClient
from chat_guardian.notifiers import Notifier
from chat_guardian.repositories import DetectionResultRepository, RuleRepository
from chat_guardian.rule_batch_scheduler import RuleBatchScheduler
from chat_guardian.settings import settings


class DetectionEngine:
    """核心检测引擎。"""

    def __init__(
        self,
        rules: RuleRepository,
        context_service: ContextWindowService,
        llm_client: LangChainLLMClient,
        result_repository: DetectionResultRepository,
        notifiers: list[Notifier],
        hook_dispatcher: ExternalHookDispatcher,
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
        if settings.detection_min_new_messages > 1 and settings.detection_wait_timeout_seconds <= 0:
            raise ValueError("When detection_min_new_messages > 1, detection_wait_timeout_seconds must be > 0")

        logger.debug(f"📥 接收事件 | 平台={event.platform} | 会话={event.chat_id} | 消息ID={event.message.message_id}")

        await self.context_service.store.enqueue_message(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            message=event.message,
        )
        logger.debug("  ✓ 消息已入队")

        state = self._state_of(event.platform, event.chat_type.value, event.chat_id)
        await self._ensure_timeout_task(event.platform, event.chat_type.value, event.chat_id, state)

        min_new = max(1, settings.detection_min_new_messages)
        pending = await self.context_service.store.pending_size(event.platform, event.chat_type.value, event.chat_id)
        logger.info(f"📊 队列状态 | 待处理={pending} | 最小触发={min_new}")

        if pending < min_new:
            logger.debug("⏳ 消息不足，等待更多消息或超时触发...")
            return None

        logger.info("🚀 满足最小条件，触发检测...")
        return await self._try_trigger(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            force_all_pending=False,
        )

    async def _process_event_with_context(self, event: ChatEvent, context_messages: list[ChatMessage]) -> EngineOutput:
        logger.debug(f"🔍 开始处理事件 | 会话={event.chat_id} | 消息ID={event.message.message_id} | 上下文数={len(context_messages)}")

        active_rules = [rule for rule in await self.rules.list_enabled() if rule.matcher.matches(event)]
        logger.info(f"📋 适用规则 | 总数={len(active_rules)}")

        self_ids = set(settings.detection_self_sender_ids)
        if self_ids:
            self_in_ctx = any(msg.sender_id in self_ids for msg in context_messages if msg.sender_id)
            if self_in_ctx:
                logger.info(f"⏭️ 上下文含有自身消息，跳过 LLM 分析 | 会话={event.chat_id}")
                return EngineOutput(
                    event_id=f"evt-{event.message.message_id}",
                    results=[],
                    triggered_rule_ids=[],
                    notified_count=0,
                )

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
                is_in_last = await self.result_repository.contains_message_in_last_triggered(
                    decision.rule_id,
                    earliest_message_id,
                )
                if is_in_last:
                    logger.warning(f"⚠️ 规则 {decision.rule_id} 抑制: 上下文与最后触发重叠")
                    await self.result_repository.merge_into_last_triggered(decision.rule_id, context_messages)
                    suppressed = True
                    suppression_reason = "context overlaps with last triggered result"

            if suppressed:
                logger.debug(f"  ↩️ 抑制结果已合并至最近记录 | rule_id={decision.rule_id}")
                continue

            result = DetectionResult(
                result_id=f"{event_id}:{decision.rule_id}:{len(all_results)}",
                event_id=event_id,
                rule_id=decision.rule_id,
                adapter=event.platform,
                chat_type=event.chat_type.value,
                chat_id=event.chat_id,
                message_id=event.message.message_id,
                decision=decision,
                context_messages=list(context_messages),
                generated_at=datetime.now(timezone.utc),
                trigger_suppressed=suppressed,
                suppression_reason=suppression_reason,
            )
            await self.result_repository.add(result)
            all_results.append(result)
            logger.debug(
                f"  📍 生成结果 | rule_id={decision.rule_id} | triggered={decision.triggered} | suppressed={suppressed}"
            )

            if not decision.triggered or suppressed:
                continue

            triggered_rule_ids.append(decision.rule_id)
            logger.success(f"🎯 规则触发! | rule_id={decision.rule_id} | confidence={decision.confidence:.2f}")

            for notifier in self.notifiers:
                sent = await notifier.notify(event, decision, context_messages)
                notify_count += 1 if sent else 0
                logger.debug(f"  📢 通知器 {notifier.__class__.__name__} 已派发")

            await self.hook_dispatcher.dispatch(event, decision, context_messages)
            logger.debug("  🔗 Hook 已派发")

        logger.info(
            f"✅ 事件处理完成 | 事件ID={event_id} | 结果数={len(all_results)} | 触发数={len(triggered_rule_ids)} | 通知数={notify_count}"
        )
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
        state = self._state_of(platform, chat_type, chat_id)
        async with state.lock:
            now = datetime.now(timezone.utc)
            cooldown = max(0.0, settings.detection_cooldown_seconds)

            logger.debug(f"🔒 获取会话锁 | 会话={chat_id} | force_all={force_all_pending}")

            if state.last_detection_at and cooldown > 0:
                due = state.last_detection_at + timedelta(seconds=cooldown)
                if now < due:
                    remaining = (due - now).total_seconds()
                    logger.info(f"⏸️ 处于冷却期 | 剩余时间={remaining:.2f}s | 安排延迟触发")
                    await self._ensure_cooldown_task(platform, chat_type, chat_id, state, remaining)
                    return None

            logger.debug("🎯 检查冷却期通过，开始处理待选消息...")
            output = await self._drain_pending_and_detect(platform, chat_type, chat_id, force_all_pending)
            if output is None:
                logger.debug("⏭️ 无消息可处理，返回")
                return None

            state.last_detection_at = datetime.now(timezone.utc)
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
            logger.debug("⏭️ 无待处理消息")
            return None

        logger.info(f"📋 取出消息 | 数量={len(pending_messages)}")

        await self.context_service.store.append_history_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            messages=pending_messages,
        )
        logger.debug("  ✓ 消息已追加到历史记录")

        anchor_message = pending_messages[-1]
        event = ChatEvent(
            chat_type=ChatType(chat_type),
            chat_id=chat_id,
            message=anchor_message,
            platform=platform,
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
        if state.cooldown_task and not state.cooldown_task.done():
            logger.debug("⏳ 冷却任务已存在，跳过创建")
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
            logger.debug("⏰ 超时任务已存在，跳过创建")
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
