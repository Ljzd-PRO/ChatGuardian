import { Outlet, useLocation } from 'react-router-dom';
import Sidebar, { useSidebar } from './Sidebar';
import TopNavbar from './Navbar';

const PAGE_TITLES: Record<string, string> = {
  '/':              'Dashboard',
  '/rules':         'Detection Rules',
  '/stats':         'Trigger Statistics',
  '/users':         'User Profiles',
  '/adapters':      'Adapters',
  '/llm':           'LLM Configuration',
  '/notifications': 'Notifications',
  '/queues':        'Message Queues',
  '/logs':          'System Logs',
  '/settings':      'Settings',
};

export default function AppLayout() {
  const { open, toggle, close } = useSidebar();
  const { pathname } = useLocation();
  const title = PAGE_TITLES[pathname] ?? 'ChatGuardian';

  return (
    <div className="flex min-h-screen bg-default-50">
      <Sidebar open={open} onClose={close} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopNavbar onMenuClick={toggle} title={title} />
        <main className="flex-1 p-4 md:p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
