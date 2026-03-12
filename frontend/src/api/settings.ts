import { apiFetch } from './client';

export interface AppSettings {
  app_name: string;
  environment: string;
  llm_langchain_backend: string;
  llm_langchain_model: string;
  llm_langchain_api_base: string | null;
  llm_langchain_api_key: string | null;
  llm_langchain_temperature: number;
  llm_ollama_base_url: string;
  llm_display_timezone: string;
  llm_batch_timeout_seconds: number;
  llm_batch_max_retries: number;
  llm_batch_rate_limit_per_second: number;
  llm_batch_idempotency_cache_size: number;
  llm_timeout_seconds: number;
  llm_max_parallel_batches: number;
  llm_rules_per_batch: number;
  context_message_limit: number;
  pending_queue_limit: number;
  history_list_limit: number;
  detection_cooldown_seconds: number;
  detection_min_new_messages: number;
  detection_wait_timeout_seconds: number;
  email_notifier_enabled: boolean;
  email_notifier_to_email: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_password: string | null;
  smtp_sender: string | null;
  hook_timeout_seconds: number;
  enable_internal_rule_generation: boolean;
  external_rule_generation_endpoint: string | null;
  bark_notifier_enabled: boolean;
  bark_device_key: string | null;
  bark_device_keys: string[];
  bark_server_url: string;
  bark_group: string | null;
  bark_level: string | null;
  memory_target_user_ids: string[];
  enabled_adapters: string[];
  onebot_host: string;
  onebot_port: number;
  onebot_access_token: string | null;
  telegram_bot_token: string | null;
  telegram_polling_timeout: number;
  telegram_drop_pending_updates: boolean;
  wechat_endpoint: string | null;
  feishu_app_id: string | null;
  virtual_adapter_chat_count: number;
  virtual_adapter_members_per_chat: number;
  virtual_adapter_messages_per_chat: number;
  virtual_adapter_interval_min_seconds: number;
  virtual_adapter_interval_max_seconds: number;
  virtual_adapter_script_path: string | null;
}

export interface NotificationsConfig {
  email: {
    enabled: boolean;
    smtp_host: string | null;
    smtp_port: number;
    smtp_username: string | null;
    smtp_password: string | null;
    smtp_sender: string | null;
    to_email: string | null;
  };
  bark: {
    enabled: boolean;
    device_key: string | null;
    device_keys: string[];
    server_url: string;
    group: string | null;
    level: string | null;
  };
}

export interface LLMConfig {
  backend: string;
  model: string;
  api_base: string | null;
  temperature: number;
  timeout_seconds: number;
  max_parallel_batches: number;
  rules_per_batch: number;
  ollama_base_url: string;
}

export const fetchSettings          = () => apiFetch<AppSettings>('/api/settings');
export const updateSettings = (s: Partial<AppSettings>) => {
  // app_name and environment are injected via env (read-only); do not send to backend
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { app_name, environment, ...rest } = s;
  return apiFetch<{ status: string }>('/api/settings', { method: 'POST', body: JSON.stringify(rest) });
};
export const fetchNotificationsConfig = () => apiFetch<NotificationsConfig>('/api/notifications/config');
export const fetchLLMConfig           = () => apiFetch<LLMConfig>('/api/llm/config');
export const fetchLLMHealth           = () => apiFetch<Record<string, unknown>>('/llm/health');
