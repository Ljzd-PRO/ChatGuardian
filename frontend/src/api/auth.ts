import { apiFetch, getSavedUsername, setSavedUsername } from './client';

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

export const changePassword = (oldPassword: string, newPassword: string, newUsername?: string) => {
  const username = getSavedUsername()?.trim();
  if (!username) {
    throw new Error('NO_SAVED_USERNAME');
  }

  const nextUsername = newUsername?.trim();

  return apiFetch<AuthStatusResponse>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      username,
      old_password: oldPassword,
      new_password: newPassword,
      new_username: nextUsername || undefined,
    }),
  }).then(result => {
    if (nextUsername) {
      setSavedUsername(nextUsername);
    }
    return result;
  });
};
