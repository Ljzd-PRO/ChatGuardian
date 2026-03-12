import { useState, useEffect, useRef, type KeyboardEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, CardHeader, Chip, Divider, Input, Progress, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import addCircleBold from '@iconify/icons-solar/add-circle-bold';
import disketteBold from '@iconify/icons-solar/diskette-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import tuning2Bold from '@iconify/icons-solar/tuning-2-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import { useTranslation } from 'react-i18next';
import { fetchUserProfiles } from '../api/users';
import { fetchSettings, updateSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts';

export default function UserProfilesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  // ── Profiling settings ───────────────────────────────────────────────
  const { data: appSettings, isLoading: settingsLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });
  const [targetUserIds, setTargetUserIds] = useState<string[]>([]);
  const [newUserId, setNewUserId] = useState('');
  const [settingsReady, setSettingsReady] = useState(false);
  const initializedRef = useRef(false);

  // Only sync from server on initial load to avoid overwriting unsaved edits.
  // settingsReady (state) drives the UI; initializedRef guards against double-init in StrictMode.
  useEffect(() => {
    if (appSettings && !initializedRef.current) {
      initializedRef.current = true;
      setTargetUserIds(appSettings.memory_target_user_ids ?? []);
      setSettingsReady(true);
    }
  }, [appSettings]);

  // True while settings data is in flight or the initial sync hasn't run yet
  const isSettingsLoading = settingsLoading || !settingsReady;

  const save = useMutation({
    mutationFn: () => updateSettings({ memory_target_user_ids: targetUserIds }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['settings'] }),
  });

  function addUserId() {
    const trimmed = newUserId.trim();
    if (trimmed && !targetUserIds.includes(trimmed)) {
      setTargetUserIds(ids => [...ids, trimmed]);
      setNewUserId('');
    }
  }

  function removeUserId(id: string) {
    setTargetUserIds(ids => ids.filter(x => x !== id));
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
          <Button
            size="sm"
            color="primary"
            startContent={<Icon icon={disketteBold} fontSize={ICON_SIZES.button} />}
            isLoading={save.isPending}
            isDisabled={isSettingsLoading}
            onPress={() => save.mutate()}
            className="shrink-0"
          >
            {t('common.save')}
          </Button>
        </CardHeader>
        <Divider />
        <CardBody className="space-y-4">
          <div>
            <p className="text-sm font-medium text-default-700 mb-1">
              <Icon icon={usersGroupRoundedBold} fontSize={ICON_SIZES.input} className="inline mr-1.5 text-default-500 align-middle" />
              {t('users.targetUserIds')}
            </p>
            <p className="text-xs text-default-400 mb-3">{t('users.targetUserIdsHint')}</p>

            {/* Active target user IDs */}
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

            {/* Add new user ID */}
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

          {save.isSuccess && <p className="text-success text-sm">{t('common.saveSuccess')}</p>}
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
            const interests = Object.entries(p.interests).map(([, v]) => ({
              topic: v.topic,
              score: Math.round(v.score * 100),
            }));

            return (
              <Card key={p.user_id}>
                <CardHeader className="pb-0 gap-3">
                  <div className="p-1.5 rounded-lg bg-default-100">
                    <Icon icon={userRoundedBold} fontSize={ICON_SIZES.cardHeader} className="text-default-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-default-900">{p.user_name || p.user_id}</p>
                    <p className="text-xs text-default-400">{p.user_id}</p>
                  </div>
                </CardHeader>
                <CardBody className="space-y-3">
                  {interests.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1">{t('users.interests')}</p>
                      <ResponsiveContainer width="100%" height={160}>
                        <RadarChart data={interests}>
                          <PolarGrid />
                          <PolarAngleAxis dataKey="topic" tick={{ fontSize: 11 }} />
                          <Radar dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} />
                          <Tooltip />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {p.active_groups.length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1">{t('users.activeGroups')}</p>
                      <div className="flex flex-wrap gap-1">
                        {p.active_groups.map(g => (
                          <Chip key={g.chat_id} size="sm" variant="flat">
                            {g.chat_name || g.chat_id} ({g.message_count})
                          </Chip>
                        ))}
                      </div>
                    </div>
                  )}

                  {Object.keys(p.frequent_contacts).length > 0 && (
                    <div>
                      <p className="text-xs font-medium text-default-600 mb-1">{t('users.frequentContacts')}</p>
                      <div className="space-y-1">
                        {Object.values(p.frequent_contacts).slice(0, 3).map(c => (
                          <div key={c.user_id} className="flex items-center justify-between text-xs">
                            <span className="text-default-700">{c.display_name || c.user_id}</span>
                            <Progress size="sm" value={c.interaction_count} maxValue={100} className="w-20" aria-label={t('users.interaction')} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardBody>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
