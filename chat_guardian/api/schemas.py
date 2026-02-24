"""
API 层请求与响应的 Pydantic 模型定义。

这些模型用于 FastAPI 路由的输入/输出验证与序列化。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionTargetPayload(BaseModel):
    """会话匹配请求负载。

    Attributes:
        mode: 匹配模式（"exact" 或 "fuzzy"）。
        query: 要匹配的会话标识或描述。
    """

    mode: str = Field(default="fuzzy")
    query: str


class RuleParameterPayload(BaseModel):
    """规则参数规范的序列化模型。"""

    key: str
    description: str
    required: bool = True


class RulePayload(BaseModel):
    """规则的完整序列化表示（用于创建/查询）。"""

    rule_id: str
    name: str
    description: str
    target_session: SessionTargetPayload
    topic_hints: list[str] = Field(default_factory=list)
    score_threshold: float = 0.6
    enabled: bool = True
    parameters: list[RuleParameterPayload] = Field(default_factory=list)


class MessagePayload(BaseModel):
    """消息负载结构，表示单条聊天消息。"""

    message_id: str
    chat_id: str
    sender_id: str
    sender_name: str | None = None
    contents: list["MessageContentPayload"] = Field(default_factory=list)
    reply_from: "MessagePayload | None" = None
    timestamp: datetime


class MessageContentPayload(BaseModel):
    """消息内容片段。"""

    type: str
    text: str | None = None
    image_url: str | None = None
    mention_user_id: str | None = None


class DetectRequest(BaseModel):
    """/detect 路由的请求模型。"""

    platform: str
    chat_type: str
    is_from_self: bool = False
    message: MessagePayload


class DetectResponse(BaseModel):
    """/detect 路由的响应模型。"""

    event_id: str
    triggered_rule_ids: list[str]
    notified_count: int


class FeedbackPayload(BaseModel):
    """提交反馈的请求模型。"""

    rule_id: str
    event_id: str
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RuleGenerateRequest(BaseModel):
    """一句话生成规则的请求负载。

    - `utterance`: 用户的一句话描述。
    - `use_external`: 是否调用外部生成后端。
    - `override_system_prompt`: 可选系统提示词覆盖。
    """

    utterance: str
    use_external: bool = False
    override_system_prompt: str | None = None


class SuggestResponse(BaseModel):
    """建议返回模型，包含若干建议文本。"""

    suggestions: list[str]


MessagePayload.model_rebuild()
