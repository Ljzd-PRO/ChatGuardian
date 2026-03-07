import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Tooltip,
} from 'recharts';
import { useTranslation } from 'react-i18next';

interface TriggerChartProps {
  data: { name: string; count: number }[];
}

const COLORS = [
  'hsl(var(--heroui-primary-500))',
  'hsl(var(--heroui-secondary-500))',
  'hsl(var(--heroui-success-500))',
  'hsl(var(--heroui-warning-500))',
  'hsl(var(--heroui-danger-500))',
  'hsl(var(--heroui-primary-400))',
];

export default function TriggerChart({ data }: TriggerChartProps) {
  const { t } = useTranslation();
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-40 text-default-400 text-sm">
        {t('triggerChart.noData')}
      </div>
    );
  }

  const total = data.reduce((sum, item) => sum + (item.count ?? 0), 0);
  const totalLabel = t('common.total');

  const coloredData = data.map((item, index) => ({
    ...item,
    fill: COLORS[index % COLORS.length],
  }));

  return (
    <div className="flex flex-col gap-4">
      <ResponsiveContainer width="100%" height={240} className="[&_.recharts-surface]:outline-hidden">
        <PieChart>
          <Tooltip />
          <Pie
            data={coloredData}
            dataKey="count"
            nameKey="name"
            innerRadius="60%"
            paddingAngle={2}
            strokeWidth={0}
          />
        </PieChart>
      </ResponsiveContainer>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-default-700">
        {coloredData.map((item) => (
          <div key={item.name} className="flex items-center justify-between gap-2 rounded-medium border border-default-200 px-3 py-2">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: item.fill }}
              />
              <span className="truncate">{item.name}</span>
            </div>
            <span className="font-semibold text-default-900">{item.count}</span>
          </div>
        ))}
        <div className="flex items-center justify-between gap-2 rounded-medium bg-default-50 px-3 py-2 text-default-600">
          <span className="font-medium">{totalLabel}</span>
          <span className="font-semibold text-default-900">{total}</span>
        </div>
      </div>
    </div>
  );
}
