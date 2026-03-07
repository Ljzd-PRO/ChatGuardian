import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { fetchAuthMe, fetchAuthStatus, loginAdmin, logoutAdmin } from '../api/auth';
import { clearStoredToken, getStoredToken, storeToken } from '../api/client';

interface AuthContextValue {
  /** Whether the app has been set up (admin credentials created). */
  setupComplete: boolean;
  /** Whether we are currently validating the stored token. */
  isLoading: boolean;
  /** Currently authenticated username, or null when logged out. */
  username: string | null;
  /** Attempt to log in; throws on failure. */
  login: (username: string, password: string) => Promise<void>;
  /** Log out and clear the stored token. */
  logout: () => Promise<void>;
  /** Update setupComplete state after wizard completes. */
  markSetupComplete: (token: string, username: string) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [setupComplete, setSetupComplete] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [username, setUsername] = useState<string | null>(null);

  // On mount: check setup status and validate stored token
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchAuthStatus();
        if (cancelled) return;
        setSetupComplete(status.setup_complete);

        if (status.setup_complete && getStoredToken()) {
          try {
            const me = await fetchAuthMe();
            if (!cancelled) setUsername(me.username);
          } catch {
            // Token invalid/expired – clear it
            clearStoredToken();
          }
        }
      } catch {
        // API unreachable – fail silently; pages will handle errors themselves
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (user: string, password: string) => {
    const res = await loginAdmin(user, password);
    storeToken(res.token);
    setUsername(res.username);
  }, []);

  const logout = useCallback(async () => {
    try { await logoutAdmin(); } catch { /* best-effort */ }
    clearStoredToken();
    setUsername(null);
  }, []);

  const markSetupComplete = useCallback((token: string, user: string) => {
    storeToken(token);
    setSetupComplete(true);
    setUsername(user);
  }, []);

  return (
    <AuthContext.Provider value={{ setupComplete, isLoading, username, login, logout, markSetupComplete }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
