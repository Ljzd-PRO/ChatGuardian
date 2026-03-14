"""pytest 全局配置：将测试数据库路径重定向到独立的 test.sqlite，避免污染生产数据库。"""
from chat_guardian.settings import settings

settings.database_url = "sqlite:///./test.sqlite"
