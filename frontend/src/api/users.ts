import { apiFetch } from './client';

export interface RelatedTopicStat {
  score: number;
  last_talk: string;
}

export interface InterestTopicStat {
  score: number;
  last_active: string;
  related_chat: string[];
  keywords: string[];
}

export interface ActiveGroupStat {
  group_id: string;
  frequency: number;
  last_talk: string;
}

export interface FrequentContactStat {
  name: string;
  interaction_count: number;
  last_interact: string;
  related_topics: Record<string, RelatedTopicStat>;
  related_groups: string[];
}

export interface UserProfile {
  user_id: string;
  user_name: string;
  interests: Record<string, InterestTopicStat>;
  active_groups: ActiveGroupStat[];
  frequent_contacts: Record<string, FrequentContactStat>;
}

export const fetchUserProfiles = () => apiFetch<UserProfile[]>('/api/user_profiles');
export const fetchUserProfile  = (userId: string) => apiFetch<UserProfile>(`/api/user_profiles/${encodeURIComponent(userId)}`);
export const deleteUserProfile = (userId: string) =>
  apiFetch<{ status: string; user_id: string }>(`/api/user_profiles/${encodeURIComponent(userId)}`, { method: 'DELETE' });
