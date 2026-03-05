import { Card, CardBody, CardHeader } from '@heroui/react';
import type { ReactNode } from 'react';

interface StatsCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'default';
  description?: string;
}

export default function StatsCard({ title, value, icon, color = 'default', description }: StatsCardProps) {
  const colorMap = {
    primary: 'text-primary',
    success: 'text-success',
    warning: 'text-warning',
    danger:  'text-danger',
    default: 'text-default-700',
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex items-center gap-2 pb-0">
        {icon && <span className={colorMap[color]}>{icon}</span>}
        <span className="text-sm text-default-500">{title}</span>
      </CardHeader>
      <CardBody className="pt-1">
        <p className={`text-3xl font-bold ${colorMap[color]}`}>{value}</p>
        {description && <p className="text-xs text-default-400 mt-1">{description}</p>}
      </CardBody>
    </Card>
  );
}
