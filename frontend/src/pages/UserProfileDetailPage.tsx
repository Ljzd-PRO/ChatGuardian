import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip,
  Modal, ModalBody, ModalContent, ModalFooter, ModalHeader,
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
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  fetchUserProfile,
  deleteProfileInterest,
  deleteProfileInterestChat,
  deleteProfileInterestKeyword,
  deleteProfileActiveGroup,
  deleteProfileContact,
  deleteProfileContactTopic,
  deleteProfileContactGroup,
} from '../api/users';
import { ICON_SIZES } from '../constants/iconSizes';
import { parseBackendDate } from '../utils/dates';

/* ── Constants ──────────────────────────────────────────────────────── */
const MAX_VISIBLE_ACTIVE_GROUP_CHIPS = 20;

const MAX_CONTACT_GROUP_CHIPS = 3;
const ROWS_PER_PAGE = 10;

const INTEREST_COL_STYLES: Record<string, string> = {
  topic:        'w-28 min-w-[7rem]',
  score:        'w-20 min-w-[5rem]',
  last_active:  'w-28 min-w-[7rem]',
  related_chat: 'w-40 min-w-[10rem]',
  keywords:     'w-40 min-w-[10rem]',
  actions:      'w-16 min-w-[4rem]',
};

const CONTACT_COL_STYLES: Record<string, string> = {
  contact_id:        'w-28 min-w-[7rem]',
  name:              'w-28 min-w-[7rem]',
  interaction_count: 'w-24 min-w-[6rem]',
  last_interact:     'w-28 min-w-[7rem]',
  related_topics:    'w-40 min-w-[10rem]',
  related_groups:    'w-36 min-w-[9rem]',
  actions:           'w-16 min-w-[4rem]',
};

const INTEREST_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'topic',        labelKey: 'users.topic',       icon: hashtagCircleBold, sortable: false },
  { key: 'score',        labelKey: 'users.score',       icon: starBold,          sortable: true },
  { key: 'last_active',  labelKey: 'users.lastActive',  icon: clockCircleBold,   sortable: true },
  { key: 'related_chat', labelKey: 'users.relatedChat', icon: chatDotsBold,      sortable: false },
  { key: 'keywords',     labelKey: 'users.keywords',    icon: tagBold,           sortable: false },
  { key: 'actions',      labelKey: 'common.actions',    icon: trashBin2Bold,     sortable: false },
];

const CONTACT_COLUMNS: { key: string; labelKey: string; icon: IconifyIcon; sortable: boolean }[] = [
  { key: 'contact_id',        labelKey: 'users.contactId',        icon: userRoundedBold,       sortable: true },
  { key: 'name',              labelKey: 'users.contactName',      icon: userRoundedBold,       sortable: true },
  { key: 'interaction_count', labelKey: 'users.interactionCount', icon: chatDotsBold,          sortable: true },
  { key: 'last_interact',     labelKey: 'users.lastInteract',     icon: clockCircleBold,       sortable: false },
  { key: 'related_topics',    labelKey: 'users.relatedTopics',    icon: hashtagCircleBold,     sortable: false },
  { key: 'related_groups',    labelKey: 'users.relatedGroups',    icon: usersGroupRoundedBold, sortable: false },
  { key: 'actions',           labelKey: 'common.actions',         icon: trashBin2Bold,         sortable: false },
];

/* ── Delete target type ─────────────────────────────────────────────── */

type DeleteTarget =
  | { kind: 'interest';        topic: string }
  | { kind: 'group';           groupId: string }
  | { kind: 'contact';         contactId: string }
  | { kind: 'interest_chat';   topic: string; chatId: string }
  | { kind: 'interest_kw';     topic: string; keyword: string }
  | { kind: 'contact_topic';   contactId: string; topic: string }
  | { kind: 'contact_group';   contactId: string; groupId: string };

/* ── Component ──────────────────────────────────────────────────────── */

export default function UserProfileDetailPage() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['user_profile', userId],
    queryFn: () => fetchUserProfile(userId!),
    enabled: !!userId,
  });

  /* ── Delete state ───────────────────────────────────────────────── */

  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteError, setDeleteError] = useState(false);

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['user_profile', userId] });
    queryClient.invalidateQueries({ queryKey: ['user_profiles'] });
    setDeleteTarget(null);
    setDeleteError(false);
  }, [queryClient, userId]);

  const onError = useCallback(() => setDeleteError(true), []);

  const delInterest       = useMutation({ mutationFn: (topic: string)                              => deleteProfileInterest(userId!, topic),                       onSuccess: invalidate, onError });
  const delGroup          = useMutation({ mutationFn: (groupId: string)                            => deleteProfileActiveGroup(userId!, groupId),                  onSuccess: invalidate, onError });
  const delContact        = useMutation({ mutationFn: (contactId: string)                          => deleteProfileContact(userId!, contactId),                    onSuccess: invalidate, onError });
  const delInterestChat   = useMutation({ mutationFn: ({ topic, chatId }: { topic: string; chatId: string })           => deleteProfileInterestChat(userId!, topic, chatId),           onSuccess: invalidate, onError });
  const delInterestKw     = useMutation({ mutationFn: ({ topic, keyword }: { topic: string; keyword: string })         => deleteProfileInterestKeyword(userId!, topic, keyword),        onSuccess: invalidate, onError });
  const delContactTopic   = useMutation({ mutationFn: ({ contactId, topic }: { contactId: string; topic: string })     => deleteProfileContactTopic(userId!, contactId, topic),         onSuccess: invalidate, onError });
  const delContactGroup   = useMutation({ mutationFn: ({ contactId, groupId }: { contactId: string; groupId: string }) => deleteProfileContactGroup(userId!, contactId, groupId),       onSuccess: invalidate, onError });

  const isDeletePending =
    delInterest.isPending || delGroup.isPending || delContact.isPending ||
    delInterestChat.isPending || delInterestKw.isPending ||
    delContactTopic.isPending || delContactGroup.isPending;

  function confirmDelete() {
    if (!deleteTarget) return;
    setDeleteError(false);
    switch (deleteTarget.kind) {
      case 'interest':       delInterest.mutate(deleteTarget.topic);                                                                     break;
      case 'group':          delGroup.mutate(deleteTarget.groupId);                                                                      break;
      case 'contact':        delContact.mutate(deleteTarget.contactId);                                                                  break;
      case 'interest_chat':  delInterestChat.mutate({ topic: deleteTarget.topic, chatId: deleteTarget.chatId });                        break;
      case 'interest_kw':    delInterestKw.mutate({ topic: deleteTarget.topic, keyword: deleteTarget.keyword });                        break;
      case 'contact_topic':  delContactTopic.mutate({ contactId: deleteTarget.contactId, topic: deleteTarget.topic });                  break;
      case 'contact_group':  delContactGroup.mutate({ contactId: deleteTarget.contactId, groupId: deleteTarget.groupId });              break;
    }
  }

  function deleteConfirmText(): string {
    if (!deleteTarget) return '';
    switch (deleteTarget.kind) {
      case 'interest':       return t('users.deleteInterestConfirm',      { item: deleteTarget.topic });
      case 'group':          return t('users.deleteGroupConfirm',         { item: deleteTarget.groupId });
      case 'contact':        return t('users.deleteContactConfirm',       { item: deleteTarget.contactId });
      case 'interest_chat':  return t('users.deleteChatConfirm',         { item: deleteTarget.chatId,  parent: deleteTarget.topic });
      case 'interest_kw':    return t('users.deleteKeywordConfirm',      { item: deleteTarget.keyword, parent: deleteTarget.topic });
      case 'contact_topic':  return t('users.deleteContactTopicConfirm', { item: deleteTarget.topic,   parent: deleteTarget.contactId });
      case 'contact_group':  return t('users.deleteContactGroupConfirm', { item: deleteTarget.groupId, parent: deleteTarget.contactId });
    }
  }

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
          return (parseBackendDate(a.last_active).getTime() - parseBackendDate(b.last_active).getTime()) * dir;
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
        case 'contact_id':
          return a.contactId.localeCompare(b.contactId) * dir;
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
              {profile.active_groups
                .slice(0, MAX_VISIBLE_ACTIVE_GROUP_CHIPS)
                .map(g => (
                  <Chip
                    key={g.group_id}
                    size="sm"
                    variant="flat"
                    startContent={
                      <Icon
                        icon={usersGroupRoundedBold}
                        fontSize={ICON_SIZES.chip}
                        className="text-default-500"
                      />
                    }
                    onClose={() => setDeleteTarget({ kind: 'group', groupId: g.group_id })}
                  >
                    {g.group_id}
                  </Chip>
                ))}
              {profile.active_groups.length > MAX_VISIBLE_ACTIVE_GROUP_CHIPS && (
                <Chip
                  size="sm"
                  variant="flat"
                >
                  {`+${profile.active_groups.length - MAX_VISIBLE_ACTIVE_GROUP_CHIPS} more`}
                </Chip>
              )}
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
                    {parseBackendDate(row.last_active).toLocaleString()}
                  </TableCell>
                  <TableCell className={INTEREST_COL_STYLES.related_chat}>
                    <div className="flex flex-wrap gap-1">
                      {row.related_chat.map(chat => (
                        <Chip
                          key={chat}
                          size="sm"
                          variant="flat"
                          startContent={<Icon icon={chatDotsBold} fontSize={ICON_SIZES.chip} />}
                          onClose={() => setDeleteTarget({ kind: 'interest_chat', topic: row.topic, chatId: chat })}
                        >
                          {chat}
                        </Chip>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className={INTEREST_COL_STYLES.keywords}>
                    <div className="flex flex-wrap gap-1">
                      {row.keywords.map(kw => (
                        <Chip
                          key={kw}
                          size="sm"
                          variant="flat"
                          color="secondary"
                          startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.chip} />}
                          onClose={() => setDeleteTarget({ kind: 'interest_kw', topic: row.topic, keyword: kw })}
                        >
                          {kw}
                        </Chip>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className={INTEREST_COL_STYLES.actions}>
                    <Button
                      isIconOnly
                      size="sm"
                      variant="light"
                      color="danger"
                      aria-label={t('common.delete')}
                      onPress={() => setDeleteTarget({ kind: 'interest', topic: row.topic })}
                    >
                      <Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />
                    </Button>
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
              {pagedContacts.map(row => {
                const displayedGroups = row.related_groups.slice(0, MAX_CONTACT_GROUP_CHIPS);
                const remainingGroupCount = row.related_groups.length - displayedGroups.length;

                return (
                  <TableRow key={row.contactId}>
                    <TableCell className={cn('text-sm font-medium', CONTACT_COL_STYLES.contact_id)}>
                      <Link
                        to={`/users/${encodeURIComponent(userId!)}/contacts/${encodeURIComponent(row.contactId)}`}
                        className="text-primary hover:underline font-mono text-xs"
                      >
                        {row.contactId}
                      </Link>
                    </TableCell>
                    <TableCell className={cn('text-sm text-default-700', CONTACT_COL_STYLES.name)}>
                      {row.name || <span className="text-default-400 italic">—</span>}
                    </TableCell>
                    <TableCell className={cn('text-sm text-default-700', CONTACT_COL_STYLES.interaction_count)}>
                      {row.interaction_count}
                    </TableCell>
                    <TableCell className={cn('text-xs text-default-400', CONTACT_COL_STYLES.last_interact)}>
                      {parseBackendDate(row.last_interact).toLocaleString()}
                    </TableCell>
                    <TableCell className={CONTACT_COL_STYLES.related_topics}>
                      <div className="flex flex-wrap gap-1">
                        {row.sortedTopics.map(tp => (
                          <Chip
                            key={tp.topic}
                            size="sm"
                            variant="flat"
                            startContent={<Icon icon={hashtagCircleBold} fontSize={ICON_SIZES.chip} />}
                            onClose={() => setDeleteTarget({ kind: 'contact_topic', contactId: row.contactId, topic: tp.topic })}
                          >
                            {tp.topic}
                          </Chip>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className={CONTACT_COL_STYLES.related_groups}>
                      <div className="flex flex-wrap gap-1">
                        {displayedGroups.map(g => (
                          <Chip
                            key={g}
                            size="sm"
                            variant="flat"
                            startContent={<Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.chip} />}
                            onClose={() => setDeleteTarget({ kind: 'contact_group', contactId: row.contactId, groupId: g })}
                          >
                            {g}
                          </Chip>
                        ))}
                        {remainingGroupCount > 0 && (
                          <Chip
                            size="sm"
                            variant="flat"
                          >
                            +{remainingGroupCount}
                          </Chip>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className={CONTACT_COL_STYLES.actions}>
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="danger"
                        aria-label={t('common.delete')}
                        onPress={() => setDeleteTarget({ kind: 'contact', contactId: row.contactId })}
                      >
                        <Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardBody>
      </Card>

      {/* Delete confirmation modal */}
      <Modal
        isOpen={!!deleteTarget}
        onClose={() => { setDeleteTarget(null); setDeleteError(false); }}
        size="md"
      >
        <ModalContent>
          <ModalHeader className="flex items-center gap-2 text-danger">
            <Icon icon={trashBin2Bold} fontSize={ICON_SIZES.cardHeader} />
            {t('users.deleteItemTitle')}
          </ModalHeader>
          <ModalBody>
            <p className="text-default-600">{deleteConfirmText()}</p>
            {deleteError && (
              <p className="text-danger text-sm mt-2">{t('users.deleteFailed')}</p>
            )}
          </ModalBody>
          <ModalFooter>
            <Button
              variant="flat"
              onPress={() => { setDeleteTarget(null); setDeleteError(false); }}
              isDisabled={isDeletePending}
            >
              {t('common.cancel')}
            </Button>
            <Button
              color="danger"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
              isLoading={isDeletePending}
              onPress={confirmDelete}
            >
              {t('common.delete')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}

