import { useState, useEffect, useCallback } from 'react'
import {
  Button, Collapse, Switch, Slider, Tag, Input, Space, Modal,
  Form, Typography, Popconfirm, message, Row, Col
} from 'antd'
import { PlusOutlined, DeleteOutlined, SaveOutlined } from '@ant-design/icons'
import { listRules, saveRule, deleteRule } from '../../api/rules'
import MatcherEditor from '../../components/MatcherEditor'
import type { DetectionRule, MatcherUnion } from '../../types'

export default function RuleManagement() {
  const [rules, setRules] = useState<DetectionRule[]>([])
  const [edited, setEdited] = useState<Record<string, DetectionRule>>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [msgApi, contextHolder] = message.useMessage()
  const [form] = Form.useForm<{ name: string; description: string; score_threshold: number }>()

  const fetchRules = useCallback(async () => {
    try {
      const data = await listRules()
      setRules(data)
    } catch {
      msgApi.error('Failed to load rules')
    }
  }, [msgApi])

  useEffect(() => { void fetchRules() }, [fetchRules])

  function getRule(ruleId: string): DetectionRule {
    return edited[ruleId] ?? rules.find(r => r.rule_id === ruleId)!
  }

  function updateRule(ruleId: string, patch: Partial<DetectionRule>) {
    const base = getRule(ruleId)
    setEdited(prev => ({ ...prev, [ruleId]: { ...base, ...patch } }))
  }

  async function handleSave(ruleId: string) {
    try {
      await saveRule(getRule(ruleId))
      msgApi.success('Saved')
      setEdited(prev => { const n = { ...prev }; delete n[ruleId]; return n })
      void fetchRules()
    } catch {
      msgApi.error('Save failed')
    }
  }

  async function handleDelete(ruleId: string) {
    try {
      await deleteRule(ruleId)
      msgApi.success('Deleted')
      void fetchRules()
    } catch {
      msgApi.error('Delete failed')
    }
  }

  async function handleCreate(values: { name: string; description: string; score_threshold: number }) {
    const newRule: DetectionRule = {
      rule_id: `rule_${Date.now()}`,
      name: values.name,
      description: values.description,
      matcher: { type: 'all' },
      topic_hints: [],
      score_threshold: values.score_threshold ?? 0.5,
      enabled: true,
      parameters: [],
    }
    try {
      await saveRule(newRule)
      msgApi.success('Created')
      setModalOpen(false)
      form.resetFields()
      void fetchRules()
    } catch {
      msgApi.error('Create failed')
    }
  }

  const collapseItems = rules.map(rule => {
    const r = getRule(rule.rule_id)
    const isDirty = !!edited[rule.rule_id]
    return {
      key: rule.rule_id,
      label: (
        <Space>
          <Tag color="blue">{r.rule_id}</Tag>
          <Typography.Text strong>{r.name}</Typography.Text>
          <Switch
            checked={r.enabled}
            size="small"
            onChange={v => { updateRule(rule.rule_id, { enabled: v }) }}
            onClick={(_checked: boolean, e: React.MouseEvent<HTMLButtonElement> | React.KeyboardEvent<HTMLButtonElement>) => { e.stopPropagation() }}
          />
          {isDirty && <Tag color="orange">未保存</Tag>}
        </Space>
      ),
      children: (
        <div>
          <Row gutter={16}>
            <Col span={24}>
              <Typography.Text type="secondary">描述:</Typography.Text>
              <Input
                value={r.description}
                onChange={e => updateRule(rule.rule_id, { description: e.target.value })}
                style={{ marginTop: 4, marginBottom: 8 }}
              />
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Typography.Text type="secondary">分数阈值: {r.score_threshold}</Typography.Text>
              <Slider
                min={0} max={1} step={0.01}
                value={r.score_threshold}
                onChange={v => updateRule(rule.rule_id, { score_threshold: v })}
              />
            </Col>
            <Col span={12}>
              <Typography.Text type="secondary">主题提示:</Typography.Text>
              <div style={{ marginTop: 4 }}>
                {r.topic_hints.map((hint, i) => (
                  <Tag
                    key={i}
                    closable
                    onClose={() => {
                      const hints = r.topic_hints.filter((_, idx) => idx !== i)
                      updateRule(rule.rule_id, { topic_hints: hints })
                    }}
                  >{hint}</Tag>
                ))}
                <Input.Search
                  size="small"
                  placeholder="添加提示"
                  enterButton={<PlusOutlined />}
                  style={{ width: 160, marginTop: 4 }}
                  onSearch={v => {
                    if (v) updateRule(rule.rule_id, { topic_hints: [...r.topic_hints, v] })
                  }}
                />
              </div>
            </Col>
          </Row>

          <Typography.Text type="secondary">匹配器:</Typography.Text>
          <div style={{ marginTop: 8, padding: 8, background: '#fafafa', borderRadius: 4 }}>
            <MatcherEditor
              value={r.matcher}
              onChange={(m: MatcherUnion) => updateRule(rule.rule_id, { matcher: m })}
            />
          </div>

          <Collapse
            style={{ marginTop: 8 }}
            items={[{
              key: 'json',
              label: 'JSON 预览',
              children: <pre style={{ fontSize: 12 }}>{JSON.stringify(r, null, 2)}</pre>
            }]}
          />

          <Space style={{ marginTop: 12 }}>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              disabled={!isDirty}
              onClick={() => void handleSave(rule.rule_id)}
            >保存</Button>
            <Popconfirm
              title="确认删除此规则？"
              onConfirm={() => void handleDelete(rule.rule_id)}
            >
              <Button danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          </Space>
        </div>
      ),
    }
  })

  return (
    <div>
      {contextHolder}
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增规则</Button>
      </Space>
      <Collapse items={collapseItems} />

      <Modal
        title="新增规则"
        open={modalOpen}
        onOk={() => form.submit()}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
      >
        <Form form={form} layout="vertical" onFinish={values => void handleCreate(values)}>
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea />
          </Form.Item>
          <Form.Item name="score_threshold" label="分数阈值" initialValue={0.5}>
            <Slider min={0} max={1} step={0.01} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
