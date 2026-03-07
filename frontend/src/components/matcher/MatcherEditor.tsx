import type { MatcherUnion, MatcherType } from '../../api/types';
import { Button, Input, Select, SelectItem, Chip } from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import addCircleBold from '@iconify/icons-solar/add-circle-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import checkSquareBold from '@iconify/icons-solar/check-square-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import closeCircleBold from '@iconify/icons-solar/close-circle-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import { useTranslation } from 'react-i18next';

const TYPE_COLORS: Record<string, 'primary' | 'secondary' | 'danger' | 'default' | 'warning' | 'success'> = {
  and: 'primary',
  or: 'secondary',
  not: 'danger',
  all: 'success',
  sender: 'default',
  mention: 'default',
  chat: 'default',
  chat_type: 'warning',
  adapter: 'default',
};

const ALL_TYPES: MatcherType[] = [
  'and', 'or', 'not', 'all', 'sender', 'mention', 'chat', 'chat_type', 'adapter',
];

const MATCHER_ICONS: Record<MatcherType, IconifyIcon> = {
  and: checkSquareBold,
  or: addCircleBold,
  not: closeCircleBold,
  all: checkCircleBold,
  sender: userRoundedBold,
  mention: bellBingBold,
  chat: chatDotsBold,
  chat_type: usersGroupRoundedBold,
  adapter: plugCircleBold,
};

function defaultMatcher(type: MatcherType): MatcherUnion {
  switch (type) {
    case 'and': return { type: 'and', matchers: [] };
    case 'or':  return { type: 'or',  matchers: [] };
    case 'not': return { type: 'not', matcher: { type: 'all' } };
    case 'all': return { type: 'all' };
    case 'sender':   return { type: 'sender' };
    case 'mention':  return { type: 'mention' };
    case 'chat':     return { type: 'chat', chat_id: '' };
    case 'chat_type':return { type: 'chat_type', chat_type: 'group' };
    case 'adapter':  return { type: 'adapter', adapter_name: '' };
  }
}

interface MatcherNodeProps {
  value: MatcherUnion;
  onChange: (v: MatcherUnion) => void;
  onRemove?: () => void;
  depth?: number;
}

export function MatcherNode({ value, onChange, onRemove, depth = 0 }: MatcherNodeProps) {
  const { t } = useTranslation();
  const color = TYPE_COLORS[value.type] ?? 'default';
  const indent = depth * 12;

  function changeType(newType: MatcherType) {
    onChange(defaultMatcher(newType));
  }

  return (
    <div
      className="border border-divider rounded-lg p-3 bg-content1 space-y-2"
      style={{ marginLeft: indent }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <Chip
          color={color}
          size="sm"
          variant="flat"
          startContent={<Icon icon={MATCHER_ICONS[value.type]} width={14} />}
        >
          {value.type.toUpperCase()}
        </Chip>
        <Select
          size="sm"
          className="w-40"
          selectedKeys={[value.type]}
          onSelectionChange={(keys) => {
            const k = Array.from(keys)[0] as MatcherType;
            if (k) changeType(k);
          }}
          aria-label={t('matcher.matcherType')}
        >
          {ALL_TYPES.map(matcherType => (
            <SelectItem
              key={matcherType}
              startContent={(
                <Chip
                  size="sm"
                  variant="flat"
                  color={TYPE_COLORS[matcherType] ?? 'default'}
                  className="justify-center"
                >
                  <Icon icon={MATCHER_ICONS[matcherType]} width={14} />
                </Chip>
              )}
            >
              {t(`matcher.types.${matcherType}`)}
            </SelectItem>
          ))}
        </Select>
        {onRemove && (
          <Button isIconOnly size="sm" color="danger" variant="light" onPress={onRemove}>
            <Icon icon={trashBin2Bold} width={16} />
          </Button>
        )}
      </div>

      {/* Leaf fields */}
      {(value.type === 'sender' || value.type === 'mention') && (
        <div className="flex gap-2 flex-wrap">
          <Input
            size="sm"
            label={t('matcher.userId')}
            value={value.user_id ?? ''}
            onValueChange={v => onChange({ ...value, user_id: v || undefined })}
            className="w-40"
          />
          <Input
            size="sm"
            label={t('matcher.displayName')}
            value={value.display_name ?? ''}
            onValueChange={v => onChange({ ...value, display_name: v || undefined })}
            className="w-40"
          />
        </div>
      )}

      {value.type === 'chat' && (
        <Input
          size="sm"
          label={t('matcher.chatId')}
          isRequired
          value={value.chat_id}
          onValueChange={v => onChange({ ...value, chat_id: v })}
          className="w-48"
        />
      )}

      {value.type === 'chat_type' && (
        <Select
          size="sm"
          label={t('matcher.chatType')}
          className="w-36"
          selectedKeys={[value.chat_type]}
          onSelectionChange={(keys) => {
            const k = Array.from(keys)[0] as 'group' | 'private';
            if (k) onChange({ ...value, chat_type: k });
          }}
        >
          <SelectItem key="group">{t('matcher.group')}</SelectItem>
          <SelectItem key="private">{t('matcher.private')}</SelectItem>
        </Select>
      )}

      {value.type === 'adapter' && (
        <Input
          size="sm"
          label={t('matcher.adapterName')}
          isRequired
          value={value.adapter_name}
          onValueChange={v => onChange({ ...value, adapter_name: v })}
          className="w-48"
        />
      )}

      {/* AND / OR children */}
      {(value.type === 'and' || value.type === 'or') && (
        <div className="space-y-2">
          {value.matchers.map((child, i) => (
            <MatcherNode
              key={i}
              value={child}
              depth={depth + 1}
              onChange={v => {
                const matchers = [...value.matchers];
                matchers[i] = v;
                onChange({ ...value, matchers });
              }}
              onRemove={() => {
                const matchers = value.matchers.filter((_, idx) => idx !== i);
                onChange({ ...value, matchers });
              }}
            />
          ))}
          <Button
            size="sm"
            variant="flat"
            startContent={<Icon icon={addCircleBold} width={16} />}
            onPress={() => onChange({ ...value, matchers: [...value.matchers, { type: 'all' }] })}
          >
            {t('matcher.addCondition')}
          </Button>
        </div>
      )}

      {/* NOT child */}
      {value.type === 'not' && (
        <MatcherNode
          value={value.matcher}
          depth={depth + 1}
          onChange={v => onChange({ ...value, matcher: v })}
        />
      )}
    </div>
  );
}

interface MatcherEditorProps {
  value: MatcherUnion;
  onChange: (v: MatcherUnion) => void;
}

export default function MatcherEditor({ value, onChange }: MatcherEditorProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-default-700">{t('matcher.matcher')}</p>
      <MatcherNode value={value} onChange={onChange} />
      <details className="text-xs">
        <summary className="cursor-pointer text-default-400">{t('matcher.viewJson')}</summary>
        <pre className="mt-1 p-2 bg-default-100 rounded text-default-600 overflow-auto text-xs">
          {JSON.stringify(value, null, 2)}
        </pre>
      </details>
    </div>
  );
}
