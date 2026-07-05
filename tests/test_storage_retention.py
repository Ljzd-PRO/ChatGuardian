import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from chat_guardian.domain import (
    ChatMessage,
    ChatType,
    ContentType,
    DetectionResult,
    MessageContent,
    RuleDecision,
)
from chat_guardian.repositories import ChatHistoryStore, DetectionResultRepository
from chat_guardian.settings import settings
from chat_guardian.storage import sanitize_message_for_storage


def _message(message_id: str, *, image: bool = False, days_old: int = 0) -> ChatMessage:
    contents = (
        [MessageContent(type=ContentType.IMAGE, image_data=b"x" * 2048)]
        if image
        else [MessageContent(type=ContentType.TEXT, text=f"message {message_id}")]
    )
    return ChatMessage(
        message_id=message_id,
        chat_id="chat-1",
        sender_id="user-1",
        sender_name="User",
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_old),
        contents=contents,
    )


def _result(result_id: str, rule_id: str, messages: list[ChatMessage], *, days_old: int = 0) -> DetectionResult:
    return DetectionResult(
        result_id=result_id,
        event_id=f"evt-{result_id}",
        rule_id=rule_id,
        chat_id="chat-1",
        message_id=messages[-1].message_id,
        decision=RuleDecision(rule_id=rule_id, triggered=True, confidence=0.9, reason="test"),
        context_messages=messages,
        generated_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )


@pytest.mark.asyncio
async def test_history_persistence_strips_image_data(tmp_path):
    old_persist = settings.storage_persist_image_data
    settings.storage_persist_image_data = False
    try:
        store = ChatHistoryStore(database_url=f"sqlite:///{tmp_path / 'history.sqlite'}")
        await store.append_history_message("test", ChatType.GROUP, "chat-1", _message("m1", image=True))

        persisted = next(iter(store.history["test"]["group"]["chat-1"]))
        assert persisted.contents[0].image_data is None
        assert str(persisted).startswith("[image:")

        with store._db.session_factory() as session:  # noqa: SLF001 - focused storage regression test
            raw_json = session.scalar(text("SELECT message_json FROM chat_messages LIMIT 1"))
    finally:
        settings.storage_persist_image_data = old_persist

    payload = json.loads(raw_json)
    image_payload = payload["contents"][0]
    assert "image_data" not in image_payload
    assert image_payload["image_data_stripped"] is True
    assert image_payload["image_byte_size"] == 2048


def test_sanitized_image_message_keeps_placeholder_text():
    sanitized = sanitize_message_for_storage(_message("m1", image=True), persist_image_data=False)
    assert sanitized.contents[0].image_data is None
    assert str(sanitized).startswith("[image:")


@pytest.mark.asyncio
async def test_detection_results_strip_images_and_prune_per_rule(tmp_path):
    old_persist = settings.storage_persist_image_data
    old_max = settings.storage_detection_max_records_per_rule
    old_days = settings.storage_detection_retention_days
    settings.storage_persist_image_data = False
    settings.storage_detection_max_records_per_rule = 2
    settings.storage_detection_retention_days = 30
    try:
        repo = DetectionResultRepository(database_url=f"sqlite:///{tmp_path / 'results.sqlite'}")
        await repo.add(_result("r1", "rule-1", [_message("m1", image=True)]))
        with repo._db.session_factory() as session:  # noqa: SLF001 - focused storage regression test
            image_payload_json = session.scalar(text("SELECT payload_json FROM detection_results WHERE result_id = 'r1'"))
        image_payload = json.loads(image_payload_json)
        image_content = image_payload["context_messages"][0]["contents"][0]
        assert "image_data" not in image_content
        assert image_content["image_data_stripped"] is True

        await repo.add(_result("r2", "rule-1", [_message("m2")]))
        await repo.add(_result("r3", "rule-1", [_message("m3")]))

        assert [item.result_id for item in repo.results_by_rule["rule-1"]] == ["r2", "r3"]
        with repo._db.session_factory() as session:  # noqa: SLF001 - focused storage regression test
            assert session.scalar(text("SELECT payload_json FROM detection_results WHERE result_id = 'r1'")) is None
    finally:
        settings.storage_persist_image_data = old_persist
        settings.storage_detection_max_records_per_rule = old_max
        settings.storage_detection_retention_days = old_days


@pytest.mark.asyncio
async def test_history_prune_respects_global_message_limit(tmp_path):
    old_limit = settings.storage_history_max_total_messages
    old_days = settings.storage_history_retention_days
    settings.storage_history_max_total_messages = 2
    settings.storage_history_retention_days = 0
    try:
        store = ChatHistoryStore(database_url=f"sqlite:///{tmp_path / 'history-limit.sqlite'}")
        await store.append_history_messages(
            "test",
            ChatType.GROUP,
            "chat-1",
            [_message(f"m{index}") for index in range(3)],
        )
        removed = await store.prune_history(retention_days=None, max_total_messages=2)
        messages = list(store.history["test"]["group"]["chat-1"])
        assert removed["history_deleted_by_count"] == 1
        assert [message.message_id for message in messages] == ["m1", "m2"]
    finally:
        settings.storage_history_max_total_messages = old_limit
        settings.storage_history_retention_days = old_days


@pytest.mark.asyncio
async def test_merge_into_last_triggered_limits_context_and_strips_images(tmp_path):
    old_limit = settings.storage_detection_context_message_limit
    old_persist = settings.storage_persist_image_data
    settings.storage_detection_context_message_limit = 3
    settings.storage_persist_image_data = False
    try:
        repo = DetectionResultRepository(database_url=f"sqlite:///{tmp_path / 'merge.sqlite'}")
        await repo.add(_result("r1", "rule-1", [_message("m1"), _message("m2")]))
        merged = await repo.merge_into_last_triggered(
            "rule-1",
            [_message("m2"), _message("m3", image=True), _message("m4")],
        )
        assert merged is not None
        assert [message.message_id for message in merged.context_messages] == ["m2", "m3", "m4"]
        assert merged.context_messages[1].contents[0].image_data is None
    finally:
        settings.storage_detection_context_message_limit = old_limit
        settings.storage_persist_image_data = old_persist
