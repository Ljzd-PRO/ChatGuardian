import apiClient from './client'
import type { DetectionRule } from '../types'

export async function listRules(): Promise<DetectionRule[]> {
  const res = await apiClient.get<DetectionRule[]>('/rules/list')
  return res.data
}

export async function saveRule(rule: DetectionRule): Promise<DetectionRule> {
  const res = await apiClient.post<DetectionRule>('/rules', rule)
  return res.data
}

export async function deleteRule(ruleId: string): Promise<{ status: string; rule_id: string; deleted: boolean }> {
  const res = await apiClient.post<{ status: string; rule_id: string; deleted: boolean }>(`/rules/delete/${ruleId}`)
  return res.data
}
