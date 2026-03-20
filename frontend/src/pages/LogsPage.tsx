import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Card, CardBody, Chip, Select, SelectItem, Spinner,
  Modal, ModalBody, ModalContent, ModalFooter, ModalHeader,
} from '@heroui/react';
import { Icon } from '@iconify/react';
import refreshCircleBold from '@iconify/icons-solar/refresh-circle-bold';
import restartBold from '@iconify/icons-solar/restart-bold';
import tagBold from '@iconify/icons-solar/tag-bold';
import trashBin2Bold from '@iconify/icons-solar/trash-bin-2-bold';
import { useTranslation } from 'react-i18next';
import { clearLogs, fetchLogs, fetchVersion, restartBackend } from '../api/logs';
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

export default function LogsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [confirmRestart, setConfirmRestart] = useState(false);
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

  const clear = useMutation({
    mutationFn: clearLogs,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['logs'] }),
  });
  const restart = useMutation({ mutationFn: restartBackend });

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
          color="warning"
          variant="flat"
          startContent={<Icon icon={restartBold} fontSize={ICON_SIZES.button} />}
          isLoading={restart.isPending}
          onPress={() => setConfirmRestart(true)}
        >
          {t('logs.restart')}
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

      {isLoading && <Spinner label={t('logs.loading')} />}

      <Card>
        <CardBody className="p-2 space-y-1 max-h-[70vh] overflow-y-auto font-mono">
          {filtered.length === 0 && <p className="text-default-400 text-sm p-2">{t('logs.noEntries')}</p>}
          {filtered.map((log, i) => (
            <LogRow key={i} log={log} />
          ))}
        </CardBody>
      </Card>

      <Modal isOpen={confirmRestart} onClose={() => setConfirmRestart(false)} size="md">
        <ModalContent>
          <ModalHeader>{t('logs.restartTitle')}</ModalHeader>
          <ModalBody>
            <p className="text-default-600">{t('logs.restartWarning')}</p>
          </ModalBody>
          <ModalFooter>
            <Button variant="flat" onPress={() => setConfirmRestart(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              color="warning"
              startContent={<Icon icon={restartBold} fontSize={ICON_SIZES.button} />}
              isLoading={restart.isPending}
              onPress={() => {
                setConfirmRestart(false);
                restart.mutate();
              }}
            >
              {t('logs.restart')}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
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
