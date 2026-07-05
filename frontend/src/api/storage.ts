import { apiFetch } from './client';

export interface StorageTableStats {
  rows: number;
  payload_bytes: number;
}

export interface StorageStats {
  database_file_bytes: number | null;
  database_path: string;
  last_storage_prune_at: string | null;
  tables: Record<string, StorageTableStats>;
}

export interface StorageMaintenanceResult {
  history?: Record<string, number>;
  detection?: Record<string, number>;
  last_storage_prune_at?: string | null;
  before_bytes?: number | null;
  after_bytes?: number | null;
  compacted?: boolean;
}

export const fetchStorageStats = () => apiFetch<StorageStats>('/api/storage/stats');

export const pruneStorage = () =>
  apiFetch<StorageMaintenanceResult>('/api/storage/prune', { method: 'POST' });

export const compactStorage = () =>
  apiFetch<StorageMaintenanceResult>('/api/storage/compact', { method: 'POST' });
