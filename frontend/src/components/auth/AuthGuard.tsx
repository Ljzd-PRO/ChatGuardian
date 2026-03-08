import { Navigate } from 'react-router-dom';
import { Spinner } from '@heroui/react';
import { useAuth } from '../../contexts/AuthContext';
import type { ReactNode } from 'react';

/**
 * Wraps protected routes. Redirects to /setup if setup is required,
 * to /login if not authenticated, otherwise renders children.
 */
export default function AuthGuard({ children }: { children: ReactNode }) {
  const { loading, setupRequired, authenticated } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-default-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (setupRequired) return <Navigate to="/setup" replace />;
  if (!authenticated) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
