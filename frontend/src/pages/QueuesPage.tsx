import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, Chip, Select, SelectItem, Spinner,
  Tab, Tabs, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell,
} from '@heroui/react';
import { fetchQueues } from '../api/queues';
import type { QueueMessage } from '../api/queues';

const COLUMNS = ['Adapter', 'Type', 'Chat', 'Sender', 'Content', 'Time'];

function QueueTable({ messages }: { messages: QueueMessage[] }) {
  const [adapterFilter, setAdapterFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  const adapters = [...new Set(messages.map(m => m.adapter))];
  const types    = [...new Set(messages.map(m => m.chat_type))];

  const filtered = messages.filter(m =>
    (!adapterFilter || m.adapter === adapterFilter) &&
    (typeFilter === 'all' || m.chat_type === typeFilter)
  );

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        <Select
          size="sm"
          className="w-40"
          placeholder="All adapters"
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
            <SelectItem key="all">All types</SelectItem>,
            ...types.map(t => <SelectItem key={t}>{t}</SelectItem>),
          ]}
        </Select>
      </div>
      <Table aria-label="Messages" removeWrapper>
        <TableHeader>
          {COLUMNS.map(c => <TableColumn key={c}>{c}</TableColumn>)}
        </TableHeader>
        <TableBody emptyContent="No messages">
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
  const { data, isLoading } = useQuery({
    queryKey: ['queues'],
    queryFn: fetchQueues,
    refetchInterval: 10_000,
  });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading queues…" /></div>;

  return (
    <Tabs aria-label="Queues">
      <Tab key="pending" title={`Pending (${data?.pending.length ?? 0})`}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.pending ?? []} />
          </CardBody>
        </Card>
      </Tab>
      <Tab key="history" title={`History (${data?.history.length ?? 0})`}>
        <Card className="mt-2">
          <CardBody>
            <QueueTable messages={data?.history ?? []} />
          </CardBody>
        </Card>
      </Tab>
    </Tabs>
  );
}
