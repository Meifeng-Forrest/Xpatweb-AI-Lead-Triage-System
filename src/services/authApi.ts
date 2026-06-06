const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_STORAGE_KEY = 'xpatweb.auth.token';

export interface AuthUser {
  user_id: string;
  email: string;
  display_name: string;
  roles: string[];
  permissions: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in_seconds: number;
  user: AuthUser;
}

function summarizeEmail(email: string) {
  const domain = email.includes('@') ? email.split('@')[1] : 'invalid';
  return `***@${domain}`;
}

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAuthToken();
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const response = await fetch(input, {
    ...init,
    headers: authHeaders(init.headers),
  });
  if (response.status === 401) {
    clearAuthToken();
    window.dispatchEvent(new CustomEvent('auth:required'));
  }
  return response;
}

async function readError(response: Response) {
  const message = await response.text();
  return message.slice(0, 240);
}

export async function login(email: string, password: string): Promise<AuthUser> {
  console.log('[client/auth/login] enter', { email: summarizeEmail(email) });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/auth/login] fail', {
      email: summarizeEmail(email),
      status: response.status,
      ms: Date.now() - startedAt,
      reason,
    });
    throw new Error('Invalid email or password.');
  }

  const data: LoginResponse = await response.json();
  setAuthToken(data.access_token);
  console.log('[client/auth/login] success', {
    userId: data.user.user_id,
    roleCount: data.user.roles.length,
    ms: Date.now() - startedAt,
  });
  return data.user;
}

export async function fetchMe(): Promise<AuthUser> {
  console.log('[client/auth/me] enter', { tokenPresent: Boolean(getAuthToken()) });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/auth/me`);
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/auth/me] fail', {
      status: response.status,
      ms: Date.now() - startedAt,
      reason,
    });
    throw new Error('Authentication required.');
  }
  const data: AuthUser = await response.json();
  console.log('[client/auth/me] success', {
    userId: data.user_id,
    roleCount: data.roles.length,
    ms: Date.now() - startedAt,
  });
  return data;
}
