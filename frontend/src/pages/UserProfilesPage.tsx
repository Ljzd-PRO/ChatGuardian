import { useState, useEffect, useRef, type KeyboardEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Modal, ModalBody,
  ModalContent, ModalFooter, ModalHeader, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import addCircleBold from '@iconify/icons-solar/add-circle-bold';
import hashtagCircleBold from '@iconify/icons-solar/hashtag-circle-bold';
import starBold from '@iconify/icons-solar/star-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import tuning2Bold from '@iconify/icons-solar/tuning-2-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { fetchUserProfiles, deleteUserProfile } from '../api/users';
import { fetchSettings, updateSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';

export default function UserProfilesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // ── Profiling settings ───────────────────────────────────────────────
  const { data: appSettings, isLoading: settingsLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [targetUserIds, setTargetUserIds] = useState<string[]>([]);
  const [newUserId, setNewUserId] = useState('');
  const [settingsReady, setSettingsReady] = useState(false);
  const initializedRef = useRef(false);

  useEffect(() => {
    if (appSettings && !initializedRef.current) {
      initializedRef.current = true;
      setTargetUserIds(appSettings.memory_target_user_ids ?? []);
      setSettingsReady(true);
    }
  }, [appSettings]);

  const isSettingsLoading = settingsLoading || !settingsReady;

  const save = useMutation({
    mutationFn: (ids: string[]) => updateSettings({ memory_target_user_ids: ids }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  function addUserId() {
    const trimmed = newUserId.trim();
    if (!trimmed) return;
    setTargetUserIds(prev => {
      if (prev.includes(trimmed)) return prev;
      const next = [...prev, trimmed];
      save.mutate(next);
      return next;
    });
    setNewUserId('');
  }

  function removeUserId(id: string) {
    setTargetUserIds(prev => {
      const next = prev.filter(x => x !== id);
      save.mutate(next);
      return next;
    });
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') addUserId();
  }

  const trimmedNewUserId = newUserId.trim();

  // ── Profile list ─────────────────────────────────────────────────────
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['user_profiles'],
    queryFn: fetchUserProfiles,
  });
  const [search, setSearch] = useState('');

  const filtered = (profiles ?? []).filter(p =>
    p.user_name.toLowerCase().includes(search.toLowerCase()) ||
    p.user_id.toLowerCase().includes(search.toLowerCase()),
  );

  // ── Delete profile ──────────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const deleteProfile = useMutation({
    mutationFn: (userId: string) => deleteUserProfile(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user_profiles'] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="space-y-6 max-w-4xl">

      {/* ── Profiling Settings Card ───────────────────────────────────── */}
      <Card>
        <CardHeader className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary-50 dark:bg-primary-900/30">
              <Icon icon={tuning2Bold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
            </div>
            <div>
              <p className="font-semibold text-default-900">{t('users.settingsTitle')}</p>
              <p className="text-sm text-default-500">{t('users.settingsDescription')}</p>
            </div>
          </div>
          {save.isPending && <Spinner size="sm" />}
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          <div>
            <p className="text-sm font-medium text-default-700 mb-1">
              <Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.input} className="inline mr-1.5 text-default-500 align-middle" />
              {t('users.targetUserIds')}
            </p>
            <p className="text-xs text-default-400 mb-3">{t('users.targetUserIdsHint')}</p>

            {isSettingsLoading ? (
              <div className="mb-3">
                <Spinner size="sm" />
              </div>
            ) : targetUserIds.length === 0 ? (
              <div className="mb-3">
                <Chip size="sm" variant="flat" color="warning" startContent={<Icon icon={usersGroupRoundedBold} fontSize={14} />}>
                  {t('users.profilingDisabled')}
                </Chip>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 mb-3">
                {targetUserIds.map(id => (
                  <Chip
                    key={id}
                    size="sm"
                    variant="flat"
                    color="primary"
                    onClose={() => removeUserId(id)}
                  >
                    {id}
                  </Chip>
                ))}
              </div>
            )}

            <div className="flex gap-2 max-w-md">
              <Input
                size="sm"
                placeholder={t('users.addUserIdPlaceholder')}
                startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
                value={newUserId}
                onValueChange={setNewUserId}
                onKeyDown={handleKeyDown}
                isDisabled={isSettingsLoading}
              />
              <Button
                size="sm"
                variant="flat"
                color="primary"
                startContent={<Icon icon={addCircleBold} fontSize={ICON_SIZES.button} />}
                onPress={addUserId}
                isDisabled={isSettingsLoading || trimmedNewUserId === ''}
              >
                {t('common.add')}
              </Button>
            </div>
          </div>

          {save.isSuccess && <p className="text-success text-sm">{t('common.saved')}</p>}
          {save.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
        </CardBody>
      </Card>

      {/* ── Profile List ─────────────────────────────────────────────── */}
      <div className="space-y-4">
        <Input
          placeholder={t('users.searchPlaceholder')}
          value={search}
          onValueChange={setSearch}
          startContent={<Icon icon={textFieldFocusBold} fontSize={ICON_SIZES.input} className="text-default-500" />}
          className="max-w-sm"
        />

        {isLoading && (
          <div className="flex justify-center h-32">
            <Spinner label={t('users.loading')} />
          </div>
        )}

        {!isLoading && filtered.length === 0 && (
          <p className="text-default-400 text-sm">{t('users.noProfiles')}</p>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map(p => {
            const topInterests = Object.entries(p.interests)
              .map(([topic, stat]) => ({ topic, score: stat.score }))
              .sort((a, b) => b.score - a.score)
              .slice(0, 5);

            const topGroups = p.active_groups.slice(0, 5);

            const topContacts = Object.entries(p.frequent_contacts)
              .map(([uid, stat]) => ({ uid, name: stat.name, count: stat.interaction_count }))
              .sort((a, b) => b.count - a.count)
              .slice(0, 5);

            return (
              <Card
                key={p.user_id}
                className="w-full transition-shadow hover:shadow-md"
              >
                <div
                  className="cursor-pointer"
                  onClick={() => navigate(`/users/${encodeURIComponent(p.user_id)}`)}
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/users/${encodeURIComponent(p.user_id)}`); } }}
                >
                <CardHeader className="pb-0 gap-3 flex items-start justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-1.5 rounded-lg bg-primary-50 dark:bg-primary-900/30 shrink-0">
                      <Icon icon={userRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-primary truncate">
                        {p.user_name || p.user_id}
                      </p>
                      <p className="text-xs text-default-400 truncate font-mono">{p.user_id}</p>
                    </div>
                  </div>
                  <Button
                    isIconOnly
                    size="sm"
                    variant="light"
                    color="danger"
                    onPress={() => setDeleteTarget(p.user_id)}
                    onClick={e => e.stopPropagation()}
                    aria-label={t('common.delete')}
                  >
                    <Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />
                  </Button>
                </CardHeader>
                <CardBody className="space-y-3">
                  {topInterests.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1.5">
                        <Icon icon={starBold} fontSize={12} className="inline mr-1 text-default-500 align-middle" />
                        {t('users.interests')}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {topInterests.map(i => (
                          <Chip
                            key={i.topic}
                            size="sm"
                            variant="flat"
                            color="secondary"
                            startContent={<Icon icon={hashtagCircleBold} fontSize={ICON_SIZES.chip} />}
                          >
                            {i.topic} ({i.score.toFixed(1)})
                          </Chip>
                        ))}
                      </div>
                    </div>
                  )}

                  {topGroups.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1.5">
                        <Icon icon={usersGroupRoundedBold} fontSize={12} className="inline mr-1 text-default-500 align-middle" />
                        {t('users.activeGroups')}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {topGroups.map(g => (
                          <Chip
                            key={g.group_id}
                            size="sm"
                            variant="flat"
                            startContent={<Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.chip} />}
                          >
                            {g.group_id}
                          </Chip>
                        ))}
                      </div>
                    </div>
                  )}

                  {topContacts.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1.5">
                        <Icon icon={chatDotsBold} fontSize={12} className="inline mr-1 text-default-500 align-middle" />
                        {t('users.frequentContacts')}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {topContacts.map(c => (
                          <Chip
                            key={c.uid}
                            size="sm"
                            variant="flat"
                            color="primary"
                            startContent={<Icon icon={userRoundedBold} fontSize={ICON_SIZES.chip} />}
                          >
                            {c.name || c.uid} ({c.count})
                          </Chip>
                        ))}
                      </div>
                    </div>
                  )}
                </CardBody>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Delete confirmation modal */}
      <Modal isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} size="md">
        <ModalContent>
          <ModalHeader>{t('users.deleteProfileTitle')}</ModalHeader>
          <ModalBody>
            <p className="text-default-600">
              {t('users.deleteProfileConfirm', { userId: deleteTarget })}
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={() => setDeleteTarget(null)}>{t('common.cancel')}</Button>
            <Button
              color="danger"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
              isLoading={deleteProfile.isPending}
              onPress={() => deleteTarget && deleteProfile.mutate(deleteTarget)}
            >
              {t('common.delete')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}
