import { Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Sidebar, { useSidebar } from './Sidebar';
import TopNavbar from './Navbar';

const TITLE_KEYS: Record<string, string> = {
  '/':              'layout.titles.dashboard',
  '/rules':         'layout.titles.rules',
  '/stats':         'layout.titles.stats',
  '/users':         'layout.titles.users',
  '/adapters':      'layout.titles.adapters',
  '/llm':           'layout.titles.llm',
  '/notifications': 'layout.titles.notifications',
  '/queues':        'layout.titles.queues',
  '/logs':          'layout.titles.logs',
  '/settings':      'layout.titles.settings',
  '/change-password': 'auth.changePw.title',
};

export default function AppLayout() {
  const { open, toggle, close } = useSidebar();
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const titleKey = TITLE_KEYS[pathname] ?? 'common.appName';
  const title = t(titleKey);

  return (
    <div className="flex min-h-screen bg-default-50">
      <Sidebar open={open} onClose={close} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopNavbar onMenuClick={toggle} title={title} />
        <main className="flex-1 p-4 md:p-6 overflow-auto">
          <div className="md:hidden mb-4">
            <h1 className="text-2xl font-bold text-default-900">{title}</h1>
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
