from __future__ import annotations

from chat_guardian.matcher import MatchAll, MatchChatInfo, MatchSender


def build_rule_matcher(chat_id: str | None, users: list[str]):
    chat_matcher = MatchAll() if not chat_id else MatchChatInfo(chat_id=chat_id)
    if not users:
        return chat_matcher

    user_matcher = MatchSender(user_id=users[0])
    for user_id in users[1:]:
        user_matcher = user_matcher | MatchSender(user_id=user_id)
    return chat_matcher & user_matcher
