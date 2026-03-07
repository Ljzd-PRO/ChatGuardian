import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import {
  Accordion, AccordionItem, Card, CardBody, CardHeader, Chip, Input, Progress, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import chart2Bold from '@iconify/icons-solar/chart-2-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import clockCircleBold from '@iconify/icons-solar/clock-circle-bold';
import magniferBold from '@iconify/icons-solar/magnifer-bold';
import { useTranslation } from 'react-i18next';
import { fetchRuleStats } from '../api/stats';
import { fetchRules } from '../api/rules';
import TriggerChart from '../components/charts/TriggerChart';

export default function TriggerStatsPage() {
  const { t } = useTranslation();
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ['rule_stats'], queryFn: fetchRuleStats });
  const { data: rules, isLoading: rulesLoading } = useQuery({ queryKey: ['rules'], queryFn: fetchRules });
  const [query, setQuery] = useState('');

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

  const chartData = filtered
    .filter(r => r.stat.count > 0)
    .map(r => ({ name: r.name, count: r.stat.count }));

  if (loading) return <div className="flex justify-center h-64"><Spinner label={t('stats.loading')} /></div>;

  return (
    <div className="space-y-6">
        <Card>
          <CardHeader className="flex items-center gap-2">
            <Icon icon={chart2Bold} width={16} className="text-primary" />
            <span className="font-semibold">{t('stats.overview')}</span>
          </CardHeader>
          <CardBody>
            <TriggerChart data={chartData} />
          </CardBody>
      </Card>

      <div className="flex justify-end">
        <Input
          size="sm"
          startContent={<Icon icon={magniferBold} width={14} className="text-default-500" />}
          className="w-64"
          placeholder={t('stats.searchRules')}
          value={query}
          onValueChange={setQuery}
        />
      </div>

      <div className="space-y-4">
        {filtered.map(r => (
              <Card key={r.rule_id} className="border border-default-200 shadow-sm">
                <CardHeader className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon icon={chatDotsBold} width={16} className="text-primary" />
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
                            <Icon icon={clockCircleBold} width={12} />
                            {(rec.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                      }
                    >
                      <div className="space-y-1">
                        <p className="text-sm text-default-600 italic">{rec.reason}</p>
                        <div className="space-y-1 mt-2">
                          {rec.messages.map((m, i) => (
                            <div key={i} className="text-xs p-3 bg-default-100 rounded-lg border border-default-200">
                              <span className="font-medium text-default-700">{m.sender}: </span>
                              <span className="text-default-600">{m.content}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </AccordionItem>
                  ))}
                </Accordion>
              </CardBody>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
