const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/';
export const AUTH_TOKEN_KEY = 'cg_auth_token';

export const getAuthToken = () =>
  (typeof localStorage === 'undefined' ? null : localStorage.getItem(AUTH_TOKEN_KEY));

export const setAuthToken = (token: string) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  }
};

export const clearAuthToken = () => {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
};

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${normalizedBase}${normalizedPath}`;
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...init?.headers,
  };

  const res = await fetch(url, {
    ...init,
    headers,
  });

  if (res.status === 401) {
    clearAuthToken();
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}
