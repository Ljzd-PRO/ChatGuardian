import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Select, SelectItem, Spinner,
} from '@heroui/react';
import { Zap } from 'lucide-react';
import { fetchLLMHealth, fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

export default function LLMPage() {
  const { data: settings, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [pinging, setPinging] = useState(false);
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [pingResult, setPingResult] = useState<{ ok: boolean; latency_ms: number; error?: string } | null>(null);

  useEffect(() => {
    if (settings) {
      setForm({
        llm_langchain_backend: settings.llm_langchain_backend,
        llm_langchain_model: settings.llm_langchain_model,
        llm_langchain_api_base: settings.llm_langchain_api_base ?? '',
        llm_langchain_api_key: settings.llm_langchain_api_key ?? '',
        llm_langchain_temperature: settings.llm_langchain_temperature,
        llm_timeout_seconds: settings.llm_timeout_seconds,
        llm_max_parallel_batches: settings.llm_max_parallel_batches,
        llm_rules_per_batch: settings.llm_rules_per_batch,
        llm_ollama_base_url: settings.llm_ollama_base_url,
        llm_display_timezone: settings.llm_display_timezone,
        llm_batch_timeout_seconds: settings.llm_batch_timeout_seconds,
        llm_batch_max_retries: settings.llm_batch_max_retries,
        llm_batch_rate_limit_per_second: settings.llm_batch_rate_limit_per_second,
        llm_batch_idempotency_cache_size: settings.llm_batch_idempotency_cache_size,
      });
    }
  }, [settings]);

  const save = useMutation({
    mutationFn: () => updateSettings(form),
  });

  async function doPing() {
    setPinging(true);
    try {
      const r = await fetchLLMHealth() as { ping?: { ok: boolean; latency_ms: number; error?: string } };
      if (r.ping) setPingResult(r.ping);
    } catch {
      setPingResult({ ok: false, latency_ms: 0, error: 'Request failed' });
    } finally {
      setPinging(false);
    }
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading LLM config…" /></div>;

  return (
    <div className="space-y-4 max-w-3xl">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">LLM Configuration</span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              color="primary"
              variant="flat"
              startContent={<Zap size={14} />}
              isLoading={pinging}
              onPress={doPing}
            >
              Ping
            </Button>
            <Button
              size="sm"
              color="success"
              isLoading={save.isPending}
              onPress={() => save.mutate()}
            >
              Save
            </Button>
          </div>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          {pingResult && (
            <div className={`p-3 rounded-lg text-sm ${pingResult.ok ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'}`}>
              {pingResult.ok
                ? `✓ Connected — ${pingResult.latency_ms}ms`
                : `✗ Failed — ${pingResult.error}`}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Select
              label="Backend"
              selectedKeys={[form.llm_langchain_backend ?? 'openai_compatible']}
              onSelectionChange={k => setForm(f => ({ ...f, llm_langchain_backend: Array.from(k)[0] as string }))}
            >
              <SelectItem key="openai_compatible">OpenAI Compatible</SelectItem>
              <SelectItem key="ollama">Ollama</SelectItem>
            </Select>
            <Input label="Model" value={form.llm_langchain_model ?? ''} onValueChange={v => setForm(f => ({ ...f, llm_langchain_model: v }))} />
            <Input
              label="API Base"
              value={form.llm_langchain_api_base ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_base: v.trim() === '' ? null : v }))}
            />
            <Input
              label="API Key"
              type="password"
              value={form.llm_langchain_api_key ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_key: v.trim() === '' ? null : v }))}
            />
            <Input
              label="Temperature"
              type="number"
              step="0.05"
              value={String(form.llm_langchain_temperature ?? 0)}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_temperature: Number(v) }))}
            />
            <Input label="Display Timezone" value={form.llm_display_timezone ?? ''} onValueChange={v => setForm(f => ({ ...f, llm_display_timezone: v }))} />
            <Input
              label="Timeout (seconds)"
              type="number"
              value={String(form.llm_timeout_seconds ?? 30)}
              onValueChange={v => setForm(f => ({ ...f, llm_timeout_seconds: Number(v) }))}
            />
            <Input
              label="Max Parallel Batches"
              type="number"
              value={String(form.llm_max_parallel_batches ?? 3)}
              onValueChange={v => setForm(f => ({ ...f, llm_max_parallel_batches: Number(v) }))}
            />
            <Input
              label="Rules per Batch"
              type="number"
              value={String(form.llm_rules_per_batch ?? 2)}
              onValueChange={v => setForm(f => ({ ...f, llm_rules_per_batch: Number(v) }))}
            />
            <Input
              label="Batch Timeout (seconds)"
              type="number"
              value={String(form.llm_batch_timeout_seconds ?? 30)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_timeout_seconds: Number(v) }))}
            />
            <Input
              label="Batch Max Retries"
              type="number"
              value={String(form.llm_batch_max_retries ?? 1)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_max_retries: Number(v) }))}
            />
            <Input
              label="Batch Rate Limit (per second)"
              type="number"
              value={String(form.llm_batch_rate_limit_per_second ?? 0)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_rate_limit_per_second: Number(v) }))}
            />
            <Input
              label="Idempotency Cache Size"
              type="number"
              value={String(form.llm_batch_idempotency_cache_size ?? 1024)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_idempotency_cache_size: Number(v) }))}
            />
            <Input
              label="Ollama Base URL"
              value={form.llm_ollama_base_url ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_ollama_base_url: v }))}
            />
          </div>

          {save.isSuccess && <p className="text-success text-sm">Saved successfully.</p>}
          {save.isError && <p className="text-danger text-sm">Save failed.</p>}
        </CardBody>
      </Card>

      <LLMHealthCard />
    </div>
  );
}

function LLMHealthCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['llm_health'],
    queryFn: () => fetchLLMHealth(),
    refetchInterval: 60_000,
  });

  if (isLoading) return null;
  const sched = data?.scheduler as Record<string, unknown> | undefined;

  return (
    <Card>
      <CardHeader><span className="font-semibold">Batch Scheduler</span></CardHeader>
      <CardBody className="space-y-2">
        {sched
          ? Object.entries(sched).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-1 border-b border-divider last:border-0">
                <span className="text-sm text-default-500">{k}</span>
                <span className="text-sm font-medium text-default-800">{String(v)}</span>
              </div>
            ))
          : <p className="text-sm text-default-400">No scheduler data</p>}
        <div className="flex items-center justify-between py-1">
          <span className="text-sm text-default-500">Status</span>
          <Chip size="sm" color={data?.status === 'ok' ? 'success' : 'warning'} variant="flat">
            {String(data?.status ?? 'unknown')}
          </Chip>
        </div>
      </CardBody>
    </Card>
  );
}
