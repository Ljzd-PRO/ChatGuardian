import { apiFetch } from './client';

export interface LogEntry { timestamp: string; level: string; message: string }

export const fetchLogs = (limit = 100) =>
  apiFetch<LogEntry[]>(`/api/logs?limit=${limit}`);
