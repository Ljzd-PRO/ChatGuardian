"""Tests for the new user profile-based UserMemoryFact design and SelfMessageMemoryService."""

from datetime import datetime

from chat_guardian.domain import (
    ActiveGroupStat,
    ChatEvent,
    ChatMessage,
    ChatType,
    ContentType,
    FrequentContactStat,
    InterestTopicStat,
    MessageContent,
    RelatedTopicStat,
    UserMemoryFact,
)
from chat_guardian.repositories import MemoryRepository
from chat_guardian.services import ContextWindowService, SelfMessageMemoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_event(sender_id: str = "u-self", chat_id: str = "g-1", is_from_self: bool = True) -> ChatEvent:
    message = ChatMessage(
        message_id="m-1",
        chat_id=chat_id,
        sender_id=sender_id,
        sender_name="老张",
        contents=[MessageContent(type=ContentType.TEXT, text="聊聊黑苹果")],
        timestamp=datetime.utcnow(),
    )
    return ChatEvent(
        event_id="e-1",
        platform="test",
        chat_type=ChatType.GROUP,
        chat_id=chat_id,
        message=message,
        is_from_self=is_from_self,
    )


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------

def test_user_memory_fact_profile_defaults() -> None:
    profile = UserMemoryFact(user_id="u-1")
    assert profile.user_name == ""
    assert profile.interests == {}
    assert profile.active_groups == []
    assert profile.frequent_contacts == {}


def test_interest_topic_stat_accumulation() -> None:
    stat = InterestTopicStat(score=5, last_active="2026-03-04 10:00:00", related_chat=["g-1"], keywords=["白屏"])
    assert stat.score == 5
    assert "g-1" in stat.related_chat
    assert "白屏" in stat.keywords


def test_frequent_contact_stat_related_topics() -> None:
    contact = FrequentContactStat(name="小李", interaction_count=3, last_interact="2026-03-04 12:00:00")
    contact.related_topics["黑苹果"] = RelatedTopicStat(score=2, last_talk="2026-03-04 12:00:00")
    assert contact.related_topics["黑苹果"].score == 2


def test_user_memory_fact_serialization_roundtrip() -> None:
    profile = UserMemoryFact(
        user_id="u-1",
        user_name="老张",
        interests={
            "黑苹果": InterestTopicStat(score=13, last_active="2026-03-04 15:30:00", related_chat=["g123"], keywords=["白屏"]),
        },
        active_groups=[ActiveGroupStat(group_id="g123", frequency=9, last_talk="2026-03-04")],
        frequent_contacts={
            "u456": FrequentContactStat(
                name="小李",
                interaction_count=8,
                last_interact="2026-03-04 16:20:00",
                related_topics={"黑苹果": RelatedTopicStat(score=10, last_talk="2026-03-04 15:30:00")},
                related_groups=["g123"],
            )
        },
    )
    json_str = profile.model_dump_json()
    restored = UserMemoryFact.model_validate_json(json_str)
    assert restored.user_id == "u-1"
    assert restored.user_name == "老张"
    assert restored.interests["黑苹果"].score == 13
    assert restored.active_groups[0].group_id == "g123"
    assert restored.frequent_contacts["u456"].interaction_count == 8
    assert restored.frequent_contacts["u456"].related_topics["黑苹果"].score == 10


# ---------------------------------------------------------------------------
# MemoryRepository tests
# ---------------------------------------------------------------------------

async def test_memory_repository_upsert_and_get() -> None:
    repo = MemoryRepository()
    profile = UserMemoryFact(user_id="u-1", user_name="老张")
    await repo.upsert_profile(profile)

    fetched = await repo.get_profile("u-1")
    assert fetched is not None
    assert fetched.user_id == "u-1"
    assert fetched.user_name == "老张"


async def test_memory_repository_upsert_overwrites() -> None:
    repo = MemoryRepository()
    profile_v1 = UserMemoryFact(user_id="u-2", user_name="v1")
    await repo.upsert_profile(profile_v1)

    profile_v2 = UserMemoryFact(
        user_id="u-2",
        user_name="v2",
        interests={"黑苹果": InterestTopicStat(score=5, last_active="2026-03-04 10:00:00")},
    )
    await repo.upsert_profile(profile_v2)

    fetched = await repo.get_profile("u-2")
    assert fetched is not None
    assert fetched.user_name == "v2"
    assert "黑苹果" in fetched.interests


async def test_memory_repository_get_missing_returns_none() -> None:
    repo = MemoryRepository()
    result = await repo.get_profile("no-such-user")
    assert result is None


# ---------------------------------------------------------------------------
# SelfMessageMemoryService tests
# ---------------------------------------------------------------------------

class FakeContextService:
    async def build_context(self, event):
        return []


class FakeLLMReturnsTopics:
    async def extract_self_participation(self, event, context, existing_topics=None):
        return {
            "user_name": "老张",
            "topics": [
                {"name": "黑苹果", "score": 3, "keywords": ["白屏", "安装"]},
            ],
            "interactions": [
                {"user_id": "u-456", "user_name": "小李", "topics": ["黑苹果"]},
            ],
        }


class FakeLLMReturnsNone:
    async def extract_self_participation(self, event, context, existing_topics=None):
        return None


async def test_self_message_service_skips_non_self_message() -> None:
    repo = MemoryRepository()
    service = SelfMessageMemoryService(FakeLLMReturnsTopics(), repo, FakeContextService())
    event = _build_event(is_from_self=False)
    result = await service.process_if_self_message(event)
    assert result == 0
    assert await repo.get_profile("u-self") is None


async def test_self_message_service_builds_profile_from_scratch() -> None:
    repo = MemoryRepository()
    service = SelfMessageMemoryService(FakeLLMReturnsTopics(), repo, FakeContextService())
    event = _build_event()
    result = await service.process_if_self_message(event)

    assert result == 1
    profile = await repo.get_profile("u-self")
    assert profile is not None
    assert profile.user_name == "老张"
    assert "黑苹果" in profile.interests
    assert profile.interests["黑苹果"].score == 3
    assert "白屏" in profile.interests["黑苹果"].keywords
    assert "g-1" in profile.interests["黑苹果"].related_chat
    assert len(profile.active_groups) == 1
    assert profile.active_groups[0].group_id == "g-1"
    assert "u-456" in profile.frequent_contacts
    assert profile.frequent_contacts["u-456"].name == "小李"
    assert profile.frequent_contacts["u-456"].interaction_count == 1
    assert "黑苹果" in profile.frequent_contacts["u-456"].related_topics


async def test_self_message_service_accumulates_on_repeated_calls() -> None:
    repo = MemoryRepository()
    service = SelfMessageMemoryService(FakeLLMReturnsTopics(), repo, FakeContextService())
    event = _build_event()
    await service.process_if_self_message(event)
    await service.process_if_self_message(event)

    profile = await repo.get_profile("u-self")
    assert profile is not None
    # Score should be accumulated (3 + 3 = 6)
    assert profile.interests["黑苹果"].score == 6
    # Group frequency should be 2
    assert profile.active_groups[0].frequency == 2
    # Contact interaction count should be 2
    assert profile.frequent_contacts["u-456"].interaction_count == 2


async def test_self_message_service_handles_llm_failure_gracefully() -> None:
    repo = MemoryRepository()
    service = SelfMessageMemoryService(FakeLLMReturnsNone(), repo, FakeContextService())
    event = _build_event()
    result = await service.process_if_self_message(event)
    assert result == 0
    assert await repo.get_profile("u-self") is None


async def test_self_message_service_passes_existing_topics_to_llm() -> None:
    """Verify that existing topic names are passed to the LLM to avoid synonyms."""
    captured: list[list[str]] = []

    class CapturingLLM:
        async def extract_self_participation(self, event, context, existing_topics=None):
            captured.append(existing_topics or [])
            return {
                "user_name": "老张",
                "topics": [{"name": "汽车", "score": 2, "keywords": []}],
                "interactions": [],
            }

    repo = MemoryRepository()
    # Seed existing profile with a fully populated topic to also exercise merging
    seed = UserMemoryFact(
        user_id="u-self",
        interests={
            "黑苹果": InterestTopicStat(
                score=5,
                last_active="2026-03-01 10:00:00",
                related_chat=["g-1"],
                keywords=["白屏"],
            )
        },
    )
    await repo.upsert_profile(seed)

    service = SelfMessageMemoryService(CapturingLLM(), repo, FakeContextService())
    event = _build_event()
    await service.process_if_self_message(event)

    # The LLM must receive the existing topic list
    assert captured == [["黑苹果"]]
    # The new topic "汽车" should be added alongside the preserved "黑苹果"
    profile = await repo.get_profile("u-self")
    assert profile is not None
    assert "黑苹果" in profile.interests
    assert profile.interests["黑苹果"].score == 5  # unchanged since LLM returned "汽车" only
    assert "汽车" in profile.interests
    assert profile.interests["汽车"].score == 2
