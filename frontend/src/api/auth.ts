import { apiFetch } from './client';

export interface AuthStatus {
  setup_complete: boolean;
}

export interface AuthResponse {
  status: string;
  token: string;
  username: string;
}

export const fetchAuthStatus = () => apiFetch<AuthStatus>('/api/auth/status');

export const setupAdmin = (username: string, password: string) =>
  apiFetch<AuthResponse>('/api/auth/setup', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const loginAdmin = (username: string, password: string) =>
  apiFetch<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const logoutAdmin = () =>
  apiFetch<{ status: string }>('/api/auth/logout', { method: 'POST' });

export const fetchAuthMe = () =>
  apiFetch<{ username: string }>('/api/auth/me');

export const changePassword = (newPassword: string) =>
  apiFetch<{ status: string; token: string }>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  });
