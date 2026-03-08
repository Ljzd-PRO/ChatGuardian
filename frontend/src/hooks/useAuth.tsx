import {
  createContext, useCallback, useContext, useMemo, useState, type ReactNode,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchAuthStatus, login as loginApi, register as registerApi, logout as logoutApi, type AuthPayload,
} from '../api/auth';
import { getStoredToken, setStoredToken } from '../api/client';

type AuthContextValue = {
  token: string | null;
  setToken: (token: string | null) => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getStoredToken());

  const setToken = useCallback((next: string | null) => {
    setStoredToken(next);
    setTokenState(next);
  }, []);

  const value = useMemo(() => ({ token, setToken }), [token, setToken]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}

export function useAuthStatus() {
  const { token } = useAuthContext();
  return useQuery({
    queryKey: ['auth_status', token],
    queryFn: () => fetchAuthStatus(),
    staleTime: 5_000,
  });
}

export function useAuthActions() {
  const { setToken } = useAuthContext();
  const qc = useQueryClient();

  const login = useMutation({
    mutationFn: async (payload: AuthPayload) => {
      const res = await loginApi(payload);
      setToken(res.token);
      qc.invalidateQueries({ queryKey: ['auth_status'] });
      return res;
    },
  });

  const register = useMutation({
    mutationFn: async (payload: AuthPayload) => {
      const res = await registerApi(payload);
      setToken(res.token);
      qc.invalidateQueries({ queryKey: ['auth_status'] });
      return res;
    },
  });

  const logout = useMutation({
    mutationFn: async () => {
      try {
        await logoutApi();
      } finally {
        setToken(null);
        qc.invalidateQueries({ queryKey: ['auth_status'] });
      }
    },
  });

  return { login, register, logout };
}
