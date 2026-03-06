import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, Chip, Input, Modal, ModalBody,
  ModalContent, ModalFooter, ModalHeader, Spinner, Switch, Slider, Textarea,
} from '@heroui/react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { fetchRules, upsertRule, deleteRule } from '../api/rules';
import type { DetectionRule, MatcherUnion, RuleParameterSpec } from '../api/types';
import MatcherEditor from '../components/matcher/MatcherEditor';
import { fetchSettings, updateSettings } from '../api/settings';
import type { AppSettings } from '../api/settings';

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
  const [topicInput, setTopicInput] = useState('');
  const [search, setSearch] = useState('');
  const [detForm, setDetForm] = useState<Partial<AppSettings>>({});

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

  const filteredRules = (rules ?? []).filter(r => {
    const target = `${r.name} ${r.description} ${r.topic_hints.join(' ')}`.toLowerCase();
    return target.includes(search.toLowerCase());
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardBody className="space-y-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="font-semibold">{t('rules.detectionSettings')}</p>
              <p className="text-sm text-default-500">{t('rules.detectionSettingsDesc')}</p>
            </div>
            <Button color="primary" size="sm" isDisabled={!settings} isLoading={saveDetection.isPending} onPress={() => saveDetection.mutate()}>
              {t('common.save')}
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Input label={t('rules.appName')} value={detForm.app_name ?? ''} onValueChange={v => setDetForm(f => ({ ...f, app_name: v }))} />
            <Input label={t('rules.environment')} value={detForm.environment ?? ''} onValueChange={v => setDetForm(f => ({ ...f, environment: v }))} />
            <Input
              label={t('rules.contextMessageLimit')}
              type="number"
              value={String(detForm.context_message_limit ?? 10)}
              onValueChange={v => setDetForm(f => ({ ...f, context_message_limit: Number(v) }))}
            />
            <Input
              label={t('rules.detectionCooldown')}
              type="number"
              value={String(detForm.detection_cooldown_seconds ?? 0)}
              onValueChange={v => setDetForm(f => ({ ...f, detection_cooldown_seconds: Number(v) }))}
            />
            <Input
              label={t('rules.minNewMessages')}
              type="number"
              value={String(detForm.detection_min_new_messages ?? 1)}
              onValueChange={v => setDetForm(f => ({ ...f, detection_min_new_messages: Number(v) }))}
            />
            <Input
              label={t('rules.detectionWaitTimeout')}
              type="number"
              value={String(detForm.detection_wait_timeout_seconds ?? 30)}
              onValueChange={v => setDetForm(f => ({ ...f, detection_wait_timeout_seconds: Number(v) }))}
            />
            <Input
              label={t('rules.pendingQueueLimit')}
              type="number"
              value={String(detForm.pending_queue_limit ?? 200)}
              onValueChange={v => setDetForm(f => ({ ...f, pending_queue_limit: Number(v) }))}
            />
            <Input
              label={t('rules.historyListLimit')}
              type="number"
              value={String(detForm.history_list_limit ?? 1000)}
              onValueChange={v => setDetForm(f => ({ ...f, history_list_limit: Number(v) }))}
            />
            <Input
              label={t('rules.hookTimeout')}
              type="number"
              value={String(detForm.hook_timeout_seconds ?? 8)}
              onValueChange={v => setDetForm(f => ({ ...f, hook_timeout_seconds: Number(v) }))}
            />
            <Switch
              isSelected={detForm.enable_internal_rule_generation ?? false}
              onValueChange={v => setDetForm(f => ({ ...f, enable_internal_rule_generation: v }))}
            >
              {t('rules.enableInternalRuleGen')}
            </Switch>
            <Input
              label={t('rules.externalRuleEndpoint')}
              value={detForm.external_rule_generation_endpoint ?? ''}
              onValueChange={v => setDetForm(f => ({ ...f, external_rule_generation_endpoint: v }))}
              className="md:col-span-2"
            />
          </div>
          {saveDetection.isSuccess && <p className="text-success text-sm">{t('common.saved')}</p>}
          {saveDetection.isError && <p className="text-danger text-sm">{t('common.saveFailed')}</p>}
        </CardBody>
      </Card>

      <div className="flex justify-between items-center gap-3 flex-wrap">
        <p className="text-default-500 text-sm">{t('rules.ruleCount', { count: filteredRules.length })}</p>
        <div className="flex gap-2 flex-wrap items-center">
          <Input
            size="sm"
            placeholder={t('rules.searchPlaceholder')}
            value={search}
            onValueChange={setSearch}
            aria-label={t('rules.searchPlaceholder')}
          />
          <Button color="primary" startContent={<Plus size={16} />} onPress={openNew}>
            {t('rules.newRule')}
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        {filteredRules.map(rule => (
          <Card key={rule.rule_id} className="w-full">
            <CardBody className="flex flex-row items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-default-900">{rule.name}</span>
                  <Chip size="sm" color={rule.enabled ? 'success' : 'default'} variant="flat">
                    {rule.enabled ? t('common.enabled') : t('common.disabled')}
                  </Chip>
                  <Chip size="sm" variant="flat" color="primary">
                    {t('rules.threshold', { value: rule.score_threshold })}
                  </Chip>
                </div>
                <p className="text-sm text-default-500 mt-1 truncate">{rule.description}</p>
                {rule.topic_hints.length > 0 && (
                  <div className="flex gap-1 flex-wrap mt-1">
                    {rule.topic_hints.map(t => (
                      <Chip key={t} size="sm" variant="dot">{t}</Chip>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Switch
                  size="sm"
                  isSelected={rule.enabled}
                  onValueChange={v => upsert.mutate({ ...rule, enabled: v })}
                  aria-label={t('rules.enableRule')}
                />
                <Button isIconOnly size="sm" variant="flat" onPress={() => openEdit(rule)}>
                  <Pencil size={14} />
                </Button>
                <Button isIconOnly size="sm" variant="flat" color="danger" onPress={() => setDeleting(rule)}>
                  <Trash2 size={14} />
                </Button>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Edit modal */}
      <Modal
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
                  <p className="text-sm font-medium text-default-700 mb-1">{t('rules.scoreThreshold')}</p>
                  <div className="flex items-center gap-3 flex-wrap">
                    <Slider
                      minValue={0}
                      maxValue={1}
                      step={0.05}
                      value={editing.score_threshold}
                      onChange={v => setEditing({ ...editing, score_threshold: v as number })}
                      label={`${editing.score_threshold.toFixed(2)}`}
                      className="max-w-md"
                    />
                    <Input
                      size="sm"
                      type="number"
                      label={t('rules.manual')}
                      className="w-28"
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
                  <p className="text-sm font-medium text-default-700">{t('rules.topicHints')}</p>
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
                    <p className="text-sm font-medium text-default-700">{t('rules.parameters')}</p>
                    <Button size="sm" variant="flat" onPress={addParam} startContent={<Plus size={12} />}>
                      {t('common.add')}
                    </Button>
                  </div>
                  {editing.parameters.map((p, i) => (
                    <div key={i} className="grid w-full gap-2 sm:grid-cols-[180px,1fr,auto] sm:items-center">
                      <Input
                        size="sm"
                        label={t('rules.key')}
                        value={p.key}
                        onValueChange={v => updateParam(i, 'key', v)}
                      />
                      <Input
                        size="sm"
                        label={t('rules.description')}
                        value={p.description}
                        onValueChange={v => updateParam(i, 'description', v)}
                      />
                      <div className="flex items-center gap-2">
                        <Switch
                          size="sm"
                          isSelected={p.required}
                          onValueChange={v => updateParam(i, 'required', v)}
                        >
                          {t('rules.required')}
                        </Switch>
                        <Button isIconOnly size="sm" color="danger" variant="light" onPress={() => removeParam(i)}>
                          <Trash2 size={12} />
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
    </div>
  );
}
