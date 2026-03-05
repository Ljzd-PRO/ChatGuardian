import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Input, Spinner, Switch,
} from '@heroui/react';
import { Play, Square, Save, Plus, X } from 'lucide-react';
import { fetchAdapters, startAdapters, stopAdapters } from '../api/adapters';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

export default function AdaptersPage() {
  const qc = useQueryClient();

  // Adapter runtime status
  const { data: adapters, isLoading: adaptersLoading } = useQuery({
    queryKey: ['adapters'],
    queryFn: fetchAdapters,
    refetchInterval: 5_000,
  });

  // Settings
  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
  });
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [newAdapter, setNewAdapter] = useState('');

  useEffect(() => { if (settingsData) setForm(settingsData); }, [settingsData]);

  const start = useMutation({ mutationFn: startAdapters, onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });
  const stop  = useMutation({ mutationFn: stopAdapters,  onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });

  const save = useMutation({
    mutationFn: () => updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  function set<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setForm(f => ({ ...f, [key]: value }));
  }

  function addAdapter() {
    const v = newAdapter.trim();
    if (!v) return;
    const current = form.enabled_adapters ?? [];
    if (!current.includes(v)) {
      set('enabled_adapters', [...current, v]);
    }
    setNewAdapter('');
  }

  function removeAdapter(name: string) {
    set('enabled_adapters', (form.enabled_adapters ?? []).filter(a => a !== name));
  }

  const isLoading = adaptersLoading || settingsLoading;
  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading adapters…" /></div>;

  return (
    <div className="space-y-6">
      {/* Runtime status */}
      <div className="flex gap-2">
        <Button
          color="success"
          variant="flat"
          startContent={<Play size={14} />}
          isLoading={start.isPending}
          onPress={() => start.mutate()}
        >
          Start All
        </Button>
        <Button
          color="danger"
          variant="flat"
          startContent={<Square size={14} />}
          isLoading={stop.isPending}
          onPress={() => stop.mutate()}
        >
          Stop All
        </Button>
      </div>

      {adapters?.length === 0 && (
        <p className="text-default-400 text-sm">No adapters running.</p>
      )}

      <div className="space-y-3">
        {adapters?.map(a => (
          <Card key={a.name}>
            <CardBody className="flex flex-row items-center justify-between">
              <div>
                <p className="font-medium text-default-900">{a.name}</p>
                <p className="text-xs text-default-400">Adapter</p>
              </div>
              <Chip color={a.running ? 'success' : 'default'} variant="flat" size="sm">
                {a.running ? 'Running' : 'Stopped'}
              </Chip>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Settings */}
      <Card>
        <CardHeader><span className="font-semibold">Enabled Adapters</span></CardHeader>
        <CardBody className="space-y-3">
          <div className="flex flex-wrap gap-2 min-h-8">
            {(form.enabled_adapters ?? []).map(a => (
              <Chip
                key={a}
                size="sm"
                variant="flat"
                endContent={
                  <button onClick={() => removeAdapter(a)} className="ml-1 text-default-400 hover:text-danger">
                    <X size={10} />
                  </button>
                }
              >
                {a}
              </Chip>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              size="sm"
              placeholder="Adapter name (e.g. onebot)"
              value={newAdapter}
              onValueChange={setNewAdapter}
              onKeyDown={e => e.key === 'Enter' && addAdapter()}
              className="flex-1"
            />
            <Button size="sm" startContent={<Plus size={14} />} onPress={addAdapter}>
              Add
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* OneBot Settings */}
      <Card>
        <CardHeader><span className="font-semibold">OneBot Settings</span></CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="Host"
            placeholder="0.0.0.0"
            value={form.onebot_host ?? ''}
            onValueChange={v => set('onebot_host', v)}
          />
          <Input
            label="Port"
            type="number"
            value={String(form.onebot_port ?? 2290)}
            onValueChange={v => set('onebot_port', Number(v))}
          />
          <Input
            label="Access Token"
            type="password"
            value={form.onebot_access_token ?? ''}
            onValueChange={v => set('onebot_access_token', v || null)}
          />
        </CardBody>
      </Card>

      {/* Telegram Settings */}
      <Card>
        <CardHeader><span className="font-semibold">Telegram Settings</span></CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="Bot Token"
            type="password"
            value={form.telegram_bot_token ?? ''}
            onValueChange={v => set('telegram_bot_token', v || null)}
          />
          <Input
            label="Polling Timeout (s)"
            type="number"
            value={String(form.telegram_polling_timeout ?? 10)}
            onValueChange={v => set('telegram_polling_timeout', Number(v))}
          />
          <Switch
            isSelected={form.telegram_drop_pending_updates ?? false}
            onValueChange={v => set('telegram_drop_pending_updates', v)}
          >
            Drop Pending Updates on Start
          </Switch>
        </CardBody>
      </Card>

      <Button
        color="primary"
        startContent={<Save size={14} />}
        isLoading={save.isPending}
        onPress={() => save.mutate()}
      >
        Save Adapter Settings
      </Button>
      {save.isSuccess && <p className="text-success text-sm">✓ Saved successfully.</p>}
      {save.isError && <p className="text-danger text-sm">✗ Save failed.</p>}
    </div>
  );
}
