import { apiFetch } from './client';

export interface DashboardData {
  total_rules: number;
  enabled_rules: number;
  triggers_today: number;
  trigger_rate: number;
  messages_today: number;
  llm_status: Record<string, unknown>;
}

export const fetchDashboard = () => apiFetch<DashboardData>('/api/dashboard');
