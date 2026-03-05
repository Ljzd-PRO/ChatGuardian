import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, CardBody, CardHeader, Chip, Spinner } from '@heroui/react';
import { Zap } from 'lucide-react';
import { fetchLLMConfig, fetchLLMHealth } from '../api/settings';

export default function LLMPage() {
  const { data: config, isLoading } = useQuery({ queryKey: ['llm_config'], queryFn: fetchLLMConfig });
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState<{ ok: boolean; latency_ms: number; error?: string } | null>(null);

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

  const rows: [string, string | number | null | undefined][] = config ? [
    ['Backend', config.backend],
    ['Model', config.model],
    ['API Base', config.api_base ?? '(default)'],
    ['Temperature', config.temperature],
    ['Timeout (s)', config.timeout_seconds],
    ['Max Parallel Batches', config.max_parallel_batches],
    ['Rules per Batch', config.rules_per_batch],
    ['Ollama Base URL', config.ollama_base_url],
  ] : [];

  return (
    <div className="space-y-4 max-w-2xl">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">LLM Configuration</span>
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
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between py-1 border-b border-divider last:border-0">
              <span className="text-sm text-default-500">{label}</span>
              <span className="text-sm font-medium text-default-800">{String(value ?? '—')}</span>
            </div>
          ))}
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
