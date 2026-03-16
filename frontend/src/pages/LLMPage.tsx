import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Select, SelectItem, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import boxBold from '@iconify/icons-solar/box-bold';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import databaseBold from '@iconify/icons-solar/database-bold';
import earthBold from '@iconify/icons-solar/earth-bold';
import keyBold from '@iconify/icons-solar/key-bold';
import layersBold from '@iconify/icons-solar/layers-bold';
import lightningBold from '@iconify/icons-solar/lightning-bold';
import linkBold from '@iconify/icons-solar/link-bold';
import pulse2Bold from '@iconify/icons-solar/pulse-2-bold';
import thermometerBold from '@iconify/icons-solar/thermometer-bold';
import { useTranslation } from 'react-i18next';
import { fetchLLMHealth, fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';

export default function LLMPage() {
  const { t } = useTranslation();
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

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('llm.loading')} /></div>;

  return (
    <div className="space-y-4 max-w-3xl">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">{t('llm.title')}</span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              color="primary"
              variant="flat"
              startContent={<Icon icon={lightningBold} fontSize={ICON_SIZES.button} />}
              isLoading={pinging}
              onPress={doPing}
            >
              {t('llm.ping')}
            </Button>
            <Button
              size="sm"
              color="success"
              isLoading={save.isPending}
              onPress={() => save.mutate()}
            >
              {t('common.save')}
            </Button>
          </div>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          {pingResult && (
            <div className={`p-3 rounded-lg text-sm ${pingResult.ok ? 'bg-success-50 text-success-700' : 'bg-danger-50 text-danger-700'}`}>
              {pingResult.ok
                ? t('llm.connected', { latency: pingResult.latency_ms })
                : t('llm.failed', { error: pingResult.error })}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Select
              label={t('llm.backend')}
              selectedKeys={[form.llm_langchain_backend ?? 'openai_compatible']}
              onSelectionChange={k => setForm(f => ({ ...f, llm_langchain_backend: Array.from(k)[0] as string }))}
            >
              <SelectItem key="openai_compatible">{t('llm.openai')}</SelectItem>
              <SelectItem key="ollama">{t('llm.ollama')}</SelectItem>
              <SelectItem key="gemini">Google Gemini</SelectItem>
              <SelectItem key="anthropic">Anthropic Claude</SelectItem>
              <SelectItem key="openrouter">OpenRouter</SelectItem>
            </Select>
            <Input
              label={t('llm.model')}
              startContent={<Icon icon={cpuBoltBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.llm_langchain_model ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_model: v }))}
            />
            <Input
              label={t('llm.apiBase')}
              startContent={<Icon icon={linkBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.llm_langchain_api_base ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_base: v.trim() === '' ? null : v }))}
            />
            <Input
              label={t('llm.apiKey')}
              type="password"
              startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.llm_langchain_api_key ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_key: v.trim() === '' ? null : v }))}
            />
            <Input
              label={t('llm.temperature')}
              type="number"
              step="0.05"
              startContent={<Icon icon={thermometerBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_langchain_temperature ?? 0)}
              onValueChange={v => setForm(f => ({ ...f, llm_langchain_temperature: Number(v) }))}
            />
            <Input
              label={t('llm.displayTimezone')}
              startContent={<Icon icon={earthBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.llm_display_timezone ?? ''}
              onValueChange={v => setForm(f => ({ ...f, llm_display_timezone: v }))}
            />
            <Input
              label={t('llm.timeout')}
              type="number"
              startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_timeout_seconds ?? 30)}
              onValueChange={v => setForm(f => ({ ...f, llm_timeout_seconds: Number(v) }))}
            />
            <Input
              label={t('llm.maxParallelBatches')}
              type="number"
              startContent={<Icon icon={layersBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_max_parallel_batches ?? 3)}
              onValueChange={v => setForm(f => ({ ...f, llm_max_parallel_batches: Number(v) }))}
            />
            <Input
              label={t('llm.rulesPerBatch')}
              type="number"
              startContent={<Icon icon={boxBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_rules_per_batch ?? 2)}
              onValueChange={v => setForm(f => ({ ...f, llm_rules_per_batch: Number(v) }))}
            />
            <Input
              label={t('llm.batchTimeout')}
              type="number"
              startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_batch_timeout_seconds ?? 30)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_timeout_seconds: Number(v) }))}
            />
            <Input
              label={t('llm.batchMaxRetries')}
              type="number"
              startContent={<Icon icon={pulse2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_batch_max_retries ?? 1)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_max_retries: Number(v) }))}
            />
            <Input
              label={t('llm.batchRateLimit')}
              type="number"
              startContent={<Icon icon={chart2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_batch_rate_limit_per_second ?? 0)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_rate_limit_per_second: Number(v) }))}
            />
            <Input
              label={t('llm.idempotencyCacheSize')}
              type="number"
              startContent={<Icon icon={databaseBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.llm_batch_idempotency_cache_size ?? 1024)}
              onValueChange={v => setForm(f => ({ ...f, llm_batch_idempotency_cache_size: Number(v) }))}
            />
          </div>

          {save.isSuccess && <p className="text-success text-sm">{t('common.saveSuccess')}</p>}
          {save.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
        </CardBody>
      </Card>

      <LLMHealthCard />
    </div>
  );
}

function LLMHealthCard() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ['llm_health'],
    queryFn: () => fetchLLMHealth(),
    refetchInterval: 60_000,
  });

  if (isLoading) return null;
  const sched = data?.scheduler as Record<string, unknown> | undefined;

  return (
    <Card>
      <CardHeader><span className="font-semibold">{t('llm.batchScheduler')}</span></CardHeader>
      <CardBody className="space-y-2">
        {sched
          ? Object.entries(sched).map(([k, v]) => (
            <div key={k} className="py-2 border-b border-divider last:border-0 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-default-500">{k}</span>
                {typeof v === 'object' && v !== null ? (
                  <Chip size="sm" variant="flat" color="secondary">
                    {t('stats.viewDetails')}
                  </Chip>
                ) : (
                  <span className="text-sm font-medium text-default-800">{String(v)}</span>
                )}
              </div>
              {typeof v === 'object' && v !== null && (
                <details className="rounded-medium border border-default-200 bg-default-50 p-3 text-sm text-default-700">
                  <summary className="cursor-pointer text-primary text-sm">{t('stats.viewDetails')}</summary>
                  <div className="mt-2 space-y-1">
                    {Object.entries(v as Record<string, unknown>).map(([mk, mv]) => (
                      <div key={mk} className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-default-500">{mk}</span>
                        <span className="font-mono text-default-800 break-all">{typeof mv === 'object' && mv !== null ? JSON.stringify(mv) : String(mv)}</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))
          : <p className="text-sm text-default-400">{t('llm.noScheduler')}</p>}
        <div className="flex items-center justify-between py-1">
          <span className="text-sm text-default-500">{t('llm.status')}</span>
          <Chip size="sm" color={data?.status === 'ok' ? 'success' : 'warning'} variant="flat">
            {String(data?.status ?? 'unknown')}
          </Chip>
        </div>
      </CardBody>
    </Card>
  );
}
