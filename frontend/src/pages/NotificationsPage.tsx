import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Input, Spinner, Switch, Textarea,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import disketteBold from '@iconify/icons-solar/diskette-bold';
import earthBold from '@iconify/icons-solar/earth-bold';
import hashtagBold from '@iconify/icons-solar/hashtag-bold';
import keyBold from '@iconify/icons-solar/key-bold';
import letterBold from '@iconify/icons-solar/letter-bold';
import sendSquareBold from '@iconify/icons-solar/send-square-bold';
import server2Bold from '@iconify/icons-solar/server-2-bold';
import smartphone2Bold from '@iconify/icons-solar/smartphone-2-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import playCircleBold from '@iconify/icons-solar/play-circle-bold';
import { useTranslation } from 'react-i18next';
import { fetchNotificationsConfig, fetchSettings, updateSettings, testNotification } from '../api/settings';
import { ApiError } from '../api/client';
import type { AppSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';

export default function NotificationsPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({ queryKey: ['notifications_config'], queryFn: fetchNotificationsConfig });
  const { data: settingsData } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [emailTestState, setEmailTestState] = useState<'idle' | 'loading' | 'success' | 'error' | 'notConfigured'>('idle');
  const [barkTestState, setBarkTestState] = useState<'idle' | 'loading' | 'success' | 'error' | 'notConfigured'>('idle');
  const testResetTimers = useRef<{ email: ReturnType<typeof setTimeout> | null; bark: ReturnType<typeof setTimeout> | null }>({ email: null, bark: null });

  // Clear timers on unmount to avoid state updates on unmounted component
  useEffect(() => {
    return () => {
      if (testResetTimers.current.email !== null) clearTimeout(testResetTimers.current.email);
      if (testResetTimers.current.bark !== null) clearTimeout(testResetTimers.current.bark);
    };
  }, []);

  useEffect(() => {
    if (!data) return;
    setForm({
      email_notifier_enabled: data.email.enabled,
      email_notifier_to_email: data.email.to_email ?? '',
      smtp_host: data.email.smtp_host ?? '',
      smtp_port: data.email.smtp_port,
      smtp_username: data.email.smtp_username ?? '',
      smtp_password: data.email.smtp_password ?? '',
      smtp_sender: data.email.smtp_sender ?? '',
      bark_notifier_enabled: data.bark.enabled,
      bark_device_key: data.bark.device_key ?? '',
      bark_device_keys: data.bark.device_keys ?? [],
      bark_server_url: data.bark.server_url,
      bark_group: data.bark.group ?? '',
      bark_level: data.bark.level ?? '',
    });
  }, [data]);

  useEffect(() => {
    if (!settingsData) return;
    setForm(f => ({
      ...f,
      notification_text_template: f.notification_text_template ?? settingsData.notification_text_template ?? '',
    }));
  }, [settingsData]);

  const save = useMutation({
    mutationFn: () => updateSettings(form),
  });

  async function handleTest(type: 'email' | 'bark') {
    const setState = type === 'email' ? setEmailTestState : setBarkTestState;

    // Cancel any pending reset timer for this notifier
    if (testResetTimers.current[type] !== null) {
      clearTimeout(testResetTimers.current[type]!);
      testResetTimers.current[type] = null;
    }

    setState('loading');
    try {
      await testNotification(type);
      setState('success');
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 400) {
        setState('notConfigured');
      } else {
        setState('error');
      }
    }
    testResetTimers.current[type] = setTimeout(() => {
      testResetTimers.current[type] = null;
      setState('idle');
    }, 5000);
  }

  function testStatusText(state: typeof emailTestState): string | null {
    switch (state) {
      case 'success': return t('notifications.testSuccess');
      case 'error': return t('notifications.testFailed');
      case 'notConfigured': return t('notifications.testNotConfigured');
      default: return null;
    }
  }

  function testButtonColor(state: typeof emailTestState): 'success' | 'danger' | 'secondary' {
    if (state === 'success') return 'success';
    if (state === 'error' || state === 'notConfigured') return 'danger';
    return 'secondary';
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('notifications.loading')} /></div>;

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Email */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">{t('notifications.email')}</span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="flat"
              color={testButtonColor(emailTestState)}
              startContent={<Icon icon={playCircleBold} fontSize={ICON_SIZES.button} />}
              isLoading={emailTestState === 'loading'}
              onPress={() => handleTest('email')}
            >
              {emailTestState === 'loading' ? t('notifications.testing') : t('notifications.test')}
            </Button>
            <Switch
              isSelected={form.email_notifier_enabled ?? false}
              onValueChange={v => setForm(f => ({ ...f, email_notifier_enabled: v }))}
              aria-label={t('notifications.enableEmail')}
            />
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          {testStatusText(emailTestState) && (
            <p className={`text-sm ${emailTestState === 'success' ? 'text-success' : 'text-danger'}`}>
              {testStatusText(emailTestState)}
            </p>
          )}
          <Input
            label={t('notifications.toEmail')}
            startContent={<Icon icon={letterBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.email_notifier_to_email ?? ''}
            onValueChange={v => setForm(f => ({ ...f, email_notifier_to_email: v.trim() === '' ? null : v }))}
          />
          <Input
            label={t('notifications.smtpHost')}
            startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.smtp_host ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_host: v.trim() === '' ? null : v }))}
          />
          <Input
            label={t('notifications.smtpPort')}
            type="number"
            startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={String(form.smtp_port ?? 587)}
            onValueChange={v => setForm(f => ({ ...f, smtp_port: Number(v) }))}
          />
          <Input
            label={t('notifications.smtpUsername')}
            startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.smtp_username ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_username: v.trim() === '' ? null : v }))}
          />
          <Input
            label={t('notifications.smtpPassword')}
            type="password"
            startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.smtp_password ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_password: v.trim() === '' ? null : v }))}
          />
          <Input
            label={t('notifications.smtpSender')}
            startContent={<Icon icon={sendSquareBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.smtp_sender ?? ''}
            onValueChange={v => setForm(f => ({ ...f, smtp_sender: v.trim() === '' ? null : v }))}
          />
        </CardBody>
      </Card>

      {/* Bark */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="font-semibold">{t('notifications.bark')}</span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="flat"
              color={testButtonColor(barkTestState)}
              startContent={<Icon icon={playCircleBold} fontSize={ICON_SIZES.button} />}
              isLoading={barkTestState === 'loading'}
              onPress={() => handleTest('bark')}
            >
              {barkTestState === 'loading' ? t('notifications.testing') : t('notifications.test')}
            </Button>
            <Switch
              isSelected={form.bark_notifier_enabled ?? false}
              onValueChange={v => setForm(f => ({ ...f, bark_notifier_enabled: v }))}
              aria-label={t('notifications.enableBark')}
            />
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          {testStatusText(barkTestState) && (
            <p className={`text-sm ${barkTestState === 'success' ? 'text-success' : 'text-danger'}`}>
              {testStatusText(barkTestState)}
            </p>
          )}
          <Input
            label={t('notifications.deviceKey')}
            startContent={<Icon icon={smartphone2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.bark_device_key ?? ''}
            onValueChange={v => setForm(f => ({ ...f, bark_device_key: v }))}
          />
          <Input
            label={t('notifications.deviceKeys')}
            description={t('notifications.multiDevice')}
            startContent={<Icon icon={bellBingBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={(form.bark_device_keys ?? []).join(', ')}
            onValueChange={v => setForm(f => ({ ...f, bark_device_keys: v.split(',').map(x => x.trim()).filter(Boolean) }))}
          />
          <Input
            label={t('notifications.serverUrl')}
            startContent={<Icon icon={earthBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.bark_server_url ?? 'https://api.day.app'}
            onValueChange={v => setForm(f => ({ ...f, bark_server_url: v }))}
          />
          <Input
            label={t('notifications.group')}
            startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.bark_group ?? ''}
            onValueChange={v => setForm(f => ({ ...f, bark_group: v.trim() === '' ? null : v }))}
          />
          <Input
            label={t('notifications.level')}
            startContent={<Icon icon={chart2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.bark_level ?? ''}
            onValueChange={v => setForm(f => ({ ...f, bark_level: v.trim() === '' ? null : v }))}
          />
        </CardBody>
      </Card>

      {/* Shared text template */}
      <Card>
        <CardHeader className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <span className="font-semibold">{t('notifications.textTemplate')}</span>
            <p className="text-xs text-default-500 max-w-lg">{t('notifications.textTemplateDesc')}</p>
          </div>
        </CardHeader>
        <CardBody className="space-y-3">
          <Textarea
            label={t('notifications.textTemplate')}
            placeholder={t('notifications.textTemplatePlaceholder')}
            minRows={3}
            value={form.notification_text_template ?? ''}
            onValueChange={v => {
              const trimmed = v.trim();
              setForm(f => ({ ...f, notification_text_template: trimmed === '' ? null : trimmed }));
            }}
          />
        </CardBody>
      </Card>

        <Button
          color="primary"
          startContent={<Icon icon={disketteBold} fontSize={ICON_SIZES.button} />}
          isLoading={save.isPending}
          onPress={() => save.mutate()}
        >
        {t('notifications.saveSettings')}
      </Button>
      {save.isSuccess && <p className="text-success text-sm">{t('common.saveSuccess')}</p>}
      {save.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
    </div>
  );
}
