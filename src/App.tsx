import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  BarChart3, 
  CheckCircle2, 
  Clock, 
  FileEdit, 
  Inbox, 
  LayoutDashboard, 
  MessageSquare, 
  Phone, 
  Plus, 
  Search, 
  ShieldAlert, 
  User,
  Check,
  Send,
  X,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Loader2,
  LogOut,
  KeyRound,
  UserPlus,
  Users,
  Archive,
} from 'lucide-react';
import { Lead, LeadRating, LeadStatus } from './types';
import { MOCK_LEADS } from './mockData';
import { cn, formatDate } from './lib/utils';
import { RATING_LABELS, INBOX_BRANDS, VISA_TYPES } from './constants';
import ReactMarkdown from 'react-markdown';
import { getLeadResearch, startLeadResearch } from './services/researchService';
import { useAuth } from './contexts/AuthContext';
import { LoginView } from './components/LoginView';
import {
  approveLead as persistApproveLead,
  confirmLeadRejection as persistConfirmLeadRejection,
  createConfirmedManualLead,
  editLeadFields as persistEditLeadFields,
  editLeadDraft as persistEditLeadDraft,
  extractManualText,
  getLead,
  getPipelineTaskStatus,
  listAuditEvents,
  listLeads,
  rejectLead as persistRejectLead,
  updateLeadStatus as persistLeadStatus,
  type BackendAuditEvent,
  type ExtractedLeadFields,
  type LeadFieldEditInput,
  type ManualExtractionResponse,
} from './services/leadApi';
import {
  createManagedUser,
  listAvailableRoles,
  listManagedUsers,
  resetManagedUserPassword,
  updateUserRoutingCategories,
  updateManagedUser,
  type ManagedUser,
  type UserUpdateInput,
} from './services/usersApi';

// --- Components ---

const RatingBadge = ({ rating, confidence }: { rating?: LeadRating, confidence?: string }) => {
  if (!rating) {
    return (
      <div className="inline-flex flex-col gap-1 px-2 py-1 rounded border bg-slate-100 text-slate-500 border-slate-200">
        <span className="text-xs font-bold uppercase">Not Scored</span>
      </div>
    );
  }

  const styles = {
    [LeadRating.GD]: "bg-yellow-500/10 text-yellow-600 border-yellow-200",
    [LeadRating.MF]: "bg-blue-500/10 text-blue-600 border-blue-200",
    [LeadRating.MD]: "bg-green-500/10 text-green-600 border-green-200",
    [LeadRating.BD]: "bg-red-500/10 text-red-600 border-red-200",
  };

  return (
    <div className={cn("inline-flex flex-col items-start px-2 py-1 rounded border text-xs font-bold uppercase tracking-wider", styles[rating])}>
      <span>{rating} — {RATING_LABELS[rating]}</span>
      {confidence && <span className="text-[10px] opacity-70 italic font-normal">Confidence: {confidence}</span>}
    </div>
  );
};

const StatusBadge = ({ status }: { status: LeadStatus }) => {
  const styles = {
    [LeadStatus.PENDING]: "bg-orange-100 text-orange-700",
    [LeadStatus.CONTACTED]: "bg-blue-100 text-blue-700",
    [LeadStatus.REVIEWING]: "bg-purple-100 text-purple-700",
    [LeadStatus.APPROVED]: "bg-green-100 text-green-700",
    [LeadStatus.REJECTED]: "bg-red-100 text-red-700",
    [LeadStatus.ARCHIVED]: "bg-gray-100 text-gray-700",
  };

  return (
    <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-tight", styles[status])}>
      {status}
    </span>
  );
};

// --- App Hub ---

export default function App() {
  const { user, loading: authLoading, can, logout } = useAuth();
  const [leads, setLeads] = useState<Lead[]>(MOCK_LEADS);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'review' | 'analytics' | 'users'>('dashboard');
  const [manualEntryOpen, setManualEntryOpen] = useState(false);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);

  const selectedLead = leads.find(l => l.id === selectedLeadId);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    async function loadPersistedLeads() {
      try {
        const persistedLeads = await listLeads();
        if (!cancelled) {
          setLeads(persistedLeads.length > 0 ? persistedLeads : MOCK_LEADS);
          setLoadError(null);
        }
      } catch (err) {
        console.error('[client/app] load_leads_fail', {
          reason: err instanceof Error ? err.message : 'unknown',
        });
        if (!cancelled) {
          setLoadError('Could not load backend leads. Showing mock data.');
        }
      }
    }

    loadPersistedLeads();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const stats = {
    today: leads.length,
    pending: leads.filter(l => l.status === LeadStatus.PENDING).length,
    toCall: leads.filter(l => (l.rating === LeadRating.GD || l.rating === LeadRating.MF) && l.status === LeadStatus.PENDING).length,
    processed: leads.filter(l => l.status === LeadStatus.APPROVED || l.status === LeadStatus.REJECTED).length
  };

  const handleAddLead = async (input: {
    rawMessage: string;
    brand: string;
    extraction: ManualExtractionResponse;
  }) => {
    const persisted = await createConfirmedManualLead({
      ...input.extraction,
      rawMessage: input.rawMessage,
      brand: input.brand,
    });
    const newLead = await getLead(persisted.lead_id);
    setLeads(prev => [newLead, ...prev.filter(lead => lead.id !== newLead.id)]);
    setActiveTab('dashboard');
    setSelectedLeadId(newLead.id);
    setManualEntryOpen(false);

    if (persisted.pipeline_task_id) {
      void pollPipelineResult(persisted.lead_id, persisted.pipeline_task_id);
    }
  };

  const pollPipelineResult = async (leadId: string, taskId: string) => {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await new Promise(resolve => window.setTimeout(resolve, 2000));
      try {
        const [task, refreshedLead] = await Promise.all([getPipelineTaskStatus(taskId), getLead(leadId)]);
        setLeads(prev => prev.map(lead => lead.id === leadId ? refreshedLead : lead));
        if (task.status === 'SUCCESS') return;
        if (task.status === 'FAILURE') {
          setLoadError(`AI pipeline failed: ${task.error_type || 'unknown error'}.`);
          return;
        }
      } catch (err) {
        console.error('[client/app] pipeline_poll_fail', {
          leadId,
          taskId,
          reason: err instanceof Error ? err.message : 'unknown',
        });
      }
    }
    setLoadError('AI pipeline is still processing. Refresh the page to check the latest result.');
  };

  const updateLeadStatus = async (id: string, status: LeadStatus) => {
    const existingLead = leads.find(l => l.id === id);
    setLeads(prev => prev.map(l => l.id === id ? { ...l, status } : l));

    try {
      const persistedLead = await persistLeadStatus(id, status);
      setLeads(prev => prev.map(l => l.id === id ? { ...l, ...persistedLead } : l));
    } catch (err) {
      console.error('[client/app] update_status_fail', {
        leadId: id,
        status,
        reason: err instanceof Error ? err.message : 'unknown',
      });
      if (existingLead) {
        setLeads(prev => prev.map(l => l.id === id ? existingLead : l));
      }
      setLoadError('Could not update lead status. Backend state was not changed.');
    }
  };

  const replacePersistedLead = (persistedLead: Lead) => {
    setLeads(prev => prev.map(l => l.id === persistedLead.id ? { ...l, ...persistedLead } : l));
  };

  const approveLead = async (id: string) => {
    try {
      const persistedLead = await persistApproveLead(id);
      replacePersistedLead(persistedLead);
      setLoadError(null);
    } catch (err) {
      console.error('[client/app] approve_fail', { leadId: id, reason: err instanceof Error ? err.message : 'unknown' });
      setLoadError(err instanceof Error ? err.message : 'Could not approve lead.');
    }
  };

  const rejectLead = async (id: string) => {
    try {
      const persistedLead = await persistRejectLead(id, 'Returned for draft changes from review queue.');
      replacePersistedLead(persistedLead);
      setLoadError(null);
    } catch (err) {
      console.error('[client/app] reject_fail', { leadId: id, reason: err instanceof Error ? err.message : 'unknown' });
      setLoadError('Could not reject this review item.');
    }
  };

  const confirmLeadRejection = async (id: string) => {
    try {
      const persistedLead = await persistConfirmLeadRejection(id, 'Quality lead confirmed DNQ rejection.');
      replacePersistedLead(persistedLead);
      setLoadError(null);
    } catch (err) {
      console.error('[client/app] reject_confirm_fail', { leadId: id, reason: err instanceof Error ? err.message : 'unknown' });
      setLoadError('Could not confirm this rejection.');
    }
  };

  const editLeadDraft = async (id: string, input: { emailDraft?: string; whatsappDraft?: string; phoneScript?: string }) => {
    try {
      const persistedLead = await persistEditLeadDraft(id, {
        ...input,
        reason: 'Draft edited from frontend review workspace.',
      });
      replacePersistedLead(persistedLead);
      setLoadError(null);
    } catch (err) {
      console.error('[client/app] edit_draft_fail', { leadId: id, reason: err instanceof Error ? err.message : 'unknown' });
      setLoadError('Could not save draft edits.');
      throw err;
    }
  };

  const editLeadFields = async (id: string, input: LeadFieldEditInput) => {
    try {
      const persistedLead = await persistEditLeadFields(id, input);
      replacePersistedLead(persistedLead);
      setLoadError(null);
    } catch (err) {
      console.error('[client/app] edit_fields_fail', { leadId: id, reason: err instanceof Error ? err.message : 'unknown' });
      setLoadError('Could not save lead field edits.');
      throw err;
    }
  };

  if (authLoading && !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-slate-500">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 font-sans selection:bg-orange-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col shrink-0">
        <div className="p-6 border-bottom">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-orange-600 rounded-lg flex items-center justify-center text-white font-bold">X</div>
            <h1 className="font-bold text-lg tracking-tight">Xpatweb AI</h1>
          </div>

          <nav className="space-y-1">
            <NavItem 
              icon={<LayoutDashboard size={18} />} 
              label="Dashboard" 
              active={activeTab === 'dashboard'} 
              onClick={() => { setActiveTab('dashboard'); setSelectedLeadId(null); }} 
            />
            <NavItem 
              icon={<Inbox size={18} />} 
              label="Review Queue" 
              active={activeTab === 'review'} 
              onClick={() => { setActiveTab('review'); setSelectedLeadId(null); }} 
              badge={stats.pending}
            />
            <NavItem 
              icon={<BarChart3 size={18} />} 
              label="Analytics" 
              active={activeTab === 'analytics'} 
              onClick={() => { setActiveTab('analytics'); setSelectedLeadId(null); }} 
            />
            {can('user.manage') && (
              <NavItem
                icon={<Users size={18} />}
                label="Users"
                active={activeTab === 'users'}
                onClick={() => { setActiveTab('users'); setSelectedLeadId(null); }}
              />
            )}
          </nav>
        </div>

        <div className="mt-auto p-6 space-y-4">
          <button 
            onClick={() => setManualEntryOpen(true)}
            className="w-full py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-semibold flex items-center justify-center gap-2 transition-all shadow-sm shadow-orange-200 active:scale-95"
          >
            <Plus size={18} />
            <span>Manual Entry</span>
          </button>
          
          <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
            <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center">
              <User size={20} className="text-slate-500" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold">{user.display_name}</p>
              <p className="truncate text-[10px] text-slate-500 uppercase tracking-widest">{user.roles.join(', ')}</p>
            </div>
            <button onClick={logout} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto flex flex-col">
        {/* Header (Dynamic) */}
        <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur-md sticky top-0 z-10 px-8 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {selectedLeadId && (
              <button 
                onClick={() => setSelectedLeadId(null)}
                className="p-2 hover:bg-slate-100 rounded-full transition-colors"
                title="Close detail drawer"
              >
                <X size={18} />
              </button>
            )}
            <h2 className="font-bold text-slate-700">
              {activeTab === 'dashboard' ? 'Inbound Leads' : 
               activeTab === 'review' ? 'Review Queue' : 
               activeTab === 'users' ? 'User Management' :
               'Performance Analytics'}
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input 
                type="text" 
                placeholder="Search leads..." 
                className="pl-10 pr-4 py-2 border border-slate-200 rounded-full text-sm w-64 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all bg-slate-50"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
               <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 animate-pulse">
                  <Clock size={16} />
               </div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="p-8">
          {loadError && (
            <div className="mb-4 rounded-xl border border-yellow-200 bg-yellow-50 px-4 py-3 text-xs font-semibold text-yellow-800">
              {loadError}
            </div>
          )}
          <AnimatePresence mode="wait">
            {activeTab === 'dashboard' ? (
              <DashboardView 
                key="dashboard"
                leads={leads.filter(l => l.name.toLowerCase().includes(searchTerm.toLowerCase()))} 
                stats={stats} 
                onSelect={setSelectedLeadId} 
              />
            ) : activeTab === 'review' ? (
              <ReviewQueueView 
                key="review"
                leads={leads.filter(l => l.status === LeadStatus.PENDING || l.status === LeadStatus.REVIEWING)} 
                onSelect={setSelectedLeadId}
              />
            ) : activeTab === 'users' ? (
              <UserManagementView key="users" />
            ) : (
              <AnalyticsView key="analytics" leads={leads} />
            )}
          </AnimatePresence>
        </div>
      </main>
      <AnimatePresence>
        {selectedLead && (
          <LeadDetailDrawer
            key={selectedLead.id}
            lead={selectedLead}
            onClose={() => setSelectedLeadId(null)}
            onUpdateStatus={updateLeadStatus}
            onApproveLead={approveLead}
            onRejectLead={rejectLead}
            onConfirmLeadRejection={confirmLeadRejection}
            onEditFields={editLeadFields}
            onEditDraft={editLeadDraft}
            can={can}
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {manualEntryOpen && (
          <ManualEntryModal
            onClose={() => setManualEntryOpen(false)}
            onSubmit={handleAddLead}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// --- View Components ---

const NavItem = ({ icon, label, active, onClick, badge }: { icon: React.ReactNode, label: string, active?: boolean, onClick: () => void, badge?: number }) => (
  <button 
    onClick={onClick}
    className={cn(
      "w-full flex items-center justify-between px-4 py-2.5 rounded-xl transition-all duration-200 group text-sm font-medium",
      active ? "bg-orange-50 text-orange-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
    )}
  >
    <div className="flex items-center gap-3">
      <span className={cn(active ? "text-orange-600" : "text-slate-400 group-hover:text-slate-600")}>{icon}</span>
      <span>{label}</span>
    </div>
    {badge && badge > 0 && (
      <span className="w-5 h-5 flex items-center justify-center bg-orange-600 text-white rounded-full text-[10px] font-bold">
        {badge}
      </span>
    )}
  </button>
);

const DashboardView = ({ leads, stats, onSelect }: { leads: Lead[], stats: any, onSelect: (id: string) => void }) => {
  return (
    <motion.aside
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="space-y-8"
    >
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard title="Total Leads" value={stats.today} icon={<Inbox size={20} />} trend="+12% vs yesterday" color="bg-orange-600" />
        <StatCard title="Pending Review" value={stats.pending} icon={<Clock size={20} />} trend="Avg delay 15m" color="bg-blue-600" />
        <StatCard title="60s Call Queue" value={stats.toCall} icon={<Phone size={20} />} trend="⚡ Immediate priority" color="bg-yellow-600" flash />
        <StatCard title="Processed" value={stats.processed} icon={<CheckCircle2 size={20} />} trend="98% accuracy" color="bg-green-600" />
      </div>

      {/* Lead List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Lead Info</th>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Visa Path</th>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">AI Triage</th>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Source</th>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Status</th>
                <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {leads.map((lead) => (
                <tr 
                  key={lead.id} 
                  onClick={() => onSelect(lead.id)}
                  className="hover:bg-slate-50 cursor-pointer transition-colors group"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center text-white font-bold",
                        lead.rating === LeadRating.GD ? "bg-yellow-500" : 
                        lead.rating === LeadRating.BD ? "bg-red-500" : "bg-slate-300"
                      )}>
                        {lead.name[0]}
                      </div>
                      <div>
                        <p className="font-bold text-sm leading-none">{lead.name}</p>
                        <p className="text-xs text-slate-500 mt-1">{lead.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm font-medium">{lead.visaType}</p>
                  </td>
                  <td className="px-6 py-4">
                    <RatingBadge rating={lead.rating} confidence={lead.confidence} />
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs font-mono bg-slate-100 px-2 py-1 rounded">{lead.inboxBrand}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                       <StatusBadge status={lead.status} />
                       {lead.rating === LeadRating.GD && lead.status === LeadStatus.PENDING && (
                         <span className="text-[10px] bg-red-100 text-red-600 px-1 rounded animate-pulse font-bold">⚡ CALL NOW</span>
                       )}
                       {lead.escalationFlag && (
	                         <ShieldAlert size={14} className="text-red-600 animate-bounce" aria-label="Escalated to Jerry" />
                       )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-[10px] text-slate-400 font-mono italic">{formatDate(lead.timestamp)}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.aside>
  );
};

const StatCard = ({ title, value, icon, trend, color, flash }: any) => (
  <div className={cn("bg-white border border-slate-200 rounded-2xl p-6 shadow-sm relative overflow-hidden", flash && "border-yellow-400 ring-2 ring-yellow-400/20 shadow-yellow-100")}>
    <div className="flex justify-between items-start mb-4">
      <div className={cn("p-2 rounded-lg text-white", color)}>
        {icon}
      </div>
      {flash && <div className="bg-yellow-400 w-2 h-2 rounded-full animate-ping" />}
    </div>
    <p className="text-3xl font-bold text-slate-900 tracking-tight">{value}</p>
    <p className="text-xs font-bold text-slate-500 mt-1 uppercase tracking-wider">{title}</p>
    <p className="text-[10px] text-slate-400 mt-3 font-medium flex items-center gap-1 italic">
      {trend}
    </p>
  </div>
);

const LeadDetailDrawer = ({
  lead,
  onClose,
  onUpdateStatus,
  onApproveLead,
  onRejectLead,
  onConfirmLeadRejection,
  onEditFields,
  onEditDraft,
  can,
}: {
  lead: Lead;
  onClose: () => void;
  onUpdateStatus: (id: string, s: LeadStatus) => Promise<void>;
  onApproveLead: (id: string) => Promise<void>;
  onRejectLead: (id: string) => Promise<void>;
  onConfirmLeadRejection: (id: string) => Promise<void>;
  onEditFields: (id: string, input: LeadFieldEditInput) => Promise<void>;
  onEditDraft: (id: string, input: { emailDraft?: string; whatsappDraft?: string; phoneScript?: string }) => Promise<void>;
  can: (permission: string) => boolean;
}) => {
  const [activeTab, setActiveTab] = useState<'info' | 'brief' | 'audit'>('info');
  const [researching, setResearching] = useState(false);
  const [researchBrief, setResearchBrief] = useState(lead.researchBrief);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [draftV, setDraftV] = useState<'v1' | 'v2'>('v1');
  const [auditEvents, setAuditEvents] = useState<BackendAuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [workflowLoading, setWorkflowLoading] = useState<string | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<'emailDraft' | 'phoneScript' | 'whatsappDraft' | null>(null);
  const [editedDrafts, setEditedDrafts] = useState<string[]>([]);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [fieldDraft, setFieldDraft] = useState('');
  const [originalMessageOpen, setOriginalMessageOpen] = useState(false);
  const [originalMessageCopyState, setOriginalMessageCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [draftForm, setDraftForm] = useState({
    emailDraft: lead.emailDraft || '',
    whatsappDraft: lead.whatsappDraft || '',
    phoneScript: lead.phoneScript || '',
  });

  useEffect(() => {
    setDraftForm({
      emailDraft: lead.emailDraft || '',
      whatsappDraft: lead.whatsappDraft || '',
      phoneScript: lead.phoneScript || '',
    });
  }, [lead.emailDraft, lead.phoneScript, lead.whatsappDraft]);

  useEffect(() => {
    setOriginalMessageOpen(false);
    setOriginalMessageCopyState('idle');
    setResearchBrief(lead.researchBrief);
    setResearchError(null);
    setEditingField(null);
    setFieldDraft('');
    setEditingDraft(null);
    setEditedDrafts([]);
  }, [lead.id]);

  useEffect(() => {
    let cancelled = false;

    async function loadResearch() {
      try {
        const record = await getLeadResearch(lead.id);
        if (cancelled || !record) return;
        if (record.status === 'succeeded' && record.brief) {
          setResearchBrief(record.brief);
        } else if (record.status === 'failed') {
          setResearchError(record.error_message || 'Research is not available yet.');
        } else if (record.status === 'queued' || record.status === 'running') {
          setResearching(true);
        }
      } catch (err) {
        console.error('[client/detail/research] load_fail', {
          leadId: lead.id,
          reason: err instanceof Error ? err.message : 'unknown',
        });
      }
    }

    loadResearch();
    return () => {
      cancelled = true;
    };
  }, [lead.id]);

  useEffect(() => {
    let cancelled = false;

    async function loadAuditEvents() {
      setAuditLoading(true);
      setAuditError(null);
      try {
        const events = await listAuditEvents(lead.id);
        if (!cancelled) {
          setAuditEvents(events);
        }
      } catch (err) {
        console.error('[client/detail/audit] load_fail', {
          leadId: lead.id,
          reason: err instanceof Error ? err.message : 'unknown',
        });
        if (!cancelled) {
          setAuditEvents([]);
          setAuditError('Audit timeline unavailable.');
        }
      } finally {
        if (!cancelled) {
          setAuditLoading(false);
        }
      }
    }

    loadAuditEvents();
    return () => {
      cancelled = true;
    };
  }, [lead.id, lead.status]);

  const runWorkflow = async (name: string, action: () => Promise<void>) => {
    setWorkflowLoading(name);
    setWorkflowError(null);
    try {
      await action();
    } catch (err) {
      setWorkflowError(err instanceof Error ? err.message : 'Workflow action failed.');
    } finally {
      setWorkflowLoading(null);
    }
  };

  const saveDraftEdit = async (field: 'emailDraft' | 'phoneScript' | 'whatsappDraft') => {
    await runWorkflow(`edit-draft-${field}`, async () => {
      await onEditDraft(lead.id, { [field]: draftForm[field] });
      setEditedDrafts(current => current.includes(field) ? current : [...current, field]);
      setEditingDraft(null);
    });
  };

  const startFieldEdit = (field: string, value: string) => {
    setEditingField(field);
    setFieldDraft(value);
  };

  const saveFieldEdit = async (field: keyof LeadFieldEditInput) => {
    await runWorkflow(`field-${field}`, async () => {
      await onEditFields(lead.id, { [field]: fieldDraft || null });
      setEditingField(null);
      setFieldDraft('');
    });
  };

  const copyOriginalMessage = async () => {
    if (!lead.rawMessage) return;
    try {
      await navigator.clipboard.writeText(lead.rawMessage);
      setOriginalMessageCopyState('copied');
      window.setTimeout(() => setOriginalMessageCopyState('idle'), 1600);
    } catch {
      setOriginalMessageCopyState('failed');
      window.setTimeout(() => setOriginalMessageCopyState('idle'), 2200);
    }
  };

  const handleResearch = async () => {
    setResearching(true);
    setResearchError(null);
    try {
      await startLeadResearch(lead.id);
      for (let attempt = 0; attempt < 12; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 1000));
        const record = await getLeadResearch(lead.id);
        if (!record || record.status === 'queued' || record.status === 'running') {
          continue;
        }
        if (record.status === 'succeeded' && record.brief) {
          setResearchBrief(record.brief);
          break;
        }
        setResearchError(record.error_message || 'Research is not available yet.');
        break;
      }
      setActiveTab('brief');
    } catch (e) {
      console.error('[client/detail/research] run_fail', {
        leadId: lead.id,
        reason: e instanceof Error ? e.message : 'unknown',
      });
      setResearchError(e instanceof Error ? e.message : 'Research failed.');
    } finally {
      setResearching(false);
    }
  };

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  const hasDraft = Boolean(lead.emailDraft || lead.whatsappDraft || lead.phoneScript);
  const terminalStatus = [LeadStatus.APPROVED, LeadStatus.REJECTED, LeadStatus.ARCHIVED].includes(lead.status);
  const approveDisabledReason = terminalStatus
    ? 'Lead is already processed.'
    : !hasDraft
      ? 'No draft is available yet.'
      : !can('lead.approve')
        ? 'Approve permission required.'
        : null;
  const returnDisabledReason = terminalStatus
    ? 'Lead is already processed.'
    : !can('lead.reject')
      ? 'Return permission required.'
      : null;

  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0.8 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0.8 }}
      transition={{ type: 'spring', damping: 28, stiffness: 260 }}
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-none flex-col border-l border-slate-200 bg-white shadow-2xl shadow-slate-900/20 pointer-events-auto lg:w-[58vw] lg:min-w-[760px]"
    >
      <div className="h-1 shrink-0 bg-gradient-to-r from-orange-400 to-yellow-500" />
      <div className="flex shrink-0 items-center justify-between border-b border-slate-100 px-6 py-4">
        <div className="min-w-0">
          <h2 className="text-[10px] font-bold uppercase tracking-[0.25em] text-orange-600">Lead Detail</h2>
          <div className="mt-1 flex min-w-0 items-center gap-3">
            <h3 className="truncate text-xl font-bold text-slate-900">{lead.name}</h3>
            <RatingBadge rating={lead.rating} confidence={lead.confidence} />
            <StatusBadge status={lead.status} />
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          title="Close detail drawer"
          aria-label="Close detail drawer"
        >
          <X size={20} />
        </button>
      </div>

      <div className="flex shrink-0 border-b border-slate-100 bg-white px-6">
            <button 
              onClick={() => setActiveTab('info')}
              className={cn("px-6 py-4 text-sm font-bold tracking-tight transition-colors", activeTab === 'info' ? "text-orange-600 border-b-2 border-orange-600" : "text-slate-400")}
            >
              Overview
            </button>
            <button 
              onClick={() => setActiveTab('brief')}
              className={cn("px-6 py-4 text-sm font-bold tracking-tight transition-colors flex items-center gap-2", activeTab === 'brief' ? "text-orange-600 border-b-2 border-orange-600" : "text-slate-400")}
            >
              Research Brief
              {!researchBrief && !researching && <span className="w-2 h-2 rounded-full bg-slate-300" />}
              {researching && <Loader2 size={14} className="animate-spin text-orange-600" />}
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={cn("px-6 py-4 text-sm font-bold tracking-tight transition-colors", activeTab === 'audit' ? "text-orange-600 border-b-2 border-orange-600" : "text-slate-400")}
            >
              Activity Audit
            </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-50/70 p-6 custom-scrollbar">
        {activeTab === 'info' && (
          <div className="space-y-6">
            {(lead.rating === LeadRating.GD || lead.rating === LeadRating.MF) && lead.status === LeadStatus.PENDING && (
              <motion.div
                initial={{ scale: 0.98, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="relative overflow-hidden rounded-2xl bg-red-600 p-5 text-white shadow-xl shadow-red-200"
              >
                <div className="absolute -right-4 -top-4 h-32 w-32 rounded-full bg-white/10 blur-2xl" />
                <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 animate-pulse">
                        <Clock size={14} />
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-widest">60-Second Call Protocol</span>
                    </div>
                    <h3 className="text-lg font-bold">Immediate Contact Required</h3>
                    <p className="mt-1 text-sm leading-snug opacity-80">Gold-level leads lose value significantly after 5 minutes of non-response.</p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <a
                      href={`tel:${lead.phone}`}
                      onClick={() => onUpdateStatus(lead.id, LeadStatus.CONTACTED)}
                      className="flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-xs font-bold text-red-600 shadow-lg"
                    >
                      <Phone size={16} />
                      CALL NOW
                    </a>
                    <button
                      onClick={() => onUpdateStatus(lead.id, LeadStatus.CONTACTED)}
                      className="flex items-center justify-center gap-2 rounded-xl border border-red-500/50 bg-red-700 px-4 py-3 text-xs font-bold text-white transition-colors hover:bg-red-800"
                    >
                      <MessageSquare size={16} />
                      WHATSAPP
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="grid grid-cols-1 gap-8 text-sm xl:grid-cols-2">
                <div className="space-y-4">
                  <EditableDetailItem
                    label="Full Name"
                    value={lead.name}
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'name'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-name'}
                    onStart={() => startFieldEdit('name', lead.name)}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('name')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Email Address"
                    value={lead.email}
                    copyable
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'email'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-email'}
                    inputType="email"
                    onStart={() => startFieldEdit('email', lead.email)}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('email')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Phone Number"
                    value={lead.phone || "Not captured"}
                    copyable
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'phone'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-phone'}
                    onStart={() => startFieldEdit('phone', lead.phone || '')}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('phone')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Visa Interest"
                    value={lead.visaType}
                    highlight
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'visaCategory'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-visaCategory'}
                    options={VISA_TYPES}
                    onStart={() => startFieldEdit('visaCategory', lead.visaType)}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('visaCategory')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Source Code"
                    value={lead.source}
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'source'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-source'}
                    onStart={() => startFieldEdit('source', lead.source || '')}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('source')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Assigned To"
                    value={lead.assignedConsultant || "Melissa"}
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'assignedConsultant'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-assignedConsultant'}
                    onStart={() => startFieldEdit('assignedConsultant', lead.assignedConsultant || '')}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('assignedConsultant')}
                    onCancel={() => setEditingField(null)}
                  />
                  <EditableDetailItem
                    label="Inbox Brand"
                    value={lead.inboxBrand}
                    editable={can('lead.draft.edit')}
                    editing={editingField === 'brand'}
                    draftValue={fieldDraft}
                    loading={workflowLoading === 'field-brand'}
                    options={INBOX_BRANDS}
                    onStart={() => startFieldEdit('brand', lead.inboxBrand)}
                    onDraftChange={setFieldDraft}
                    onSave={() => saveFieldEdit('brand')}
                    onCancel={() => setEditingField(null)}
                  />
                  <DetailItem label="Est. Revenue" value={lead.estimatedRevenue || (lead.rating ? "Pending template match" : "Pending qualification")} highlight />
                </div>
                <div className="space-y-6">
                  <div>
                    <DetailLabel label="AI RATING" />
                    <div className="mt-2 flex items-center gap-4">
                      <RatingBadge rating={lead.rating} confidence={lead.confidence} />
                      <StatusBadge status={lead.status} />
                    </div>
                  </div>
                  <div>
                    <DetailLabel label="WHY THIS SCORE?" />
                    <ul className="mt-2 space-y-2">
                      {lead.reasons.map((r, i) => (
                        <li key={i} className="flex items-start gap-2 rounded border border-slate-100 bg-slate-50 p-2 text-xs text-slate-600">
                          <Check size={14} className="mt-0.5 shrink-0 text-green-500" />
                          <span>{r}</span>
                        </li>
                      ))}
                      {lead.reasons.length === 0 && (
                        <li className="flex items-start gap-2 rounded border border-slate-100 bg-slate-50 p-2 text-xs text-slate-500">
                          <Loader2 size={14} className="mt-0.5 shrink-0" />
                          <span>Qualification pending. The scoring reason will appear after the backend pipeline completes.</span>
                        </li>
                      )}
                      {lead.dnqReason && (
                        <li className="flex items-start gap-2 rounded border border-red-100 bg-red-50 p-2 text-xs text-red-600">
                          <ShieldAlert size={14} className="mt-0.5 shrink-0" />
                          <span>{lead.dnqReason}</span>
                        </li>
                      )}
                    </ul>
                  </div>
                </div>
                <OriginalMessagePanel
                  rawMessage={lead.rawMessage}
                  open={originalMessageOpen}
                  copyState={originalMessageCopyState}
                  onToggle={() => setOriginalMessageOpen(value => !value)}
                  onCopy={copyOriginalMessage}
                />
              </div>
            </div>

	            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
	              <div className="mb-6 flex items-center justify-between">
	                <DetailLabel label="COMMUNICATION DRAFTS" />
	                <div className="flex bg-slate-100 rounded-lg p-1">
	                  <button
	                    onClick={() => setDraftV('v1')}
	                    className={cn("px-3 py-1 text-[10px] font-bold rounded", draftV === 'v1' ? "bg-white shadow-sm text-orange-600" : "text-slate-500")}
	                  >TEMPLATE V1</button>
	                  <button
	                    onClick={() => setDraftV('v2')}
	                    className={cn("px-3 py-1 text-[10px] font-bold rounded", draftV === 'v2' ? "bg-white shadow-sm text-orange-600" : "text-slate-500")}
	                  >AI ENHANCED V2</button>
	                </div>
	              </div>

	              <div className="space-y-6">
	                <EditableDraftBlock
	                  title="Email Prototype"
	                  icon={<MessageSquare size={12} />}
	                  value={lead.emailDraft || "Drafting in progress..."}
	                  draftValue={draftForm.emailDraft}
	                  editing={editingDraft === 'emailDraft'}
	                  modified={editedDrafts.includes('emailDraft')}
	                  editable={can('lead.draft.edit')}
	                  loading={workflowLoading === 'edit-draft-emailDraft'}
	                  tone="neutral"
	                  rows={10}
	                  onEdit={() => setEditingDraft('emailDraft')}
	                  onChange={value => setDraftForm(current => ({ ...current, emailDraft: value }))}
	                  onSave={() => saveDraftEdit('emailDraft')}
	                  onCancel={() => {
	                    setDraftForm(current => ({ ...current, emailDraft: lead.emailDraft || '' }));
	                    setEditingDraft(null);
	                  }}
	                />

	                <div className="grid grid-cols-2 gap-4">
	                  <EditableDraftBlock
	                    title="Phone Script"
	                    icon={<Phone size={12} />}
	                    value={lead.phoneScript || "Follow standard opening protocol."}
	                    draftValue={draftForm.phoneScript}
	                    editing={editingDraft === 'phoneScript'}
	                    modified={editedDrafts.includes('phoneScript')}
	                    editable={can('lead.draft.edit')}
	                    loading={workflowLoading === 'edit-draft-phoneScript'}
	                    tone="phone"
	                    rows={7}
	                    onEdit={() => setEditingDraft('phoneScript')}
	                    onChange={value => setDraftForm(current => ({ ...current, phoneScript: value }))}
	                    onSave={() => saveDraftEdit('phoneScript')}
	                    onCancel={() => {
	                      setDraftForm(current => ({ ...current, phoneScript: lead.phoneScript || '' }));
	                      setEditingDraft(null);
	                    }}
	                  />
	                  <EditableDraftBlock
	                    title="WhatsApp Script"
	                    icon={<Plus size={12} />}
	                    value={lead.whatsappDraft || "No WhatsApp drafted."}
	                    draftValue={draftForm.whatsappDraft}
	                    editing={editingDraft === 'whatsappDraft'}
	                    modified={editedDrafts.includes('whatsappDraft')}
	                    editable={can('lead.draft.edit')}
	                    loading={workflowLoading === 'edit-draft-whatsappDraft'}
	                    tone="whatsapp"
	                    rows={7}
	                    onEdit={() => setEditingDraft('whatsappDraft')}
	                    onChange={value => setDraftForm(current => ({ ...current, whatsappDraft: value }))}
	                    onSave={() => saveDraftEdit('whatsappDraft')}
	                    onCancel={() => {
	                      setDraftForm(current => ({ ...current, whatsappDraft: lead.whatsappDraft || '' }));
	                      setEditingDraft(null);
	                    }}
	                  />
	                </div>
	              </div>
	            </div>
          </div>
        )}

        {activeTab === 'brief' && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            {researchBrief ? (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <BriefSection title="Personal Profile" content={researchBrief.personalProfile} icon={<User size={16}/>} />
                <BriefSection title="Employer Insights" content={researchBrief.employer} icon={<Inbox size={16}/>} />
                <BriefSection title="Immigration Analysis" content={researchBrief.immigrationAnalysis} icon={<ShieldAlert size={16}/>} />
                <BriefSection title="Consultant Tips" content={researchBrief.consultantTips} icon={<AlertTriangle size={16}/>} accent />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center space-y-4 py-20 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                  <Search size={32} />
                </div>
                <div>
                  <p className="font-bold text-slate-700">No Research Brief Found</p>
                  <p className="mx-auto mt-1 max-w-xs text-sm text-slate-500">
                    {researchError || 'Deep research is generated asynchronously after a Web Search provider is configured.'}
                  </p>
                </div>
                <button
                  onClick={handleResearch}
                  disabled={researching}
                  className="flex items-center gap-2 rounded-full bg-slate-900 px-6 py-2 text-sm font-bold text-white transition-all hover:bg-slate-800 disabled:bg-slate-400"
                >
                  {researching ? <Loader2 className="animate-spin" /> : <Plus size={16} />}
                  Generate Deep Research
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <DetailLabel label="ACTIVITY AUDIT" />
            <div className="mt-4 space-y-4">
              {auditLoading && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Loader2 size={14} className="animate-spin" />
                  Loading audit timeline
                </div>
              )}
              {!auditLoading && auditError && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
                  {auditError}
                </div>
              )}
              {!auditLoading && !auditError && auditEvents.length === 0 && (
                <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-500">
                  No audit events recorded yet.
                </div>
              )}
              {!auditLoading && !auditError && auditEvents.map((event) => (
                <AuditStep
                  key={event.event_id}
                  time={formatAuditTime(event.created_at)}
                  icon={auditIcon(event.event_type)}
                  text={auditText(event)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-200 bg-white px-6 py-4 shadow-[0_-8px_24px_rgba(15,23,42,0.06)]">
        {workflowError && (
          <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700">
            {workflowError}
          </div>
        )}
        {approveDisabledReason && (
          <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
            {approveDisabledReason}
          </div>
        )}
        <div className="grid grid-cols-3 gap-3">
          <WorkflowButton
            onClick={() => runWorkflow('approve', () => onApproveLead(lead.id))}
            icon={workflowLoading === 'approve' ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            label="Approve & Send"
            primary
            disabled={Boolean(workflowLoading) || Boolean(approveDisabledReason)}
            title={approveDisabledReason || undefined}
          />
          <WorkflowButton
            onClick={() => runWorkflow('reject', () => onRejectLead(lead.id))}
            icon={workflowLoading === 'reject' ? <Loader2 size={16} className="animate-spin" /> : <X size={16} />}
            label="Return"
            disabled={Boolean(workflowLoading) || Boolean(returnDisabledReason)}
            title={returnDisabledReason || undefined}
          />
          <WorkflowButton
            onClick={() => onUpdateStatus(lead.id, LeadStatus.ARCHIVED)}
            icon={<Archive size={16} />}
            label="Archive"
            disabled={Boolean(workflowLoading) || terminalStatus}
            title={terminalStatus ? 'Lead is already processed.' : undefined}
          />
        </div>
      </div>
    </motion.aside>
  );
};

const fieldClass = "w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all";

const ManualField = ({
  label,
  value,
  onChange,
  type = 'text',
  required = false,
  placeholder,
}: {
  label: string;
  value: string | number | null;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) => (
  <label className="space-y-1.5">
    <span className="flex items-center gap-2 text-[11px] font-bold text-slate-500 uppercase tracking-widest">
      {label}
      {!value && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] text-amber-700">Needs input</span>}
    </span>
    <input
      required={required}
      type={type}
      className={fieldClass}
      value={value ?? ''}
      placeholder={placeholder}
      onChange={event => onChange(event.target.value)}
    />
  </label>
);

const ManualEntryModal = ({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (input: { rawMessage: string; brand: string; extraction: ManualExtractionResponse }) => Promise<void>;
}) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [rawText, setRawText] = useState('');
  const [brand, setBrand] = useState('');
  const [extraction, setExtraction] = useState<ManualExtractionResponse | null>(null);
  const [showMore, setShowMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateExtracted = <K extends keyof ExtractedLeadFields>(key: K, value: ExtractedLeadFields[K]) => {
    setExtraction(current => current ? { ...current, extracted: { ...current.extracted, [key]: value } } : current);
  };

  const booleanValue = (value: boolean | null) => value === null ? '' : String(value);
  const parseBoolean = (value: string) => value === '' ? null : value === 'true';
  const canSubmit = Boolean(
    extraction?.extracted.sender_name.trim()
    && extraction.extracted.sender_name !== 'Not Provided'
    && extraction.extracted.email_address
    && extraction.extracted.visa_category
    && brand
  );

  const handleExtract = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await extractManualText(rawText);
      setExtraction(result);
      setStep(2);
    } catch (err) {
      console.error('[client/manual-modal] extract_fail', { reason: err instanceof Error ? err.message : 'unknown' });
      setError(err instanceof Error ? err.message : 'Extraction failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-6 backdrop-blur-sm"
      onMouseDown={event => event.target === event.currentTarget && !loading && onClose()}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }}
        className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-8 py-5">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-orange-600">Manual Entry · Step {step} of 2</p>
            <h3 className="mt-1 text-xl font-bold">{step === 1 ? 'Paste lead information' : 'Confirm extracted fields'}</h3>
          </div>
          <button onClick={onClose} disabled={loading} className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X size={20} />
          </button>
        </div>

        <div className="overflow-y-auto p-8 custom-scrollbar">
          {step === 1 ? (
            <div className="space-y-6">
              <div className="rounded-2xl border border-orange-100 bg-orange-50 p-4 text-sm text-orange-900">
                Paste the email body, headers, form response, or any other natural-language lead information. The AI extraction service will prepare the fields for review.
              </div>
              <textarea
                autoFocus
                rows={15}
                className={`${fieldClass} resize-none font-mono text-sm leading-relaxed`}
                placeholder="Paste the full enquiry here..."
                value={rawText}
                onChange={event => setRawText(event.target.value)}
              />
              <button
                onClick={handleExtract}
                disabled={loading || !rawText.trim()}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 py-4 font-bold text-white shadow-xl disabled:bg-slate-400"
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <ChevronRight size={18} />}
                {loading ? 'EXTRACTING INFORMATION' : 'EXTRACT INFORMATION'}
              </button>
            </div>
          ) : extraction ? (
            <form
              className="space-y-6"
              onSubmit={async event => {
                event.preventDefault();
                setLoading(true);
                setError(null);
                try {
                  await onSubmit({ rawMessage: rawText, brand, extraction });
                } catch (err) {
                  console.error('[client/manual-modal] submit_fail', { reason: err instanceof Error ? err.message : 'unknown' });
                  setError(err instanceof Error ? err.message : 'Lead could not be saved.');
                  setLoading(false);
                }
              }}
            >
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <ManualField label="Full Name" required value={extraction.extracted.sender_name} onChange={value => updateExtracted('sender_name', value)} />
                <ManualField label="Email Address" required type="email" value={extraction.extracted.email_address} onChange={value => updateExtracted('email_address', value || null)} />
                <ManualField label="Phone Number" value={extraction.extracted.contact_number} onChange={value => updateExtracted('contact_number', value || null)} />
                <ManualField label="Visa Category" required value={extraction.extracted.visa_category} placeholder={VISA_TYPES.join(', ')} onChange={value => updateExtracted('visa_category', value || null)} />
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Inbox Brand <span className="text-red-500">*</span></p>
                <div className="grid grid-cols-4 gap-2">
                  {INBOX_BRANDS.map(item => (
                    <button key={item} type="button" onClick={() => setBrand(item)} className={cn("rounded-xl border py-3 text-xs font-bold", brand === item ? "border-orange-600 bg-orange-600 text-white" : "border-slate-200 text-slate-500")}>
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              <button type="button" onClick={() => setShowMore(value => !value)} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-700">
                More extracted fields
                <ChevronDown size={18} className={cn("transition-transform", showMore && "rotate-180")} />
              </button>

              {showMore && (
                <div className="grid grid-cols-1 gap-5 rounded-2xl border border-slate-200 p-5 md:grid-cols-2">
                  <ManualField label="Lead Type" value={extraction.extracted.lead_type} onChange={value => updateExtracted('lead_type', (value || null) as ExtractedLeadFields['lead_type'])} />
                  <ManualField label="Current Visa" value={extraction.extracted.current_visa} onChange={value => updateExtracted('current_visa', value || null)} />
                  <ManualField label="PR Route" value={extraction.extracted.pr_route} onChange={value => updateExtracted('pr_route', (value || null) as ExtractedLeadFields['pr_route'])} />
                  <ManualField label="Nationality" value={extraction.extracted.nationality} onChange={value => updateExtracted('nationality', value || null)} />
                  <ManualField label="Job Title" value={extraction.extracted.job_title} onChange={value => updateExtracted('job_title', value || null)} />
                  <ManualField label="Net Worth / Income Signal" value={extraction.extracted.net_worth_indicator} onChange={value => updateExtracted('net_worth_indicator', value || null)} />
                  <ManualField label="Qualifying Work Visa Years" type="number" value={extraction.extracted.qualifying_work_visa_years} onChange={value => updateExtracted('qualifying_work_visa_years', value ? Number(value) : null)} />
                  <ManualField label="Annual Salary ZAR" type="number" value={extraction.extracted.annual_salary_zar} onChange={value => updateExtracted('annual_salary_zar', value ? Number(value) : null)} />
                  <ManualField label="Relationship Duration" value={extraction.extracted.relationship_duration} onChange={value => updateExtracted('relationship_duration', value || null)} />
                  <ManualField label="Marriage Type" value={extraction.extracted.marriage_type} onChange={value => updateExtracted('marriage_type', (value || null) as ExtractedLeadFields['marriage_type'])} />
                  <ManualField label="Rejection Date" type="date" value={extraction.extracted.rejection_date} onChange={value => updateExtracted('rejection_date', value || null)} />
                  <ManualField label="Additional Information" value={extraction.extracted.additional_info} onChange={value => updateExtracted('additional_info', value || null)} />
                  {([
                    ['First-world nationality', 'is_first_world'],
                    ['Has job offer', 'has_job_offer'],
                    ['PBS score below 100', 'pbs_total_score_below_100'],
                  ] as const).map(([label, key]) => (
                    <label key={key} className="space-y-1.5">
                      <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</span>
                      <select className={fieldClass} value={booleanValue(extraction.extracted[key])} onChange={event => updateExtracted(key, parseBoolean(event.target.value))}>
                        <option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option>
                      </select>
                    </label>
                  ))}
                  <label className="space-y-1.5">
                    <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Email Coherence</span>
                    <select className={fieldClass} value={extraction.extracted.email_coherence} onChange={event => updateExtracted('email_coherence', event.target.value as ExtractedLeadFields['email_coherence'])}>
                      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                    </select>
                  </label>
                  <label className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium">
                    <input type="checkbox" checked={extraction.extracted.urgency_flag} onChange={event => updateExtracted('urgency_flag', event.target.checked)} /> Urgency detected
                  </label>
                  <label className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium">
                    <input type="checkbox" checked={extraction.extracted.multi_visa_flag} onChange={event => updateExtracted('multi_visa_flag', event.target.checked)} /> Multiple visas detected
                  </label>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button type="button" disabled={loading} onClick={() => setStep(1)} className="rounded-2xl border border-slate-200 px-6 py-4 font-bold text-slate-600">BACK</button>
                <button type="submit" disabled={loading || !canSubmit} className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-slate-900 py-4 font-bold text-white disabled:bg-slate-400">
                  {loading ? <Loader2 size={18} className="animate-spin" /> : <ChevronRight size={18} />}
                  {loading ? 'SAVING & STARTING AI' : 'CONFIRM & PROCESS LEAD'}
                </button>
              </div>
            </form>
          ) : null}
          {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div>}
        </div>
      </motion.div>
    </motion.div>
  );
};

const ReviewQueueView = ({ leads, onSelect }: any) => (
  <div className="space-y-6 max-w-5xl mx-auto">
    <div className="flex items-center justify-between mb-2">
       <div>
          <h3 className="text-xl font-bold tracking-tight">Review Queue</h3>
          <p className="text-sm text-slate-500 mt-1">Approval required for all outgoing correspondence.</p>
       </div>
       <div className="flex gap-2">
          <span className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-[10px] font-bold uppercase tracking-wider border border-yellow-200">3 Priority Pending</span>
       </div>
    </div>
    
    <div className="space-y-4">
      {leads.length > 0 ? leads.map((lead: Lead) => (
        <div 
          key={lead.id} 
          onClick={() => onSelect(lead.id)}
          className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
               <div className="w-12 h-12 bg-slate-100 rounded-xl flex items-center justify-center text-slate-500 font-bold text-lg">
                  {lead.name[0]}
               </div>
               <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-slate-900">{lead.name}</h4>
                    <RatingBadge rating={lead.rating} />
                    {lead.rating === LeadRating.BD && <span className="text-[10px] bg-red-100 text-red-600 px-1 rounded uppercase font-bold">DNQ Audit</span>}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{lead.visaType} — {lead.inboxBrand} Inbox</p>
               </div>
            </div>
            <div className="flex items-center gap-4">
               <div className="text-right">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Waiting time</p>
                  <p className="text-xs font-mono font-bold text-slate-700">12 MINUTES</p>
               </div>
               <div className="p-2 border border-slate-100 rounded-full group-hover:bg-orange-50 group-hover:text-orange-600 transition-colors">
                  <ChevronRight size={20} />
               </div>
            </div>
          </div>
        </div>
      )) : (
        <div className="py-20 text-center bg-slate-50 border-2 border-dashed border-slate-200 rounded-3xl">
           <CheckCircle2 className="mx-auto text-slate-300 mb-4" size={48} />
           <p className="font-bold text-slate-500">Queue Clear! Good job.</p>
        </div>
      )}
    </div>
  </div>
);

const ROLE_LABELS: Record<string, string> = {
  superadmin: 'Superadmin',
  approver: 'Approver',
  agent: 'Agent',
  quality_lead: 'Quality Lead',
  reviewer: 'Reviewer',
};

const CATEGORY_LABELS: Record<string, string> = {
  escalation: '升级',
  dnq_reject: 'DNQ',
  visa_verification: '签证',
  standard_review: '常规',
};

const ROUTING_CATEGORIES = ['escalation', 'dnq_reject', 'visa_verification', 'standard_review'];

const UserManagementView = () => {
  const { can } = useAuth();
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null);
  const [newUser, setNewUser] = useState({
    email: '',
    displayName: '',
    password: '',
    role: 'agent',
    isActive: true,
  });

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedUsers, loadedRoles] = await Promise.all([listManagedUsers(), listAvailableRoles()]);
      setUsers(loadedUsers);
      setRoles(loadedRoles);
    } catch (err) {
      console.error('[client/users/view] load_fail', { reason: err instanceof Error ? err.message : 'unknown' });
      setError(err instanceof Error ? err.message : 'Could not load users.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const replaceUser = (updated: ManagedUser) => {
    setUsers(current => current.map(user => user.user_id === updated.user_id ? updated : user));
  };

  const createUser = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newUser.email || !newUser.displayName || newUser.password.length < 8 || !newUser.role) return;

    setSaving('create');
    setError(null);
    try {
      const created = await createManagedUser({ ...newUser, roles: [newUser.role], isActive: newUser.isActive });
      setUsers(current => [created, ...current]);
      setNewUser({ email: '', displayName: '', password: '', role: 'agent', isActive: true });
      setShowCreate(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create user.');
    } finally {
      setSaving(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="mx-auto max-w-6xl space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold tracking-tight">Users</h3>
          <p className="mt-1 text-sm text-slate-500">Manage accounts, permission roles, and per-user routing.</p>
        </div>
        <button
          onClick={() => setShowCreate(value => !value)}
          className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white shadow-md hover:bg-slate-800"
        >
          <UserPlus size={16} />
          Add User
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}

      {showCreate && (
        <form onSubmit={createUser} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <input
              className={fieldClass}
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={event => setNewUser(current => ({ ...current, email: event.target.value }))}
            />
            <input
              className={fieldClass}
              placeholder="Display name"
              value={newUser.displayName}
              onChange={event => setNewUser(current => ({ ...current, displayName: event.target.value }))}
            />
            <input
              className={fieldClass}
              type="password"
              placeholder="Temporary password"
              value={newUser.password}
              onChange={event => setNewUser(current => ({ ...current, password: event.target.value }))}
            />
            <label className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold">
              <input
                type="checkbox"
                checked={newUser.isActive}
                onChange={event => setNewUser(current => ({ ...current, isActive: event.target.checked }))}
              />
              Active
            </label>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {roles.map(role => (
              <button
                key={role}
                type="button"
                onClick={() => setNewUser(current => ({ ...current, role }))}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-[11px] font-bold uppercase tracking-tight",
                  newUser.role === role
                    ? "border-orange-600 bg-orange-50 text-orange-700"
                    : "border-slate-200 bg-white text-slate-500"
                )}
              >
                {ROLE_LABELS[role] || role}
              </button>
            ))}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setShowCreate(false)} className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving === 'create' || newUser.password.length < 8}
              className="flex items-center gap-2 rounded-xl bg-orange-600 px-4 py-2 text-xs font-bold text-white disabled:bg-slate-400"
            >
              {saving === 'create' && <Loader2 size={14} className="animate-spin" />}
              Create User
            </button>
          </div>
        </form>
      )}

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center gap-2 p-12 text-sm font-semibold text-slate-500">
            <Loader2 size={18} className="animate-spin" />
            Loading users
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest text-slate-500">User</th>
                  <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest text-slate-500">Role</th>
                  <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-widest text-slate-500">Routing</th>
                  <th className="px-6 py-4 text-right text-[11px] font-bold uppercase tracking-widest text-slate-500">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map(user => (
                  <tr key={user.user_id} className="hover:bg-slate-50">
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-3">
                        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 font-bold text-slate-500">
                          <span
                            className={cn(
                              "absolute -left-1 -top-1 h-3 w-3 rounded-full border-2 border-white",
                              user.is_active ? "bg-green-500" : "bg-slate-300"
                            )}
                            title={user.is_active ? 'Active' : 'Disabled'}
                          />
                          {user.display_name[0]?.toUpperCase() || 'U'}
                        </div>
                        <div>
                          <p className="text-sm font-bold text-slate-900">{user.display_name}</p>
                          <p className="text-xs text-slate-500">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-5">
                      <span className="rounded-full border border-orange-200 bg-orange-50 px-3 py-1.5 text-[10px] font-bold uppercase tracking-tight text-orange-700">
                        {ROLE_LABELS[user.roles[0]] || user.roles[0] || 'No Role'}
                      </span>
                    </td>
                    <td className="px-6 py-5">
                      {user.routing_categories.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {user.routing_categories.map(category => (
                            <span key={category} className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
                              {CATEGORY_LABELS[category] || category}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs font-semibold text-slate-400">— superadmin fallback</span>
                      )}
                    </td>
                    <td className="px-6 py-5 text-right">
                      <button
                        onClick={() => setEditingUser(user)}
                        className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {editingUser && (
        <UserEditModal
          user={editingUser}
          roles={roles}
          canConfigureRouting={can('routing.config')}
          saving={saving}
          onClose={() => setEditingUser(null)}
          onSaveUser={async input => {
            setSaving(`${editingUser.user_id}:save`);
            setError(null);
            try {
              const updated = await updateManagedUser(editingUser.user_id, input);
              replaceUser(updated);
              setEditingUser(updated);
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not update user.');
              throw err;
            } finally {
              setSaving(null);
            }
          }}
          onSaveRouting={async categories => {
            setSaving(`${editingUser.user_id}:routing`);
            setError(null);
            try {
              const updated = await updateUserRoutingCategories(editingUser.user_id, categories);
              replaceUser(updated);
              setEditingUser(updated);
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not update routing categories.');
              throw err;
            } finally {
              setSaving(null);
            }
          }}
          onResetPassword={async password => {
            setSaving(`${editingUser.user_id}:password`);
            setError(null);
            try {
              const updated = await resetManagedUserPassword(editingUser.user_id, password);
              replaceUser(updated);
              setEditingUser(updated);
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Could not reset password.');
              throw err;
            } finally {
              setSaving(null);
            }
          }}
        />
      )}
    </motion.div>
  );
};

const UserEditModal = ({
  user,
  roles,
  canConfigureRouting,
  saving,
  onClose,
  onSaveUser,
  onSaveRouting,
  onResetPassword,
}: {
  user: ManagedUser;
  roles: string[];
  canConfigureRouting: boolean;
  saving: string | null;
  onClose: () => void;
  onSaveUser: (input: UserUpdateInput) => Promise<void>;
  onSaveRouting: (categories: string[]) => Promise<void>;
  onResetPassword: (password: string) => Promise<void>;
}) => {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [isActive, setIsActive] = useState(user.is_active);
  const [role, setRole] = useState(user.roles[0] || 'agent');
  const [categories, setCategories] = useState<string[]>(user.routing_categories);
  const [password, setPassword] = useState('');
  const [modalError, setModalError] = useState<string | null>(null);

  useEffect(() => {
    setDisplayName(user.display_name);
    setIsActive(user.is_active);
    setRole(user.roles[0] || 'agent');
    setCategories(user.routing_categories);
    setPassword('');
    setModalError(null);
  }, [user]);

  const toggleCategory = (category: string) => {
    setCategories(current => current.includes(category)
      ? current.filter(item => item !== category)
      : [...current, category]);
  };

  const handleSave = async () => {
    setModalError(null);
    try {
      await onSaveUser({ displayName, isActive, roles: [role] });
      if (canConfigureRouting) {
        await onSaveRouting(categories);
      }
      onClose();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Could not save user.');
    }
  };

  const handlePasswordReset = async () => {
    if (password.length < 8) return;
    setModalError(null);
    try {
      await onResetPassword(password);
      setPassword('');
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Could not reset password.');
    }
  };

  const isBusy = Boolean(saving);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-6 backdrop-blur-sm">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-orange-600">Edit User</p>
            <h3 className="mt-1 text-xl font-bold">{user.display_name}</h3>
          </div>
          <button onClick={onClose} disabled={isBusy} className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X size={20} />
          </button>
        </div>
        <div className="max-h-[75vh] space-y-6 overflow-y-auto p-6 custom-scrollbar">
          {modalError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {modalError}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Display Name</span>
              <input className={fieldClass} value={displayName} onChange={event => setDisplayName(event.target.value)} />
            </label>
            <label className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Email</span>
              <input className={fieldClass} value={user.email} readOnly />
            </label>
          </div>

          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Status</p>
            <div className="flex gap-2">
              {[
                [true, 'Active'],
                [false, 'Disabled'],
              ].map(([value, label]) => (
                <button
                  key={String(value)}
                  type="button"
                  onClick={() => setIsActive(Boolean(value))}
                  className={cn(
                    "rounded-xl border px-4 py-2 text-xs font-bold",
                    isActive === value ? "border-orange-600 bg-orange-50 text-orange-700" : "border-slate-200 text-slate-500"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Role</p>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {roles.map(item => (
                <label key={item} className={cn("flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold", role === item ? "border-orange-500 bg-orange-50 text-orange-700" : "border-slate-200 text-slate-600")}>
                  <input type="radio" name="role" checked={role === item} onChange={() => setRole(item)} />
                  {ROLE_LABELS[item] || item}
                </label>
              ))}
            </div>
          </div>

          <div className={cn("space-y-2", !canConfigureRouting && "opacity-60")}>
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Routing Categories</p>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {ROUTING_CATEGORIES.map(category => (
                <label key={category} className={cn("flex items-center gap-2 rounded-xl border px-3 py-3 text-xs font-bold", categories.includes(category) ? "border-orange-500 bg-orange-50 text-orange-700" : "border-slate-200 text-slate-500")}>
                  <input
                    type="checkbox"
                    disabled={!canConfigureRouting}
                    checked={categories.includes(category)}
                    onChange={() => toggleCategory(category)}
                  />
                  {CATEGORY_LABELS[category]}
                </label>
              ))}
            </div>
            <p className="text-[11px] font-semibold text-slate-500">
              {canConfigureRouting ? 'No category selected means superadmin receives fallback notifications.' : 'Routing categories require superadmin permission.'}
            </p>
          </div>

          <div className="space-y-2 border-t border-slate-100 pt-5">
            <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Reset Password</p>
            <div className="flex gap-2">
              <input
                type="password"
                className={fieldClass}
                placeholder="New password"
                value={password}
                onChange={event => setPassword(event.target.value)}
              />
              <button
                type="button"
                onClick={handlePasswordReset}
                disabled={isBusy || password.length < 8}
                className="flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                <KeyRound size={14} />
                Reset
              </button>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
          <button onClick={onClose} disabled={isBusy} className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600">
            Cancel
          </button>
          <button onClick={handleSave} disabled={isBusy || !displayName.trim()} className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white disabled:bg-slate-400">
            {isBusy && <Loader2 size={14} className="animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

const AnalyticsView = ({ leads }: { leads: Lead[] }) => (
  <div className="space-y-8">
     <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
           <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-4">Rating Mix</p>
           <div className="flex flex-col gap-3">
              <AnalyticsBar label="GOLD (GD)" value={leads.filter(l => l.rating === LeadRating.GD).length} total={leads.length} color="bg-yellow-500" />
              <AnalyticsBar label="MED. F/U (MF)" value={leads.filter(l => l.rating === LeadRating.MF).length} total={leads.length} color="bg-blue-500" />
              <AnalyticsBar label="MEDIUM (MD)" value={leads.filter(l => l.rating === LeadRating.MD).length} total={leads.length} color="bg-green-500" />
              <AnalyticsBar label="BAD (BD)" value={leads.filter(l => l.rating === LeadRating.BD).length} total={leads.length} color="bg-red-500" />
           </div>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm col-span-2">
           <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-4">Weekly Volume</p>
           <div className="h-40 flex items-end justify-between px-4">
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => (
                <div key={day} className="flex flex-col items-center gap-2 w-10">
                   <div className="w-full bg-slate-100 rounded-t-lg relative group">
                      <div className="absolute bottom-0 w-full bg-orange-500 rounded-t-lg transition-all" style={{ height: Math.random() * 80 + '%' }} />
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-2 py-0.5 rounded text-[8px] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                         24 Leads
                      </div>
                   </div>
                   <span className="text-[10px] font-bold text-slate-400">{day}</span>
                </div>
              ))}
           </div>
        </div>
     </div>

     <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <table className="w-full text-left">
           <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                 <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Source Code</th>
                 <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Lead Count</th>
                 <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">GD %</th>
                 <th className="px-6 py-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">Est. Revenue</th>
              </tr>
           </thead>
           <tbody className="divide-y divide-slate-100 text-sm">
              <tr>
                 <td className="px-6 py-4 font-bold text-orange-600">RSA024</td>
                 <td className="px-6 py-4">38</td>
                 <td className="px-6 py-4">71%</td>
                 <td className="px-6 py-4 text-green-600 font-bold">R1,892,000</td>
              </tr>
              <tr>
                 <td className="px-6 py-4 font-bold text-orange-600">XP-ORGANIC</td>
                 <td className="px-6 py-4">55</td>
                 <td className="px-6 py-4">28%</td>
                 <td className="px-6 py-4 text-green-600 font-bold">R892,000</td>
              </tr>
           </tbody>
        </table>
     </div>
  </div>
);

// --- Sub-components ---

const AnalyticsBar = ({ label, value, total, color }: any) => (
  <div>
     <div className="flex justify-between text-[9px] font-bold text-slate-500 mb-1">
        <span>{label}</span>
        <span>{value} ({Math.round(value/total*100) || 0}%)</span>
     </div>
     <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-1000", color)} style={{ width: (value/total*100) + '%' }} />
     </div>
  </div>
);

const EditableDetailItem = ({
  label,
  value,
  copyable,
  highlight,
  editable,
  editing,
  draftValue,
  inputType = 'text',
  options,
  loading,
  onStart,
  onDraftChange,
  onSave,
  onCancel,
}: {
  label: string;
  value: string;
  copyable?: boolean;
  highlight?: boolean;
  editable: boolean;
  editing: boolean;
  draftValue: string;
  inputType?: string;
  options?: string[];
  loading?: boolean;
  onStart: () => void;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) => (
  <div>
    <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
    {editing ? (
      <div className="flex items-center gap-2">
        {options ? (
          <select
            className="min-w-0 flex-1 rounded-lg border border-orange-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
            value={draftValue}
            onChange={event => onDraftChange(event.target.value)}
          >
            {options.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        ) : (
          <input
            type={inputType}
            className="min-w-0 flex-1 rounded-lg border border-orange-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20"
            value={draftValue}
            onChange={event => onDraftChange(event.target.value)}
          />
        )}
        <button
          onClick={onSave}
          disabled={loading}
          className="rounded-lg bg-slate-900 p-2 text-white hover:bg-slate-800 disabled:bg-slate-400"
          title="Save field"
          aria-label="Save field"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50 disabled:opacity-50"
          title="Cancel edit"
          aria-label="Cancel edit"
        >
          <X size={14} />
        </button>
      </div>
    ) : (
      <div className="group flex items-center justify-between gap-2">
        <p className={cn("min-w-0 truncate font-semibold leading-tight", highlight ? "text-orange-600 text-lg" : "text-slate-800")}>{value}</p>
        <div className="flex shrink-0 items-center gap-1">
          {copyable && (
            <button className="rounded p-1 text-slate-400 opacity-0 transition-opacity hover:bg-slate-100 group-hover:opacity-100">
              <Inbox size={14} />
            </button>
          )}
          {editable && (
            <button
              onClick={onStart}
              className="rounded p-1 text-slate-400 opacity-0 transition-opacity hover:bg-orange-50 hover:text-orange-600 group-hover:opacity-100"
              title={`Edit ${label}`}
              aria-label={`Edit ${label}`}
            >
              <FileEdit size={14} />
            </button>
          )}
        </div>
      </div>
    )}
  </div>
);

const EditableDraftBlock = ({
  title,
  icon,
  value,
  draftValue,
  editing,
  modified,
  editable,
  loading,
  tone,
  rows,
  onEdit,
  onChange,
  onSave,
  onCancel,
}: {
  title: string;
  icon: React.ReactNode;
  value: string;
  draftValue: string;
  editing: boolean;
  modified: boolean;
  editable: boolean;
  loading?: boolean;
  tone: 'neutral' | 'phone' | 'whatsapp';
  rows: number;
  onEdit: () => void;
  onChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}) => {
  const displayStyles = {
    neutral: "bg-slate-50 border-slate-200 font-mono whitespace-pre-wrap leading-relaxed",
    phone: "bg-yellow-50 border-yellow-200 italic border-l-4",
    whatsapp: "bg-green-50 border-green-200 font-mono",
  };
  const editStyles = {
    neutral: "bg-slate-50 border-slate-200 font-mono",
    phone: "bg-yellow-50 border-yellow-200 italic",
    whatsapp: "bg-green-50 border-green-200 font-mono",
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            {icon} {title}
          </p>
          {modified && (
            <span className="rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-orange-700">
              Modified
            </span>
          )}
        </div>
        {!editing && (
          <div className="flex shrink-0 items-center gap-2">
            {editable && (
              <button
                onClick={onEdit}
                className="flex items-center gap-1 rounded-lg border border-orange-200 bg-orange-50 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-orange-700 hover:border-orange-500 hover:bg-orange-100"
              >
                <FileEdit size={12} />
                Edit
              </button>
            )}
            <button className="text-[10px] text-orange-600 font-bold hover:underline">COPY</button>
          </div>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            rows={rows}
            className={cn(
              "w-full resize-none rounded-xl border p-4 text-xs text-slate-700 outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/20",
              editStyles[tone],
            )}
            value={draftValue}
            onChange={event => onChange(event.target.value)}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={onCancel}
              disabled={loading}
              className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onSave}
              disabled={loading}
              className="flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:bg-slate-400"
            >
              {loading && <Loader2 size={14} className="animate-spin" />}
              Save
            </button>
          </div>
        </div>
      ) : (
        <div className={cn("rounded-xl border p-4 text-xs text-slate-700", displayStyles[tone])}>
          {value}
        </div>
      )}
    </div>
  );
};

const DetailItem = ({ label, value, copyable, highlight }: any) => (
  <div>
    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">{label}</p>
    <div className="flex items-center justify-between group">
      <p className={cn("font-semibold leading-tight", highlight ? "text-orange-600 text-lg" : "text-slate-800")}>{value}</p>
      {copyable && (
        <button className="p-1 hover:bg-slate-100 rounded text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity"><Inbox size={14} /></button>
      )}
    </div>
  </div>
);

const OriginalMessagePanel = ({
  rawMessage,
  open,
  copyState,
  onToggle,
  onCopy,
}: {
  rawMessage?: string;
  open: boolean;
  copyState: 'idle' | 'copied' | 'failed';
  onToggle: () => void;
  onCopy: () => void;
}) => {
  const hasMessage = Boolean(rawMessage);
  const messageLength = rawMessage?.length ?? 0;
  const messageLabel = hasMessage
    ? `Original Message (${messageLength.toLocaleString()} chars)`
    : 'Original Message (not captured)';
  const copyLabel = copyState === 'copied' ? 'Copied' : copyState === 'failed' ? 'Copy failed' : 'Copy';

  return (
    <div className="col-span-2 border-t border-slate-200 pt-4">
      <div className="rounded-xl border border-slate-200 bg-slate-50/70">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <button
            type="button"
            onClick={onToggle}
            className="flex min-w-0 flex-1 items-center gap-2 text-left text-xs font-bold uppercase tracking-wider text-slate-700 hover:text-orange-600"
            aria-expanded={open}
          >
            {open ? <ChevronDown size={16} className="shrink-0" /> : <ChevronRight size={16} className="shrink-0" />}
            <Inbox size={16} className="shrink-0 text-slate-400" />
            <span className="truncate">{messageLabel}</span>
          </button>
          <button
            type="button"
            onClick={onCopy}
            disabled={!hasMessage}
            className={cn(
              "shrink-0 rounded-lg border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors",
              hasMessage
                ? "border-orange-200 bg-white text-orange-600 hover:border-orange-500 hover:bg-orange-50"
                : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
            )}
          >
            {copyLabel}
          </button>
        </div>
        {open && (
          <div className="border-t border-slate-200 p-4">
            {hasMessage ? (
              <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4 font-mono text-xs leading-relaxed text-slate-700 whitespace-pre-wrap custom-scrollbar">
                {rawMessage ?? ''}
              </div>
            ) : (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs font-semibold text-amber-700">
                Original message was not returned with this lead yet.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const DetailLabel = ({ label }: { label: string }) => (
  <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">{label}</p>
);

const BriefSection = ({ title, content, icon, accent }: any) => (
  <div className={cn("p-4 rounded-xl border border-slate-100 space-y-3", accent ? "bg-orange-50 border-orange-100 ring-1 ring-orange-200/50" : "bg-white")}>
    <div className="flex items-center gap-2 text-slate-900 border-b border-slate-100 pb-2">
      <span className={accent ? "text-orange-600" : "text-slate-400"}>{icon}</span>
      <h5 className="text-xs font-bold uppercase tracking-tight">{title}</h5>
    </div>
    <div className="text-xs text-slate-600 leading-relaxed max-h-40 overflow-auto pr-2 custom-scrollbar">
       <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  </div>
);

const WorkflowButton = ({ icon, label, onClick, primary, disabled, title }: any) => (
  <button
    onClick={onClick}
    disabled={disabled}
    title={title}
    className={cn(
      "w-full justify-center py-2.5 px-4 rounded-xl text-xs font-bold flex items-center gap-3 transition-all disabled:cursor-not-allowed disabled:opacity-50",
      primary ? "bg-slate-900 text-white hover:bg-slate-800 shadow-md shadow-slate-200" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
    )}
  >
    {icon}
    <span>{label}</span>
  </button>
);

const formatAuditTime = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-ZA', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

const statusLabel = (value: unknown) => {
  if (typeof value !== 'string') return 'unknown';
  return value.replace(/_/g, ' ');
};

const fieldLabel = (value: unknown) => {
  const labels: Record<string, string> = {
    name: 'full name',
    email: 'email address',
    phone: 'phone number',
    visa_category: 'visa interest',
    visaCategory: 'visa interest',
    source: 'source code',
    assigned_consultant: 'assigned consultant',
    assignedConsultant: 'assigned consultant',
    brand: 'inbox brand',
    emailDraft: 'email draft',
    phoneScript: 'phone script',
    whatsappDraft: 'WhatsApp script',
    email_draft: 'email draft',
    phone_script: 'phone script',
    whatsapp_draft: 'WhatsApp script',
  };
  return typeof value === 'string' ? labels[value] || value.replace(/_/g, ' ') : 'field';
};

const auditText = (event: BackendAuditEvent) => {
  if (event.event_type === 'lead.received.manual') {
    return 'Lead received from manual entry.';
  }

  if (event.event_type === 'lead.status_changed') {
    return `Status changed: ${statusLabel(event.metadata.previous_status)} -> ${statusLabel(event.metadata.new_status)}.`;
  }

  if (event.event_type === 'lead.fields.edited') {
    return `Lead ${fieldLabel(event.metadata.field)} was edited.`;
  }

  if (event.event_type === 'lead.drafts.edited') {
    const changed = Array.isArray(event.metadata.changed_fields)
      ? event.metadata.changed_fields.map(fieldLabel).join(', ')
      : 'draft content';
    return `Draft edited: ${changed}.`;
  }

  if (event.event_type === 'lead.approved') {
    return 'Lead approved for sending.';
  }

  if (event.event_type === 'lead.review.rejected') {
    return 'Lead returned for draft changes.';
  }

  if (event.event_type === 'lead.reject.confirmed') {
    return 'DNQ rejection confirmed.';
  }

  return event.event_type.replace(/\./g, ' ');
};

const auditIcon = (eventType: string) => {
  if (eventType === 'lead.received.manual') return <Inbox size={12} />;
  if (eventType === 'lead.status_changed') return <CheckCircle2 size={12} />;
  if (eventType === 'lead.fields.edited') return <FileEdit size={12} />;
  if (eventType === 'lead.drafts.edited') return <MessageSquare size={12} />;
  if (eventType === 'lead.approved') return <Send size={12} />;
  if (eventType === 'lead.review.rejected' || eventType === 'lead.reject.confirmed') return <X size={12} />;
  if (eventType.includes('triage') || eventType.includes('scored')) return <BarChart3 size={12} />;
  if (eventType.includes('call')) return <Phone size={12} />;
  return <Clock size={12} />;
};

const AuditStep = ({ time, icon, text }: any) => (
  <div className="flex gap-3">
     <div className="flex flex-col items-center gap-1 shrink-0">
        <div className="w-6 h-6 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-400">
           {icon}
        </div>
        <div className="w-px flex-1 bg-slate-200" />
     </div>
     <div className="pb-4">
        <p className="text-[10px] font-bold text-slate-400 leading-tight mb-1">{time}</p>
        <p className="text-xs text-slate-600 leading-snug">{text}</p>
     </div>
  </div>
);
