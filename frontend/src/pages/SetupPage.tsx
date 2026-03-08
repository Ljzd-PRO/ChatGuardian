import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Input,
  Select,
  SelectItem,
  Switch,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import lockBold from '@iconify/icons-solar/lock-bold';
import userBold from '@iconify/icons-solar/user-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import shieldBold from '@iconify/icons-solar/shield-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import linkBold from '@iconify/icons-solar/link-bold';
import thermometerBold from '@iconify/icons-solar/thermometer-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import layersBold from '@iconify/icons-solar/layers-bold';
import playBold from '@iconify/icons-solar/play-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import server2Bold from '@iconify/icons-solar/server-2-bold';
import hashtagBold from '@iconify/icons-solar/hashtag-bold';
import keyBold from '@iconify/icons-solar/key-bold';
import sendSquareBold from '@iconify/icons-solar/send-square-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import letterBold from '@iconify/icons-solar/letter-bold';
import smartphone2Bold from '@iconify/icons-solar/smartphone-2-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import earthBold from '@iconify/icons-solar/earth-bold';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import RowSteps from '../components/RowSteps';
import { fetchSetupStatus, setupAccount } from '../api/auth';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';
import { clearAuthToken, getAuthToken, setAuthToken } from '../api/client';
import { ICON_SIZES } from '../constants/iconSizes';

const STEP_ACCOUNT = 0;
const STEP_LLM = 1;
const STEP_ADAPTERS = 2;
const STEP_NOTIFICATIONS = 3;

export default function SetupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [token, setToken] = useState<string | null>(() => getAuthToken());

  const setupStatus = useQuery({ queryKey: ['setup-status'], queryFn: fetchSetupStatus });
  const hasToken = !!token;
  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    enabled: hasToken,
  });

  const [currentStep, setCurrentStep] = useState(0);
  const [justCreatedAccount, setJustCreatedAccount] = useState(false);
  const [accountForm, setAccountForm] = useState({ username: '', password: '', confirm: '' });
  const [accountError, setAccountError] = useState<string | null>(null);

  const [llmForm, setLlmForm] = useState<Partial<AppSettings>>({});
  const [adapterForm, setAdapterForm] = useState<Partial<AppSettings>>({});
  const [notificationForm, setNotificationForm] = useState<Partial<AppSettings>>({});
  const handleStepChange = (idx: number) => {
    if (!hasToken && idx > STEP_ACCOUNT) return;
    setCurrentStep(idx);
  };

  useEffect(() => {
    if (settingsQuery.data) {
      const s = settingsQuery.data;
      setLlmForm({
        llm_langchain_backend: s.llm_langchain_backend,
        llm_langchain_model: s.llm_langchain_model,
        llm_langchain_api_base: s.llm_langchain_api_base ?? '',
        llm_langchain_api_key: s.llm_langchain_api_key ?? '',
        llm_langchain_temperature: s.llm_langchain_temperature,
        llm_timeout_seconds: s.llm_timeout_seconds,
        llm_max_parallel_batches: s.llm_max_parallel_batches,
        llm_rules_per_batch: s.llm_rules_per_batch,
      });

      setAdapterForm({
        enabled_adapters: s.enabled_adapters ?? [],
        onebot_host: s.onebot_host,
        onebot_port: s.onebot_port,
        onebot_access_token: s.onebot_access_token ?? '',
        telegram_bot_token: s.telegram_bot_token ?? '',
      });

      setNotificationForm({
        email_notifier_enabled: s.email_notifier_enabled,
        email_notifier_to_email: s.email_notifier_to_email ?? '',
        smtp_host: s.smtp_host ?? '',
        smtp_port: s.smtp_port,
        smtp_username: s.smtp_username ?? '',
        smtp_password: s.smtp_password ?? '',
        smtp_sender: s.smtp_sender ?? '',
        bark_notifier_enabled: s.bark_notifier_enabled,
        bark_device_key: s.bark_device_key ?? '',
        bark_server_url: s.bark_server_url ?? 'https://api.day.app',
        bark_group: s.bark_group ?? '',
        bark_level: s.bark_level ?? '',
      });
    }
  }, [settingsQuery.data]);

  useEffect(() => {
    if (setupStatus.data?.setup_required === false && hasToken && currentStep === STEP_ACCOUNT && !justCreatedAccount) {
      navigate('/', { replace: true });
    } else if (setupStatus.data?.setup_required === false && !hasToken) {
      navigate('/login', { replace: true });
    }
  }, [currentStep, hasToken, justCreatedAccount, navigate, setupStatus.data?.setup_required]);

  const accountMutation = useMutation({
    mutationFn: () => setupAccount({ username: accountForm.username, password: accountForm.password }),
    onSuccess: res => {
      setAuthToken(res.token);
      setToken(res.token);
      qc.invalidateQueries({ queryKey: ['setup-status'] });
      setupStatus.refetch();
      setJustCreatedAccount(true);
      setCurrentStep(STEP_LLM);
    },
    onError: err => {
      setAccountError(err instanceof Error ? err.message : t('common.saveFailed'));
      clearAuthToken();
    },
  });

  const settingsMutation = useMutation({
    mutationFn: (payload: Partial<AppSettings>) => updateSettings(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
    },
  });

  const steps = useMemo(
    () => [
      { title: t('setup.account.title') },
      { title: t('setup.llm.title') },
      { title: t('setup.adapters.title') },
      { title: t('setup.notifications.title') },
    ],
    [t],
  );

  if (setupStatus.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-default-50 px-4">
        <Card shadow="sm" className="max-w-md w-full">
          <CardBody className="flex items-center justify-center gap-3">
            <span className="text-sm text-default-500">{t('common.loading')}</span>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-950 to-black flex items-center justify-center px-4 py-8">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.04),transparent_25%),radial-gradient(circle_at_80%_0,rgba(59,130,246,0.06),transparent_30%)]" />
      <Card className="relative max-w-6xl w-full border border-white/10 bg-white/5 backdrop-blur-xl shadow-2xl">
        <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-2xl bg-primary/10 text-primary shadow-inner">
              <Icon icon={shieldBold} fontSize={26} />
            </div>
            <div>
              <p className="text-xl font-semibold text-white">{t('setup.title')}</p>
              <p className="text-sm text-white/70">{t('setup.subtitle')}</p>
            </div>
          </div>
          <div className="text-xs text-white/60">{t('setup.optionalHint')}</div>
        </CardHeader>
        <Divider className="border-white/10" />
        <CardBody className="space-y-6">
          <RowSteps
            steps={steps}
            currentStep={currentStep}
            onStepChange={handleStepChange}
            className="text-white"
            stepClassName="px-3"
          />

          {currentStep === STEP_ACCOUNT && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-3">
                <Input
                  label={t('auth.username')}
                  aria-label={t('auth.username')}
                  variant="bordered"
                  labelPlacement="outside"
                  radius="lg"
                  startContent={<Icon icon={userBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={accountForm.username}
                  onValueChange={v => setAccountForm(f => ({ ...f, username: v }))}
                  classNames={{
                    label: 'text-default-200',
                    input: 'text-white',
                    inputWrapper: 'bg-white/5 border-white/15',
                  }}
                />
                <Input
                  label={t('auth.password')}
                  aria-label={t('auth.password')}
                  type="password"
                  variant="bordered"
                  labelPlacement="outside"
                  radius="lg"
                  startContent={<Icon icon={lockBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={accountForm.password}
                  onValueChange={v => setAccountForm(f => ({ ...f, password: v }))}
                  classNames={{
                    label: 'text-default-200',
                    input: 'text-white',
                    inputWrapper: 'bg-white/5 border-white/15',
                  }}
                />
                <Input
                  label={t('setup.account.confirm')}
                  aria-label={t('setup.account.confirm')}
                  type="password"
                  variant="bordered"
                  labelPlacement="outside"
                  radius="lg"
                  startContent={<Icon icon={lockBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={accountForm.confirm}
                  onValueChange={v => setAccountForm(f => ({ ...f, confirm: v }))}
                  classNames={{
                    label: 'text-default-200',
                    input: 'text-white',
                    inputWrapper: 'bg-white/5 border-white/15',
                  }}
                />
                {accountError && <p className="text-danger text-sm">{accountError}</p>}
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-white/80 shadow-inner">
                <p className="font-semibold text-white mb-2">{t('setup.account.hintTitle')}</p>
                <p className="text-sm leading-6">{t('setup.account.hintDesc')}</p>
              </div>
              <div className="md:col-span-2 flex flex-wrap items-center gap-3 justify-end">
                <Button
                  color="primary"
                  endContent={<Icon icon={arrowRightBold} fontSize={ICON_SIZES.button} />}
                  isLoading={accountMutation.isPending}
                  onPress={() => {
                    setAccountError(null);
                    if (!accountForm.username || !accountForm.password) {
                      setAccountError(t('setup.account.required'));
                      return;
                    }
                    if (accountForm.password !== accountForm.confirm) {
                      setAccountError(t('setup.account.mismatch'));
                      return;
                    }
                    accountMutation.mutate();
                  }}
                >
                  {t('setup.account.submit')}
                </Button>
              </div>
            </div>
          )}

          {currentStep === STEP_LLM && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Select
                  label={t('llm.backend')}
                  selectedKeys={[llmForm.llm_langchain_backend ?? 'openai_compatible']}
                  onSelectionChange={k =>
                    setLlmForm(f => ({ ...f, llm_langchain_backend: Array.from(k)[0] as string }))
                  }
                >
                  <SelectItem key="openai_compatible">{t('llm.openai')}</SelectItem>
                  <SelectItem key="ollama">{t('llm.ollama')}</SelectItem>
                </Select>
                <Input
                  label={t('llm.model')}
                  startContent={<Icon icon={cpuBoltBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={llmForm.llm_langchain_model ?? ''}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_model: v }))}
                />
                <Input
                  label={t('llm.apiBase')}
                  startContent={<Icon icon={linkBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={llmForm.llm_langchain_api_base ?? ''}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_api_base: v.trim() === '' ? null : v }))}
                />
                <Input
                  label={t('llm.apiKey')}
                  type="password"
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={llmForm.llm_langchain_api_key ?? ''}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_api_key: v.trim() === '' ? null : v }))}
                />
                <Input
                  label={t('llm.temperature')}
                  type="number"
                  startContent={<Icon icon={thermometerBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={String(llmForm.llm_langchain_temperature ?? 0)}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_temperature: Number(v) }))}
                />
                <Input
                  label={t('llm.timeout')}
                  type="number"
                  startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={String(llmForm.llm_timeout_seconds ?? 30)}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_timeout_seconds: Number(v) }))}
                />
                <Input
                  label={t('llm.maxParallelBatches')}
                  type="number"
                  startContent={<Icon icon={layersBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={String(llmForm.llm_max_parallel_batches ?? 3)}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_max_parallel_batches: Number(v) }))}
                />
                <Input
                  label={t('llm.rulesPerBatch')}
                  type="number"
                  startContent={<Icon icon={layersBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                  value={String(llmForm.llm_rules_per_batch ?? 2)}
                  onValueChange={v => setLlmForm(f => ({ ...f, llm_rules_per_batch: Number(v) }))}
                />
              </div>
              <div className="flex justify-between">
                <Button variant="light" onPress={() => setCurrentStep(STEP_ADAPTERS)}>
                  {t('setup.skip')}
                </Button>
                <Button
                  color="primary"
                  endContent={<Icon icon={arrowRightBold} fontSize={ICON_SIZES.button} />}
                  isLoading={settingsMutation.isPending}
                  onPress={() => {
                    settingsMutation.mutate(llmForm, {
                      onSuccess: () => setCurrentStep(STEP_ADAPTERS),
                    });
                  }}
                >
                  {t('common.save')}
                </Button>
              </div>
            </div>
          )}

          {currentStep === STEP_ADAPTERS && (
            <div className="space-y-4">
              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
                  <div className="flex items-center gap-2 font-semibold text-default-900">
                    <Icon icon={plugCircleBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                    <span>OneBot</span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      label="Host"
                      startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                      value={adapterForm.onebot_host ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_host: v }))}
                    />
                    <Input
                      label="Port"
                      type="number"
                      startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                      value={String(adapterForm.onebot_port ?? 2290)}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_port: Number(v) }))}
                    />
                    <Input
                      label="Access Token"
                      startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                      value={adapterForm.onebot_access_token ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_access_token: v.trim() === '' ? null : v }))}
                      className="sm:col-span-2"
                    />
                  </div>
                </div>

                <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
                  <div className="flex items-center gap-2 font-semibold text-default-900">
                    <Icon icon={sendSquareBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                    <span>Telegram</span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      label="Bot Token"
                      startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                      value={adapterForm.telegram_bot_token ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, telegram_bot_token: v.trim() === '' ? null : v }))}
                      className="sm:col-span-2"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium text-default-700">
                  <Icon icon={plugCircleBold} fontSize={ICON_SIZES.input} aria-hidden="true" />
                  <span>{t('adapters.enabledAdapters')}</span>
                </div>
                <Select
                  label={t('adapters.enabledAdapters')}
                  selectionMode="multiple"
                  selectedKeys={new Set(adapterForm.enabled_adapters ?? [])}
                  onSelectionChange={keys => setAdapterForm(f => ({ ...f, enabled_adapters: Array.from(keys) as string[] }))}
                  className="max-w-xl"
                >
                  {['onebot', 'telegram', 'wechat', 'feishu', 'virtual'].map(a => (
                    <SelectItem key={a}>{a}</SelectItem>
                  ))}
                </Select>
              </div>

              <div className="flex justify-between">
                <Button variant="light" onPress={() => setCurrentStep(STEP_NOTIFICATIONS)}>
                  {t('setup.skip')}
                </Button>
                <Button
                  color="primary"
                  startContent={<Icon icon={playBold} fontSize={ICON_SIZES.button} />}
                  isLoading={settingsMutation.isPending}
                  onPress={() => {
                    settingsMutation.mutate(adapterForm, {
                      onSuccess: () => setCurrentStep(STEP_NOTIFICATIONS),
                    });
                  }}
                >
                  {t('common.save')}
                </Button>
              </div>
            </div>
          )}

          {currentStep === STEP_NOTIFICATIONS && (
            <div className="space-y-4">
              <Card>
                <CardHeader className="flex items-center justify-between">
                  <span className="font-semibold">{t('notifications.email')}</span>
                  <Switch
                    isSelected={notificationForm.email_notifier_enabled ?? false}
                    onValueChange={v => setNotificationForm(f => ({ ...f, email_notifier_enabled: v }))}
                    aria-label={t('notifications.enableEmail')}
                  />
                </CardHeader>
                <CardBody className="space-y-3">
                  <Input
                    label={t('notifications.toEmail')}
                    startContent={<Icon icon={letterBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.email_notifier_to_email ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, email_notifier_to_email: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('notifications.smtpHost')}
                    startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.smtp_host ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, smtp_host: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('notifications.smtpPort')}
                    type="number"
                    startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={String(notificationForm.smtp_port ?? 587)}
                    onValueChange={v => setNotificationForm(f => ({ ...f, smtp_port: Number(v) }))}
                  />
                  <Input
                    label={t('notifications.smtpUsername')}
                    startContent={<Icon icon={userBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.smtp_username ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, smtp_username: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('notifications.smtpPassword')}
                    type="password"
                    startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.smtp_password ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, smtp_password: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('notifications.smtpSender')}
                    startContent={<Icon icon={sendSquareBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.smtp_sender ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, smtp_sender: v.trim() === '' ? null : v }))}
                  />
                </CardBody>
              </Card>

              <Card>
                <CardHeader className="flex items-center justify-between">
                  <span className="font-semibold">{t('notifications.bark')}</span>
                  <Switch
                    isSelected={notificationForm.bark_notifier_enabled ?? false}
                    onValueChange={v => setNotificationForm(f => ({ ...f, bark_notifier_enabled: v }))}
                    aria-label={t('notifications.enableBark')}
                  />
                </CardHeader>
                <CardBody className="space-y-3">
                  <Input
                    label={t('notifications.deviceKey')}
                    startContent={<Icon icon={smartphone2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.bark_device_key ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, bark_device_key: v }))}
                  />
                  <Input
                    label={t('notifications.serverUrl')}
                    startContent={<Icon icon={earthBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.bark_server_url ?? 'https://api.day.app'}
                    onValueChange={v => setNotificationForm(f => ({ ...f, bark_server_url: v }))}
                  />
                  <Input
                    label={t('notifications.group')}
                    startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.bark_group ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, bark_group: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('notifications.level')}
                    startContent={<Icon icon={bellBingBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                    value={notificationForm.bark_level ?? ''}
                    onValueChange={v => setNotificationForm(f => ({ ...f, bark_level: v.trim() === '' ? null : v }))}
                  />
                </CardBody>
              </Card>

              <div className="flex justify-between">
                <Button
                  variant="light"
                  onPress={() => {
                    setJustCreatedAccount(false);
                    navigate('/', { replace: true });
                  }}
                >
                  {t('setup.finishLater')}
                </Button>
                <Button
                  color="primary"
                  startContent={<Icon icon={arrowRightBold} fontSize={ICON_SIZES.button} />}
                  isLoading={settingsMutation.isPending}
                  onPress={() => {
                    settingsMutation.mutate(notificationForm, {
                      onSuccess: () => {
                        setJustCreatedAccount(false);
                        navigate('/', { replace: true });
                      },
                    });
                  }}
                >
                  {t('setup.complete')}
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
