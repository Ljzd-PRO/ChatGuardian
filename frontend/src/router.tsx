import { createBrowserRouter } from 'react-router-dom';
import ProtectedApp from './components/layout/ProtectedApp';
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
import SetupPage          from './pages/SetupPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/setup', element: <SetupPage /> },
  {
    path: '/',
    element: <ProtectedApp />,
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
