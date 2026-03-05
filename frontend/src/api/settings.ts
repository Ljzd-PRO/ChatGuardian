import { apiFetch } from './client';

export interface AppSettings {
  // General
  app_name: string;
  environment: string;
  // LLM
  llm_langchain_backend: string;
  llm_langchain_model: string;
  llm_langchain_api_base: string | null;
  llm_langchain_api_key: string | null;
  llm_langchain_temperature: number;
  llm_timeout_seconds: number;
  llm_max_parallel_batches: number;
  llm_rules_per_batch: number;
  llm_ollama_base_url: string;
  llm_display_timezone: string;
  // Detection
  context_message_limit: number;
  detection_cooldown_seconds: number;
  detection_min_new_messages: number;
  detection_wait_timeout_seconds: number;
  pending_queue_limit: number;
  history_list_limit: number;
  // Notifications – Email
  email_notifier_enabled: boolean;
  email_notifier_to_email: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_password: string | null;
  smtp_sender: string | null;
  // Notifications – Bark
  bark_notifier_enabled: boolean;
  bark_device_key: string | null;
  bark_server_url: string;
  bark_group: string | null;
  bark_level: string | null;
  // Adapters
  enabled_adapters: string[];
  onebot_host: string;
  onebot_port: number;
  onebot_access_token: string | null;
  telegram_bot_token: string | null;
  telegram_polling_timeout: number;
  telegram_drop_pending_updates: boolean;
  // Rule generation
  enable_internal_rule_generation: boolean;
  external_rule_generation_endpoint: string | null;
}

export interface NotificationsConfig {
  email: {
    enabled: boolean;
    smtp_host: string | null;
    smtp_port: number;
    smtp_username: string | null;
    smtp_sender: string | null;
    to_email: string | null;
  };
  bark: {
    enabled: boolean;
    device_key: string | null;
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
export const updateSettings         = (s: Partial<AppSettings>) =>
  apiFetch<{ status: string }>('/api/settings', { method: 'POST', body: JSON.stringify(s) });
export const fetchNotificationsConfig = () => apiFetch<NotificationsConfig>('/api/notifications/config');
export const fetchLLMConfig           = () => apiFetch<LLMConfig>('/api/llm/config');
export const fetchLLMHealth           = () => apiFetch<Record<string, unknown>>('/llm/health');
