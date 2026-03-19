import type { TFunction } from 'i18next';

const ADAPTER_LABEL_KEYS: Record<string, string> = {
  onebot: 'OneBot',
  telegram: 'Telegram',
  discord: 'Discord',
  wechat: 'adapters.wechatTitle',
  dingtalk: 'adapters.dingtalkTitle',
  feishu: 'Feishu',
  virtual: 'adapters.virtualAdapter',
};

export function formatAdapterName(t: TFunction, adapterName?: string | null): string {
  if (!adapterName) return '—';
  const keyOrLiteral = ADAPTER_LABEL_KEYS[adapterName];
  if (!keyOrLiteral) return adapterName;
  if (keyOrLiteral.includes('.')) return t(keyOrLiteral);
  return keyOrLiteral;
}

export function formatChatType(t: TFunction, chatType?: string | null): string {
  if (!chatType) return '—';
  if (chatType === 'group') return t('matcher.group');
  if (chatType === 'private') return t('matcher.private');
  return chatType;
}
