import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, CardHeader, Chip, Spinner,
  Accordion, AccordionItem, Progress,
} from '@heroui/react';
import { fetchRuleStats } from '../api/stats';
import { fetchRules } from '../api/rules';
import TriggerChart from '../components/charts/TriggerChart';

export default function TriggerStatsPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({ queryKey: ['rule_stats'], queryFn: fetchRuleStats });
  const { data: rules, isLoading: rulesLoading } = useQuery({ queryKey: ['rules'], queryFn: fetchRules });

  const loading = statsLoading || rulesLoading;

  const allRules = rules ?? [];
  const statsData = stats?.data ?? {};

  const merged = allRules.map(r => ({
    rule_id: r.rule_id,
    name: r.name,
    description: r.description,
    stat: statsData[r.name] ?? { count: 0, description: r.description, records: [] },
  }));

  const chartData = merged
    .filter(r => r.stat.count > 0)
    .map(r => ({ name: r.name, count: r.stat.count }));

  if (loading) return <div className="flex justify-center h-64"><Spinner label="Loading stats…" /></div>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><span className="font-semibold">Trigger Overview</span></CardHeader>
        <CardBody>
          <TriggerChart data={chartData} />
        </CardBody>
      </Card>

      <div className="space-y-3">
        {merged.map(r => (
          <Card key={r.rule_id}>
            <CardHeader className="flex items-center justify-between">
              <div>
                <span className="font-medium text-default-900">{r.name}</span>
                <p className="text-xs text-default-500">{r.description}</p>
              </div>
              <Chip
                size="sm"
                color={r.stat.count > 0 ? 'warning' : 'default'}
                variant="flat"
              >
                {r.stat.count} triggers
              </Chip>
            </CardHeader>
            {r.stat.records.length > 0 && (
              <CardBody className="pt-0">
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
                            aria-label="Confidence"
                          />
                          <span className="text-xs text-default-500">{(rec.confidence * 100).toFixed(0)}%</span>
                        </div>
                      }
                    >
                      <div className="space-y-1">
                        <p className="text-sm text-default-600 italic">{rec.reason}</p>
                        <div className="space-y-1 mt-2">
                          {rec.messages.map((m, i) => (
                            <div key={i} className="text-xs p-2 bg-default-100 rounded">
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
