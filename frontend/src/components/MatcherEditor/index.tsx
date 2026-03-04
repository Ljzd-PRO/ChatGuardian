import { Button, Input, Select, Tag, Space } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type {
  MatcherUnion,
  AndMatcher,
  OrMatcher,
  NotMatcher,
} from '../../types'

interface MatcherEditorProps {
  value: MatcherUnion
  onChange: (m: MatcherUnion) => void
  onDelete?: () => void
}

function defaultMatcher(): MatcherUnion {
  return { type: 'all' }
}

function LeafEditor({ value, onChange }: { value: MatcherUnion; onChange: (m: MatcherUnion) => void }) {
  const type = value.type

  function handleTypeChange(newType: string) {
    switch (newType) {
      case 'all': onChange({ type: 'all' }); break
      case 'sender': onChange({ type: 'sender', user_id: null, display_name: null }); break
      case 'mention': onChange({ type: 'mention', user_id: null, display_name: null }); break
      case 'chat': onChange({ type: 'chat', chat_id: '' }); break
      case 'chat_type': onChange({ type: 'chat_type', chat_type: 'group' }); break
      case 'adapter': onChange({ type: 'adapter', adapter_name: '' }); break
      case 'and': onChange({ type: 'and', matchers: [] }); break
      case 'or': onChange({ type: 'or', matchers: [] }); break
      case 'not': onChange({ type: 'not', matcher: { type: 'all' } }); break
      default: onChange({ type: 'all' })
    }
  }

  const typeOptions = [
    { value: 'all', label: '🌟 全匹配 (All)' },
    { value: 'sender', label: '👤 发送者 (Sender)' },
    { value: 'mention', label: '📢 @提及 (Mention)' },
    { value: 'chat', label: '💬 聊天室 (Chat)' },
    { value: 'chat_type', label: '📝 聊天类型 (Chat Type)' },
    { value: 'adapter', label: '🔌 适配器 (Adapter)' },
    { value: 'and', label: '🔵 AND 组 (全部满足)' },
    { value: 'or', label: '🟣 OR 组 (任一满足)' },
    { value: 'not', label: '🟥 NOT 组 (条件取反)' },
  ]

  return (
    <Space wrap>
      <Select
        value={type}
        onChange={handleTypeChange}
        options={typeOptions}
        style={{ width: 200 }}
        size="small"
      />
      {(type === 'sender' || type === 'mention') && (
        <>
          <Input
            placeholder="user_id"
            size="small"
            style={{ width: 120 }}
            value={(value as { type: string; user_id?: string | null }).user_id ?? ''}
            onChange={e => onChange({ ...value, user_id: e.target.value || null } as MatcherUnion)}
          />
          <Input
            placeholder="display_name"
            size="small"
            style={{ width: 120 }}
            value={(value as { type: string; display_name?: string | null }).display_name ?? ''}
            onChange={e => onChange({ ...value, display_name: e.target.value || null } as MatcherUnion)}
          />
        </>
      )}
      {type === 'chat' && (
        <Input
          placeholder="chat_id"
          size="small"
          style={{ width: 120 }}
          value={(value as { type: string; chat_id: string }).chat_id}
          onChange={e => onChange({ type: 'chat', chat_id: e.target.value })}
        />
      )}
      {type === 'chat_type' && (
        <Select
          value={(value as { type: string; chat_type: string }).chat_type}
          onChange={v => onChange({ type: 'chat_type', chat_type: v as 'group' | 'private' })}
          options={[{ value: 'group', label: 'Group' }, { value: 'private', label: 'Private' }]}
          style={{ width: 100 }}
          size="small"
        />
      )}
      {type === 'adapter' && (
        <Input
          placeholder="adapter_name"
          size="small"
          style={{ width: 120 }}
          value={(value as { type: string; adapter_name: string }).adapter_name}
          onChange={e => onChange({ type: 'adapter', adapter_name: e.target.value })}
        />
      )}
      {type === 'all' && <Tag color="blue">匹配所有消息</Tag>}
    </Space>
  )
}

const GROUP_LABELS: Record<string, string> = {
  and: '🔵 AND — 所有条件都要满足',
  or: '🟣 OR — 任一条件满足即可',
  not: '🟥 NOT — 子条件结果取反',
}

export default function MatcherEditor({ value, onChange, onDelete }: MatcherEditorProps) {
  const isGroup = value.type === 'and' || value.type === 'or'
  const isNot = value.type === 'not'

  const borderColor =
    value.type === 'and' ? '#1677ff' :
    value.type === 'or' ? '#722ed1' :
    value.type === 'not' ? '#ff4d4f' : '#d9d9d9'

  const bgColor =
    value.type === 'and' ? '#f0f7ff' :
    value.type === 'or' ? '#f9f0ff' :
    value.type === 'not' ? '#fff1f0' : 'transparent'

  function addChild(childType: 'and' | 'or' | 'not' | 'leaf') {
    let child: MatcherUnion
    if (childType === 'and') child = { type: 'and', matchers: [] }
    else if (childType === 'or') child = { type: 'or', matchers: [] }
    else if (childType === 'not') child = { type: 'not', matcher: { type: 'all' } }
    else child = defaultMatcher()

    if (value.type === 'and') {
      onChange({ type: 'and', matchers: [...(value as AndMatcher).matchers, child] })
    } else if (value.type === 'or') {
      onChange({ type: 'or', matchers: [...(value as OrMatcher).matchers, child] })
    }
  }

  function updateChild(index: number, child: MatcherUnion) {
    if (value.type === 'and') {
      const matchers = [...(value as AndMatcher).matchers]
      matchers[index] = child
      onChange({ type: 'and', matchers })
    } else if (value.type === 'or') {
      const matchers = [...(value as OrMatcher).matchers]
      matchers[index] = child
      onChange({ type: 'or', matchers })
    }
  }

  function deleteChild(index: number) {
    if (value.type === 'and') {
      const matchers = (value as AndMatcher).matchers.filter((_, i) => i !== index)
      onChange({ type: 'and', matchers })
    } else if (value.type === 'or') {
      const matchers = (value as OrMatcher).matchers.filter((_, i) => i !== index)
      onChange({ type: 'or', matchers })
    }
  }

  return (
    <div style={{ borderLeft: `3px solid ${borderColor}`, background: bgColor, paddingLeft: 12, paddingTop: 6, paddingBottom: 6, marginBottom: 8, borderRadius: '0 4px 4px 0' }}>
      <Space style={{ marginBottom: 4 }}>
        {(isGroup || isNot) && (
          <Tag color={value.type === 'and' ? 'blue' : value.type === 'or' ? 'purple' : 'red'} style={{ fontWeight: 600 }}>
            {GROUP_LABELS[value.type]}
          </Tag>
        )}
        {onDelete && (
          <Button size="small" danger icon={<DeleteOutlined />} onClick={onDelete} />
        )}
      </Space>

      {isGroup && (
        <>
          {(value as AndMatcher | OrMatcher).matchers.map((child, i) => (
            <MatcherEditor
              key={i}
              value={child}
              onChange={m => updateChild(i, m)}
              onDelete={() => deleteChild(i)}
            />
          ))}
          {(value as AndMatcher | OrMatcher).matchers.length === 0 && (
            <div style={{ color: '#aaa', marginBottom: 6, fontSize: 12 }}>（此组内暂无条件，请通过下方按钮添加子条件）</div>
          )}
          <Space wrap>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('leaf')}>➕ 条件</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('and')} style={{ color: '#1677ff', borderColor: '#1677ff' }}>🔵 AND 子组</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('or')} style={{ color: '#722ed1', borderColor: '#722ed1' }}>🟣 OR 子组</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('not')} style={{ color: '#ff4d4f', borderColor: '#ff4d4f' }}>🟥 NOT 子组</Button>
          </Space>
        </>
      )}

      {isNot && (
        <MatcherEditor
          value={(value as NotMatcher).matcher}
          onChange={m => onChange({ type: 'not', matcher: m })}
        />
      )}

      {!isGroup && !isNot && (
        <LeafEditor value={value} onChange={onChange} />
      )}
    </div>
  )
}
