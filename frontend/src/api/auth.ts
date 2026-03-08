import { apiFetch } from './client';

export interface AuthStatus {
  setup_required: boolean;
  authenticated: boolean;
  username: string | null;
  using_default_credentials: boolean;
}

export interface AuthPayload {
  username: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  expires_at: string;
  username: string;
}

export const fetchAuthStatus = () => apiFetch<AuthStatus>('/api/auth/status');
export const login = (payload: AuthPayload) => apiFetch<AuthResponse>('/api/auth/login', {
  method: 'POST',
  body: JSON.stringify(payload),
});
export const logout = () => apiFetch<{ status: string }>('/api/auth/logout', { method: 'POST' });
