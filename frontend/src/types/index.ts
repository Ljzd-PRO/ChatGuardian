export type MatcherType = "all" | "sender" | "mention" | "chat" | "chat_type" | "adapter" | "and" | "or" | "not"

export interface MatchAll { type: "all" }
export interface MatchSender { type: "sender"; user_id?: string | null; display_name?: string | null }
export interface MatchMention { type: "mention"; user_id?: string | null; display_name?: string | null }
export interface MatchChatInfo { type: "chat"; chat_id: string }
export interface MatchChatType { type: "chat_type"; chat_type: "group" | "private" }
export interface MatchAdapter { type: "adapter"; adapter_name: string }
export interface AndMatcher { type: "and"; matchers: MatcherUnion[] }
export interface OrMatcher { type: "or"; matchers: MatcherUnion[] }
export interface NotMatcher { type: "not"; matcher: MatcherUnion }
export type MatcherUnion = MatchAll | MatchSender | MatchMention | MatchChatInfo | MatchChatType | MatchAdapter | AndMatcher | OrMatcher | NotMatcher

export interface RuleParameterSpec { key: string; description: string; required: boolean }
export interface DetectionRule {
  rule_id: string
  name: string
  description: string
  matcher: MatcherUnion
  topic_hints: string[]
  score_threshold: number
  enabled: boolean
  parameters: RuleParameterSpec[]
}

export interface AdapterStatus {
  name: string
  running: boolean
}

export interface HealthResponse {
  status: string
  time: string
}

export interface LLMInfo {
  backend: string
  model: string
  api_key_configured: boolean
  client_class: string
}

export interface SchedulerMetrics {
  total_requests: number
  total_batches: number
  total_llm_calls: number
  successful_batches: number
  fallback_batches: number
  retry_attempts: number
  idempotency_completed_hits: number
}

export interface SchedulerInfo {
  max_parallel_batches: number
  metrics: SchedulerMetrics
}

export interface LLMHealthResponse {
  status: string
  time: string
  llm: LLMInfo
  scheduler: SchedulerInfo
}

export interface TriggerRecord {
  id: string
  trigger_time: string
  confidence: number
  result: string
  rule_name: string
  messages: { sender: string; content: string }[]
  reason: string
}

export interface RuleStats {
  count: number
  description: string
  records: TriggerRecord[]
}

export interface StatsResponse {
  stats: Record<string, number>
  data: Record<string, RuleStats>
}

export interface QueueMessage {
  adapter: string
  chat_type: string
  chat_id: string
  sender_name: string
  content: string
  timestamp: string
}

export interface QueuesResponse {
  pending: QueueMessage[]
  history: QueueMessage[]
}
