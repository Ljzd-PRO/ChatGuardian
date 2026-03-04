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
      default: onChange({ type: 'all' })
    }
  }

  const typeOptions = [
    { value: 'all', label: 'All' },
    { value: 'sender', label: 'Sender' },
    { value: 'mention', label: 'Mention' },
    { value: 'chat', label: 'Chat' },
    { value: 'chat_type', label: 'Chat Type' },
    { value: 'adapter', label: 'Adapter' },
  ]

  return (
    <Space wrap>
      <Select
        value={type}
        onChange={handleTypeChange}
        options={typeOptions}
        style={{ width: 120 }}
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
      {type === 'all' && <Tag color="blue">Match All</Tag>}
    </Space>
  )
}

export default function MatcherEditor({ value, onChange, onDelete }: MatcherEditorProps) {
  const isGroup = value.type === 'and' || value.type === 'or'
  const isNot = value.type === 'not'

  const borderColor =
    value.type === 'and' ? '#1677ff' :
    value.type === 'or' ? '#722ed1' :
    value.type === 'not' ? '#ff4d4f' : '#d9d9d9'

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
    <div style={{ borderLeft: `3px solid ${borderColor}`, paddingLeft: 12, marginBottom: 8 }}>
      <Space style={{ marginBottom: 4 }}>
        <Tag color={value.type === 'and' ? 'blue' : value.type === 'or' ? 'purple' : value.type === 'not' ? 'red' : 'default'}>
          {value.type.toUpperCase()}
        </Tag>
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
          <Space>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('leaf')}>Leaf</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('and')} style={{ color: '#1677ff' }}>AND</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('or')} style={{ color: '#722ed1' }}>OR</Button>
            <Button size="small" icon={<PlusOutlined />} onClick={() => addChild('not')} style={{ color: '#ff4d4f' }}>NOT</Button>
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
