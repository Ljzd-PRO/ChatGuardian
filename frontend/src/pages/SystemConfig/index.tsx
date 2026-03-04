import { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Typography, Tag, Space, message } from 'antd'
import { getHealth, getLLMHealth } from '../../api/dashboard'
import type { HealthResponse, LLMHealthResponse } from '../../types'

export default function SystemConfig() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [llmHealth, setLLMHealth] = useState<LLMHealthResponse | null>(null)
  const [msgApi, contextHolder] = message.useMessage()

  const fetchAll = useCallback(async () => {
    try {
      const [h, l] = await Promise.allSettled([getHealth(), getLLMHealth()])
      if (h.status === 'fulfilled') setHealth(h.value)
      if (l.status === 'fulfilled') setLLMHealth(l.value)
    } catch {
      msgApi.error('Failed to load config')
    }
  }, [msgApi])

  useEffect(() => { void fetchAll() }, [fetchAll])

  return (
    <div>
      {contextHolder}
      <Row gutter={[16, 16]}>
        {health && (
          <Col span={24}>
            <Card title="系统健康状态">
              <Space>
                <Tag color={health.status === 'ok' ? 'green' : 'red'}>{health.status}</Tag>
                <Typography.Text type="secondary">最后检查: {health.time}</Typography.Text>
              </Space>
            </Card>
          </Col>
        )}
        {llmHealth && (
          <>
            <Col xs={24} md={12}>
              <Card title="LLM 配置">
                <Row gutter={[8, 8]}>
                  <Col span={12}><Typography.Text type="secondary">Backend:</Typography.Text></Col>
                  <Col span={12}><Typography.Text>{llmHealth.llm.backend}</Typography.Text></Col>
                  <Col span={12}><Typography.Text type="secondary">Model:</Typography.Text></Col>
                  <Col span={12}><Typography.Text>{llmHealth.llm.model}</Typography.Text></Col>
                  <Col span={12}><Typography.Text type="secondary">Client Class:</Typography.Text></Col>
                  <Col span={12}><Typography.Text>{llmHealth.llm.client_class}</Typography.Text></Col>
                  <Col span={12}><Typography.Text type="secondary">API Key:</Typography.Text></Col>
                  <Col span={12}>
                    <Tag color={llmHealth.llm.api_key_configured ? 'green' : 'red'}>
                      {llmHealth.llm.api_key_configured ? '已配置' : '未配置'}
                    </Tag>
                  </Col>
                </Row>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card title="调度器配置">
                <Row gutter={[8, 8]}>
                  <Col span={16}><Typography.Text type="secondary">最大并行批次:</Typography.Text></Col>
                  <Col span={8}><Typography.Text>{llmHealth.scheduler.max_parallel_batches}</Typography.Text></Col>
                </Row>
              </Card>
            </Col>
          </>
        )}
      </Row>
    </div>
  )
}
