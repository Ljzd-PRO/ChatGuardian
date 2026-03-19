import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card, CardBody, Chip, Input, Pagination, Select, SelectItem, Spinner,
  Tab, Tabs, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, cn,
} from '@heroui/react';
import type { Selection, SortDescriptor } from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import dangerTriangleBold from '@iconify/icons-solar/danger-triangle-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import textBoldCircle from '@iconify/icons-solar/text-bold-circle-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import settingsBold from '@iconify/icons-solar/settings-bold';
import { useTranslation } from 'react-i18next';
import { clearHistoryMessages, deleteHistoryMessages, fetchQueues } from '../api/queues';
import type { HistoryMessageKey, QueueMessage } from '../api/queues';
import { ICON_SIZES } from '../constants/iconSizes';
import { formatAdapterName, formatChatType } from '../utils/chatLabels';

const COLUMN_CONFIG: { key: string; labelKey: string; icon: IconifyIcon }[] = [
  { key: 'adapter', labelKey: 'queues.adapter', icon: plugCircleBold },
  { key: 'type', labelKey: 'queues.type', icon: usersGroupRoundedBold },
  { key: 'chat', labelKey: 'queues.chat', icon: chatDotsBold },
  { key: 'sender', labelKey: 'queues.sender', icon: userRoundedBold },
  { key: 'content', labelKey: 'queues.content', icon: textBoldCircle },
  { key: 'time', labelKey: 'queues.time', icon: clockCircleBold },
];
/** Tailwind classes applied to the selection-checkbox column (first th/td) */
const SELECTION_COL_CLASS = 'first:w-12 first:min-w-0 first:px-2';
const COLUMN_STYLES: Record<string, string> = {
  adapter: 'w-28 min-w-[5rem]',
  type: 'w-24 min-w-[5rem]',
  chat: 'w-44 min-w-[7rem]',
  sender: 'w-44 min-w-[7rem]',
  content: 'w-[18rem] min-w-[10rem] max-w-[22rem]',
  time: 'w-48 min-w-[8rem]',
  actions: 'w-32 min-w-[6rem]',
};
const ROWS_PER_PAGE = 10;
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
  const [page, setPage] = useState(1);
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({ column: 'time', direction: 'descending' });

  const adapters = useMemo(() => [...new Set(messages.map(m => m.adapter))], [messages]);
  const types = useMemo(() => [...new Set(messages.map(m => m.chat_type))], [messages]);

  const columns = useMemo<{ key: string; label: string; icon?: IconifyIcon; sortable?: boolean }[]>(() => {
    const base = COLUMN_CONFIG.map(c => ({ key: c.key, label: t(c.labelKey), icon: c.icon, sortable: true }));
    if (enableHistoryActions) {
      base.push({ key: 'actions', label: t('common.actions'), icon: settingsBold, sortable: false });
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

  const sorted = useMemo(() => {
    const items = [...filtered];
    const { column, direction } = sortDescriptor;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => {
      const getValue = (key: string) => {
        switch (key) {
          case 'adapter': return a.adapter.localeCompare(b.adapter);
          case 'type': return a.chat_type.localeCompare(b.chat_type);
          case 'chat': return a.chat_id.localeCompare(b.chat_id);
          case 'sender': return a.sender_name.localeCompare(b.sender_name);
          case 'content': return a.content.localeCompare(b.content);
          case 'time': return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          default: return 0;
        }
      };
      return getValue(column as string) * dir;
    });
    return items;
  }, [filtered, sortDescriptor]);

  const filteredKeys = useMemo(() => new Set(filtered.map(messageKey)), [filtered]);
  const pages = useMemo(() => Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE)), [filtered.length]);
  const pageItems = useMemo(
    () => sorted.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE),
    [sorted, page],
  );

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

  useEffect(() => {
    setPage(1);
  }, [adapterFilter, typeFilter, searchField, query]);

  useEffect(() => {
    setPage(p => Math.min(Math.max(1, p), pages));
  }, [pages]);

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

  const bottomContent = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: filtered.length })}
      </span>
      <Pagination
        isCompact
        showControls
        page={page}
        total={pages}
        onChange={setPage}
      />
    </div>
  ), [filtered.length, page, pages, t]);

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap items-center">
        <Select
          size="sm"
          className="w-44"
          placeholder={t('queues.allAdapters')}
          onSelectionChange={k => setAdapterFilter(Array.from(k)[0] as string ?? '')}
        >
          {adapters.map(a => <SelectItem key={a}>{formatAdapterName(t, a)}</SelectItem>)}
        </Select>
        <Select
          size="sm"
          className="w-40"
          selectedKeys={[typeFilter]}
          onSelectionChange={k => setTypeFilter(Array.from(k)[0] as string ?? 'all')}
        >
          {[
            <SelectItem key="all">{t('queues.allTypes')}</SelectItem>,
            ...types.map(chatType => <SelectItem key={chatType}>{formatChatType(t, chatType)}</SelectItem>),
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
          startContent={<Icon icon={textFieldFocusBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          onValueChange={setQuery}
        />

        {enableHistoryActions && (
          <div className="flex items-center gap-2 ml-auto">
            <Button
              size="sm"
              color="warning"
              variant="flat"
              startContent={<Icon icon={dangerTriangleBold} fontSize={ICON_SIZES.button} />}
              isDisabled={bulkDisabled || selectedMessages.length === 0}
              onPress={() => setConfirmBulk(true)}
            >
              {t('queues.deleteSelected', { count: selectedMessages.length })}
            </Button>
            <Button
              size="sm"
              color="danger"
              variant="solid"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
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
        bottomContent={bottomContent}
        sortDescriptor={sortDescriptor}
        onSortChange={setSortDescriptor}
        classNames={{
          th: enableHistoryActions ? SELECTION_COL_CLASS : undefined,
          td: enableHistoryActions ? SELECTION_COL_CLASS : undefined,
          sortIcon: 'text-default-500',
        }}
      >
        <TableHeader columns={columns}>
          {(column) => (
            <TableColumn
              key={column.key}
              allowsSorting={column.sortable !== false && column.key !== 'actions'}
              align="start"
              className={cn('text-sm md:text-base whitespace-nowrap', COLUMN_STYLES[column.key] ?? '')}
            >
              <span className="inline-flex items-center gap-1">
                {column.icon && <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />}
                {column.label}
              </span>
            </TableColumn>
          )}
        </TableHeader>
        <TableBody emptyContent={t('queues.noMessages')} isLoading={loading}>
          {enableHistoryActions
            ? pageItems.map(m => (
              <TableRow key={messageKey(m)}>
                <TableCell className={COLUMN_STYLES.adapter}>
                  <Chip size="sm" variant="flat">{formatAdapterName(t, m.adapter)}</Chip>
                </TableCell>
                <TableCell className={COLUMN_STYLES.type}>
                  <Chip size="sm" color="primary" variant="flat">{formatChatType(t, m.chat_type)}</Chip>
                </TableCell>
                <TableCell className={cn('text-xs md:text-sm text-default-500', COLUMN_STYLES.chat)}>{m.chat_id}</TableCell>
                <TableCell className={cn('text-sm md:text-base', COLUMN_STYLES.sender)}>{m.sender_name}</TableCell>
                <TableCell className={cn('text-sm md:text-base truncate', COLUMN_STYLES.content)} title={m.content}>{m.content}</TableCell>
                <TableCell className={cn('text-xs md:text-sm text-default-400', COLUMN_STYLES.time)}>{new Date(m.timestamp).toLocaleString()}</TableCell>
                <TableCell className={COLUMN_STYLES.actions}>
                  <Button
                    size="sm"
                    color="danger"
                    variant="light"
                    isDisabled={bulkDisabled}
                    startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
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
            : pageItems.map(m => (
              <TableRow key={messageKey(m)}>
                <TableCell className={COLUMN_STYLES.adapter}>
                  <Chip size="sm" variant="flat">{formatAdapterName(t, m.adapter)}</Chip>
                </TableCell>
                <TableCell className={COLUMN_STYLES.type}>
                  <Chip size="sm" color="primary" variant="flat">{formatChatType(t, m.chat_type)}</Chip>
                </TableCell>
                <TableCell className={cn('text-xs md:text-sm text-default-500', COLUMN_STYLES.chat)}>{m.chat_id}</TableCell>
                <TableCell className={cn('text-sm md:text-base', COLUMN_STYLES.sender)}>{m.sender_name}</TableCell>
                <TableCell className={cn('text-sm md:text-base truncate', COLUMN_STYLES.content)} title={m.content}>{m.content}</TableCell>
                <TableCell className={cn('text-xs md:text-sm text-default-400', COLUMN_STYLES.time)}>{new Date(m.timestamp).toLocaleString()}</TableCell>
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
                  startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
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
                  startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
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
    <Tabs aria-label={t('queues.messages')} defaultSelectedKey="history">
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
      <Tab key="pending" title={t('queues.pending', { count: data?.pending.length ?? 0 })}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.pending ?? []} loading={isFetching} />
          </CardBody>
        </Card>
      </Tab>
    </Tabs>
  );
}
