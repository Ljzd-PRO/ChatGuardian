// Domain types matching Python backend

export type MatcherType =
  | 'and' | 'or' | 'not' | 'all'
  | 'sender' | 'mention' | 'chat' | 'chat_type' | 'adapter';

export interface AndMatcher { type: 'and'; matchers: MatcherUnion[] }
export interface OrMatcher  { type: 'or';  matchers: MatcherUnion[] }
export interface NotMatcher { type: 'not'; matcher: MatcherUnion }
export interface MatchAll   { type: 'all' }
export interface MatchSender  { type: 'sender';    user_id?: string; display_name?: string }
export interface MatchMention { type: 'mention';   user_id?: string; display_name?: string }
export interface MatchChatInfo { type: 'chat';     chat_id: string }
export interface MatchChatType { type: 'chat_type'; chat_type: 'group' | 'private' }
export interface MatchAdapter  { type: 'adapter';  adapter_name: string }

export type MatcherUnion =
  | AndMatcher | OrMatcher | NotMatcher | MatchAll
  | MatchSender | MatchMention | MatchChatInfo | MatchChatType | MatchAdapter;

export interface RuleParameterSpec {
  key: string;
  description: string;
  required: boolean;
}

export interface DetectionRule {
  rule_id: string;
  name: string;
  description: string;
  matcher: MatcherUnion;
  topic_hints: string[];
  score_threshold: number;
  enabled: boolean;
  parameters: RuleParameterSpec[];
}
