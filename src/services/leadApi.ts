import { Lead, LeadRating, LeadStatus } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ManualLeadInput {
  name: string;
  email: string;
  visaType: string;
  brand: string;
}

export interface ManualLeadResponse {
  lead_id: string;
  status: 'received' | LeadStatus;
  source_box: string;
  message: string;
  created_at: string;
  pipeline_task_id?: string | null;
}

export interface ExtractedLeadFields {
  sender_name: string;
  email_address: string | null;
  contact_number: string | null;
  email_domain: 'corporate' | 'gmail' | 'other_personal' | null;
  lead_type: 'Individual' | 'Corporate Individual' | 'Corporate' | null;
  visa_category: string | null;
  current_visa: string | null;
  pr_route: 'work_visa' | 'financially_independent' | 'relative' | 'other' | null;
  nationality: string | null;
  is_first_world: boolean | null;
  job_title: string | null;
  net_worth_indicator: string | null;
  has_job_offer: boolean | null;
  qualifying_work_visa_years: number | null;
  annual_salary_zar: number | null;
  pbs_total_score_below_100: boolean | null;
  relationship_duration: string | null;
  marriage_type: 'registered' | 'traditional' | 'unregistered' | 'common-law' | null;
  rejection_date: string | null;
  urgency_flag: boolean;
  multi_visa_flag: boolean;
  email_coherence: 'high' | 'medium' | 'low';
  additional_info: string | null;
}

export interface ManualExtractionResponse {
  provider: string;
  model: string;
  temperature: number;
  extracted: ExtractedLeadFields;
}

export interface ConfirmedManualLeadInput extends ManualExtractionResponse {
  rawMessage: string;
  brand: string;
}

export interface BackendLead {
  lead_id: string;
  sender_name: string;
  email_address: string;
  contact_number: string | null;
  email_domain: string;
  visa_category: string | null;
  source_box: string;
  lead_source: string | null;
  status: 'received' | 'contacted' | 'scored' | 'drafted' | 'in_review' | 'sent' | 'dnq' | 'archived';
  lead_score?: 'GD' | 'MF' | 'MD' | 'BD' | null;
  dnq_reason?: string | null;
  score_confidence?: 'high' | 'medium' | 'low' | null;
  score_rationale?: string | null;
  escalation_flag?: boolean | null;
  soft_dnq_warning?: string | null;
  email_draft?: string | null;
  whatsapp_draft?: string | null;
  phone_script?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineTaskStatus {
  task_id: string;
  status: string;
  result: Record<string, unknown> | null;
  error_type: string | null;
}

export interface BackendAuditEvent {
  event_id: number;
  lead_id: string;
  event_type: string;
  actor: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

function summarizeEmail(email: string) {
  const domain = email.includes('@') ? email.split('@')[1] : 'invalid';
  return `***@${domain}`;
}

export async function createManualLead(input: ManualLeadInput): Promise<ManualLeadResponse> {
  const rawMessage = `Manual lead entered from frontend. Name provided: ${Boolean(input.name)}. Visa category: ${input.visaType}.`;
  const summary = {
    sourceBox: input.brand,
    email: summarizeEmail(input.email),
    visaCategory: input.visaType,
    rawMessageLength: rawMessage.length,
  };
  console.log('[client/leads/manual] enter', summary);

  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sender_name: input.name,
      email_address: input.email,
      visa_category: input.visaType,
      source_box: input.brand,
      lead_source: 'Manual',
      raw_message: rawMessage,
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    console.error('[client/leads/manual] fail', {
      status: response.status,
      ms: Date.now() - startedAt,
      reason: message.slice(0, 200),
    });
    throw new Error('Failed to persist manual lead');
  }

  const data = await response.json();
  console.log('[client/leads/manual] success', {
    leadId: data.lead_id,
    status: data.status,
    ms: Date.now() - startedAt,
  });
  return data;
}

async function readError(response: Response) {
  const message = await response.text();
  return message.slice(0, 300);
}

export async function extractManualText(rawText: string): Promise<ManualExtractionResponse> {
  console.log('[client/extraction/manual] enter', { rawTextLength: rawText.length });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/extraction/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_text: rawText }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/extraction/manual] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not extract information from the pasted text.');
  }
  const data: ManualExtractionResponse = await response.json();
  console.log('[client/extraction/manual] success', {
    provider: data.provider,
    model: data.model,
    fieldCount: Object.keys(data.extracted).length,
    ms: Date.now() - startedAt,
  });
  return data;
}

export async function createConfirmedManualLead(input: ConfirmedManualLeadInput): Promise<ManualLeadResponse> {
  console.log('[client/leads/manual-confirmed] enter', {
    sourceBox: input.brand,
    rawMessageLength: input.rawMessage.length,
    provider: input.provider,
    model: input.model,
  });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/manual-confirmed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_message: input.rawMessage,
      source_box: input.brand,
      extracted: input.extracted,
      extraction_provider: input.provider,
      extraction_model: input.model,
      extraction_temperature: input.temperature,
    }),
  });
  if (!response.ok) {
    const reason = await readError(response);
    console.error('[client/leads/manual-confirmed] fail', { status: response.status, ms: Date.now() - startedAt, reason });
    throw new Error('Could not save the confirmed lead.');
  }
  const data: ManualLeadResponse = await response.json();
  console.log('[client/leads/manual-confirmed] success', {
    leadId: data.lead_id,
    taskId: data.pipeline_task_id,
    ms: Date.now() - startedAt,
  });
  return data;
}

function mapBackendStatus(status: BackendLead['status']): LeadStatus {
  if (status === 'contacted') return LeadStatus.CONTACTED;
  if (status === 'in_review') return LeadStatus.REVIEWING;
  if (status === 'sent') return LeadStatus.APPROVED;
  if (status === 'dnq') return LeadStatus.REJECTED;
  if (status === 'archived') return LeadStatus.ARCHIVED;
  return LeadStatus.PENDING;
}

function mapFrontendStatus(status: LeadStatus): BackendLead['status'] {
  if (status === LeadStatus.CONTACTED) return 'contacted';
  if (status === LeadStatus.REVIEWING) return 'in_review';
  if (status === LeadStatus.APPROVED) return 'sent';
  if (status === LeadStatus.REJECTED) return 'dnq';
  if (status === LeadStatus.ARCHIVED) return 'archived';
  return 'received';
}

function mapBackendRating(score: BackendLead['lead_score']): LeadRating | undefined {
  if (score === 'GD') return LeadRating.GD;
  if (score === 'MF') return LeadRating.MF;
  if (score === 'MD') return LeadRating.MD;
  if (score === 'BD') return LeadRating.BD;
  return undefined;
}

export function mapBackendLeadToLead(lead: BackendLead): Lead {
  return {
    id: lead.lead_id,
    name: lead.sender_name,
    email: lead.email_address,
    phone: lead.contact_number || '',
    visaType: lead.visa_category || 'Not Provided',
    source: lead.lead_source || 'Backend',
    inboxBrand: lead.source_box,
    timestamp: lead.created_at,
    status: mapBackendStatus(lead.status),
    rating: mapBackendRating(lead.lead_score),
    confidence: lead.score_confidence || undefined,
    reasons: lead.score_rationale ? [lead.score_rationale] : [],
    emailDraft: lead.email_draft || undefined,
    whatsappDraft: lead.whatsapp_draft || undefined,
    phoneScript: lead.phone_script || undefined,
    escalationFlag: Boolean(lead.escalation_flag),
    dnqReason: lead.dnq_reason || lead.soft_dnq_warning || undefined,
  };
}

export async function listLeads(limit = 100): Promise<Lead[]> {
  console.log('[client/leads/list] enter', { limit });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/leads?limit=${limit}`);

  if (!response.ok) {
    const message = await response.text();
    console.error('[client/leads/list] fail', {
      status: response.status,
      ms: Date.now() - startedAt,
      reason: message.slice(0, 200),
    });
    throw new Error('Failed to load leads');
  }

  const data: BackendLead[] = await response.json();
  console.log('[client/leads/list] success', {
    count: data.length,
    ms: Date.now() - startedAt,
  });
  return data.map(mapBackendLeadToLead);
}

export async function getLead(leadId: string): Promise<Lead> {
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/${leadId}`);
  if (!response.ok) {
    console.error('[client/leads/get] fail', { leadId, status: response.status });
    throw new Error('Failed to load lead');
  }
  const data: BackendLead = await response.json();
  return mapBackendLeadToLead(data);
}

export async function getPipelineTaskStatus(taskId: string): Promise<PipelineTaskStatus> {
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/pipeline-tasks/${taskId}`);
  if (!response.ok) {
    console.error('[client/leads/pipeline-task] fail', { taskId, status: response.status });
    throw new Error('Failed to load pipeline task');
  }
  return response.json();
}

export async function updateLeadStatus(leadId: string, status: LeadStatus): Promise<Lead> {
  const backendStatus = mapFrontendStatus(status);
  console.log('[client/leads/status] enter', { leadId, status: backendStatus });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/${leadId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      status: backendStatus,
      actor: 'frontend',
    }),
  });

  if (!response.ok) {
    const message = await response.text();
    console.error('[client/leads/status] fail', {
      leadId,
      status: backendStatus,
      httpStatus: response.status,
      ms: Date.now() - startedAt,
      reason: message.slice(0, 200),
    });
    throw new Error('Failed to update lead status');
  }

  const data: BackendLead = await response.json();
  console.log('[client/leads/status] success', {
    leadId,
    status: data.status,
    ms: Date.now() - startedAt,
  });
  return mapBackendLeadToLead(data);
}

export async function listAuditEvents(leadId: string): Promise<BackendAuditEvent[]> {
  console.log('[client/leads/audit] enter', { leadId });
  const startedAt = Date.now();
  const response = await fetch(`${API_BASE_URL}/api/v1/leads/${leadId}/audit-events`);

  if (!response.ok) {
    const message = await response.text();
    console.error('[client/leads/audit] fail', {
      leadId,
      status: response.status,
      ms: Date.now() - startedAt,
      reason: message.slice(0, 200),
    });
    throw new Error('Failed to load audit events');
  }

  const data: BackendAuditEvent[] = await response.json();
  console.log('[client/leads/audit] success', {
    leadId,
    count: data.length,
    ms: Date.now() - startedAt,
  });
  return data;
}
