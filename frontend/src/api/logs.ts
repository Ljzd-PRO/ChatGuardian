import { apiFetch } from './client';

export interface LogEntry { timestamp: string; level: string; message: string }
export interface VersionInfo { name: string; version: string }

export const fetchLogs = (limit = 100) =>
  apiFetch<LogEntry[]>(`/api/logs?limit=${limit}`);

export const clearLogs = () =>
  apiFetch<{ cleared: number }>('/api/logs', { method: 'DELETE' });

export const restartBackend = () =>
  apiFetch<{ status: string }>('/api/logs/restart', { method: 'POST' });

export const fetchVersion = () =>
  apiFetch<VersionInfo>('/api/version');
