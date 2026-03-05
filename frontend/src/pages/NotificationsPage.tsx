import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Input, Select, SelectItem, Spinner, Switch,
} from '@heroui/react';
import { Save } from 'lucide-react';
import { fetchNotificationsConfig, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

const BARK_LEVELS = ['active', 'timeSensitive', 'passive', 'critical'];

export default function NotificationsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['notifications_config'], queryFn: fetchNotificationsConfig });
  const [form, setForm] = useState<Partial<AppSettings>>({});

  useEffect(() => {
    if (!data) return;
    setForm({
      email_notifier_enabled: data.email.enabled,
      email_notifier_to_email: data.email.to_email ?? '',
      smtp_host: data.email.smtp_host ?? '',
      smtp_port: data.email.smtp_port,
      smtp_username: data.email.smtp_username ?? '',
      smtp_sender: data.email.smtp_sender ?? '',
      bark_notifier_enabled: data.bark.enabled,
      bark_device_key: data.bark.device_key ?? '',
      bark_server_url: data.bark.server_url,
      bark_group: data.bark.group ?? '',
      bark_level: data.bark.level ?? '',
    });
  }, [data]);

  const save = useMutation({
    mutationFn: () => updateSettings(form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications_config'] }),
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading…" /></div>;

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Email */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">Email Notifications</span>
          <Switch
            isSelected={form.email_notifier_enabled ?? false}
            onValueChange={v => setForm(f => ({ ...f, email_notifier_enabled: v }))}
            aria-label="Enable email"
          />
        </CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="To Email"
            placeholder="recipient@example.com"
            value={form.email_notifier_to_email ?? ''}
            onValueChange={v => setForm(f => ({ ...f, email_notifier_to_email: v }))}
          />
          <Input
            label="SMTP Host"
            placeholder="smtp.example.com"
            value={form.smtp_host ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_host: v }))}
          />
          <Input
            label="SMTP Port"
            type="number"
            value={String(form.smtp_port ?? 587)}
            onValueChange={v => setForm(f => ({ ...f, smtp_port: Number(v) }))}
          />
          <Input
            label="SMTP Username"
            value={form.smtp_username ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_username: v }))}
          />
          <Input
            label="SMTP Password"
            type="password"
            placeholder="(unchanged if empty)"
            value={form.smtp_password ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_password: v || null }))}
          />
          <Input
            label="SMTP Sender"
            placeholder="sender@example.com"
            value={form.smtp_sender ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_sender: v }))}
          />
        </CardBody>
      </Card>

      {/* Bark */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">Bark Notifications</span>
          <Switch
            isSelected={form.bark_notifier_enabled ?? false}
            onValueChange={v => setForm(f => ({ ...f, bark_notifier_enabled: v }))}
            aria-label="Enable Bark"
          />
        </CardHeader>
        <CardBody className="space-y-3">
          <Input
            label="Device Key"
            value={form.bark_device_key ?? ''}
            onValueChange={v => setForm(f => ({ ...f, bark_device_key: v }))}
          />
          <Input
            label="Server URL"
            value={form.bark_server_url ?? 'https://api.day.app'}
            onValueChange={v => setForm(f => ({ ...f, bark_server_url: v }))}
          />
          <Input
            label="Group"
            value={form.bark_group ?? ''}
            onValueChange={v => setForm(f => ({ ...f, bark_group: v }))}
          />
          <Select
            label="Level"
            placeholder="Default"
            selectedKeys={form.bark_level ? [form.bark_level] : []}
            onSelectionChange={k => {
              const val = Array.from(k)[0] as string ?? '';
              setForm(f => ({ ...f, bark_level: val || null }));
            }}
          >
            {BARK_LEVELS.map(l => <SelectItem key={l}>{l}</SelectItem>)}
          </Select>
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
