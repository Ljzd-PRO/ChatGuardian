import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Accordion, AccordionItem, Button, Card, CardBody, Checkbox, Chip, Input, Modal, ModalBody,
  ModalContent, ModalFooter, ModalHeader, Select, SelectItem, Spinner, Switch, Slider, Textarea, Tooltip,
} from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import addCircleBold from '@iconify/icons-solar/add-circle-bold';
import alignLeftBold from '@iconify/icons-solar/align-left-bold';
import bellBingBold from '@iconify/icons-solar/bell-bing-bold';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import checkCircleBold from '@iconify/icons-solar/check-circle-bold';
import checkSquareBold from '@iconify/icons-solar/check-square-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import closeCircleBold from '@iconify/icons-solar/close-circle-bold';
import eyeBold from '@iconify/icons-solar/eye-bold';
import filterBold from '@iconify/icons-solar/filter-bold';
import hashtagCircleBold from '@iconify/icons-solar/hashtag-circle-bold';
import listCheckBold from '@iconify/icons-solar/list-check-bold';
import magicStick2Bold from '@iconify/icons-solar/magic-stick-2-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import pen2Bold from '@iconify/icons-solar/pen-2-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import pulse2Bold from '@iconify/icons-solar/pulse-2-bold';
import settingsBold from '@iconify/icons-solar/settings-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import tuning2Bold from '@iconify/icons-solar/tuning-2-bold';
import userRoundedBold from '@iconify/icons-solar/user-rounded-bold';
import usersGroupRoundedBold from '@iconify/icons-solar/users-group-rounded-bold';
import { useTranslation } from 'react-i18next';
import { fetchRules, upsertRule, deleteRule } from '../api/rules';
import type {
  DetectionRule, MatcherType, MatcherUnion, RuleParameterSpec,
  MatchAdapter, MatchChatInfo, MatchChatType, MatchMention, MatchSender,
} from '../api/types';
import MatcherEditor from '../components/matcher/MatcherEditor';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';
import { ICON_SIZES } from '../constants/iconSizes';

type LeafMatcher = MatchSender | MatchMention | MatchChatInfo | MatchChatType | MatchAdapter;
const LEAF_MATCHER_TYPES: LeafMatcher['type'][] = ['sender', 'mention', 'chat', 'chat_type', 'adapter'];

const EMPTY_RULE: DetectionRule = {
  rule_id: '',
  name: '',
  description: '',
  matcher: { type: 'all' },
  topic_hints: [],
  score_threshold: 0.7,
  enabled: true,
  parameters: [],
};

export default function RulesPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: rules, isLoading } = useQuery({ queryKey: ['rules'], queryFn: fetchRules });
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });

  const [editing, setEditing] = useState<DetectionRule | null>(null);
  const [deleting, setDeleting] = useState<DetectionRule | null>(null);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
  const [topicInput, setTopicInput] = useState('');
  const [search, setSearch] = useState('');
  const [detForm, setDetForm] = useState<Partial<AppSettings>>({});
  const [selectedRules, setSelectedRules] = useState<Record<string, boolean>>({});
  const [matcherFilters, setMatcherFilters] = useState<Partial<LeafMatcher>[]>([{ type: 'sender' }]);
  const [matcherFilterEnabled, setMatcherFilterEnabled] = useState(false);
  const [swipeStart, setSwipeStart] = useState<number | null>(null);
  const [swipedRule, setSwipedRule] = useState<string | null>(null);
  const swipeTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!settings) return;
    setDetForm({
      app_name: settings.app_name,
      environment: settings.environment,
      context_message_limit: settings.context_message_limit,
      detection_cooldown_seconds: settings.detection_cooldown_seconds,
      detection_min_new_messages: settings.detection_min_new_messages,
      detection_wait_timeout_seconds: settings.detection_wait_timeout_seconds,
      pending_queue_limit: settings.pending_queue_limit,
      history_list_limit: settings.history_list_limit,
      hook_timeout_seconds: settings.hook_timeout_seconds,
      enable_internal_rule_generation: settings.enable_internal_rule_generation,
      external_rule_generation_endpoint: settings.external_rule_generation_endpoint ?? '',
    });
  }, [settings]);

  useEffect(() => () => {
    if (swipeTimer.current) window.clearTimeout(swipeTimer.current);
  }, []);

  const upsert = useMutation({
    mutationFn: upsertRule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['rules'] }); setEditing(null); },
  });

  const del = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['rules'] }); setDeleting(null); },
  });
  const saveDetection = useMutation({
    mutationFn: () => updateSettings(detForm),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  useEffect(() => {
    if (!rules) return;
    setSelectedRules(prev => {
      const next: Record<string, boolean> = {};
      rules.forEach(r => { if (prev[r.rule_id]) next[r.rule_id] = true; });
      return next;
    });
  }, [rules]);

  const selectedIds = useMemo(() => Object.keys(selectedRules).filter(id => selectedRules[id]), [selectedRules]);
  const activeMatcherFilters = useMemo(
    () => matcherFilters.filter(f => f.type),
    [matcherFilters],
  );
  const replaceMatcherFilter = useCallback((index: number, next: Partial<LeafMatcher>) => {
    setMatcherFilters(prev => prev.map((f, i) => (i === index ? next : f)));
  }, []);
  const patchMatcherFilter = useCallback((index: number, patch: Partial<LeafMatcher>) => {
    setMatcherFilters(prev => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }, []);
  const matcherPreview = useMemo(() => {
    const leafChip = (
      color: 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger',
      icon: IconifyIcon,
      label: string,
    ) => (
      <Chip
        size="sm"
        variant="flat"
        color={color}
        className="max-w-[180px]"
        startContent={<Icon icon={icon} fontSize={ICON_SIZES.chip} />}
      >
        <span className="truncate">{label}</span>
      </Chip>
    );

    const renderMatcher = (m: MatcherUnion, path = 'root'): ReactNode => {
      if (m.type === 'all') {
        return (
          <Chip
            key={path}
            size="sm"
            variant="flat"
            color="success"
            startContent={<Icon icon={checkCircleBold} fontSize={ICON_SIZES.chip} />}
          >
            {t('matcher.preview.all')}
          </Chip>
        );
      }
      if (m.type === 'and' || m.type === 'or') {
        const connector = (
          <Chip
            size="sm"
            variant="bordered"
            color="secondary"
            className="uppercase tracking-wide"
          >
            {t(`matcher.types.${m.type}`)}
          </Chip>
        );
        return (
          <div key={path} className="flex flex-wrap items-center gap-1">
            {m.matchers.map((child, idx) => (
              <div key={`${path}-${idx}`} className="flex items-center gap-1">
                {idx > 0 && connector}
                {renderMatcher(child, `${path}-${idx}`)}
              </div>
            ))}
          </div>
        );
      }
      if (m.type === 'not') {
        return (
          <div key={path} className="flex items-center gap-1">
          <Chip
            size="sm"
            variant="bordered"
            color="danger"
            startContent={<Icon icon={closeCircleBold} fontSize={ICON_SIZES.chip} />}
            className="uppercase tracking-wide"
          >
            {t('matcher.types.not')}
          </Chip>
            {renderMatcher(m.matcher, `${path}-not`)}
          </div>
        );
      }
      if (m.type === 'sender') {
        return leafChip(
          'primary',
          userRoundedBold,
          `${t('matcher.types.sender')}:${m.display_name || m.user_id || t('common.none')}`,
        );
      }
      if (m.type === 'mention') {
        return leafChip(
          'secondary',
          bellBingBold,
          `${t('matcher.types.mention')}:${m.display_name || m.user_id || t('common.none')}`,
        );
      }
      if (m.type === 'chat') {
        return leafChip(
          'default',
          chatDotsBold,
          `${t('matcher.types.chat')}:${m.chat_id || t('common.none')}`,
        );
      }
      if (m.type === 'chat_type') {
        return leafChip(
          'warning',
          usersGroupRoundedBold,
          `${t('matcher.types.chat_type')}:${m.chat_type}`,
        );
      }
      if (m.type === 'adapter') {
        return leafChip(
          'default',
          plugCircleBold,
          `${t('matcher.types.adapter')}:${m.adapter_name || t('common.none')}`,
        );
      }
      return null;
    };

    return (rule: DetectionRule) => (
      <div className="flex flex-wrap items-center gap-1 max-w-lg">
        {renderMatcher(rule.matcher)}
      </div>
    );
  }, [t]);

  function matcherContains(root: MatcherUnion, target: Partial<LeafMatcher>): boolean {
    if (!target.type) return false;
    switch (root.type) {
      case 'and': return root.matchers.some(m => matcherContains(m, target));
      case 'or': return root.matchers.some(m => matcherContains(m, target));
      case 'not': return matcherContains(root.matcher, target);
      default:
        if (root.type !== target.type) return false;
        if (root.type === 'sender' || root.type === 'mention') {
          const t = target as Partial<MatchSender>;
          const user = t.user_id?.trim();
          const display = t.display_name?.trim();
          const matchesUser = user ? root.user_id === user : true;
          const matchesDisplay = display ? root.display_name === display : true;
          return matchesUser && matchesDisplay;
        }
        if (root.type === 'chat') {
          const t = target as Partial<MatchChatInfo>;
          const chatId = t.chat_id?.trim();
          return chatId ? root.chat_id === chatId : true;
        }
        if (root.type === 'chat_type') {
          const t = target as Partial<MatchChatType>;
          return t.chat_type ? root.chat_type === t.chat_type : true;
        }
        if (root.type === 'adapter') {
          const t = target as Partial<MatchAdapter>;
          const adapterName = t.adapter_name?.trim();
          return adapterName ? root.adapter_name === adapterName : true;
        }
        return false;
    }
  }

  function ruleMatchesSearch(rule: DetectionRule) {
    const keywordTarget = `${rule.name} ${rule.description} ${rule.topic_hints.join(' ')}`.toLowerCase();
    const keywordOk = keywordTarget.includes(search.toLowerCase());
    if (!matcherFilterEnabled) return keywordOk;
    const usableFilters = activeMatcherFilters;
    if (usableFilters.length === 0) return keywordOk;
    return keywordOk && usableFilters.every(f => matcherContains(rule.matcher, f));
  }

  function toggleSelect(id: string) {
    setSelectedRules(prev => ({ ...prev, [id]: !prev[id] }));
  }

  function selectAllFiltered(ids: string[]) {
    setSelectedRules(prev => {
      const next = { ...prev };
      ids.forEach(id => { next[id] = true; });
      return next;
    });
  }

  function handleBulkEnable(enable: boolean, ids: string[]) {
    ids.forEach(id => {
      const rule = rules?.find(r => r.rule_id === id);
      if (rule) upsert.mutate({ ...rule, enabled: enable });
    });
  }

  function handleBulkDelete(ids: string[]) {
    if (ids.length === 0) return;
    setBulkDeleteLoading(true);
    Promise.all(ids.map(id => del.mutateAsync(id)))
      .finally(() => {
        setBulkDeleteLoading(false);
        setBulkConfirmOpen(false);
        setSelectedRules({});
      });
  }

  function handleTouchStart(x: number, id: string) {
    setSwipeStart(x);
    setSwipedRule(id);
    if (swipeTimer.current) window.clearTimeout(swipeTimer.current);
    swipeTimer.current = window.setTimeout(() => setSwipedRule(null), 3500);
  }

  function handleTouchMove(x: number) {
    if (swipeStart === null) return;
    const diff = swipeStart - x;
    if (diff > 60) {
      setSwipeStart(null);
      if (swipedRule) setDeleting(rules?.find(r => r.rule_id === swipedRule) ?? null);
    }
  }

  function handleTouchEnd() {
    setSwipeStart(null);
  }

  function openNew() {
    setEditing({ ...EMPTY_RULE, rule_id: crypto.randomUUID() });
    setTopicInput('');
  }

  function openEdit(r: DetectionRule) {
    setEditing({ ...r });
    setTopicInput('');
  }

  function addTopic() {
    if (!topicInput.trim() || !editing) return;
    setEditing({ ...editing, topic_hints: [...editing.topic_hints, topicInput.trim()] });
    setTopicInput('');
  }

  function removeTopic(t: string) {
    if (!editing) return;
    setEditing({ ...editing, topic_hints: editing.topic_hints.filter(x => x !== t) });
  }

  function addParam() {
    if (!editing) return;
    setEditing({ ...editing, parameters: [...editing.parameters, { key: '', description: '', required: false }] });
  }

  function updateParam(i: number, field: keyof RuleParameterSpec, val: string | boolean) {
    if (!editing) return;
    const params = editing.parameters.map((p, idx) => idx === i ? { ...p, [field]: val } : p);
    setEditing({ ...editing, parameters: params });
  }

  function removeParam(i: number) {
    if (!editing) return;
    setEditing({ ...editing, parameters: editing.parameters.filter((_, idx) => idx !== i) });
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('rules.loading')} /></div>;

  const filteredRules = (rules ?? []).filter(ruleMatchesSearch);

  return (
    <div className="space-y-4">
      <Accordion
        selectionMode="multiple"
        defaultExpandedKeys={new Set()}
        itemClasses={{ title: 'w-full' }}
        variant="splitted"
        className="bg-transparent"
      >
        <AccordionItem
          key="detection"
          aria-label={t('rules.detectionSettings')}
            title={(
              <div className="flex items-center gap-2">
                <Icon icon={shieldCheckBold} width={18} className="text-primary" />
                <div className="text-left">
                  <p className="font-semibold">{t('rules.detectionSettings')}</p>
                  <p className="text-sm text-default-500">{t('rules.detectionSettingsDesc')}</p>
                </div>
              </div>
            )}
        >
          <Card className="shadow-md">
            <CardBody className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Input
                  label={t('rules.appName')}
                  startContent={<Icon icon={tagBold} width={16} className="text-default-500" />}
                  value={detForm.app_name ?? ''}
                  isReadOnly
                />
                <Input
                  label={t('rules.environment')}
                  startContent={<Icon icon={magicStick2Bold} width={16} className="text-default-500" />}
                  value={detForm.environment ?? ''}
                  isReadOnly
                />
                <Input
                  label={t('rules.contextMessageLimit')}
                  type="number"
                  startContent={<Icon icon={chart2Bold} width={16} className="text-default-500" />}
                  value={String(detForm.context_message_limit ?? 10)}
                  onValueChange={v => setDetForm(f => ({ ...f, context_message_limit: Number(v) }))}
                />
                <Input
                  label={t('rules.detectionCooldown')}
                  type="number"
                  startContent={<Icon icon={chart2Bold} width={16} className="text-default-500" />}
                  value={String(detForm.detection_cooldown_seconds ?? 0)}
                  onValueChange={v => setDetForm(f => ({ ...f, detection_cooldown_seconds: Number(v) }))}
                />
                <Input
                  label={t('rules.minNewMessages')}
                  type="number"
                  startContent={<Icon icon={chart2Bold} width={16} className="text-default-500" />}
                  value={String(detForm.detection_min_new_messages ?? 1)}
                  onValueChange={v => setDetForm(f => ({ ...f, detection_min_new_messages: Number(v) }))}
                />
                <Input
                  label={t('rules.detectionWaitTimeout')}
                  type="number"
                  startContent={<Icon icon={chart2Bold} width={16} className="text-default-500" />}
                  value={String(detForm.detection_wait_timeout_seconds ?? 30)}
                  onValueChange={v => setDetForm(f => ({ ...f, detection_wait_timeout_seconds: Number(v) }))}
                />
                <Input
                  label={t('rules.pendingQueueLimit')}
                  type="number"
                  startContent={<Icon icon={listCheckBold} width={16} className="text-default-500" />}
                  value={String(detForm.pending_queue_limit ?? 200)}
                  onValueChange={v => setDetForm(f => ({ ...f, pending_queue_limit: Number(v) }))}
                />
                <Input
                  label={t('rules.historyListLimit')}
                  type="number"
                  startContent={<Icon icon={listCheckBold} width={16} className="text-default-500" />}
                  value={String(detForm.history_list_limit ?? 1000)}
                  onValueChange={v => setDetForm(f => ({ ...f, history_list_limit: Number(v) }))}
                />
                <Input
                  label={t('rules.hookTimeout')}
                  type="number"
                  startContent={<Icon icon={chart2Bold} width={16} className="text-default-500" />}
                  value={String(detForm.hook_timeout_seconds ?? 8)}
                  onValueChange={v => setDetForm(f => ({ ...f, hook_timeout_seconds: Number(v) }))}
                />
                <div className="flex items-center justify-between gap-3 rounded-lg border border-default-200 bg-default-50 px-3 py-2">
                  <div className="flex items-center gap-2 text-sm text-default-700">
                    <Icon icon={checkSquareBold} width={16} className="text-default-500" />
                    <span>{t('rules.enableInternalRuleGen')}</span>
                  </div>
                  <Switch
                    isSelected={detForm.enable_internal_rule_generation ?? false}
                    onValueChange={v => setDetForm(f => ({ ...f, enable_internal_rule_generation: v }))}
                    aria-label={t('rules.enableInternalRuleGen')}
                  />
                </div>
                <Input
                  label={t('rules.externalRuleEndpoint')}
                  startContent={<Icon icon={alignLeftBold} width={16} className="text-default-500" />}
                  value={detForm.external_rule_generation_endpoint ?? ''}
                  onValueChange={v => setDetForm(f => ({ ...f, external_rule_generation_endpoint: v }))}
                  className="md:col-span-2"
                />
              </div>
              <div className="flex items-center justify-end gap-3 flex-wrap">
                <Button color="primary" size="sm" isDisabled={!settings} isLoading={saveDetection.isPending} onPress={() => saveDetection.mutate()}>
                  {t('common.save')}
                </Button>
              </div>
              {saveDetection.isSuccess && <p className="text-success text-sm">{t('common.saved')}</p>}
              {saveDetection.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
            </CardBody>
          </Card>
        </AccordionItem>
      </Accordion>

      <div className="border-b border-default-200" />

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <p className="text-default-500 text-sm">{t('rules.ruleCount', { count: filteredRules.length })}</p>
          <div className="flex gap-2 flex-wrap items-center">
            <Chip
              size="sm"
              variant="flat"
              color="primary"
              startContent={<Icon icon={filterBold} fontSize={ICON_SIZES.chip} />}
            >
              {t('rules.filtersActive', { count: matcherFilterEnabled ? activeMatcherFilters.length : 0 })}
            </Chip>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon={closeCircleBold} fontSize={ICON_SIZES.button} />}
              onPress={() => { setMatcherFilterEnabled(false); setMatcherFilters([{ type: 'sender' }]); }}
            >
              {t('rules.clearFilters')}
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon={checkSquareBold} fontSize={ICON_SIZES.button} />}
              onPress={() => selectAllFiltered(filteredRules.map(r => r.rule_id))}
              isDisabled={filteredRules.length === 0}
            >
              {t('rules.selectFiltered')}
            </Button>
            <Button
              size="sm"
              variant="light"
              startContent={<Icon icon={closeCircleBold} fontSize={ICON_SIZES.button} />}
              onPress={() => setSelectedRules({})}
              isDisabled={selectedIds.length === 0}
            >
              {t('rules.clearSelection')}
            </Button>
          </div>
        </div>
        <div className="flex flex-row flex-wrap gap-2 items-center">
          <div className="flex flex-1 gap-2 items-center min-w-[280px]">
            <Input
              size="sm"
              startContent={<Icon icon={textFieldFocusBold} fontSize={ICON_SIZES.button} className="text-default-500" />}
              placeholder={t('rules.searchPlaceholder')}
              value={search}
              onValueChange={setSearch}
              aria-label={t('rules.searchPlaceholder')}
              className="w-full min-w-[220px]"
            />
            <Button
              color="primary"
              startContent={<Icon icon={addCircleBold} fontSize={ICON_SIZES.button} />}
              onPress={openNew}
              className="whitespace-nowrap"
            >
              {t('rules.newRule')}
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon={settingsBold} fontSize={ICON_SIZES.button} />}
              onPress={() => setMatcherFilterEnabled(v => !v)}
              color={matcherFilterEnabled ? 'primary' : 'default'}
            >
              {t('rules.matcherFilter')}
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon={shieldCheckBold} fontSize={ICON_SIZES.button} />}
              isDisabled={selectedIds.length === 0}
              onPress={() => handleBulkEnable(true, selectedIds)}
            >
              {t('rules.bulkEnable')}
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon={shieldCheckBold} fontSize={ICON_SIZES.button} />}
              isDisabled={selectedIds.length === 0}
              onPress={() => handleBulkEnable(false, selectedIds)}
            >
              {t('rules.bulkDisable')}
            </Button>
            <Button
              size="sm"
              variant="flat"
              color="danger"
              startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
              isDisabled={selectedIds.length === 0}
              onPress={() => setBulkConfirmOpen(true)}
            >
              {t('rules.bulkDelete')}
            </Button>
          </div>
        </div>
        {matcherFilterEnabled && (
          <div className="flex flex-col gap-3 border border-default-200 rounded-xl p-3 bg-default-50">
            {matcherFilters.map((filter, idx) => (
              <div key={idx} className="flex flex-col gap-2 border border-default-200 rounded-lg p-3 bg-content1">
                <div className="flex flex-wrap items-center gap-2">
                  <Select
                    size="sm"
                    label={t('rules.matcherType')}
                    className="w-44"
                    selectedKeys={[filter.type ?? 'sender']}
                    onSelectionChange={keys => {
                      const k = Array.from(keys)[0] as MatcherType;
                      if (!k || !LEAF_MATCHER_TYPES.includes(k as LeafMatcher['type'])) return;
                      const base: Partial<LeafMatcher> = { type: k as LeafMatcher['type'] };
                      replaceMatcherFilter(idx, base);
                    }}
                  >
                    {LEAF_MATCHER_TYPES.map(mt => (
                      <SelectItem key={mt}>{t(`matcher.types.${mt}`)}</SelectItem>
                    ))}
                  </Select>
                  <Chip size="sm" variant="dot">{t('rules.matcherSearchDesc')}</Chip>
                  {matcherFilters.length > 1 && (
                    <Button
                      isIconOnly
                      size="sm"
                      variant="light"
                      color="danger"
                      onPress={() => setMatcherFilters(f => f.filter((_, i) => i !== idx))}
                      aria-label={t('rules.clearFilters')}
                    >
                      <Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />
                    </Button>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {(filter.type === 'sender' || filter.type === 'mention') && (
                    <>
                      <Input
                        size="sm"
                        label={t('matcher.userId')}
                        value={filter.user_id ?? ''}
                        onValueChange={v => patchMatcherFilter(idx, { user_id: v })}
                        className="w-48"
                      />
                      <Input
                        size="sm"
                        label={t('matcher.displayName')}
                        value={filter.display_name ?? ''}
                        onValueChange={v => patchMatcherFilter(idx, { display_name: v })}
                        className="w-48"
                      />
                    </>
                  )}
                  {filter.type === 'chat' && (
                    <Input
                      size="sm"
                      label={t('matcher.chatId')}
                      value={filter.chat_id ?? ''}
                      onValueChange={v => patchMatcherFilter(idx, { chat_id: v })}
                      className="w-60"
                    />
                  )}
                  {filter.type === 'chat_type' && (
                    <Select
                      size="sm"
                      label={t('matcher.chatType')}
                      selectedKeys={filter.chat_type ? [filter.chat_type] : []}
                      onSelectionChange={keys => {
                        const k = Array.from(keys)[0] as 'group' | 'private';
                        if (k) patchMatcherFilter(idx, { chat_type: k });
                      }}
                      className="w-48"
                    >
                      <SelectItem key="group">{t('matcher.group')}</SelectItem>
                      <SelectItem key="private">{t('matcher.private')}</SelectItem>
                    </Select>
                  )}
                  {filter.type === 'adapter' && (
                    <Input
                        size="sm"
                        label={t('matcher.adapterName')}
                        value={filter.adapter_name ?? ''}
                        onValueChange={v => patchMatcherFilter(idx, { adapter_name: v })}
                        className="w-60"
                      />
                  )}
                </div>
              </div>
            ))}
            <div className="flex gap-2 flex-wrap items-center">
              <Button
                size="sm"
                variant="flat"
                color="secondary"
                onPress={() => setMatcherFilters([{ type: matcherFilters[0]?.type ?? 'sender' }])}
              >
                {t('rules.resetMatcherFilter')}
              </Button>
              <Button
                size="sm"
                variant="flat"
                startContent={<Icon icon={addCircleBold} fontSize={ICON_SIZES.button} />}
                onPress={() => setMatcherFilters(f => [...f, { type: 'sender' }])}
              >
                {t('rules.addMatcherFilter')}
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-4">
        {filteredRules.map(rule => (
          <Card key={rule.rule_id} className="w-full border border-default-200 shadow-sm">
            <CardBody
              className="flex flex-col gap-3 md:flex-row md:items-start justify-between md:gap-6"
              onTouchStart={e => handleTouchStart(e.touches[0].clientX, rule.rule_id)}
              onTouchMove={e => handleTouchMove(e.touches[0].clientX)}
              onTouchEnd={handleTouchEnd}
            >
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <Checkbox
                  isSelected={!!selectedRules[rule.rule_id]}
                  onValueChange={() => toggleSelect(rule.rule_id)}
                  aria-label={t('rules.selectRule')}
                  className="mt-1"
                />
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      type="button"
                      onClick={() => openEdit(rule)}
                      className="font-semibold text-primary hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 rounded-sm"
                    >
                      {rule.name}
                    </button>
                    <Chip
                      size="sm"
                      color={rule.enabled ? 'success' : 'default'}
                      variant="flat"
                      startContent={<Icon icon={pulse2Bold} fontSize={ICON_SIZES.chip} />}
                    >
                      {rule.enabled ? t('common.enabled') : t('common.disabled')}
                    </Chip>
                    <Chip
                      size="sm"
                      variant="flat"
                      color="primary"
                      startContent={<Icon icon={tuning2Bold} fontSize={ICON_SIZES.chip} />}
                    >
                      {t('rules.threshold', { value: rule.score_threshold.toFixed(2) })}
                    </Chip>
                  </div>
                  <p className="text-sm text-default-500 truncate">{rule.description}</p>
                  {rule.topic_hints.length > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      {rule.topic_hints.map((topic, idx) => (
                        <Chip
                          key={`${rule.rule_id}-topic-${idx}`}
                          size="sm"
                          variant="solid"
                          color="secondary"
                          startContent={<Icon icon={hashtagCircleBold} fontSize={ICON_SIZES.chip} />}
                        >
                          {topic}
                        </Chip>
                      ))}
                    </div>
                  )}
                  {rule.parameters.length > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      {rule.parameters.map((param, idx) => (
                        <Chip
                          key={`${rule.rule_id}-param-${idx}`}
                          size="sm"
                          variant={param.required ? 'solid' : 'bordered'}
                          color="warning"
                          startContent={<Icon icon={tagBold} fontSize={ICON_SIZES.chip} />}
                        >
                          {param.key || t('rules.unnamedParam')}{param.required ? ' *' : ''}
                        </Chip>
                      ))}
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Tooltip content={matcherPreview(rule)}>
                      <Button
                        size="sm"
                        variant="light"
                        startContent={<Icon icon={eyeBold} fontSize={ICON_SIZES.button} />}
                      >
                        {t('rules.matcherPreviewLabel')}
                      </Button>
                    </Tooltip>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Switch
                  size="md"
                  isSelected={rule.enabled}
                  onValueChange={v => upsert.mutate({ ...rule, enabled: v })}
                  aria-label={t('rules.enableRule')}
                />
                <Button isIconOnly size="md" variant="flat" onPress={() => openEdit(rule)}>
                  <Icon icon={pen2Bold} width={18} />
                </Button>
                <Button
                  isIconOnly
                  size="md"
                  variant="flat"
                  color="danger"
                  onPress={() => setDeleting(rule)}
                >
                  <Icon icon={trashBin2Bold} width={18} />
                </Button>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Edit modal */}
      <Modal
        isDismissable={false}
        isOpen={!!editing}
        onClose={() => setEditing(null)}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalContent>
          {editing && (
            <>
              <ModalHeader>
                {editing.name ? t('rules.editPrefix', { name: editing.name }) : t('rules.newRule')}
              </ModalHeader>
              <ModalBody className="space-y-4">
                <Input
                  label={t('rules.ruleName')}
                  isRequired
                  description={t('rules.ruleNameDesc')}
                  startContent={<Icon icon={tagBold} width={16} className="text-default-500" />}
                  value={editing.name}
                  onValueChange={v => setEditing({ ...editing, name: v })}
                />
                <Textarea
                  label={t('rules.description')}
                  description={t('rules.descriptionDesc')}
                  value={editing.description}
                  onValueChange={v => setEditing({ ...editing, description: v })}
                />
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-default-700 mb-1">
                    <Icon icon={chart2Bold} width={16} className="text-default-500" />
                    <span>{t('rules.scoreThreshold')}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <Slider
                      minValue={0}
                      maxValue={1}
                      step={0.1}
                      value={editing.score_threshold}
                      onChange={v => setEditing({ ...editing, score_threshold: Array.isArray(v) ? v[0] : v })}
                      startContent={<span className="text-xs text-default-500 w-4 text-right">0</span>}
                      endContent={<span className="text-xs text-default-500 w-4">1</span>}
                      getValue={val => {
                        const numeric = Array.isArray(val) ? val[0] : val;
                        const numValue = typeof numeric === 'number' ? numeric : Number(numeric);
                        const safe = Number.isFinite(numValue) ? numValue : 0;
                        return safe.toFixed(2);
                      }}
                      className="max-w-md"
                    />
                    <Input
                      size="sm"
                      type="number"
                      label={t('rules.scoreThreshold')}
                      className="w-28"
                      step={0.1}
                      value={String(editing.score_threshold)}
                      onValueChange={v => {
                        const num = Math.max(0, Math.min(1, Number(v)));
                        setEditing({ ...editing, score_threshold: isNaN(num) ? editing.score_threshold : num });
                      }}
                    />
                  </div>
                </div>
                <Switch
                  isSelected={editing.enabled}
                  onValueChange={v => setEditing({ ...editing, enabled: v })}
                >
                  {t('common.enabled')}
                </Switch>

                {/* Topic hints */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-default-700">
                    <Icon icon={magicStick2Bold} width={16} className="text-default-500" />
                    <span>{t('rules.topicHints')}</span>
                  </div>
                  <div className="flex gap-2">
                    <Input
                      size="sm"
                      placeholder={t('rules.topicHintPlaceholder')}
                      value={topicInput}
                      onValueChange={setTopicInput}
                      onKeyDown={e => e.key === 'Enter' && addTopic()}
                    />
                    <Button size="sm" onPress={addTopic}>{t('common.add')}</Button>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {editing.topic_hints.map(t => (
                      <Chip
                        key={t}
                        size="sm"
                        onClose={() => removeTopic(t)}
                        variant="flat"
                      >
                        {t}
                      </Chip>
                    ))}
                  </div>
                </div>

                {/* Parameters */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Icon icon={listCheckBold} width={16} className="text-default-500" />
                        <p className="text-sm font-medium text-default-700">{t('rules.parameters')}</p>
                      </div>
                    <Button
                      size="sm"
                      variant="flat"
                      onPress={addParam}
                      startContent={<Icon icon={addCircleBold} fontSize={ICON_SIZES.button} />}
                    >
                      {t('common.add')}
                    </Button>
                  </div>
                  {editing.parameters.map((p, i) => (
                    <div key={i} className="rounded-xl border border-default-200 bg-default-50 p-3 space-y-3">
                      <div className="grid w-full gap-2 sm:grid-cols-[190px,1fr]">
                        <Input
                          size="sm"
                          label={t('rules.key')}
                          startContent={<Icon icon={tagBold} width={14} className="text-default-500" />}
                          value={p.key}
                          onValueChange={v => updateParam(i, 'key', v)}
                        />
                        <Input
                          size="sm"
                          label={t('rules.description')}
                          startContent={<Icon icon={alignLeftBold} width={14} className="text-default-500" />}
                          value={p.description}
                          onValueChange={v => updateParam(i, 'description', v)}
                        />
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <Switch
                          size="sm"
                          isSelected={p.required}
                          onValueChange={v => updateParam(i, 'required', v)}
                        >
                          {t('rules.required')}
                        </Switch>
                        <Button isIconOnly size="sm" color="danger" variant="light" onPress={() => removeParam(i)}>
                          <Icon icon={trashBin2Bold} width={16} />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Matcher editor */}
                <MatcherEditor
                  value={editing.matcher}
                  onChange={(m: MatcherUnion) => setEditing({ ...editing, matcher: m })}
                />
              </ModalBody>
              <ModalFooter>
                <Button variant="flat" onPress={() => setEditing(null)}>{t('common.cancel')}</Button>
                <Button
                  color="primary"
                  isLoading={upsert.isPending}
                  onPress={() => upsert.mutate(editing)}
                  isDisabled={!editing.name.trim()}
                >
                  {t('common.save')}
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* Delete confirm */}
      <Modal isOpen={!!deleting} onClose={() => setDeleting(null)} size="sm">
        <ModalContent>
          {deleting && (
            <>
              <ModalHeader>{t('rules.deleteRule')}</ModalHeader>
              <ModalBody>
                <p>{t('rules.deleteRuleConfirm', { name: deleting.name })}</p>
              </ModalBody>
              <ModalFooter>
                <Button variant="flat" onPress={() => setDeleting(null)}>{t('common.cancel')}</Button>
                <Button
                  color="danger"
                  isLoading={del.isPending}
                  onPress={() => del.mutate(deleting.rule_id)}
                >
                  {t('common.delete')}
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      <Modal isOpen={bulkConfirmOpen} onClose={() => setBulkConfirmOpen(false)} size="md">
        <ModalContent>
          <>
            <ModalHeader>{t('rules.bulkDelete')}</ModalHeader>
            <ModalBody>
              <p>{t('rules.bulkDeleteConfirm', { count: selectedIds.length })}</p>
              <div className="flex flex-wrap gap-1">
                {selectedIds.map(id => {
                  const name = rules?.find(r => r.rule_id === id)?.name ?? id;
                  return <Chip key={id} size="sm" variant="flat" color="danger">{name}</Chip>;
                })}
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setBulkConfirmOpen(false)}>{t('common.cancel')}</Button>
              <Button
                color="danger"
                isLoading={bulkDeleteLoading}
                onPress={() => handleBulkDelete(selectedIds)}
              >
                {t('common.delete')}
              </Button>
            </ModalFooter>
          </>
        </ModalContent>
      </Modal>
    </div>
  );
}
