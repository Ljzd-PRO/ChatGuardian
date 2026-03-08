import { apiFetch } from './client';

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  username: string;
  using_default_credentials: boolean;
}

export interface AuthStatus {
  authenticated: boolean;
  username: string;
  using_default_credentials: boolean;
  setup_required: boolean;
}

export interface SetupStatus {
  setup_required: boolean;
  using_default_credentials?: boolean;
}

export const login = (payload: LoginPayload) =>
  apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const fetchAuthStatus = () => apiFetch<AuthStatus>('/auth/status');

export const logout = () => apiFetch<{ status: string }>('/auth/logout', { method: 'POST' });

export const fetchSetupStatus = () => apiFetch<SetupStatus>('/auth/setup-status');

export const setupAccount = (payload: LoginPayload) =>
  apiFetch<LoginResponse & { setup_required: boolean }>('/auth/setup', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
