import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, Chip, Input, Select, SelectItem, Spinner,
  Tab, Tabs, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell,
} from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { fetchQueues } from '../api/queues';
import type { QueueMessage } from '../api/queues';

const COLUMNS = ['adapter', 'type', 'chat', 'sender', 'content', 'time'];

function QueueTable({ messages }: { messages: QueueMessage[] }) {
  const { t } = useTranslation();
  const [adapterFilter, setAdapterFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [searchField, setSearchField] = useState<'content' | 'sender_name' | 'chat_id' | 'adapter'>('content');
  const [query, setQuery] = useState('');

  const adapters = [...new Set(messages.map(m => m.adapter))];
  const types    = [...new Set(messages.map(m => m.chat_type))];

  const filtered = messages.filter(m => {
    const fieldValue =
      searchField === 'content' ? m.content
      : searchField === 'sender_name' ? m.sender_name
      : searchField === 'chat_id' ? m.chat_id
      : m.adapter;

    return (
      (!adapterFilter || m.adapter === adapterFilter) &&
      (typeFilter === 'all' || m.chat_type === typeFilter) &&
      (!query || String(fieldValue ?? '').toLowerCase().includes(query.toLowerCase()))
    );
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        <Select
          size="sm"
          className="w-40"
          placeholder={t('queues.allAdapters')}
          onSelectionChange={k => setAdapterFilter(Array.from(k)[0] as string ?? '')}
        >
          {adapters.map(a => <SelectItem key={a}>{a}</SelectItem>)}
        </Select>
        <Select
          size="sm"
          className="w-36"
          selectedKeys={[typeFilter]}
          onSelectionChange={k => setTypeFilter(Array.from(k)[0] as string ?? 'all')}
        >
          {[
            <SelectItem key="all">{t('queues.allTypes')}</SelectItem>,
            ...types.map(t => <SelectItem key={t}>{t}</SelectItem>),
          ]}
        </Select>
        <Select
          size="sm"
          className="w-44"
          selectedKeys={[searchField]}
          onSelectionChange={k => setSearchField(Array.from(k)[0] as typeof searchField)}
        >
          <SelectItem key="content">{t('queues.content')}</SelectItem>
          <SelectItem key="sender_name">{t('queues.sender')}</SelectItem>
          <SelectItem key="chat_id">{t('queues.chatId')}</SelectItem>
          <SelectItem key="adapter">{t('queues.adapter')}</SelectItem>
        </Select>
        <Input
          size="sm"
          className="w-60"
          placeholder={t('queues.search')}
          value={query}
          onValueChange={setQuery}
        />
      </div>
      <Table aria-label={t('queues.messages')} removeWrapper>
        <TableHeader>
          {COLUMNS.map(c => <TableColumn key={c}>{t(`queues.${c}`)}</TableColumn>)}
        </TableHeader>
        <TableBody emptyContent={t('queues.noMessages')}>
          {filtered.map((m, i) => (
            <TableRow key={i}>
              <TableCell><Chip size="sm" variant="flat">{m.adapter}</Chip></TableCell>
              <TableCell><Chip size="sm" color="primary" variant="flat">{m.chat_type}</Chip></TableCell>
              <TableCell className="text-xs text-default-500">{m.chat_id}</TableCell>
              <TableCell className="text-sm">{m.sender_name}</TableCell>
              <TableCell className="text-sm max-w-xs truncate">{m.content}</TableCell>
              <TableCell className="text-xs text-default-400">{new Date(m.timestamp).toLocaleString()}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function QueuesPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ['queues'],
    queryFn: fetchQueues,
    refetchInterval: 10_000,
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label={t('queues.loading')} /></div>;

  return (
    <Tabs aria-label={t('queues.messages')}>
      <Tab key="pending" title={t('queues.pending', { count: data?.pending.length ?? 0 })}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.pending ?? []} />
          </CardBody>
        </Card>
      </Tab>
      <Tab key="history" title={t('queues.history', { count: data?.history.length ?? 0 })}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.history ?? []} />
          </CardBody>
        </Card>
      </Tab>
    </Tabs>
  );
}
