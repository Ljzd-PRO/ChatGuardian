import { useState, useEffect, useRef, forwardRef, useImperativeHandle, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button, Card, CardBody, Input, Select, SelectItem, Switch, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import arrowLeftBold from '@iconify/icons-solar/arrow-left-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import databaseBold from '@iconify/icons-solar/database-bold';
import earthBold from '@iconify/icons-solar/earth-bold';
import eyeBold from '@iconify/icons-solar/eye-bold';
import eyeClosedLinear from '@iconify/icons-solar/eye-closed-linear';
import hashtagBold from '@iconify/icons-solar/hashtag-bold';
import keyBold from '@iconify/icons-solar/key-bold';
import layersBold from '@iconify/icons-solar/layers-bold';
import letterBold from '@iconify/icons-solar/letter-bold';
import linkBold from '@iconify/icons-solar/link-bold';
import lockPasswordBold from '@iconify/icons-solar/lock-password-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import pulse2Bold from '@iconify/icons-solar/pulse-2-bold';
import sendSquareBold from '@iconify/icons-solar/send-square-bold';
import server2Bold from '@iconify/icons-solar/server-2-bold';
import smartphone2Bold from '@iconify/icons-solar/smartphone-2-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import thermometerBold from '@iconify/icons-solar/thermometer-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import boxBold from '@iconify/icons-solar/box-bold';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { register } from '../api/auth';
import { updateSettings, fetchSettings, type AppSettings } from '../api/settings';
import RowSteps from '../components/steps/RowSteps';
import { ICON_SIZES } from '../constants/iconSizes';

const STEP_KEYS = ['account', 'llm', 'adapters', 'notifications'] as const;

interface StepHandle {
  save: () => Promise<void>;
}

export default function SetupWizardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login, loading: authLoading, setupRequired, authenticated, refreshSetupState } = useAuth();
  const [step, setStep] = useState(0);
  const [accountDone, setAccountDone] = useState(false);
  const [nextSaving, setNextSaving] = useState(false);
  const [stepError, setStepError] = useState('');

  const llmStepRef = useRef<StepHandle>(null);
  const adapterStepRef = useRef<StepHandle>(null);
  const notificationStepRef = useRef<StepHandle>(null);

  function getActiveStepRef() {
    if (step === 1) return llmStepRef;
    if (step === 2) return adapterStepRef;
    if (step === 3) return notificationStepRef;
    return null;
  }

  const steps = STEP_KEYS.map(k => ({ title: t(`setup.steps.${k}`) }));

  // Dynamic document title
  useEffect(() => {
    document.title = `${t('setup.title')} - ${t('common.appName')}`;
  }, [t]);

  // Redirect to dashboard if already set up and authenticated
  // Redirect to login if already set up but not authenticated
  useEffect(() => {
    if (authLoading) return;
    if (!setupRequired && authenticated && !accountDone) {
      navigate('/', { replace: true });
    } else if (!setupRequired && !authenticated) {
      navigate('/login', { replace: true });
    }
  }, [authLoading, setupRequired, authenticated, accountDone, navigate]);

  async function saveCurrentStep(): Promise<void> {
    const ref = getActiveStepRef();
    if (ref?.current) {
      setNextSaving(true);
      setStepError('');
      try {
        await ref.current.save();
      } finally {
        setNextSaving(false);
      }
    }
  }

  async function handleNext() {
    try {
      await saveCurrentStep();
      setStep(s => s + 1);
    } catch {
      setStepError(t('common.saveFailed'));
    }
  }

  async function handleFinish() {
    try {
      await saveCurrentStep();
      await refreshSetupState();
      navigate('/', { replace: true });
    } catch {
      setStepError(t('common.saveFailed'));
    }
  }

  /** Prevent clicking steps beyond 0 until account is created */
  function handleStepChange(idx: number) {
    if (!accountDone && idx > 0) return;
    setStepError('');
    setStep(idx);
  }

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-default-50">
        <Spinner size="lg" />
      </div>
    );
  }

  const canGoBack = step > 0;
  const isLast = step === STEP_KEYS.length - 1;

  return (
    <div className="flex min-h-screen items-center justify-center bg-default-50 px-4 py-8">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-primary">{t('common.appName')}</h1>
          <p className="text-default-500">{t('setup.welcome')}</p>
        </div>

        <div className="flex justify-center">
          <RowSteps currentStep={step} onStepChange={handleStepChange} steps={steps} />
        </div>

        <Card className="shadow-lg">
          <CardBody className="p-6 md:p-8">
            {step === 0 && (
              <AccountStep
                done={accountDone}
                onDone={async (u, p) => {
                  await register(u, p);
                  await login(u, p);
                  setAccountDone(true);
                }}
              />
            )}
            {step === 1 && <LLMStep ref={llmStepRef} />}
            {step === 2 && <AdapterStep ref={adapterStepRef} />}
            {step === 3 && <NotificationStep ref={notificationStepRef} />}
          </CardBody>
        </Card>

        <div className="flex items-center justify-between">
          <Button
            variant="flat"
            isDisabled={!canGoBack}
            onPress={() => { setStepError(''); setStep(s => s - 1); }}
            startContent={<Icon icon={arrowLeftBold} fontSize={ICON_SIZES.button} />}
          >
            {t('setup.back')}
          </Button>
          <div className="flex flex-col items-end gap-2">
            {stepError && <p className="text-danger text-sm">{stepError}</p>}
            <div className="flex gap-2">
              {step > 0 && !isLast && (
                <Button variant="light" isDisabled={nextSaving} onPress={() => { setStepError(''); setStep(s => s + 1); }}>
                  {t('setup.skip')}
                </Button>
              )}
              {isLast ? (
                <Button
                  color="primary"
                  isDisabled={!accountDone}
                  isLoading={nextSaving}
                  onPress={handleFinish}
                  endContent={<Icon icon={checkCircleBold} fontSize={ICON_SIZES.button} />}
                >
                  {t('setup.finish')}
                </Button>
              ) : (
                <Button
                  color="primary"
                  isDisabled={step === 0 && !accountDone}
                  isLoading={nextSaving}
                  onPress={handleNext}
                  endContent={<Icon icon={arrowRightBold} fontSize={ICON_SIZES.button} />}
                >
                  {t('setup.next')}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Step 1: Account ─────────────────────────────────────────────────────── */

function AccountStep({ done, onDone }: { done: boolean; onDone: (u: string, p: string) => Promise<void> }) {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (done) {
    return (
      <div className="flex flex-col items-center gap-4 py-8">
        <Icon icon={checkCircleBold} fontSize={48} className="text-success" />
        <p className="text-lg font-medium text-success">{t('setup.accountCreated')}</p>
      </div>
    );
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!username.trim()) { setError(t('setup.accountUsernameRequired')); return; }
    if (!password.trim()) { setError(t('setup.accountPasswordRequired')); return; }
    if (password !== confirm) { setError(t('setup.accountPasswordMismatch')); return; }
    if (password.length < 8) { setError(t('setup.accountPasswordTooShort')); return; }
    setLoading(true);
    try {
      await onDone(username.trim(), password);
    } catch {
      setError(t('setup.accountCreateFailed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleCreate}>
      <p className="text-default-600 text-sm mb-4">{t('setup.accountDesc')}</p>
      <Input
        isRequired
        label={t('auth.login.username')}
        variant="bordered"
        value={username}
        onValueChange={setUsername}
        startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
        autoComplete="username"
      />
      <Input
        isRequired
        label={t('auth.login.password')}
        variant="bordered"
        type={showPw ? 'text' : 'password'}
        value={password}
        onValueChange={setPassword}
        startContent={<Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
        endContent={
          <button type="button" onClick={() => setShowPw(p => !p)} aria-label={t('auth.login.togglePassword')}>
            <Icon className="text-default-400 text-xl" icon={showPw ? eyeClosedLinear : eyeBold} />
          </button>
        }
        autoComplete="new-password"
      />
      <Input
        isRequired
        label={t('setup.confirmPassword')}
        variant="bordered"
        type={showPw ? 'text' : 'password'}
        value={confirm}
        onValueChange={setConfirm}
        startContent={<Icon icon={lockPasswordBold} fontSize={ICON_SIZES.input} className="text-default-400" />}
        autoComplete="new-password"
      />
      {error && <p className="text-sm text-danger">{error}</p>}
      <Button type="submit" color="primary" className="w-full" isLoading={loading}>
        {t('setup.createAccount')}
      </Button>
    </form>
  );
}

/* ─── Step 2: LLM ─────────────────────────────────────────────────────────── */

const LLMStep = forwardRef<StepHandle>(function LLMStep(_, ref) {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Partial<AppSettings> | null>(null);
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then(s => {
        setSettings(s);
        setForm({
          llm_langchain_backend: s.llm_langchain_backend,
          llm_langchain_model: s.llm_langchain_model,
          llm_langchain_api_base: s.llm_langchain_api_base ?? '',
          llm_langchain_api_key: s.llm_langchain_api_key ?? '',
          llm_langchain_temperature: s.llm_langchain_temperature,
          llm_timeout_seconds: s.llm_timeout_seconds,
          llm_max_parallel_batches: s.llm_max_parallel_batches,
          llm_rules_per_batch: s.llm_rules_per_batch,
          llm_ollama_base_url: s.llm_ollama_base_url,
          llm_display_timezone: s.llm_display_timezone,
          llm_batch_timeout_seconds: s.llm_batch_timeout_seconds,
          llm_batch_max_retries: s.llm_batch_max_retries,
          llm_batch_rate_limit_per_second: s.llm_batch_rate_limit_per_second,
          llm_batch_idempotency_cache_size: s.llm_batch_idempotency_cache_size,
        });
      })
      .catch(() => setLoadError(true));
  }, []);

  useImperativeHandle(ref, () => ({
    save: async () => {
      await updateSettings(form);
    },
  }));

  if (loadError) return <p className="text-danger text-sm">{t('common.saveFailed')}</p>;
  if (!settings) return <div className="flex justify-center py-8"><Spinner label={t('llm.loading')} /></div>;

  return (
    <div className="space-y-4">
      <p className="text-default-600 text-sm">{t('setup.llmDesc')}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Select
          label={t('llm.backend')}
          selectedKeys={[form.llm_langchain_backend ?? 'openai_compatible']}
          onSelectionChange={k => setForm(f => ({ ...f, llm_langchain_backend: Array.from(k)[0] as string }))}
        >
          <SelectItem key="openai_compatible">{t('llm.openai')}</SelectItem>
          <SelectItem key="ollama">{t('llm.ollama')}</SelectItem>
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
        <Input
          label={t('llm.ollamaBaseUrl')}
          startContent={<Icon icon={linkBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.llm_ollama_base_url ?? ''}
          onValueChange={v => setForm(f => ({ ...f, llm_ollama_base_url: v }))}
        />
      </div>
    </div>
  );
});

/* ─── Step 3: Adapters ────────────────────────────────────────────────────── */

const AdapterStep = forwardRef<StepHandle>(function AdapterStep(_, ref) {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<Partial<AppSettings> | null>(null);
  const [form, setForm] = useState<Partial<AppSettings>>({});

  useEffect(() => {
    fetchSettings()
      .then(s => {
        setSettings(s);
        setForm({
          enabled_adapters: s.enabled_adapters ?? [],
          onebot_host: s.onebot_host,
          onebot_port: s.onebot_port,
          onebot_access_token: s.onebot_access_token ?? '',
          telegram_bot_token: s.telegram_bot_token ?? '',
          telegram_polling_timeout: s.telegram_polling_timeout,
          telegram_drop_pending_updates: s.telegram_drop_pending_updates,
          wechat_endpoint: s.wechat_endpoint ?? '',
          feishu_app_id: s.feishu_app_id ?? '',
        });
      })
      .catch(() => { /* ignore */ });
  }, []);

  useImperativeHandle(ref, () => ({
    save: async () => {
      await updateSettings(form);
    },
  }));

  if (!settings) return <div className="flex justify-center py-8"><Spinner label={t('adapters.loading')} /></div>;

  return (
    <div className="space-y-4">
      <p className="text-default-600 text-sm">{t('setup.adaptersDesc')}</p>

      <Select
        label={t('adapters.enabledAdapters')}
        selectionMode="multiple"
        selectedKeys={new Set(form.enabled_adapters ?? [])}
        onSelectionChange={keys => setForm(f => ({ ...f, enabled_adapters: Array.from(keys) as string[] }))}
      >
        {['onebot', 'telegram', 'wechat', 'feishu', 'virtual'].map(a => (
          <SelectItem key={a}>{a}</SelectItem>
        ))}
      </Select>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* OneBot */}
        <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-default-900">
            <Icon icon={cpuBoltBold} fontSize={ICON_SIZES.cardHeader} />
            <span>OneBot</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Host" startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.onebot_host ?? ''} onValueChange={v => setForm(f => ({ ...f, onebot_host: v }))} />
            <Input label="Port" type="number" startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.onebot_port ?? 2290)} onValueChange={v => setForm(f => ({ ...f, onebot_port: Number(v) }))} />
            <Input label="Access Token" className="sm:col-span-2"
              startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.onebot_access_token ?? ''} onValueChange={v => setForm(f => ({ ...f, onebot_access_token: v.trim() === '' ? null : v }))} />
          </div>
        </div>

        {/* Telegram */}
        <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-default-900">
            <Icon icon={sendSquareBold} fontSize={ICON_SIZES.cardHeader} />
            <span>Telegram</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Bot Token" startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={form.telegram_bot_token ?? ''} onValueChange={v => setForm(f => ({ ...f, telegram_bot_token: v.trim() === '' ? null : v }))} />
            <Input label="Polling Timeout (s)" type="number"
              startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              value={String(form.telegram_polling_timeout ?? 10)} onValueChange={v => setForm(f => ({ ...f, telegram_polling_timeout: Number(v) }))} />
            <div className="sm:col-span-2">
              <Switch isSelected={form.telegram_drop_pending_updates ?? false}
                onValueChange={v => setForm(f => ({ ...f, telegram_drop_pending_updates: v }))}>
                {t('adapters.telegramDropPending')}
              </Switch>
            </div>
          </div>
        </div>

        {/* WeChat */}
        <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-default-900">
            <Icon icon={plugCircleBold} fontSize={ICON_SIZES.cardHeader} />
            <span>WeChat</span>
          </div>
          <Input label="Endpoint" startContent={<Icon icon={linkBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.wechat_endpoint ?? ''} onValueChange={v => setForm(f => ({ ...f, wechat_endpoint: v.trim() === '' ? null : v }))} />
        </div>

        {/* Feishu */}
        <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
          <div className="flex items-center gap-2 font-semibold text-default-900">
            <Icon icon={plugCircleBold} fontSize={ICON_SIZES.cardHeader} />
            <span>Feishu</span>
          </div>
          <Input label="App ID" startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
            value={form.feishu_app_id ?? ''} onValueChange={v => setForm(f => ({ ...f, feishu_app_id: v.trim() === '' ? null : v }))} />
        </div>
      </div>

    </div>
  );
});

/* ─── Step 4: Notifications ───────────────────────────────────────────────── */

const NotificationStep = forwardRef<StepHandle>(function NotificationStep(_, ref) {
  const { t } = useTranslation();
  const [form, setForm] = useState<Partial<AppSettings>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetchSettings()
      .then(s => {
        setForm({
          email_notifier_enabled: s.email_notifier_enabled,
          email_notifier_to_email: s.email_notifier_to_email ?? '',
          smtp_host: s.smtp_host ?? '',
          smtp_port: s.smtp_port,
          smtp_username: s.smtp_username ?? '',
          smtp_password: s.smtp_password ?? '',
          smtp_sender: s.smtp_sender ?? '',
          bark_notifier_enabled: s.bark_notifier_enabled,
          bark_device_key: s.bark_device_key ?? '',
          bark_device_keys: s.bark_device_keys ?? [],
          bark_server_url: s.bark_server_url,
          bark_group: s.bark_group ?? '',
          bark_level: s.bark_level ?? '',
        });
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  useImperativeHandle(ref, () => ({
    save: async () => {
      await updateSettings(form);
    },
  }));

  if (!loaded) return <div className="flex justify-center py-8"><Spinner label={t('notifications.loading')} /></div>;

  return (
    <div className="space-y-4">
      <p className="text-default-600 text-sm">{t('setup.notificationsDesc')}</p>

      {/* Email */}
      <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-default-900">{t('notifications.email')}</span>
          <Switch isSelected={form.email_notifier_enabled ?? false}
            onValueChange={v => setForm(f => ({ ...f, email_notifier_enabled: v }))}
            aria-label={t('notifications.enableEmail')} />
        </div>
        <Input label={t('notifications.toEmail')} startContent={<Icon icon={letterBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.email_notifier_to_email ?? ''} onValueChange={v => setForm(f => ({ ...f, email_notifier_to_email: v.trim() === '' ? null : v }))} />
        <Input label={t('notifications.smtpHost')} startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.smtp_host ?? ''} onValueChange={v => setForm(f => ({ ...f, smtp_host: v.trim() === '' ? null : v }))} />
        <Input label={t('notifications.smtpPort')} type="number" startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={String(form.smtp_port ?? 587)} onValueChange={v => setForm(f => ({ ...f, smtp_port: Number(v) }))} />
        <Input label={t('notifications.smtpUsername')} startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.smtp_username ?? ''} onValueChange={v => setForm(f => ({ ...f, smtp_username: v.trim() === '' ? null : v }))} />
        <Input label={t('notifications.smtpPassword')} type="password" startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.smtp_password ?? ''} onValueChange={v => setForm(f => ({ ...f, smtp_password: v.trim() === '' ? null : v }))} />
        <Input label={t('notifications.smtpSender')} startContent={<Icon icon={sendSquareBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.smtp_sender ?? ''} onValueChange={v => setForm(f => ({ ...f, smtp_sender: v.trim() === '' ? null : v }))} />
      </div>

      {/* Bark */}
      <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-default-900">{t('notifications.bark')}</span>
          <Switch isSelected={form.bark_notifier_enabled ?? false}
            onValueChange={v => setForm(f => ({ ...f, bark_notifier_enabled: v }))}
            aria-label={t('notifications.enableBark')} />
        </div>
        <Input label={t('notifications.deviceKey')} startContent={<Icon icon={smartphone2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.bark_device_key ?? ''} onValueChange={v => setForm(f => ({ ...f, bark_device_key: v }))} />
        <Input label={t('notifications.deviceKeys')} description={t('notifications.multiDevice')}
          startContent={<Icon icon={bellBingBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={(form.bark_device_keys ?? []).join(', ')} onValueChange={v => setForm(f => ({ ...f, bark_device_keys: v.split(',').map(x => x.trim()).filter(Boolean) }))} />
        <Input label={t('notifications.serverUrl')} startContent={<Icon icon={earthBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.bark_server_url ?? 'https://api.day.app'} onValueChange={v => setForm(f => ({ ...f, bark_server_url: v }))} />
        <Input label={t('notifications.group')} startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.bark_group ?? ''} onValueChange={v => setForm(f => ({ ...f, bark_group: v.trim() === '' ? null : v }))} />
        <Input label={t('notifications.level')} startContent={<Icon icon={chart2Bold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          value={form.bark_level ?? ''} onValueChange={v => setForm(f => ({ ...f, bark_level: v.trim() === '' ? null : v }))} />
      </div>

    </div>
  );
});
