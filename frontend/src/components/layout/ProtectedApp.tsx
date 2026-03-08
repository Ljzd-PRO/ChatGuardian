import { Card, CardBody, Spinner } from '@heroui/react';
import { useQuery } from '@tanstack/react-query';
import { createContext, useContext, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchAuthStatus, fetchSetupStatus, logout as apiLogout } from '../../api/auth';
import type { AuthStatus, SetupStatus } from '../../api/auth';
import { clearAuthToken, getAuthToken } from '../../api/client';
import AppLayout from './AppLayout';

type AuthContextValue = {
  status: AuthStatus;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthContext provider');
  }
  return ctx;
};

export default function ProtectedApp() {
  const token = getAuthToken();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();

  const setupQuery = useQuery<SetupStatus>({
    queryKey: ['setup-status'],
    queryFn: fetchSetupStatus,
    refetchInterval: query => (query.state.data?.setup_required ? 5_000 : false),
  });

  const statusQuery = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    enabled: !!token && setupQuery.data?.setup_required === false,
    retry: 1,
  });

  useEffect(() => {
    if (setupQuery.data?.setup_required && location.pathname !== '/setup') {
      navigate('/setup', { replace: true });
      return;
    }
    if (!token && setupQuery.data?.setup_required === false) {
      navigate('/login', { replace: true, state: { from: location.pathname } });
    }
  }, [location.pathname, navigate, setupQuery.data?.setup_required, token]);

  useEffect(() => {
    if (statusQuery.data && !statusQuery.data.authenticated) {
      clearAuthToken();
      navigate('/login', { replace: true, state: { from: location.pathname } });
    }
  }, [location.pathname, navigate, statusQuery.data]);

  useEffect(() => {
    if (statusQuery.isError) {
      clearAuthToken();
      navigate('/login', { replace: true, state: { from: location.pathname } });
    }
  }, [location.pathname, navigate, statusQuery.isError]);

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // ignore errors to ensure client logout succeeds
    } finally {
      clearAuthToken();
      navigate('/login', { replace: true });
    }
  };

  if (setupQuery.isError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-default-50 px-4">
        <Card shadow="sm" className="max-w-md w-full">
          <CardBody className="flex items-center justify-center">
            <span className="text-default-700">
              Failed to load application state. Please try again.
            </span>
          </CardBody>
        </Card>
      </div>
    );
  }

  if (setupQuery.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-default-50 px-4">
        <Card shadow="sm" className="max-w-md w-full">
          <CardBody className="flex items-center justify-center gap-3">
            <Spinner label={t('common.loading')} />
          </CardBody>
        </Card>
      </div>
    );
  }

  if (setupQuery.data?.setup_required) {
    return null;
  }

  if (!token || statusQuery.isFetching || !statusQuery.data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-default-50 px-4">
        <Card shadow="sm" className="max-w-md w-full">
          <CardBody className="flex items-center justify-center gap-3">
            <Spinner label={t('common.loading')} />
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ status: statusQuery.data, logout: handleLogout }}>
      <AppLayout />
    </AuthContext.Provider>
  );
}
