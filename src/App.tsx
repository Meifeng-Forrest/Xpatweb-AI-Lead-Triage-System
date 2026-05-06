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
  ArrowLeft,
  Check,
  Send,
  X,
  AlertTriangle,
  ChevronRight,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { Lead, LeadRating, LeadStatus } from './types';
import { MOCK_LEADS } from './mockData';
import { cn, formatDate } from './lib/utils';
import { RATING_LABELS, INBOX_BRANDS, VISA_TYPES } from './constants';
import ReactMarkdown from 'react-markdown';
import { triageLead, generateResearchBrief } from './services/geminiService';

// --- Components ---

const RatingBadge = ({ rating, confidence }: { rating: LeadRating, confidence?: string }) => {
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
  const [leads, setLeads] = useState<Lead[]>(MOCK_LEADS);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'review' | 'entry' | 'analytics'>('dashboard');
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const selectedLead = leads.find(l => l.id === selectedLeadId);

  const stats = {
    today: leads.length,
    pending: leads.filter(l => l.status === LeadStatus.PENDING).length,
    toCall: leads.filter(l => (l.rating === LeadRating.GD || l.rating === LeadRating.MF) && l.status === LeadStatus.PENDING).length,
    processed: leads.filter(l => l.status === LeadStatus.APPROVED || l.status === LeadStatus.REJECTED).length
  };

  const handleAddLead = async (input: { name: string, email: string, visaType: string, brand: string }) => {
    const newLead: Lead = {
      id: Math.random().toString(36).substr(2, 9),
      name: input.name,
      email: input.email,
      phone: "",
      visaType: input.visaType,
      source: "Manual",
      inboxBrand: input.brand,
      timestamp: new Date().toISOString(),
      status: LeadStatus.PENDING,
      rating: LeadRating.MD, // Temporary
      confidence: "medium",
      reasons: ["Manually entered"],
      escalationFlag: false
    };

    setLeads(prev => [newLead, ...prev]);
    setActiveTab('dashboard');
    setSelectedLeadId(newLead.id);

    // Run AI Triage in background
    try {
      const aiResponse = await triageLead(`New lead: ${input.name}, email: ${input.email}, visa: ${input.visaType}`);
      setLeads(prev => prev.map(l => l.id === newLead.id ? { ...l, ...aiResponse } : l));
    } catch (e) {
      console.error(e);
    }
  };

  const updateLeadStatus = (id: string, status: LeadStatus) => {
    setLeads(prev => prev.map(l => l.id === id ? { ...l, status } : l));
  };

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
          </nav>
        </div>

        <div className="mt-auto p-6 space-y-4">
          <button 
            onClick={() => setActiveTab('entry')}
            className="w-full py-2.5 px-4 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-semibold flex items-center justify-center gap-2 transition-all shadow-sm shadow-orange-200 active:scale-95"
          >
            <Plus size={18} />
            <span>Manual Entry</span>
          </button>
          
          <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
            <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center">
              <User size={20} className="text-slate-500" />
            </div>
            <div>
              <p className="text-sm font-bold">Melissa</p>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest">Lead Manager</p>
            </div>
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
              >
                <ArrowLeft size={18} />
              </button>
            )}
            <h2 className="font-bold text-slate-700">
              {activeTab === 'dashboard' ? 'Inbound Leads' : 
               activeTab === 'review' ? 'Review Queue' : 
               activeTab === 'entry' ? 'New Lead Entry' : 'Performance Analytics'}
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
          <AnimatePresence mode="wait">
            {selectedLeadId ? (
              <LeadDetailView 
                key="detail"
                lead={selectedLead!} 
                onClose={() => setSelectedLeadId(null)} 
                onUpdateStatus={updateLeadStatus}
              />
            ) : activeTab === 'dashboard' ? (
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
            ) : activeTab === 'entry' ? (
              <LeadEntryView 
                key="entry"
                onSubmit={handleAddLead} 
              />
            ) : (
              <AnalyticsView key="analytics" leads={leads} />
            )}
          </AnimatePresence>
        </div>
      </main>
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
    <motion.div 
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
                         <ShieldAlert size={14} className="text-red-600 animate-bounce" title="Escalated to Jerry" />
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
    </motion.div>
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

const LeadDetailView = ({ lead, onClose, onUpdateStatus }: { lead: Lead, onClose: () => void, onUpdateStatus: (id: string, s: LeadStatus) => void }) => {
  const [activeTab, setActiveTab] = useState<'info' | 'brief'>('info');
  const [researching, setResearching] = useState(false);
  const [draftV, setDraftV] = useState<'v1' | 'v2'>('v1');

  const handleResearch = async () => {
    setResearching(true);
    try {
      const brief = await generateResearchBrief(lead);
      lead.researchBrief = brief; // In a real app, update state/db
      setActiveTab('brief');
    } catch (e) {
      console.error(e);
    } finally {
      setResearching(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="grid grid-cols-1 lg:grid-cols-3 gap-8"
    >
      {/* Left Col: Info & Action */}
      <div className="lg:col-span-2 space-y-8">
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
          <div className="h-1 bg-gradient-to-r from-orange-400 to-yellow-500" />
          
          <div className="flex border-b border-slate-100">
            <button 
              onClick={() => setActiveTab('info')}
              className={cn("px-6 py-4 text-sm font-bold tracking-tight transition-colors", activeTab === 'info' ? "text-orange-600 border-b-2 border-orange-600" : "text-slate-400")}
            >
              Leads Information
            </button>
            <button 
              onClick={() => setActiveTab('brief')}
              className={cn("px-6 py-4 text-sm font-bold tracking-tight transition-colors flex items-center gap-2", activeTab === 'brief' ? "text-orange-600 border-b-2 border-orange-600" : "text-slate-400")}
            >
              Research Brief
              {!lead.researchBrief && !researching && <span className="w-2 h-2 rounded-full bg-slate-300" />}
              {researching && <Loader2 size={14} className="animate-spin text-orange-600" />}
            </button>
          </div>

          <div className="p-8">
            {activeTab === 'info' ? (
               <div className="grid grid-cols-2 gap-8 text-sm">
                  <div className="space-y-4">
                    <DetailItem label="Full Name" value={lead.name} />
                    <DetailItem label="Email Address" value={lead.email} copyable />
                    <DetailItem label="Phone Number" value={lead.phone || "Not captured"} copyable />
                    <DetailItem label="Visa Interest" value={lead.visaType} highlight />
                    <DetailItem label="Source Code" value={lead.source} />
                    <DetailItem label="Assigned To" value={lead.assignedConsultant || "Melissa"} />
                    <DetailItem label="Est. Revenue" value={lead.rating === LeadRating.GD ? "R44,760" : "R12,500"} highlight />
                  </div>
                  <div className="space-y-6">
                    <div>
                      <DetailLabel label="AI RATING" />
                      <div className="mt-2 flex items-center gap-4">
                         <RatingBadge rating={lead.rating} />
                         <StatusBadge status={lead.status} />
                      </div>
                    </div>
                    <div>
                      <DetailLabel label="WHY THIS SCORE?" />
                      <ul className="mt-2 space-y-2">
                        {lead.reasons.map((r, i) => (
                           <li key={i} className="flex gap-2 items-start text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100">
                             <Check size={14} className="text-green-500 shrink-0 mt-0.5" />
                             <span>{r}</span>
                           </li>
                        ))}
                        {lead.dnqReason && (
                           <li className="flex gap-2 items-start text-xs text-red-600 bg-red-50 p-2 rounded border border-red-100">
                             <ShieldAlert size={14} className="shrink-0 mt-0.5" />
                             <span>{lead.dnqReason}</span>
                           </li>
                        )}
                      </ul>
                    </div>
                  </div>
               </div>
            ) : (
              <div className="space-y-8">
                 {lead.researchBrief ? (
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <BriefSection title="Personal Profile" content={lead.researchBrief.personalProfile} icon={<User size={16}/>} />
                      <BriefSection title="Employer Insights" content={lead.researchBrief.employer} icon={<Inbox size={16}/>} />
                      <BriefSection title="Immigration Analysis" content={lead.researchBrief.immigrationAnalysis} icon={<ShieldAlert size={16}/>} />
                      <BriefSection title="Consultant Tips" content={lead.researchBrief.consultantTips} icon={<AlertTriangle size={16}/>} accent />
                   </div>
                 ) : (
                    <div className="py-20 flex flex-col items-center justify-center text-center space-y-4">
                       <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-slate-400">
                          <Search size={32} />
                       </div>
                       <div>
                          <p className="font-bold text-slate-700">No Research Brief Found</p>
                          <p className="text-sm text-slate-500 max-w-xs mx-auto mt-1">Deep research is generated asynchronously for high-value Gold leads.</p>
                       </div>
                       <button 
                         onClick={handleResearch} 
                         disabled={researching}
                         className="px-6 py-2 bg-slate-900 text-white rounded-full text-sm font-bold hover:bg-slate-800 transition-all flex items-center gap-2"
                       >
                         {researching ? <Loader2 className="animate-spin" /> : <Plus size={16} />}
                         Generate Deep Research
                       </button>
                    </div>
                 )}
              </div>
            )}
          </div>
        </div>

        {/* Draft Section */}
        <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
           <div className="flex items-center justify-between mb-6">
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
              <div className="space-y-2">
                 <div className="flex items-center justify-between">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                       <MessageSquare size={12} /> Email Prototype
                    </p>
                    <button className="text-[10px] text-orange-600 font-bold hover:underline">COPY TO CLIPBOARD</button>
                 </div>
                 <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {lead.emailDraft || "Drafting in progress..."}
                 </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                 <div className="space-y-2">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                       <Phone size={12} /> Phone Script
                    </p>
                    <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-xs text-slate-700 italic border-l-4">
                       {lead.phoneScript || "Follow standard opening protocol."}
                    </div>
                 </div>
                 <div className="space-y-2">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-1">
                       <Plus size={12} /> WhatsApp Script
                    </p>
                    <div className="p-4 bg-green-50 border border-green-200 rounded-xl text-xs text-slate-700 font-mono">
                       {lead.whatsappDraft || "No WhatsApp drafted."}
                    </div>
                 </div>
              </div>
           </div>
        </div>
      </div>

      {/* Right Col: Priority Actions & Logs */}
      <div className="space-y-8">
        {/* 60s Call Box */}
        {(lead.rating === LeadRating.GD || lead.rating === LeadRating.MF) && lead.status === LeadStatus.PENDING && (
           <motion.div 
             initial={{ scale: 0.9, opacity: 0 }}
             animate={{ scale: 1, opacity: 1 }}
             className="bg-red-600 rounded-2xl p-6 text-white shadow-xl shadow-red-200 relative overflow-hidden"
           >
              <div className="absolute -right-4 -top-4 w-32 h-32 bg-white/10 rounded-full blur-2xl" />
              <div className="relative z-10">
                 <div className="flex items-center gap-2 mb-4">
                    <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center animate-pulse">
                       <Clock size={14} />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-widest">60-Second Call Protocol</span>
                 </div>
                 <h3 className="text-xl font-bold mb-2">Immediate Contact Required</h3>
                 <p className="text-sm opacity-80 mb-6 leading-snug">Gold-level leads lose value significantly after 5 minutes of non-response.</p>
                 
                 <div className="space-y-3">
                    <a 
                      href={`tel:${lead.phone}`}
                      onClick={() => onUpdateStatus(lead.id, LeadStatus.CONTACTED)}
                      className="w-full py-3 bg-white text-red-600 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg"
                    >
                       <Phone size={18} />
                       CALL NOW
                    </a>
                    <button 
                      onClick={() => onUpdateStatus(lead.id, LeadStatus.CONTACTED)}
                      className="w-full py-3 bg-red-700 hover:bg-red-800 text-white rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-colors border border-red-500/50"
                    >
                       <MessageSquare size={16} />
                       SEND WHATSAPP FIRST
                    </button>
                 </div>
              </div>
           </motion.div>
        )}

        {/* Workflow Actions */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
           <DetailLabel label="WORKFLOW ACTIONS" />
           <div className="space-y-2">
              <WorkflowButton 
                onClick={() => onUpdateStatus(lead.id, LeadStatus.REVIEWING)} 
                icon={<CheckCircle2 size={16} />} 
                label="Approve & Send Drafts" 
                primary 
              />
              <WorkflowButton 
                onClick={() => {}} 
                icon={<FileEdit size={16} />} 
                label="Edit Drafts" 
              />
              <WorkflowButton 
                onClick={() => onUpdateStatus(lead.id, LeadStatus.ARCHIVED)} 
                icon={<X size={16} />} 
                label="Archive Lead" 
              />
           </div>

           {lead.rating === LeadRating.BD && (
             <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
                <div className="flex items-center gap-2 text-red-700 font-bold text-xs mb-1">
                   <ShieldAlert size={14} />
                   MARISA APPROVAL REQUIRED
                </div>
                <p className="text-[10px] text-red-600 leading-tight">Rejection drafts for BD/DNQ leads must be audited by Quality Assurance before sending.</p>
                <button className="mt-3 w-full py-2 bg-red-600 text-white rounded-lg text-xs font-bold shadow-sm">SEND TO MARISA</button>
             </div>
           )}
        </div>

        {/* Audit Log */}
        <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 shadow-sm">
           <DetailLabel label="ACTIVITY AUDIT" />
           <div className="mt-4 space-y-4">
              <AuditStep time="09:23" icon={<Inbox size={12} />} text="Lead ingested from XP brand." />
              <AuditStep time="09:23" icon={<BarChart3 size={12} />} text="AI Triage complete: Scored GD." />
              <AuditStep time="09:24" icon={<Phone size={12} />} text="60s Call Protocol activated." />
           </div>
        </div>
      </div>
    </motion.div>
  );
};

const LeadEntryView = ({ onSubmit }: { onSubmit: (data: any) => void }) => {
  const [formData, setFormData] = useState({ name: '', email: '', visaType: VISA_TYPES[0], brand: INBOX_BRANDS[0] });

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-2xl mx-auto bg-white border border-slate-200 rounded-3xl p-10 shadow-xl shadow-slate-100"
    >
      <div className="mb-10 text-center">
         <div className="w-16 h-16 bg-orange-100 text-orange-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Plus size={32} />
         </div>
         <h3 className="text-2xl font-bold tracking-tight">Manual Lead Insertion</h3>
         <p className="text-sm text-slate-500 mt-1">AI Triage will process the lead immediately upon submission.</p>
      </div>

      <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); onSubmit(formData); }}>
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Full Name</label>
            <input 
              required
              type="text" 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
              placeholder="e.g. John Smith"
              value={formData.name}
              onChange={e => setFormData({...formData, name: e.target.value})}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Email Address</label>
            <input 
              required
              type="email" 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
              placeholder="e.g. john@corp.com"
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Visa Path</label>
            <select 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all"
              value={formData.visaType}
              onChange={e => setFormData({...formData, visaType: e.target.value})}
            >
              {VISA_TYPES.map(v => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Inbox Brand</label>
            <div className="flex gap-2">
              {INBOX_BRANDS.map(brand => (
                <button
                  key={brand}
                  type="button"
                  onClick={() => setFormData({...formData, brand})}
                  className={cn(
                    "flex-1 py-3 rounded-xl border font-bold text-xs transition-all",
                    formData.brand === brand ? "bg-orange-600 border-orange-600 text-white shadow-md shadow-orange-100" : "bg-white border-slate-200 text-slate-500 hover:bg-slate-50"
                  )}
                >
                  {brand}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="pt-6">
          <button 
            type="submit"
            className="w-full py-4 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl font-bold tracking-tight transition-all shadow-xl shadow-slate-200 flex items-center justify-center gap-2"
          >
            PROCESS LEAD THROUGH AI
            <ChevronRight size={18} />
          </button>
        </div>
      </form>
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

const WorkflowButton = ({ icon, label, onClick, primary }: any) => (
  <button 
    onClick={onClick}
    className={cn(
      "w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center gap-3 transition-all",
      primary ? "bg-slate-900 text-white hover:bg-slate-800 shadow-md shadow-slate-200" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
    )}
  >
    {icon}
    <span>{label}</span>
  </button>
);

const AuditStep = ({ time, icon, text }: any) => (
  <div className="flex gap-3">
     <div className="flex flex-col items-center gap-1 shrink-0">
        <div className="w-6 h-6 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-400">
           {icon}
        </div>
        <div className="w-px flex-1 bg-slate-200" />
     </div>
     <div className="pb-4">
        <p className="text-[10px] font-bold text-slate-400 leading-tight mb-1">{time} AM</p>
        <p className="text-xs text-slate-600 leading-snug">{text}</p>
     </div>
  </div>
);
