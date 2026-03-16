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

export const deleteProfileInterest = (userId: string, topic: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/interests/${encodeURIComponent(topic)}`,
    { method: 'DELETE' },
  );

export const deleteProfileInterestChat = (userId: string, topic: string, chatId: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/interests/${encodeURIComponent(topic)}/related_chat/${encodeURIComponent(chatId)}`,
    { method: 'DELETE' },
  );

export const deleteProfileInterestKeyword = (userId: string, topic: string, keyword: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/interests/${encodeURIComponent(topic)}/keywords/${encodeURIComponent(keyword)}`,
    { method: 'DELETE' },
  );

export const deleteProfileActiveGroup = (userId: string, groupId: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/active_groups/${encodeURIComponent(groupId)}`,
    { method: 'DELETE' },
  );

export const deleteProfileContact = (userId: string, contactId: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/frequent_contacts/${encodeURIComponent(contactId)}`,
    { method: 'DELETE' },
  );

export const deleteProfileContactTopic = (userId: string, contactId: string, topic: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/frequent_contacts/${encodeURIComponent(contactId)}/related_topics/${encodeURIComponent(topic)}`,
    { method: 'DELETE' },
  );

export const deleteProfileContactGroup = (userId: string, contactId: string, groupId: string) =>
  apiFetch<UserProfile>(
    `/api/user_profiles/${encodeURIComponent(userId)}/frequent_contacts/${encodeURIComponent(contactId)}/related_groups/${encodeURIComponent(groupId)}`,
    { method: 'DELETE' },
  );

