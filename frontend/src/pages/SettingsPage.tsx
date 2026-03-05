import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Input, Select, SelectItem, Spinner,
} from '@heroui/react';
import { Save } from 'lucide-react';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

export default function SettingsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [form, setForm] = useState<Partial<AppSettings>>({});

  useEffect(() => { if (data) setForm(data); }, [data]);

  const save = useMutation({ mutationFn: () => updateSettings(form) });

  function set<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setForm(f => ({ ...f, [key]: value }));
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading settings…" /></div>;

  return (
    <div className="space-y-4 max-w-2xl">
      {/* General */}
      <Card>
        <CardHeader><span className="font-semibold">General</span></CardHeader>
        <CardBody className="space-y-3">
          <Input label="App Name" value={form.app_name ?? ''} onValueChange={v => set('app_name', v)} />
          <Select
            label="Environment"
            selectedKeys={[form.environment ?? 'dev']}
            onSelectionChange={k => set('environment', Array.from(k)[0] as string)}
          >
            <SelectItem key="dev">dev</SelectItem>
            <SelectItem key="prod">prod</SelectItem>
          </Select>
        </CardBody>
      </Card>

      {/* Detection */}
      <Card>
        <CardHeader><span className="font-semibold">Detection</span></CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="Cooldown Seconds"
            type="number"
            value={String(form.detection_cooldown_seconds ?? 0)}
            onValueChange={v => set('detection_cooldown_seconds', Number(v))}
          />
          <Input
            label="Min New Messages"
            type="number"
            value={String(form.detection_min_new_messages ?? 1)}
            onValueChange={v => set('detection_min_new_messages', Number(v))}
          />
          <Input
            label="Context Message Limit"
            type="number"
            value={String(form.context_message_limit ?? 10)}
            onValueChange={v => set('context_message_limit', Number(v))}
          />
        </CardBody>
      </Card>

      {/* LLM */}
      <Card>
        <CardHeader><span className="font-semibold">LLM</span></CardHeader>
        <CardBody className="space-y-3">
          <Select
            label="Backend"
            selectedKeys={[form.llm_langchain_backend ?? 'openai_compatible']}
            onSelectionChange={k => set('llm_langchain_backend', Array.from(k)[0] as string)}
          >
            <SelectItem key="openai_compatible">OpenAI Compatible</SelectItem>
            <SelectItem key="ollama">Ollama</SelectItem>
          </Select>
          <Input label="Model" value={form.llm_langchain_model ?? ''} onValueChange={v => set('llm_langchain_model', v)} />
          <Input label="API Base" value={form.llm_langchain_api_base ?? ''} onValueChange={v => set('llm_langchain_api_base', v)} />
          <Input label="API Key" type="password" value={form.llm_langchain_api_key ?? ''} onValueChange={v => set('llm_langchain_api_key', v)} />
          <Input
            label="Temperature"
            type="number"
            step="0.1"
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
        </CardBody>
      </Card>

      <Button
        color="primary"
        startContent={<Save size={14} />}
        isLoading={save.isPending}
        onPress={() => save.mutate()}
      >
        Save Settings
      </Button>
      {save.isSuccess && <p className="text-success text-sm">✓ Saved successfully.</p>}
      {save.isError && <p className="text-danger text-sm">✗ Save failed.</p>}
    </div>
  );
}
