import { apiFetch } from './client';

export interface QueueMessage {
  adapter: string;
  chat_type: string;
  chat_id: string;
  platform: string;
  message_id: string;
  sender_name: string;
  content: string;
  timestamp: string;
}

export interface HistoryMessageKey {
  adapter: string;
  chat_type: string;
  chat_id: string;
  platform: string;
  message_id: string;
}

export interface QueuesData { pending: QueueMessage[]; history: QueueMessage[] }

export const fetchQueues = () => apiFetch<QueuesData>('/api/queues');

export const deleteHistoryMessages = (items: HistoryMessageKey[]) =>
  apiFetch<{ deleted: number }>('/api/queues/history', {
    method: 'DELETE',
    body: JSON.stringify({ items }),
  });

export const clearHistoryMessages = () =>
  apiFetch<{ cleared: number }>('/api/queues/history', {
    method: 'DELETE',
    body: JSON.stringify({ clear_all: true }),
  });
