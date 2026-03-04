import { apiFetch } from './client';

export interface AppSettings {
  app_name: string;
  environment: string;
  llm_langchain_backend: string;
  llm_langchain_model: string;
  llm_langchain_api_base: string | null;
  llm_langchain_api_key: string | null;
  llm_langchain_temperature: number;
  llm_timeout_seconds: number;
  llm_max_parallel_batches: number;
  llm_rules_per_batch: number;
  context_message_limit: number;
  detection_cooldown_seconds: number;
  detection_min_new_messages: number;
  email_notifier_enabled: boolean;
  email_notifier_to_email: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_sender: string | null;
  bark_notifier_enabled: boolean;
  bark_device_key: string | null;
  bark_server_url: string;
  bark_group: string | null;
  enabled_adapters: string[];
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
