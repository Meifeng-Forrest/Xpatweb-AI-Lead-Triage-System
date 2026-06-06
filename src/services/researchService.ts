import { ResearchBrief } from '../types';
import { authFetch } from './authApi';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface BackendResearchBrief {
  lead_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  task_id: string | null;
  brief: ResearchBrief | null;
  source_refs: Array<Record<string, unknown>>;
  error_type: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export async function startLeadResearch(leadId: string): Promise<{ lead_id: string; task_id: string; status: string }> {
  console.log('[client/research/start] enter', { leadId });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/leads/${leadId}/research`, {
    method: 'POST',
  });
  if (!response.ok) {
    const reason = (await response.text()).slice(0, 240);
    console.error('[client/research/start] fail', { leadId, status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not queue research.');
  }
  const data = await response.json();
  console.log('[client/research/start] success', { leadId, taskId: data.task_id, ms: Date.now() - startedAt });
  return data;
}

export async function getLeadResearch(leadId: string): Promise<BackendResearchBrief | null> {
  console.log('[client/research/get] enter', { leadId });
  const startedAt = Date.now();
  const response = await authFetch(`${API_BASE_URL}/api/v1/leads/${leadId}/research`);
  if (response.status === 404) {
    console.log('[client/research/get] empty', { leadId, ms: Date.now() - startedAt });
    return null;
  }
  if (!response.ok) {
    const reason = (await response.text()).slice(0, 240);
    console.error('[client/research/get] fail', { leadId, status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not load research.');
  }
  const data: BackendResearchBrief = await response.json();
  console.log('[client/research/get] success', { leadId, status: data.status, sourceCount: data.source_refs.length, ms: Date.now() - startedAt });
  return data;
}
