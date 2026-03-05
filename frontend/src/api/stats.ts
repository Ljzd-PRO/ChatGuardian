import { apiFetch } from './client';

export interface RuleRecord {
  id: string;
  trigger_time: string;
  confidence: number;
  result: string;
  rule_name: string;
  messages: { sender: string; content: string }[];
  reason: string;
}

export interface RuleStat {
  count: number;
  description: string;
  records: RuleRecord[];
}

export interface RuleStatsData { stats: string; data: Record<string, RuleStat> }

export const fetchRuleStats = () => apiFetch<RuleStatsData>('/api/rule_stats');
