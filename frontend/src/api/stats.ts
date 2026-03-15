import { apiFetch } from './client';

export interface RuleRecord {
  id: string;
  result_id?: string;
  event_id?: string;
  rule_id?: string;
  adapter?: string;
  chat_type?: string;
  chat_id?: string;
  message_id?: string;
  trigger_time: string;
  confidence: number;
  result: string;
  rule_name: string;
  trigger_suppressed?: boolean;
  suppression_reason?: string | null;
  messages: { sender: string; content: string }[];
  extracted_params?: Record<string, string>;
  reason: string;
}

export interface RuleStat {
  count: number;
  description: string;
  records: RuleRecord[];
}

export interface RuleStatsData { stats: string; data: Record<string, RuleStat> }

export interface RuleStatDetail {
  rule_id: string;
  rule_name: string;
  description: string;
  count: number;
  records: RuleRecord[];
}

export const fetchRuleStats = () => apiFetch<RuleStatsData>('/api/rule_stats');
export const fetchRuleStat = (ruleId: string) =>
  apiFetch<RuleStatDetail>(`/api/rule_stats/${encodeURIComponent(ruleId)}`);
export const deleteRuleRecords = (ruleId: string, recordIds?: string[]) =>
  apiFetch<{ deleted: number }>(`/api/rule_stats/${encodeURIComponent(ruleId)}/records`, {
    method: 'DELETE',
    body: JSON.stringify({ record_ids: recordIds ?? null }),
  });
