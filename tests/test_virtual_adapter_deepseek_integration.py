from __future__ import annotations

import os

import asyncio

import pytest

from chat_guardian.adapters import AdapterManager, VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage
from chat_guardian.domain import DetectionRule
from chat_guardian.matcher import MatchChatInfo
from chat_guardian.repositories import (
    InMemoryChatHistoryStore,
    InMemoryDetectionResultRepository,
    InMemoryRuleRepository,
)
from chat_guardian.services import ContextWindowService, DetectionEngine, ExternalHookDispatcher, build_llm_client
from chat_guardian.settings import settings


@pytest.mark.asyncio
async def test_virtual_adapter_with_deepseek_real_run() -> None:
    if os.getenv("RUN_DEEPSEEK_INTEGRATION") != "1":
        pytest.skip("set RUN_DEEPSEEK_INTEGRATION=1 to run this integration test")

    api_key = os.getenv("CHAT_GUARDIAN_LLM_LANGCHAIN_API_KEY")
    if not api_key:
        pytest.skip("CHAT_GUARDIAN_LLM_LANGCHAIN_API_KEY is required")

    # 保存旧配置
    old_values = {
        "backend": settings.llm_langchain_backend,
        "model": settings.llm_langchain_model,
        "api_base": settings.llm_langchain_api_base,
        "api_key": settings.llm_langchain_api_key,
        "batch_size": settings.llm_rules_per_batch,
        "max_parallel": settings.llm_max_parallel_batches,
        "batch_timeout": settings.llm_batch_timeout_seconds,
        "batch_retries": settings.llm_batch_max_retries,
        "cooldown": settings.detection_cooldown_seconds,
        "min_new": settings.detection_min_new_messages,
        "wait_timeout": settings.detection_wait_timeout_seconds,
    }

    try:
        settings.llm_langchain_backend = "openai_compatible"
        settings.llm_langchain_model = os.getenv("CHAT_GUARDIAN_LLM_LANGCHAIN_MODEL", "deepseek-chat")
        settings.llm_langchain_api_base = os.getenv("CHAT_GUARDIAN_LLM_LANGCHAIN_API_BASE", "https://api.deepseek.com/v1")
        settings.llm_langchain_api_key = api_key

        settings.llm_rules_per_batch = 2
        settings.llm_max_parallel_batches = 2
        settings.llm_batch_timeout_seconds = 12
        settings.llm_batch_max_retries = 0

        settings.detection_cooldown_seconds = 0.2
        settings.detection_min_new_messages = 3
        settings.detection_wait_timeout_seconds = 1.5

        history_store = InMemoryChatHistoryStore(pending_queue_limit=500, history_list_limit=2000)
        rule_repo = InMemoryRuleRepository()
        result_repo = InMemoryDetectionResultRepository()
        llm_client = build_llm_client()

        for idx, topic in enumerate(["部署计划", "数据库迁移", "模型效果评估", "告警阈值"]):
            await rule_repo.upsert(
                DetectionRule(
                    rule_id=f"integration-rule-{idx + 1}",
                    name=f"集成规则-{idx + 1}",
                    description=f"检测主题：{topic}",
                    matcher=MatchChatInfo(chat_id="virtual-group"),
                    topic_hints=[topic],
                    score_threshold=0.4,
                    enabled=True,
                )
            )

        engine = DetectionEngine(
            rules=rule_repo,
            context_service=ContextWindowService(history_store),
            llm_client=llm_client,
            result_repository=result_repo,
            notifiers=[],
            hook_dispatcher=ExternalHookDispatcher([]),
        )

        scripted_messages = [
            VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-1", sender_name="A", text="我还好，有香菜挑出来就好了", delay_seconds=0.05),
            VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-2", sender_name="B", text="我老公吃香菜会吐", delay_seconds=0.12),
            VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-3", sender_name="C", text="不知道是不是过敏", delay_seconds=0.09),
            VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-4", sender_name="D", text="我女朋友也不吃香菜", delay_seconds=0.11),
            VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-5", sender_name="E", text="每次都记得备注不加", delay_seconds=0.07),
            VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-1", sender_name="A", text="实在有就挑给我", delay_seconds=0.08),
            VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-2", sender_name="B", text="这样啊", delay_seconds=0.06),
            VirtualScriptedMessage(chat_id="virtual-group-3", sender_id="u-6", sender_name="F", text="我们这桌也有人不吃香菜", delay_seconds=0.10),
            VirtualScriptedMessage(chat_id="virtual-group-3", sender_id="u-3", sender_name="C", text="下次统一备注不要放香菜", delay_seconds=0.12),
        ]

        manager = AdapterManager([VirtualAdapter(VirtualAdapterConfig(scripted_messages=scripted_messages))])
        handled_events = {"count": 0}
        handler_errors: list[str] = []

        async def wrapped_handler(event):
            handled_events["count"] += 1
            try:
                await engine.ingest_event(event)
            except Exception as exc:  # pragma: no cover - 集成测试调试保护
                handler_errors.append(str(exc))

        for adapter in manager.adapters:
            adapter.register_handler(wrapped_handler)

        await manager.start_all()
        await asyncio.sleep(4.0)
        await manager.stop_all()

        scheduler_metrics = engine.batch_scheduler.diagnostics()["metrics"]

        assert handled_events["count"] > 0
        assert handler_errors == []
        assert len(result_repo.results) > 0
        assert scheduler_metrics["total_batches"] > 0
        assert scheduler_metrics["total_llm_calls"] > 0

    finally:
        settings.llm_langchain_backend = old_values["backend"]
        settings.llm_langchain_model = old_values["model"]
        settings.llm_langchain_api_base = old_values["api_base"]
        settings.llm_langchain_api_key = old_values["api_key"]
        settings.llm_rules_per_batch = old_values["batch_size"]
        settings.llm_max_parallel_batches = old_values["max_parallel"]
        settings.llm_batch_timeout_seconds = old_values["batch_timeout"]
        settings.llm_batch_max_retries = old_values["batch_retries"]
        settings.detection_cooldown_seconds = old_values["cooldown"]
        settings.detection_min_new_messages = old_values["min_new"]
        settings.detection_wait_timeout_seconds = old_values["wait_timeout"]
