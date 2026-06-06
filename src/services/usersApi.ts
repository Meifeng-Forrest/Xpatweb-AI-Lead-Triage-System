import { authFetch, type AuthUser } from './authApi';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ManagedUser extends AuthUser {
  routing_categories: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreateInput {
  email: string;
  displayName: string;
  password: string;
  roles: string[];
  isActive: boolean;
}

export interface UserUpdateInput {
  displayName?: string;
  roles?: string[];
  isActive?: boolean;
}

async function readError(response: Response) {
  const message = await response.text();
  return message.slice(0, 260);
}

function summarizeEmail(email: string) {
  const domain = email.includes('@') ? email.split('@')[1] : 'invalid';
  return `***@${domain}`;
}

export async function listManagedUsers(): Promise<ManagedUser[]> {
  console.log('[client/users/list] enter', {});
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users`);
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/list] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not load users.');
  }
  const data: ManagedUser[] = await response.json();
  console.log('[client/users/list] success', { count: data.length, ms: Date.now() - startedAt });
  return data;
}

export async function listAvailableRoles(): Promise<string[]> {
  console.log('[client/users/roles] enter', {});
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users/roles`);
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/roles] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not load roles.');
  }
  const data: string[] = await response.json();
  console.log('[client/users/roles] success', { count: data.length, ms: Date.now() - startedAt });
  return data;
}

export async function createManagedUser(input: UserCreateInput): Promise<ManagedUser> {
  console.log('[client/users/create] enter', {
    email: summarizeEmail(input.email),
    roleCount: input.roles.length,
    isActive: input.isActive,
    passwordLength: input.password.length,
  });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: input.email,
      display_name: input.displayName,
      password: input.password,
      roles: input.roles,
      is_active: input.isActive,
    }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/create] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error(response.status === 409 ? 'A user with this email already exists.' : 'Could not create user.');
  }
  const data: ManagedUser = await response.json();
  console.log('[client/users/create] success', { userId: data.user_id, roleCount: data.roles.length, ms: Date.now() - startedAt });
  return data;
}

export async function updateManagedUser(userId: string, input: UserUpdateInput): Promise<ManagedUser> {
  console.log('[client/users/update] enter', {
    userId,
    displayNameChanged: input.displayName !== undefined,
    rolesChanged: input.roles !== undefined,
    isActive: input.isActive,
  });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users/${userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      display_name: input.displayName,
      roles: input.roles,
      is_active: input.isActive,
    }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/update] fail', { userId, status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error(response.status === 409 ? 'At least one active superadmin is required.' : 'Could not update user.');
  }
  const data: ManagedUser = await response.json();
  console.log('[client/users/update] success', { userId, roleCount: data.roles.length, isActive: data.is_active, ms: Date.now() - startedAt });
  return data;
}

export async function updateUserRoutingCategories(userId: string, categories: string[]): Promise<ManagedUser> {
  console.log('[client/users/routing-categories] enter', { userId, categoryCount: categories.length });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users/${userId}/routing-categories`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ categories }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/routing-categories] fail', { userId, status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error(response.status === 403 ? 'Routing configuration permission required.' : 'Could not update routing categories.');
  }
  const data: ManagedUser = await response.json();
  console.log('[client/users/routing-categories] success', {
    userId,
    categoryCount: data.routing_categories.length,
    ms: Date.now() - startedAt,
  });
  return data;
}

export async function resetManagedUserPassword(userId: string, password: string): Promise<ManagedUser> {
  console.log('[client/users/password] enter', { userId, passwordLength: password.length });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/users/${userId}/password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/users/password] fail', { userId, status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not reset password.');
  }
  const data: ManagedUser = await response.json();
  console.log('[client/users/password] success', { userId, ms: Date.now() - startedAt });
  return data;
}
