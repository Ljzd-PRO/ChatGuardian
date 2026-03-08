import { createBrowserRouter, Navigate, useLocation } from 'react-router-dom';
import { Spinner } from '@heroui/react';
import type { ReactNode } from 'react';
import AppLayout from './components/layout/AppLayout';
import DashboardPage      from './pages/DashboardPage';
import RulesPage          from './pages/RulesPage';
import TriggerStatsPage   from './pages/TriggerStatsPage';
import UserProfilesPage   from './pages/UserProfilesPage';
import AdaptersPage       from './pages/AdaptersPage';
import LLMPage            from './pages/LLMPage';
import NotificationsPage  from './pages/NotificationsPage';
import QueuesPage         from './pages/QueuesPage';
import LogsPage           from './pages/LogsPage';
import SettingsPage       from './pages/SettingsPage';
import LoginPage          from './pages/LoginPage';
import SetupWizardPage    from './pages/SetupWizardPage';
import { useAuthStatus }  from './hooks/useAuth';

function FullPageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Spinner size="lg" />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { data, isLoading } = useAuthStatus();
  const location = useLocation();
  if (isLoading || !data) return <FullPageLoader />;
  if (data.setup_required) return <Navigate to="/setup" replace />;
  if (!data.authenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

function SetupOnly({ children }: { children: ReactNode }) {
  const { data, isLoading } = useAuthStatus();
  if (isLoading || !data) return <FullPageLoader />;
  if (!data.setup_required) return <Navigate to="/" replace />;
  return children;
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/setup', element: (
    <SetupOnly>
      <SetupWizardPage />
    </SetupOnly>
  ) },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true,              element: <DashboardPage /> },
      { path: 'rules',            element: <RulesPage /> },
      { path: 'stats',            element: <TriggerStatsPage /> },
      { path: 'users',            element: <UserProfilesPage /> },
      { path: 'adapters',         element: <AdaptersPage /> },
      { path: 'llm',              element: <LLMPage /> },
      { path: 'notifications',    element: <NotificationsPage /> },
      { path: 'queues',           element: <QueuesPage /> },
      { path: 'logs',             element: <LogsPage /> },
      { path: 'settings',         element: <SettingsPage /> },
    ],
  },
], { basename: '/app' });
