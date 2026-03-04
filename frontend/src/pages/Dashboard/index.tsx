import { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Badge, Button, Space, Statistic, Typography, message } from 'antd'
import { PlayCircleOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons'
import { getHealth, getLLMHealth, getAdapterStatus, startAdapters, stopAdapters } from '../../api/dashboard'
import type { HealthResponse, LLMHealthResponse, AdapterStatus } from '../../types'

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [llmHealth, setLLMHealth] = useState<LLMHealthResponse | null>(null)
  const [adapters, setAdapters] = useState<AdapterStatus[]>([])
  const [loading, setLoading] = useState(false)
  const [msgApi, contextHolder] = message.useMessage()

  const fetchAll = useCallback(async () => {
    setLoading(true)
    try {
      const [h, l, a] = await Promise.allSettled([getHealth(), getLLMHealth(), getAdapterStatus()])
      if (h.status === 'fulfilled') setHealth(h.value)
      if (l.status === 'fulfilled') setLLMHealth(l.value)
      if (a.status === 'fulfilled') setAdapters(a.value)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchAll() }, [fetchAll])

  async function handleStart() {
    try {
      await startAdapters()
      msgApi.success('Adapters started')
      void fetchAll()
    } catch {
      msgApi.error('Failed to start adapters')
    }
  }

  async function handleStop() {
    try {
      await stopAdapters()
      msgApi.success('Adapters stopped')
      void fetchAll()
    } catch {
      msgApi.error('Failed to stop adapters')
    }
  }

  const metrics = llmHealth?.scheduler?.metrics

  return (
    <div>
      {contextHolder}
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<PlayCircleOutlined />} type="primary" onClick={() => void handleStart()}>启动全部适配器</Button>
        <Button icon={<StopOutlined />} danger onClick={() => void handleStop()}>停止全部适配器</Button>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void fetchAll()}>刷新</Button>
      </Space>

      <Row gutter={[16, 16]}>
        {adapters.map(a => (
          <Col key={a.name} xs={24} sm={12} md={8}>
            <Card size="small" title={a.name}>
              <Badge status={a.running ? 'success' : 'error'} text={a.running ? '运行中' : '已停止'} />
            </Card>
          </Col>
        ))}
      </Row>

      {health && (
        <Card title="系统状态" style={{ marginTop: 16 }}>
          <Typography.Text>状态: {health.status}</Typography.Text>
          <br />
          <Typography.Text type="secondary">时间: {health.time}</Typography.Text>
        </Card>
      )}

      {llmHealth && (
        <Card title="LLM 配置" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="Backend" value={llmHealth.llm.backend} /></Col>
            <Col span={8}><Statistic title="Model" value={llmHealth.llm.model} /></Col>
            <Col span={8}><Statistic title="API Key" value={llmHealth.llm.api_key_configured ? '已配置' : '未配置'} /></Col>
          </Row>
        </Card>
      )}

      {metrics && (
        <Card title="调度器指标" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}><Statistic title="总请求数" value={metrics.total_requests} /></Col>
            <Col span={6}><Statistic title="总批次数" value={metrics.total_batches} /></Col>
            <Col span={6}><Statistic title="LLM 调用次数" value={metrics.total_llm_calls} /></Col>
            <Col span={6}><Statistic title="成功批次" value={metrics.successful_batches} /></Col>
            <Col span={6}><Statistic title="回退批次" value={metrics.fallback_batches} /></Col>
            <Col span={6}><Statistic title="重试次数" value={metrics.retry_attempts} /></Col>
            <Col span={6}><Statistic title="幂等命中" value={metrics.idempotency_completed_hits} /></Col>
          </Row>
        </Card>
      )}
    </div>
  )
}
