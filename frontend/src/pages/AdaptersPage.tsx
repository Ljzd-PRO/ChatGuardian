import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Select, SelectItem, Spinner, Switch,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import chartBold from '@iconify/icons-solar/chart-2-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import cloudBold from '@iconify/icons-solar/cloud-bold';
import code2Bold from '@iconify/icons-solar/code-2-bold';
import cpuBoltBold from '@iconify/icons-solar/cpu-bolt-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import globeLinear from '@iconify/icons-solar/globe-linear';
import hashtagBold from '@iconify/icons-solar/hash-bold';
import keyBold from '@iconify/icons-solar/key-bold';
import magicStick2Bold from '@iconify/icons-solar/magic-stick-2-bold';
import playBold from '@iconify/icons-solar/play-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import sendSquareBold from '@iconify/icons-solar/send-square-bold';
import server2Bold from '@iconify/icons-solar/server-2-bold';
import settingsBold from '@iconify/icons-solar/settings-bold';
import stopBold from '@iconify/icons-solar/stop-bold';
import { useTranslation } from 'react-i18next';
import { fetchAdapters, startAdapters, stopAdapters } from '../api/adapters';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';

export default function AdaptersPage() {
  const { t } = useTranslation();
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
      discord_bot_token: settings.discord_bot_token ?? '',
      discord_guild_ids: settings.discord_guild_ids ?? [],
      wechat_token: settings.wechat_token ?? '',
      wechat_encoding_aes_key: settings.wechat_encoding_aes_key ?? '',
      wechat_corp_id: settings.wechat_corp_id ?? '',
      wechat_host: settings.wechat_host ?? '0.0.0.0',
      wechat_port: settings.wechat_port ?? 8082,
      dingtalk_client_id: settings.dingtalk_client_id ?? '',
      dingtalk_client_secret: settings.dingtalk_client_secret ?? '',
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] });
      qc.invalidateQueries({ queryKey: ['adapters'] });
    },
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('adapters.loading')} /></div>;

  return (
    <div className="space-y-5 lg:space-y-6">
      {/* ── Adapter Controls ── */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-default-900">
            <Icon icon={plugCircleBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
            <span className="font-semibold">{t('adapters.controls')}</span>
          </div>
          <div className="flex gap-2">
            <Button
              color="success"
              variant="flat"
              startContent={<Icon icon={playBold} fontSize={ICON_SIZES.button} />}
              isLoading={start.isPending}
              onPress={() => start.mutate()}
            >
              {t('adapters.startAll')}
            </Button>
            <Button
              color="danger"
              variant="flat"
              startContent={<Icon icon={stopBold} fontSize={ICON_SIZES.button} />}
              isLoading={stop.isPending}
              onPress={() => stop.mutate()}
            >
              {t('adapters.stopAll')}
            </Button>
          </div>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          {adapters?.length === 0 && (
            <p className="text-default-400 text-sm">{t('adapters.noAdapters')}</p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {adapters?.map(a => (
              <Card key={a.name} className="border border-default-200">
                <CardBody className="flex flex-row items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Icon icon={plugCircleBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
                      <p className="font-medium text-default-900">{a.name}</p>
                    </div>
                    <p className="text-xs text-default-400">{t('adapters.adapterLabel')}</p>
                  </div>
                  <Chip color={a.running ? 'success' : 'default'} variant="flat" size="sm">
                    {a.running ? t('common.running') : t('common.stopped')}
                  </Chip>
                </CardBody>
              </Card>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* ── Adapter Settings ── */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-default-900">
            <Icon icon={settingsBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
            <span className="font-semibold">{t('adapters.adapterSettings')}</span>
          </div>
          <Button color="primary" isDisabled={!settings} isLoading={save.isPending} onPress={() => save.mutate()}>
            {t('common.save')}
          </Button>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-5">

          {/* ── Enabled Adapters multi-select ── */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-default-700">
              <Icon icon={plugCircleBold} fontSize={ICON_SIZES.input} aria-hidden="true" />
              <span>{t('adapters.enabledAdapters')}</span>
            </div>
            <Select
              label={t('adapters.enabledAdapters')}
              selectionMode="multiple"
              selectedKeys={new Set(form.enabled_adapters ?? [])}
              onSelectionChange={keys => setForm(f => ({ ...f, enabled_adapters: Array.from(keys) as string[] }))}
              className="max-w-xl"
            >
              {['onebot', 'telegram', 'discord', 'wechat', 'dingtalk', 'feishu', 'virtual'].map(a => (
                <SelectItem key={a}>{a}</SelectItem>
              ))}
            </Select>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">

            {/* ── OneBot ── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={cpuBoltBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>OneBot</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Host"
                  startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.onebot_host ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, onebot_host: v }))}
                />
                <Input
                  label="Port"
                  type="number"
                  startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={String(form.onebot_port ?? 2290)}
                  onValueChange={v => setForm(f => ({ ...f, onebot_port: Number(v) }))}
                />
                <Input
                  label="Access Token"
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.onebot_access_token ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, onebot_access_token: v.trim() === '' ? null : v }))}
                  className="sm:col-span-2"
                />
              </div>
            </div>

            {/* ── Telegram ── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={sendSquareBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>Telegram</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label="Bot Token"
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.telegram_bot_token ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, telegram_bot_token: v.trim() === '' ? null : v }))}
                />
                <Input
                  label={t('adapters.telegramPollingTimeout')}
                  startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  type="number"
                  value={String(form.telegram_polling_timeout ?? 10)}
                  onValueChange={v => setForm(f => ({ ...f, telegram_polling_timeout: Number(v) }))}
                />
                <div className="sm:col-span-2">
                  <Switch
                    isSelected={form.telegram_drop_pending_updates ?? false}
                    onValueChange={v => setForm(f => ({ ...f, telegram_drop_pending_updates: v }))}
                  >
                    {t('adapters.telegramDropPending')}
                  </Switch>
                </div>
              </div>
            </div>

            {/* ── Discord ── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={chatDotsBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>Discord</span>
              </div>
              <p className="text-xs text-default-500">{t('adapters.discordDesc')}</p>
              <div className="grid gap-3">
                <Input
                  label={t('adapters.discordBotToken')}
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.discord_bot_token ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, discord_bot_token: v.trim() === '' ? null : v }))}
                />
                <Input
                  label={t('adapters.discordGuildIds')}
                  startContent={<Icon icon={globeLinear} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={(form.discord_guild_ids ?? []).join(',')}
                  onValueChange={v => {
                    const ids = v.split(',').map(s => s.trim()).filter(Boolean).map(Number).filter(n => !isNaN(n));
                    setForm(f => ({ ...f, discord_guild_ids: ids }));
                  }}
                  description={t('adapters.discordGuildIdsHint')}
                />
              </div>
            </div>

            {/* ── WeChat Work（企业微信）── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={chatDotsBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>{t('adapters.wechatTitle')}</span>
              </div>
              <p className="text-xs text-default-500">{t('adapters.wechatDesc')}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label={t('adapters.wechatToken')}
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.wechat_token ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, wechat_token: v.trim() === '' ? null : v }))}
                  className="sm:col-span-2"
                />
                <Input
                  label={t('adapters.wechatEncodingAesKey')}
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.wechat_encoding_aes_key ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, wechat_encoding_aes_key: v.trim() === '' ? null : v }))}
                  className="sm:col-span-2"
                />
                <Input
                  label={t('adapters.wechatCorpId')}
                  startContent={<Icon icon={cloudBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.wechat_corp_id ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, wechat_corp_id: v.trim() === '' ? null : v }))}
                  className="sm:col-span-2"
                />
                <Input
                  label={t('adapters.wechatCallbackHost')}
                  startContent={<Icon icon={server2Bold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.wechat_host ?? '0.0.0.0'}
                  onValueChange={v => setForm(f => ({ ...f, wechat_host: v }))}
                />
                <Input
                  label={t('adapters.wechatCallbackPort')}
                  type="number"
                  startContent={<Icon icon={hashtagBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={String(form.wechat_port ?? 8082)}
                  onValueChange={v => setForm(f => ({ ...f, wechat_port: Number(v) }))}
                />
              </div>
            </div>

            {/* ── DingTalk（钉钉）── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={chatDotsBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>{t('adapters.dingtalkTitle')}</span>
              </div>
              <p className="text-xs text-default-500">{t('adapters.dingtalkDesc')}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  label={t('adapters.dingtalkClientId')}
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.dingtalk_client_id ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, dingtalk_client_id: v.trim() === '' ? null : v }))}
                />
                <Input
                  label={t('adapters.dingtalkClientSecret')}
                  startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                  value={form.dingtalk_client_secret ?? ''}
                  onValueChange={v => setForm(f => ({ ...f, dingtalk_client_secret: v.trim() === '' ? null : v }))}
                />
              </div>
            </div>

            {/* ── Feishu ── */}
            <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
              <div className="flex items-center gap-2 font-semibold text-default-900">
                <Icon icon={chatDotsBold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
                <span>Feishu</span>
              </div>
              <Input
                label="App ID"
                startContent={<Icon icon={keyBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={form.feishu_app_id ?? ''}
                onValueChange={v => setForm(f => ({ ...f, feishu_app_id: v.trim() === '' ? null : v }))}
              />
            </div>

          </div>

          {/* ── Virtual Adapter ── */}
          <div className="rounded-2xl border border-default-200 bg-default-50 p-4 space-y-3 shadow-sm">
            <div className="flex items-center gap-2 font-semibold text-default-900">
              <Icon icon={magicStick2Bold} fontSize={ICON_SIZES.cardHeader} aria-hidden="true" />
              <span>{t('adapters.virtualAdapter')}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Input
                label={t('adapters.chatCount')}
                type="number"
                startContent={<Icon icon={chartBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={String(form.virtual_adapter_chat_count ?? 3)}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_chat_count: Number(v) }))}
              />
              <Input
                label={t('adapters.membersPerChat')}
                type="number"
                startContent={<Icon icon={cpuBoltBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={String(form.virtual_adapter_members_per_chat ?? 5)}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_members_per_chat: Number(v) }))}
              />
              <Input
                label={t('adapters.messagesPerChat')}
                type="number"
                startContent={<Icon icon={chatDotsBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={String(form.virtual_adapter_messages_per_chat ?? 10)}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_messages_per_chat: Number(v) }))}
              />
              <Input
                label={t('adapters.intervalMin')}
                type="number"
                startContent={<Icon icon={chartBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={String(form.virtual_adapter_interval_min_seconds ?? 0.1)}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_interval_min_seconds: Number(v) }))}
              />
              <Input
                label={t('adapters.intervalMax')}
                type="number"
                startContent={<Icon icon={chartBold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={String(form.virtual_adapter_interval_max_seconds ?? 0.6)}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_interval_max_seconds: Number(v) }))}
              />
              <Input
                label={t('adapters.scriptPath')}
                startContent={<Icon icon={code2Bold} fontSize={ICON_SIZES.input} className="text-default-500" aria-hidden="true" />}
                value={form.virtual_adapter_script_path ?? ''}
                onValueChange={v => setForm(f => ({ ...f, virtual_adapter_script_path: v.trim() === '' ? null : v }))}
              />
            </div>
          </div>

          {save.isSuccess && <p className="text-success text-sm">{t('common.saveSuccess')}</p>}
          {save.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
        </CardBody>
      </Card>
    </div>
  );
}
