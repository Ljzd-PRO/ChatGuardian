"""
应用设置模块。

此模块定义 `Settings` 配置类，使用环境变量（前缀 `CHAT_GUARDIAN_`）进行初始化。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置类。

    属性说明：
    - `database_url`: SQLAlchemy/数据库连接字符串。
    - `llm_*`: 与 LLM 调用与并发控制相关的参数。
    - `context_message_limit`: 在判断时回溯的消息条数。
    - `smtp_*`: 邮件发送配置（可为空，当未配置时邮件通知将被跳过）。
    - `external_rule_generation_endpoint`: 可选的外部规则生成 API 地址。
    - `enabled_adapters`: 启用的 adapter 列表（可多选）。
    """

    model_config = SettingsConfigDict(env_prefix="CHAT_GUARDIAN_", env_file=".env", extra="ignore")

    app_name: str = "ChatGuardian"
    environment: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./chat_guardian.db"

    # LLM 与批处理相关设置
    llm_timeout_seconds: float = 30.0
    llm_max_parallel_batches: int = 3
    llm_rules_per_batch: int = 2
    llm_batch_timeout_seconds: float = 30.0
    llm_batch_max_retries: int = 1
    llm_batch_rate_limit_per_second: float = 0.0
    llm_batch_idempotency_cache_size: int = 1024
    llm_langchain_backend: str = "openai_compatible"
    llm_langchain_model: str = "gpt-4o-mini"
    llm_langchain_api_base: str | None = None
    llm_langchain_api_key: str | None = None
    llm_langchain_temperature: float = 0.0
    llm_ollama_base_url: str = "http://localhost:11434"

    # 从会话中获取历史消息条数
    context_message_limit: int = 10

    # 消息缓冲配置：未处理队列与滚动历史上限
    pending_queue_limit: int = 200
    history_list_limit: int = 1000

    # 检测触发配置：冷却、新消息最小数量、等待超时
    detection_cooldown_seconds: float = 5.0
    detection_min_new_messages: int = 1
    detection_wait_timeout_seconds: float = 30.0

    # SMTP 发信配置（可用于 EmailNotifier）
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None

    # 外部 Hook 与规则生成端点
    hook_timeout_seconds: float = 8.0
    enable_internal_rule_generation: bool = True
    external_rule_generation_endpoint: str | None = None

    # Adapter 插件配置
    enabled_adapters: list[str] = []

    onebot_api_root: str | None = None
    onebot_access_token: str | None = None
    onebot_retry_interval_seconds: float = 5.0
    onebot_connect_timeout_seconds: float = 10.0

    telegram_bot_token: str | None = None
    wechat_endpoint: str | None = None
    feishu_app_id: str | None = None


settings = Settings()
