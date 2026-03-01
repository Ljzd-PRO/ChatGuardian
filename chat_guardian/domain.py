"""
领域模型（domain objects）。

本模块定义了消息事件、规则、检测结果、用户记忆与反馈等核心数据结构，
这些类型用于在系统各层（接入、规则引擎、LLM 交互、存储）之间传递数据。
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic.dataclasses import dataclass
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from chat_guardian.matcher import MatcherBase


class ChatType(str, Enum):
    """
    聊天类型枚举。

    Attributes:
        GROUP: 群聊。
        PRIVATE: 私聊。
    """

    GROUP = "group"
    PRIVATE = "private"


class ContentType(str, Enum):
    """
    消息内容片段类型。

    Attributes:
        TEXT: 文本。
        IMAGE: 图片。
        MENTION: 提及。
    """

    TEXT = "text"
    IMAGE = "image"
    MENTION = "mention"


@dataclass(slots=True)
class UserInfo:
    """
    用户信息结构。

    Attributes:
        user_id: 用户 ID。
        display_name: 显示名称。
    """

    user_id: str
    display_name: str | None = None

    def __str__(self) -> str:
        return self.display_name or self.user_id


@dataclass(slots=True)
class MessageContent:
    """
    消息内容链中的单个片段。

    Attributes:
        type: 片段类型。
        text: 文本内容（type=text 时使用）。
        image_url: 图片地址（type=image 时使用）。
        mention_user: 被提及用户（type=mention 时使用）。
    """

    type: ContentType
    text: str | None = None
    image_url: str | None = None
    mention_user: UserInfo | None = None

    @staticmethod
    def _generate_short_id(s: str, length: int = 5) -> str:
        """
        为字符串生成固定长度的短标识符

        Args:
            s: 原始字符串
            length: 标识符长度，默认5位

        Returns:
            固定长度的十六进制标识符（0-9, a-f），如需大写可转成upper()
        """
        s_bytes = s.encode('utf-8')
        hash_obj = hashlib.sha1(s_bytes)
        hash_hex = hash_obj.hexdigest()
        short_id = hash_hex[:length].upper()
        return short_id

    def __str__(self) -> str:
        if self.type == ContentType.TEXT and self.text:
            return self.text
        elif self.type == ContentType.IMAGE and self.image_url:
            return f"[image: {self._generate_short_id(self.image_url)}]"
        elif self.type == ContentType.MENTION and self.mention_user:
            return f"@{self.mention_user}"
        return ""


# noinspection PyDataclass
@dataclass(slots=True)
class ChatMessage:
    """
    表示一条聊天消息的结构。

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
    contents: list[MessageContent] = Field(default_factory=list)
    reply_from: ChatMessage | None = None

    def __str__(self) -> str:
        return "".join(str(content) for content in self.contents)


@dataclass(slots=True)
class ChatEvent:
    """
    表示从消息平台流入的事件包装。

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


def _default_matcher() -> "MatcherBase":
    from chat_guardian.matcher import MatchAll

    return MatchAll()


@dataclass(slots=True)
class RuleParameterSpec:
    """
    规则参数规范，描述规则在触发时应当提取的结构化字段。

    Attributes:
        key: 参数键名。
        description: 参数描述。
        required: 是否为必填参数。
    """

    key: str
    description: str
    required: bool = True


# noinspection PyDataclass
@dataclass(slots=True)
class DetectionRule:
    """
    检测规则主体。

    Attributes:
        rule_id: 规则唯一标识。
        name: 规则名称。
        description: 规则描述文本。
        matcher: 规则匹配器对象，使用 `matcher.matches(event)` 进行事件筛选。
        topic_hints: 主题关键词提示，用于轻量匹配或作为 LLM 提示。
        score_threshold: 触发阈值（0-1）。
        enabled: 是否启用。
        parameters: 触发时需要提取的参数规范列表。
    """

    rule_id: str
    name: str
    description: str
    matcher: object = Field(default_factory=_default_matcher)
    topic_hints: list[str] = Field(default_factory=list)
    score_threshold: float = 0.6
    enabled: bool = True
    parameters: list[RuleParameterSpec] = Field(default_factory=list)


# noinspection PyDataclass
@dataclass(slots=True)
class RuleDecision:
    """
    单条规则在一次事件评估中的决策结果。

    Attributes:
        rule_id: 规则 ID。
        triggered: 是否被触发。
        confidence: 置信度。
        reason: 触发原因。
        extracted_params: 提取的参数。
    """

    rule_id: str
    triggered: bool
    confidence: float
    reason: str
    extracted_params: dict[str, str] = Field(default_factory=dict)


@dataclass(slots=True)
class DetectionResult:
    """
    单条规则在一次检测中的结果记录。

    Attributes:
        result_id: 结果唯一 ID。
        event_id: 事件 ID。
        rule_id: 规则 ID。
        chat_id: 会话 ID。
        message_id: 消息 ID。
        decision: 规则决策。
        context_messages: 检测时的上下文消息。
        generated_at: 生成时间。
        trigger_suppressed: 是否被抑制。
        suppression_reason: 抑制原因。
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
    """
    表示系统记忆的一条事实（由用户自己参与的会话生成）。

    Attributes:
        user_id: 用户 ID。
        chat_id: 会话 ID。
        topic: 主题。
        counterpart_user_ids: 对方用户 ID 列表。
        confidence: 置信度。
        captured_at: 采集时间。
    """

    user_id: str
    chat_id: str
    topic: str
    counterpart_user_ids: list[str]
    confidence: float
    captured_at: datetime


@dataclass(slots=True)
class Feedback:
    """
    用户对一次规则命中后的反馈记录。

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
