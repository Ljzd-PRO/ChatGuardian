import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, CardBody, Chip, Spinner } from '@heroui/react';
import { Play, Square } from 'lucide-react';
import { fetchAdapters, startAdapters, stopAdapters } from '../api/adapters';

export default function AdaptersPage() {
  const qc = useQueryClient();
  const { data: adapters, isLoading } = useQuery({
    queryKey: ['adapters'],
    queryFn: fetchAdapters,
    refetchInterval: 5_000,
  });

  const start = useMutation({ mutationFn: startAdapters, onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });
  const stop  = useMutation({ mutationFn: stopAdapters,  onSuccess: () => qc.invalidateQueries({ queryKey: ['adapters'] }) });

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading adapters…" /></div>;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button
          color="success"
          variant="flat"
          startContent={<Play size={14} />}
          isLoading={start.isPending}
          onPress={() => start.mutate()}
        >
          Start All
        </Button>
        <Button
          color="danger"
          variant="flat"
          startContent={<Square size={14} />}
          isLoading={stop.isPending}
          onPress={() => stop.mutate()}
        >
          Stop All
        </Button>
      </div>

      {adapters?.length === 0 && (
        <p className="text-default-400 text-sm">No adapters configured.</p>
      )}

      <div className="space-y-3">
        {adapters?.map(a => (
          <Card key={a.name}>
            <CardBody className="flex flex-row items-center justify-between">
              <div>
                <p className="font-medium text-default-900">{a.name}</p>
                <p className="text-xs text-default-400">Adapter</p>
              </div>
              <Chip color={a.running ? 'success' : 'default'} variant="flat" size="sm">
                {a.running ? 'Running' : 'Stopped'}
              </Chip>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
