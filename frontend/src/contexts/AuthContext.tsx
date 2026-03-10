import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { checkSetupRequired, login as apiLogin, register as apiRegister } from '../api/auth';
import { getToken, setToken, clearToken } from '../api/client';

interface AuthState {
  /** Whether we're still loading the initial auth state */
  loading: boolean;
  /** Whether admin credentials have been configured */
  setupRequired: boolean;
  /** Whether the user is currently authenticated */
  authenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Refresh the setup-required state from the server */
  refreshSetupState: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    loading: true,
    setupRequired: false,
    authenticated: false,
  });

  const refreshSetupState = useCallback(async () => {
    try {
      const { setup_required } = await checkSetupRequired();
      setState(prev => ({
        ...prev,
        setupRequired: setup_required,
        loading: false,
        authenticated: !setup_required && !!getToken(),
      }));
    } catch {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    refreshSetupState();
  }, [refreshSetupState]);

  const login = useCallback(async (username: string, password: string) => {
    const { token } = await apiLogin(username, password);
    setToken(token);
    setState(prev => ({ ...prev, authenticated: true }));
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    await apiRegister(username, password);
    setState(prev => ({ ...prev, setupRequired: false }));
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState(prev => ({ ...prev, authenticated: false }));
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshSetupState }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
