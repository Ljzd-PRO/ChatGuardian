import { apiFetch } from './client';

export interface InterestTopicStat { topic: string; score: number; mention_count: number }
export interface ActiveGroupStat   { chat_id: string; chat_name?: string; message_count: number }
export interface FrequentContactStat { user_id: string; display_name?: string; interaction_count: number }

export interface UserProfile {
  user_id: string;
  user_name: string;
  interests: Record<string, InterestTopicStat>;
  active_groups: ActiveGroupStat[];
  frequent_contacts: Record<string, FrequentContactStat>;
}

export const fetchUserProfiles = () => apiFetch<UserProfile[]>('/api/user_profiles');
export const fetchUserProfile  = (userId: string) => apiFetch<UserProfile>(`/api/user_profiles/${userId}`);
