export enum LeadRating {
  GD = "GD",
  MF = "MF",
  MD = "MD",
  BD = "BD",
}

export enum LeadStatus {
  PENDING = "pending",
  CONTACTED = "contacted",
  REVIEWING = "reviewing",
  APPROVED = "approved",
  REJECTED = "rejected",
  ARCHIVED = "archived",
}

export interface ResearchBrief {
  personalProfile: string;
  employer: string;
  immigrationAnalysis: string;
  news: string;
  consultantTips: string;
}

export interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  visaType: string;
  source: string;
  inboxBrand: string;
  timestamp: string;
  status: LeadStatus;
  rating?: LeadRating;
  confidence?: "low" | "medium" | "high";
  reasons: string[];
  emailDraft?: string;
  whatsappDraft?: string;
  phoneScript?: string;
  researchBrief?: ResearchBrief;
  escalationFlag: boolean;
  dnqReason?: string;
  assignedConsultant?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: "leads_team" | "melissa" | "marisa" | "jerry" | "willem";
}
