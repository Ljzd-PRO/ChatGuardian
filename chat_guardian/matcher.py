from abc import ABC
from typing import Optional, Literal

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass

from chat_guardian.domain import ChatEvent, ContentType


class MatcherBase(ABC):
    """所有匹配器的基类，支持使用 & 和 | 运算符组合规则"""

    def __and__(self, other: "MatcherBase") -> "AndMatcher":
        """使用 & 运算符创建"与"规则链"""
        if isinstance(self, AndMatcher):
            return AndMatcher(matchers=self.matchers + [other])
        return AndMatcher(matchers=[self, other])

    def __or__(self, other: "MatcherBase") -> "OrMatcher":
        """使用 | 运算符创建"或"规则链"""
        if isinstance(self, OrMatcher):
            return OrMatcher(matchers=self.matchers + [other])
        return OrMatcher(matchers=[self, other])

    def matches(self, event: "ChatEvent") -> bool:
        """检查事件是否匹配规则，需在子类中实现具体逻辑"""
        raise NotImplementedError("MatcherBase is an abstract class and cannot be instantiated directly")


@dataclass(slots=True, config=ConfigDict(arbitrary_types_allowed=True))
class AndMatcher(MatcherBase):
    """表示多个匹配规则的"与"关系"""
    matchers: list[MatcherBase]

    def __and__(self, other: MatcherBase) -> "AndMatcher":
        """继续添加"与"条件"""
        return AndMatcher(matchers=self.matchers + [other])

    def matches(self, event: "ChatEvent") -> bool:
        """事件必须满足所有规则才匹配成功"""
        return all(matcher.matches(event) for matcher in self.matchers)


@dataclass(slots=True, config=ConfigDict(arbitrary_types_allowed=True))
class OrMatcher(MatcherBase):
    """表示多个匹配规则的"或"关系"""
    matchers: list[MatcherBase]

    def __or__(self, other: MatcherBase) -> "OrMatcher":
        """继续添加"或"条件"""
        return OrMatcher(matchers=self.matchers + [other])

    def matches(self, event: "ChatEvent") -> bool:
        """事件满足任一规则即匹配成功"""
        return any(matcher.matches(event) for matcher in self.matchers)


@dataclass(slots=True)
class MatchAll(MatcherBase):
    """匹配所有事件的规则"""
    def matches(self, events: "ChatEvent") -> bool:
        return True

@dataclass(slots=True)
class _MatchUserInfo(MatcherBase):
    user_id: Optional[str] = None
    display_name: Optional[str] = None

    def matches(self, event: "ChatEvent") -> bool:
        raise NotImplementedError("This is a base class for user info matchers and should not be used directly")


@dataclass(slots=True)
class MatchSender(_MatchUserInfo):
    def matches(self, event: "ChatEvent") -> bool:
        if not event.message or not event.message.sender_id:
            return False
        if self.user_id and self.user_id != event.message.sender_id:
            return False
        if self.display_name and self.display_name != (event.message.sender_name or ""):
            return False
        return True

@dataclass(slots=True)
class MatchMention(_MatchUserInfo):
    def matches(self, event: "ChatEvent") -> bool:
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

@dataclass(slots=True)
class MatchChatInfo(MatcherBase):
    chat_id: str

    def matches(self, event: "ChatEvent") -> bool:
        return event.chat_id == self.chat_id

@dataclass(slots=True)
class MatchChatType(MatcherBase):
    type: Literal["group", "private"]

    def matches(self, event: "ChatEvent") -> bool:
        return event.chat_type.value == self.type

@dataclass(slots=True)
class MatchAdapter(MatcherBase):
    adapter_name: str

    def matches(self, event: "ChatEvent") -> bool:
        return event.platform == self.adapter_name
