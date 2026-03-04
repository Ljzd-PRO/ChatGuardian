from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from chat_guardian.domain import ChatEvent

EventHandler = Callable[[ChatEvent], Awaitable[None]]


class Adapter(Protocol):
    name: str

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    def register_handler(self, handler: EventHandler) -> None: ...

    def is_running(self) -> bool: ...
