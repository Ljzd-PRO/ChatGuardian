import { apiFetch } from './client';
import type { DetectionRule } from './types';

export const fetchRules = () => apiFetch<DetectionRule[]>('/rules/list');

export const upsertRule = (rule: DetectionRule) =>
  apiFetch<DetectionRule>('/rules', { method: 'POST', body: JSON.stringify(rule) });

export const deleteRule = (ruleId: string) =>
  apiFetch<{ status: string }>(`/rules/delete/${ruleId}`, { method: 'POST' });
