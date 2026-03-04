from abc import ABC
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from chat_guardian.domain import ChatEvent, ContentType


class Matcher(BaseModel, ABC):
    """所有匹配器的基类，支持使用 & 和 | 运算符组合规则"""

    def __and__(self, other: "Matcher") -> "AndMatcher":
        """使用 & 运算符创建"与"规则链"""
        if isinstance(self, AndMatcher):
            return AndMatcher(matchers=self.matchers + [other])
        return AndMatcher(matchers=[self, other])

    def __or__(self, other: "Matcher") -> "OrMatcher":
        """使用 | 运算符创建"或"规则链"""
        if isinstance(self, OrMatcher):
            return OrMatcher(matchers=self.matchers + [other])
        return OrMatcher(matchers=[self, other])

    def __invert__(self) -> "NotMatcher":
        """使用 ~ 运算符创建"非"规则"""
        return NotMatcher(matcher=self)

    def matches(self, event: ChatEvent) -> bool:
        """检查事件是否匹配规则，需在子类中实现具体逻辑"""
        raise NotImplementedError("MatcherBase is an abstract class and cannot be instantiated directly")


class AndMatcher(Matcher):
    """表示多个匹配规则的"与"关系"""
    type: Literal["and"] = "and"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    matchers: list["MatcherUnion"] = Field(default_factory=list)

    def __and__(self, other: Matcher) -> "AndMatcher":
        """继续添加"与"条件"""
        return AndMatcher(matchers=self.matchers + [other])

    def matches(self, event: ChatEvent) -> bool:
        """事件必须满足所有规则才匹配成功"""
        return all(matcher.matches(event) for matcher in self.matchers)


class OrMatcher(Matcher):
    """表示多个匹配规则的"或"关系"""
    type: Literal["or"] = "or"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    matchers: list["MatcherUnion"] = Field(default_factory=list)

    def __or__(self, other: Matcher) -> "OrMatcher":
        """继续添加"或"条件"""
        return OrMatcher(matchers=self.matchers + [other])

    def matches(self, event: ChatEvent) -> bool:
        """事件满足任一规则即匹配成功"""
        return any(matcher.matches(event) for matcher in self.matchers)


class NotMatcher(Matcher):
    """表示单个匹配规则的"非"关系"""
    type: Literal["not"] = "not"
    model_config = ConfigDict(arbitrary_types_allowed=True)
    matcher: "MatcherUnion" = Field(default_factory=lambda: MatchAll())

    def matches(self, event: ChatEvent) -> bool:
        """事件满足子规则时返回 False，否则返回 True"""
        return not self.matcher.matches(event)


class MatchAll(Matcher):
    """匹配所有事件的规则"""
    type: Literal["all"] = "all"

    def matches(self, events: ChatEvent) -> bool:
        return True


class _MatchUserInfo(Matcher):
    user_id: Optional[str] = None
    display_name: Optional[str] = None

    def matches(self, event: ChatEvent) -> bool:
        raise NotImplementedError("This is a base class for user info matchers and should not be used directly")


class MatchSender(_MatchUserInfo):
    type: Literal["sender"] = "sender"

    def matches(self, event: ChatEvent) -> bool:
        if not event.message or not event.message.sender_id:
            return False
        if self.user_id and self.user_id != event.message.sender_id:
            return False
        if self.display_name and self.display_name != (event.message.sender_name or ""):
            return False
        return True


class MatchMention(_MatchUserInfo):
    type: Literal["mention"] = "mention"

    def matches(self, event: ChatEvent) -> bool:
        if not event.message or not event.message.contents:
            return False
        for content in event.message.contents:
            if content.type == ContentType.MENTION and content.mention_user:
                if self.user_id and self.user_id != content.mention_user.user_id:
                    continue
                if self.display_name and content.mention_user.display_name and self.display_name != content.mention_user.display_name:
                    continue
                return True
        return False


class MatchChatInfo(Matcher):
    type: Literal["chat"] = "chat"
    chat_id: str

    def matches(self, event: ChatEvent) -> bool:
        return event.chat_id == self.chat_id


class MatchChatType(Matcher):
    type: Literal["chat_type"] = "chat_type"
    chat_type: Literal["group", "private"]

    def matches(self, event: ChatEvent) -> bool:
        return event.chat_type.value == self.chat_type


class MatchAdapter(Matcher):
    type: Literal["adapter"] = "adapter"
    adapter_name: str

    def matches(self, event: ChatEvent) -> bool:
        return event.platform == self.adapter_name


# Discriminated union of all concrete Matcher types, used for JSON serialization/deserialization.
MatcherUnion = Annotated[
    Union[
        AndMatcher, OrMatcher, NotMatcher, MatchAll, MatchSender, MatchMention, MatchChatInfo, MatchChatType, MatchAdapter],
    Field(discriminator="type"),
]

# Resolve forward references in recursive models
AndMatcher.model_rebuild()
OrMatcher.model_rebuild()
NotMatcher.model_rebuild()
