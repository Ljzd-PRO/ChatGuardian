"""
领域模型（domain objects）。

本模块定义了消息事件、规则、检测结果、用户记忆与反馈等核心数据结构，
这些类型用于在系统各层（接入、规则引擎、LLM 交互、存储）之间传递数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ChatType(str, Enum):
    """聊天类型枚举。

    - GROUP: 群聊
    - PRIVATE: 私聊
    """

    GROUP = "group"
    PRIVATE = "private"


class ContentType(str, Enum):
    """消息内容片段类型。"""

    TEXT = "text"
    IMAGE = "image"
    MENTION = "mention"


@dataclass(slots=True)
class MessageContent:
    """消息内容链中的单个片段。

    Attributes:
        type: 片段类型。
        text: 文本内容（type=text 时使用）。
        image_url: 图片地址（type=image 时使用）。
        mention_user_id: 被提及用户 ID（type=mention 时使用）。
    """

    type: ContentType
    text: str | None = None
    image_url: str | None = None
    mention_user_id: str | None = None


@dataclass(slots=True)
class ChatMessage:
    """表示一条聊天消息的结构。

    Attributes:
        message_id: 消息唯一 ID（平台侧的标识）。
        chat_id: 会话/群组 ID。
        sender_id: 发送者用户 ID。
        sender_name: 可选的发送者昵称。
        contents: 内容链，可包含文本、图片、提及等片段。
        reply_from: 当前消息回复的消息（可为空，支持嵌套）。
        timestamp: 消息时间戳。
    """

    message_id: str
    chat_id: str
    sender_id: str
    sender_name: str | None
    timestamp: datetime
    contents: list[MessageContent] = field(default_factory=list)
    reply_from: ChatMessage | None = None

    def extract_plain_text(self) -> str:
        """提取消息内容链中的文本表示。

        Returns:
            将内容链可读化拼接后的文本。
        """
        parts: list[str] = []
        for item in self.contents:
            if item.type == ContentType.TEXT and item.text:
                parts.append(item.text)
            elif item.type == ContentType.MENTION and item.mention_user_id:
                parts.append(f"@{item.mention_user_id}")
            elif item.type == ContentType.IMAGE and item.image_url:
                parts.append("[image]")
        return " ".join(parts).strip()


@dataclass(slots=True)
class ChatEvent:
    """表示从消息平台流入的事件包装。

    Attributes:
        chat_type: 聊天类型（群/私聊）。
        chat_id: 会话 ID。
        message: `ChatMessage` 实例。
        platform: 消息平台标识（例如 nonebot、telegram）。
        is_from_self: 是否为当前用户/机器人自身发送的消息。
    """

    chat_type: ChatType
    chat_id: str
    message: ChatMessage
    platform: str
    is_from_self: bool = False


class SessionMatchMode(str, Enum):
    """会话匹配模式：精确或模糊。"""

    EXACT = "exact"
    FUZZY = "fuzzy"


@dataclass(slots=True)
class SessionTarget:
    """表示规则所匹配的目标会话。

    Attributes:
        mode: 匹配模式（`SessionMatchMode`）。
        query: 用于匹配的查询文本或 ID（取决于 mode）。
    """

    mode: SessionMatchMode
    query: str


@dataclass(slots=True)
class ParticipantConstraint:
    """参与者约束，用于限制规则只针对特定用户集合触发。"""

    participant_ids: set[str] = field(default_factory=set)
    relation_hint: str | None = None


@dataclass(slots=True)
class RuleParameterSpec:
    """规则参数规范，描述规则在触发时应当提取的结构化字段。"""

    key: str
    description: str
    required: bool = True


@dataclass(slots=True)
class DetectionRule:
    """检测规则主体。

    Attributes:
        rule_id: 规则唯一标识。
        name: 规则名称。
        description: 规则描述文本。
        target_session: `SessionTarget`，决定规则应用的会话范围。
        topic_hints: 主题关键词提示，用于轻量匹配或作为 LLM 提示。
        participant_constraint: 可选的参与者约束。
        score_threshold: 触发阈值（0-1）。
        enabled: 是否启用。
        parameters: 触发时需要提取的参数规范列表。
    """

    rule_id: str
    name: str
    description: str
    target_session: SessionTarget
    topic_hints: list[str] = field(default_factory=list)
    participant_constraint: ParticipantConstraint | None = None
    score_threshold: float = 0.6
    enabled: bool = True
    parameters: list[RuleParameterSpec] = field(default_factory=list)


@dataclass(slots=True)
class RuleDecision:
    """单条规则在一次事件评估中的决策结果。"""

    rule_id: str
    triggered: bool
    confidence: float
    reason: str
    extracted_params: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class DetectionResult:
    """单条规则在一次检测中的结果记录。

    说明：
    - 检测结果按 `rule_id` 归档；
    - 每条结果包含当次检测使用的上下文窗口；
    - 当命中被去重抑制时，`trigger_suppressed=True`。
    """

    result_id: str
    event_id: str
    rule_id: str
    chat_id: str
    message_id: str
    decision: RuleDecision
    context_messages: list[ChatMessage]
    generated_at: datetime
    trigger_suppressed: bool = False
    suppression_reason: str | None = None


@dataclass(slots=True)
class UserMemoryFact:
    """表示系统记忆的一条事实（由用户自己参与的会话生成）。"""

    user_id: str
    chat_id: str
    topic: str
    counterpart_user_ids: list[str]
    confidence: float
    captured_at: datetime


@dataclass(slots=True)
class Feedback:
    """用户对一次规则命中后的反馈记录。

    Attributes:
        rule_id: 对应规则 ID。
        event_id: 触发事件 ID。
        score: 评分（例如 1-5）。
        comment: 可选的文字说明。
        created_at: 反馈时间。
    """

    rule_id: str
    event_id: str
    score: int
    comment: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
