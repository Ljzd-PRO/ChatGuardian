from __future__ import annotations
import os
import asyncio
import pytest

from chat_guardian.adapters import AdapterManager, VirtualAdapter, VirtualAdapterConfig, VirtualScriptedMessage
from chat_guardian.domain import DetectionRule
from chat_guardian.matcher import MatchChatInfo
from chat_guardian.repositories import InMemoryChatHistoryStore, InMemoryDetectionResultRepository, InMemoryRuleRepository
from chat_guardian.services import ContextWindowService, DetectionEngine, ExternalHookDispatcher, build_llm_client
from chat_guardian.settings import settings

@pytest.mark.asyncio
async def test_virtual_adapter_detection_deepseek():
    # 配置 DeepSeek API，优先从环境变量读取
    if os.getenv("RUN_DEEPSEEK_INTEGRATION") != "1":
        pytest.skip("set RUN_DEEPSEEK_INTEGRATION=1 to run this integration test")

    api_key = os.getenv("CHAT_GUARDIAN_LLM_LANGCHAIN_API_KEY")
    if not api_key:
        pytest.skip("CHAT_GUARDIAN_LLM_LANGCHAIN_API_KEY is required")

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

    # 检测主题
    topics = ["电子产品", "汽车", "股市", "音乐"]
    rule_repo = InMemoryRuleRepository()
    for idx, topic in enumerate(topics):
        await rule_repo.upsert(
            DetectionRule(
                rule_id=f"rule-{idx+1}",
                name=f"检测主题-{topic}",
                description=f"检测主题：{topic}",
                matcher=MatchChatInfo(chat_id="virtual-group"),
                topic_hints=[topic],
                score_threshold=0.4,
                enabled=True,
            )
        )

    history_store = InMemoryChatHistoryStore(pending_queue_limit=500, history_list_limit=2000)
    result_repo = InMemoryDetectionResultRepository()
    llm_client = build_llm_client()
    engine = DetectionEngine(
        rules=rule_repo,
        context_service=ContextWindowService(history_store),
        llm_client=llm_client,
        result_repository=result_repo,
        notifiers=[],
        hook_dispatcher=ExternalHookDispatcher([]),
    )

    # 聊天消息
    scripted_messages = [
        # 香菜话题
        VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-1", sender_name="A", text="我还好，有香菜挑出来就好了", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-2", sender_name="B", text="我老公吃香菜会吐", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-3", sender_name="C", text="不知道是不是过敏", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-1", sender_id="u-4", sender_name="D", text="我女朋友也不吃香菜", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-5", sender_name="E", text="每次都记得备注不加", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-1", sender_name="A", text="实在有就挑给我", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-2", sender_id="u-2", sender_name="B", text="这样啊", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-3", sender_id="u-6", sender_name="F", text="我们这桌也有人不吃香菜", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-3", sender_id="u-3", sender_name="C", text="下次统一备注不要放香菜", delay_seconds=0),
        # 电动汽车品牌选择
        VirtualScriptedMessage(chat_id="virtual-group-4", sender_id="u-7", sender_name="G", text="最近在看电动车，特斯拉和比亚迪怎么选？", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-4", sender_id="u-8", sender_name="H", text="我觉得比亚迪性价比高，售后也方便。", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-4", sender_id="u-9", sender_name="I", text="特斯拉自动驾驶体验不错，就是贵点。", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-4", sender_id="u-7", sender_name="G", text="主要是家里能不能装充电桩还没定。", delay_seconds=0),
        # 单机游戏讨论
        VirtualScriptedMessage(chat_id="virtual-group-5", sender_id="u-10", sender_name="J", text="最近有啥好玩的单机游戏推荐吗？", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-5", sender_id="u-11", sender_name="K", text="我刚通关了《艾尔登法环》，超赞！", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-5", sender_id="u-12", sender_name="L", text="喜欢解谜的话可以试试《未上锁的房间》系列。", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-5", sender_id="u-10", sender_name="J", text="感谢，回头都试试！", delay_seconds=0),
        # 电子设备选择
        VirtualScriptedMessage(chat_id="virtual-group-6", sender_id="u-13", sender_name="M", text="想换个平板，iPad 和小米平板怎么选？", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-6", sender_id="u-14", sender_name="N", text="iPad生态好，适合画画和学习。", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-6", sender_id="u-15", sender_name="O", text="小米平板性价比高，安卓自由度大。", delay_seconds=0),
        VirtualScriptedMessage(chat_id="virtual-group-6", sender_id="u-13", sender_name="M", text="主要是预算有限，可能会选小米。", delay_seconds=0),
    ]

    manager = AdapterManager([VirtualAdapter(VirtualAdapterConfig(scripted_messages=scripted_messages))])
    handled_events = {"count": 0}
    handler_errors: list[str] = []

    async def wrapped_handler(event):
        handled_events["count"] += 1
        try:
            await engine.ingest_event(event)
        except Exception as exc:
            handler_errors.append(str(exc))

    for adapter in manager.adapters:
        adapter.register_handler(wrapped_handler)

    await manager.start_all()
    await asyncio.sleep(40.0)
    await manager.stop_all()

    scheduler_metrics = engine.batch_scheduler.diagnostics()["metrics"]
    # 检查事件处理和检测结果
    assert handled_events["count"] > 0
    assert handler_errors == []
    assert len(result_repo.results) > 0
    assert scheduler_metrics["total_batches"] > 0
    assert scheduler_metrics["total_llm_calls"] > 0

    # 输出检测结果日志
    print("\n--- 检测结果日志 ---")
    for result in result_repo.results:
        print(f"rule_id={result.rule_id}, topic={result.decision.reason}, params={result.decision.extracted_params}")
    print("--- END ---\n")

    # 只允许 "电子产品" "汽车" 被触发
    triggered_topics = set(result.rule_id for result in result_repo.results if result.decision.triggered)
    assert "rule-1" in triggered_topics  # 电子产品
    assert "rule-2" in triggered_topics  # 汽车
    assert "rule-3" not in triggered_topics  # 股市
    assert "rule-4" not in triggered_topics  # 音乐