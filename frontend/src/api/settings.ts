import { apiFetch } from './client';

export interface AppSettings {
  cors_allow_origins: string[];
  llm_langchain_backend: string;
  llm_langchain_model: string;
  llm_langchain_api_base: string | null;
  llm_langchain_api_key: string | null;
  llm_langchain_temperature: number;
  llm_display_timezone: string;
  rule_detection_system_prompt: string | null;
  user_profile_system_prompt: string | null;
  admin_agent_system_prompt: string | null;
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
  detection_self_sender_ids: string[];
  enable_image_parsing: boolean;
  max_images: number;
  enable_image_compression: boolean;
  image_compression_max_width: number;
  image_compression_max_height: number;
  email_notifier_enabled: boolean;
  email_notifier_to_email: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_password: string | null;
  smtp_sender: string | null;
  hook_timeout_seconds: number;
  bark_notifier_enabled: boolean;
  bark_device_key: string | null;
  bark_device_keys: string[];
  bark_server_url: string;
  bark_group: string | null;
  bark_level: string | null;
  notification_text_template: string | null;
  memory_target_user_ids: string[];
  user_memory_min_new_messages: number;
  enabled_adapters: string[];
  onebot_host: string;
  onebot_port: number;
  onebot_access_token: string | null;
  telegram_bot_token: string | null;
  telegram_polling_timeout: number;
  telegram_drop_pending_updates: boolean;
  discord_bot_token: string | null;
  discord_guild_ids: number[];
  wechat_token: string | null;
  wechat_encoding_aes_key: string | null;
  wechat_corp_id: string | null;
  wechat_host: string;
  wechat_port: number;
  dingtalk_client_id: string | null;
  dingtalk_client_secret: string | null;
  feishu_app_id: string | null;
  virtual_adapter_chat_count: number;
  virtual_adapter_members_per_chat: number;
  virtual_adapter_messages_per_chat: number;
  virtual_adapter_interval_min_seconds: number;
  virtual_adapter_interval_max_seconds: number;
  virtual_adapter_script_path: string | null;
  mcp_http_enabled: boolean;
  mcp_http_transport: 'sse' | 'streamable-http';
  mcp_http_host: string;
  mcp_http_port: number;
  mcp_http_path: string;
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

export interface DefaultPrompts {
  rule_detection_system_prompt: string;
  user_profile_system_prompt: string;
  admin_agent_system_prompt: string;
}

export interface DefaultNotificationTemplate {
  notification_text_template: string;
}

export const fetchSettings = () => apiFetch<AppSettings>('/api/settings');
export const updateSettings = (s: Partial<AppSettings>) =>
  apiFetch<{ status: string }>('/api/settings', { method: 'POST', body: JSON.stringify(s) });
export const fetchDefaultPrompts = () => apiFetch<DefaultPrompts>('/api/prompts/defaults');
export const fetchDefaultNotificationTemplate = () => apiFetch<DefaultNotificationTemplate>('/api/notifications/default-template');
export const fetchNotificationsConfig = () => apiFetch<NotificationsConfig>('/api/notifications/config');
export const fetchLLMConfig = () => apiFetch<LLMConfig>('/api/llm/config');
export const fetchLLMHealth = () => apiFetch<Record<string, unknown>>('/llm/health');
export const testNotification = (type: 'email' | 'bark') =>
  apiFetch<{ ok: boolean }>(`/api/notifications/test/${type}`, { method: 'POST' });
