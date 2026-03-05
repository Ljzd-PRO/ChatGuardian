import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, CardBody, CardHeader, Input, Spinner, Chip, Progress,
} from '@heroui/react';
import { Search } from 'lucide-react';
import { fetchUserProfiles } from '../api/users';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts';

export default function UserProfilesPage() {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['user_profiles'],
    queryFn: fetchUserProfiles,
  });
  const [search, setSearch] = useState('');

  const filtered = (profiles ?? []).filter(p =>
    p.user_name.toLowerCase().includes(search.toLowerCase()) ||
    p.user_id.toLowerCase().includes(search.toLowerCase())
  );

  if (isLoading) return <div className="flex justify-center h-64"><Spinner label="Loading profiles…" /></div>;

  return (
    <div className="space-y-4">
      <Input
        placeholder="Search users…"
        value={search}
        onValueChange={setSearch}
        startContent={<Search size={16} />}
        className="max-w-sm"
      />
      {filtered.length === 0 && (
        <p className="text-default-400 text-sm">No user profiles yet.</p>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {filtered.map(p => {
          const interests = Object.entries(p.interests).map(([, v]) => ({
            topic: v.topic,
            score: Math.round(v.score * 100),
          }));

          return (
            <Card key={p.user_id}>
              <CardHeader className="pb-0">
                <div>
                  <p className="font-semibold text-default-900">{p.user_name || p.user_id}</p>
                  <p className="text-xs text-default-400">{p.user_id}</p>
                </div>
              </CardHeader>
              <CardBody className="space-y-3">
                {interests.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-default-600 mb-1">Interests</p>
                    <ResponsiveContainer width="100%" height={160}>
                      <RadarChart data={interests}>
                        <PolarGrid />
                        <PolarAngleAxis dataKey="topic" tick={{ fontSize: 11 }} />
                        <Radar dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} />
                        <Tooltip />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {p.active_groups.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-default-600 mb-1">Active Groups</p>
                    <div className="flex flex-wrap gap-1">
                      {p.active_groups.map(g => (
                        <Chip key={g.chat_id} size="sm" variant="flat">
                          {g.chat_name || g.chat_id} ({g.message_count})
                        </Chip>
                      ))}
                    </div>
                  </div>
                )}

                {Object.keys(p.frequent_contacts).length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-default-600 mb-1">Frequent Contacts</p>
                    <div className="space-y-1">
                      {Object.values(p.frequent_contacts).slice(0, 3).map(c => (
                        <div key={c.user_id} className="flex items-center justify-between text-xs">
                          <span className="text-default-700">{c.display_name || c.user_id}</span>
                          <Progress size="sm" value={c.interaction_count} maxValue={100} className="w-20" aria-label="Interaction" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardBody>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
