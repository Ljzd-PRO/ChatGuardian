"""
应用设置模块。

此模块定义 `Settings` 配置类。`database_url`、`app_name`、`environment` 通过环境变量（前缀
`CHAT_GUARDIAN_`）读取，其余配置项通过 SQLAlchemy SQLite 数据库保存与读取，并可通过前端 API 修改。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class _EnvConfig(BaseSettings):
    """仅从环境变量读取 database_url 及只读的基础元信息。"""

    model_config = SettingsConfigDict(env_prefix="CHAT_GUARDIAN_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./db.sqlite"
    app_name: str | None = None
    environment: str | None = None


class Settings(BaseModel):
    """
    全局配置类。

    除 database_url 外，所有配置项均通过数据库存储和读取，并可通过前端 API 修改。
    database_url 仅通过环境变量（CHAT_GUARDIAN_DATABASE_URL）配置。

    Attributes:
        database_url: SQLAlchemy/数据库连接字符串（仅通过环境变量配置）。
        app_name: 应用名称。
        environment: 当前环境（如 dev、prod）。
        llm_timeout_seconds: LLM 单次调用超时时间（秒）。
        llm_max_parallel_batches: LLM 最大并行批次数。
        llm_rules_per_batch: 每批处理的规则数。
        llm_batch_timeout_seconds: LLM 批处理超时时间（秒）。
        llm_batch_max_retries: LLM 批处理最大重试次数。
        llm_batch_rate_limit_per_second: LLM 批处理限流速率（每秒）。
        llm_batch_idempotency_cache_size: LLM 幂等缓存大小。
        llm_langchain_backend: LangChain 后端类型。
        llm_langchain_model: LangChain 使用的模型名称。
        llm_langchain_api_base: LangChain API 基础地址。
        llm_langchain_api_key: LangChain API 密钥。
        llm_langchain_temperature: LangChain 采样温度。
        llm_ollama_base_url: Ollama 基础地址。
        llm_display_timezone: LLM 输入展示时间的时区（IANA 时区名，例如 Asia/Shanghai）。
        context_message_limit: 检测时回溯的历史消息条数。
        pending_queue_limit: 未处理消息队列上限。
        history_list_limit: 滚动历史消息上限。
        detection_cooldown_seconds: 检测冷却时间（秒）。
        detection_min_new_messages: 检测触发所需最小新消息数。
        detection_wait_timeout_seconds: 检测等待超时时间（秒）。
        smtp_host: SMTP 邮件服务器主机。
        smtp_port: SMTP 端口。
        smtp_username: SMTP 用户名。
        smtp_password: SMTP 密码。
        smtp_sender: SMTP 发件人。
        email_notifier_enabled: 是否启用 Email 通知器。
        email_notifier_to_email: Email 通知器收件人。
        bark_notifier_enabled: 是否启用 Bark 通知器。
        bark_device_key: Bark 设备 Key。
        bark_device_keys: Bark 设备 Key 数组（用于批量推送）。
        bark_server_url: Bark 服务地址。
        bark_group: Bark 推送分组。
        bark_level: Bark 推送级别（如 active/timeSensitive/passive/critical）。
        hook_timeout_seconds: 外部 Hook 超时时间（秒）。
        enable_internal_rule_generation: 是否启用内置规则生成。
        external_rule_generation_endpoint: 外部规则生成 API 地址。
        enabled_adapters: 启用的 adapter 列表。
        onebot_host: OneBot WebSocket 服务器监听地址。
        onebot_port: OneBot WebSocket 服务器监听端口。
        onebot_access_token: OneBot 访问令牌。
        telegram_bot_token: Telegram Bot Token。
        telegram_polling_timeout: Telegram 长轮询超时时间（秒）。
        telegram_drop_pending_updates: 启动时是否丢弃待处理的 Telegram 更新。
        wechat_endpoint: WeChat 端点。
        feishu_app_id: 飞书 App ID。
        virtual_adapter_chat_count: 虚拟 adapter 聊天数。
        virtual_adapter_members_per_chat: 虚拟 adapter 每个聊天成员数。
        virtual_adapter_messages_per_chat: 虚拟 adapter 每个聊天消息数。
        virtual_adapter_interval_min_seconds: 虚拟 adapter 消息最小间隔（秒）。
        virtual_adapter_interval_max_seconds: 虚拟 adapter 消息最大间隔（秒）。
        virtual_adapter_script_path: 虚拟 adapter 脚本路径。
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    # database_url 仅通过环境变量配置，不存储在数据库中
    database_url: str = "sqlite:///./db.sqlite"
    app_name: str = "ChatGuardian"
    environment: str = "dev"

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
    llm_langchain_api_base: Optional[str] = None
    llm_langchain_api_key: Optional[str] = None
    llm_langchain_temperature: float = 0.0
    llm_ollama_base_url: str = "http://localhost:11434"
    llm_display_timezone: str = "Asia/Shanghai"

    # 从会话中获取历史消息条数
    context_message_limit: int = 10

    # 消息缓冲配置：未处理队列与滚动历史上限
    pending_queue_limit: int = 200
    history_list_limit: int = 1000

    # 检测触发配置：冷却、新消息最小数量、等待超时
    detection_cooldown_seconds: float = 0
    detection_min_new_messages: int = 1
    detection_wait_timeout_seconds: float = 30.0

    # SMTP 发信配置（可用于 EmailNotifier）
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_sender: Optional[str] = None

    email_notifier_enabled: bool = False
    email_notifier_to_email: Optional[str] = None

    bark_notifier_enabled: bool = False
    bark_device_key: Optional[str] = None
    bark_device_keys: list[str] = []
    bark_server_url: str = "https://api.day.app"
    bark_group: Optional[str] = None
    bark_level: Optional[str] = None

    # 外部 Hook 与规则生成端点
    hook_timeout_seconds: float = 8.0
    enable_internal_rule_generation: bool = True
    external_rule_generation_endpoint: Optional[str] = None

    # Adapter 插件配置
    enabled_adapters: list[str] = []

    # OneBot - 反向 WebSocket 连接方式
    # OneBot 实例需要配置连接到此服务，例如：ws://host:port/ws/event/
    onebot_host: str = "0.0.0.0"
    onebot_port: int = 2290
    onebot_access_token: Optional[str] = None

    telegram_bot_token: Optional[str] = None
    telegram_polling_timeout: int = 10
    telegram_drop_pending_updates: bool = False
    wechat_endpoint: Optional[str] = None
    feishu_app_id: Optional[str] = None

    # Virtual Adapter（测试用）配置
    virtual_adapter_chat_count: int = 3
    virtual_adapter_members_per_chat: int = 5
    virtual_adapter_messages_per_chat: int = 10
    virtual_adapter_interval_min_seconds: float = 0.1
    virtual_adapter_interval_max_seconds: float = 0.6
    virtual_adapter_script_path: Optional[str] = None


_env_overrides = _EnvConfig().model_dump(exclude_none=True)
settings = Settings(**_env_overrides)
