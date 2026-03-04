import apiClient from './client'
import type { QueuesResponse } from '../types'

export async function getQueues(): Promise<QueuesResponse> {
  const res = await apiClient.get<QueuesResponse>('/api/queues')
  return res.data
}
