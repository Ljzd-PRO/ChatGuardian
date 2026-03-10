import { useState, useRef, useEffect, useCallback, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Card,
  CardBody,
  Chip,
  Spinner,
  Textarea,
  ScrollShadow,
  Tooltip,
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

import {
  streamAgentChat,
  fetchAgentCapabilities,
  type AgentEvent,
  type AgentMessage,
} from '../api/agent';

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
}

/* ─── Markdown-ish renderer (safe subset) ──────────────────────────── */

function renderMarkdown(text: string) {
  if (!text) return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="list-disc list-inside space-y-1 my-2">
          {listItems.map((item, i) => (
            <li key={i} className="text-default-700 dark:text-default-300 text-sm">
              {renderInlineMarkdown(item)}
            </li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  const flushCode = () => {
    if (codeLines.length > 0) {
      elements.push(
        <pre
          key={`code-${elements.length}`}
          className="bg-default-100 dark:bg-default-50/50 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono"
        >
          <code>{codeLines.join('\n')}</code>
        </pre>,
      );
      codeLines = [];
    }
  };

  for (const line of lines) {
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={`h3-${elements.length}`} className="font-semibold text-default-800 dark:text-default-200 text-sm mt-3 mb-1">
          {renderInlineMarkdown(line.slice(4))}
        </h4>,
      );
    } else if (line.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={`h2-${elements.length}`} className="font-bold text-default-900 dark:text-default-100 text-base mt-3 mb-1">
          {renderInlineMarkdown(line.slice(3))}
        </h3>,
      );
    } else if (line.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={`h1-${elements.length}`} className="font-bold text-default-900 dark:text-default-100 text-lg mt-3 mb-1">
          {renderInlineMarkdown(line.slice(2))}
        </h2>,
      );
    } else if (/^[-*]\s/.test(line)) {
      listItems.push(line.replace(/^[-*]\s/, ''));
    } else if (/^\d+\.\s/.test(line)) {
      flushList();
      elements.push(
        <p key={`ol-${elements.length}`} className="text-default-700 dark:text-default-300 text-sm my-0.5">
          {renderInlineMarkdown(line)}
        </p>,
      );
    } else if (line.trim() === '') {
      flushList();
      elements.push(<div key={`br-${elements.length}`} className="h-2" />);
    } else {
      flushList();
      elements.push(
        <p key={`p-${elements.length}`} className="text-default-700 dark:text-default-300 text-sm my-0.5">
          {renderInlineMarkdown(line)}
        </p>,
      );
    }
  }

  flushList();
  if (inCodeBlock) flushCode();

  return <>{elements}</>;
}

function renderInlineMarkdown(text: string): React.ReactNode {
  // Bold, italic, inline code, links
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold: **text**
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    // Inline code: `text`
    const codeMatch = remaining.match(/`(.+?)`/);

    type InlineMatch = { index: number; full: string; node: React.ReactNode };
    const candidates: InlineMatch[] = [];

    if (boldMatch?.index !== undefined) {
      candidates.push({
        index: boldMatch.index,
        full: boldMatch[0],
        node: <strong key={key++} className="font-semibold text-default-900 dark:text-default-100">{boldMatch[1]}</strong>,
      });
    }

    if (codeMatch?.index !== undefined) {
      candidates.push({
        index: codeMatch.index,
        full: codeMatch[0],
        node: (
          <code key={key++} className="bg-default-100 dark:bg-default-50/60 text-primary-600 dark:text-primary-400 px-1.5 py-0.5 rounded text-xs font-mono">
            {codeMatch[1]}
          </code>
        ),
      });
    }

    candidates.sort((a, b) => a.index - b.index);
    const firstMatch = candidates[0] ?? null;

    if (firstMatch) {
      if (firstMatch.index > 0) {
        parts.push(remaining.slice(0, firstMatch.index));
      }
      parts.push(firstMatch.node);
      remaining = remaining.slice(firstMatch.index + firstMatch.full.length);
    } else {
      parts.push(remaining);
      break;
    }
  }

  return parts.length === 1 ? parts[0] : <>{parts}</>;
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
    <div className="my-2 rounded-lg border border-default-200 dark:border-default-100 overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 text-left bg-default-50 dark:bg-default-100/50 hover:bg-default-100 dark:hover:bg-default-100 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {toolCall.isLoading ? (
          <Spinner size="sm" className="w-4 h-4" />
        ) : isError ? (
          <span className="text-danger text-sm">✗</span>
        ) : (
          <span className="text-success text-sm">✓</span>
        )}
        <span className="text-sm font-medium text-default-700 dark:text-default-300 flex-1">
          {toolCall.displayName}
        </span>
        <span className="text-xs text-default-400">
          {expanded ? '▲' : '▼'}
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 bg-default-50/50 dark:bg-default-50/30 border-t border-default-200 dark:border-default-100">
          {toolCall.args && (
            <div className="mb-2">
              <p className="text-xs text-default-400 mb-1">{t('agent.toolArgs')}:</p>
              <pre className="text-xs bg-default-100 dark:bg-default-50/50 rounded p-2 overflow-x-auto font-mono text-default-600 dark:text-default-400">
                {(() => {
                  try { return JSON.stringify(JSON.parse(toolCall.args), null, 2); }
                  catch { return toolCall.args; }
                })()}
              </pre>
            </div>
          )}
          {resultStr && (
            <div>
              <p className="text-xs text-default-400 mb-1">{t('agent.toolResult')}:</p>
              <pre className="text-xs bg-default-100 dark:bg-default-50/50 rounded p-2 overflow-x-auto max-h-48 font-mono text-default-600 dark:text-default-400">
                {resultStr.length > 2000 ? resultStr.slice(0, 2000) + '\n...(truncated)' : resultStr}
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

/* ─── Main component ───────────────────────────────────────────────── */

export default function AgentChatPage() {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language.startsWith('zh');

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: capabilities } = useQuery({
    queryKey: ['agent-capabilities'],
    queryFn: fetchAgentCapabilities,
    staleTime: 60_000,
  });

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const suggestedPrompts = [
    t('agent.prompts.dashboard'),
    t('agent.prompts.listRules'),
    t('agent.prompts.llmHealth'),
    t('agent.prompts.adapters'),
    t('agent.prompts.createRule'),
    t('agent.prompts.viewLogs'),
  ];

  const handleSubmit = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || isStreaming) return;

      const userMsg: ChatMessage = { role: 'user', content };
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);
      setInput('');
      setIsStreaming(true);

      // Prepare history for API (only role/content)
      const apiMessages: AgentMessage[] = newMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: '',
        toolCalls: [],
      };

      setMessages([...newMessages, assistantMsg]);

      const abort = new AbortController();
      abortRef.current = abort;

      // Track ongoing tool calls for streaming accumulation
      const toolCallsMap: Record<string, ToolCallInfo> = {};

      try {
        await streamAgentChat(
          apiMessages,
          (event: AgentEvent) => {
            setMessages((prev) => {
              const updated = [...prev];
              const lastMsg = { ...updated[updated.length - 1] };
              lastMsg.toolCalls = [...(lastMsg.toolCalls ?? [])];

              switch (event.type) {
                case 'token':
                  lastMsg.content += event.content ?? '';
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
                  lastMsg.toolCalls = [
                    ...lastMsg.toolCalls.filter((t) => t.id !== tcId),
                    tc,
                  ];
                  break;
                }

                case 'tool_call_args': {
                  const tcId = event.tool_call_id ?? '';
                  if (toolCallsMap[tcId]) {
                    toolCallsMap[tcId].args += event.args_delta ?? '';
                    lastMsg.toolCalls = lastMsg.toolCalls.map((t) =>
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
                    lastMsg.toolCalls = lastMsg.toolCalls.map((t) =>
                      t.id === tcId
                        ? { ...toolCallsMap[tcId], result: event.result, isLoading: false }
                        : t,
                    );
                  } else {
                    lastMsg.toolCalls = [
                      ...lastMsg.toolCalls,
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
                  lastMsg.content += `\n\n❌ ${event.content ?? 'Unknown error'}`;
                  break;

                case 'done':
                  break;
              }

              updated[updated.length - 1] = lastMsg;
              return updated;
            });
          },
          abort.signal,
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = { ...updated[updated.length - 1] };
            lastMsg.content += `\n\n❌ ${err instanceof Error ? err.message : 'Unknown error'}`;
            updated[updated.length - 1] = lastMsg;
            return updated;
          });
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [input, isStreaming, messages],
  );

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleReset = () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setMessages([]);
    setIsStreaming(false);
  };

  const handlePromptClick = (prompt: string) => {
    handleSubmit(prompt);
  };

  /* ─── Empty state: capabilities + prompts ─────────────────────────── */

  const showEmptyState = messages.length === 0;

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-4xl mx-auto">
      {/* Messages area */}
      <ScrollShadow className="flex-1 overflow-y-auto px-1 pb-4">
        {showEmptyState ? (
          <div className="flex flex-col items-center justify-center h-full gap-6 py-8">
            {/* Header */}
            <div className="text-center space-y-2">
              <div className="flex items-center justify-center gap-2 mb-4">
                <Icon icon={cpuBold} className="text-primary" fontSize={32} />
              </div>
              <h2 className="text-xl font-bold text-default-900 dark:text-default-100">
                {t('agent.title')}
              </h2>
              <p className="text-sm text-default-500 dark:text-default-400 max-w-md">
                {t('agent.description')}
              </p>
            </div>

            {/* Capabilities */}
            {capabilities && (
              <div className="w-full max-w-2xl space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Card className="border border-default-200 dark:border-default-100">
                    <CardBody className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Icon icon={chartBold} className="text-primary" fontSize={18} />
                        <h3 className="font-semibold text-sm text-default-800 dark:text-default-200">
                          {t('agent.capabilities.query')}
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {capabilities.capabilities
                          .find((c) => c.category === 'query')
                          ?.items.map((item) => {
                            const display = capabilities.tool_display_names[item];
                            const label = display
                              ? isZh
                                ? display.zh
                                : display.en
                              : item;
                            const icon = CAPABILITY_ICONS[item];
                            return (
                              <Chip
                                key={item}
                                size="sm"
                                variant="flat"
                                color="default"
                                startContent={
                                  icon ? (
                                    <Icon icon={icon} fontSize={12} className="text-default-500" />
                                  ) : undefined
                                }
                                className="text-xs"
                              >
                                {label}
                              </Chip>
                            );
                          })}
                      </div>
                    </CardBody>
                  </Card>

                  <Card className="border border-default-200 dark:border-default-100">
                    <CardBody className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Icon icon={settingsBold} className="text-primary" fontSize={18} />
                        <h3 className="font-semibold text-sm text-default-800 dark:text-default-200">
                          {t('agent.capabilities.management')}
                        </h3>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {capabilities.capabilities
                          .find((c) => c.category === 'management')
                          ?.items.map((item) => {
                            const display = capabilities.tool_display_names[item];
                            const label = display
                              ? isZh
                                ? display.zh
                                : display.en
                              : item;
                            const icon = CAPABILITY_ICONS[item];
                            return (
                              <Chip
                                key={item}
                                size="sm"
                                variant="flat"
                                color="default"
                                startContent={
                                  icon ? (
                                    <Icon icon={icon} fontSize={12} className="text-default-500" />
                                  ) : undefined
                                }
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

                {/* Suggested prompts */}
                <div>
                  <p className="text-xs text-default-400 mb-2">{t('agent.suggestedPrompts')}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {suggestedPrompts.map((prompt) => (
                      <button
                        type="button"
                        key={prompt}
                        onClick={() => handlePromptClick(prompt)}
                        className="text-left px-3 py-2.5 rounded-lg border border-default-200 dark:border-default-100
                          bg-default-50 dark:bg-default-50/30
                          hover:bg-default-100 dark:hover:bg-default-100/50
                          text-sm text-default-600 dark:text-default-400
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
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground rounded-br-md'
                      : 'bg-default-100 dark:bg-default-50/60 text-default-800 dark:text-default-200 rounded-bl-md'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <>
                      {/* Tool calls */}
                      {msg.toolCalls?.map((tc) => (
                        <ToolCallCard key={tc.id} toolCall={tc} />
                      ))}
                      {/* Text content */}
                      {msg.content ? (
                        <div className="prose-sm">{renderMarkdown(msg.content)}</div>
                      ) : (
                        !msg.toolCalls?.length &&
                        isStreaming &&
                        idx === messages.length - 1 && (
                          <div className="flex items-center gap-2">
                            <Spinner size="sm" />
                            <span className="text-sm text-default-400">{t('agent.thinking')}</span>
                          </div>
                        )
                      )}
                    </>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </ScrollShadow>

      {/* Input area */}
      <div className="border-t border-divider pt-3 pb-2">
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
                inputWrapper: 'bg-default-50 dark:bg-default-100/30',
              }}
              isDisabled={isStreaming}
            />
          </div>
          <div className="flex gap-1 pb-1">
            <Tooltip content={t('agent.send')}>
              <Button
                type="submit"
                isIconOnly
                color="primary"
                size="lg"
                isDisabled={!input.trim() || isStreaming}
                aria-label={t('agent.send')}
              >
                <Icon icon={paperPlaneBold} fontSize={20} />
              </Button>
            </Tooltip>
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
  );
}
