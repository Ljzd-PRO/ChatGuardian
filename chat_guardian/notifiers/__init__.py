"""
通知器系统（统一入口）。

说明：
- 本文件仅做通知器协议与实现导出；
- 具体通知器实现见 notifiers 子模块。
"""

from .base import Notifier
from .email import EmailNotifier, NotificationConfig

__all__ = ["Notifier", "EmailNotifier", "NotificationConfig"]
