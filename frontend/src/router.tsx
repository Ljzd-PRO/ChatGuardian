import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import AuthGuard from './components/auth/AuthGuard';
import DashboardPage      from './pages/DashboardPage';
import RulesPage          from './pages/RulesPage';
import TriggerStatsPage   from './pages/TriggerStatsPage';
import RuleTriggerDetailPage from './pages/RuleTriggerDetailPage';
import UserProfilesPage   from './pages/UserProfilesPage';
import UserProfileDetailPage from './pages/UserProfileDetailPage';
import FrequentContactDetailPage from './pages/FrequentContactDetailPage';
import AdaptersPage       from './pages/AdaptersPage';
import LLMPage            from './pages/LLMPage';
import NotificationsPage  from './pages/NotificationsPage';
import QueuesPage         from './pages/QueuesPage';
import LogsPage           from './pages/LogsPage';
import LoginPage          from './pages/LoginPage';
import SetupWizardPage    from './pages/SetupWizardPage';
import ChangePasswordPage from './pages/ChangePasswordPage';
import AgentChatPage      from './pages/AgentChatPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/setup',
    element: <SetupWizardPage />,
  },
  {
    path: '/',
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),
    children: [
      { index: true,              element: <DashboardPage /> },
      { path: 'rules',            element: <RulesPage /> },
      { path: 'stats',            element: <TriggerStatsPage /> },
      { path: 'stats/:ruleId',    element: <RuleTriggerDetailPage /> },
      { path: 'users',            element: <UserProfilesPage /> },
      { path: 'users/:userId',    element: <UserProfileDetailPage /> },
      { path: 'users/:userId/contacts/:contactId', element: <FrequentContactDetailPage /> },
      { path: 'adapters',         element: <AdaptersPage /> },
      { path: 'llm',              element: <LLMPage /> },
      { path: 'notifications',    element: <NotificationsPage /> },
      { path: 'queues',           element: <QueuesPage /> },
      { path: 'logs',             element: <LogsPage /> },
      { path: 'change-password',  element: <ChangePasswordPage /> },
      { path: 'agent',            element: <AgentChatPage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
], { basename: '/app' });
