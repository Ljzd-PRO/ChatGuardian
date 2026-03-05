import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, Chip, Select, SelectItem, Spinner,
  Tab, Tabs, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell, Input,
} from '@heroui/react';
import { Search } from 'lucide-react';
import { fetchQueues } from '../api/queues';
import type { QueueMessage } from '../api/queues';

const COLUMNS = ['Adapter', 'Type', 'Chat', 'Sender', 'Content', 'Time'];

type SearchField = 'all' | 'chat_id' | 'sender_name' | 'content' | 'adapter';
const SEARCH_FIELDS: { key: SearchField; label: string }[] = [
  { key: 'all',         label: 'All fields' },
  { key: 'adapter',     label: 'Adapter' },
  { key: 'chat_id',     label: 'Chat ID' },
  { key: 'sender_name', label: 'Sender' },
  { key: 'content',     label: 'Content' },
];

function QueueTable({ messages }: { messages: QueueMessage[] }) {
  const [adapterFilter, setAdapterFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [searchField, setSearchField] = useState<SearchField>('all');

  const adapters = [...new Set(messages.map(m => m.adapter))];
  const types    = [...new Set(messages.map(m => m.chat_type))];

  const q = searchText.toLowerCase();

  const filtered = messages.filter(m => {
    if (adapterFilter && m.adapter !== adapterFilter) return false;
    if (typeFilter !== 'all' && m.chat_type !== typeFilter) return false;
    if (q) {
      const haystack =
        searchField === 'all'
          ? `${m.adapter} ${m.chat_id} ${m.sender_name} ${m.content}`.toLowerCase()
          : String(m[searchField] ?? '').toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

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
        <Select
          size="sm"
          className="w-36"
          selectedKeys={[searchField]}
          onSelectionChange={k => setSearchField((Array.from(k)[0] as SearchField) ?? 'all')}
          aria-label="Search field"
        >
          {SEARCH_FIELDS.map(f => <SelectItem key={f.key}>{f.label}</SelectItem>)}
        </Select>
        <Input
          size="sm"
          placeholder="Search…"
          value={searchText}
          onValueChange={setSearchText}
          startContent={<Search size={14} className="text-default-400 shrink-0" />}
          isClearable
          onClear={() => setSearchText('')}
          className="flex-1 min-w-[160px]"
        />
      </div>
      <p className="text-xs text-default-400">{filtered.length} / {messages.length} messages</p>
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
