import { apiFetch } from './client';

export interface SetupRequiredResponse {
  setup_required: boolean;
}

export interface LoginResponse {
  token: string;
}

export interface AuthStatusResponse {
  status: string;
}

export const checkSetupRequired = () =>
  apiFetch<SetupRequiredResponse>('/api/auth/setup-required');

export const register = (username: string, password: string) =>
  apiFetch<AuthStatusResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const login = (username: string, password: string) =>
  apiFetch<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

export const changePassword = (username: string, oldPassword: string, newPassword: string) =>
  apiFetch<AuthStatusResponse>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ username, old_password: oldPassword, new_password: newPassword }),
  });
