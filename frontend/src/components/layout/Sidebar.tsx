import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, ShieldCheck, BarChart2, Users,
  Plug, Brain, Bell, ListOrdered, ScrollText, Settings, X, Menu,
} from 'lucide-react';
import { Button } from '@heroui/react';

const NAV_ITEMS = [
  { path: '/',             label: 'Dashboard',      icon: LayoutDashboard },
  { path: '/rules',        label: 'Rules',          icon: ShieldCheck },
  { path: '/stats',        label: 'Trigger Stats',  icon: BarChart2 },
  { path: '/users',        label: 'User Profiles',  icon: Users },
  { path: '/adapters',     label: 'Adapters',       icon: Plug },
  { path: '/llm',          label: 'LLM',            icon: Brain },
  { path: '/notifications',label: 'Notifications',  icon: Bell },
  { path: '/queues',       label: 'Queues',         icon: ListOrdered },
  { path: '/logs',         label: 'Logs',           icon: ScrollText },
  { path: '/settings',     label: 'Settings',       icon: Settings },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { pathname } = useLocation();

  const inner = (
    <nav className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-5 border-b border-divider">
        <span className="font-bold text-lg text-primary">ChatGuardian</span>
        <Button isIconOnly size="sm" variant="light" className="md:hidden" onPress={onClose}>
          <X size={16} />
        </Button>
      </div>
      <ul className="flex-1 overflow-y-auto py-3 space-y-1 px-2">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const active = pathname === path;
          return (
            <li key={path}>
              <Link
                to={path}
                onClick={onClose}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                  ${active
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'text-default-600 hover:bg-default-100 hover:text-default-900'}`}
              >
                <Icon size={16} />
                {label}
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
      <aside className="hidden md:flex flex-col w-56 h-screen bg-background border-r border-divider sticky top-0 shrink-0">
        {inner}
      </aside>

      {/* Mobile overlay */}
      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/40" onClick={onClose} />
          <aside className="relative z-10 w-56 h-full bg-background shadow-xl">
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
