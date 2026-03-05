import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, CardHeader, Chip, Spinner,
} from '@heroui/react';
import { fetchSettings } from '../api/settings';

function Row({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  const display =
    value === null || value === undefined ? '—' :
    typeof value === 'boolean' ? (value ? 'Yes' : 'No') :
    String(value) || '—';
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-divider last:border-0">
      <span className="text-sm text-default-500">{label}</span>
      <span className="text-sm font-medium text-default-800 text-right max-w-xs truncate">{display}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <span className="font-semibold">{title}</span>
        <span className="ml-2 text-xs text-default-400">(read-only overview)</span>
      </CardHeader>
      <CardBody className="py-2">{children}</CardBody>
    </Card>
  );
}

export default function SettingsPage() {
  const { data: s, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading settings…" /></div>;
  if (!s) return null;

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center gap-2 text-default-500 text-sm p-3 bg-default-50 rounded-lg">
        <Chip size="sm" color="primary" variant="flat">ℹ</Chip>
        Settings are configured on their respective pages (Adapters, LLM, Notifications). This page provides a read-only overview of all active settings.
      </div>

      <Section title="General">
        <Row label="App Name" value={s.app_name} />
        <Row label="Environment" value={s.environment} />
      </Section>

      <Section title="LLM">
        <Row label="Backend" value={s.llm_langchain_backend} />
        <Row label="Model" value={s.llm_langchain_model} />
        <Row label="API Base" value={s.llm_langchain_api_base} />
        <Row label="API Key" value={s.llm_langchain_api_key ? '••••••••' : null} />
        <Row label="Temperature" value={s.llm_langchain_temperature} />
        <Row label="Timeout (s)" value={s.llm_timeout_seconds} />
        <Row label="Max Parallel Batches" value={s.llm_max_parallel_batches} />
        <Row label="Rules per Batch" value={s.llm_rules_per_batch} />
        <Row label="Ollama Base URL" value={s.llm_ollama_base_url} />
        <Row label="Display Timezone" value={s.llm_display_timezone} />
      </Section>

      <Section title="Detection">
        <Row label="Context Message Limit" value={s.context_message_limit} />
        <Row label="Cooldown (s)" value={s.detection_cooldown_seconds} />
        <Row label="Min New Messages" value={s.detection_min_new_messages} />
        <Row label="Wait Timeout (s)" value={s.detection_wait_timeout_seconds} />
        <Row label="Pending Queue Limit" value={s.pending_queue_limit} />
        <Row label="History List Limit" value={s.history_list_limit} />
      </Section>

      <Section title="Email Notifications">
        <Row label="Enabled" value={s.email_notifier_enabled} />
        <Row label="To Email" value={s.email_notifier_to_email} />
        <Row label="SMTP Host" value={s.smtp_host} />
        <Row label="SMTP Port" value={s.smtp_port} />
        <Row label="SMTP Username" value={s.smtp_username} />
        <Row label="SMTP Password" value="(write-only)" />
        <Row label="SMTP Sender" value={s.smtp_sender} />
      </Section>

      <Section title="Bark Notifications">
        <Row label="Enabled" value={s.bark_notifier_enabled} />
        <Row label="Device Key" value={s.bark_device_key ? '••••••••' : null} />
        <Row label="Server URL" value={s.bark_server_url} />
        <Row label="Group" value={s.bark_group} />
        <Row label="Level" value={s.bark_level} />
      </Section>

      <Section title="Adapters">
        <Row label="Enabled Adapters" value={s.enabled_adapters.length > 0 ? s.enabled_adapters.join(', ') : 'none'} />
        <Row label="OneBot Host" value={s.onebot_host} />
        <Row label="OneBot Port" value={s.onebot_port} />
        <Row label="OneBot Access Token" value={s.onebot_access_token ? '••••••••' : null} />
        <Row label="Telegram Bot Token" value={s.telegram_bot_token ? '••••••••' : null} />
        <Row label="Telegram Polling Timeout" value={s.telegram_polling_timeout} />
        <Row label="Drop Pending Updates" value={s.telegram_drop_pending_updates} />
      </Section>

      <Section title="Rule Generation">
        <Row label="Internal Rule Generation" value={s.enable_internal_rule_generation} />
        <Row label="External Endpoint" value={s.external_rule_generation_endpoint} />
      </Section>
    </div>
  );
}
