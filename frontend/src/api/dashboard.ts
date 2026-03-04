import apiClient from './client'
import type { HealthResponse, LLMHealthResponse, AdapterStatus } from '../types'

export async function getHealth(): Promise<HealthResponse> {
  const res = await apiClient.get<HealthResponse>('/health')
  return res.data
}

export async function getLLMHealth(): Promise<LLMHealthResponse> {
  const res = await apiClient.get<LLMHealthResponse>('/llm/health', { params: { do_ping: false } })
  return res.data
}

export async function getAdapterStatus(): Promise<AdapterStatus[]> {
  const res = await apiClient.get<AdapterStatus[]>('/api/adapters/status')
  return res.data
}

export async function startAdapters(): Promise<{ status: string; enabled_adapters: string[] }> {
  const res = await apiClient.post<{ status: string; enabled_adapters: string[] }>('/adapters/start')
  return res.data
}

export async function stopAdapters(): Promise<{ status: string; enabled_adapters: string[] }> {
  const res = await apiClient.post<{ status: string; enabled_adapters: string[] }>('/adapters/stop')
  return res.data
}
