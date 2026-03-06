import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, CardBody, Chip, Select, SelectItem, Spinner } from '@heroui/react';
import { RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { fetchLogs } from '../api/logs';
import type { LogEntry } from '../api/logs';

const LEVEL_COLORS: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
  DEBUG:    'default',
  INFO:     'primary',
  SUCCESS:  'success',
  WARNING:  'warning',
  ERROR:    'danger',
  CRITICAL: 'danger',
};

export default function LogsPage() {
  const { t } = useTranslation();
  const [levelFilter, setLevelFilter] = useState('ALL');
  const { data: logs, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['logs'],
    queryFn: () => fetchLogs(200),
    refetchInterval: 10_000,
  });

  const levels = ['ALL', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'];

  const filtered = (logs ?? []).filter(l =>
    levelFilter === 'ALL' || l.level === levelFilter
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Select
          size="sm"
          className="w-36"
          selectedKeys={[levelFilter]}
          onSelectionChange={k => setLevelFilter(Array.from(k)[0] as string ?? 'ALL')}
          aria-label={t('logs.filter')}
        >
          {levels.map(l => <SelectItem key={l}>{l}</SelectItem>)}
        </Select>
        <Button
          size="sm"
          variant="flat"
          startContent={<RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />}
          onPress={() => refetch()}
        >
          {t('logs.refresh')}
        </Button>
        <span className="text-xs text-default-400">{t('common.entries', { count: filtered.length })}</span>
      </div>

      {isLoading && <Spinner label={t('logs.loading')} />}

      <Card>
        <CardBody className="p-2 space-y-1 max-h-[70vh] overflow-y-auto font-mono">
          {filtered.length === 0 && <p className="text-default-400 text-sm p-2">{t('logs.noEntries')}</p>}
          {filtered.map((log, i) => (
            <LogRow key={i} log={log} />
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

function LogRow({ log }: { log: LogEntry }) {
  const color = LEVEL_COLORS[log.level] ?? 'default';
  return (
    <div className="flex items-start gap-2 text-xs py-1 border-b border-divider last:border-0">
      <span className="text-default-400 shrink-0 w-36">
        {new Date(log.timestamp).toLocaleTimeString()}
      </span>
      <Chip size="sm" color={color} variant="flat" className="shrink-0 text-[10px]">
        {log.level}
      </Chip>
      <span className="text-default-700 break-all">{log.message}</span>
    </div>
  );
}
