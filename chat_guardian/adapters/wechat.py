from chat_guardian.adapters.base import Adapter, EventHandler


class WeChatAdapter(Adapter):
    """WeChat 适配器占位实现。"""
    name = "wechat"

    def __init__(self):
        self._handlers: list[EventHandler] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def register_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def is_running(self) -> bool:
        return False
