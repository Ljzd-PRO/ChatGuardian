from pydantic import BaseModel
from typing import Optional

class DiagnosticsModel(BaseModel):
    backend: str
    model: str
    client_class: str
    api_base: Optional[str]
    api_key_configured: bool
    ollama_base_url: Optional[str]

class RuleBatchSchedulerMetricsModel(BaseModel):
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
