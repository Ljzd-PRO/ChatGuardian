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
import magnetBold from '@iconify/icons-solar/magnet-bold';
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

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallInfo[];
  elapsedMs?: number;
  dbId?: number;
}

/* ─── Markdown components for react-markdown ───────────────────────── */

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h2 className="font-bold text-foreground text-lg mt-3 mb-1">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="font-bold text-foreground text-base mt-3 mb-1">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="font-semibold text-foreground text-sm mt-3 mb-1">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="text-foreground/80 text-sm my-1 leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside space-y-1 my-2 text-foreground/80 text-sm">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside space-y-1 my-2 text-foreground/80 text-sm">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-foreground/80 text-sm">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic">{children}</em>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return <code className="text-xs font-mono">{children}</code>;
    }
    return (
      <code className="bg-primary/10 text-primary px-1.5 py-0.5 rounded text-xs font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="bg-content1 border border-divider rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono text-foreground">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full border-collapse border border-divider text-sm">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-content2">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border border-divider px-3 py-2 text-left font-semibold text-foreground text-xs">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-divider px-3 py-2 text-foreground/80 text-xs">
      {children}
    </td>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-3 border-primary/50 pl-3 my-2 text-foreground/60 italic">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-divider my-3" />,
};

function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
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
    <Tooltip content={copied ? t('agent.copied') : t('agent.copy')}>
      <button
        type="button"
        onClick={handleCopy}
        className="p-1 rounded-md hover:bg-content2 transition-colors text-foreground/40 hover:text-foreground/70"
        aria-label={t('agent.copy')}
      >
        <Icon icon={copyBold} fontSize={14} />
      </button>
    </Tooltip>
  );
}

/* ─── Tool call display ────────────────────────────────────────────── */

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
    <div className="my-2 rounded-lg border border-divider overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 text-left bg-content1 hover:bg-content2 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {toolCall.isLoading ? (
          <Spinner size="sm" className="w-4 h-4" />
        ) : isError ? (
          <span className="text-danger text-sm">✗</span>
        ) : (
          <span className="text-success text-sm">✓</span>
        )}
        <span className="text-sm font-medium text-foreground flex-1">
          {toolCall.displayName}
        </span>
        <span className="text-xs text-foreground/40">
          {expanded ? '▲' : '▼'}
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 bg-content1/50 border-t border-divider">
          {toolCall.args && (
            <div className="mb-2">
              <p className="text-xs text-foreground/50 mb-1">{t('agent.toolArgs')}:</p>
              <pre className="text-xs bg-content1 border border-divider rounded p-2 overflow-x-auto font-mono text-foreground/70">
                {(() => {
                  try { return JSON.stringify(JSON.parse(toolCall.args), null, 2); }
                  catch { return toolCall.args; }
                })()}
              </pre>
            </div>
          )}
          {resultStr && (
            <div>
              <p className="text-xs text-foreground/50 mb-1">{t('agent.toolResult')}:</p>
              <pre className="text-xs bg-content1 border border-divider rounded p-2 overflow-x-auto max-h-48 font-mono text-foreground/70">
                {resultStr.length > MAX_TOOL_RESULT_LENGTH ? resultStr.slice(0, MAX_TOOL_RESULT_LENGTH) + '\n...(truncated)' : resultStr}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Suggested prompts ────────────────────────────────────────────── */

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
  generate_rule_from_description: magnetBold,
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
  t,
}: {
  sessions: AgentSession[];
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  isLoading: boolean;
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
      <div className="p-3 border-b border-divider">
        <Button
          color="primary"
          variant="flat"
          size="sm"
          className="w-full"
          startContent={<Icon icon={addBold} fontSize={16} />}
          onPress={onNewSession}
        >
          {t('agent.newSession')}
        </Button>
      </div>
      <ScrollShadow className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner size="sm" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-8 text-foreground/40 text-sm">
            {t('agent.noSessions')}
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                className={`group flex items-center gap-1 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                  currentSessionId === session.session_id
                    ? 'bg-primary/10 text-primary'
                    : 'hover:bg-content2 text-foreground'
                }`}
                onClick={() => onSelectSession(session.session_id)}
              >
                <Icon icon={chatBold} fontSize={14} className="flex-shrink-0 opacity-50" />
                {editingId === session.session_id ? (
                  <input
                    className="flex-1 min-w-0 text-sm bg-content1 border border-divider rounded px-1 py-0.5 text-foreground outline-none"
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
                  <span className="flex-1 min-w-0 text-sm truncate">
                    {session.title || t('agent.untitledSession')}
                  </span>
                )}
                <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                  <button
                    type="button"
                    className="p-1 rounded hover:bg-content3 transition-colors text-foreground/50 hover:text-foreground"
                    onClick={(e) => { e.stopPropagation(); startRename(session); }}
                    aria-label={t('agent.rename')}
                  >
                    <Icon icon={penBold} fontSize={12} />
                  </button>
                  <button
                    type="button"
                    className="p-1 rounded hover:bg-danger/20 transition-colors text-foreground/50 hover:text-danger"
                    onClick={(e) => { e.stopPropagation(); onDeleteSession(session.session_id); }}
                    aria-label={t('agent.deleteSession')}
                  >
                    <Icon icon={trashBold} fontSize={12} />
                  </button>
                </div>
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
    let cancelled = false;
    fetchSessionMessages(currentSessionId).then((msgs) => {
      if (cancelled) return;
      const chatMsgs: ChatMessage[] = msgs.map((m: AgentSessionMessage) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
        toolCalls: (m.tool_calls ?? []).map((tc: any) => ({
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
        toolCalls: (m.tool_calls ?? []).map((tc: any) => ({
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
    <div className="flex h-[calc(100vh-8rem)] max-w-6xl mx-auto gap-0">
      {/* ── Sidebar (desktop) ── */}
      {!isMobile && (
        <div className="w-64 flex-shrink-0 border-r border-divider bg-content1 rounded-l-xl overflow-hidden">
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelectSession={(id) => { setCurrentSessionId(id); }}
            onNewSession={handleNewSession}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
            isLoading={sessionsLoading}
            t={t}
          />
        </div>
      )}

      {/* ── Sidebar (mobile drawer) ── */}
      {isMobile && (
        <Modal isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} placement="center" size="sm" scrollBehavior="inside">
          <ModalContent>
            <ModalHeader className="pb-1">{t('agent.sessions')}</ModalHeader>
            <ModalBody className="p-0 min-h-[50vh]">
              <SessionSidebar
                sessions={sessions}
                currentSessionId={currentSessionId}
                onSelectSession={(id) => { setCurrentSessionId(id); setSidebarOpen(false); }}
                onNewSession={() => { handleNewSession(); setSidebarOpen(false); }}
                onDeleteSession={handleDeleteSession}
                onRenameSession={handleRenameSession}
                isLoading={sessionsLoading}
                t={t}
              />
            </ModalBody>
          </ModalContent>
        </Modal>
      )}

      {/* ── Main chat area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {isMobile && (
          <div className="flex items-center gap-2 px-3 py-2 border-b border-divider">
            <Button
              isIconOnly
              variant="light"
              size="sm"
              onPress={() => setSidebarOpen(true)}
              aria-label={t('agent.sessions')}
            >
              <Icon icon={menuBold} fontSize={20} />
            </Button>
            <span className="text-sm font-medium text-foreground truncate flex-1">
              {t('agent.title')}
            </span>
          </div>
        )}

        <ScrollShadow className="flex-1 overflow-y-auto px-2 sm:px-4 pb-4">
          {showEmptyState ? (
            <div className="flex flex-col items-center justify-center h-full gap-6 py-8">
              <div className="text-center space-y-2">
                <div className="flex items-center justify-center gap-2 mb-4">
                  <Icon icon={cpuBold} className="text-primary" fontSize={32} />
                </div>
                <h2 className="text-xl font-bold text-foreground">
                  {t('agent.title')}
                </h2>
                <p className="text-sm text-foreground/50 max-w-md">
                  {t('agent.description')}
                </p>
              </div>

              {capabilities && (
                <div className="w-full max-w-2xl space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Card className="border border-divider">
                      <CardBody className="p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Icon icon={chartBold} className="text-primary" fontSize={18} />
                          <h3 className="font-semibold text-sm text-foreground">
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
                                  startContent={icon ? <Icon icon={icon} fontSize={12} className="text-foreground/50" /> : undefined}
                                  className="text-xs"
                                >
                                  {label}
                                </Chip>
                              );
                            })}
                        </div>
                      </CardBody>
                    </Card>

                    <Card className="border border-divider">
                      <CardBody className="p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Icon icon={settingsBold} className="text-primary" fontSize={18} />
                          <h3 className="font-semibold text-sm text-foreground">
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
                                  startContent={icon ? <Icon icon={icon} fontSize={12} className="text-foreground/50" /> : undefined}
                                  className="text-xs"
                                >
                                  {label}
                                </Chip>
                              );
                            })}
                        </div>
                      </CardBody>
                    </Card>
                  </div>

                  <div>
                    <p className="text-xs text-foreground/40 mb-2">{t('agent.suggestedPrompts')}</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {suggestedPrompts.map((prompt) => (
                        <button
                          type="button"
                          key={prompt}
                          onClick={() => handlePromptClick(prompt)}
                          className="text-left px-3 py-2.5 rounded-lg border border-divider
                            bg-content1 hover:bg-content2
                            text-sm text-foreground/60
                            transition-colors cursor-pointer"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4 py-4">
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
                    key={idx}
                    className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    {!isUser && (
                      <div className="flex-shrink-0 mr-2 mt-1">
                        <div className="w-8 h-8 rounded-full bg-secondary/20 flex items-center justify-center">
                          <Icon icon={cpuBold} className="text-secondary" fontSize={16} />
                        </div>
                      </div>
                    )}

                    <div className={`max-w-[85%] sm:max-w-[80%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                      <div
                        className={`group relative rounded-2xl px-4 py-3 shadow-sm ${
                          isUser
                            ? 'bg-primary text-primary-foreground rounded-br-md'
                            : 'bg-content2 rounded-bl-md'
                        }`}
                      >
                        {!isUser ? (
                          <>
                            {msg.toolCalls?.map((tc) => (
                              <ToolCallCard key={tc.id} toolCall={tc} />
                            ))}
                            {msg.content ? (
                              <div className="prose-sm">
                                <MarkdownContent content={msg.content} />
                              </div>
                            ) : (
                              showThinking && (
                                <div className="flex items-center gap-2">
                                  <Spinner size="sm" />
                                  <span className="text-sm text-foreground/40">{t('agent.thinking')}</span>
                                </div>
                              )
                            )}
                          </>
                        ) : (
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        )}

                        {msg.content && !isStreaming && (
                          <div className={`absolute ${isUser ? '-left-8' : '-right-8'} top-1 flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity`}>
                            <CopyButton text={msg.content} t={t} />
                            {canDeletePair && (
                              <Tooltip content={t('agent.deletePair')}>
                                <button
                                  type="button"
                                  onClick={() => requestDeletePair(currentSessionId!, msg.dbId!)}
                                  className="p-1 rounded-md hover:bg-danger/20 transition-colors text-foreground/40 hover:text-danger"
                                  aria-label={t('agent.deletePair')}
                                >
                                  <Icon icon={trashBold} fontSize={14} />
                                </button>
                              </Tooltip>
                            )}
                          </div>
                        )}
                      </div>

                      {!isUser && msg.elapsedMs != null && (!isStreaming || !isLast) && (
                        <div className="flex items-center gap-1 mt-1.5 px-1">
                          <Icon icon={clockBold} className="text-foreground/30" fontSize={12} />
                          <span className="text-xs text-foreground/40">
                            {t('agent.elapsed', { time: formatElapsed(msg.elapsedMs) })}
                          </span>
                        </div>
                      )}
                    </div>

                    {isUser && (
                      <div className="flex-shrink-0 ml-2 mt-1">
                        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
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

        <div className="border-t border-divider pt-3 pb-2 px-2 sm:px-4">
          <form onSubmit={handleFormSubmit} className="flex gap-2 items-end">
            <div className="flex-1">
              <Textarea
                ref={textareaRef}
                value={input}
                onValueChange={setInput}
                onKeyDown={handleKeyDown}
                placeholder={t('agent.inputPlaceholder')}
                minRows={1}
                maxRows={5}
                variant="bordered"
                size="lg"
                classNames={{
                  inputWrapper: 'bg-content1',
                }}
                isDisabled={isStreaming}
              />
            </div>
            <div className="flex gap-1 pb-1">
              {isStreaming ? (
                <Tooltip content={t('agent.stop')}>
                  <Button
                    isIconOnly
                    color="danger"
                    variant="flat"
                    size="lg"
                    onPress={handleStop}
                    aria-label={t('agent.stop')}
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
                    isDisabled={!input.trim()}
                    aria-label={t('agent.send')}
                  >
                    <Icon icon={paperPlaneBold} fontSize={20} />
                  </Button>
                </Tooltip>
              )}
              <Tooltip content={t('agent.reset')}>
                <Button
                  isIconOnly
                  variant="flat"
                  size="lg"
                  onPress={handleReset}
                  aria-label={t('agent.reset')}
                >
                  <Icon icon={restartBold} fontSize={20} />
                </Button>
              </Tooltip>
            </div>
          </form>
        </div>
      </div>

      <Modal isOpen={isDeleteOpen} onClose={onDeleteClose} placement="center" size="sm">
        <ModalContent>
          <ModalHeader>{t('agent.deletePairTitle')}</ModalHeader>
          <ModalBody>
            <p className="text-sm text-foreground/70">{t('agent.deletePairConfirm')}</p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={onDeleteClose}>{t('agent.cancel')}</Button>
            <Button color="danger" onPress={handleDeletePair}>{t('agent.delete')}</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
