import { Card, CardBody, Spinner } from '@heroui/react';
import { useQuery } from '@tanstack/react-query';
import { createContext, useContext, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchAuthStatus, logout as apiLogout } from '../../api/auth';
import type { AuthStatus } from '../../api/auth';
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

  const statusQuery = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    enabled: !!token,
    retry: 1,
  });

  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true, state: { from: location.pathname } });
    }
  }, [location.pathname, navigate, token]);

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
