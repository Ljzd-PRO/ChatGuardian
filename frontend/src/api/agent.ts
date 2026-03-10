import { getToken } from './client';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/';

export interface AgentEvent {
  type: 'token' | 'tool_call_start' | 'tool_call_args' | 'tool_result' | 'error' | 'done';
  content?: string;
  tool_call_id?: string;
  name?: string;
  display_name?: string;
  args_delta?: string;
  result?: unknown;
}

export interface AgentMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolDisplayNames {
  [toolName: string]: {
    en: string;
    zh: string;
  };
}

export interface AgentCapability {
  category: string;
  items: string[];
}

export interface AgentCapabilitiesResponse {
  tool_display_names: ToolDisplayNames;
  capabilities: AgentCapability[];
}

export async function streamAgentChat(
  messages: AgentMessage[],
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  const url = `${normalizedBase}/api/agent/chat`;
  const token = getToken();

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data: ')) continue;
      const jsonStr = trimmed.slice(6);
      try {
        const event: AgentEvent = JSON.parse(jsonStr);
        onEvent(event);
      } catch {
        // skip unparseable lines
      }
    }
  }

  // Process any remaining data in buffer
  if (buffer.trim()) {
    const trimmed = buffer.trim();
    if (trimmed.startsWith('data: ')) {
      try {
        const event: AgentEvent = JSON.parse(trimmed.slice(6));
        onEvent(event);
      } catch {
        // skip
      }
    }
  }
}

export async function fetchAgentCapabilities(): Promise<AgentCapabilitiesResponse> {
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  const url = `${normalizedBase}/api/agent/capabilities`;
  const token = getToken();

  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json();
}
