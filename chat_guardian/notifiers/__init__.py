"""
通知器系统（统一入口）。

说明：
- 本文件仅做通知器协议与实现导出；
- 具体通知器实现见 notifiers 子模块。
"""

from .base import Notifier
from .bark import BarkNotifier, BarkNotificationConfig, build_bark_notifier_from_settings
from .email import EmailNotifier, NotificationConfig, build_email_notifier_from_settings


def build_notifiers_from_settings() -> list[Notifier]:
    notifiers: list[Notifier] = []

    email_notifier = build_email_notifier_from_settings()
    if email_notifier is not None:
        notifiers.append(email_notifier)

    bark_notifier = build_bark_notifier_from_settings()
    if bark_notifier is not None:
        notifiers.append(bark_notifier)

    return notifiers

__all__ = [
	"Notifier",
	"EmailNotifier",
	"NotificationConfig",
	"BarkNotifier",
	"BarkNotificationConfig",
	"build_notifiers_from_settings",
]
