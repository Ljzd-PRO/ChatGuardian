from chat_guardian.adapters.onebot import OneBotAdapter, OneBotAdapterConfig
from chat_guardian.domain import ContentType


async def test_build_message_parses_at_segment_to_userinfo() -> None:
    adapter = OneBotAdapter(OneBotAdapterConfig())
    event = {
        "self_id": 2484316894,
        "user_id": 986306709,
        "time": 1772812747,
        "message_id": 712780548,
        "message_type": "group",
        "sender": {
            "user_id": 986306709,
            "nickname": "gugugu",
        },
        "message": [
            {"type": "at", "data": {"qq": "1040351227"}},
            {"type": "text", "data": {"text": "哥我毕业一个月三千"}},
        ],
        "group_id": 65840633,
    }

    message = await adapter._build_message(event)

    assert message is not None
    mention_items = [item for item in message.contents if item.type == ContentType.MENTION]
    assert len(mention_items) == 1
    assert mention_items[0].mention_user is not None
    assert mention_items[0].mention_user.user_id == "1040351227"
