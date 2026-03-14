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
import tagBold from '@iconify/icons-solar/tag-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import starBold from '@iconify/icons-solar/star-bold';
import altArrowLeftBold from '@iconify/icons-solar/alt-arrow-left-bold';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { fetchUserProfile } from '../api/users';
import { ICON_SIZES } from '../constants/iconSizes';

/* ── Constants ──────────────────────────────────────────────────────── */

const ROWS_PER_PAGE = 10;

const INTEREST_COL_STYLES: Record<string, string> = {
  topic:        'w-40 min-w-[10rem]',
  score:        'w-24 min-w-[6rem]',
  last_active:  'w-40 min-w-[10rem]',
  related_chat: 'w-64 min-w-[16rem]',
  keywords:     'w-64 min-w-[16rem]',
};

const CONTACT_COL_STYLES: Record<string, string> = {
  name:              'w-40 min-w-[10rem]',
  interaction_count: 'w-32 min-w-[8rem]',
  last_interact:     'w-40 min-w-[10rem]',
  related_topics:    'w-64 min-w-[16rem]',
  related_groups:    'w-48 min-w-[12rem]',
};

const INTEREST_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'topic',        labelKey: 'users.topic',       icon: hashtagCircleBold, sortable: false },
  { key: 'score',        labelKey: 'users.score',       icon: starBold,          sortable: true },
  { key: 'last_active',  labelKey: 'users.lastActive',  icon: clockCircleBold,   sortable: true },
  { key: 'related_chat', labelKey: 'users.relatedChat', icon: chatDotsBold,      sortable: false },
  { key: 'keywords',     labelKey: 'users.keywords',    icon: tagBold,           sortable: false },
];

const CONTACT_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'name',              labelKey: 'users.contactName',      icon: userRoundedBold,       sortable: true },
  { key: 'interaction_count', labelKey: 'users.interactionCount', icon: chatDotsBold,          sortable: true },
  { key: 'last_interact',     labelKey: 'users.lastInteract',     icon: clockCircleBold,       sortable: false },
  { key: 'related_topics',    labelKey: 'users.relatedTopics',    icon: hashtagCircleBold,     sortable: false },
  { key: 'related_groups',    labelKey: 'users.relatedGroups',    icon: usersGroupRoundedBold, sortable: false },
];

/* ── Component ──────────────────────────────────────────────────────── */

export default function UserProfileDetailPage() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['user_profile', userId],
    queryFn: () => fetchUserProfile(userId!),
    enabled: !!userId,
  });

  /* ── Interest table state ───────────────────────────────────────── */

  const interestRows = useMemo(() => {
    if (!profile) return [];
    return Object.entries(profile.interests).map(([topic, stat]) => ({
      topic,
      ...stat,
    }));
  }, [profile]);

  const [interestSort, setInterestSort] = useState<SortDescriptor>({
    column: 'score',
    direction: 'descending',
  });
  const [interestPage, setInterestPage] = useState(1);

  const sortedInterests = useMemo(() => {
    const items = [...interestRows];
    const { column, direction } = interestSort;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => {
      switch (column) {
        case 'score':
          return (a.score - b.score) * dir;
        case 'last_active':
          return (new Date(a.last_active).getTime() - new Date(b.last_active).getTime()) * dir;
        default:
          return 0;
      }
    });
    return items;
  }, [interestRows, interestSort]);

  const interestPages = Math.max(1, Math.ceil(sortedInterests.length / ROWS_PER_PAGE));
  const pagedInterests = useMemo(
    () => sortedInterests.slice((interestPage - 1) * ROWS_PER_PAGE, interestPage * ROWS_PER_PAGE),
    [sortedInterests, interestPage],
  );

  useEffect(() => {
    setInterestPage(p => Math.min(Math.max(1, p), interestPages));
  }, [interestPages]);

  /* ── Contact table state ────────────────────────────────────────── */

  const contactRows = useMemo(() => {
    if (!profile) return [];
    return Object.entries(profile.frequent_contacts).map(([contactId, stat]) => ({
      contactId,
      ...stat,
      sortedTopics: Object.entries(stat.related_topics)
        .map(([topic, ts]) => ({ topic, score: ts.score }))
        .sort((a, b) => b.score - a.score),
    }));
  }, [profile]);

  const [contactSort, setContactSort] = useState<SortDescriptor>({
    column: 'interaction_count',
    direction: 'descending',
  });
  const [contactPage, setContactPage] = useState(1);

  const sortedContacts = useMemo(() => {
    const items = [...contactRows];
    const { column, direction } = contactSort;
    if (!column) return items;
    const dir = direction === 'descending' ? -1 : 1;
    items.sort((a, b) => {
      switch (column) {
        case 'interaction_count':
          return (a.interaction_count - b.interaction_count) * dir;
        case 'name':
          return a.name.localeCompare(b.name) * dir;
        default:
          return 0;
      }
    });
    return items;
  }, [contactRows, contactSort]);

  const contactPages = Math.max(1, Math.ceil(sortedContacts.length / ROWS_PER_PAGE));
  const pagedContacts = useMemo(
    () => sortedContacts.slice((contactPage - 1) * ROWS_PER_PAGE, contactPage * ROWS_PER_PAGE),
    [sortedContacts, contactPage],
  );

  useEffect(() => {
    setContactPage(p => Math.min(Math.max(1, p), contactPages));
  }, [contactPages]);

  /* ── Translated column arrays ───────────────────────────────────── */

  const interestColumns = useMemo(
    () => INTEREST_COLUMNS.map(c => ({ ...c, label: t(c.labelKey) })),
    [t],
  );

  const contactColumns = useMemo(
    () => CONTACT_COLUMNS.map(c => ({ ...c, label: t(c.labelKey) })),
    [t],
  );

  /* ── Pagination bottom content ──────────────────────────────────── */

  const interestBottom = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: sortedInterests.length })}
      </span>
      <Pagination isCompact showControls page={interestPage} total={interestPages} onChange={setInterestPage} />
    </div>
  ), [sortedInterests.length, interestPage, interestPages, t]);

  const contactBottom = useMemo(() => (
    <div className="flex items-center justify-between px-2 py-2">
      <span className="text-xs text-default-500">
        {t('common.entries', { count: sortedContacts.length })}
      </span>
      <Pagination isCompact showControls page={contactPage} total={contactPages} onChange={setContactPage} />
    </div>
  ), [sortedContacts.length, contactPage, contactPages, t]);

  /* ── Loading / error states ─────────────────────────────────────── */

  if (isLoading) {
    return (
      <div className="flex justify-center h-64">
        <Spinner label={t('users.loading')} />
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="space-y-4">
        <Button
          variant="light"
          startContent={<Icon icon={altArrowLeftBold} fontSize={ICON_SIZES.button} />}
          onPress={() => navigate('/users')}
        >
          {t('users.backToList')}
        </Button>
        <p className="text-danger">{t('users.loadError')}</p>
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
        onPress={() => navigate('/users')}
      >
        {t('users.backToList')}
      </Button>

      {/* Header card */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-primary-50 dark:bg-primary-900/30">
            <Icon icon={userRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
          </div>
          <div>
            <p className="font-semibold text-lg text-default-900">
              {profile.user_name || profile.user_id}
            </p>
            <p className="text-sm text-default-500">{profile.user_id}</p>
          </div>
        </CardHeader>
      </Card>

      {/* Active groups */}
      {profile.active_groups.length > 0 && (
        <Card>
          <CardHeader className="gap-3">
            <div className="p-2 rounded-lg bg-default-100">
              <Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
            </div>
            <p className="font-semibold text-default-900">{t('users.activeGroups')}</p>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-2">
              {profile.active_groups.slice(0, 10).map(g => (
                <Chip
                  key={g.group_id}
                  size="sm"
                  variant="flat"
                  startContent={<Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.chip} className="text-default-500" />}
                >
                  {g.group_id}
                </Chip>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Interests table */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-default-100">
            <Icon icon={starBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
          </div>
          <p className="font-semibold text-default-900">{t('users.interests')}</p>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <Table
            aria-label={t('users.interests')}
            removeWrapper
            isHeaderSticky
            sortDescriptor={interestSort}
            onSortChange={setInterestSort}
            bottomContent={interestBottom}
            classNames={{ sortIcon: 'text-default-500' }}
          >
            <TableHeader columns={interestColumns}>
              {(column) => (
                <TableColumn
                  key={column.key}
                  allowsSorting={column.sortable}
                  className={cn('text-sm md:text-base whitespace-nowrap', INTEREST_COL_STYLES[column.key] ?? '')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />
                    {column.label}
                  </span>
                </TableColumn>
              )}
            </TableHeader>
            <TableBody emptyContent={t('users.noInterests')}>
              {pagedInterests.map(row => (
                <TableRow key={row.topic}>
                  <TableCell className={cn('text-sm font-medium text-default-900', INTEREST_COL_STYLES.topic)}>
                    {row.topic}
                  </TableCell>
                  <TableCell className={cn('text-sm text-default-700', INTEREST_COL_STYLES.score)}>
                    {row.score.toFixed(2)}
                  </TableCell>
                  <TableCell className={cn('text-xs text-default-400', INTEREST_COL_STYLES.last_active)}>
                    {new Date(row.last_active).toLocaleString()}
                  </TableCell>
                  <TableCell className={INTEREST_COL_STYLES.related_chat}>
                    <div className="flex flex-wrap gap-1">
                      {row.related_chat.slice(0, 5).map(chat => (
                        <Chip key={chat} size="sm" variant="flat" startContent={<Icon icon={chatDotsBold} fontSize={ICON_SIZES.chip} />}>
                          {chat}
                        </Chip>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className={INTEREST_COL_STYLES.keywords}>
                    <div className="flex flex-wrap gap-1">
                      {row.keywords.slice(0, 5).map(kw => (
                        <Chip key={kw} size="sm" variant="flat" color="secondary" startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.chip} />}>
                          {kw}
                        </Chip>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardBody>
      </Card>

      {/* Frequent contacts table */}
      <Card>
        <CardHeader className="gap-3">
          <div className="p-2 rounded-lg bg-default-100">
            <Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
          </div>
          <p className="font-semibold text-default-900">{t('users.frequentContacts')}</p>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <Table
            aria-label={t('users.frequentContacts')}
            removeWrapper
            isHeaderSticky
            sortDescriptor={contactSort}
            onSortChange={setContactSort}
            bottomContent={contactBottom}
            classNames={{ sortIcon: 'text-default-500' }}
          >
            <TableHeader columns={contactColumns}>
              {(column) => (
                <TableColumn
                  key={column.key}
                  allowsSorting={column.sortable}
                  className={cn('text-sm md:text-base whitespace-nowrap', CONTACT_COL_STYLES[column.key] ?? '')}
                >
                  <span className="inline-flex items-center gap-1">
                    <Icon icon={column.icon} fontSize={ICON_SIZES.input} className="text-default-500" />
                    {column.label}
                  </span>
                </TableColumn>
              )}
            </TableHeader>
            <TableBody emptyContent={t('users.noContacts')}>
              {pagedContacts.map(row => (
                <TableRow key={row.contactId}>
                  <TableCell className={cn('text-sm font-medium', CONTACT_COL_STYLES.name)}>
                    <Link
                      to={`/users/${encodeURIComponent(userId!)}/contacts/${encodeURIComponent(row.contactId)}`}
                      className="text-primary hover:underline"
                    >
                      {row.name}
                    </Link>
                  </TableCell>
                  <TableCell className={cn('text-sm text-default-700', CONTACT_COL_STYLES.interaction_count)}>
                    {row.interaction_count}
                  </TableCell>
                  <TableCell className={cn('text-xs text-default-400', CONTACT_COL_STYLES.last_interact)}>
                    {new Date(row.last_interact).toLocaleString()}
                  </TableCell>
                  <TableCell className={CONTACT_COL_STYLES.related_topics}>
                    <div className="flex flex-wrap gap-1">
                      {row.sortedTopics.slice(0, 5).map(tp => (
                        <Chip key={tp.topic} size="sm" variant="flat" startContent={<Icon icon={hashtagCircleBold} fontSize={ICON_SIZES.chip} />}>
                          {tp.topic}
                        </Chip>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className={CONTACT_COL_STYLES.related_groups}>
                    <div className="flex flex-wrap gap-1">
                      {row.related_groups.slice(0, 3).map(g => (
                        <Chip key={g} size="sm" variant="flat" startContent={<Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.chip} />}>
                          {g}
                        </Chip>
                      ))}
                    </div>
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
