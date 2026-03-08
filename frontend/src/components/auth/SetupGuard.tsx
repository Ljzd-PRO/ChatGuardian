import { Navigate } from 'react-router-dom';
import { Spinner } from '@heroui/react';
import { useAuth } from '../../contexts/AuthContext';
import type { ReactNode } from 'react';

/**
 * Wraps the setup wizard route. Only renders children when setup is required.
 * Redirects to /login otherwise.
 */
export default function SetupGuard({ children }: { children: ReactNode }) {
  const { loading, setupRequired } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-default-50">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!setupRequired) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
