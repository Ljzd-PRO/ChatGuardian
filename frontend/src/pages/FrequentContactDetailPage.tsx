import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip,
  Pagination, Spinner,
  Table, TableHeader, TableColumn, TableBody, TableRow, TableCell,
  cn,
} from '@heroui/react';
import type { SortDescriptor } from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import hashtagCircleBold from '@iconify/icons-solar/hashtag-circle-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import starBold from '@iconify/icons-solar/star-bold';
import altArrowLeftBold from '@iconify/icons-solar/alt-arrow-left-bold';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchUserProfile } from '../api/users';
import { ICON_SIZES } from '../constants/iconSizes';

/* ── Constants ──────────────────────────────────────────────────────── */

const ROWS_PER_PAGE = 10;

const TOPIC_COL_STYLES: Record<string, string> = {
  topic:     'w-48 min-w-[12rem]',
  score:     'w-24 min-w-[6rem]',
  last_talk: 'w-44 min-w-[11rem]',
};

const GROUP_COL_STYLES: Record<string, string> = {
  group_id: 'w-64 min-w-[16rem]',
};

const TOPIC_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'topic',     labelKey: 'users.topic',    icon: hashtagCircleBold, sortable: true },
  { key: 'score',     labelKey: 'users.score',    icon: starBold,          sortable: true },
  { key: 'last_talk', labelKey: 'users.lastTalk', icon: clockCircleBold,   sortable: true },
];

const GROUP_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'group_id', labelKey: 'users.groupId', icon: usersGroupRoundedBold, sortable: true },
];

/* ── Component ──────────────────────────────────────────────────────── */

export default function FrequentContactDetailPage() {
  const { t } = useTranslation();
  const { userId, contactId } = useParams<{ userId: string; contactId: string }>();
  const navigate = useNavigate();

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['user_profile', userId],
    queryFn: () => fetchUserProfile(userId!),
    enabled: !!userId,
  });

  const contact = profile?.frequent_contacts?.[contactId ?? ''];

  /* ── Topics table state ─────────────────────────────────────────── */

  const topicRows = useMemo(() => {
    if (!contact) return [];
    return Object.entries(contact.related_topics).map(([topic, stat]) => ({
      topic,
      score: stat.score,
      last_talk: stat.last_talk,
    }));
  }, [contact]);

  const [topicSort, setTopicSort] = useState<SortDescriptor>({ column: 'score', direction: 'descending' });
  const [topicPage, setTopicPage] = useState(1);

  const sortedTopics = useMemo(() => {
    const items = [...topicRows];
    const { column, direction } = topicSort;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => {
      switch (column) {
        case 'score': return (a.score - b.score) * dir;
        case 'topic': return a.topic.localeCompare(b.topic) * dir;
        case 'last_talk': return (new Date(a.last_talk).getTime() - new Date(b.last_talk).getTime()) * dir;
        default: return 0;
      }
    });
    return items;
  }, [topicRows, topicSort]);

  const topicPages = Math.max(1, Math.ceil(sortedTopics.length / ROWS_PER_PAGE));
  const pagedTopics = useMemo(
    () => sortedTopics.slice((topicPage - 1) * ROWS_PER_PAGE, topicPage * ROWS_PER_PAGE),
    [sortedTopics, topicPage],
  );

  useEffect(() => {
    setTopicPage(p => Math.min(Math.max(1, p), topicPages));
  }, [topicPages]);

  /* ── Groups table state ─────────────────────────────────────────── */

  const groupRows = useMemo(() => {
    if (!contact) return [];
    return contact.related_groups.map(g => ({ group_id: g }));
  }, [contact]);

  const [groupSort, setGroupSort] = useState<SortDescriptor>({ column: 'group_id', direction: 'ascending' });
  const [groupPage, setGroupPage] = useState(1);

  const sortedGroups = useMemo(() => {
    const items = [...groupRows];
    const { column, direction } = groupSort;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => a.group_id.localeCompare(b.group_id) * dir);
    return items;
  }, [groupRows, groupSort]);

  const groupPages = Math.max(1, Math.ceil(sortedGroups.length / ROWS_PER_PAGE));
  const pagedGroups = useMemo(
    () => sortedGroups.slice((groupPage - 1) * ROWS_PER_PAGE, groupPage * ROWS_PER_PAGE),
    [sortedGroups, groupPage],
  );

  useEffect(() => {
    setGroupPage(p => Math.min(Math.max(1, p), groupPages));
  }, [groupPages]);

  /* ── Translated columns ─────────────────────────────────────────── */

  const topicColumns = useMemo(
    () => TOPIC_COLUMNS.map(c => ({ ...c, label: t(c.labelKey) })),
    [t],
  );

  const groupColumns = useMemo(
    () => GROUP_COLUMNS.map(c => ({ ...c, label: t(c.labelKey) })),
    [t],
  );

  /* ── Pagination bottom content ──────────────────────────────────── */

  const topicBottom = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: sortedTopics.length })}
      </span>
      <Pagination isCompact showControls page={topicPage} total={topicPages} onChange={setTopicPage} />
    </div>
  ), [sortedTopics.length, topicPage, topicPages, t]);

  const groupBottom = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: sortedGroups.length })}
      </span>
      <Pagination isCompact showControls page={groupPage} total={groupPages} onChange={setGroupPage} />
    </div>
  ), [sortedGroups.length, groupPage, groupPages, t]);

  /* ── Loading / error states ─────────────────────────────────────── */

  if (isLoading) {
    return (
      <div className="flex justify-center h-64">
        <Spinner label={t('users.loading')} />
      </div>
    );
  }

  if (isError || !profile || !contact) {
    return (
      <div className="space-y-4">
        <Button
          variant="light"
          startContent={<Icon icon={altArrowLeftBold} fontSize={ICON_SIZES.button} />}
          onPress={() => navigate(`/users/${encodeURIComponent(userId!)}`)}
        >
          {t('users.backToProfile')}
        </Button>
        <p className="text-danger">{t('users.contactNotFound')}</p>
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
        onPress={() => navigate(`/users/${encodeURIComponent(userId!)}`)}
      >
        {t('users.backToProfile')}
      </Button>

      {/* Contact header card */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-primary-50 dark:bg-primary-900/30">
            <Icon icon={userRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
          </div>
          <div>
            <p className="font-semibold text-lg text-default-900">{contact.name || contactId}</p>
            <p className="text-sm text-default-500">{contactId}</p>
          </div>
          <div className="flex items-center gap-4 ml-auto">
            <Chip size="sm" variant="flat" color="primary" startContent={<Icon icon={chatDotsBold} fontSize={ICON_SIZES.chip} />}>
              {t('users.interactionCount')}: {contact.interaction_count}
            </Chip>
            {contact.last_interact && (
              <Chip size="sm" variant="flat" startContent={<Icon icon={clockCircleBold} fontSize={ICON_SIZES.chip} />}>
                {new Date(contact.last_interact).toLocaleString()}
              </Chip>
            )}
          </div>
        </CardHeader>
      </Card>

      {/* Related topics table */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-default-100">
            <Icon icon={hashtagCircleBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
          </div>
          <p className="font-semibold text-default-900">{t('users.relatedTopics')}</p>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <Table
            aria-label={t('users.relatedTopics')}
            removeWrapper
            isHeaderSticky
            sortDescriptor={topicSort}
            onSortChange={setTopicSort}
            bottomContent={topicBottom}
            classNames={{ sortIcon: 'text-default-500' }}
          >
            <TableHeader columns={topicColumns}>
              {(column) => (
                <TableColumn
                  key={column.key}
                  allowsSorting={column.sortable}
                  className={cn('text-sm md:text-base whitespace-nowrap', TOPIC_COL_STYLES[column.key] ?? '')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />
                    {column.label}
                  </span>
                </TableColumn>
              )}
            </TableHeader>
            <TableBody emptyContent={t('users.noTopics')}>
              {pagedTopics.map(row => (
                <TableRow key={row.topic}>
                  <TableCell className={cn('text-sm font-medium text-default-900', TOPIC_COL_STYLES.topic)}>
                    {row.topic}
                  </TableCell>
                  <TableCell className={cn('text-sm text-default-700', TOPIC_COL_STYLES.score)}>
                    {row.score}
                  </TableCell>
                  <TableCell className={cn('text-xs text-default-400', TOPIC_COL_STYLES.last_talk)}>
                    {new Date(row.last_talk).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardBody>
      </Card>

      {/* Related groups table */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-default-100">
            <Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
          </div>
          <p className="font-semibold text-default-900">{t('users.relatedGroups')}</p>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <Table
            aria-label={t('users.relatedGroups')}
            removeWrapper
            isHeaderSticky
            sortDescriptor={groupSort}
            onSortChange={setGroupSort}
            bottomContent={groupBottom}
            classNames={{ sortIcon: 'text-default-500' }}
          >
            <TableHeader columns={groupColumns}>
              {(column) => (
                <TableColumn
                  key={column.key}
                  allowsSorting={column.sortable}
                  className={cn('text-sm md:text-base whitespace-nowrap', GROUP_COL_STYLES[column.key] ?? '')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />
                    {column.label}
                  </span>
                </TableColumn>
              )}
            </TableHeader>
            <TableBody emptyContent={t('users.noGroups')}>
              {pagedGroups.map(row => (
                <TableRow key={row.group_id}>
                  <TableCell className={cn('text-sm text-default-900', GROUP_COL_STYLES.group_id)}>
                    {row.group_id}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardBody>
      </Card>
    </div>
  );
}
