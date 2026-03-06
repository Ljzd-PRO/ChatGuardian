import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Select, SelectItem, Spinner, Switch,
} from '@heroui/react';
import { Play, Square } from 'lucide-react';
import { fetchAdapters, startAdapters, stopAdapters } from '../api/adapters';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

export default function AdaptersPage() {
  const qc = useQueryClient();
  const { data: adapters, isLoading } = useQuery({
    queryKey: ['adapters'],
    queryFn: fetchAdapters,
    refetchInterval: 5_000,
  });
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });

  const [form, setForm] = useState<Partial<AppSettings>>({});

  useEffect(() => {
    if (!settings) return;
    setForm({
      enabled_adapters: settings.enabled_adapters ?? [],
      onebot_host: settings.onebot_host,
      onebot_port: settings.onebot_port,
      onebot_access_token: settings.onebot_access_token ?? '',
      telegram_bot_token: settings.telegram_bot_token ?? '',
      telegram_polling_timeout: settings.telegram_polling_timeout,
      telegram_drop_pending_updates: settings.telegram_drop_pending_updates,
      wechat_endpoint: settings.wechat_endpoint ?? '',
      feishu_app_id: settings.feishu_app_id ?? '',
      virtual_adapter_chat_count: settings.virtual_adapter_chat_count,
      virtual_adapter_members_per_chat: settings.virtual_adapter_members_per_chat,
      virtual_adapter_messages_per_chat: settings.virtual_adapter_messages_per_chat,
      virtual_adapter_interval_min_seconds: settings.virtual_adapter_interval_min_seconds,
      virtual_adapter_interval_max_seconds: settings.virtual_adapter_interval_max_seconds,
      virtual_adapter_script_path: settings.virtual_adapter_script_path ?? '',
    });
  }, [settings]);

  const start = useMutation({ mutationFn: startAdapters, onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });
  const stop  = useMutation({ mutationFn: stopAdapters,  onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });
  const save  = useMutation({
    mutationFn: () => updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading adapters…" /></div>;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">Adapter Controls</span>
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
        </CardHeader>
        <Divider />
        <CardBody className="space-y-3">
          {adapters?.length === 0 && (
            <p className="text-default-400 text-sm">No adapters configured.</p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
        </CardBody>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">Adapter Settings</span>
          <Button color="primary" isDisabled={!settings} isLoading={save.isPending} onPress={() => save.mutate()}>Save</Button>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Select
              label="Enabled Adapters"
              selectionMode="multiple"
              selectedKeys={new Set(form.enabled_adapters ?? [])}
              onSelectionChange={keys => setForm(f => ({ ...f, enabled_adapters: Array.from(keys) as string[] }))}
            >
              {['onebot', 'telegram', 'wechat', 'feishu', 'virtual'].map(a => (
                <SelectItem key={a}>{a}</SelectItem>
              ))}
            </Select>
            <Input label="OneBot Host" value={form.onebot_host ?? ''} onValueChange={v => setForm(f => ({ ...f, onebot_host: v }))} />
            <Input label="OneBot Port" type="number" value={String(form.onebot_port ?? 2290)} onValueChange={v => setForm(f => ({ ...f, onebot_port: Number(v) }))} />
            <Input
              label="OneBot Access Token"
              value={form.onebot_access_token ?? ''}
              onValueChange={v => setForm(f => ({ ...f, onebot_access_token: v.trim() === '' ? null : v }))}
            />
            <Input
              label="Telegram Bot Token"
              value={form.telegram_bot_token ?? ''}
              onValueChange={v => setForm(f => ({ ...f, telegram_bot_token: v.trim() === '' ? null : v }))}
            />
            <Input label="Telegram Polling Timeout" type="number" value={String(form.telegram_polling_timeout ?? 10)} onValueChange={v => setForm(f => ({ ...f, telegram_polling_timeout: Number(v) }))} />
            <Switch isSelected={form.telegram_drop_pending_updates ?? false} onValueChange={v => setForm(f => ({ ...f, telegram_drop_pending_updates: v }))}>
              Telegram Drop Pending Updates
            </Switch>
            <Input
              label="WeChat Endpoint"
              value={form.wechat_endpoint ?? ''}
              onValueChange={v => setForm(f => ({ ...f, wechat_endpoint: v.trim() === '' ? null : v }))}
            />
            <Input
              label="Feishu App ID"
              value={form.feishu_app_id ?? ''}
              onValueChange={v => setForm(f => ({ ...f, feishu_app_id: v.trim() === '' ? null : v }))}
            />
          </div>

          <Divider />
          <p className="text-sm font-medium text-default-700">Virtual Adapter</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input
              label="Chat Count"
              type="number"
              value={String(form.virtual_adapter_chat_count ?? 3)}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_chat_count: Number(v) }))}
            />
            <Input
              label="Members per Chat"
              type="number"
              value={String(form.virtual_adapter_members_per_chat ?? 5)}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_members_per_chat: Number(v) }))}
            />
            <Input
              label="Messages per Chat"
              type="number"
              value={String(form.virtual_adapter_messages_per_chat ?? 10)}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_messages_per_chat: Number(v) }))}
            />
            <Input
              label="Interval Min (s)"
              type="number"
              value={String(form.virtual_adapter_interval_min_seconds ?? 0.1)}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_interval_min_seconds: Number(v) }))}
            />
            <Input
              label="Interval Max (s)"
              type="number"
              value={String(form.virtual_adapter_interval_max_seconds ?? 0.6)}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_interval_max_seconds: Number(v) }))}
            />
            <Input
              label="Script Path"
              value={form.virtual_adapter_script_path ?? ''}
              onValueChange={v => setForm(f => ({ ...f, virtual_adapter_script_path: v.trim() === '' ? null : v }))}
            />
          </div>
          {save.isSuccess && <p className="text-success text-sm">Saved successfully.</p>}
          {save.isError && <p className="text-danger text-sm">Save failed.</p>}
        </CardBody>
      </Card>
    </div>
  );
}
