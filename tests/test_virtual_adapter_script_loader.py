from pathlib import Path

from chat_guardian.adapters import VirtualAdapter, build_adapters_from_settings, load_virtual_scripted_messages
from chat_guardian.settings import Settings


def test_load_virtual_scripted_messages_from_json(tmp_path: Path) -> None:
    script_path = tmp_path / "dialogue.json"
    script_path.write_text(
        """
[
  {"chat_id": "g-1", "sender_id": "u-1", "sender_name": "A", "text": "我还好，有香菜挑出来就好了", "delay_seconds": 0.1},
  {"chat_id": "g-1", "sender_id": "u-2", "sender_name": "B", "text": "我老公吃香菜会吐", "delay_seconds": 0.2},
  {"chat_id": "g-1", "sender_id": "u-3", "sender_name": "C", "text": "不知道是不是过敏", "delay_seconds": 0.15}
]
        """.strip(),
        encoding="utf-8",
    )

    messages = load_virtual_scripted_messages(str(script_path))

    assert len(messages) == 3
    assert messages[0].text == "我还好，有香菜挑出来就好了"
    assert messages[1].sender_id == "u-2"


def test_build_virtual_adapter_from_script_path(tmp_path: Path) -> None:
    script_path = tmp_path / "dialogue.json"
    script_path.write_text(
        """
[
  {"chat_id": "virtual-group-1", "sender_id": "u-1", "text": "每次都记得备注不加", "delay_seconds": 0.05},
  {"chat_id": "virtual-group-1", "sender_id": "u-2", "text": "实在有就挑给我", "delay_seconds": 0.05}
]
        """.strip(),
        encoding="utf-8",
    )

    local_settings = Settings(
        enabled_adapters=["virtual"],
        virtual_adapter_script_path=str(script_path),
    )

    adapters = build_adapters_from_settings(local_settings)
    assert len(adapters) == 1
    assert isinstance(adapters[0], VirtualAdapter)
