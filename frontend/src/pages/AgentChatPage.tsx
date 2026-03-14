import { useState, useRef, useEffect, useCallback, useMemo, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  CardBody,
  Chip,
  Spinner,
  Textarea,
  ScrollShadow,
  Tooltip,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
  Divider,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import paperPlaneBold from '@iconify/icons-solar/map-arrow-up-bold';
import restartBold from '@iconify/icons-solar/restart-bold';
import widgetBold from '@iconify/icons-solar/widget-2-bold';
import settingsBold from '@iconify/icons-solar/settings-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import chartBold from '@iconify/icons-solar/chart-2-bold';
import documentTextBold from '@iconify/icons-solar/document-text-bold';
import usersGroupBold from '@iconify/icons-solar/users-group-rounded-bold';
import bellBold from '@iconify/icons-solar/bell-bing-bold';
import cpuBold from '@iconify/icons-solar/cpu-bolt-bold';
import plugBold from '@iconify/icons-solar/plug-circle-bold';
import listBold from '@iconify/icons-solar/list-check-bold';
import healthBold from '@iconify/icons-solar/health-bold';
import eraserBold from '@iconify/icons-solar/eraser-bold';
import clockBold from '@iconify/icons-solar/clock-circle-bold';
import stopBold from '@iconify/icons-solar/stop-bold';
import copyBold from '@iconify/icons-solar/copy-bold';
import trashBold from '@iconify/icons-solar/trash-bin-trash-bold';
import chatBold from '@iconify/icons-solar/chat-round-dots-bold';
import addBold from '@iconify/icons-solar/add-circle-bold';
import menuBold from '@iconify/icons-solar/hamburger-menu-bold';
import penBold from '@iconify/icons-solar/pen-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import closeCircleBold from '@iconify/icons-solar/close-circle-bold';
import arrowDownBold from '@iconify/icons-solar/alt-arrow-down-bold';
import arrowRightBold from '@iconify/icons-solar/alt-arrow-right-bold';
import sparklesLinear from '@iconify/icons-solar/stars-line-duotone';
import keyboardBold from '@iconify/icons-solar/keyboard-bold';

import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import {
  streamAgentChat,
  fetchAgentCapabilities,
  fetchAgentSessions,
  createAgentSession,
  deleteAgentSession,
  updateAgentSessionTitle,
  fetchSessionMessages,
  saveSessionMessage,
  deleteMessagePair,
  type AgentEvent,
  type AgentMessage,
  type AgentSession,
  type AgentSessionMessage,
} from '../api/agent';

const messageKeyMap = new WeakMap<AgentMessage, string>();

function getMessageKey(msg: AgentMessage, idx: number): string {
  const existing = messageKeyMap.get(msg);
  if (existing) {
    return existing;
  }

  let key: string;
  if (msg.dbId != null) {
    key = String(msg.dbId);
  } else if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    key = `tmp-${crypto.randomUUID()}`;
  } else {
    key = `tmp-${idx}`;
  }

  messageKeyMap.set(msg, key);
  return key;
}

/* ─── Constants ─────────────────────────────────────────────────────── */

const MAX_TOOL_RESULT_LENGTH = 2000;

/* ─── Types ────────────────────────────────────────────────────────── */

interface ToolCallInfo {
  id: string;
  name: string;
  displayName: string;
  args: string;
  result?: unknown;
  isLoading: boolean;
}

interface StoredToolCall {
  id?: string;
  name?: string;
  displayName?: string;
  display_name?: string;
  args?: string;
  result?: unknown;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
  elapsedMs?: number;
  dbId?: number;
}

/* ─── Markdown components ───────────────────────────────────────────── */

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h2 className="font-bold text-foreground text-lg mt-4 mb-2 leading-tight">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="font-bold text-foreground text-base mt-3 mb-1.5 leading-tight">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="font-semibold text-foreground text-sm mt-3 mb-1 leading-tight">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="text-foreground/85 text-sm my-1.5 leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-outside ml-4 space-y-1 my-2 text-foreground/85 text-sm">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside ml-4 space-y-1 my-2 text-foreground/85 text-sm">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-foreground/85 text-sm leading-relaxed">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-foreground/80">{children}</em>
  ),
  code: ({ className, children }) => (
    <code className={`bg-primary/10 text-primary px-1.5 py-0.5 rounded-md text-xs font-mono ${className ?? ''}`}>
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="bg-default-100 dark:bg-default-50/10 border border-divider rounded-xl p-4 my-3 overflow-x-auto text-xs font-mono text-foreground/90 leading-relaxed [&_code]:bg-transparent [&_code]:text-foreground/90 [&_code]:px-0 [&_code]:py-0 [&_code]:rounded-none shadow-inner">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-divider">
      <table className="min-w-full border-collapse text-sm">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-default-100 dark:bg-default-50/10">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border-b border-divider px-4 py-2.5 text-left font-semibold text-foreground text-xs tracking-wide">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-divider px-4 py-2.5 text-foreground/80 text-xs last:border-b-0">
      {children}
    </td>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className="text-primary hover:text-primary/80 underline underline-offset-2 decoration-primary/40 hover:decoration-primary/80 transition-colors">
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-primary/40 pl-4 my-3 text-foreground/60 italic bg-default-100/50 dark:bg-default-50/5 rounded-r-lg py-2 pr-3">
      {children}
    </blockquote>
  ),
  hr: () => <Divider className="my-4" />,
};

function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
  );
}

/* ─── Typing indicator ──────────────────────────────────────────────── */

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-foreground/30 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.9s' }}
        />
      ))}
    </div>
  );
}

/* ─── Copy button ──────────────────────────────────────────────────── */

function CopyButton({ text, t }: { text: string; t: (key: string) => string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [text]);

  return (
    <Tooltip content={copied ? t('agent.copied') : t('agent.copy')} placement="left">
      <button
        type="button"
        onClick={handleCopy}
        className={`p-1.5 rounded-lg transition-all duration-200 ${
          copied
            ? 'bg-success/20 text-success'
            : 'hover:bg-content3 text-foreground/40 hover:text-foreground/70'
        }`}
        aria-label={t('agent.copy')}
      >
        <Icon icon={copied ? checkCircleBold : copyBold} fontSize={14} />
      </button>
    </Tooltip>
  );
}

/* ─── Tool call card ────────────────────────────────────────────────── */

function ToolCallCard({ toolCall }: { toolCall: ToolCallInfo }) {
  const [expanded, setExpanded] = useState(false);
  const { t } = useTranslation();

  const resultStr =
    toolCall.result != null
      ? typeof toolCall.result === 'string'
        ? toolCall.result
        : JSON.stringify(toolCall.result, null, 2)
      : '';

  const isError =
    typeof toolCall.result === 'object' &&
    toolCall.result !== null &&
    'error' in (toolCall.result as Record<string, unknown>);

  return (
    <div className="my-2 rounded-xl border border-divider overflow-hidden shadow-sm">
      <button
        type="button"
        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-left bg-default-50/80 dark:bg-default-100/20 hover:bg-default-100/80 dark:hover:bg-default-100/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-shrink-0">
          {toolCall.isLoading ? (
            <Spinner size="sm" className="w-4 h-4" color="primary" />
          ) : isError ? (
            <Icon icon={closeCircleBold} className="text-danger" fontSize={16} />
          ) : (
            <Icon icon={checkCircleBold} className="text-success" fontSize={16} />
          )}
        </div>
        <span className="text-sm font-medium text-foreground flex-1 truncate">
          {toolCall.displayName}
        </span>
        <Icon
          icon={expanded ? arrowDownBold : arrowRightBold}
          className="text-foreground/40 flex-shrink-0 transition-transform duration-200"
          fontSize={14}
        />
      </button>
      {expanded && (
        <div className="px-3.5 py-3 bg-default-50/50 dark:bg-default-50/5 border-t border-divider space-y-3">
          {toolCall.args && (
            <div>
              <p className="text-xs font-medium text-foreground/50 mb-1.5">{t('agent.toolArgs')}</p>
              <pre className="text-xs bg-default-100 dark:bg-default-50/10 border border-divider rounded-lg p-3 overflow-x-auto font-mono text-foreground/75 leading-relaxed">
                {(() => {
                  try { return JSON.stringify(JSON.parse(toolCall.args), null, 2); }
                  catch { return toolCall.args; }
                })()}
              </pre>
            </div>
          )}
          {resultStr && (
            <div>
              <p className="text-xs font-medium text-foreground/50 mb-1.5">{t('agent.toolResult')}</p>
              <pre className={`text-xs border rounded-lg p-3 overflow-x-auto max-h-52 font-mono leading-relaxed ${
                isError
                  ? 'bg-danger/5 border-danger/20 text-danger/80'
                  : 'bg-default-100 dark:bg-default-50/10 border-divider text-foreground/75'
              }`}>
                {resultStr.length > MAX_TOOL_RESULT_LENGTH ? resultStr.slice(0, MAX_TOOL_RESULT_LENGTH) + '\n…(truncated)' : resultStr}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Capability icons map ──────────────────────────────────────────── */

const CAPABILITY_ICONS: Record<string, typeof widgetBold> = {
  get_dashboard: widgetBold,
  get_rules_list: shieldCheckBold,
  get_rule_stats: chartBold,
  get_adapters_status: plugBold,
  get_queues: listBold,
  get_system_logs: documentTextBold,
  get_user_profiles: usersGroupBold,
  get_user_profile: usersGroupBold,
  get_settings: settingsBold,
  get_notifications_config: bellBold,
  get_llm_config: cpuBold,
  check_llm_health: healthBold,
  check_system_health: healthBold,
  create_or_update_rule: shieldCheckBold,
  delete_rule: shieldCheckBold,
  start_adapters: plugBold,
  stop_adapters: plugBold,
  update_settings: settingsBold,
  clear_message_history: eraserBold,
  clear_system_logs: eraserBold,
};

/* ─── Elapsed time formatting ──────────────────────────────────────── */

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m ${secs.toFixed(0)}s`;
}

/* ─── Session sidebar ──────────────────────────────────────────────── */

function SessionSidebar({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  isLoading,
  isStreaming,
  t,
}: {
  sessions: AgentSession[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  isLoading: boolean;
  isStreaming: boolean;
  t: (key: string) => string;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const startRename = (session: AgentSession) => {
    setEditingId(session.session_id);
    setEditTitle(session.title || t('agent.untitledSession'));
  };

  const commitRename = () => {
    if (editingId && editTitle.trim()) {
      onRenameSession(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-divider flex-shrink-0">
        <div className="flex items-center gap-2 px-1 mb-3">
          <Icon icon={chatBold} className="text-primary" fontSize={16} />
          <span className="text-sm font-semibold text-foreground">{t('agent.sessions')}</span>
        </div>
        <Button
          color="primary"
          variant="flat"
          size="sm"
          className="w-full font-medium"
          startContent={<Icon icon={addBold} fontSize={16} />}
          onPress={onNewSession}
          isDisabled={isStreaming}
        >
          {t('agent.newSession')}
        </Button>
      </div>

      {/* Session list */}
      <ScrollShadow className="flex-1 min-h-0 overflow-y-auto">
        {isLoading ? (
          <div className="flex justify-center items-center py-12">
            <Spinner size="sm" color="primary" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 gap-2">
            <Icon icon={chatBold} className="text-foreground/20" fontSize={32} />
            <p className="text-center text-foreground/40 text-xs">{t('agent.noSessions')}</p>
          </div>
        ) : (
          <div className="p-2 space-y-0.5">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                className={`group flex items-center gap-1.5 px-3 py-2.5 rounded-xl transition-all duration-150 ${
                  isStreaming
                    ? 'cursor-not-allowed opacity-60'
                    : 'cursor-pointer'
                } ${
                  currentSessionId === session.session_id
                    ? 'bg-primary/15 text-primary shadow-sm'
                    : isStreaming
                      ? 'text-foreground'
                      : 'hover:bg-default-100/80 text-foreground/80 hover:text-foreground'
                }`}
                onClick={() => { if (!isStreaming) onSelectSession(session.session_id); }}
              >
                <Icon
                  icon={chatBold}
                  fontSize={13}
                  className={`flex-shrink-0 ${
                    currentSessionId === session.session_id ? 'text-primary' : 'opacity-40'
                  }`}
                />
                {editingId === session.session_id ? (
                  <input
                    className="flex-1 min-w-0 text-xs bg-content1 border border-primary/40 rounded-lg px-2 py-1 text-foreground outline-none focus:ring-1 focus:ring-primary/40"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitRename();
                      if (e.key === 'Escape') setEditingId(null);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                  />
                ) : (
                  <span className="flex-1 min-w-0 text-xs truncate font-medium">
                    {session.title || t('agent.untitledSession')}
                  </span>
                )}
                {!isStreaming && (
                  <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                    <button
                      type="button"
                      className="p-1 rounded-lg hover:bg-content3 transition-colors text-foreground/40 hover:text-foreground"
                      onClick={(e) => { e.stopPropagation(); startRename(session); }}
                      aria-label={t('agent.rename')}
                    >
                      <Icon icon={penBold} fontSize={11} />
                    </button>
                    <button
                      type="button"
                      className="p-1 rounded-lg hover:bg-danger/15 transition-colors text-foreground/40 hover:text-danger"
                      onClick={(e) => { e.stopPropagation(); onDeleteSession(session.session_id); }}
                      aria-label={t('agent.deleteSession')}
                    >
                      <Icon icon={trashBold} fontSize={11} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollShadow>
    </div>
  );
}

/* ─── Main component ───────────────────────────────────────────────── */

export default function AgentChatPage() {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language.startsWith('zh');
  const queryClient = useQueryClient();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const pendingMsgRef = useRef<ChatMessage | null>(null);
  const rafIdRef = useRef<number>(0);
  const streamStartRef = useRef<number>(0);
  // When a new session is created programmatically (first message), we skip the
  // automatic message re-fetch triggered by the currentSessionId effect to avoid
  // a race condition where the effect's fetch returns [] before messages are saved.
  const skipNextSessionLoadRef = useRef(false);

  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<{ sessionId: string; userMsgId: number } | null>(null);

  const { data: capabilities } = useQuery({
    queryKey: ['agent-capabilities'],
    queryFn: fetchAgentCapabilities,
    staleTime: 60_000,
  });

  const { data: sessions = [], isLoading: sessionsLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: fetchAgentSessions,
    staleTime: 10_000,
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    const onBeforeUnload = () => { abortRef.current?.abort(); };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload);
      abortRef.current?.abort();
    };
  }, []);

  /* ─── Load session messages when session changes ─────────────────── */
  useEffect(() => {
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    if (skipNextSessionLoadRef.current) {
      skipNextSessionLoadRef.current = false;
      return;
    }
    let cancelled = false;
    fetchSessionMessages(currentSessionId).then((msgs) => {
      if (cancelled) return;
      const chatMsgs: ChatMessage[] = msgs.map((m: AgentSessionMessage) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        toolCalls: ((m.tool_calls ?? []) as StoredToolCall[]).map((tc) => ({
          id: tc.id ?? '',
          name: tc.name ?? '',
          displayName: tc.displayName ?? tc.display_name ?? tc.name ?? '',
          args: tc.args ?? '',
          result: tc.result,
          isLoading: false,
        })),
        elapsedMs: m.elapsed_ms ?? undefined,
        dbId: m.id,
      }));
      setMessages(chatMsgs);
    }).catch(() => {
      if (!cancelled) setMessages([]);
    });
    return () => { cancelled = true; };
  }, [currentSessionId]);

  const scheduleFlush = useCallback(() => {
    if (rafIdRef.current) return;
    rafIdRef.current = requestAnimationFrame(() => {
      rafIdRef.current = 0;
      const msg = pendingMsgRef.current;
      if (!msg) return;
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { ...msg, toolCalls: [...(msg.toolCalls ?? [])] };
        return updated;
      });
    });
  }, []);

  const suggestedPrompts = useMemo(() => [
    t('agent.prompts.dashboard'),
    t('agent.prompts.listRules'),
    t('agent.prompts.llmHealth'),
    t('agent.prompts.adapters'),
    t('agent.prompts.createRule'),
    t('agent.prompts.viewLogs'),
  ], [t]);

  const handleNewSession = useCallback(async () => {
    const session = await createAgentSession();
    queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
    setCurrentSessionId(session.session_id);
    setMessages([]);
    setSidebarOpen(false);
  }, [queryClient]);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    await deleteAgentSession(sessionId);
    queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
    if (currentSessionId === sessionId) {
      setCurrentSessionId(null);
      setMessages([]);
    }
  }, [currentSessionId, queryClient]);

  const handleRenameSession = useCallback(async (sessionId: string, title: string) => {
    await updateAgentSessionTitle(sessionId, title);
    queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
  }, [queryClient]);

  const handleDeletePair = useCallback(async () => {
    if (!deleteTarget) return;
    await deleteMessagePair(deleteTarget.sessionId, deleteTarget.userMsgId);
    if (currentSessionId) {
      const msgs = await fetchSessionMessages(currentSessionId);
      const chatMsgs: ChatMessage[] = msgs.map((m: AgentSessionMessage) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        toolCalls: ((m.tool_calls ?? []) as StoredToolCall[]).map((tc) => ({
          id: tc.id ?? '',
          name: tc.name ?? '',
          displayName: tc.displayName ?? tc.display_name ?? tc.name ?? '',
          args: tc.args ?? '',
          result: tc.result,
          isLoading: false,
        })),
        elapsedMs: m.elapsed_ms ?? undefined,
        dbId: m.id,
      }));
      setMessages(chatMsgs);
    }
    setDeleteTarget(null);
    onDeleteClose();
  }, [deleteTarget, currentSessionId, onDeleteClose]);

  const handleSubmit = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || isStreaming) return;

      let sessionId = currentSessionId;
      if (!sessionId) {
        const session = await createAgentSession(content.slice(0, 50));
        sessionId = session.session_id;
        skipNextSessionLoadRef.current = true;
        setCurrentSessionId(sessionId);
        queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
      }

      const userMsg: ChatMessage = { role: 'user', content };
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);
      setInput('');
      setIsStreaming(true);
      streamStartRef.current = Date.now();

      let userMsgDb: AgentSessionMessage | null = null;
      try {
        userMsgDb = await saveSessionMessage(sessionId, 'user', content);
      } catch { /* ignore */ }

      if (userMsgDb) {
        userMsg.dbId = userMsgDb.id;
      }

      const apiMessages: AgentMessage[] = newMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: '',
        toolCalls: [],
      };
      pendingMsgRef.current = assistantMsg;

      setMessages([...newMessages, assistantMsg]);

      const abort = new AbortController();
      abortRef.current = abort;

      const toolCallsMap: Record<string, ToolCallInfo> = {};

      try {
        await streamAgentChat(
          apiMessages,
          (event: AgentEvent) => {
            const msg = pendingMsgRef.current;
            if (!msg) return;

            switch (event.type) {
              case 'token':
                msg.content += event.content ?? '';
                break;

              case 'tool_call_start': {
                const tcId = event.tool_call_id ?? '';
                const tc: ToolCallInfo = {
                  id: tcId,
                  name: event.name ?? '',
                  displayName: event.display_name ?? event.name ?? '',
                  args: '',
                  isLoading: true,
                };
                toolCallsMap[tcId] = tc;
                msg.toolCalls = [
                  ...(msg.toolCalls ?? []).filter((t) => t.id !== tcId),
                  tc,
                ];
                break;
              }

              case 'tool_call_args': {
                const tcId = event.tool_call_id ?? '';
                if (toolCallsMap[tcId]) {
                  toolCallsMap[tcId].args += event.args_delta ?? '';
                  msg.toolCalls = (msg.toolCalls ?? []).map((t) =>
                    t.id === tcId ? { ...toolCallsMap[tcId] } : t,
                  );
                }
                break;
              }

              case 'tool_result': {
                const tcId = event.tool_call_id ?? '';
                if (toolCallsMap[tcId]) {
                  toolCallsMap[tcId].result = event.result;
                  toolCallsMap[tcId].isLoading = false;
                  msg.toolCalls = (msg.toolCalls ?? []).map((t) =>
                    t.id === tcId
                      ? { ...toolCallsMap[tcId], result: event.result, isLoading: false }
                      : t,
                  );
                } else {
                  msg.toolCalls = [
                    ...(msg.toolCalls ?? []),
                    {
                      id: tcId,
                      name: event.name ?? '',
                      displayName: event.display_name ?? event.name ?? '',
                      args: '',
                      result: event.result,
                      isLoading: false,
                    },
                  ];
                }
                break;
              }

              case 'error':
                msg.content += `\n\n❌ ${event.content ?? 'Unknown error'}`;
                break;

              case 'done':
                break;
            }

            scheduleFlush();
          },
          abort.signal,
          sessionId ?? undefined,
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          const msg = pendingMsgRef.current;
          if (msg) {
            msg.content += `\n\n❌ ${err instanceof Error ? err.message : 'Unknown error'}`;
          }
        }
      } finally {
        if (rafIdRef.current) {
          cancelAnimationFrame(rafIdRef.current);
          rafIdRef.current = 0;
        }

        const elapsed = Date.now() - streamStartRef.current;
        const msg = pendingMsgRef.current;
        if (msg) {
          msg.elapsedMs = elapsed;
        }
        pendingMsgRef.current = null;

        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = { ...last, ...(msg ?? {}), elapsedMs: elapsed };
          }
          return updated;
        });
        setIsStreaming(false);
        abortRef.current = null;

        if (sessionId && msg) {
          const tcForDb = (msg.toolCalls ?? []).map((tc) => ({
            id: tc.id,
            name: tc.name,
            displayName: tc.displayName,
            display_name: tc.displayName,
            args: tc.args,
            result: tc.result,
          }));
          saveSessionMessage(sessionId, 'assistant', msg.content, tcForDb, elapsed).then((saved) => {
            if (saved?.id) {
              setMessages((prev) => {
                const updated = [...prev];
                const lastIdx = updated.length - 1;
                if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
                  updated[lastIdx] = { ...updated[lastIdx], dbId: saved.id };
                }
                return updated;
              });
            }
          }).catch(() => {});

          if (messages.length === 0) {
            updateAgentSessionTitle(sessionId, content.slice(0, 50)).then(() => {
              queryClient.invalidateQueries({ queryKey: ['agent-sessions'] });
            }).catch(() => {});
          }
        }
      }
    },
    [input, isStreaming, messages, scheduleFlush, currentSessionId, queryClient],
  );

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleReset = () => {
    abortRef.current?.abort();
    setCurrentSessionId(null);
    setMessages([]);
    setIsStreaming(false);
  };

  const handlePromptClick = (prompt: string) => {
    handleSubmit(prompt);
  };

  const requestDeletePair = (sessionId: string, userMsgId: number) => {
    setDeleteTarget({ sessionId, userMsgId });
    onDeleteOpen();
  };

  const showEmptyState = messages.length === 0;

  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  return (
    <div className="flex h-full gap-0 rounded-xl overflow-hidden border border-divider shadow-sm bg-background">
      {/* ── Sidebar (desktop) ── */}
      {!isMobile && (
        <aside className="w-60 flex-shrink-0 border-r border-divider bg-content1/60 backdrop-blur-sm">
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelectSession={(id) => { setCurrentSessionId(id); }}
            onNewSession={handleNewSession}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
            isLoading={sessionsLoading}
            isStreaming={isStreaming}
            t={t}
          />
        </aside>
      )}

      {/* ── Sidebar (mobile modal) ── */}
      {isMobile && (
        <Modal isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} placement="center" size="sm" scrollBehavior="inside">
          <ModalContent>
            <ModalHeader className="pb-1 text-sm font-semibold">{t('agent.sessions')}</ModalHeader>
            <ModalBody className="p-0 min-h-[50vh]">
              <SessionSidebar
                sessions={sessions}
                currentSessionId={currentSessionId}
                onSelectSession={(id) => { setCurrentSessionId(id); setSidebarOpen(false); }}
                onNewSession={() => { handleNewSession(); setSidebarOpen(false); }}
                onDeleteSession={handleDeleteSession}
                onRenameSession={handleRenameSession}
                isLoading={sessionsLoading}
                isStreaming={isStreaming}
                t={t}
              />
            </ModalBody>
          </ModalContent>
        </Modal>
      )}

      {/* ── Main chat area ── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {/* Mobile header */}
        {isMobile && (
          <div className="flex items-center gap-2 px-3 py-2.5 border-b border-divider bg-content1/50 flex-shrink-0">
            <Button
              isIconOnly
              variant="light"
              size="sm"
              onPress={() => setSidebarOpen(true)}
              aria-label={t('agent.sessions')}
            >
              <Icon icon={menuBold} fontSize={20} />
            </Button>
            <div className="flex items-center gap-1.5 flex-1">
              <Icon icon={cpuBold} className="text-primary" fontSize={16} />
              <span className="text-sm font-semibold text-foreground">{t('agent.title')}</span>
            </div>
            {isStreaming && <Spinner size="sm" color="primary" className="flex-shrink-0" />}
          </div>
        )}

        {/* Desktop header bar */}
        {!isMobile && (
          <div className="flex items-center justify-between px-5 py-3 border-b border-divider bg-content1/30 flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-primary/15 flex items-center justify-center">
                <Icon icon={cpuBold} className="text-primary" fontSize={15} />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground leading-none">{t('agent.title')}</p>
                {currentSessionId &&
                  (() => {
                    const currentSession = sessions.find(s => s.session_id === currentSessionId);
                    if (!currentSession) return null;
                    return (
                      <p className="text-xs text-foreground/40 mt-0.5 truncate max-w-xs">
                        {currentSession.title || t('agent.untitledSession')}
                      </p>
                    );
                  })()}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {isStreaming && (
                <div className="flex items-center gap-1.5 mr-1">
                  <Spinner size="sm" color="primary" />
                  <span className="text-xs text-foreground/50">{t('agent.thinking')}</span>
                </div>
              )}
              <Tooltip content={t('agent.reset')}>
                <Button
                  isIconOnly
                  variant="light"
                  size="sm"
                  onPress={handleReset}
                  aria-label={t('agent.reset')}
                  className="text-foreground/50 hover:text-foreground"
                >
                  <Icon icon={restartBold} fontSize={16} />
                </Button>
              </Tooltip>
            </div>
          </div>
        )}

        {/* ── Messages area ── */}
        <ScrollShadow
          className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4"
          hideScrollBar={false}
        >
          {showEmptyState ? (
            /* ── Empty / welcome state ── */
            <div className="flex flex-col items-center justify-center h-full min-h-[300px] gap-7 py-8">
              {/* Icon */}
              <div className="relative">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center shadow-md">
                  <Icon icon={sparklesLinear} className="text-primary" fontSize={32} />
                </div>
                <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-success/20 border-2 border-background flex items-center justify-center">
                  <Icon icon={cpuBold} className="text-success" fontSize={11} />
                </div>
              </div>

              {/* Title */}
              <div className="text-center space-y-2 max-w-sm">
                <h2 className="text-xl font-bold text-foreground">{t('agent.title')}</h2>
                <p className="text-sm text-foreground/50 leading-relaxed">{t('agent.description')}</p>
              </div>

              {/* Capabilities */}
              {capabilities && (
                <div className="w-full max-w-xl space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Card className="border border-divider shadow-none bg-content1/80">
                      <CardBody className="p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-6 h-6 rounded-lg bg-primary/10 flex items-center justify-center">
                            <Icon icon={chartBold} className="text-primary" fontSize={13} />
                          </div>
                          <h3 className="font-semibold text-xs text-foreground/70 uppercase tracking-wide">
                            {t('agent.capabilities.query')}
                          </h3>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {capabilities.capabilities
                            .find((c) => c.category === 'query')
                            ?.items.map((item) => {
                              const display = capabilities.tool_display_names[item];
                              const label = display ? (isZh ? display.zh : display.en) : item;
                              const icon = CAPABILITY_ICONS[item];
                              return (
                                <Chip
                                  key={item}
                                  size="sm"
                                  variant="flat"
                                  color="default"
                                  startContent={icon ? <Icon icon={icon} fontSize={11} className="text-foreground/50" /> : undefined}
                                  className="text-xs h-6"
                                >
                                  {label}
                                </Chip>
                              );
                            })}
                        </div>
                      </CardBody>
                    </Card>

                    <Card className="border border-divider shadow-none bg-content1/80">
                      <CardBody className="p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <div className="w-6 h-6 rounded-lg bg-secondary/10 flex items-center justify-center">
                            <Icon icon={settingsBold} className="text-secondary" fontSize={13} />
                          </div>
                          <h3 className="font-semibold text-xs text-foreground/70 uppercase tracking-wide">
                            {t('agent.capabilities.management')}
                          </h3>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {capabilities.capabilities
                            .find((c) => c.category === 'management')
                            ?.items.map((item) => {
                              const display = capabilities.tool_display_names[item];
                              const label = display ? (isZh ? display.zh : display.en) : item;
                              const icon = CAPABILITY_ICONS[item];
                              return (
                                <Chip
                                  key={item}
                                  size="sm"
                                  variant="flat"
                                  color="default"
                                  startContent={icon ? <Icon icon={icon} fontSize={11} className="text-foreground/50" /> : undefined}
                                  className="text-xs h-6"
                                >
                                  {label}
                                </Chip>
                              );
                            })}
                        </div>
                      </CardBody>
                    </Card>
                  </div>

                  {/* Suggested prompts */}
                  <div>
                    <p className="text-xs text-foreground/40 mb-2 font-medium">{t('agent.suggestedPrompts')}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {suggestedPrompts.map((prompt) => (
                        <button
                          type="button"
                          key={prompt}
                          onClick={() => handlePromptClick(prompt)}
                          className="text-left px-3.5 py-3 rounded-xl border border-divider
                            bg-content1/60 hover:bg-content2 hover:border-primary/30
                            text-sm text-foreground/65 hover:text-foreground/90
                            transition-all duration-150 cursor-pointer group"
                        >
                          <div className="flex items-start gap-2">
                            <Icon icon={sparklesLinear} className="text-primary/40 group-hover:text-primary/70 flex-shrink-0 mt-0.5 transition-colors" fontSize={14} />
                            <span className="text-xs leading-relaxed">{prompt}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* ── Message list ── */
            <div className="space-y-5 py-2">
              {messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                const isLast = idx === messages.length - 1;
                const showThinking =
                  !isUser &&
                  !msg.content &&
                  !msg.toolCalls?.length &&
                  isStreaming &&
                  isLast;

                const canDeletePair = isUser && msg.dbId != null && currentSessionId != null && !isStreaming;

                return (
                  <div
                    key={getMessageKey(msg, idx)}
                    className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    {/* AI avatar */}
                    {!isUser && (
                      <div className="flex-shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-secondary/20 to-primary/20 flex items-center justify-center shadow-sm border border-divider">
                          <Icon icon={cpuBold} className="text-secondary" fontSize={15} />
                        </div>
                      </div>
                    )}

                    <div className={`flex flex-col gap-1 ${isUser ? 'items-end max-w-[78%] sm:max-w-[70%]' : 'items-start max-w-[85%] sm:max-w-[80%]'}`}>
                      {/* Bubble */}
                      <div
                        className={`group relative rounded-2xl px-4 py-3 ${
                          isUser
                            ? 'bg-primary text-primary-foreground rounded-br-sm shadow-sm'
                            : 'bg-content2/80 backdrop-blur-sm rounded-bl-sm shadow-sm border border-divider/50'
                        }`}
                      >
                        {!isUser ? (
                          <>
                            {msg.toolCalls?.map((tc) => (
                              <ToolCallCard key={tc.id} toolCall={tc} />
                            ))}
                            {msg.content ? (
                              <div className="prose-sm max-w-none">
                                <MarkdownContent content={msg.content} />
                              </div>
                            ) : (
                              showThinking && <TypingIndicator />
                            )}
                          </>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                        )}

                        {/* Hover action buttons */}
                        {msg.content && !isStreaming && (
                          <div className={`absolute ${isUser ? '-left-9' : '-right-9'} top-1 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150`}>
                            <CopyButton text={msg.content} t={t} />
                            {canDeletePair && currentSessionId && msg.dbId != null && (
                              <Tooltip content={t('agent.deletePair')} placement="left">
                                <button
                                  type="button"
                                  onClick={() => requestDeletePair(currentSessionId, msg.dbId as number)}
                                  className="p-1.5 rounded-lg hover:bg-danger/15 transition-all duration-150 text-foreground/40 hover:text-danger"
                                  aria-label={t('agent.deletePair')}
                                >
                                  <Icon icon={trashBold} fontSize={14} />
                                </button>
                              </Tooltip>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Elapsed time */}
                      {!isUser && msg.elapsedMs != null && (!isStreaming || !isLast) && (
                        <div className="flex items-center gap-1 px-1">
                          <Icon icon={clockBold} className="text-foreground/25" fontSize={11} />
                          <span className="text-xs text-foreground/35">
                            {formatElapsed(msg.elapsedMs)}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* User avatar */}
                    {isUser && (
                      <div className="flex-shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-xl bg-primary/15 border border-primary/20 flex items-center justify-center shadow-sm">
                          <span className="text-primary text-xs font-bold">U</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollShadow>

        {/* ── Input area ── */}
        <div className="flex-shrink-0 border-t border-divider bg-content1/30 px-3 sm:px-5 pt-3 pb-3">
          <form onSubmit={handleFormSubmit}>
            <div className="flex gap-2 items-end">
              <div className="flex-1 relative">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onValueChange={setInput}
                  onKeyDown={handleKeyDown}
                  placeholder={t('agent.inputPlaceholder')}
                  minRows={1}
                  maxRows={6}
                  variant="bordered"
                  classNames={{
                    base: 'w-full',
                    inputWrapper: [
                      'bg-content1 border-divider',
                      'hover:border-primary/50',
                      'focus-within:!border-primary',
                      'transition-colors duration-200',
                      'rounded-xl shadow-sm',
                    ].join(' '),
                    input: 'text-sm pr-1 resize-none',
                  }}
                  isDisabled={isStreaming}
                />
              </div>

              <div className="flex gap-1.5 pb-1 flex-shrink-0">
                {isStreaming ? (
                  <Tooltip content={t('agent.stop')}>
                    <Button
                      isIconOnly
                      color="danger"
                      variant="flat"
                      size="lg"
                      onPress={handleStop}
                      aria-label={t('agent.stop')}
                      className="rounded-xl"
                    >
                      <Icon icon={stopBold} fontSize={20} />
                    </Button>
                  </Tooltip>
                ) : (
                  <Tooltip content={t('agent.send')}>
                    <Button
                      type="submit"
                      isIconOnly
                      color="primary"
                      size="lg"
                      isDisabled={!input.trim() || isStreaming}
                      aria-label={t('agent.send')}
                      className="rounded-xl shadow-sm"
                    >
                      <Icon icon={paperPlaneBold} fontSize={20} />
                    </Button>
                  </Tooltip>
                )}
                {isMobile && (
                  <Tooltip content={t('agent.reset')}>
                    <Button
                      isIconOnly
                      variant="flat"
                      size="lg"
                      onPress={handleReset}
                      aria-label={t('agent.reset')}
                      className="rounded-xl"
                    >
                      <Icon icon={restartBold} fontSize={18} />
                    </Button>
                  </Tooltip>
                )}
              </div>
            </div>

            {/* Hint */}
            <div className="flex items-center gap-1.5 mt-1.5 px-0.5">
              <Icon icon={keyboardBold} className="text-foreground/25" fontSize={12} />
              <span className="text-xs text-foreground/30">{t('agent.sendHint')}</span>
            </div>
          </form>
        </div>
      </div>

      {/* ── Delete confirmation modal ── */}
      <Modal isOpen={isDeleteOpen} onClose={onDeleteClose} placement="center" size="sm">
        <ModalContent>
          <ModalHeader className="text-base font-semibold">{t('agent.deletePairTitle')}</ModalHeader>
          <ModalBody>
            <p className="text-sm text-foreground/70 leading-relaxed">{t('agent.deletePairConfirm')}</p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={onDeleteClose} size="sm">{t('agent.cancel')}</Button>
            <Button color="danger" onPress={handleDeletePair} size="sm">{t('agent.delete')}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
