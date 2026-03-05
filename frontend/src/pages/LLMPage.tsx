import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Input, Select, SelectItem, Spinner,
} from '@heroui/react';
import { Save, Zap } from 'lucide-react';
import { fetchSettings, updateSettings, fetchLLMHealth } from '../api/settings';
import type { AppSettings } from '../api/settings';

export default function LLMPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [form, setForm] = useState<Partial<AppSettings>>({});

  useEffect(() => { if (data) setForm(data); }, [data]);

  const save = useMutation({
    mutationFn: () => updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  function set<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setForm(f => ({ ...f, [key]: value }));
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading LLM settings…" /></div>;

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Connection & Model */}
      <Card>
        <CardHeader><span className="font-semibold">LLM Connection</span></CardHeader>
        <CardBody className="space-y-3">
          <Select
            label="Backend"
            selectedKeys={[form.llm_langchain_backend ?? 'openai_compatible']}
            onSelectionChange={k => set('llm_langchain_backend', Array.from(k)[0] as string)}
          >
            <SelectItem key="openai_compatible">OpenAI Compatible</SelectItem>
            <SelectItem key="ollama">Ollama</SelectItem>
          </Select>
          <Input
            label="Model"
            value={form.llm_langchain_model ?? ''}
            onValueChange={v => set('llm_langchain_model', v)}
          />
          <Input
            label="API Base URL"
            placeholder="https://api.openai.com/v1"
            value={form.llm_langchain_api_base ?? ''}
            onValueChange={v => set('llm_langchain_api_base', v || null)}
          />
          <Input
            label="API Key"
            type="password"
            value={form.llm_langchain_api_key ?? ''}
            onValueChange={v => set('llm_langchain_api_key', v || null)}
          />
          <Input
            label="Ollama Base URL"
            placeholder="http://localhost:11434"
            value={form.llm_ollama_base_url ?? ''}
            onValueChange={v => set('llm_ollama_base_url', v)}
          />
        </CardBody>
      </Card>

      {/* Tuning */}
      <Card>
        <CardHeader><span className="font-semibold">Tuning</span></CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="Temperature"
            type="number"
            step="0.1"
            min={0}
            max={2}
            value={String(form.llm_langchain_temperature ?? 0)}
            onValueChange={v => set('llm_langchain_temperature', Number(v))}
          />
          <Input
            label="Timeout (seconds)"
            type="number"
            value={String(form.llm_timeout_seconds ?? 30)}
            onValueChange={v => set('llm_timeout_seconds', Number(v))}
          />
          <Input
            label="Max Parallel Batches"
            type="number"
            value={String(form.llm_max_parallel_batches ?? 3)}
            onValueChange={v => set('llm_max_parallel_batches', Number(v))}
          />
          <Input
            label="Rules per Batch"
            type="number"
            value={String(form.llm_rules_per_batch ?? 2)}
            onValueChange={v => set('llm_rules_per_batch', Number(v))}
          />
          <Input
            label="Display Timezone"
            placeholder="Asia/Shanghai"
            value={form.llm_display_timezone ?? ''}
            onValueChange={v => set('llm_display_timezone', v)}
          />
        </CardBody>
      </Card>

      <Button
        color="primary"
        startContent={<Save size={14} />}
        isLoading={save.isPending}
        onPress={() => save.mutate()}
      >
        Save LLM Settings
      </Button>
      {save.isSuccess && <p className="text-success text-sm">✓ Saved successfully.</p>}
      {save.isError && <p className="text-danger text-sm">✗ Save failed.</p>}

      {/* Health / Ping */}
      <LLMHealthCard />
    </div>
  );
}

function LLMHealthCard() {
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState<{ ok: boolean; latency_ms: number; error?: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['llm_health'],
    queryFn: () => fetchLLMHealth(),
    refetchInterval: 60_000,
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

  const sched = data?.scheduler as Record<string, unknown> | undefined;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <span className="font-semibold">Health &amp; Scheduler</span>
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
      </CardHeader>
      <CardBody className="space-y-2">
        {pingResult && (
          <div className={`p-3 rounded-lg text-sm ${pingResult.ok ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'}`}>
            {pingResult.ok
              ? `✓ Connected — ${pingResult.latency_ms}ms`
              : `✗ Failed — ${pingResult.error}`}
          </div>
        )}
        {!isLoading && (
          <>
            {sched
              ? Object.entries(sched).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1 border-b border-divider last:border-0">
                    <span className="text-sm text-default-500">{k}</span>
                    <span className="text-sm font-medium text-default-800">{String(v)}</span>
                  </div>
                ))
              : null}
            <div className="flex items-center justify-between py-1">
              <span className="text-sm text-default-500">Status</span>
              <Chip size="sm" color={data?.status === 'ok' ? 'success' : 'warning'} variant="flat">
                {String(data?.status ?? 'unknown')}
              </Chip>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
