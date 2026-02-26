from pydantic import BaseModel
from typing import Optional

class DiagnosticsModel(BaseModel):
    """
    后端诊断信息模型。

    Attributes:
        backend: LLM 后端类型。
        model: 使用的模型名称。
        client_class: 客户端类名。
        api_base: API 基础地址。
        api_key_configured: API 密钥是否已配置。
        ollama_base_url: Ollama 基础地址。
    """
    backend: str
    model: str
    client_class: str
    api_base: Optional[str]
    api_key_configured: bool
    ollama_base_url: Optional[str]

class RuleBatchSchedulerMetricsModel(BaseModel):
    """
    批处理调度器指标模型。

    Attributes:
        total_requests: 总请求数。
        total_batches: 总批次数。
        total_llm_calls: LLM 调用总数。
        successful_batches: 成功批次数。
        fallback_batches: 回退批次数。
        retry_attempts: 重试次数。
        batch_timeouts: 批处理超时次数。
        idempotency_completed_hits: 幂等完成命中数。
        idempotency_inflight_hits: 幂等进行中命中数。
        rate_limit_wait_count: 限流等待次数。
        rate_limit_wait_ms: 限流等待总时长（毫秒）。
    """
    total_requests: int
    total_batches: int
    total_llm_calls: int
    successful_batches: int
    fallback_batches: int
    retry_attempts: int
    batch_timeouts: int
    idempotency_completed_hits: int
    idempotency_inflight_hits: int
    rate_limit_wait_count: int
    rate_limit_wait_ms: float

class RuleBatchSchedulerDiagnosticsModel(BaseModel):
    """
    批处理调度器诊断信息模型。

    Attributes:
        batch_size: 批处理大小。
        max_parallel_batches: 最大并行批次数。
        batch_timeout_seconds: 批处理超时时间（秒）。
        max_retries: 最大重试次数。
        rate_limit_per_second: 限流速率（每秒）。
        idempotency_cache_size: 幂等缓存大小。
        idempotency_completed_cache_entries: 幂等完成缓存条目数。
        idempotency_inflight_entries: 幂等进行中条目数。
        metrics: 调度器指标。
    """
    batch_size: int
    max_parallel_batches: int
    batch_timeout_seconds: float
    max_retries: int
    rate_limit_per_second: float
    idempotency_cache_size: int
    idempotency_completed_cache_entries: int
    idempotency_inflight_entries: int
    metrics: RuleBatchSchedulerMetricsModel

# 可根据后续梳理结果继续补充 payload、其他 dict 结构
