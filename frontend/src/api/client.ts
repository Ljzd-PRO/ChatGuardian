const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/';

const TOKEN_KEY = 'cg_auth_token';

/** Thrown by apiFetch when the server returns a non-2xx status. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const normalizedBase = API_BASE.endsWith('/') ? API_BASE.slice(0, -1) : API_BASE;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${normalizedBase}${normalizedPath}`;
  const headers = new Headers(init?.headers);
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    // Redirect to login if we get a 401 and we're not on an auth page
    const p = window.location.pathname;
    if (p !== '/app/login' && p !== '/app/setup' && !p.startsWith('/app/login/') && !p.startsWith('/app/setup/')) {
      window.location.href = '/app/login';
    }
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}
