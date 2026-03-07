import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Spinner } from '@heroui/react';
import { useAuth } from '../../contexts/AuthContext';

/**
 * AuthGuard wraps protected routes.
 * - If setup is not done → redirect to /setup
 * - If not authenticated → redirect to /login
 * - While loading → show spinner
 */
export default function AuthGuard() {
  const { setupComplete, isLoading, username } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!setupComplete) {
    return <Navigate to="/setup" replace state={{ from: location }} />;
  }

  if (!username) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
