from __future__ import annotations
import asyncio
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import TYPE_CHECKING
from chat_guardian.domain import ChatEvent, ChatMessage, ChatType, ContentType, MessageContent
from chat_guardian.adapters.base import Adapter, EventHandler

@dataclass(slots=True)
class VirtualAdapterConfig:
    chat_count: int = 3
    members_per_chat: int = 5
    messages_per_chat: int = 10
    interval_min_seconds: float = 0.1
    interval_max_seconds: float = 0.6
    random_seed: int = 42
    scripted_messages: list["VirtualScriptedMessage"] | None = None

@dataclass(slots=True)
class VirtualScriptedMessage:
    chat_id: str
    sender_id: str
    text: str
    sender_name: str | None = None
    delay_seconds: float = 0.1
    chat_type: ChatType = ChatType.GROUP
    is_from_self: bool = False

def load_virtual_scripted_messages(script_path: str) -> list[VirtualScriptedMessage]:
    path = Path(script_path)
    if not path.exists():
        raise ValueError(f"Virtual adapter script file not found: {script_path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise ValueError("PyYAML is required to load .yaml/.yml script files") from exc
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise ValueError(f"Unsupported virtual adapter script format: {suffix}")
    if not isinstance(raw_data, list):
        raise ValueError("Virtual adapter script must be a list of message objects")
    messages: list[VirtualScriptedMessage] = []
    for index, item in enumerate(raw_data):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid scripted message at index {index}: expected object")
        chat_id = str(item.get("chat_id", "")).strip()
        sender_id = str(item.get("sender_id", "")).strip()
        text = str(item.get("text", ""))
        if not chat_id or not sender_id:
            raise ValueError(f"Invalid scripted message at index {index}: chat_id/sender_id required")
        raw_chat_type = str(item.get("chat_type", ChatType.GROUP.value))
        try:
            chat_type = ChatType(raw_chat_type)
        except ValueError as exc:
            raise ValueError(f"Invalid chat_type at index {index}: {raw_chat_type}") from exc
        messages.append(
            VirtualScriptedMessage(
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=(str(item["sender_name"]) if item.get("sender_name") is not None else None),
                text=text,
                delay_seconds=float(item.get("delay_seconds", 0.1)),
                chat_type=chat_type,
                is_from_self=bool(item.get("is_from_self", False)),
            )
        )
    return messages

class VirtualAdapter(Adapter):
    name = "virtual"
    def __init__(self, config: VirtualAdapterConfig):
        self.config = config
        self._handlers: list[EventHandler] = []
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._rng = random.Random(config.random_seed)
        self._message_sequences: dict[str, int] = defaultdict(int)
    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)
    def is_running(self) -> bool:
        return self._running
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self.config.scripted_messages:
            self._tasks = [asyncio.create_task(self._run_scripted_messages(self.config.scripted_messages))]
            return
        self._tasks = [
            asyncio.create_task(self._simulate_chat(chat_id=f"virtual-group-{index + 1}"))
            for index in range(max(1, self.config.chat_count))
        ]
    async def stop(self) -> None:
        self._running = False
        if self._tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*self._tasks, return_exceptions=True), timeout=20.0)
            except asyncio.TimeoutError:
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
    async def _simulate_chat(self, chat_id: str) -> None:
        member_count = max(2, self.config.members_per_chat)
        members = [f"user-{chat_id}-{idx + 1}" for idx in range(member_count)]
        for _ in range(max(1, self.config.messages_per_chat)):
            if not self._running:
                break
            interval = self._rng.uniform(
                min(self.config.interval_min_seconds, self.config.interval_max_seconds),
                max(self.config.interval_min_seconds, self.config.interval_max_seconds),
            )
            await asyncio.sleep(interval)
            sender_id = self._rng.choice(members)
            sender_name = sender_id.replace("user", "member")
            text = f"message-{self._message_sequences[chat_id] + 1} from {sender_name}"
            self._message_sequences[chat_id] += 1
            message = ChatMessage(
                message_id=f"{chat_id}-m-{self._message_sequences[chat_id]}",
                chat_id=chat_id,
                sender_id=sender_id,
                sender_name=sender_name,
                timestamp=datetime.now(timezone.utc),
                contents=[MessageContent(type=ContentType.TEXT, text=text)],
            )
            event = ChatEvent(
                chat_type=ChatType.GROUP,
                chat_id=chat_id,
                message=message,
                platform=self.name,
                is_from_self=False,
            )
            await asyncio.gather(*(handler(event) for handler in self._handlers), return_exceptions=True)
    async def _run_scripted_messages(self, scripted_messages: list[VirtualScriptedMessage]) -> None:
        for item in scripted_messages:
            if not self._running:
                break
            await asyncio.sleep(max(0.0, item.delay_seconds))
            self._message_sequences[item.chat_id] += 1
            message = ChatMessage(
                message_id=f"{item.chat_id}-m-{self._message_sequences[item.chat_id]}",
                chat_id=item.chat_id,
                sender_id=item.sender_id,
                sender_name=item.sender_name,
                timestamp=datetime.now(timezone.utc),
                contents=[MessageContent(type=ContentType.TEXT, text=item.text)],
            )
            event = ChatEvent(
                chat_type=item.chat_type,
                chat_id=item.chat_id,
                message=message,
                platform=self.name,
                is_from_self=item.is_from_self,
            )
            await asyncio.gather(*(handler(event) for handler in self._handlers), return_exceptions=True)
