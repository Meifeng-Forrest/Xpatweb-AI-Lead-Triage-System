import { authFetch } from './authApi';
import type { ManagedUser } from './usersApi';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface RoutingRule {
  category: string;
  recipients: ManagedUser[];
  fallback_to_superadmin: boolean;
}

async function readError(response: Response) {
  const message = await response.text();
  return message.slice(0, 260);
}

export async function listRoutingRules(): Promise<RoutingRule[]> {
  console.log('[client/routing/rules/list] enter', {});
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/routing/rules`);
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/routing/rules/list] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not load routing rules.');
  }
  const data: RoutingRule[] = await response.json();
  console.log('[client/routing/rules/list] success', { categoryCount: data.length, ms: Date.now() - startedAt });
  return data;
}
