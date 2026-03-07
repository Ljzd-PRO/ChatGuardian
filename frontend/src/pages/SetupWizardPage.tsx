/**
 * SetupWizardPage – First-time setup wizard styled after HeroUI's multi-step wizard.
 *
 * Layout: left sidebar (step list) + right content panel.
 * Step 1 – Account/Password (required, cannot skip)
 * Step 2 – LLM Model (optional)
 * Step 3 – Adapters (optional)
 * Step 4 – Notifications (optional)
 * Step 5 – Rules (optional)
 */
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  CardBody,
  Checkbox,
  CheckboxGroup,
  Input,
  Select,
  SelectItem,
  Switch,
  Textarea,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import arrowLeftBold from '@iconify/icons-solar/arrow-left-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import eyeBold from '@iconify/icons-solar/eye-bold';
import eyeClosedBold from '@iconify/icons-solar/eye-closed-bold';
import flagBold from '@iconify/icons-solar/flag-bold';
import lockBold from '@iconify/icons-solar/lock-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import { useTranslation } from 'react-i18next';
import { setupAdmin } from '../api/auth';
import { updateSettings } from '../api/settings';
import { useAuth } from '../contexts/AuthContext';

// ── Step definitions ──────────────────────────────────────────────────────────

interface StepDef {
  id: number;
  titleKey: string;
  descKey: string;
  icon: object;
  required: boolean;
}

const STEPS: StepDef[] = [
  { id: 1, titleKey: 'setup.steps.account',       descKey: 'setup.steps.accountDesc',       icon: userRoundedBold,  required: true },
  { id: 2, titleKey: 'setup.steps.llm',           descKey: 'setup.steps.llmDesc',           icon: cpuBoltBold,      required: false },
  { id: 3, titleKey: 'setup.steps.adapters',      descKey: 'setup.steps.adaptersDesc',      icon: plugCircleBold,   required: false },
  { id: 4, titleKey: 'setup.steps.notifications', descKey: 'setup.steps.notificationsDesc', icon: bellBingBold,     required: false },
  { id: 5, titleKey: 'setup.steps.rules',         descKey: 'setup.steps.rulesDesc',         icon: flagBold,         required: false },
];

// ── Helper: StepIndicator ─────────────────────────────────────────────────────

interface StepIndicatorProps {
  step: StepDef;
  current: number;
  completed: Set<number>;
}

function StepIndicator({ step, current, completed }: StepIndicatorProps) {
  const { t } = useTranslation();
  const isActive = step.id === current;
  const isDone = completed.has(step.id);

  return (
    <div className="flex gap-3 items-start">
      {/* Circle / number */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all
            ${isActive  ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/30'
            : isDone    ? 'bg-primary/20 text-primary border border-primary/40'
            : 'bg-default-100 text-default-400 border border-default-200'}`}
        >
          {isDone ? (
            <Icon icon={checkCircleBold} fontSize={16} />
          ) : (
            <span>{step.id}</span>
          )}
        </div>
        {/* Connector line (not shown for last step) */}
        {step.id < STEPS.length && (
          <div className={`w-px flex-1 min-h-[28px] mt-1 ${isDone ? 'bg-primary/40' : 'bg-default-200'}`} />
        )}
      </div>

      {/* Labels */}
      <div className="pb-6">
        <p className={`text-sm font-semibold leading-tight ${isActive ? 'text-default-900' : isDone ? 'text-primary' : 'text-default-400'}`}>
          {t(step.titleKey)}
        </p>
        <p className={`text-xs mt-0.5 leading-tight ${isActive ? 'text-default-500' : 'text-default-400/70'}`}>
          {t(step.descKey)}
        </p>
      </div>
    </div>
  );
}

// ── Step content components ───────────────────────────────────────────────────

// Step 1: Account
interface AccountForm {
  username: string;
  password: string;
  confirmPassword: string;
}

function AccountStep({ onNext }: { onNext: (username: string, password: string) => Promise<void> }) {
  const { t } = useTranslation();
  const [form, setForm] = useState<AccountForm>({ username: '', password: '', confirmPassword: '' });
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [errors, setErrors] = useState<Partial<AccountForm>>({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  function validate(): boolean {
    const errs: Partial<AccountForm> = {};
    if (!form.username.trim()) errs.username = t('setup.account.usernameRequired');
    if (form.password.length < 6) errs.password = t('setup.account.passwordTooShort');
    if (form.password !== form.confirmPassword) errs.confirmPassword = t('setup.account.passwordMismatch');
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleNext() {
    if (!validate()) return;
    setLoading(true);
    setApiError(null);
    try {
      await onNext(form.username.trim(), form.password);
    } catch (e: unknown) {
      setApiError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-default-900">{t('setup.account.title')}</h2>
        <p className="text-default-500 mt-1">{t('setup.account.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <Input
          label={t('setup.account.username')}
          placeholder={t('setup.account.usernamePlaceholder')}
          value={form.username}
          onValueChange={v => setForm(f => ({ ...f, username: v }))}
          startContent={<Icon icon={userRoundedBold} className="text-default-400" fontSize={18} />}
          variant="bordered"
          isRequired
          isInvalid={!!errors.username}
          errorMessage={errors.username}
          autoFocus
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label={t('setup.account.password')}
            placeholder={t('setup.account.passwordPlaceholder')}
            value={form.password}
            onValueChange={v => setForm(f => ({ ...f, password: v }))}
            type={showPwd ? 'text' : 'password'}
            startContent={<Icon icon={lockBold} className="text-default-400" fontSize={18} />}
            endContent={
              <button type="button" onClick={() => setShowPwd(v => !v)} className="text-default-400 hover:text-default-600">
                <Icon icon={showPwd ? eyeClosedBold : eyeBold} fontSize={18} />
              </button>
            }
            variant="bordered"
            isRequired
            isInvalid={!!errors.password}
            errorMessage={errors.password}
          />
          <Input
            label={t('setup.account.confirmPassword')}
            placeholder={t('setup.account.confirmPasswordPlaceholder')}
            value={form.confirmPassword}
            onValueChange={v => setForm(f => ({ ...f, confirmPassword: v }))}
            type={showConfirm ? 'text' : 'password'}
            startContent={<Icon icon={lockBold} className="text-default-400" fontSize={18} />}
            endContent={
              <button type="button" onClick={() => setShowConfirm(v => !v)} className="text-default-400 hover:text-default-600">
                <Icon icon={showConfirm ? eyeClosedBold : eyeBold} fontSize={18} />
              </button>
            }
            variant="bordered"
            isRequired
            isInvalid={!!errors.confirmPassword}
            errorMessage={errors.confirmPassword}
          />
        </div>
      </div>

      {apiError && (
        <div className="text-danger text-sm bg-danger-50 dark:bg-danger/10 rounded-lg px-3 py-2">{apiError}</div>
      )}

      <div className="flex justify-end pt-2">
        <Button
          color="primary"
          size="lg"
          onPress={handleNext}
          isLoading={loading}
          isDisabled={!form.username || !form.password || !form.confirmPassword || loading}
          endContent={!loading && <Icon icon={arrowRightBold} fontSize={18} />}
        >
          {t('setup.navigation.next')}
        </Button>
      </div>
    </div>
  );
}

// Step 2: LLM
interface LLMForm {
  llm_langchain_backend: string;
  llm_langchain_model: string;
  llm_langchain_api_base: string;
  llm_langchain_api_key: string;
  llm_ollama_base_url: string;
}

function LLMStep({ onNext, onSkip, onBack }: { onNext: (data: Partial<LLMForm>) => Promise<void>; onSkip: () => void; onBack: () => void }) {
  const { t } = useTranslation();
  const [form, setForm] = useState<LLMForm>({
    llm_langchain_backend: 'openai_compatible',
    llm_langchain_model: 'gpt-4o-mini',
    llm_langchain_api_base: '',
    llm_langchain_api_key: '',
    llm_ollama_base_url: 'http://localhost:11434',
  });
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);

  const isOllama = form.llm_langchain_backend === 'ollama';

  async function handleNext() {
    setLoading(true);
    try {
      await onNext(form);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-default-900">{t('setup.llm.title')}</h2>
        <p className="text-default-500 mt-1">{t('setup.llm.subtitle')}</p>
      </div>

      <Select
        label={t('llm.backend')}
        selectedKeys={[form.llm_langchain_backend]}
        onSelectionChange={keys => setForm(f => ({ ...f, llm_langchain_backend: String([...keys][0]) }))}
        variant="bordered"
      >
        <SelectItem key="openai_compatible">{t('llm.backendOpenAI')}</SelectItem>
        <SelectItem key="ollama">{t('llm.backendOllama')}</SelectItem>
      </Select>

      <Input
        label={t('llm.model')}
        value={form.llm_langchain_model}
        onValueChange={v => setForm(f => ({ ...f, llm_langchain_model: v }))}
        variant="bordered"
      />

      {isOllama ? (
        <Input
          label={t('llm.ollamaBaseUrl')}
          value={form.llm_ollama_base_url}
          onValueChange={v => setForm(f => ({ ...f, llm_ollama_base_url: v }))}
          variant="bordered"
        />
      ) : (
        <>
          <Input
            label={t('llm.apiBase')}
            placeholder="https://api.openai.com/v1"
            value={form.llm_langchain_api_base}
            onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_base: v }))}
            variant="bordered"
          />
          <Input
            label={t('llm.apiKey')}
            value={form.llm_langchain_api_key}
            onValueChange={v => setForm(f => ({ ...f, llm_langchain_api_key: v }))}
            type={showKey ? 'text' : 'password'}
            endContent={
              <button type="button" onClick={() => setShowKey(v => !v)} className="text-default-400 hover:text-default-600">
                <Icon icon={showKey ? eyeClosedBold : eyeBold} fontSize={18} />
              </button>
            }
            variant="bordered"
          />
        </>
      )}

      <StepNavigation onBack={onBack} onSkip={onSkip} onNext={handleNext} loading={loading} />
    </div>
  );
}

// Step 3: Adapters
function AdaptersStep({ onNext, onSkip, onBack }: { onNext: (data: object) => Promise<void>; onSkip: () => void; onBack: () => void }) {
  const { t } = useTranslation();
  const [enabledAdapters, setEnabledAdapters] = useState<string[]>([]);
  const [onebotPort, setOnebotPort] = useState('2290');
  const [telegramToken, setTelegramToken] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleNext() {
    setLoading(true);
    try {
      const data: Record<string, unknown> = { enabled_adapters: enabledAdapters };
      if (enabledAdapters.includes('onebot')) {
        data.onebot_port = Number(onebotPort) || 2290;
      }
      if (enabledAdapters.includes('telegram')) {
        data.telegram_bot_token = telegramToken;
      }
      await onNext(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-default-900">{t('setup.adapters.title')}</h2>
        <p className="text-default-500 mt-1">{t('setup.adapters.subtitle')}</p>
      </div>

      <CheckboxGroup
        label={t('adapters.enabledAdapters')}
        value={enabledAdapters}
        onValueChange={setEnabledAdapters}
        orientation="horizontal"
        classNames={{ label: 'text-sm text-default-700' }}
      >
        <Checkbox value="onebot">OneBot</Checkbox>
        <Checkbox value="telegram">Telegram</Checkbox>
      </CheckboxGroup>

      {enabledAdapters.includes('onebot') && (
        <Input
          label={t('adapters.onebotPort')}
          value={onebotPort}
          onValueChange={setOnebotPort}
          type="number"
          variant="bordered"
        />
      )}

      {enabledAdapters.includes('telegram') && (
        <Input
          label={t('adapters.telegramBotToken')}
          value={telegramToken}
          onValueChange={setTelegramToken}
          type="password"
          variant="bordered"
        />
      )}

      <StepNavigation onBack={onBack} onSkip={onSkip} onNext={handleNext} loading={loading} />
    </div>
  );
}

// Step 4: Notifications
function NotificationsStep({ onNext, onSkip, onBack }: { onNext: (data: object) => Promise<void>; onSkip: () => void; onBack: () => void }) {
  const { t } = useTranslation();
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState('587');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPass, setSmtpPass] = useState('');
  const [toEmail, setToEmail] = useState('');
  const [barkEnabled, setBarkEnabled] = useState(false);
  const [barkKey, setBarkKey] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleNext() {
    setLoading(true);
    try {
      await onNext({
        email_notifier_enabled: emailEnabled,
        ...(emailEnabled && {
          smtp_host: smtpHost,
          smtp_port: Number(smtpPort) || 587,
          smtp_username: smtpUser,
          smtp_password: smtpPass,
          email_notifier_to_email: toEmail,
        }),
        bark_notifier_enabled: barkEnabled,
        ...(barkEnabled && { bark_device_key: barkKey }),
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-default-900">{t('setup.notifications.title')}</h2>
        <p className="text-default-500 mt-1">{t('setup.notifications.subtitle')}</p>
      </div>

      {/* Email */}
      <Card className="border border-default-200">
        <CardBody className="gap-4">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{t('notifications.email')}</span>
            <Switch isSelected={emailEnabled} onValueChange={setEmailEnabled} size="sm" />
          </div>
          {emailEnabled && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label={t('notifications.smtpHost')} value={smtpHost} onValueChange={setSmtpHost} variant="bordered" size="sm" />
              <Input label={t('notifications.smtpPort')} value={smtpPort} onValueChange={setSmtpPort} type="number" variant="bordered" size="sm" />
              <Input label={t('notifications.smtpUsername')} value={smtpUser} onValueChange={setSmtpUser} variant="bordered" size="sm" />
              <Input label={t('notifications.smtpPassword')} value={smtpPass} onValueChange={setSmtpPass} type="password" variant="bordered" size="sm" />
              <Input label={t('notifications.toEmail')} value={toEmail} onValueChange={setToEmail} variant="bordered" size="sm" className="sm:col-span-2" />
            </div>
          )}
        </CardBody>
      </Card>

      {/* Bark */}
      <Card className="border border-default-200">
        <CardBody className="gap-4">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{t('notifications.bark')}</span>
            <Switch isSelected={barkEnabled} onValueChange={setBarkEnabled} size="sm" />
          </div>
          {barkEnabled && (
            <Input label={t('notifications.barkDeviceKey')} value={barkKey} onValueChange={setBarkKey} variant="bordered" size="sm" />
          )}
        </CardBody>
      </Card>

      <StepNavigation onBack={onBack} onSkip={onSkip} onNext={handleNext} loading={loading} />
    </div>
  );
}

// Step 5: Rules
function RulesStep({ onComplete, onSkip, onBack }: { onComplete: (data: object) => Promise<void>; onSkip: () => void; onBack: () => void }) {
  const { t } = useTranslation();
  const [ruleName, setRuleName] = useState('');
  const [ruleDesc, setRuleDesc] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleComplete() {
    setLoading(true);
    try {
      await onComplete({ ruleName, ruleDesc });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-default-900">{t('setup.rules.title')}</h2>
        <p className="text-default-500 mt-1">{t('setup.rules.subtitle')}</p>
      </div>

      <Input
        label={t('setup.rules.name')}
        placeholder={t('setup.rules.namePlaceholder')}
        value={ruleName}
        onValueChange={setRuleName}
        variant="bordered"
      />

      <Textarea
        label={t('setup.rules.description')}
        placeholder={t('setup.rules.descriptionPlaceholder')}
        value={ruleDesc}
        onValueChange={setRuleDesc}
        variant="bordered"
        minRows={3}
      />

      <p className="text-xs text-default-400">{t('setup.rules.hint')}</p>

      <div className="flex justify-between pt-2">
        <Button variant="flat" onPress={onBack} startContent={<Icon icon={arrowLeftBold} fontSize={18} />}>
          {t('setup.navigation.back')}
        </Button>
        <div className="flex gap-2">
          <Button variant="flat" color="default" onPress={onSkip}>
            {t('setup.navigation.skip')}
          </Button>
          <Button
            color="primary"
            onPress={handleComplete}
            isLoading={loading}
            endContent={!loading && <Icon icon={checkCircleBold} fontSize={18} />}
          >
            {t('setup.navigation.complete')}
          </Button>
        </div>
      </div>
    </div>
  );
}

// Shared navigation bar for steps 2–4
function StepNavigation({
  onBack, onSkip, onNext, loading,
}: {
  onBack: () => void;
  onSkip: () => void;
  onNext: () => void;
  loading: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex justify-between pt-2">
      <Button variant="flat" onPress={onBack} startContent={<Icon icon={arrowLeftBold} fontSize={18} />}>
        {t('setup.navigation.back')}
      </Button>
      <div className="flex gap-2">
        <Button variant="flat" color="default" onPress={onSkip}>
          {t('setup.navigation.skip')}
        </Button>
        <Button
          color="primary"
          onPress={onNext}
          isLoading={loading}
          endContent={!loading && <Icon icon={arrowRightBold} fontSize={18} />}
        >
          {t('setup.navigation.next')}
        </Button>
      </div>
    </div>
  );
}

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function SetupWizardPage() {
  const { t } = useTranslation();
  const { markSetupComplete } = useAuth();
  const navigate = useNavigate();

  const [currentStep, setCurrentStep] = useState(1);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [done, setDone] = useState(false);

  const completeStep = useCallback((step: number) => {
    setCompletedSteps(prev => new Set([...prev, step]));
  }, []);

  // Step 1: Account
  const handleAccountNext = useCallback(async (username: string, password: string) => {
    const res = await setupAdmin(username, password);
    markSetupComplete(res.token, res.username);
    completeStep(1);
    setCurrentStep(2);
  }, [markSetupComplete, completeStep]);

  // Step 2: LLM
  const handleLLMNext = useCallback(async (data: object) => {
    try { await updateSettings(data as Parameters<typeof updateSettings>[0]); } catch { /* ignore */ }
    completeStep(2);
    setCurrentStep(3);
  }, [completeStep]);

  // Step 3: Adapters
  const handleAdaptersNext = useCallback(async (data: object) => {
    try { await updateSettings(data as Parameters<typeof updateSettings>[0]); } catch { /* ignore */ }
    completeStep(3);
    setCurrentStep(4);
  }, [completeStep]);

  // Step 4: Notifications
  const handleNotificationsNext = useCallback(async (data: object) => {
    try { await updateSettings(data as Parameters<typeof updateSettings>[0]); } catch { /* ignore */ }
    completeStep(4);
    setCurrentStep(5);
  }, [completeStep]);

  // Step 5: Rules – complete setup
  const handleRulesComplete = useCallback(async (_data: object) => {
    completeStep(5);
    setDone(true);
  }, [completeStep]);

  const handleSkip = useCallback((step: number) => {
    completeStep(step);
    setCurrentStep(step + 1);
  }, [completeStep]);

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-default-50 via-default-100 to-default-200 dark:from-[#0d0d1a] dark:via-[#13131f] dark:to-[#1a1a2e] px-4">
        <div className="text-center space-y-6 max-w-md">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-success/10 mx-auto">
            <Icon icon={checkCircleBold} className="text-success" fontSize={40} />
          </div>
          <h1 className="text-3xl font-bold text-default-900">{t('setup.complete.title')}</h1>
          <p className="text-default-500">{t('setup.complete.subtitle')}</p>
          <Button
            color="primary"
            size="lg"
            className="font-semibold px-8"
            onPress={() => navigate('/', { replace: true })}
            startContent={<Icon icon={shieldCheckBold} fontSize={18} />}
          >
            {t('setup.complete.goButton')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-default-50 via-default-100 to-default-200 dark:from-[#0d0d1a] dark:via-[#13131f] dark:to-[#1a1a2e] p-4">
      <div
        className="w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl border border-default-200/40 flex"
        style={{ minHeight: 520 }}
      >
        {/* ── Left sidebar ─────────────────────────────────────────────── */}
        <div
          className="hidden md:flex flex-col w-72 shrink-0 p-7 relative overflow-hidden"
          style={{
            background: 'linear-gradient(160deg, #1e1b4b 0%, #312e81 40%, #4c1d95 80%, #5b21b6 100%)',
          }}
        >
          {/* Decorative blobs */}
          <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-white/5 blur-2xl pointer-events-none" />
          <div className="absolute bottom-10 -left-10 w-32 h-32 rounded-full bg-white/5 blur-xl pointer-events-none" />

          {/* Brand */}
          <div className="mb-8 relative z-10">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center">
                <Icon icon={shieldCheckBold} className="text-white" fontSize={20} />
              </div>
              <span className="font-bold text-white text-lg">{t('common.appName')}</span>
            </div>
            <p className="text-white/60 text-xs leading-relaxed">{t('setup.sidebarDesc')}</p>
          </div>

          {/* Steps */}
          <div className="flex-1 relative z-10">
            {STEPS.map(step => (
              <StepIndicator
                key={step.id}
                step={step}
                current={currentStep}
                completed={completedSteps}
              />
            ))}
          </div>

          {/* Help widget */}
          <div className="mt-6 p-3 rounded-xl bg-white/10 backdrop-blur-sm relative z-10">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                <Icon icon={shieldCheckBold} className="text-white" fontSize={14} />
              </div>
              <p className="text-white/70 text-xs leading-relaxed">{t('setup.helpText')}</p>
            </div>
          </div>
        </div>

        {/* ── Right content area ────────────────────────────────────────── */}
        <div className="flex-1 bg-background flex flex-col">
          {/* Mobile step indicator */}
          <div className="md:hidden flex items-center gap-2 px-6 pt-5 pb-3 border-b border-divider">
            {STEPS.map(s => (
              <div
                key={s.id}
                className={`h-1 flex-1 rounded-full transition-all ${
                  completedSteps.has(s.id) || s.id === currentStep ? 'bg-primary' : 'bg-default-200'
                }`}
              />
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-6 md:p-10">
            {/* Step indicator chip (mobile) */}
            <div className="md:hidden text-xs text-default-500 mb-4">
              {t('setup.stepOf', { current: currentStep, total: STEPS.length })}
            </div>

            {currentStep === 1 && <AccountStep onNext={handleAccountNext} />}
            {currentStep === 2 && <LLMStep onNext={handleLLMNext} onSkip={() => handleSkip(2)} onBack={() => setCurrentStep(1)} />}
            {currentStep === 3 && <AdaptersStep onNext={handleAdaptersNext} onSkip={() => handleSkip(3)} onBack={() => setCurrentStep(2)} />}
            {currentStep === 4 && <NotificationsStep onNext={handleNotificationsNext} onSkip={() => handleSkip(4)} onBack={() => setCurrentStep(3)} />}
            {currentStep === 5 && <RulesStep onComplete={handleRulesComplete} onSkip={() => { completeStep(5); setDone(true); }} onBack={() => setCurrentStep(4)} />}
          </div>
        </div>
      </div>
    </div>
  );
}
