import { Lead, LeadRating, LeadStatus } from "./types";

export const MOCK_LEADS: Lead[] = [
  {
    id: "1",
    name: "John Smith",
    email: "john@corp.com",
    rawMessage: "Hi,\n\nI'm interested in the retired person visa. My wife and I are considering moving to Cape Town later this year and would like to understand the financial requirements, expected timelines, and next steps.\n\nRegards,\nJohn",
    phone: "+27 82 123 4567",
    visaType: "Retired Person Visa",
    source: "RSA024",
    inboxBrand: "RISA",
    timestamp: new Date().toISOString(),
    status: LeadStatus.PENDING,
    rating: LeadRating.GD,
    confidence: "high",
    reasons: ["High income", "Clear move timeline", "UK nationality"],
    phoneScript: "Dear John, my name is [Name] from Retire In SA. We received your enquiry regarding Retired Person Visa...",
    emailDraft: "Subject: Your Retired Person Visa Enquiry\n\nDear John,\n\nThank you for your valued enquiry regarding moving to South Africa...",
    whatsappDraft: "RISA – GD – Consultation booked",
    researchBrief: {
      personalProfile: "Managing Director at Smith & Partners. High net worth.",
      employer: "Smith & Partners Ltd, UK financial consultancy.",
      immigrationAnalysis: "Meets all criteria for Retired Person Visa.",
      news: "Company recently announced international expansion.",
      consultantTips: "Open with: 'We noticed you reached out last year...'"
    },
    escalationFlag: false,
    assignedConsultant: "Melissa"
  },
  {
    id: "2",
    name: "Maria Rossi",
    email: "m@company.it",
    rawMessage: "Hello, I work remotely for an Italian company and want to spend an extended period in South Africa. Could you advise if the remote work visa is suitable and what documents are needed?",
    phone: "+39 345 678 9012",
    visaType: "Remote Work Visa",
    source: "RISA",
    inboxBrand: "RISA",
    timestamp: new Date().toISOString(),
    status: LeadStatus.REVIEWING,
    rating: LeadRating.GD,
    confidence: "high",
    reasons: ["Digital nomad trend", "High salary", "Italy based"],
    escalationFlag: false
  },
  {
    id: "3",
    name: "James Banda",
    email: "jb@yahoo.com",
    rawMessage: "Good day, I want to apply for a Critical Skills Work Visa but I do not currently have a formal job offer. Please tell me if I can still proceed.",
    phone: "+260 977 123456",
    visaType: "Critical Skills Work Visa",
    source: "XP",
    inboxBrand: "XP",
    timestamp: new Date().toISOString(),
    status: LeadStatus.PENDING,
    rating: LeadRating.BD,
    confidence: "high",
    reasons: ["No job offer", "DNQ-01 triggered"],
    dnqReason: "DNQ-01: Critical Skills Work Visa — No formal job offer found.",
    emailDraft: "Dear James, Thank you for your enquiry. In order to lodge a Critical Skills Work Visa, a formal offer of employment is required...",
    escalationFlag: false
  }
];
