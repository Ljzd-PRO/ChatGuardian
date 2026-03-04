import apiClient from './client'
import type { StatsResponse } from '../types'

export async function getRuleStats(): Promise<StatsResponse> {
  const res = await apiClient.get<StatsResponse>('/api/rule_stats')
  return res.data
}
