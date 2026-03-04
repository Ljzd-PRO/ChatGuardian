import { useState, useEffect, useCallback } from 'react'
import { Tabs, Card, Typography, Tag, Space, message, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { getQueues } from '../../api/queues'
import type { QueueMessage } from '../../types'

function groupMessages(messages: QueueMessage[]): Record<string, QueueMessage[]> {
  const groups: Record<string, QueueMessage[]> = {}
  for (const msg of messages) {
    const key = `${msg.adapter}|${msg.chat_type}|${msg.chat_id}`
    if (!groups[key]) groups[key] = []
    groups[key].push(msg)
  }
  return groups
}

function MessageGroup({ groupKey, messages }: { groupKey: string; messages: QueueMessage[] }) {
  const [adapter, chatType, chatId] = groupKey.split('|')
  return (
    <Card
      size="small"
      title={
        <Space>
          <Tag color="blue">{adapter}</Tag>
          <Tag color={chatType === 'group' ? 'green' : 'orange'}>{chatType}</Tag>
          <Typography.Text type="secondary">#{chatId}</Typography.Text>
        </Space>
      }
      style={{ marginBottom: 12 }}
    >
      {messages.map((msg, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <div style={{
              background: '#e6f4ff',
              borderRadius: 8,
              padding: '6px 12px',
              maxWidth: '70%',
            }}>
              <Typography.Text strong style={{ fontSize: 12, display: 'block' }}>{msg.sender_name}</Typography.Text>
              <Typography.Text style={{ fontSize: 13 }}>{msg.content}</Typography.Text>
            </div>
            <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>{msg.timestamp}</Typography.Text>
          </div>
        </div>
      ))}
    </Card>
  )
}

export default function MessageQueue() {
  const [pending, setPending] = useState<QueueMessage[]>([])
  const [history, setHistory] = useState<QueueMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [msgApi, contextHolder] = message.useMessage()

  const fetchQueues = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getQueues()
      setPending(data.pending)
      setHistory(data.history)
    } catch {
      msgApi.error('Failed to load queues')
    } finally {
      setLoading(false)
    }
  }, [msgApi])

  useEffect(() => { void fetchQueues() }, [fetchQueues])

  const pendingGroups = groupMessages(pending)
  const historyGroups = groupMessages(history)

  const tabItems = [
    {
      key: 'pending',
      label: `待处理 (${pending.length})`,
      children: (
        <div>
          {Object.entries(pendingGroups).length === 0
            ? <Typography.Text type="secondary">暂无待处理消息</Typography.Text>
            : Object.entries(pendingGroups).map(([k, msgs]) => (
              <MessageGroup key={k} groupKey={k} messages={msgs} />
            ))
          }
        </div>
      ),
    },
    {
      key: 'history',
      label: `历史 (${history.length})`,
      children: (
        <div>
          {Object.entries(historyGroups).length === 0
            ? <Typography.Text type="secondary">暂无历史消息</Typography.Text>
            : Object.entries(historyGroups).map(([k, msgs]) => (
              <MessageGroup key={k} groupKey={k} messages={msgs} />
            ))
          }
        </div>
      ),
    },
  ]

  return (
    <div>
      {contextHolder}
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void fetchQueues()}>刷新</Button>
      </Space>
      <Tabs items={tabItems} />
    </div>
  )
}
