import { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  CardBody,
  Checkbox,
  Input,
  Select,
  SelectItem,
  Slider,
  Spinner,
  Switch,
  Textarea,
} from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import shieldUserBold from '@iconify/icons-solar/shield-user-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import bellBold from '@iconify/icons-solar/bell-bold';
import listCheckBold from '@iconify/icons-solar/list-check-bold';
import arrowRightBold from '@iconify/icons-solar/arrow-right-bold';
import arrowLeftBold from '@iconify/icons-solar/arrow-left-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthActions, useAuthStatus } from '../hooks/useAuth';
import {
  fetchSettings,
  updateSettings,
  fetchNotificationsConfig,
  type AppSettings,
  type NotificationsConfig,
} from '../api/settings';

type WizardStepKey = 'account' | 'llm' | 'adapters' | 'notifications' | 'rules';

const STEPS: { key: WizardStepKey; titleKey: string; descKey: string; icon: IconifyIcon; optional?: boolean }[] = [
  { key: 'account',        titleKey: 'setup.steps.account.title',        descKey: 'setup.steps.account.desc',        icon: shieldUserBold },
  { key: 'llm',            titleKey: 'setup.steps.llm.title',            descKey: 'setup.steps.llm.desc',            icon: cpuBoltBold, optional: true },
  { key: 'adapters',       titleKey: 'setup.steps.adapters.title',       descKey: 'setup.steps.adapters.desc',       icon: plugCircleBold, optional: true },
  { key: 'notifications',  titleKey: 'setup.steps.notifications.title',  descKey: 'setup.steps.notifications.desc',  icon: bellBold, optional: true },
  { key: 'rules',          titleKey: 'setup.steps.rules.title',          descKey: 'setup.steps.rules.desc',          icon: listCheckBold, optional: true },
];

export default function SetupWizardPage() {
  const { data: auth } = useAuthStatus();
  const navigate = useNavigate();
  const { t } = useTranslation();

  if (!auth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
        <Spinner size="lg" label={t('common.loading')} />
      </div>
    );
  }

  return <WizardContent />;
}

function WizardContent() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { register: registerMut } = useAuthActions();
  const settingsQuery = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const notificationsQuery = useQuery({ queryKey: ['notifications_config'], queryFn: fetchNotificationsConfig });

  const [stepIndex, setStepIndex] = useState(0);
  const [completed, setCompleted] = useState<boolean[]>(Array(STEPS.length).fill(false));
  const [accountForm, setAccountForm] = useState({ username: '', password: '', confirm: '', agree: true });
  const [llmForm, setLlmForm] = useState<Partial<AppSettings>>({});
  const [adapterForm, setAdapterForm] = useState<Partial<AppSettings>>({});
  const [notifForm, setNotifForm] = useState<NotificationsConfig | null>(null);
  const [ruleForm, setRuleForm] = useState<Partial<AppSettings>>({});
  const [error, setError] = useState<string | null>(null);

  const llmSave = useMutation({ mutationFn: () => updateSettings(llmForm) });
  const adapterSave = useMutation({ mutationFn: () => updateSettings(adapterForm) });
  const notifSave = useMutation({
    mutationFn: () => updateSettings({
      email_notifier_enabled: notifForm?.email.enabled,
      email_notifier_to_email: notifForm?.email.to_email,
      smtp_host: notifForm?.email.smtp_host,
      smtp_port: notifForm?.email.smtp_port,
      smtp_username: notifForm?.email.smtp_username,
      smtp_password: notifForm?.email.smtp_password,
      smtp_sender: notifForm?.email.smtp_sender,
      bark_notifier_enabled: notifForm?.bark.enabled,
      bark_device_key: notifForm?.bark.device_key,
      bark_device_keys: notifForm?.bark.device_keys,
      bark_server_url: notifForm?.bark.server_url,
      bark_group: notifForm?.bark.group,
      bark_level: notifForm?.bark.level,
    }),
  });
  const ruleSave = useMutation({ mutationFn: () => updateSettings(ruleForm) });

  useEffect(() => {
    if (settingsQuery.data) {
      setLlmForm(f => ({
        llm_langchain_backend: f.llm_langchain_backend ?? settingsQuery.data.llm_langchain_backend,
        llm_langchain_model: f.llm_langchain_model ?? settingsQuery.data.llm_langchain_model,
        llm_langchain_api_base: f.llm_langchain_api_base ?? settingsQuery.data.llm_langchain_api_base,
        llm_langchain_api_key: f.llm_langchain_api_key ?? settingsQuery.data.llm_langchain_api_key,
        llm_langchain_temperature: f.llm_langchain_temperature ?? settingsQuery.data.llm_langchain_temperature,
        llm_timeout_seconds: f.llm_timeout_seconds ?? settingsQuery.data.llm_timeout_seconds,
        llm_max_parallel_batches: f.llm_max_parallel_batches ?? settingsQuery.data.llm_max_parallel_batches,
        llm_rules_per_batch: f.llm_rules_per_batch ?? settingsQuery.data.llm_rules_per_batch,
        llm_ollama_base_url: f.llm_ollama_base_url ?? settingsQuery.data.llm_ollama_base_url,
        llm_display_timezone: f.llm_display_timezone ?? settingsQuery.data.llm_display_timezone,
      }));
      setAdapterForm(f => ({
        enabled_adapters: f.enabled_adapters ?? settingsQuery.data.enabled_adapters,
        onebot_host: f.onebot_host ?? settingsQuery.data.onebot_host,
        onebot_port: f.onebot_port ?? settingsQuery.data.onebot_port,
        onebot_access_token: f.onebot_access_token ?? settingsQuery.data.onebot_access_token,
        telegram_bot_token: f.telegram_bot_token ?? settingsQuery.data.telegram_bot_token,
        telegram_polling_timeout: f.telegram_polling_timeout ?? settingsQuery.data.telegram_polling_timeout,
        telegram_drop_pending_updates: f.telegram_drop_pending_updates ?? settingsQuery.data.telegram_drop_pending_updates,
        wechat_endpoint: f.wechat_endpoint ?? settingsQuery.data.wechat_endpoint,
        feishu_app_id: f.feishu_app_id ?? settingsQuery.data.feishu_app_id,
      }));
      setRuleForm(f => ({
        context_message_limit: f.context_message_limit ?? settingsQuery.data.context_message_limit,
        detection_cooldown_seconds: f.detection_cooldown_seconds ?? settingsQuery.data.detection_cooldown_seconds,
        detection_min_new_messages: f.detection_min_new_messages ?? settingsQuery.data.detection_min_new_messages,
        detection_wait_timeout_seconds: f.detection_wait_timeout_seconds ?? settingsQuery.data.detection_wait_timeout_seconds,
        hook_timeout_seconds: f.hook_timeout_seconds ?? settingsQuery.data.hook_timeout_seconds,
        enable_internal_rule_generation: f.enable_internal_rule_generation ?? settingsQuery.data.enable_internal_rule_generation,
        pending_queue_limit: f.pending_queue_limit ?? settingsQuery.data.pending_queue_limit,
        history_list_limit: f.history_list_limit ?? settingsQuery.data.history_list_limit,
        external_rule_generation_endpoint: f.external_rule_generation_endpoint ?? settingsQuery.data.external_rule_generation_endpoint,
      }));
    }
  }, [settingsQuery.data]);

  useEffect(() => {
    if (notificationsQuery.data) {
      setNotifForm(notificationsQuery.data);
    }
  }, [notificationsQuery.data]);

  const currentStep = STEPS[stepIndex];
  const isLast = stepIndex === STEPS.length - 1;

  const stepStatus = useMemo(() => STEPS.map((_, idx) => {
    if (completed[idx]) return 'done';
    if (idx === stepIndex) return 'active';
    return 'idle';
  }), [completed, stepIndex]);

  async function next() {
    setError(null);
    const proceed = async () => {
      setCompleted(prev => prev.map((v, i) => (i === stepIndex ? true : v)));
      if (!isLast) setStepIndex(i => i + 1);
      else navigate('/', { replace: true });
    };

    if (currentStep.key === 'account') {
      if (!accountForm.username || !accountForm.password || accountForm.password !== accountForm.confirm) {
        setError(t('setup.validation.account'));
        return;
      }
      registerMut.mutate(
        { username: accountForm.username, password: accountForm.password },
        {
          onSuccess: async () => {
            await qc.invalidateQueries({ queryKey: ['auth_status'] });
            proceed();
          },
          onError: err => setError((err as Error).message),
        },
      );
      return;
    }

    if (currentStep.key === 'llm' && llmForm.llm_langchain_model) {
      llmSave.mutate(undefined, { onSuccess: proceed, onError: err => setError((err as Error).message) });
      return;
    }
    if (currentStep.key === 'adapters' && adapterForm.enabled_adapters) {
      adapterSave.mutate(undefined, { onSuccess: proceed, onError: err => setError((err as Error).message) });
      return;
    }
    if (currentStep.key === 'notifications' && notifForm) {
      notifSave.mutate(undefined, { onSuccess: proceed, onError: err => setError((err as Error).message) });
      return;
    }
    if (currentStep.key === 'rules' && ruleForm.context_message_limit !== undefined) {
      ruleSave.mutate(undefined, { onSuccess: proceed, onError: err => setError((err as Error).message) });
      return;
    }

    proceed();
  }

  function back() {
    setError(null);
    setStepIndex(i => Math.max(0, i - 1));
  }

  function skip() {
    setCompleted(prev => prev.map((v, i) => (i === stepIndex ? true : v)));
    if (!isLast) setStepIndex(i => i + 1);
    else navigate('/', { replace: true });
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-950 to-black text-white flex">
      <aside className="w-full max-w-sm bg-gradient-to-b from-pink-600/70 via-purple-700/80 to-indigo-900/80 p-6 md:p-8 flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-white/10">
            <Icon icon={shieldCheckBold} fontSize={24} />
          </div>
          <div>
            <p className="text-xl font-semibold">{t('setup.title')}</p>
            <p className="text-sm text-white/80">{t('setup.subtitle')}</p>
          </div>
        </div>
        <div className="space-y-3">
          {STEPS.map((step, idx) => (
            <div
              key={step.key}
              className={`flex gap-3 items-center rounded-2xl px-3 py-3 transition ${
                idx === stepIndex ? 'bg-white/10 border border-white/20' : 'bg-white/5 border border-transparent'
              }`}
            >
              <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                stepStatus[idx] === 'done' ? 'bg-green-500/20 text-green-200' :
                stepStatus[idx] === 'active' ? 'bg-white/15 text-white' :
                'bg-white/5 text-white/60'
              }`}>
                {stepStatus[idx] === 'done' ? (
                  <Icon icon={checkCircleBold} fontSize={20} />
                ) : (
                  <Icon icon={step.icon} fontSize={20} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{t(step.titleKey)}</p>
                <p className="text-xs text-white/70 truncate">{t(step.descKey)}</p>
              </div>
              {step.optional && <span className="text-[11px] text-white/60">{t('setup.optional')}</span>}
            </div>
          ))}
        </div>
        <div className="mt-auto text-xs text-white/70">
          {t('setup.hint')}
        </div>
      </aside>

      <main className="flex-1 p-4 md:p-8 lg:p-12 bg-gradient-to-br from-slate-900/60 via-slate-950 to-black overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <header className="mb-6">
            <p className="uppercase tracking-wide text-xs text-white/60">{t('setup.stepLabel', { current: stepIndex + 1, total: STEPS.length })}</p>
            <h1 className="text-3xl font-bold text-white mt-1">{t(currentStep.titleKey)}</h1>
            <p className="text-white/70 mt-2 max-w-3xl">{t(currentStep.descKey)}</p>
          </header>

          <Card className="bg-white/5 border border-white/10 shadow-2xl">
            <CardBody>
              {currentStep.key === 'account' && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label={t('auth.username')}
                    value={accountForm.username}
                    onValueChange={v => setAccountForm(f => ({ ...f, username: v }))}
                    isRequired
                  />
                  <Input
                    label={t('auth.password')}
                    type="password"
                    value={accountForm.password}
                    onValueChange={v => setAccountForm(f => ({ ...f, password: v }))}
                    isRequired
                  />
                  <Input
                    label={t('auth.confirmPassword')}
                    type="password"
                    value={accountForm.confirm}
                    onValueChange={v => setAccountForm(f => ({ ...f, confirm: v }))}
                    isRequired
                  />
                  <div className="md:col-span-2">
                    <Checkbox
                      isSelected={accountForm.agree}
                      onValueChange={v => setAccountForm(f => ({ ...f, agree: v }))}
                    >
                      {t('setup.agreement')}
                    </Checkbox>
                  </div>
                </div>
              )}

              {currentStep.key === 'llm' && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Select
                    label={t('llm.backend')}
                    selectedKeys={[llmForm.llm_langchain_backend ?? 'openai_compatible']}
                    onSelectionChange={keys => setLlmForm(f => ({ ...f, llm_langchain_backend: Array.from(keys)[0] as string }))}
                  >
                    <SelectItem key="openai_compatible">OpenAI</SelectItem>
                    <SelectItem key="ollama">Ollama</SelectItem>
                  </Select>
                  <Input
                    label={t('llm.model')}
                    value={llmForm.llm_langchain_model ?? ''}
                    onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_model: v }))}
                  />
                  <Input
                    label={t('llm.apiBase')}
                    value={llmForm.llm_langchain_api_base ?? ''}
                    onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_api_base: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('llm.apiKey')}
                    type="password"
                    value={llmForm.llm_langchain_api_key ?? ''}
                    onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_api_key: v.trim() === '' ? null : v }))}
                  />
                  <Input
                    label={t('llm.temperature')}
                    type="number"
                    value={String(llmForm.llm_langchain_temperature ?? 0)}
                    onValueChange={v => setLlmForm(f => ({ ...f, llm_langchain_temperature: Number(v) }))}
                  />
                  <Input
                    label={t('llm.timeout')}
                    type="number"
                    value={String(llmForm.llm_timeout_seconds ?? 30)}
                    onValueChange={v => setLlmForm(f => ({ ...f, llm_timeout_seconds: Number(v) }))}
                  />
                </div>
              )}

              {currentStep.key === 'adapters' && (
                <div className="space-y-4">
                  <Select
                    label={t('adapters.enabledAdapters')}
                    selectionMode="multiple"
                    selectedKeys={new Set(adapterForm.enabled_adapters ?? [])}
                    onSelectionChange={keys => setAdapterForm(f => ({ ...f, enabled_adapters: Array.from(keys) as string[] }))}
                  >
                    {['onebot', 'telegram', 'wechat', 'feishu', 'virtual'].map(a => (
                      <SelectItem key={a}>{a}</SelectItem>
                    ))}
                  </Select>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      label="OneBot Host"
                      value={adapterForm.onebot_host ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_host: v }))}
                    />
                    <Input
                      label="OneBot Port"
                      type="number"
                      value={String(adapterForm.onebot_port ?? 2290)}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_port: Number(v) }))}
                    />
                    <Input
                      label="Access Token"
                      value={adapterForm.onebot_access_token ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, onebot_access_token: v.trim() === '' ? null : v }))}
                    />
                    <Input
                      label="Telegram Bot Token"
                      value={adapterForm.telegram_bot_token ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, telegram_bot_token: v.trim() === '' ? null : v }))}
                    />
                    <Input
                      label="Polling Timeout (s)"
                      value={String(adapterForm.telegram_polling_timeout ?? 10)}
                      type="number"
                      onValueChange={v => setAdapterForm(f => ({ ...f, telegram_polling_timeout: Number(v) }))}
                    />
                    <Switch
                      isSelected={adapterForm.telegram_drop_pending_updates ?? false}
                      onValueChange={v => setAdapterForm(f => ({ ...f, telegram_drop_pending_updates: v }))}
                    >
                      {t('adapters.telegramDropPending')}
                    </Switch>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Input
                      label="WeChat Endpoint"
                      value={adapterForm.wechat_endpoint ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, wechat_endpoint: v.trim() === '' ? null : v }))}
                    />
                    <Input
                      label="Feishu App ID"
                      value={adapterForm.feishu_app_id ?? ''}
                      onValueChange={v => setAdapterForm(f => ({ ...f, feishu_app_id: v.trim() === '' ? null : v }))}
                    />
                  </div>
                </div>
              )}

              {currentStep.key === 'notifications' && !notifForm && (
                <div className="flex justify-center py-6"><Spinner /></div>
              )}
              {currentStep.key === 'notifications' && notifForm && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Switch
                    isSelected={notifForm.email.enabled}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, enabled: v } }) : f)}
                  >
                    {t('notifications.email')}
                  </Switch>
                  <Switch
                    isSelected={notifForm.bark.enabled}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, bark: { ...f.bark, enabled: v } }) : f)}
                  >
                    Bark
                  </Switch>
                  <Input
                    label="SMTP Host"
                    value={notifForm.email.smtp_host ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, smtp_host: v } }) : f)}
                  />
                  <Input
                    label="SMTP Port"
                    type="number"
                    value={String(notifForm.email.smtp_port ?? 587)}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, smtp_port: Number(v) } }) : f)}
                  />
                  <Input
                    label="SMTP Username"
                    value={notifForm.email.smtp_username ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, smtp_username: v.trim() || null } }) : f)}
                  />
                  <Input
                    label="SMTP Password"
                    type="password"
                    value={notifForm.email.smtp_password ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, smtp_password: v.trim() || null } }) : f)}
                  />
                  <Input
                    label="Sender"
                    value={notifForm.email.smtp_sender ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, smtp_sender: v.trim() || null } }) : f)}
                  />
                  <Input
                    label="To Email"
                    value={notifForm.email.to_email ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, email: { ...f.email, to_email: v.trim() || null } }) : f)}
                  />
                  <Input
                    label="Bark Device Key"
                    value={notifForm.bark.device_key ?? ''}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, bark: { ...f.bark, device_key: v.trim() || null } }) : f)}
                  />
                  <Input
                    label="Bark Server URL"
                    value={notifForm.bark.server_url}
                    onValueChange={v => setNotifForm(f => f ? ({ ...f, bark: { ...f.bark, server_url: v } }) : f)}
                  />
                </div>
              )}

              {currentStep.key === 'rules' && (
                <div className="grid gap-4">
                  <Input
                    label={t('rules.contextMessageLimit')}
                    type="number"
                    value={String(ruleForm.context_message_limit ?? 10)}
                    onValueChange={v => setRuleForm(f => ({ ...f, context_message_limit: Number(v) }))}
                  />
                  <Slider
                    label={t('rules.detectionCooldown')}
                    value={ruleForm.detection_cooldown_seconds ?? 0}
                    onChange={v => setRuleForm(f => ({ ...f, detection_cooldown_seconds: Number(v) }))}
                    minValue={0}
                    maxValue={120}
                  />
                  <Slider
                    label={t('rules.minNewMessages')}
                    value={ruleForm.detection_min_new_messages ?? 1}
                    onChange={v => setRuleForm(f => ({ ...f, detection_min_new_messages: Number(v) }))}
                    minValue={1}
                    maxValue={10}
                  />
                  <Slider
                    label={t('rules.detectionWaitTimeout')}
                    value={ruleForm.detection_wait_timeout_seconds ?? 30}
                    onChange={v => setRuleForm(f => ({ ...f, detection_wait_timeout_seconds: Number(v) }))}
                    minValue={5}
                    maxValue={120}
                  />
                  <Input
                    label={t('rules.pendingQueueLimit')}
                    type="number"
                    value={String(ruleForm.pending_queue_limit ?? 200)}
                    onValueChange={v => setRuleForm(f => ({ ...f, pending_queue_limit: Number(v) }))}
                  />
                  <Input
                    label={t('rules.historyListLimit')}
                    type="number"
                    value={String(ruleForm.history_list_limit ?? 1000)}
                    onValueChange={v => setRuleForm(f => ({ ...f, history_list_limit: Number(v) }))}
                  />
                  <Switch
                    isSelected={ruleForm.enable_internal_rule_generation ?? false}
                    onValueChange={v => setRuleForm(f => ({ ...f, enable_internal_rule_generation: v }))}
                  >
                    {t('rules.enableInternalRuleGen')}
                  </Switch>
                  <Textarea
                    label={t('rules.externalRuleEndpoint')}
                    value={ruleForm.external_rule_generation_endpoint ?? ''}
                    onValueChange={v => setRuleForm(f => ({ ...f, external_rule_generation_endpoint: v.trim() === '' ? null : v }))}
                  />
                </div>
              )}

              {error && <p className="text-danger mt-4">{error}</p>}
            </CardBody>
          </Card>

          <div className="flex flex-wrap gap-3 justify-between items-center mt-6">
            <Button
              variant="flat"
              color="default"
              startContent={<Icon icon={arrowLeftBold} fontSize={18} />}
              isDisabled={stepIndex === 0}
              onPress={back}
            >
              {t('setup.back')}
            </Button>
            <div className="flex gap-2">
              {currentStep.optional && (
                <Button
                  variant="light"
                  color="secondary"
                  startContent={<Icon icon={arrowRightBold} fontSize={18} />}
                  onPress={skip}
                >
                  {t('setup.skip')}
                </Button>
              )}
              <Button
                color="primary"
                endContent={<Icon icon={arrowRightBold} fontSize={18} />}
                isLoading={registerMut.isPending || llmSave.isPending || adapterSave.isPending || notifSave.isPending || ruleSave.isPending}
                onPress={next}
              >
                {isLast ? t('setup.finish') : t('setup.continue')}
              </Button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
