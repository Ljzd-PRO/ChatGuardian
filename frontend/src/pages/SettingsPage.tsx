import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, CardHeader, Chip, Divider, Spinner,
} from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { fetchSettings } from '../api/settings';

const SECRET_KEYS = ['key', 'token', 'password'];

export default function SettingsPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings });

  const entries = useMemo(() => {
    if (!data) return [];
    return Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  function renderValue(value: unknown, key: string) {
    const isSecret = SECRET_KEYS.some(k => key.toLowerCase().includes(k));
    if (value === null || value === undefined) return t('settingsPage.none');
    if (Array.isArray(value)) return value.length ? value.join(', ') : t('settingsPage.emptyArray');
    if (typeof value === 'object') return JSON.stringify(value);
    if (isSecret && String(value).length > 2) return '••••••';
    return String(value);
  }

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('settingsPage.loading')} /></div>;

  return (
    <div className="space-y-4 max-w-4xl">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <p className="font-semibold">{t('settingsPage.title')}</p>
            <p className="text-sm text-default-500">{t('settingsPage.description')}</p>
          </div>
          <Chip size="sm" variant="flat" color="warning">{t('settingsPage.previewOnly')}</Chip>
        </CardHeader>
        <Divider />
        <CardBody className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {entries.map(([key, value]) => (
            <div key={key} className="p-3 rounded-lg border border-divider bg-content1 space-y-1">
              <p className="text-xs uppercase text-default-400 tracking-wide">{key}</p>
              <p className="text-sm font-medium text-default-800 break-words">{renderValue(value, key)}</p>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
