import { Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect } from 'react';
import Sidebar, { useSidebar } from './Sidebar';
import TopNavbar from './Navbar';

const TITLE_KEYS: Record<string, string> = {
  '/':              'layout.titles.dashboard',
  '/rules':         'layout.titles.rules',
  '/stats':         'layout.titles.stats',
  '/users':         'layout.titles.users',
  '/adapters':      'layout.titles.adapters',
  '/llm':           'layout.titles.llm',
  '/agent':         'layout.titles.agent',
  '/notifications': 'layout.titles.notifications',
  '/queues':        'layout.titles.queues',
  '/logs':          'layout.titles.logs',
  '/change-password': 'auth.changePw.title',
};

export default function AppLayout() {
  const { open, toggle, close } = useSidebar();
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const titleKey = TITLE_KEYS[pathname] ?? 'common.appName';
  const title = t(titleKey);

  // Dynamic document title
  useEffect(() => {
    const appName = t('common.appName');
    document.title = title === appName ? appName : `${title} - ${appName}`;
  }, [title, t]);

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-default-50">
      <Sidebar open={open} onClose={close} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopNavbar onMenuClick={toggle} title={title} />
        <main className="flex-1 min-h-0 p-4 md:p-6 flex flex-col overflow-hidden">
          <div className="md:hidden mb-4 flex-shrink-0">
            <h1 className="text-2xl font-bold text-default-900">{title}</h1>
          </div>
          <div className="flex-1 min-h-0 overflow-auto px-1 py-1">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
