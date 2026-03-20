"""
领域模型（domain objects）。

本模块定义了消息事件、规则、检测结果、用户记忆等核心数据结构，
这些类型用于在系统各层（接入、规则引擎、LLM 交互、存储）之间传递数据。
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from chat_guardian.matcher import MatchAll, MatcherUnion

if TYPE_CHECKING:
    pass


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


class UserInfo(BaseModel):
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


class MessageContent(BaseModel):
    """
    消息内容链中的单个片段。

    Attributes:
        type: 片段类型。
        text: 文本内容（type=text 时使用）。
        image_data: 图像二进制数据（type=image 时使用）。
        mention_user: 被提及用户（type=mention 时使用）。
    """

    type: ContentType
    text: str | None = None
    image_data: bytes | None = None
    mention_user: UserInfo | None = None
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    @staticmethod
    def generate_short_id(s: str | bytes, length: int = 5) -> str:
        """
        为字符串生成固定长度的短标识符

        Args:
            s: 原始字符串
            length: 标识符长度，默认5位

        Returns:
            固定长度的十六进制标识符（0-9, a-f），如需大写可转成upper()
        """
        s_bytes = s if isinstance(s, bytes) else s.encode('utf-8')
        hash_obj = hashlib.sha1(s_bytes)
        hash_hex = hash_obj.hexdigest()
        short_id = hash_hex[:length].upper()
        return short_id

    def __str__(self) -> str:
        if self.type == ContentType.TEXT and self.text:
            return self.text
        elif self.type == ContentType.IMAGE and self.image_data:
            return f"[image: {self.generate_short_id(self.image_data)}]"
        elif self.type == ContentType.MENTION and self.mention_user:
            return f"@{self.mention_user}"
        return ""


class ChatMessage(BaseModel):
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


class ChatEvent(BaseModel):
    """
    表示从消息平台流入的事件包装。

    Attributes:
        chat_type: 聊天类型（群/私聊）。
        chat_id: 会话 ID。
        message: `ChatMessage` 实例。
        platform: 消息平台标识（例如 nonebot、telegram）。
    """

    chat_type: ChatType
    chat_id: str
    message: ChatMessage
    platform: str


class RuleParameterSpec(BaseModel):
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


class DetectionRule(BaseModel):
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
    # noinspection PyTypeHints
    matcher: MatcherUnion = Field(default_factory=MatchAll)
    topic_hints: list[str] = Field(default_factory=list)
    score_threshold: float = 0.6
    enabled: bool = True
    parameters: list[RuleParameterSpec] = Field(default_factory=list)


class RuleDecision(BaseModel):
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


class DetectionResult(BaseModel):
    """
    单条规则在一次检测中的结果记录。

    Attributes:
        result_id: 结果唯一 ID。
        event_id: 事件 ID。
        rule_id: 规则 ID。
        adapter: 适配器名称（平台标识）。
        chat_type: 聊天类型（group/private）。
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
    adapter: str = ''
    chat_type: str = ''
    chat_id: str
    message_id: str
    decision: RuleDecision
    context_messages: list[ChatMessage]
    generated_at: datetime
    trigger_suppressed: bool = False
    suppression_reason: str | None = None


class InterestTopicStat(BaseModel):
    """
    某一话题的兴趣统计数据。

    Attributes:
        score: 参与次数（每次检测到参与则累加）。
        last_active: 最近活跃时间，格式为 YYYY-MM-DD HH:MM:SS。
        related_chat: 涉及该话题的群聊/会话 ID 列表。
        keywords: 该话题相关的核心关键词列表。
    """

    score: int = 0
    last_active: str = ""
    related_chat: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ActiveGroupStat(BaseModel):
    """
    用户在某群聊中的活跃统计数据。

    Attributes:
        group_id: 群聊/会话 ID。
        frequency: 累计发言次数。
        last_talk: 最近发言日期，格式为 YYYY-MM-DD。
    """

    group_id: str
    frequency: int = 0
    last_talk: str = ""


class RelatedTopicStat(BaseModel):
    """
    与某联系人在某话题下的互动统计。

    Attributes:
        score: 该话题下的参与次数。
        last_talk: 最近互动时间，格式为 YYYY-MM-DD HH:MM:SS。
    """

    score: int = 0
    last_talk: str = ""


class FrequentContactStat(BaseModel):
    """
    与某群友的互动统计数据。

    Attributes:
        name: 群友昵称（每次自动更新）。
        interaction_count: 总互动次数。
        last_interact: 最近互动时间，格式为 YYYY-MM-DD HH:MM:SS。
        related_topics: 和该群友常聊的话题，以话题名为键。
        related_groups: 和该群友共同活跃的群聊/会话 ID 列表。
    """

    name: str = ""
    interaction_count: int = 0
    last_interact: str = ""
    related_topics: dict[str, RelatedTopicStat] = Field(default_factory=dict)
    related_groups: list[str] = Field(default_factory=list)


class UserMemoryFact(BaseModel):
    """
    用户行为画像（由用户自己参与的会话持续累积生成）。

    Attributes:
        user_id: 用户 ID。
        user_name: 用户昵称（每次自动更新）。
        interests: 话题兴趣画像，以话题名为键。
        active_groups: 活跃群聊列表。
        frequent_contacts: 常联系群友，以用户 ID 为键。
    """

    user_id: str
    user_name: str = ""
    interests: dict[str, InterestTopicStat] = Field(default_factory=dict)
    active_groups: list[ActiveGroupStat] = Field(default_factory=list)
    frequent_contacts: dict[str, FrequentContactStat] = Field(default_factory=dict)


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
    lock: asyncio.Lock = dc_field(default_factory=asyncio.Lock)
    cooldown_task: asyncio.Task[None] | None = None
    timeout_task: asyncio.Task[None] | None = None
