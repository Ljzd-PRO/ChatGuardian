import { apiFetch } from './client';

export interface QueueMessage {
  adapter: string;
  chat_type: string;
  chat_id: string;
  sender_name: string;
  content: string;
  timestamp: string;
}
export interface QueuesData { pending: QueueMessage[]; history: QueueMessage[] }

export const fetchQueues = () => apiFetch<QueuesData>('/api/queues');
