import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, Chip, Input, Modal, ModalBody,
  ModalContent, ModalFooter, ModalHeader, Spinner, Switch, Slider, Textarea,
} from '@heroui/react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { fetchRules, upsertRule, deleteRule } from '../api/rules';
import type { DetectionRule, MatcherUnion, RuleParameterSpec } from '../api/types';
import MatcherEditor from '../components/matcher/MatcherEditor';

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
  const qc = useQueryClient();
  const { data: rules, isLoading } = useQuery({ queryKey: ['rules'], queryFn: fetchRules });

  const [editing, setEditing] = useState<DetectionRule | null>(null);
  const [deleting, setDeleting] = useState<DetectionRule | null>(null);
  const [topicInput, setTopicInput] = useState('');

  const upsert = useMutation({
    mutationFn: upsertRule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['rules'] }); setEditing(null); },
  });

  const del = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['rules'] }); setDeleting(null); },
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

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading rules…" /></div>;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-default-500 text-sm">{rules?.length ?? 0} rules</p>
        <Button color="primary" startContent={<Plus size={16} />} onPress={openNew}>
          New Rule
        </Button>
      </div>

      <div className="space-y-3">
        {rules?.map(rule => (
          <Card key={rule.rule_id} className="w-full">
            <CardBody className="flex flex-row items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-default-900">{rule.name}</span>
                  <Chip size="sm" color={rule.enabled ? 'success' : 'default'} variant="flat">
                    {rule.enabled ? 'Enabled' : 'Disabled'}
                  </Chip>
                  <Chip size="sm" variant="flat" color="primary">
                    threshold: {rule.score_threshold}
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
                  aria-label="Enable rule"
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
                {editing.name ? `Edit: ${editing.name}` : 'New Rule'}
              </ModalHeader>
              <ModalBody className="space-y-4">
                <Input
                  label="Rule Name"
                  isRequired
                  description="A short, descriptive name"
                  value={editing.name}
                  onValueChange={v => setEditing({ ...editing, name: v })}
                />
                <Textarea
                  label="Description"
                  description="What does this rule detect?"
                  value={editing.description}
                  onValueChange={v => setEditing({ ...editing, description: v })}
                />
                <div>
                  <p className="text-sm font-medium text-default-700 mb-1">Score Threshold</p>
                  <Slider
                    minValue={0}
                    maxValue={1}
                    step={0.05}
                    value={editing.score_threshold}
                    onChange={v => setEditing({ ...editing, score_threshold: v as number })}
                    label={`${editing.score_threshold}`}
                    className="max-w-md"
                  />
                </div>
                <Switch
                  isSelected={editing.enabled}
                  onValueChange={v => setEditing({ ...editing, enabled: v })}
                >
                  Enabled
                </Switch>

                {/* Topic hints */}
                <div className="space-y-2">
                  <p className="text-sm font-medium text-default-700">Topic Hints</p>
                  <div className="flex gap-2">
                    <Input
                      size="sm"
                      placeholder="Add topic hint"
                      value={topicInput}
                      onValueChange={setTopicInput}
                      onKeyDown={e => e.key === 'Enter' && addTopic()}
                    />
                    <Button size="sm" onPress={addTopic}>Add</Button>
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
                    <p className="text-sm font-medium text-default-700">Parameters</p>
                    <Button size="sm" variant="flat" onPress={addParam} startContent={<Plus size={12} />}>
                      Add
                    </Button>
                  </div>
                  {editing.parameters.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 flex-wrap">
                      <Input
                        size="sm"
                        label="Key"
                        value={p.key}
                        onValueChange={v => updateParam(i, 'key', v)}
                        className="w-32"
                      />
                      <Input
                        size="sm"
                        label="Description"
                        value={p.description}
                        onValueChange={v => updateParam(i, 'description', v)}
                        className="flex-1"
                      />
                      <Switch
                        size="sm"
                        isSelected={p.required}
                        onValueChange={v => updateParam(i, 'required', v)}
                      >
                        Required
                      </Switch>
                      <Button isIconOnly size="sm" color="danger" variant="light" onPress={() => removeParam(i)}>
                        <Trash2 size={12} />
                      </Button>
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
                <Button variant="flat" onPress={() => setEditing(null)}>Cancel</Button>
                <Button
                  color="primary"
                  isLoading={upsert.isPending}
                  onPress={() => upsert.mutate(editing)}
                  isDisabled={!editing.name.trim()}
                >
                  Save
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
              <ModalHeader>Delete Rule</ModalHeader>
              <ModalBody>
                <p>Delete <strong>{deleting.name}</strong>? This cannot be undone.</p>
              </ModalBody>
              <ModalFooter>
                <Button variant="flat" onPress={() => setDeleting(null)}>Cancel</Button>
                <Button
                  color="danger"
                  isLoading={del.isPending}
                  onPress={() => del.mutate(deleting.rule_id)}
                >
                  Delete
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>
    </div>
  );
}
