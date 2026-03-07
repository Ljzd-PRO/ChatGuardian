import { useQuery } from '@tanstack/react-query';
import { Button, Card, CardBody, CardHeader, Chip, Spinner, cn } from '@heroui/react';
import { Icon, type IconifyIcon } from '@iconify/react';
import lightningBold from '@iconify/icons-solar/lightning-bold';
import plugCircleBold from '@iconify/icons-solar/plug-circle-bold';
import pulse2Bold from '@iconify/icons-solar/pulse-2-bold';
import shieldCheckBold from '@iconify/icons-solar/shield-check-bold';
import chatDotsBold from '@iconify/icons-solar/chat-dots-bold';
import { useTranslation } from 'react-i18next';
import TriggerChart from '../components/charts/TriggerChart';
import { fetchDashboard } from '../api/dashboard';
import { fetchAdapters } from '../api/adapters';
import { fetchRuleStats } from '../api/stats';
import { ICON_SIZES } from '../constants/iconSizes';
import { Link } from 'react-router-dom';

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

  type StatCard = {
    title: string;
    value: number;
    icon: IconifyIcon;
    color: 'success' | 'warning' | 'danger' | 'secondary';
    href: string;
  };

  const statCards: StatCard[] = [
    {
      title: t('dashboard.totalRules'),
      value: dash?.total_rules ?? 0,
      icon: shieldCheckBold,
      color: 'secondary' as const,
      href: '/rules',
    },
    {
      title: t('dashboard.enabledRules'),
      value: dash?.enabled_rules ?? 0,
      icon: lightningBold,
      color: 'success' as const,
      href: '/rules',
    },
    {
      title: t('dashboard.triggersToday'),
      value: dash?.triggers_today ?? 0,
      icon: pulse2Bold,
      color: 'warning' as const,
      href: '/stats',
    },
    {
      title: t('dashboard.messagesToday'),
      value: dash?.messages_today ?? 0,
      icon: chatDotsBold,
      color: 'secondary' as const,
      href: '/queues',
    },
  ];

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
      <dl className="grid w-full grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map(({ title, value, icon, color, href }, idx) => (
          <Card key={idx} className="relative dark:border-default-100 border border-transparent overflow-hidden">
            <div className="flex p-4 items-center gap-4">
              <div
                className={cn('mt-1 flex h-10 w-10 items-center justify-center rounded-md', {
                  'bg-success-50': color === 'success',
                  'bg-warning-50': color === 'warning',
                  'bg-danger-50': color === 'danger',
                  'bg-secondary-50': color === 'secondary',
                })}
              >
                <Icon
                  className={
                    color === 'success'
                      ? 'text-success'
                      : color === 'warning'
                        ? 'text-warning'
                        : color === 'danger'
                          ? 'text-danger'
                          : 'text-secondary'
                  }
                  icon={icon}
                  fontSize={ICON_SIZES.dashboard}
                />
              </div>

              <div className="flex flex-col gap-y-1">
                <dt className="text-small text-default-500">{title}</dt>
                <dd className="text-default-700 text-3xl font-semibold">{value}</dd>
              </div>
            </div>

            <div className="bg-default-100">
              <Button
                as={Link}
                to={href}
                fullWidth
                className="text-default-500 flex justify-start text-xs data-pressed:scale-100"
                radius="none"
                variant="light"
              >
                {t('dashboard.viewAll')}
              </Button>
            </div>
          </Card>
        ))}
      </dl>

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
          <CardBody>
            {adapters?.length ? (
              <div className="flex flex-wrap gap-2">
                {adapters.map(a => (
                  <Chip
                    key={a.name}
                    size="sm"
                    variant="flat"
                    color={a.running ? 'success' : 'default'}
                    startContent={<Icon icon={plugCircleBold} fontSize={ICON_SIZES.chip} />}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{a.name}</span>
                      <span className="text-xs text-default-600">
                        {a.running ? t('common.running') : t('common.stopped')}
                      </span>
                    </div>
                  </Chip>
                ))}
              </div>
            ) : (
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
