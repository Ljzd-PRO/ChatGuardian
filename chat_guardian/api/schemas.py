"""
API 层请求与响应的 Pydantic 模型定义。

这些模型用于 FastAPI 路由的输入/输出验证与序列化。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionTargetPayload(BaseModel):
    """
    会话匹配请求负载。

    Attributes:
        mode: 匹配模式（"exact" 或 "fuzzy"）。
        query: 要匹配的会话标识或描述。
    """

    mode: str = Field(default="fuzzy")
    query: str


class RuleParameterPayload(BaseModel):
    """
    规则参数规范的序列化模型。

    Attributes:
        key: 参数键名。
        description: 参数描述。
        required: 是否为必填参数。
    """

    key: str
    description: str
    required: bool = True


class RulePayload(BaseModel):
    """
    规则的完整序列化表示（用于创建/查询）。

    Attributes:
        rule_id: 规则唯一标识。
        name: 规则名称。
        description: 规则描述。
        target_session: 匹配目标会话。
        topic_hints: 主题关键词提示。
        score_threshold: 触发阈值。
        enabled: 是否启用。
        parameters: 触发时需要提取的参数规范列表。
    """

    rule_id: str
    name: str
    description: str
    target_session: SessionTargetPayload
    topic_hints: list[str] = Field(default_factory=list)
    score_threshold: float = 0.6
    enabled: bool = True
    parameters: list[RuleParameterPayload] = Field(default_factory=list)


class MessagePayload(BaseModel):
    """
    消息负载结构，表示单条聊天消息。

    Attributes:
        message_id: 消息唯一 ID。
        chat_id: 会话/群组 ID。
        sender_id: 发送者用户 ID。
        sender_name: 发送者昵称。
        contents: 消息内容片段列表。
        reply_from: 回复的消息。
        timestamp: 消息时间戳。
    """

    message_id: str
    chat_id: str
    sender_id: str
    sender_name: str | None = None
    contents: list["MessageContentPayload"] = Field(default_factory=list)
    reply_from: "MessagePayload | None" = None
    timestamp: datetime


class MessageContentPayload(BaseModel):
    """
    消息内容片段。

    Attributes:
        type: 片段类型（text/image/mention）。
        text: 文本内容。
        image_url: 图片地址。
        mention_user_id: 被提及用户 ID。
    """

    type: str
    text: str | None = None
    image_url: str | None = None
    mention_user_id: str | None = None


class DetectRequest(BaseModel):
    """
    /detect 路由的请求模型。

    Attributes:
        platform: 消息平台。
        chat_type: 聊天类型。
        is_from_self: 是否为自身消息。
        message: 消息负载。
    """

    platform: str
    chat_type: str
    is_from_self: bool = False
    message: MessagePayload


class DetectResponse(BaseModel):
    """
    /detect 路由的响应模型。

    Attributes:
        event_id: 检测事件 ID。
        triggered_rule_ids: 被触发的规则 ID 列表。
        notified_count: 通知数量。
    """

    event_id: str
    triggered_rule_ids: list[str]
    notified_count: int


class FeedbackPayload(BaseModel):
    """
    提交反馈的请求模型。

    Attributes:
        rule_id: 规则 ID。
        event_id: 事件 ID。
        score: 评分（1-5）。
        comment: 文字说明。
    """

    rule_id: str
    event_id: str
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class RuleGenerateRequest(BaseModel):
    """
    一句话生成规则的请求负载。

    Attributes:
        utterance: 用户的一句话描述。
        use_external: 是否调用外部生成后端。
        override_system_prompt: 可选系统提示词覆盖。
    """

    utterance: str
    use_external: bool = False
    override_system_prompt: str | None = None


class SuggestResponse(BaseModel):
    """
    建议返回模型，包含若干建议文本。

    Attributes:
        suggestions: 建议文本列表。
    """

    suggestions: list[str]


MessagePayload.model_rebuild()
