import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Input,
  Modal, ModalBody, ModalContent, ModalFooter, ModalHeader,
  Pagination, Select, SelectItem, Spinner,
  Table, TableHeader, TableColumn, TableBody, TableRow, TableCell,
  cn,
} from '@heroui/react';
import type { Selection, SortDescriptor } from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import altArrowLeftBold from '@iconify/icons-solar/alt-arrow-left-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import dangerTriangleBold from '@iconify/icons-solar/danger-triangle-bold';
import documentTextBold from '@iconify/icons-solar/document-text-bold';
import hashtagCircleBold from '@iconify/icons-solar/hashtag-circle-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchRuleStat, deleteRuleRecords } from '../api/stats';
import type { RuleRecord } from '../api/stats';
import { ICON_SIZES } from '../constants/iconSizes';

/* ── Helpers ────────────────────────────────────────────────────────── */

function formatTriggerTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'numeric', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  });
}

/* ── Constants ──────────────────────────────────────────────────────── */

const ROWS_PER_PAGE = 10;
type SelectionKey = Selection extends Set<infer K> ? K : never;

const COLUMN_CONFIG: { key: string; labelKey: string; icon: IconifyIcon }[] = [
  { key: 'adapter',   labelKey: 'stats.adapter',   icon: plugCircleBold },
  { key: 'chat_type', labelKey: 'stats.chatType',  icon: usersGroupRoundedBold },
  { key: 'chat_id',   labelKey: 'stats.chatIdCol', icon: hashtagCircleBold },
  { key: 'reason',    labelKey: 'stats.reasonCol',  icon: documentTextBold },
  { key: 'time',      labelKey: 'stats.timeCol',    icon: clockCircleBold },
];

const COLUMN_STYLES: Record<string, string> = {
  adapter:   'w-28 min-w-[5rem]',
  chat_type: 'w-24 min-w-[5rem]',
  chat_id:   'w-44 min-w-[7rem]',
  reason:    'w-[20rem] min-w-[10rem] max-w-[24rem]',
  time:      'w-48 min-w-[8rem]',
  actions:   'w-32 min-w-[6rem]',
};

const SELECTION_COL_CLASS = 'first:w-12 first:min-w-0 first:px-2';

/* ── Component ──────────────────────────────────────────────────────── */

export default function RuleTriggerDetailPage() {
  const { t } = useTranslation();
  const { ruleId } = useParams<{ ruleId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['rule_stat', ruleId],
    queryFn: () => fetchRuleStat(ruleId!),
    enabled: !!ruleId,
  });

  /* ── Delete mutations ───────────────────────────────────────────── */

  const deleteSome = useMutation({
    mutationFn: (ids: string[]) => deleteRuleRecords(ruleId!, ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rule_stat', ruleId] });
      queryClient.invalidateQueries({ queryKey: ['rule_stats'] });
    },
  });

  const deleteAll = useMutation({
    mutationFn: () => deleteRuleRecords(ruleId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rule_stat', ruleId] });
      queryClient.invalidateQueries({ queryKey: ['rule_stats'] });
    },
  });

  const bulkDisabled = deleteSome.isPending || deleteAll.isPending;

  /* ── Filter / search ────────────────────────────────────────────── */

  const records = data?.records ?? [];

  const [adapterFilter, setAdapterFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  // chat_type is excluded because it has its own dedicated filter dropdown
  const [searchField, setSearchField] = useState<'reason' | 'chat_id' | 'adapter'>('reason');
  const [query, setQuery] = useState('');

  const adapters = useMemo(() => [...new Set(records.map(r => r.adapter ?? '').filter(Boolean))], [records]);
  const types = useMemo(() => [...new Set(records.map(r => r.chat_type ?? '').filter(Boolean))], [records]);

  const filtered = useMemo(() => records.filter(r => {
    const fieldValue =
      searchField === 'reason' ? r.reason
        : searchField === 'chat_id' ? (r.chat_id ?? '')
          : (r.adapter ?? '');

    return (
      (!adapterFilter || (r.adapter ?? '') === adapterFilter) &&
      (typeFilter === 'all' || (r.chat_type ?? '') === typeFilter) &&
      (!query || fieldValue.toLowerCase().includes(query.toLowerCase()))
    );
  }), [records, adapterFilter, typeFilter, searchField, query]);

  /* ── Sorting ────────────────────────────────────────────────────── */

  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({ column: 'time', direction: 'descending' });

  const sorted = useMemo(() => {
    const items = [...filtered];
    const { column, direction } = sortDescriptor;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => {
      switch (column) {
        case 'adapter': return (a.adapter ?? '').localeCompare(b.adapter ?? '') * dir;
        case 'chat_type': return (a.chat_type ?? '').localeCompare(b.chat_type ?? '') * dir;
        case 'chat_id': return (a.chat_id ?? '').localeCompare(b.chat_id ?? '') * dir;
        case 'reason': return a.reason.localeCompare(b.reason) * dir;
        case 'time': return (new Date(a.trigger_time).getTime() - new Date(b.trigger_time).getTime()) * dir;
        default: return 0;
      }
    });
    return items;
  }, [filtered, sortDescriptor]);

  /* ── Pagination ─────────────────────────────────────────────────── */

  const [page, setPage] = useState(1);
  const pages = useMemo(() => Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE)), [filtered.length]);
  const pageItems = useMemo(
    () => sorted.slice((page - 1) * ROWS_PER_PAGE, page * ROWS_PER_PAGE),
    [sorted, page],
  );

  useEffect(() => { setPage(1); }, [adapterFilter, typeFilter, searchField, query]);
  useEffect(() => { setPage(p => Math.min(Math.max(1, p), pages)); }, [pages]);

  /* ── Selection ──────────────────────────────────────────────────── */

  const [selectedKeys, setSelectedKeys] = useState<Selection>(new Set());
  const [confirmBulk, setConfirmBulk] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const filteredKeySet = useMemo(() => new Set(filtered.map(r => r.id)), [filtered]);

  useEffect(() => {
    setSelectedKeys(prev => {
      if (prev === 'all') return prev;
      const next = new Set<SelectionKey>();
      (prev as Set<SelectionKey>).forEach(k => {
        if (filteredKeySet.has(String(k))) next.add(k);
      });
      return next;
    });
  }, [filteredKeySet]);

  const resolvedSelection: Set<string> = useMemo(() => {
    if (selectedKeys === 'all') return new Set(filtered.map(r => r.id));
    return new Set(Array.from(selectedKeys as Set<SelectionKey>).map(k => String(k)));
  }, [filtered, selectedKeys]);

  const selectedIds = useMemo(
    () => filtered.filter(r => resolvedSelection.has(r.id)).map(r => r.id),
    [filtered, resolvedSelection],
  );

  /* ── Columns ────────────────────────────────────────────────────── */

  const columns = useMemo(() => COLUMN_CONFIG.map(c => ({
    key: c.key, label: t(c.labelKey), icon: c.icon, sortable: true,
  })), [t]);

  /* ── Bottom content ─────────────────────────────────────────────── */

  const bottomContent = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: filtered.length })}
      </span>
      <Pagination isCompact showControls page={page} total={pages} onChange={setPage} />
    </div>
  ), [filtered.length, page, pages, t]);

  /* ── Loading / error states ─────────────────────────────────────── */

  if (isLoading) {
    return (
      <div className="flex justify-center h-64">
        <Spinner label={t('stats.loading')} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <Button
          variant="light"
          startContent={<Icon icon={altArrowLeftBold} fontSize={ICON_SIZES.button} />}
          onPress={() => navigate('/stats')}
        >
          {t('stats.backToStats')}
        </Button>
        <p className="text-danger">{t('stats.loadError')}</p>
      </div>
    );
  }

  /* ── Render ─────────────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Button
        variant="light"
        startContent={<Icon icon={altArrowLeftBold} fontSize={ICON_SIZES.button} />}
        onPress={() => navigate('/stats')}
      >
        {t('stats.backToStats')}
      </Button>

      {/* Rule info card */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-primary-50 dark:bg-primary-900/30">
            <Icon icon={chatDotsBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-lg text-default-900">{data.rule_name}</p>
            <p className="text-sm text-default-500">{data.description}</p>
          </div>
          <Chip size="sm" color={data.count > 0 ? 'warning' : 'default'} variant="flat">
            {t('stats.triggers', { count: data.count })}
          </Chip>
        </CardHeader>
      </Card>

      {/* Filter bar + table */}
      <Card>
        <CardBody className="space-y-3">
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
                ...types.map(tp => <SelectItem key={tp}>{tp}</SelectItem>),
              ]}
            </Select>
            <Select
              size="sm"
              className="w-44"
              selectedKeys={[searchField]}
              onSelectionChange={k => setSearchField(Array.from(k)[0] as typeof searchField)}
            >
              <SelectItem key="reason">{t('stats.reasonCol')}</SelectItem>
              <SelectItem key="chat_id">{t('stats.chatIdCol')}</SelectItem>
              <SelectItem key="adapter">{t('stats.adapter')}</SelectItem>
            </Select>
            <Input
              size="sm"
              className="w-64"
              placeholder={t('common.search')}
              value={query}
              startContent={<Icon icon={textFieldFocusBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
              onValueChange={setQuery}
            />

            <div className="flex items-center gap-2 ml-auto">
              <Button
                size="sm"
                color="warning"
                variant="flat"
                startContent={<Icon icon={dangerTriangleBold} fontSize={ICON_SIZES.button} />}
                isDisabled={bulkDisabled || selectedIds.length === 0}
                onPress={() => setConfirmBulk(true)}
              >
                {t('stats.deleteSelected', { count: selectedIds.length })}
              </Button>
              <Button
                size="sm"
                color="danger"
                variant="solid"
                startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
                isDisabled={bulkDisabled || records.length === 0}
                isLoading={deleteAll.isPending}
                onPress={() => setConfirmClear(true)}
              >
                {t('stats.clearAll')}
              </Button>
            </div>
          </div>

          <Table
            aria-label={t('stats.triggerRecords')}
            removeWrapper
            selectionMode="multiple"
            selectedKeys={selectedKeys}
            onSelectionChange={keys => setSelectedKeys(keys)}
            isHeaderSticky
            bottomContent={bottomContent}
            sortDescriptor={sortDescriptor}
            onSortChange={setSortDescriptor}
            classNames={{
              th: SELECTION_COL_CLASS,
              td: SELECTION_COL_CLASS,
              sortIcon: 'text-default-500',
            }}
          >
            <TableHeader columns={columns}>
              {(column) => (
                <TableColumn
                  key={column.key}
                  allowsSorting={column.sortable}
                  align="start"
                  className={cn('text-sm md:text-base whitespace-nowrap', COLUMN_STYLES[column.key] ?? '')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />
                    {column.label}
                  </span>
                </TableColumn>
              )}
            </TableHeader>
            <TableBody emptyContent={t('stats.noRecords')} isLoading={isLoading || deleteSome.isPending}>
              {pageItems.map((rec: RuleRecord) => (
                <TableRow key={rec.id}>
                  <TableCell className={COLUMN_STYLES.adapter}>
                    <Chip size="sm" variant="flat">{rec.adapter ?? '—'}</Chip>
                  </TableCell>
                  <TableCell className={COLUMN_STYLES.chat_type}>
                    <Chip size="sm" color="primary" variant="flat">{rec.chat_type ?? '—'}</Chip>
                  </TableCell>
                  <TableCell className={cn('text-xs md:text-sm text-default-500', COLUMN_STYLES.chat_id)}>
                    {rec.chat_id ?? '—'}
                  </TableCell>
                  <TableCell className={cn('text-sm truncate', COLUMN_STYLES.reason)} title={rec.reason}>
                    {rec.reason}
                  </TableCell>
                  <TableCell className={cn('text-xs md:text-sm text-default-400', COLUMN_STYLES.time)}>
                    {formatTriggerTime(rec.trigger_time)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardBody>
      </Card>

      {/* Confirm bulk delete */}
      <Modal isOpen={confirmBulk} onClose={() => setConfirmBulk(false)} size="md">
        <ModalContent>
          <ModalHeader>{t('stats.deleteSelectedTitle')}</ModalHeader>
          <ModalBody>
            <p className="text-default-600">
              {t('stats.deleteSelectedConfirm', { count: selectedIds.length })}
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={() => setConfirmBulk(false)}>{t('common.cancel')}</Button>
            <Button
              color="danger"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
              isDisabled={selectedIds.length === 0}
              onPress={() => {
                setConfirmBulk(false);
                deleteSome.mutate(selectedIds);
                setSelectedKeys(new Set());
              }}
            >
              {t('stats.deleteSelectedShort')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Confirm clear all */}
      <Modal isOpen={confirmClear} onClose={() => setConfirmClear(false)} size="md">
        <ModalContent>
          <ModalHeader>{t('stats.clearAll')}</ModalHeader>
          <ModalBody>
            <p className="text-default-600">
              {t('stats.clearAllConfirm')}
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={() => setConfirmClear(false)}>{t('common.cancel')}</Button>
            <Button
              color="danger"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
              onPress={() => {
                setConfirmClear(false);
                deleteAll.mutate();
                setSelectedKeys(new Set());
              }}
            >
              {t('stats.clearAll')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
