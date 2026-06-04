import { GoogleGenAI, Type } from "@google/genai";
import { Lead, LeadRating } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });
const TRIAGE_MODEL = process.env.GEMINI_MODEL_TRIAGE || "gemini-3-flash-preview";
const RESEARCH_MODEL = process.env.GEMINI_MODEL_RESEARCH || "gemini-3.1-pro-preview";

const TRIAGE_SYSTEM_PROMPT = `
You are an expert Lead Triage AI for Xpatweb, a visa consultancy.
Your task is to analyze an inbound lead and:
1. Parse fields (name, email, phone, visaType, etc.)
2. Score the lead (GD, MF, MD, BD) based on value and feasibility.
3. Draft a response email, WhatsApp message, and phone script.

Rating Criteria:
- GD (Gold): High value, clear intent, qualifies for major visa. (e.g. Retired Person with high income, CEO move). Action: 60s Call.
- MF (Medium Follow Up): Interested but needs more info or slight gaps. Action: 60s Call.
- MD (Medium): Standard enquiry, follows standard pricing. Action: Quote email.
- BD (Bad): Low value, disqualified (DNQ), or junk. Action: Rejection or low-priority email.

Routing Rules:
- If visaType involves "Verification", assign to "Willem Pretorius".
- If user seems angry, urgent, or high-risk, set escalationFlag: true (assigned to Jerry).
- Default assignedConsultant is "Melissa".

DNQ Rules:
- Critical Skills without job offer -> BD.
- PBS Salary too low -> BD.
- No work invitation for critical skills -> DNQ-01.

Output MUST be JSON.
`;

export async function triageLead(leadInput: string): Promise<Partial<Lead>> {
  const response = await ai.models.generateContent({
    model: TRIAGE_MODEL,
    contents: leadInput,
    config: {
      systemInstruction: TRIAGE_SYSTEM_PROMPT,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          name: { type: Type.STRING },
          email: { type: Type.STRING },
          phone: { type: Type.STRING },
          visaType: { type: Type.STRING },
          rating: { type: Type.STRING, enum: Object.values(LeadRating) },
          confidence: { type: Type.STRING, enum: ["low", "medium", "high"] },
          reasons: { type: Type.ARRAY, items: { type: Type.STRING } },
          emailDraft: { type: Type.STRING },
          whatsappDraft: { type: Type.STRING },
          phoneScript: { type: Type.STRING },
          escalationFlag: { type: Type.BOOLEAN },
          dnqReason: { type: Type.STRING },
        },
        required: ["name", "email", "rating", "confidence", "reasons"],
      },
    },
  });

  try {
    return JSON.parse(response.text);
  } catch (e) {
    console.error("Failed to parse Gemini response", e);
    throw new Error("Lead triage failed");
  }
}

export async function generateResearchBrief(lead: Lead): Promise<Lead["researchBrief"]> {
  const prompt = `Research brief for: ${lead.name}, ${lead.visaType}, from ${lead.email}.
  Include:
  - Personal Profile: Background, seniority.
  - Employer: Company info, scale.
  - Immigration Analysis: Path feasibility, risk markers.
  - News: Recent notable news about them or company.
  - Consultant Tips: Opening line, time zone, payment capacity.
  `;

  const response = await ai.models.generateContent({
    model: RESEARCH_MODEL,
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          personalProfile: { type: Type.STRING },
          employer: { type: Type.STRING },
          immigrationAnalysis: { type: Type.STRING },
          news: { type: Type.STRING },
          consultantTips: { type: Type.STRING },
        },
        required: ["personalProfile", "employer", "immigrationAnalysis", "news", "consultantTips"],
      },
    },
  });

  try {
    return JSON.parse(response.text);
  } catch (e) {
    console.error("Failed to parse Research Brief", e);
    return {
      personalProfile: "Error generating profile",
      employer: "Error generating employer info",
      immigrationAnalysis: "Error generating analysis",
      news: "Error generating news",
      consultantTips: "Error generating tips",
    };
  }
}
