"""
后台管理智能体模块。

基于 LangChain 构建的管理智能体，将已有 MCP 操作封装为工具函数，
供管理员通过自然语言对话完成各项设置和信息查询操作。
支持流式输出与工具调用结果展示。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from loguru import logger

from chat_guardian.settings import settings

# ── 工具名称到用户可读描述的映射 ─────────────────────────────────────────
TOOL_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "get_dashboard": {
        "en": "View Dashboard",
        "zh": "查看仪表盘",
    },
    "get_rules_list": {
        "en": "View Rules",
        "zh": "查看规则列表",
    },
    "create_or_update_rule": {
        "en": "Create/Update Rule",
        "zh": "创建/更新规则",
    },
    "delete_rule": {
        "en": "Delete Rule",
        "zh": "删除规则",
    },
    "generate_rule_from_description": {
        "en": "Generate Rule from Description",
        "zh": "根据描述生成规则",
    },
    "get_rule_stats": {
        "en": "View Rule Statistics",
        "zh": "查看规则统计",
    },
    "get_adapters_status": {
        "en": "View Adapter Status",
        "zh": "查看适配器状态",
    },
    "start_adapters": {
        "en": "Start Adapters",
        "zh": "启动适配器",
    },
    "stop_adapters": {
        "en": "Stop Adapters",
        "zh": "停止适配器",
    },
    "get_queues": {
        "en": "View Message Queues",
        "zh": "查看消息队列",
    },
    "clear_message_history": {
        "en": "Clear Message History",
        "zh": "清除消息历史",
    },
    "get_system_logs": {
        "en": "View System Logs",
        "zh": "查看系统日志",
    },
    "clear_system_logs": {
        "en": "Clear System Logs",
        "zh": "清除系统日志",
    },
    "get_user_profiles": {
        "en": "View User Profiles",
        "zh": "查看用户画像列表",
    },
    "get_user_profile": {
        "en": "View User Profile Detail",
        "zh": "查看用户画像详情",
    },
    "get_settings": {
        "en": "View Settings",
        "zh": "查看系统设置",
    },
    "update_settings": {
        "en": "Update Settings",
        "zh": "更新系统设置",
    },
    "get_notifications_config": {
        "en": "View Notification Settings",
        "zh": "查看通知设置",
    },
    "get_llm_config": {
        "en": "View LLM Configuration",
        "zh": "查看 LLM 配置",
    },
    "check_llm_health": {
        "en": "Check LLM Health",
        "zh": "检查 LLM 健康状态",
    },
    "check_system_health": {
        "en": "Check System Health",
        "zh": "检查系统健康状态",
    },
}

SYSTEM_PROMPT = """\
你是 ChatGuardian 后台管理智能助手。你的职责是帮助管理员通过自然语言对话完成系统的各项管理操作。

## 你的能力

你可以帮助用户完成以下操作：

### 📊 信息查询
- 查看仪表盘概览（规则数、触发数、消息数等）
- 查看和搜索检测规则列表
- 查看规则触发统计数据
- 查看消息队列（待处理和历史消息）
- 查看系统日志
- 查看用户画像列表和详情
- 查看当前系统设置
- 查看通知配置（邮件、Bark）
- 查看 LLM 配置
- 检查 LLM 和系统健康状态

### 🛡️ 规则管理
- 创建新的检测规则
- 修改现有规则（名称、描述、阈值、启用状态等）
- 删除规则
- 根据自然语言描述自动生成规则

### ⚙️ 系统管理
- 启动/停止消息适配器
- 修改系统设置（LLM 配置、检测参数、通知设置等）
- 清除消息历史
- 清除系统日志

## 使用规则

1. 当用户的请求需要操作系统时，你应该调用相应的工具来执行操作，而不是仅给出说明。
2. 在执行可能影响系统的操作（如删除规则、清除日志）前，先向用户确认。
3. 查询信息时，将结果以清晰、有条理的方式呈现给用户。
4. 如果操作失败，向用户解释原因并给出建议。
5. 面向没有技术背景的用户，用通俗易懂的语言进行交流。
6. 以 Markdown 格式输出回复，使内容清晰美观。

## 注意事项

- 你无法直接修改数据库，所有操作都通过工具函数完成。
- 部分高危操作（如清除全部消息）需要确认。
- 当前已配置的 LLM 后端和模型信息可以通过工具查询。
"""


def _build_agent_tools(operations: Any) -> list:
    """基于 ChatGuardianOperations 构建 LangChain 工具列表。"""

    @tool
    async def get_dashboard() -> dict:
        """获取仪表盘概览数据，包括规则总数、启用规则数、今日触发次数、触发率、今日处理消息数和 LLM 状态。"""
        return await operations.get_dashboard()

    @tool
    async def get_rules_list() -> list:
        """获取所有检测规则的列表，每条规则包含 ID、名称、描述、匹配器、阈值、启用状态等信息。"""
        rules = await operations.list_rules()
        return [r.model_dump() if hasattr(r, "model_dump") else r for r in rules]

    @tool
    async def create_or_update_rule(
        rule_id: str,
        name: str,
        description: str,
        score_threshold: float = 0.6,
        enabled: bool = True,
        topic_hints: list[str] | None = None,
    ) -> dict:
        """创建或更新一条检测规则。如果 rule_id 已存在则更新，否则创建新规则。

        Args:
            rule_id: 规则唯一标识符。创建新规则时可以使用有意义的英文 ID。
            name: 规则名称，简短描述规则的用途。
            description: 规则的详细描述，说明何时应该触发此规则。
            score_threshold: 触发阈值，范围 0-1，默认 0.6。越高越严格。
            enabled: 是否启用此规则，默认启用。
            topic_hints: 主题关键词提示列表，用于辅助匹配。
        """
        from chat_guardian.domain import DetectionRule, MatchAll

        rule = DetectionRule(
            rule_id=rule_id,
            name=name,
            description=description,
            matcher=MatchAll(),
            topic_hints=topic_hints or [],
            score_threshold=score_threshold,
            enabled=enabled,
        )
        result = await operations.upsert_rule(rule)
        return result.model_dump() if hasattr(result, "model_dump") else result

    @tool
    async def delete_rule(rule_id: str) -> dict:
        """删除指定 ID 的检测规则。

        Args:
            rule_id: 要删除的规则 ID。
        """
        try:
            return await operations.delete_rule(rule_id)
        except Exception as exc:
            return {"error": str(exc)}

    @tool
    async def generate_rule_from_description(description: str) -> dict:
        """根据自然语言描述自动生成一条检测规则。系统会利用 LLM 理解描述并创建结构化规则。

        Args:
            description: 用自然语言描述你想要的规则，例如 "当有人发送广告链接时触发"。
        """
        from chat_guardian.api.schemas import RuleGenerateRequest

        try:
            req = RuleGenerateRequest(utterance=description)
            result = await operations.generate_rule(req)
            return result.model_dump() if hasattr(result, "model_dump") else result
        except Exception as exc:
            return {"error": str(exc)}

    @tool
    async def get_rule_stats() -> dict:
        """获取规则触发统计数据，包括每条规则的触发次数和触发记录详情。"""
        return await operations.get_rule_stats()

    @tool
    async def get_adapters_status() -> list:
        """获取所有消息适配器（如 Telegram、OneBot 等）的运行状态。"""
        return await operations.get_adapters_status()

    @tool
    async def start_adapters() -> dict:
        """启动所有已启用的消息适配器。"""
        return await operations.start_adapters()

    @tool
    async def stop_adapters() -> dict:
        """停止所有正在运行的消息适配器。"""
        return await operations.stop_adapters()

    @tool
    async def get_queues() -> dict:
        """获取消息队列信息，包括待处理消息和历史消息。"""
        return await operations.get_queues()

    @tool
    async def clear_message_history() -> dict:
        """清空所有历史消息记录。此操作不可撤销。"""
        return await operations.delete_history_messages({"clear_all": True})

    @tool
    async def get_system_logs(limit: int = 50) -> list:
        """获取最近的系统运行日志。

        Args:
            limit: 返回的最大日志条数，默认 50。
        """
        return await operations.get_logs(limit=limit)

    @tool
    async def clear_system_logs() -> dict:
        """清空系统日志缓冲区。此操作不可撤销。"""
        return await operations.clear_logs()

    @tool
    async def get_user_profiles() -> list:
        """获取所有用户画像列表。"""
        profiles = await operations.list_user_profiles()
        return [p.model_dump() if hasattr(p, "model_dump") else p for p in profiles]

    @tool
    async def get_user_profile(user_id: str) -> dict:
        """获取指定用户的详细画像信息。

        Args:
            user_id: 用户 ID。
        """
        try:
            profile = await operations.get_user_profile(user_id)
            return profile.model_dump() if hasattr(profile, "model_dump") else profile
        except Exception as exc:
            return {"error": str(exc)}

    @tool
    async def get_settings() -> dict:
        """获取当前所有系统设置。"""
        return await operations.get_settings()

    @tool
    async def update_settings(updates: dict) -> dict:
        """更新系统设置。可以一次更新多个设置项。设置会立即生效并保存到数据库。

        Args:
            updates: 要更新的设置键值对，例如 {"llm_langchain_model": "gpt-4o", "llm_langchain_temperature": 0.5}。
        """
        try:
            return await operations.update_settings(updates)
        except Exception as exc:
            return {"error": str(exc)}

    @tool
    async def get_notifications_config() -> dict:
        """获取通知配置信息，包括邮件通知和 Bark 推送通知的设置。"""
        return operations.get_notifications_config()

    @tool
    async def get_llm_config() -> dict:
        """获取当前 LLM（大语言模型）的配置信息，包括后端类型、模型名称、API 地址等。"""
        return operations.get_llm_config()

    @tool
    async def check_llm_health(do_ping: bool = True) -> dict:
        """检查 LLM 服务的健康状态，可选择是否执行 ping 测试。

        Args:
            do_ping: 是否执行 ping 连通性测试，默认 True。
        """
        return await operations.llm_health(do_ping=do_ping)

    @tool
    async def check_system_health() -> dict:
        """检查系统整体健康状态。"""
        return await operations.health()

    return [
        get_dashboard,
        get_rules_list,
        create_or_update_rule,
        delete_rule,
        generate_rule_from_description,
        get_rule_stats,
        get_adapters_status,
        start_adapters,
        stop_adapters,
        get_queues,
        clear_message_history,
        get_system_logs,
        clear_system_logs,
        get_user_profiles,
        get_user_profile,
        get_settings,
        update_settings,
        get_notifications_config,
        get_llm_config,
        check_llm_health,
        check_system_health,
    ]


def _build_chat_model() -> ChatOpenAI | ChatOllama:
    """根据当前设置构建用于 Agent 的 Chat 模型。"""
    backend = settings.llm_langchain_backend.strip().lower()
    if backend == "openai_compatible":
        api_key = settings.llm_langchain_api_key or "chat-guardian-dev-placeholder-key"
        return ChatOpenAI(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            base_url=settings.llm_langchain_api_base,
            api_key=api_key,
            streaming=True,
        )
    elif backend == "ollama":
        return ChatOllama(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            base_url=settings.llm_ollama_base_url,
        )
    raise ValueError(f"Unsupported llm_langchain_backend: {settings.llm_langchain_backend}")


class AdminAgent:
    """后台管理智能体，基于 LangChain 的 tool-calling agent。"""

    def __init__(self, operations: Any):
        self.operations = operations
        self.tools = _build_agent_tools(operations)
        self._tools_by_name = {t.name: t for t in self.tools}

    def _get_model(self) -> ChatOpenAI | ChatOllama:
        """每次调用时重新构建模型，确保使用最新配置。"""
        model = _build_chat_model()
        return model.bind_tools(self.tools)

    async def stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[dict[str, Any]]:
        """流式处理用户消息，返回事件流。

        事件类型:
        - {"type": "token", "content": str}  - AI 文本 token
        - {"type": "tool_call_start", "tool_call_id": str, "name": str, "display_name": str}
        - {"type": "tool_call_args", "tool_call_id": str, "args_delta": str}
        - {"type": "tool_result", "tool_call_id": str, "name": str, "display_name": str, "result": Any}
        - {"type": "error", "content": str}
        - {"type": "done"}
        """
        # 构建 LangChain 消息列表
        lc_messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        model = self._get_model()
        max_iterations = 10  # 防止无限循环

        for _iteration in range(max_iterations):
            try:
                # 流式调用模型
                full_response = AIMessage(content="")
                tool_calls_buffer: dict[int, dict] = {}

                async for chunk in model.astream(lc_messages):
                    if not isinstance(chunk, AIMessageChunk):
                        continue

                    # 处理文本内容
                    if chunk.content:
                        text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if text:
                            yield {"type": "token", "content": text}

                    # 处理工具调用
                    if chunk.tool_call_chunks:
                        for tc_chunk in chunk.tool_call_chunks:
                            idx = tc_chunk.get("index", 0) if isinstance(tc_chunk, dict) else getattr(tc_chunk, "index", 0)
                            tc_id = tc_chunk.get("id") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "id", None)
                            tc_name = tc_chunk.get("name") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "name", None)
                            tc_args = tc_chunk.get("args") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "args", None)

                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": tc_id or "",
                                    "name": tc_name or "",
                                    "args_str": "",
                                }

                            buf = tool_calls_buffer[idx]
                            if tc_id:
                                buf["id"] = tc_id
                            if tc_name:
                                buf["name"] = tc_name
                                display = TOOL_DISPLAY_NAMES.get(tc_name, {})
                                yield {
                                    "type": "tool_call_start",
                                    "tool_call_id": buf["id"],
                                    "name": tc_name,
                                    "display_name": display.get("zh", display.get("en", tc_name)),
                                }
                            if tc_args:
                                buf["args_str"] += tc_args
                                yield {
                                    "type": "tool_call_args",
                                    "tool_call_id": buf["id"],
                                    "args_delta": tc_args,
                                }

                # 收集完整的 tool_calls
                tool_calls = []
                for _idx, buf in sorted(tool_calls_buffer.items()):
                    args_str = buf["args_str"]
                    try:
                        parsed_args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        parsed_args = {}
                    tool_calls.append({
                        "id": buf["id"],
                        "name": buf["name"],
                        "args": parsed_args,
                    })

                if not tool_calls:
                    # 没有工具调用，对话完成
                    yield {"type": "done"}
                    return

                # 构造包含 tool_calls 的 AI 消息并加入历史
                ai_msg = AIMessage(
                    content="",
                    tool_calls=[
                        {"id": tc["id"], "name": tc["name"], "args": tc["args"], "type": "tool_call"}
                        for tc in tool_calls
                    ],
                )
                lc_messages.append(ai_msg)

                # 执行工具调用
                for tc in tool_calls:
                    tool_name = tc["name"]
                    tool_fn = self._tools_by_name.get(tool_name)
                    display = TOOL_DISPLAY_NAMES.get(tool_name, {})
                    display_name = display.get("zh", display.get("en", tool_name))

                    if not tool_fn:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        try:
                            result = await tool_fn.ainvoke(tc["args"])
                        except Exception as exc:
                            logger.warning(f"Tool {tool_name} failed: {exc}")
                            result = {"error": str(exc)}

                    # 序列化结果
                    if hasattr(result, "model_dump"):
                        result = result.model_dump()

                    yield {
                        "type": "tool_result",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "display_name": display_name,
                        "result": result,
                    }

                    # 添加工具结果消息
                    result_str = json.dumps(result, ensure_ascii=False, default=str) if not isinstance(result, str) else result
                    lc_messages.append(
                        ToolMessage(content=result_str, tool_call_id=tc["id"])
                    )

                # 继续循环，让模型处理工具结果

            except Exception as exc:
                logger.error(f"Agent stream error: {exc}")
                yield {"type": "error", "content": str(exc)}
                yield {"type": "done"}
                return

        # 达到最大迭代次数
        yield {"type": "error", "content": "达到最大工具调用次数限制"}
        yield {"type": "done"}
