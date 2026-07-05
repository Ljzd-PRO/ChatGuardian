import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Accordion, AccordionItem, Button, Card, CardBody, Chip, Select, SelectItem, Spinner,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import refreshCircleBold from '@iconify/icons-solar/refresh-circle-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import eraserCircleBold from '@iconify/icons-solar/eraser-circle-bold';
import disketteBoldDuotone from '@iconify/icons-solar/diskette-bold-duotone';
import databaseBold from '@iconify/icons-solar/database-bold';
import { useTranslation } from 'react-i18next';
import { clearLogs, fetchLogs, fetchVersion } from '../api/logs';
import { compactStorage, fetchStorageStats, pruneStorage } from '../api/storage';
import type { LogEntry } from '../api/logs';
import { ICON_SIZES } from '../constants/iconSizes';

const LEVEL_COLORS: Record<string, 'default' | 'primary' | 'warning' | 'danger' | 'success'> = {
  DEBUG: 'default',
  INFO: 'primary',
  SUCCESS: 'success',
  WARNING: 'warning',
  ERROR: 'danger',
  CRITICAL: 'danger',
};

function formatBytes(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = value / 1024;
  let unit = units[0];
  for (let i = 1; i < units.length && size >= 1024; i += 1) {
    size /= 1024;
    unit = units[i];
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${unit}`;
}

export default function LogsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [levelFilter, setLevelFilter] = useState('ALL');
  const { data: logs, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['logs'],
    queryFn: () => fetchLogs(200),
    refetchInterval: 10_000,
  });
  const { data: versionInfo } = useQuery({
    queryKey: ['backend-version'],
    queryFn: fetchVersion,
    staleTime: 60_000,
  });
  const { data: storageStats, isLoading: storageLoading } = useQuery({
    queryKey: ['storage-stats'],
    queryFn: fetchStorageStats,
    refetchInterval: 60_000,
  });

  const clear = useMutation({
    mutationFn: clearLogs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logs'] }),
  });
  const prune = useMutation({
    mutationFn: pruneStorage,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['storage-stats'] }),
  });
  const compact = useMutation({
    mutationFn: compactStorage,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['storage-stats'] }),
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
          startContent={(
            <Icon
              icon={refreshCircleBold}
              fontSize={ICON_SIZES.button}
              className={isFetching ? 'animate-spin' : ''}
            />
          )}
          onPress={() => refetch()}
        >
          {t('logs.refresh')}
        </Button>
        <Button
          size="sm"
          color="danger"
          variant="flat"
          startContent={<Icon icon={trashBin2Bold} fontSize={ICON_SIZES.button} />}
          isLoading={clear.isPending}
          onPress={() => clear.mutate()}
        >
          {t('logs.clear')}
        </Button>
        <span className="text-xs text-default-400">{t('common.entries', { count: filtered.length })}</span>
        <Chip
          size="sm"
          variant="flat"
          color="default"
          startContent={<Icon icon={tagBold} fontSize={12} className="text-default-500" />}
        >
          {t('logs.versionLabel')}: {versionInfo?.version ?? t('logs.versionUnknown')}
        </Chip>
      </div>

      <Accordion variant="splitted" className="bg-transparent" itemClasses={{ title: 'w-full' }}>
        <AccordionItem
          key="storage"
          aria-label={t('logs.storageTitle')}
          title={(
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <Icon icon={databaseBold} fontSize={ICON_SIZES.cardHeader} className="text-primary" />
                <span className="font-semibold">{t('logs.storageTitle')}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Chip size="sm" variant="flat" color="primary">
                  {t('logs.databaseSize')}: {formatBytes(storageStats?.database_file_bytes)}
                </Chip>
                <Chip size="sm" variant="flat" color="default">
                  {t('logs.lastPrune')}: {
                    storageStats?.last_storage_prune_at
                      ? new Date(storageStats.last_storage_prune_at).toLocaleString()
                      : t('logs.never')
                  }
                </Chip>
              </div>
            </div>
          )}
        >
          <div className="space-y-3 px-1 pb-2">
            <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-sm text-default-500">{t('logs.storageDescription')}</p>
                <p className="text-xs text-warning mt-1">{t('logs.compactWarning')}</p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="flat"
                  color="primary"
                  startContent={<Icon icon={eraserCircleBold} fontSize={ICON_SIZES.button} />}
                  isLoading={prune.isPending}
                  onPress={() => prune.mutate()}
                >
                  {t('logs.prune')}
                </Button>
                <Button
                  size="sm"
                  variant="flat"
                  color="warning"
                  startContent={<Icon icon={disketteBoldDuotone} fontSize={ICON_SIZES.button} />}
                  isLoading={compact.isPending}
                  onPress={() => compact.mutate()}
                >
                  {t('logs.compact')}
                </Button>
              </div>
            </div>

            {storageLoading ? (
              <Spinner size="sm" label={t('common.loading')} />
            ) : (
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {Object.entries(storageStats?.tables ?? {}).map(([name, table]) => (
                  <div key={name} className="rounded-lg border border-divider px-3 py-2">
                    <div className="text-sm font-medium text-default-800">{name}</div>
                    <div className="text-xs text-default-500">
                      {t('logs.tableRows', { count: table.rows })} · {t('logs.payloadSize')}: {formatBytes(table.payload_bytes)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </AccordionItem>
      </Accordion>

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
