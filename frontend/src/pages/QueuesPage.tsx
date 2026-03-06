import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card, CardBody, Chip, Input, Select, SelectItem, Spinner,
  Tab, Tabs, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter,
} from '@heroui/react';
import type { Selection } from '@heroui/react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { clearHistoryMessages, deleteHistoryMessages, fetchQueues } from '../api/queues';
import type { HistoryMessageKey, QueueMessage } from '../api/queues';

const COLUMNS = ['adapter', 'type', 'chat', 'sender', 'content', 'time'] as const;
type SelectionKey = Selection extends Set<infer K> ? K : never;

const messageKey = (m: QueueMessage) => `${m.platform}|${m.chat_type}|${m.chat_id}|${m.message_id}`;

function QueueTable({
  messages,
  enableHistoryActions,
  onDeleteOne,
  onDeleteMany,
  onClearAll,
  bulkDisabled,
  loading,
  clearing,
}: {
  messages: QueueMessage[];
  enableHistoryActions?: boolean;
  onDeleteOne?: (key: HistoryMessageKey) => void;
  onDeleteMany?: (keys: HistoryMessageKey[]) => void;
  onClearAll?: () => void;
  bulkDisabled?: boolean;
  loading?: boolean;
  clearing?: boolean;
}) {
  const { t } = useTranslation();
  const [adapterFilter, setAdapterFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [searchField, setSearchField] = useState<'content' | 'sender_name' | 'chat_id' | 'adapter'>('content');
  const [query, setQuery] = useState('');
  const [selectedKeys, setSelectedKeys] = useState<Selection>(new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const adapters = useMemo(() => [...new Set(messages.map(m => m.adapter))], [messages]);
  const types = useMemo(() => [...new Set(messages.map(m => m.chat_type))], [messages]);

  const columns = useMemo<{ key: string; label: string }[]>(() => {
    const base = COLUMNS.map(c => ({ key: c as string, label: t(`queues.${c}`) }));
    if (enableHistoryActions) {
      base.push({ key: 'actions', label: t('common.actions') });
    }
    return base;
  }, [enableHistoryActions, t]);

  const filtered = useMemo(() => messages.filter(m => {
    const fieldValue =
      searchField === 'content' ? m.content
        : searchField === 'sender_name' ? m.sender_name
          : searchField === 'chat_id' ? m.chat_id
            : m.adapter;

    return (
      (!adapterFilter || m.adapter === adapterFilter) &&
      (typeFilter === 'all' || m.chat_type === typeFilter) &&
      (!query || String(fieldValue ?? '').toLowerCase().includes(query.toLowerCase()))
    );
  }), [adapterFilter, messages, query, searchField, typeFilter]);

  const filteredKeys = useMemo(() => new Set(filtered.map(messageKey)), [filtered]);

  useEffect(() => {
    if (!enableHistoryActions) return;
    setSelectedKeys(prev => {
      if (prev === 'all') return prev;
      const next = new Set<SelectionKey>();
      (prev as Set<SelectionKey>).forEach(k => {
        if (filteredKeys.has(String(k))) next.add(k);
      });
      return next;
    });
  }, [enableHistoryActions, filteredKeys]);

  const resolvedSelection: Set<string> = useMemo(() => {
    if (selectedKeys === 'all') return new Set(filtered.map(messageKey));
    return new Set(Array.from(selectedKeys as Set<SelectionKey>).map(k => String(k)));
  }, [filtered, selectedKeys]);

  const selectedMessages: HistoryMessageKey[] = useMemo(
    () => filtered
      .filter(m => resolvedSelection.has(messageKey(m)))
      .map(m => ({
        adapter: m.adapter,
        platform: m.platform,
        chat_type: m.chat_type,
        chat_id: m.chat_id,
        message_id: m.message_id,
      })),
    [filtered, resolvedSelection],
  );

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap items-center">
        <Select
          size="sm"
          className="w-44"
          placeholder={t('queues.allAdapters')}
          onSelectionChange={k => setAdapterFilter(Array.from(k)[0] as string ?? '')}
        >
          {adapters.map(a => <SelectItem key={a}>{a}</SelectItem>)}
        </Select>
        <Select
          size="sm"
          className="w-40"
          selectedKeys={[typeFilter]}
          onSelectionChange={k => setTypeFilter(Array.from(k)[0] as string ?? 'all')}
        >
          {[
            <SelectItem key="all">{t('queues.allTypes')}</SelectItem>,
            ...types.map(t => <SelectItem key={t}>{t}</SelectItem>),
          ]}
        </Select>
        <Select
          size="sm"
          className="w-44"
          selectedKeys={[searchField]}
          onSelectionChange={k => setSearchField(Array.from(k)[0] as typeof searchField)}
        >
          <SelectItem key="content">{t('queues.content')}</SelectItem>
          <SelectItem key="sender_name">{t('queues.sender')}</SelectItem>
          <SelectItem key="chat_id">{t('queues.chatId')}</SelectItem>
          <SelectItem key="adapter">{t('queues.adapter')}</SelectItem>
        </Select>
        <Input
          size="sm"
          className="w-64"
          placeholder={t('queues.search')}
          value={query}
          onValueChange={setQuery}
        />

        {enableHistoryActions && (
          <div className="flex items-center gap-2 ml-auto">
            <Button
              size="sm"
              color="warning"
              variant="flat"
              startContent={<AlertTriangle size={18} />}
              isDisabled={bulkDisabled || selectedMessages.length === 0}
              onPress={() => setConfirmBulk(true)}
            >
              {t('queues.deleteSelected', { count: selectedMessages.length })}
            </Button>
            <Button
              size="sm"
              color="danger"
              variant="solid"
              startContent={<Trash2 size={18} />}
              isDisabled={bulkDisabled || (filtered.length === 0)}
              isLoading={clearing}
              onPress={() => setConfirmClear(true)}
            >
              {t('queues.clearHistory')}
            </Button>
          </div>
        )}
      </div>
      <Table
        aria-label={t('queues.messages')}
        removeWrapper
        selectionMode={enableHistoryActions ? 'multiple' : 'none'}
        selectedKeys={enableHistoryActions ? selectedKeys : undefined}
        onSelectionChange={enableHistoryActions ? (keys => setSelectedKeys(keys)) : undefined}
        isHeaderSticky
      >
        <TableHeader columns={columns}>
          {(column) => (
            <TableColumn key={column.key} className="text-sm md:text-base">
              {column.label}
            </TableColumn>
          )}
        </TableHeader>
        <TableBody emptyContent={t('queues.noMessages')} isLoading={loading}>
          {enableHistoryActions
            ? filtered.map(m => (
              <TableRow key={messageKey(m)}>
                <TableCell><Chip size="sm" variant="flat">{m.adapter}</Chip></TableCell>
                <TableCell><Chip size="sm" color="primary" variant="flat">{m.chat_type}</Chip></TableCell>
                <TableCell className="text-xs md:text-sm text-default-500">{m.chat_id}</TableCell>
                <TableCell className="text-sm md:text-base">{m.sender_name}</TableCell>
                <TableCell className="text-sm md:text-base max-w-xs md:max-w-md truncate">{m.content}</TableCell>
                <TableCell className="text-xs md:text-sm text-default-400">{new Date(m.timestamp).toLocaleString()}</TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    color="danger"
                    variant="light"
                    isDisabled={bulkDisabled}
                    startContent={<Trash2 size={16} />}
                    onPress={() => onDeleteOne?.({
                      adapter: m.adapter,
                      platform: m.platform,
                      chat_type: m.chat_type,
                      chat_id: m.chat_id,
                      message_id: m.message_id,
                    })}
                  >
                    {t('common.delete')}
                  </Button>
                </TableCell>
              </TableRow>
            ))
            : filtered.map(m => (
              <TableRow key={messageKey(m)}>
                <TableCell><Chip size="sm" variant="flat">{m.adapter}</Chip></TableCell>
                <TableCell><Chip size="sm" color="primary" variant="flat">{m.chat_type}</Chip></TableCell>
                <TableCell className="text-xs md:text-sm text-default-500">{m.chat_id}</TableCell>
                <TableCell className="text-sm md:text-base">{m.sender_name}</TableCell>
                <TableCell className="text-sm md:text-base max-w-xs md:max-w-md truncate">{m.content}</TableCell>
                <TableCell className="text-xs md:text-sm text-default-400">{new Date(m.timestamp).toLocaleString()}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>

      {enableHistoryActions && (
        <>
          <Modal isOpen={confirmBulk} onClose={() => setConfirmBulk(false)} size="md">
            <ModalContent>
              <ModalHeader>{t('queues.deleteSelectedTitle')}</ModalHeader>
              <ModalBody>
                <p className="text-default-600">
                  {t('queues.deleteSelectedConfirm', { count: selectedMessages.length })}
                </p>
              </ModalBody>
              <ModalFooter>
                <Button variant="flat" onPress={() => setConfirmBulk(false)}>{t('common.cancel')}</Button>
                <Button
                  color="danger"
                  startContent={<Trash2 size={18} />}
                  isDisabled={selectedMessages.length === 0}
                  onPress={() => {
                    setConfirmBulk(false);
                    onDeleteMany?.(selectedMessages);
                  }}
                >
                  {t('queues.deleteSelectedShort')}
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>

          <Modal isOpen={confirmClear} onClose={() => setConfirmClear(false)} size="md">
            <ModalContent>
              <ModalHeader>{t('queues.clearHistory')}</ModalHeader>
              <ModalBody>
                <p className="text-default-600">
                  {t('queues.clearHistoryConfirm')}
                </p>
              </ModalBody>
              <ModalFooter>
                <Button variant="flat" onPress={() => setConfirmClear(false)}>{t('common.cancel')}</Button>
                <Button
                  color="danger"
                  startContent={<Trash2 size={18} />}
                  onPress={() => {
                    setConfirmClear(false);
                    onClearAll?.();
                  }}
                >
                  {t('queues.clearHistory')}
                </Button>
              </ModalFooter>
            </ModalContent>
          </Modal>
        </>
      )}
    </div>
  );
}

export default function QueuesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['queues'],
    queryFn: fetchQueues,
    refetchInterval: 10_000,
  });

  const remove = useMutation({
    mutationFn: (items: HistoryMessageKey[]) => deleteHistoryMessages(items),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['queues'] }),
  });

  const clearHistory = useMutation({
    mutationFn: clearHistoryMessages,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['queues'] }),
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('queues.loading')} /></div>;

  return (
    <Tabs aria-label={t('queues.messages')}>
      <Tab key="pending" title={t('queues.pending', { count: data?.pending.length ?? 0 })}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.pending ?? []} loading={isFetching} />
          </CardBody>
        </Card>
      </Tab>
      <Tab key="history" title={t('queues.history', { count: data?.history.length ?? 0 })}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable
              messages={data?.history ?? []}
              enableHistoryActions
              onDeleteOne={key => remove.mutate([key])}
              onDeleteMany={keys => remove.mutate(keys)}
              onClearAll={() => clearHistory.mutate()}
              bulkDisabled={remove.isPending || clearHistory.isPending}
              loading={isFetching || remove.isPending}
              clearing={clearHistory.isPending}
            />
          </CardBody>
        </Card>
      </Tab>
    </Tabs>
  );
}
