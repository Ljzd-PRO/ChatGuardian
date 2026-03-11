"""
Repository 实现：内存缓存 + SQLAlchemy 持久化。

默认用于本地开发时可通过 SQLite 文件持久化（例如 `db.sqlite`），并在启动时自动
将已有数据加载到内存索引结构，兼顾运行时访问效率与重启后数据保留。
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from chat_guardian.domain import ChatMessage, ChatType, DetectionResult, DetectionRule, Feedback, UserMemoryFact


class _Base(DeclarativeBase):
    pass


class _ChatMessageRecord(_Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(16), index=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    chat_type: Mapped[str] = mapped_column(String(32), index=True)
    chat_id: Mapped[str] = mapped_column(String(128), index=True)
    message_json: Mapped[str] = mapped_column(Text)


class _RuleRecord(_Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)


class _FeedbackRecord(_Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class _MemoryFactRecord(_Base):
    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class _DetectionResultRecord(_Base):
    __tablename__ = "detection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(128), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    triggered: Mapped[bool] = mapped_column(Boolean, index=True)
    trigger_suppressed: Mapped[bool] = mapped_column(Boolean, index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class _SettingRecord(_Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class _AdminCredentialRecord(_Base):
    __tablename__ = "admin_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(512))


class _AgentSessionRecord(_Base):
    __tablename__ = "agent_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[str] = mapped_column(String(32))


class _AgentMessageRecord(_Base):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls_json: Mapped[str] = mapped_column(Text, default="[]")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))


class _RepositoryDatabase:
    def __init__(self, database_url: str):
        normalized_url = normalize_database_url(database_url)
        engine_kwargs: dict[str, Any] = {"future": True}
        if normalized_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self.engine = create_engine(normalized_url, **engine_kwargs)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        _Base.metadata.create_all(self.engine)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return database_url


_DB_MANAGERS: dict[str, _RepositoryDatabase] = {}


def _get_db_manager(database_url: str | None) -> _RepositoryDatabase | None:
    if not database_url:
        return None

    normalized_key = normalize_database_url(database_url)
    manager = _DB_MANAGERS.get(normalized_key)
    if manager is None:
        manager = _RepositoryDatabase(normalized_key)
        _DB_MANAGERS[normalized_key] = manager
    return manager


class ChatHistoryStore:
    """将消息按 adapter/chat_type/chat_id 分类保存在内存中。

    Methods:
        enqueue_message: 将消息写入未处理队列。
        pop_pending_messages: 从未处理队列头部取消息。
        append_history_messages: 将消息写入滚动历史列表。
        recent_history_messages: 获取指定消息之前的最近若干条历史消息（按时间升序）。
    """

    def __init__(self, pending_queue_limit: int = 200, history_list_limit: int = 1000, database_url: str | None = None):
        self.pending_queue_limit = pending_queue_limit
        self.history_list_limit = history_list_limit
        self._db = _get_db_manager(database_url)
        self.pending: dict[str, dict[str, dict[str, deque[ChatMessage]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(deque))
        )
        self.history: dict[str, dict[str, dict[str, deque[ChatMessage]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(deque))
        )
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return

        with self._db.session_factory() as session:
            rows = session.scalars(select(_ChatMessageRecord).order_by(_ChatMessageRecord.id)).all()

        for row in rows:
            message = ChatMessage.model_validate_json(row.message_json)
            if row.bucket == "pending":
                bucket = self.pending[row.platform][row.chat_type][row.chat_id]
                bucket.append(message)
                while len(bucket) > self.pending_queue_limit:
                    bucket.popleft()
            else:
                bucket = self.history[row.platform][row.chat_type][row.chat_id]
                bucket.append(message)
                while len(bucket) > self.history_list_limit:
                    bucket.popleft()

    def _insert_chat_message(self, bucket: str, platform: str, chat_type: str, chat_id: str,
                             message: ChatMessage) -> None:
        if self._db is None:
            return

        with self._db.session_factory() as session:
            session.add(
                _ChatMessageRecord(
                    bucket=bucket,
                    platform=platform,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    message_json=message.model_dump_json(),
                )
            )
            session.commit()

    def _delete_oldest_chat_messages(self, bucket: str, platform: str, chat_type: str, chat_id: str,
                                     count: int) -> None:
        if self._db is None or count <= 0:
            return

        with self._db.session_factory() as session:
            ids = session.scalars(
                select(_ChatMessageRecord.id)
                .where(
                    _ChatMessageRecord.bucket == bucket,
                    _ChatMessageRecord.platform == platform,
                    _ChatMessageRecord.chat_type == chat_type,
                    _ChatMessageRecord.chat_id == chat_id,
                )
                .order_by(_ChatMessageRecord.id)
                .limit(count)
            ).all()
            if ids:
                session.execute(delete(_ChatMessageRecord).where(_ChatMessageRecord.id.in_(ids)))
                session.commit()

    @staticmethod
    def _chat_type_key(chat_type: ChatType | str) -> str:
        return chat_type.value if isinstance(chat_type, ChatType) else str(chat_type)

    async def enqueue_message(self, platform: str, chat_type: ChatType | str, chat_id: str,
                              message: ChatMessage) -> None:
        """将新消息追加到未处理队列（按 platform/chat_type/chat_id 分类）。

        如果队列超过 `pending_queue_limit`，会从最旧处丢弃消息以保证容量上限。

        Args:
            platform: 消息来源平台标识（如 onebot）。
            chat_type: 聊天类型（'group' 或 'private'）。
            chat_id: 会话/群组 ID。
            message: 要入队的 `ChatMessage` 实例。
        """
        chat_type_key = self._chat_type_key(chat_type)
        bucket = self.pending[platform][chat_type_key][chat_id]
        bucket.append(message)
        self._insert_chat_message("pending", platform, chat_type_key, chat_id, message)

        overflow = len(bucket) - self.pending_queue_limit
        if overflow > 0:
            self._delete_oldest_chat_messages("pending", platform, chat_type_key, chat_id, overflow)
        while len(bucket) > self.pending_queue_limit:
            bucket.popleft()

    async def pending_size(self, platform: str, chat_type: ChatType | str, chat_id: str) -> int:
        """返回指定队列当前的未处理消息数量。"""
        return len(self.pending[platform][self._chat_type_key(chat_type)][chat_id])

    async def oldest_pending_timestamp(
            self,
            platform: str,
            chat_type: ChatType | str,
            chat_id: str,
    ) -> datetime | None:
        """返回队列中最早一条未处理消息的时间戳，如果队列为空返回 None。"""
        bucket = self.pending[platform][self._chat_type_key(chat_type)][chat_id]
        if not bucket:
            return None
        return bucket[0].timestamp

    async def pop_pending_messages(
            self,
            platform: str,
            chat_type: ChatType | str,
            chat_id: str,
            max_count: int | None,
    ) -> list[ChatMessage]:
        """从未处理队列头部弹出最多 `max_count` 条消息并返回。

        如果 `max_count` 为 None，则弹出全部消息。
        返回值为按时间顺序（从旧到新）的消息列表。
        """
        chat_type_key = self._chat_type_key(chat_type)
        bucket = self.pending[platform][chat_type_key][chat_id]
        if max_count is None:
            max_count = len(bucket)
        items: list[ChatMessage] = []
        while bucket and len(items) < max_count:
            items.append(bucket.popleft())

        self._delete_oldest_chat_messages("pending", platform, chat_type_key, chat_id, len(items))
        return items

    async def append_history_message(
            self,
            platform: str,
            chat_type: ChatType | str,
            chat_id: str,
            message: ChatMessage,
    ) -> None:
        """将单条消息追加到已处理滚动历史中，超过上限会从旧端丢弃。"""
        chat_type_key = self._chat_type_key(chat_type)
        bucket = self.history[platform][chat_type_key][chat_id]
        bucket.append(message)
        self._insert_chat_message("history", platform, chat_type_key, chat_id, message)

        overflow = len(bucket) - self.history_list_limit
        if overflow > 0:
            self._delete_oldest_chat_messages("history", platform, chat_type_key, chat_id, overflow)
        while len(bucket) > self.history_list_limit:
            bucket.popleft()

    async def append_history_messages(
            self,
            platform: str,
            chat_type: ChatType | str,
            chat_id: str,
            messages: list[ChatMessage],
    ) -> None:
        """将多条消息按顺序追加到已处理滚动历史中。"""
        for message in messages:
            await self.append_history_message(platform, chat_type, chat_id, message)

    async def recent_history_messages(
            self,
            platform: str,
            chat_type: ChatType | str,
            chat_id: str,
            before_message_id: str | None,
            limit: int,
    ) -> list[ChatMessage]:
        """获取指定会话在 `before_message_id` 之前的最近若干条历史消息。

        Args:
            platform: 平台标识。
            chat_type: 聊天类型。
            chat_id: 会话 ID。
            before_message_id: 以该消息为分界（不包含该消息），如果为 None 则取最新。
            limit: 返回的最大条数。
        """
        bucket = list(self.history[platform][self._chat_type_key(chat_type)][chat_id])
        if before_message_id:
            try:
                idx = next(index for index, message in enumerate(bucket) if message.message_id == before_message_id)
                bucket = bucket[:idx]
            except StopIteration:
                pass
        return bucket[-limit:]

    async def delete_history_messages(
            self,
            items: list[tuple[str, str, str, str]],
    ) -> int:
        """
        按 message_id 删除历史消息。

        Args:
            items: (platform, chat_type, chat_id, message_id) 元组列表。

        Returns:
            实际删除的消息条数。
        """
        deleted = 0
        to_delete: dict[tuple[str, str, str], set[str]] = defaultdict(set)

        for platform, chat_type, chat_id, message_id in items:
            chat_type_key = self._chat_type_key(chat_type)
            bucket = self.history.get(platform, {}).get(chat_type_key, {}).get(chat_id)
            if not bucket:
                continue

            for message in list(bucket):
                if message.message_id == message_id:
                    try:
                        bucket.remove(message)
                    except ValueError:
                        continue
                    deleted += 1
                    to_delete[(platform, chat_type_key, chat_id)].add(message_id)
                    break

        if self._db is not None and to_delete:
            with self._db.session_factory() as session:
                ids: list[int] = []
                for (platform, chat_type_key, chat_id), message_ids in to_delete.items():
                    rows = session.scalars(
                        select(_ChatMessageRecord)
                        .where(
                            _ChatMessageRecord.bucket == "history",
                            _ChatMessageRecord.platform == platform,
                            _ChatMessageRecord.chat_type == chat_type_key,
                            _ChatMessageRecord.chat_id == chat_id,
                        )
                    ).all()
                    for row in rows:
                        try:
                            message = ChatMessage.model_validate_json(row.message_json)
                        except Exception:
                            continue
                        if message.message_id in message_ids:
                            ids.append(row.id)
                if ids:
                    session.execute(delete(_ChatMessageRecord).where(_ChatMessageRecord.id.in_(ids)))
                    session.commit()

        return deleted

    async def clear_history(self) -> int:
        """清空所有历史消息，返回被清理的条数。"""
        cleared = 0
        for by_type in self.history.values():
            for by_chat in by_type.values():
                for bucket in by_chat.values():
                    cleared += len(bucket)
        self.history = defaultdict(lambda: defaultdict(lambda: defaultdict(deque)))

        if self._db is not None:
            with self._db.session_factory() as session:
                session.execute(delete(_ChatMessageRecord).where(_ChatMessageRecord.bucket == "history"))
                session.commit()

        return cleared


class RuleRepository:
    """内存中的规则存储实现，支持上载/列举已启用规则。"""

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)
        self.rules: dict[str, DetectionRule] = {}
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        with self._db.session_factory() as session:
            rows = session.scalars(select(_RuleRecord)).all()
        self.rules = {row.rule_id: DetectionRule.model_validate_json(row.payload_json) for row in rows}

    async def list_enabled(self) -> list[DetectionRule]:
        return [rule for rule in self.rules.values() if rule.enabled]

    async def list_all(self) -> list[DetectionRule]:
        return list(self.rules.values())

    async def upsert(self, rule: DetectionRule) -> DetectionRule:
        self.rules[rule.rule_id] = rule
        if self._db is not None:
            with self._db.session_factory() as session:
                row = session.get(_RuleRecord, rule.rule_id)
                if row is None:
                    row = _RuleRecord(rule_id=rule.rule_id, payload_json=rule.model_dump_json())
                    session.add(row)
                else:
                    row.payload_json = rule.model_dump_json()
                session.commit()
        return rule

    async def get(self, rule_id: str) -> DetectionRule | None:
        return self.rules.get(rule_id)

    async def delete(self, rule_id: str) -> bool:
        if rule_id not in self.rules:
            return False
        del self.rules[rule_id]
        if self._db is not None:
            with self._db.session_factory() as session:
                row = session.get(_RuleRecord, rule_id)
                if row is not None:
                    session.delete(row)
                    session.commit()
        return True


class FeedbackRepository:
    """简单的反馈存储（按规则分组）。"""

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)
        self.feedback_by_rule: dict[str, list[Feedback]] = defaultdict(list)
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        with self._db.session_factory() as session:
            rows = session.scalars(select(_FeedbackRecord).order_by(_FeedbackRecord.id)).all()
        for row in rows:
            feedback = Feedback.model_validate_json(row.payload_json)
            self.feedback_by_rule[feedback.rule_id].append(feedback)

    async def add(self, feedback: Feedback) -> None:
        self.feedback_by_rule[feedback.rule_id].append(feedback)
        if self._db is not None:
            with self._db.session_factory() as session:
                session.add(_FeedbackRecord(rule_id=feedback.rule_id, payload_json=feedback.model_dump_json()))
                session.commit()

    async def list_by_rule(self, rule_id: str) -> list[Feedback]:
        return list(self.feedback_by_rule.get(rule_id, []))


class MemoryRepository:
    """用户画像存储，每个用户唯一一份 `UserMemoryFact` 画像，支持增量合并更新。"""

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)
        self.profiles: dict[str, UserMemoryFact] = {}
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        with self._db.session_factory() as session:
            rows = session.scalars(select(_MemoryFactRecord)).all()
        for row in rows:
            profile = UserMemoryFact.model_validate_json(row.payload_json)
            self.profiles[profile.user_id] = profile

    async def upsert_profile(self, profile: UserMemoryFact) -> None:
        """保存或更新用户画像（每个用户仅保留一条记录）。"""
        self.profiles[profile.user_id] = profile
        if self._db is not None:
            with self._db.session_factory() as session:
                existing = session.scalar(
                    select(_MemoryFactRecord).where(_MemoryFactRecord.user_id == profile.user_id)
                )
                if existing:
                    existing.payload_json = profile.model_dump_json()
                else:
                    session.add(_MemoryFactRecord(user_id=profile.user_id, payload_json=profile.model_dump_json()))
                session.commit()

    async def get_profile(self, user_id: str) -> UserMemoryFact | None:
        """获取指定用户的画像，不存在则返回 None。"""
        return self.profiles.get(user_id)


class DetectionResultRepository:
    """按规则索引检测结果，并维护最近触发结果的 O(1) 查询结构。"""

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)
        self.results: list[DetectionResult] = []
        self.results_by_rule: dict[str, list[DetectionResult]] = defaultdict(list)
        self.last_triggered_by_rule: dict[str, DetectionResult] = {}
        self.last_triggered_message_ids: dict[str, set[str]] = {}
        self._load_from_db()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        with self._db.session_factory() as session:
            rows = session.scalars(select(_DetectionResultRecord).order_by(_DetectionResultRecord.id)).all()

        for row in rows:
            result = DetectionResult.model_validate_json(row.payload_json)
            self.results.append(result)
            self.results_by_rule[result.rule_id].append(result)
            if result.decision.triggered and not result.trigger_suppressed:
                self.last_triggered_by_rule[result.rule_id] = result
                self.last_triggered_message_ids[result.rule_id] = {message.message_id for message in
                                                                   result.context_messages}

    async def add(self, result: DetectionResult) -> None:
        """新增一条检测结果，并同步更新按规则索引。"""
        self.results.append(result)
        self.results_by_rule[result.rule_id].append(result)

        if self._db is not None:
            with self._db.session_factory() as session:
                session.add(
                    _DetectionResultRecord(
                        rule_id=result.rule_id,
                        generated_at=result.generated_at,
                        triggered=result.decision.triggered,
                        trigger_suppressed=result.trigger_suppressed,
                        payload_json=result.model_dump_json(),
                    )
                )
                session.commit()

        if result.decision.triggered and not result.trigger_suppressed:
            self.last_triggered_by_rule[result.rule_id] = result
            self.last_triggered_message_ids[result.rule_id] = {message.message_id for message in
                                                               result.context_messages}

    async def list_by_rule(self, rule_id: str) -> list[DetectionResult]:
        """返回指定规则的全部检测结果。"""
        return list(self.results_by_rule.get(rule_id, []))

    async def contains_message_in_last_triggered(self, rule_id: str, message_id: str) -> bool:
        """O(1) 判断某消息是否在该规则最近一次“已触发且未抑制”的结果里。"""
        return message_id in self.last_triggered_message_ids.get(rule_id, set())

    async def merge_into_last_triggered(self, rule_id: str,
                                        new_context_messages: list[ChatMessage]) -> DetectionResult | None:
        """将新增上下文消息并入该规则最近一次触发结果，避免重复触发。"""
        last = self.last_triggered_by_rule.get(rule_id)
        if last is None:
            return None

        known_ids = self.last_triggered_message_ids.setdefault(rule_id, set())
        merged = list(last.context_messages)
        for message in new_context_messages:
            if message.message_id in known_ids:
                continue
            merged.append(message)
            known_ids.add(message.message_id)

        last.context_messages = merged
        if self._db is not None:
            with self._db.session_factory() as session:
                row = session.scalar(
                    select(_DetectionResultRecord)
                    .where(
                        _DetectionResultRecord.rule_id == rule_id,
                        _DetectionResultRecord.triggered.is_(True),
                        _DetectionResultRecord.trigger_suppressed.is_(False),
                    )
                    .order_by(_DetectionResultRecord.id.desc())
                    .limit(1)
                )
                if row is not None:
                    row.payload_json = last.model_dump_json()
                    session.commit()
        return last


class SettingsRepository:
    """应用配置存储，将配置项以 JSON 序列化形式持久化到数据库。

    Args:
        database_url: 连接字符串。
        disallow_keys: 不允许读写到数据库的配置键集合（通常为只读的环境变量项）。
    """

    def __init__(self, database_url: str | None = None, disallow_keys: frozenset[str] | None = None):
        self._db = _get_db_manager(database_url)
        self._disallow_keys = set(disallow_keys or frozenset())

    def load_all(self) -> dict[str, Any]:
        """从数据库加载所有配置，返回已反序列化的 key->value 字典。"""
        if self._db is None:
            return {}
        with self._db.session_factory() as session:
            rows = session.scalars(select(_SettingRecord)).all()
        result: dict[str, Any] = {}
        for row in rows:
            if row.key in self._disallow_keys:
                continue
            try:
                result[row.key] = json.loads(row.value)
            except (json.JSONDecodeError, ValueError):
                from loguru import logger
                logger.warning(f"⚠️ 配置项 '{row.key}' JSON 反序列化失败，已跳过: {row.value!r}")
        return result

    def save(self, updates: dict[str, Any]) -> None:
        """将配置项批量 upsert 到数据库。"""
        if self._db is None:
            return
        filtered = {k: v for k, v in updates.items() if k not in self._disallow_keys}
        if not filtered:
            return
        with self._db.session_factory() as session:
            for key, value in filtered.items():
                serialized = json.dumps(value)
                row = session.get(_SettingRecord, key)
                if row is None:
                    session.add(_SettingRecord(key=key, value=serialized))
                else:
                    row.value = serialized
            session.commit()


class AdminCredentialRepository:
    """管理员凭据仓库，使用 PBKDF2-SHA256 进行密码哈希存储。"""

    # OWASP 2023 推荐 PBKDF2-SHA256 至少 600,000 次迭代；
    # 此处使用 260,000 次作为安全与性能之间的折中。
    _ITERATIONS = 260_000

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)

    def _hash_password(self, password: str, salt: bytes | None = None) -> str:
        """生成 ``salt_hex$hash_hex`` 格式的密码哈希。"""
        if salt is None:
            salt = os.urandom(32)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self._ITERATIONS)
        return f"{salt.hex()}${dk.hex()}"

    def _verify_hash(self, password: str, stored: str) -> bool:
        """验证密码是否匹配已存储的哈希。"""
        try:
            salt_hex, hash_hex = stored.split("$", 1)
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self._ITERATIONS)
        return secrets.compare_digest(dk.hex(), hash_hex)

    def is_configured(self) -> bool:
        """检查管理员凭据是否已配置。"""
        if self._db is None:
            return False
        with self._db.session_factory() as session:
            row = session.scalars(select(_AdminCredentialRecord).limit(1)).first()
        return row is not None

    def set_credentials(self, username: str, password: str) -> None:
        """设置管理员凭据（upsert，仅保留一条记录）。"""
        if self._db is None:
            return
        hashed = self._hash_password(password)
        with self._db.session_factory() as session:
            session.execute(delete(_AdminCredentialRecord))
            session.add(_AdminCredentialRecord(username=username, password_hash=hashed))
            session.commit()

    def verify(self, username: str, password: str) -> bool:
        """验证用户名与密码是否正确。"""
        if self._db is None:
            return False
        with self._db.session_factory() as session:
            row = session.scalars(select(_AdminCredentialRecord).limit(1)).first()
        if row is None:
            return False
        return row.username == username and self._verify_hash(password, row.password_hash)

    def get_username(self) -> str | None:
        """获取已配置的管理员用户名。"""
        if self._db is None:
            return None
        with self._db.session_factory() as session:
            row = session.scalars(select(_AdminCredentialRecord).limit(1)).first()
        return row.username if row else None

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改管理员密码，需验证旧密码。"""
        if not self.verify(username, old_password):
            return False
        self.set_credentials(username, new_password)
        return True


class AgentSessionRepository:
    """管理 AI 助手会话与消息的仓库。"""

    def __init__(self, database_url: str | None = None):
        self._db = _get_db_manager(database_url)

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话，按更新时间降序排列。"""
        if self._db is None:
            return []
        with self._db.session_factory() as session:
            rows = session.scalars(
                select(_AgentSessionRecord).order_by(_AgentSessionRecord.updated_at.desc())
            ).all()
        return [
            {
                "session_id": r.session_id,
                "title": r.title,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    def create_session(self, session_id: str, title: str = "") -> dict[str, Any]:
        """创建新会话。"""
        if self._db is None:
            return {"session_id": session_id, "title": title, "created_at": "", "updated_at": ""}
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        record = _AgentSessionRecord(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        with self._db.session_factory() as session:
            session.add(record)
            session.commit()
        return {
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题。"""
        if self._db is None:
            return False
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with self._db.session_factory() as session:
            row = session.get(_AgentSessionRecord, session_id)
            if row is None:
                return False
            row.title = title
            row.updated_at = now
            session.commit()
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息。"""
        if self._db is None:
            return False
        with self._db.session_factory() as session:
            session.execute(
                delete(_AgentMessageRecord).where(_AgentMessageRecord.session_id == session_id)
            )
            result = session.execute(
                delete(_AgentSessionRecord).where(_AgentSessionRecord.session_id == session_id)
            )
            session.commit()
        return result.rowcount > 0

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的所有消息。"""
        if self._db is None:
            return []
        with self._db.session_factory() as session:
            rows = session.scalars(
                select(_AgentMessageRecord)
                .where(_AgentMessageRecord.session_id == session_id)
                .order_by(_AgentMessageRecord.id.asc())
            ).all()
        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "role": r.role,
                "content": r.content,
                "tool_calls": json.loads(r.tool_calls_json) if r.tool_calls_json else [],
                "elapsed_ms": r.elapsed_ms,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def add_message(
        self, session_id: str, role: str, content: str,
        tool_calls: list | None = None, elapsed_ms: int | None = None,
    ) -> dict[str, Any]:
        """向会话添加一条消息。"""
        if self._db is None:
            return {}
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        tc_json = json.dumps(tool_calls or [], ensure_ascii=False, default=str)
        with self._db.session_factory() as session:
            # Validate the session exists to prevent orphaned messages
            sess_row = session.get(_AgentSessionRecord, session_id)
            if sess_row is None:
                return {}
            record = _AgentMessageRecord(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls_json=tc_json,
                elapsed_ms=elapsed_ms,
                created_at=now,
            )
            session.add(record)
            # Also update session's updated_at
            sess_row.updated_at = now
            session.commit()
            msg_id = record.id
        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls or [],
            "elapsed_ms": elapsed_ms,
            "created_at": now,
        }

    def delete_message_pair(self, session_id: str, user_message_id: int) -> bool:
        """删除一组问答对：指定的用户消息及其后紧接的助手消息。"""
        if self._db is None:
            return False
        with self._db.session_factory() as session:
            # Verify user message exists and belongs to session
            user_msg = session.get(_AgentMessageRecord, user_message_id)
            if user_msg is None or user_msg.session_id != session_id or user_msg.role != "user":
                return False

            # Find the next assistant message after this user message
            assistant_msg = session.scalars(
                select(_AgentMessageRecord)
                .where(
                    _AgentMessageRecord.session_id == session_id,
                    _AgentMessageRecord.id > user_message_id,
                    _AgentMessageRecord.role == "assistant",
                )
                .order_by(_AgentMessageRecord.id.asc())
                .limit(1)
            ).first()

            session.delete(user_msg)
            if assistant_msg is not None:
                session.delete(assistant_msg)
            session.commit()
        return True
