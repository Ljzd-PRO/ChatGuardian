import { apiFetch } from './client';

export interface AdapterStatus { name: string; running: boolean }

export const fetchAdapters = () => apiFetch<AdapterStatus[]>('/api/adapters/status');
export const startAdapters  = () => apiFetch<{ status: string }>('/adapters/start', { method: 'POST' });
export const stopAdapters   = () => apiFetch<{ status: string }>('/adapters/stop',  { method: 'POST' });
