import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import {
  Accordion, AccordionItem, Button, Card, CardBody, CardHeader, Chip, Input, Modal, ModalBody, ModalContent,
  ModalFooter, ModalHeader, Pagination, Progress, Snippet, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import documentTextBold from '@iconify/icons-solar/document-text-bold';
import dangerTriangleBold from '@iconify/icons-solar/danger-triangle-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import textFieldFocusBold from '@iconify/icons-solar/text-field-focus-bold';
import { useTranslation } from 'react-i18next';
import { fetchRuleStats } from '../api/stats';
import { fetchRules } from '../api/rules';
import TriggerChart from '../components/charts/TriggerChart';
import type { RuleRecord } from '../api/stats';

type RuleRecordWithMetadata = RuleRecord & { ruleLabel: string; ruleDescription?: string };

export default function TriggerStatsPage() {
  const { t } = useTranslation();
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ['rule_stats'], queryFn: fetchRuleStats });
  const { data: rules, isLoading: rulesLoading } = useQuery({ queryKey: ['rules'], queryFn: fetchRules });
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [selectedRecord, setSelectedRecord] = useState<RuleRecordWithMetadata | null>(null);
  const RULES_PER_PAGE = 5;

  const loading = statsLoading || rulesLoading;

  const allRules = rules ?? [];
  const statsData = stats?.data ?? {};

  const merged = useMemo(() => allRules.map(r => ({
    rule_id: r.rule_id,
    name: r.name,
    description: r.description,
    stat: statsData[r.name] ?? { count: 0, description: r.description, records: [] },
  })), [allRules, statsData]);

  const filtered = merged.filter(r => {
    const target = `${r.name} ${r.description}`.toLowerCase();
    return target.includes(query.toLowerCase());
  });

  const pages = Math.max(1, Math.ceil(filtered.length / RULES_PER_PAGE));
  const pagedRules = useMemo(
    () => filtered.slice((page - 1) * RULES_PER_PAGE, page * RULES_PER_PAGE),
    [filtered, page],
  );

  useEffect(() => {
    setPage(1);
  }, [query]);

  useEffect(() => {
    // Clamp current page when filtered results shrink to avoid empty views
    setPage(p => Math.min(Math.max(1, p), pages));
  }, [pages]);

  const chartData = filtered
    .filter(r => r.stat.count > 0)
    .map(r => ({ name: r.name, count: r.stat.count }));

  if (loading) return <div className="flex justify-center h-64"><Spinner label={t('stats.loading')} /></div>;

  return (
    <div className="space-y-6">
        <Card>
          <CardHeader className="flex items-center gap-2">
            <Icon icon={chart2Bold} fontSize={16} className="text-primary" />
            <span className="font-semibold">{t('stats.overview')}</span>
          </CardHeader>
          <CardBody>
            <TriggerChart data={chartData} />
          </CardBody>
      </Card>

      <div className="flex justify-end">
        <Input
          size="sm"
          startContent={<Icon icon={textFieldFocusBold} fontSize={14} className="text-default-500" />}
          className="w-64"
          placeholder={t('stats.searchRules')}
          value={query}
          onValueChange={setQuery}
        />
      </div>

      <div className="space-y-4">
        {pagedRules.map(r => (
              <Card key={r.rule_id} className="border border-default-200 shadow-sm">
                <CardHeader className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon icon={chatDotsBold} fontSize={16} className="text-primary" />
                    <div>
                      <span className="font-medium text-default-900">{r.name}</span>
                      <p className="text-xs text-default-500">{r.description}</p>
                    </div>
                  </div>
              <Chip
                size="sm"
                color={r.stat.count > 0 ? 'warning' : 'default'}
                variant="flat"
              >
                {t('stats.triggers', { count: r.stat.count })}
              </Chip>
            </CardHeader>
            {r.stat.records.length > 0 && (
              <CardBody className="pt-0 space-y-2">
                <Accordion>
                  {r.stat.records.slice(0, 5).map(rec => (
                    <AccordionItem
                      key={rec.id}
                      title={
                        <div className="flex items-center gap-2 text-sm">
                          <span className="text-default-500">{rec.trigger_time}</span>
                          <Progress
                            size="sm"
                            value={rec.confidence * 100}
                            color="warning"
                            className="w-24"
                            aria-label={t('stats.confidence')}
                          />
                          <div className="flex items-center gap-1 text-xs text-default-500">
                            <Icon icon={clockCircleBold} fontSize={12} />
                            {(rec.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                      }
                    >
                      <div className="space-y-3">
                        <p className="text-sm text-default-700 whitespace-pre-wrap break-words">{rec.reason}</p>
                        <div className="space-y-2">
                          {rec.messages.map((m, i) => (
                            <div key={i} className="flex justify-start">
                              <div className="max-w-[80%] rounded-2xl border px-3 py-2 shadow-sm bg-primary-50 border-primary-100 text-primary-800">
                                <p className="text-xs font-medium text-primary-600 mb-1">{m.sender}</p>
                                <p className="text-sm whitespace-pre-wrap break-words">{m.content}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                        <Button
                          size="sm"
                          variant="light"
                          color="primary"
                          className="mt-1"
                          onPress={() => setSelectedRecord({ ...rec, ruleLabel: r.name, ruleDescription: r.description })}
                        >
                          {t('stats.viewDetails')}
                        </Button>
                      </div>
                    </AccordionItem>
                  ))}
                </Accordion>
              </CardBody>
            )}
          </Card>
        ))}
        <div className="flex items-center justify-between text-sm text-default-500">
          <span>{t('common.entries', { count: filtered.length })}</span>
          <Pagination
            size="sm"
            showControls
            total={pages}
            page={page}
            onChange={setPage}
            color="primary"
          />
        </div>
      </div>

      <Modal
        isOpen={!!selectedRecord}
        onClose={() => setSelectedRecord(null)}
        size="lg"
        scrollBehavior="inside"
      >
        <ModalContent>
          {selectedRecord && (
            <>
              <ModalHeader className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Icon icon={chatDotsBold} fontSize={18} className="text-primary" />
                  <span className="font-semibold">{selectedRecord.ruleLabel}</span>
                </div>
                {selectedRecord.ruleDescription && (
                  <p className="text-sm text-default-500">{selectedRecord.ruleDescription}</p>
                )}
              </ModalHeader>
              <ModalBody className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex items-center gap-2 text-sm text-default-700">
                    <Icon icon={clockCircleBold} fontSize={16} className="text-warning" />
                    <span>{t('stats.triggeredAt', { time: selectedRecord.trigger_time })}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-default-700">
                    <Icon icon={chart2Bold} fontSize={16} className="text-warning" />
                    <span>{t('stats.confidenceValue', { value: (selectedRecord.confidence * 100).toFixed(0) })}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-default-700">
                    <Icon icon={documentTextBold} fontSize={16} className="text-primary" />
                    <span>{selectedRecord.result}</span>
                  </div>
                  {selectedRecord.chat_id && (
                    <div className="flex items-center gap-2 text-sm text-default-700">
                      <Icon icon={chatDotsBold} fontSize={16} className="text-default-500" />
                      <span>{t('stats.chatId', { id: selectedRecord.chat_id })}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-sm text-default-700">
                    <Icon
                      icon={selectedRecord.trigger_suppressed ? dangerTriangleBold : documentTextBold}
                      fontSize={16}
                      className={selectedRecord.trigger_suppressed ? 'text-warning' : 'text-success'}
                    />
                    <span>
                      {selectedRecord.trigger_suppressed
                        ? t('stats.suppressed')
                        : t('stats.notSuppressed')}
                    </span>
                  </div>
                </div>
                {selectedRecord.trigger_suppressed && (
                  <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-700 space-y-1">
                    <p className="font-semibold">{t('stats.suppressed')}</p>
                    {selectedRecord.suppression_reason && (
                      <p className="whitespace-pre-wrap break-words">{selectedRecord.suppression_reason}</p>
                    )}
                  </div>
                )}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-default-700">
                    <Icon icon={documentTextBold} fontSize={16} className="text-primary" />
                    <span>{t('stats.reasonLabel')}</span>
                  </div>
                  <p className="text-sm text-default-700 whitespace-pre-wrap break-words">{selectedRecord.reason}</p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-default-700">
                    <Icon icon={tagBold} fontSize={16} className="text-secondary" />
                    <span>{t('stats.extractedParams')}</span>
                  </div>
                  {selectedRecord.extracted_params && Object.keys(selectedRecord.extracted_params).length > 0 ? (
                    <div className="grid gap-2">
                      {Object.entries(selectedRecord.extracted_params).map(([key, val]) => (
                        <div
                          key={key}
                          className="flex items-start gap-2 rounded-lg border border-default-200 bg-default-50 px-3 py-2"
                        >
                          <Chip size="sm" variant="flat" color="secondary" className="shrink-0">{key}</Chip>
                          <Snippet
                            hideSymbol
                            variant="flat"
                            size="sm"
                            className="text-left"
                            classNames={{ pre: 'whitespace-pre-wrap break-words text-sm' }}
                          >
                            {String(val)}
                          </Snippet>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-default-500">{t('stats.noParams')}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-default-700">
                    <Icon icon={chatDotsBold} fontSize={16} className="text-primary" />
                    <span>{t('stats.contextMessages')}</span>
                  </div>
                  <div className="space-y-3">
                    {selectedRecord.messages.map((m, idx) => (
                      <div key={idx} className="flex justify-start">
                        <div className="max-w-[80%] rounded-2xl border px-3 py-2 shadow-sm bg-primary-50 border-primary-100 text-primary-800">
                          <p className="text-xs font-medium text-primary-600 mb-1">{m.sender}</p>
                          <p className="text-sm whitespace-pre-wrap break-words">{m.content}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </ModalBody>
              <ModalFooter>
                <Button variant="light" onPress={() => setSelectedRecord(null)}>
                  {t('common.cancel')}
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>
    </div>
  );
}
