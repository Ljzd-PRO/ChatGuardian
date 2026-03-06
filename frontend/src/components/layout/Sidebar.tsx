import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, ShieldCheck, BarChart2, Users,
  Plug, Brain, Bell, ListOrdered, ScrollText, Settings, X, Menu,
} from 'lucide-react';
import { Button } from '@heroui/react';
import { useTranslation } from 'react-i18next';

const NAV_ITEMS = [
  { path: '/',             labelKey: 'layout.nav.dashboard',     icon: LayoutDashboard },
  { path: '/rules',        labelKey: 'layout.nav.rules',         icon: ShieldCheck },
  { path: '/stats',        labelKey: 'layout.nav.stats',         icon: BarChart2 },
  { path: '/users',        labelKey: 'layout.nav.users',         icon: Users },
  { path: '/adapters',     labelKey: 'layout.nav.adapters',      icon: Plug },
  { path: '/llm',          labelKey: 'layout.nav.llm',           icon: Brain },
  { path: '/notifications',labelKey: 'layout.nav.notifications', icon: Bell },
  { path: '/queues',       labelKey: 'layout.nav.queues',        icon: ListOrdered },
  { path: '/logs',         labelKey: 'layout.nav.logs',          icon: ScrollText },
  { path: '/settings',     labelKey: 'layout.nav.settings',      icon: Settings },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { pathname } = useLocation();
  const { t } = useTranslation();

  const inner = (
    <nav className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-6 border-b border-divider">
        <span className="font-bold text-lg text-primary">{t('common.appName')}</span>
        <Button isIconOnly size="sm" variant="light" className="md:hidden" onPress={onClose}>
          <X size={16} />
        </Button>
      </div>
      <ul className="flex-1 overflow-y-auto py-4 space-y-2 px-3">
        {NAV_ITEMS.map(({ path, labelKey, icon: Icon }) => {
          const active = pathname === path;
          return (
            <li key={path}>
              <Link
                to={path}
                onClick={onClose}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm transition-colors
                  ${active
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'text-default-600 hover:bg-default-100 hover:text-default-900'}`}
              >
                <Icon size={16} />
                {t(labelKey)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-64 h-screen bg-background border-r border-divider sticky top-0 shrink-0">
        {inner}
      </aside>

      {/* Mobile overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={onClose} />
          <aside className="relative z-10 w-64 h-full bg-background shadow-xl">
            {inner}
          </aside>
        </div>
      )}
    </>
  );
}

export function useSidebar() {
  const [open, setOpen] = useState(false);
  return { open, toggle: () => setOpen(p => !p), close: () => setOpen(false) };
}

export { Menu };
