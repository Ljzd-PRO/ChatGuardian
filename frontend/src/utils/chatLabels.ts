import type { TFunction } from 'i18next';

const ADAPTER_LABEL_KEYS: Record<string, { key: string; defaultValue: string }> = {
  onebot:   { key: 'adapters.onebotTitle',   defaultValue: 'OneBot' },
  telegram: { key: 'adapters.telegramTitle', defaultValue: 'Telegram' },
  discord:  { key: 'adapters.discordTitle',  defaultValue: 'Discord' },
  wechat:   { key: 'adapters.wechatTitle',   defaultValue: 'WeChat' },
  dingtalk: { key: 'adapters.dingtalkTitle', defaultValue: 'DingTalk' },
  feishu:   { key: 'adapters.feishuTitle',   defaultValue: 'Feishu' },
  virtual:  { key: 'adapters.virtualAdapter', defaultValue: 'Virtual' },
};

export function formatAdapterName(t: TFunction, adapterName?: string | null): string {
  if (!adapterName) return '—';
  const entry = ADAPTER_LABEL_KEYS[adapterName];
  if (!entry) return adapterName;
  const { key, defaultValue } = entry;
  return t(key, { defaultValue });
}

export function formatChatType(t: TFunction, chatType?: string | null): string {
  if (!chatType) return '—';
  if (chatType === 'group') return t('matcher.group');
  if (chatType === 'private') return t('matcher.private');
  return chatType;
}
