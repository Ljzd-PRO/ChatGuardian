import { useQuery } from '@tanstack/react-query';
import { Card, CardBody, CardHeader, Chip, Spinner } from '@heroui/react';
import { ShieldCheck, Zap, TrendingUp, Activity } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import StatsCard from '../components/charts/StatsCard';
import TriggerChart from '../components/charts/TriggerChart';
import { fetchDashboard } from '../api/dashboard';
import { fetchAdapters } from '../api/adapters';
import { fetchRuleStats } from '../api/stats';

export default function DashboardPage() {
  const { t } = useTranslation();
  const { data: dash, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 30_000,
  });

  const { data: adapters } = useQuery({
    queryKey: ['adapters'],
    queryFn: fetchAdapters,
    refetchInterval: 30_000,
  });

  const { data: stats } = useQuery({
    queryKey: ['rule_stats'],
    queryFn: fetchRuleStats,
    refetchInterval: 30_000,
  });

  const chartData = stats
    ? Object.entries(stats.data).map(([name, s]) => ({ name, count: s.count }))
    : [];

  const recentTriggers = stats
    ? Object.values(stats.data)
        .flatMap(s => s.records)
        .sort((a, b) => b.trigger_time.localeCompare(a.trigger_time))
        .slice(0, 10)
    : [];

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spinner label={t('dashboard.loading')} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard
          title={t('dashboard.totalRules')}
          value={dash?.total_rules ?? 0}
          icon={<ShieldCheck size={18} />}
          color="primary"
        />
        <StatsCard
          title={t('dashboard.enabledRules')}
          value={dash?.enabled_rules ?? 0}
          icon={<Zap size={18} />}
          color="success"
        />
        <StatsCard
          title={t('dashboard.triggersToday')}
          value={dash?.triggers_today ?? 0}
          icon={<Activity size={18} />}
          color="warning"
        />
        <StatsCard
          title={t('dashboard.triggerRate')}
          value={`${((dash?.trigger_rate ?? 0) * 100).toFixed(1)}%`}
          icon={<TrendingUp size={18} />}
          color="danger"
        />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Chart */}
        <Card>
          <CardHeader className="pb-0">
            <span className="font-semibold text-default-800">{t('dashboard.triggersPerRule')}</span>
          </CardHeader>
          <CardBody>
            <TriggerChart data={chartData} />
          </CardBody>
        </Card>

        {/* Adapter status */}
        <Card>
          <CardHeader className="pb-0">
            <span className="font-semibold text-default-800">{t('dashboard.adapters')}</span>
          </CardHeader>
          <CardBody className="space-y-2">
            {adapters?.length ? adapters.map(a => (
              <div key={a.name} className="flex items-center justify-between py-1">
                <span className="text-sm text-default-700">{a.name}</span>
                <Chip
                  size="sm"
                  color={a.running ? 'success' : 'default'}
                  variant="flat"
                >
                  {a.running ? t('common.running') : t('common.stopped')}
                </Chip>
              </div>
            )) : (
              <p className="text-sm text-default-400">{t('dashboard.noAdapters')}</p>
            )}
          </CardBody>
        </Card>
      </div>

        {/* Recent triggers */}
        <Card>
          <CardHeader className="pb-0">
            <span className="font-semibold text-default-800">{t('dashboard.recentTriggers')}</span>
          </CardHeader>
          <CardBody>
            {recentTriggers.length ? (
            <div className="space-y-2">
              {recentTriggers.map(r => (
                <div key={r.id} className="flex items-start justify-between gap-2 py-2 border-b border-divider last:border-0">
                  <div>
                    <p className="text-sm font-medium text-default-800">{r.rule_name}</p>
                    <p className="text-xs text-default-500">{r.reason}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <Chip size="sm" color="warning" variant="flat">{(r.confidence * 100).toFixed(0)}%</Chip>
                    <p className="text-xs text-default-400 mt-1">{r.trigger_time}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-default-400">{t('dashboard.noTriggers')}</p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
