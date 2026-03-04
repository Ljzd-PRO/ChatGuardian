import { useState, useEffect, useCallback } from 'react'
import { Collapse, Progress, Tag, Typography, Space, Card, message } from 'antd'
import { getRuleStats } from '../../api/stats'
import type { StatsResponse } from '../../types'

export default function TriggerStats() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [msgApi, contextHolder] = message.useMessage()

  const fetchStats = useCallback(async () => {
    try {
      const data = await getRuleStats()
      setStats(data)
    } catch {
      msgApi.error('Failed to load stats')
    }
  }, [msgApi])

  useEffect(() => { void fetchStats() }, [fetchStats])

  if (!stats) return <div>{contextHolder}<Typography.Text>加载中...</Typography.Text></div>

  const items = Object.entries(stats.data).map(([ruleName, ruleData]) => ({
    key: ruleName,
    label: (
      <Space>
        <Typography.Text strong>{ruleName}</Typography.Text>
        <Tag color="blue">触发 {ruleData.count} 次</Tag>
      </Space>
    ),
    children: (
      <div>
        <Typography.Text type="secondary">{ruleData.description}</Typography.Text>
        {ruleData.records.map(record => (
          <Card key={record.id} size="small" style={{ marginTop: 8 }}>
            <Space wrap>
              <Typography.Text type="secondary">{record.trigger_time}</Typography.Text>
              <Tag color={record.result === 'violation' ? 'red' : 'green'}>{record.result}</Tag>
              <div style={{ minWidth: 200 }}>
                <Typography.Text type="secondary">置信度: </Typography.Text>
                <Progress percent={Math.round(record.confidence * 100)} size="small" style={{ width: 150 }} />
              </div>
            </Space>
            {record.reason && (
              <Typography.Paragraph style={{ marginTop: 8, marginBottom: 8 }}>
                <Typography.Text type="secondary">原因: </Typography.Text>{record.reason}
              </Typography.Paragraph>
            )}
            <div style={{ marginTop: 8 }}>
              {record.messages.map((msg, i) => (
                <div key={i} style={{
                  background: '#f5f5f5',
                  borderRadius: 8,
                  padding: '6px 12px',
                  marginBottom: 4,
                  display: 'inline-block',
                  maxWidth: '80%',
                }}>
                  <Typography.Text strong style={{ fontSize: 12 }}>{msg.sender}: </Typography.Text>
                  <Typography.Text style={{ fontSize: 12 }}>{msg.content}</Typography.Text>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    ),
  }))

  return (
    <div>
      {contextHolder}
      <Collapse items={items} />
    </div>
  )
}
