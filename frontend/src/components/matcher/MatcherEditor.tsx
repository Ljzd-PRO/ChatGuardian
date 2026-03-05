import type { MatcherUnion, MatcherType } from '../../api/types';
import { Button, Input, Select, SelectItem, Chip } from '@heroui/react';
import { Plus, Trash2 } from 'lucide-react';

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
        <Chip color={color} size="sm" variant="flat">
          {value.type.toUpperCase()}
        </Chip>
        <Select
          size="sm"
          className="w-36"
          selectedKeys={[value.type]}
          onSelectionChange={(keys) => {
            const k = Array.from(keys)[0] as MatcherType;
            if (k) changeType(k);
          }}
          aria-label="Matcher type"
        >
          {ALL_TYPES.map(t => (
            <SelectItem key={t}>{t}</SelectItem>
          ))}
        </Select>
        {onRemove && (
          <Button isIconOnly size="sm" color="danger" variant="light" onPress={onRemove}>
            <Trash2 size={14} />
          </Button>
        )}
      </div>

      {/* Leaf fields */}
      {(value.type === 'sender' || value.type === 'mention') && (
        <div className="flex gap-2 flex-wrap">
          <Input
            size="sm"
            label="User ID"
            placeholder="e.g. 123456"
            value={value.user_id ?? ''}
            onValueChange={v => onChange({ ...value, user_id: v || undefined })}
            className="w-40"
          />
          <Input
            size="sm"
            label="Display Name"
            placeholder="e.g. Alice"
            value={value.display_name ?? ''}
            onValueChange={v => onChange({ ...value, display_name: v || undefined })}
            className="w-40"
          />
        </div>
      )}

      {value.type === 'chat' && (
        <Input
          size="sm"
          label="Chat ID"
          isRequired
          placeholder="e.g. group_001"
          value={value.chat_id}
          onValueChange={v => onChange({ ...value, chat_id: v })}
          className="w-48"
        />
      )}

      {value.type === 'chat_type' && (
        <Select
          size="sm"
          label="Chat Type"
          className="w-36"
          selectedKeys={[value.chat_type]}
          onSelectionChange={(keys) => {
            const k = Array.from(keys)[0] as 'group' | 'private';
            if (k) onChange({ ...value, chat_type: k });
          }}
        >
          <SelectItem key="group">Group</SelectItem>
          <SelectItem key="private">Private</SelectItem>
        </Select>
      )}

      {value.type === 'adapter' && (
        <Input
          size="sm"
          label="Adapter"
          isRequired
          placeholder="e.g. onebot"
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
            startContent={<Plus size={14} />}
            onPress={() => onChange({ ...value, matchers: [...value.matchers, { type: 'all' }] })}
          >
            Add condition
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
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-default-700">Matcher</p>
      <MatcherNode value={value} onChange={onChange} />
      <details className="text-xs">
        <summary className="cursor-pointer text-default-400">View JSON</summary>
        <pre className="mt-1 p-2 bg-default-100 rounded text-default-600 overflow-auto text-xs">
          {JSON.stringify(value, null, 2)}
        </pre>
      </details>
    </div>
  );
}
