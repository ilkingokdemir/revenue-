import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Wrench, CheckCircle, Clock, X, Eye, Plus, ArrowsClockwise, WarningCircle, Camera,
  ChatText, Timer, CurrencyDollar, CalendarBlank, Repeat, Lightning, Funnel,
} from "@phosphor-icons/react";
import { AlertTriangle, LayoutGrid, List, Send, ChevronRight, Upload, Trash2, MessageSquare } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PRIORITY_CONFIG = {
  critical: { label: "Critical", color: "bg-red-600 text-white", ring: "ring-red-400", sla: "2h" },
  high: { label: "High", color: "bg-orange-500 text-white", ring: "ring-orange-300", sla: "8h" },
  medium: { label: "Medium", color: "bg-amber-100 text-amber-800", ring: "ring-amber-200", sla: "24h" },
  low: { label: "Low", color: "bg-stone-100 text-stone-600", ring: "ring-stone-200", sla: "72h" },
};

const STATUS_CONFIG = {
  open: { label: "Open", color: "bg-red-50 text-red-700 border-red-200" },
  acknowledged: { label: "Acknowledged", color: "bg-blue-50 text-blue-700 border-blue-200" },
  in_progress: { label: "In Progress", color: "bg-amber-50 text-amber-700 border-amber-200" },
  resolved: { label: "Resolved", color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  closed: { label: "Closed", color: "bg-stone-100 text-stone-500 border-stone-200" },
};

const CATEGORY_CONFIG = {
  plumbing: { label: "Plumbing", icon: "🔧" },
  electrical: { label: "Electrical", icon: "⚡" },
  hvac: { label: "HVAC / AC", icon: "❄️" },
  furniture: { label: "Furniture", icon: "🪑" },
  appliance: { label: "Appliance", icon: "🔌" },
  structural: { label: "Structural", icon: "🏗️" },
  cleaning: { label: "Cleaning", icon: "🧹" },
  pest_control: { label: "Pest Control", icon: "🐛" },
  safety: { label: "Safety", icon: "🛡️" },
  it_network: { label: "IT / Network", icon: "📡" },
  general: { label: "General", icon: "🔨" },
};

const KANBAN_COLUMNS = [
  { id: "open", label: "Open", statuses: ["open"] },
  { id: "working", label: "In Progress", statuses: ["acknowledged", "in_progress"] },
  { id: "done", label: "Resolved", statuses: ["resolved", "closed"] },
];

export function MaintenancePanel({ properties, activePropertyId: propActivePropertyId }) {
  const activePropertyId = propActivePropertyId || "all";
  const [issues, setIssues] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("kanban"); // kanban, table
  const [tab, setTab] = useState("issues"); // issues, recurring, analytics
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showRecurring, setShowRecurring] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [filterCategory, setFilterCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [recurring, setRecurring] = useState([]);
  const [assignees, setAssignees] = useState([]);

  const fetchData = useCallback(async () => {
    if (!activePropertyId) return;
    try {
      const [issuesRes, statsRes, assigneesRes] = await Promise.all([
        axios.get(`${API}/maintenance/issues/${activePropertyId}`),
        axios.get(`${API}/maintenance/stats/${activePropertyId}`),
        axios.get(`${API}/maintenance/assignees/${activePropertyId}`),
      ]);
      setIssues(issuesRes.data);
      setStats(statsRes.data);
      setAssignees(assigneesRes.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [activePropertyId]);

  const fetchRecurring = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/maintenance/recurring/${activePropertyId}`);
      setRecurring(data);
    } catch { }
  }, [activePropertyId]);

  useEffect(() => { fetchData(); fetchRecurring(); }, [fetchData, fetchRecurring]);

  const filtered = issues.filter(i => {
    if (filterStatus !== "all" && i.status !== filterStatus) return false;
    if (filterPriority !== "all" && i.priority !== filterPriority) return false;
    if (filterCategory !== "all" && i.category !== filterCategory) return false;
    if (search && !i.title?.toLowerCase().includes(search.toLowerCase()) && !i.location?.toLowerCase().includes(search.toLowerCase()) && !i.room_number?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const updateStatus = async (issue, newStatus) => {
    try {
      await axios.put(`${API}/maintenance/issues/${issue.id}`, { status: newStatus });
      toast.success(`Status updated to ${newStatus}`);
      fetchData();
    } catch { toast.error("Failed to update"); }
  };

  return (
    <div className="p-6 space-y-5" data-testid="maintenance-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-800" data-testid="maintenance-title">Maintenance</h1>
          <p className="text-sm text-stone-500 mt-0.5">Issues, SLA tracking, costs & preventive maintenance</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { axios.post(`${API}/maintenance/check-sla/${activePropertyId}`).then(() => { toast.success("SLA check complete"); fetchData(); }); }} className="px-3 py-2 text-xs font-medium text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50 transition flex items-center gap-1.5" data-testid="btn-check-sla">
            <Timer size={14} /> Check SLA
          </button>
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-orange-500 text-white text-sm font-semibold rounded-lg hover:bg-orange-600 transition flex items-center gap-1.5" data-testid="btn-new-issue">
            <Plus size={14} weight="bold" /> Report Issue
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3" data-testid="maintenance-stats">
        {[
          { label: "Open", value: stats.open || 0, color: "bg-red-50 text-red-700", icon: <WarningCircle size={16} className="text-red-500" weight="fill" /> },
          { label: "In Progress", value: stats.in_progress || 0, color: "bg-amber-50 text-amber-700", icon: <Wrench size={16} className="text-amber-500" weight="fill" /> },
          { label: "Resolved", value: stats.resolved || 0, color: "bg-emerald-50 text-emerald-700", icon: <CheckCircle size={16} className="text-emerald-500" weight="fill" /> },
          { label: "Overdue (SLA)", value: stats.overdue || 0, color: stats.overdue > 0 ? "bg-red-100 text-red-800" : "bg-stone-50 text-stone-600", icon: <Timer size={16} className={stats.overdue > 0 ? "text-red-600" : "text-stone-400"} weight="fill" /> },
          { label: "Total Cost", value: `£${(stats.costs?.total_actual || 0).toLocaleString()}`, color: "bg-blue-50 text-blue-700", icon: <CurrencyDollar size={16} className="text-blue-500" weight="fill" /> },
        ].map((s, i) => (
          <div key={i} className={`${s.color} rounded-xl p-3.5 flex items-center gap-2.5`} data-testid={`stat-${s.label.toLowerCase().replace(/ /g, "-")}`}>
            {s.icon}
            <div>
              <p className="text-xl font-bold">{s.value}</p>
              <p className="text-[10px] font-medium opacity-70">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs + View Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-stone-100 p-1 rounded-lg" data-testid="maint-tabs">
          {[
            { id: "issues", label: "Issues", icon: <Wrench size={13} /> },
            { id: "team", label: "Team", icon: <Lightning size={13} /> },
            { id: "vendors", label: "Vendors", icon: <Lightning size={13} /> },
            { id: "recurring", label: "Preventive", icon: <Repeat size={13} /> },
            { id: "analytics", label: "Analytics", icon: <Lightning size={13} /> },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-1.5 text-xs font-medium rounded-md flex items-center gap-1.5 transition ${tab === t.id ? "bg-white shadow-sm text-stone-800" : "text-stone-500"}`} data-testid={`maint-tab-${t.id}`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
        {tab === "issues" && (
          <div className="flex gap-1 bg-stone-100 p-0.5 rounded-lg">
            <button onClick={() => setView("kanban")} className={`p-1.5 rounded-md transition ${view === "kanban" ? "bg-white shadow-sm" : ""}`} data-testid="view-kanban"><LayoutGrid size={14} className="text-stone-600" /></button>
            <button onClick={() => setView("table")} className={`p-1.5 rounded-md transition ${view === "table" ? "bg-white shadow-sm" : ""}`} data-testid="view-table"><List size={14} className="text-stone-600" /></button>
          </div>
        )}
      </div>

      {tab === "issues" && (
        <>
          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap" data-testid="maint-filters">
            <Input data-testid="maint-search" placeholder="Search issues..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-[200px] h-8 text-xs" />
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                {Object.entries(STATUS_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="w-28 h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priority</SelectItem>
                {Object.entries(PRIORITY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Category</SelectItem>
                {Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <button onClick={fetchData} className="p-1.5 text-stone-400 hover:text-stone-600"><ArrowsClockwise size={14} /></button>
          </div>

          {/* Kanban View */}
          {view === "kanban" && (
            <div className="grid grid-cols-3 gap-4" data-testid="kanban-board">
              {KANBAN_COLUMNS.map(col => {
                const colIssues = filtered.filter(i => col.statuses.includes(i.status));
                return (
                  <div key={col.id} className="bg-stone-50 rounded-xl p-3" data-testid={`kanban-col-${col.id}`}>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-bold text-stone-600 uppercase tracking-wide">{col.label}</h3>
                      <span className="text-[10px] font-bold text-stone-400 bg-stone-200 px-1.5 py-0.5 rounded-full">{colIssues.length}</span>
                    </div>
                    <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                      {colIssues.map(issue => (
                        <IssueCard key={issue.id} issue={issue} onClick={() => setSelectedIssue(issue)} onStatusChange={updateStatus} />
                      ))}
                      {colIssues.length === 0 && <p className="text-xs text-stone-400 text-center py-6">No issues</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Table View */}
          {view === "table" && (
            <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden" data-testid="issues-table">
              <div className="grid grid-cols-[1fr_90px_90px_120px_100px_80px_80px_80px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
                <span>Issue</span><span>Priority</span><span>Category</span><span>Location</span><span>Status</span><span>SLA</span><span>Cost</span><span>Actions</span>
              </div>
              <ScrollArea className="max-h-[45vh]">
                {filtered.length === 0 ? (
                  <div className="p-8 text-center text-stone-400 text-sm">No issues found</div>
                ) : filtered.map(issue => (
                  <div key={issue.id} className="grid grid-cols-[1fr_90px_90px_120px_100px_80px_80px_80px] gap-2 px-4 py-2.5 border-b border-stone-100 items-center hover:bg-stone-50/50 cursor-pointer" onClick={() => setSelectedIssue(issue)} data-testid={`issue-row-${issue.id}`}>
                    <div>
                      <p className="text-sm font-medium text-stone-800 truncate">{issue.title || "Untitled"}</p>
                      <p className="text-[10px] text-stone-400 truncate">{issue.description?.slice(0, 50)}</p>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-fit ${PRIORITY_CONFIG[issue.priority]?.color || "bg-stone-100"}`}>{PRIORITY_CONFIG[issue.priority]?.label || issue.priority}</span>
                    <span className="text-[10px] text-stone-600">{CATEGORY_CONFIG[issue.category]?.icon} {CATEGORY_CONFIG[issue.category]?.label || issue.category}</span>
                    <span className="text-xs text-stone-600 truncate">{issue.location || issue.room_number || "—"}</span>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border w-fit ${STATUS_CONFIG[issue.status]?.color || ""}`}>{STATUS_CONFIG[issue.status]?.label || issue.status}</span>
                    <span className={`text-[10px] font-medium ${issue.sla_breached ? "text-red-600 font-bold" : "text-stone-500"}`}>{issue.sla_breached ? "OVERDUE" : `${issue.sla_hours || 24}h`}</span>
                    <span className="text-xs text-stone-600">£{issue.actual_cost || 0}</span>
                    <button onClick={(e) => { e.stopPropagation(); setSelectedIssue(issue); }} className="p-1 text-stone-400 hover:text-stone-600"><Eye size={14} /></button>
                  </div>
                ))}
              </ScrollArea>
            </div>
          )}
        </>
      )}

      {/* Team Tab */}
      {tab === "team" && (
        <TeamTab propertyId={activePropertyId} onRefresh={fetchData} />
      )}

      {/* Vendors Tab */}
      {tab === "vendors" && (
        <VendorsTab propertyId={activePropertyId} onRefresh={fetchData} />
      )}

      {/* Recurring / Preventive Tab */}
      {tab === "recurring" && (
        <RecurringTab recurring={recurring} propertyId={activePropertyId} onRefresh={() => { fetchRecurring(); fetchData(); }} />
      )}

      {/* Analytics Tab */}
      {tab === "analytics" && (
        <AnalyticsTab stats={stats} issues={issues} />
      )}

      {/* Create Issue Dialog */}
      <CreateIssueDialog open={showCreate} onClose={() => setShowCreate(false)} propertyId={activePropertyId} assignees={assignees} onCreated={() => { setShowCreate(false); fetchData(); }} />

      {/* Issue Detail Drawer */}
      <IssueDetailDrawer issue={selectedIssue} onClose={() => setSelectedIssue(null)} assignees={assignees} onUpdate={() => { fetchData(); }} />
    </div>
  );
}

/* ==================== ISSUE CARD (Kanban) ==================== */
function IssueCard({ issue, onClick, onStatusChange }) {
  const pri = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
  const nextStatus = issue.status === "open" ? "acknowledged" : issue.status === "acknowledged" ? "in_progress" : issue.status === "in_progress" ? "resolved" : null;

  return (
    <div className="bg-white rounded-lg border border-stone-200/80 p-3 hover:shadow-sm transition cursor-pointer" onClick={onClick} data-testid={`kanban-card-${issue.id}`}>
      <div className="flex items-start justify-between mb-1.5">
        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${pri.color}`}>{pri.label}</span>
        {issue.sla_breached && <span className="text-[9px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">SLA BREACH</span>}
      </div>
      <p className="text-sm font-semibold text-stone-800 mb-0.5 line-clamp-1">{issue.title || "Untitled"}</p>
      <p className="text-[10px] text-stone-400 mb-2 line-clamp-2">{issue.description?.slice(0, 80)}</p>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-stone-500">
          <span>{CATEGORY_CONFIG[issue.category]?.icon || "🔨"}</span>
          <span>{issue.location || issue.room_number || "—"}</span>
          {issue.photos?.length > 0 && <span className="flex items-center gap-0.5"><Camera size={10} /> {issue.photos.length}</span>}
          {issue.comments?.length > 0 && <span className="flex items-center gap-0.5"><ChatText size={10} /> {issue.comments.length}</span>}
        </div>
        {nextStatus && (
          <button onClick={(e) => { e.stopPropagation(); onStatusChange(issue, nextStatus); }} className="text-[9px] px-2 py-1 bg-orange-500 text-white rounded font-bold hover:bg-orange-600 transition" data-testid={`btn-advance-${issue.id}`}>
            {nextStatus === "acknowledged" ? "Ack" : nextStatus === "in_progress" ? "Start" : "Resolve"}
          </button>
        )}
      </div>
    </div>
  );
}

/* ==================== CREATE ISSUE DIALOG ==================== */
function CreateIssueDialog({ open, onClose, propertyId, assignees = [], onCreated }) {
  const [form, setForm] = useState({ title: "", description: "", category: "general", priority: "medium", location: "", room_number: "", assigned_to: "" });
  const [creating, setCreating] = useState(false);
  const [photos, setPhotos] = useState([]);
  const fileRef = useRef(null);

  const handlePhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setPhotos(prev => [...prev, { file, preview: ev.target.result, name: file.name }]);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const create = async () => {
    if (!form.title) { toast.error("Title is required"); return; }
    setCreating(true);
    try {
      const { data } = await axios.post(`${API}/maintenance/issues`, { ...form, property_id: propertyId });
      // Upload photos
      for (const p of photos) {
        const fd = new FormData();
        fd.append("file", p.file);
        await axios.post(`${API}/maintenance/upload-photo/${data.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      toast.success("Issue reported!"); setForm({ title: "", description: "", category: "general", priority: "medium", location: "", room_number: "", assigned_to: "" }); setPhotos([]); onCreated();
    } catch { toast.error("Failed to create"); }
    setCreating(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="create-issue-dialog">
        <DialogHeader><DialogTitle>Report Maintenance Issue</DialogTitle></DialogHeader>
        <div className="space-y-3 max-h-[60vh] overflow-y-auto">
          <Input data-testid="issue-title" value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} placeholder="Issue title *" />
          <div className="grid grid-cols-2 gap-3">
            <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-category"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.icon} {v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={form.priority} onValueChange={v => setForm(p => ({ ...p, priority: v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-priority"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(PRIORITY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.label} (SLA: {v.sla})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input data-testid="issue-location" value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} placeholder="Location (e.g. Lobby)" />
            <Input data-testid="issue-room" value={form.room_number} onChange={e => setForm(p => ({ ...p, room_number: e.target.value }))} placeholder="Room number" />
          </div>
          <Select value={form.assigned_to || "_unassigned"} onValueChange={v => setForm(p => ({ ...p, assigned_to: v === "_unassigned" ? "" : v }))}>
            <SelectTrigger className="h-9 text-sm" data-testid="issue-assignee"><SelectValue placeholder="Assign to..." /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_unassigned">Unassigned</SelectItem>
              {assignees.filter(a => a.type === "internal").length > 0 && <div className="px-2 py-1 text-[9px] font-bold text-stone-400 uppercase">Internal Team</div>}
              {assignees.filter(a => a.type === "internal").map(a => (
                <SelectItem key={a.name} value={a.name}>{a.name} ({a.open_issues} open)</SelectItem>
              ))}
              {assignees.filter(a => a.type === "external").length > 0 && <div className="px-2 py-1 text-[9px] font-bold text-stone-400 uppercase">External Vendors</div>}
              {assignees.filter(a => a.type === "external").map(a => (
                <SelectItem key={a.name} value={a.name}>{a.name} — £{a.hourly_rate}/h ({a.open_issues} open)</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Textarea data-testid="issue-description" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Describe the issue in detail..." rows={3} />

          {/* Photo Upload */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">Photos</label>
            <div className="flex gap-2 flex-wrap">
              {photos.map((p, i) => (
                <div key={i} className="w-16 h-16 rounded-lg border border-stone-200 overflow-hidden relative group">
                  <img src={p.preview} alt="" className="w-full h-full object-cover" />
                  <button onClick={() => setPhotos(prev => prev.filter((_, idx) => idx !== i))} className="absolute top-0 right-0 bg-red-500 text-white p-0.5 rounded-bl opacity-0 group-hover:opacity-100 transition"><X size={10} /></button>
                </div>
              ))}
              <button onClick={() => fileRef.current?.click()} className="w-16 h-16 rounded-lg border-2 border-dashed border-stone-300 flex items-center justify-center text-stone-400 hover:border-orange-400 hover:text-orange-500 transition" data-testid="btn-add-photo">
                <Camera size={20} />
              </button>
              <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={handlePhoto} className="hidden" />
            </div>
          </div>

          <button onClick={create} disabled={creating} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-600 disabled:opacity-50 transition" data-testid="btn-submit-issue">
            {creating ? "Submitting..." : "Submit Issue"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ==================== ISSUE DETAIL DRAWER ==================== */
function IssueDetailDrawer({ issue, onClose, assignees = [], onUpdate }) {
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [costForm, setCostForm] = useState({ estimated_cost: 0, actual_cost: 0, cost_notes: "" });
  const [showCost, setShowCost] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    if (issue) setCostForm({ estimated_cost: issue.estimated_cost || 0, actual_cost: issue.actual_cost || 0, cost_notes: issue.cost_notes || "" });
  }, [issue]);

  if (!issue) return null;

  const addComment = async () => {
    if (!comment.trim()) return;
    setSending(true);
    try {
      await axios.post(`${API}/maintenance/issues/${issue.id}/comment`, { text: comment });
      setComment(""); toast.success("Comment added"); onUpdate();
    } catch { toast.error("Failed"); }
    setSending(false);
  };

  const uploadPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await axios.post(`${API}/maintenance/upload-photo/${issue.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Photo uploaded"); onUpdate();
    } catch { toast.error("Upload failed"); }
    e.target.value = "";
  };

  const saveCost = async () => {
    try {
      await axios.put(`${API}/maintenance/issues/${issue.id}/cost`, costForm);
      toast.success("Cost saved"); setShowCost(false); onUpdate();
    } catch { toast.error("Failed"); }
  };

  const updateStatus = async (s) => {
    try {
      await axios.put(`${API}/maintenance/issues/${issue.id}`, { status: s });
      toast.success(`Status: ${s}`); onUpdate();
    } catch { toast.error("Failed"); }
  };

  const pri = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
  const sta = STATUS_CONFIG[issue.status] || {};

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/40 flex items-center justify-end z-50" onClick={onClose}>
        <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }} className="bg-white h-full w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()} data-testid="issue-detail-drawer">
          <div className="p-4 border-b border-stone-100 flex items-center justify-between">
            <h3 className="font-semibold text-stone-800 text-sm truncate pr-4">{issue.title || "Issue Detail"}</h3>
            <button onClick={onClose} className="p-1.5 hover:bg-stone-100 rounded-lg"><X size={16} className="text-stone-400" /></button>
          </div>
          <ScrollArea className="h-[calc(100vh-56px)]">
            <div className="p-4 space-y-4">
              {/* Status + Priority */}
              <div className="flex gap-2 flex-wrap">
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${pri.color}`}>{pri.label}</span>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${sta.color}`}>{sta.label}</span>
                {issue.sla_breached && <span className="text-xs font-bold text-red-600 bg-red-50 px-2.5 py-1 rounded-full">SLA BREACHED</span>}
              </div>

              {/* Quick Status Actions */}
              <div className="flex gap-1.5 flex-wrap">
                {["open", "acknowledged", "in_progress", "resolved", "closed"].filter(s => s !== issue.status).map(s => (
                  <button key={s} onClick={() => updateStatus(s)} className="text-[10px] px-2.5 py-1 border border-stone-200 rounded-lg hover:bg-stone-50 text-stone-600 font-medium transition" data-testid={`btn-status-${s}`}>
                    {STATUS_CONFIG[s]?.label}
                  </button>
                ))}
              </div>

              {/* Info */}
              <div className="bg-stone-50 rounded-xl p-3 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-stone-500">Category</span><span className="font-medium">{CATEGORY_CONFIG[issue.category]?.icon} {CATEGORY_CONFIG[issue.category]?.label}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Location</span><span className="font-medium">{issue.location || issue.room_number || "—"}</span></div>
                <div className="flex justify-between items-center"><span className="text-stone-500">Assigned</span>
                  <Select value={issue.assigned_to || "_unassigned"} onValueChange={async (v) => {
                    try { await axios.put(`${API}/maintenance/issues/${issue.id}`, { assigned_to: v === "_unassigned" ? "" : v }); toast.success("Reassigned"); onUpdate(); } catch {}
                  }}>
                    <SelectTrigger className="h-7 w-40 text-xs border-stone-200" data-testid="reassign-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_unassigned">Unassigned</SelectItem>
                      {assignees.filter(a => a.type === "internal").map(a => <SelectItem key={a.name} value={a.name}>{a.name}</SelectItem>)}
                      {assignees.filter(a => a.type === "external").map(a => <SelectItem key={a.name} value={a.name}>{a.name} (vendor)</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex justify-between"><span className="text-stone-500">Reported by</span><span className="font-medium">{issue.reported_by || "—"}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">SLA Target</span><span className="font-medium">{issue.sla_hours}h</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Created</span><span className="font-medium text-xs">{issue.created_at ? new Date(issue.created_at).toLocaleString() : "—"}</span></div>
                {issue.resolved_at && <div className="flex justify-between"><span className="text-stone-500">Resolved</span><span className="font-medium text-xs">{new Date(issue.resolved_at).toLocaleString()}</span></div>}
              </div>

              {/* Description */}
              {issue.description && (
                <div><h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">Description</h4><p className="text-sm text-stone-700 bg-stone-50 rounded-xl p-3">{issue.description}</p></div>
              )}

              {/* Photos */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Photos ({issue.photos?.length || 0})</h4>
                  <button onClick={() => fileRef.current?.click()} className="text-[10px] text-orange-600 font-medium hover:underline" data-testid="btn-drawer-upload-photo">+ Add Photo</button>
                  <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={uploadPhoto} className="hidden" />
                </div>
                {issue.photos?.length > 0 ? (
                  <div className="flex gap-2 flex-wrap">
                    {issue.photos.map((p, i) => (
                      <img key={i} src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt="" className="w-20 h-20 rounded-lg object-cover border border-stone-200" />
                    ))}
                  </div>
                ) : <p className="text-xs text-stone-400">No photos attached</p>}
              </div>

              {/* Cost Tracking */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Cost Tracking</h4>
                  <button onClick={() => setShowCost(!showCost)} className="text-[10px] text-orange-600 font-medium hover:underline">{showCost ? "Cancel" : "Edit Costs"}</button>
                </div>
                {showCost ? (
                  <div className="bg-stone-50 rounded-xl p-3 space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div><label className="text-[10px] text-stone-500">Estimated (£)</label><Input type="number" value={costForm.estimated_cost} onChange={e => setCostForm(p => ({ ...p, estimated_cost: Number(e.target.value) }))} className="h-8 text-sm" /></div>
                      <div><label className="text-[10px] text-stone-500">Actual (£)</label><Input type="number" value={costForm.actual_cost} onChange={e => setCostForm(p => ({ ...p, actual_cost: Number(e.target.value) }))} className="h-8 text-sm" /></div>
                    </div>
                    <Input value={costForm.cost_notes} onChange={e => setCostForm(p => ({ ...p, cost_notes: e.target.value }))} placeholder="Cost notes (parts, labour...)" className="h-8 text-sm" />
                    <button onClick={saveCost} className="text-xs px-3 py-1.5 bg-orange-500 text-white rounded-lg font-medium">Save Costs</button>
                  </div>
                ) : (
                  <div className="bg-stone-50 rounded-xl p-3 flex gap-4 text-sm">
                    <div><span className="text-stone-500">Est:</span> <span className="font-medium">£{issue.estimated_cost || 0}</span></div>
                    <div><span className="text-stone-500">Actual:</span> <span className="font-medium">£{issue.actual_cost || 0}</span></div>
                    {issue.cost_notes && <div className="text-xs text-stone-500">{issue.cost_notes}</div>}
                  </div>
                )}
              </div>

              {/* Comments / Activity Log */}
              <div>
                <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">Activity ({issue.comments?.length || 0})</h4>
                <div className="space-y-2 mb-3 max-h-40 overflow-y-auto">
                  {(issue.comments || []).map(c => (
                    <div key={c.id} className="bg-stone-50 rounded-lg p-2.5">
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs font-semibold text-stone-700">{c.author}</span>
                        <span className="text-[10px] text-stone-400">{c.created_at ? new Date(c.created_at).toLocaleString() : ""}</span>
                      </div>
                      <p className="text-xs text-stone-600">{c.text}</p>
                    </div>
                  ))}
                  {(!issue.comments || issue.comments.length === 0) && <p className="text-xs text-stone-400">No comments yet</p>}
                </div>
                <div className="flex gap-2">
                  <Input data-testid="comment-input" value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addComment()} placeholder="Add a comment..." className="h-8 text-xs flex-1" />
                  <button onClick={addComment} disabled={sending} className="px-3 py-1.5 bg-[#1e3a5f] text-white text-xs font-medium rounded-lg hover:bg-[#15304f] disabled:opacity-50" data-testid="btn-add-comment">
                    <Send size={12} />
                  </button>
                </div>
              </div>
            </div>
          </ScrollArea>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* ==================== RECURRING TAB ==================== */
function RecurringTab({ recurring, propertyId, onRefresh }) {
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", category: "general", priority: "medium", frequency: "monthly", location: "", assigned_to: "" });

  const create = async () => {
    if (!form.title) return;
    try {
      await axios.post(`${API}/maintenance/recurring`, { ...form, property_id: propertyId });
      toast.success("Recurring schedule created"); setShowNew(false);
      setForm({ title: "", description: "", category: "general", priority: "medium", frequency: "monthly", location: "", assigned_to: "" });
      onRefresh();
    } catch { toast.error("Failed"); }
  };

  const generate = async () => {
    try {
      const { data } = await axios.post(`${API}/maintenance/recurring/generate/${propertyId}`);
      toast.success(`Generated ${data.generated} tasks from ${data.schedules_checked} schedules`);
      onRefresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-4" data-testid="recurring-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">Schedule preventive maintenance tasks that auto-generate on a recurring basis</p>
        <div className="flex gap-2">
          <button onClick={generate} className="px-3 py-2 text-xs font-medium border border-stone-200 rounded-lg hover:bg-stone-50 flex items-center gap-1.5" data-testid="btn-generate-recurring"><Lightning size={13} /> Generate Due Tasks</button>
          <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-new-recurring"><Plus size={13} weight="bold" /> New Schedule</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
        <div className="grid grid-cols-[1fr_100px_90px_90px_100px_100px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
          <span>Task</span><span>Category</span><span>Priority</span><span>Frequency</span><span>Next Due</span><span>Status</span>
        </div>
        {recurring.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">No recurring schedules. Create one to automate preventive maintenance.</div>
        ) : recurring.map(r => (
          <div key={r.id} className="grid grid-cols-[1fr_100px_90px_90px_100px_100px] gap-2 px-4 py-3 border-b border-stone-100 items-center" data-testid={`recurring-${r.id}`}>
            <div>
              <p className="text-sm font-medium text-stone-800">{r.title}</p>
              <p className="text-[10px] text-stone-400">{r.location || "All areas"} · {r.assigned_to || "Unassigned"}</p>
            </div>
            <span className="text-xs text-stone-600">{CATEGORY_CONFIG[r.category]?.icon} {CATEGORY_CONFIG[r.category]?.label}</span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-fit ${PRIORITY_CONFIG[r.priority]?.color}`}>{PRIORITY_CONFIG[r.priority]?.label}</span>
            <span className="text-xs text-stone-600 capitalize">{r.frequency}</span>
            <span className="text-xs text-stone-600">{r.next_due ? new Date(r.next_due).toLocaleDateString() : "—"}</span>
            <span className={`text-[10px] font-medium ${r.is_active ? "text-emerald-600" : "text-stone-400"}`}>{r.is_active ? "Active" : "Paused"}</span>
          </div>
        ))}
      </div>

      {/* New Recurring Dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-recurring-dialog">
          <DialogHeader><DialogTitle>New Recurring Schedule</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} placeholder="Task title *" data-testid="recurring-title" />
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.icon} {v.label}</SelectItem>)}</SelectContent>
              </Select>
              <Select value={form.frequency} onValueChange={v => setForm(p => ({ ...p, frequency: v }))}>
                <SelectTrigger className="h-9 text-sm" data-testid="recurring-frequency"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="quarterly">Quarterly</SelectItem>
                  <SelectItem value="yearly">Yearly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Input value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} placeholder="Location" />
            <Input value={form.assigned_to} onChange={e => setForm(p => ({ ...p, assigned_to: e.target.value }))} placeholder="Assign to" />
            <Textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Description..." rows={2} />
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-recurring">Create Schedule</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==================== ANALYTICS TAB ==================== */
function AnalyticsTab({ stats, issues }) {
  const categories = Object.entries(stats.by_category || {}).sort((a, b) => b[1] - a[1]);
  const priorities = Object.entries(stats.by_priority || {}).sort((a, b) => b[1] - a[1]);
  const maxCat = Math.max(...categories.map(c => c[1]), 1);
  const maxPri = Math.max(...priorities.map(p => p[1]), 1);

  // Avg resolution time
  const resolvedIssues = issues.filter(i => i.resolved_at && i.created_at);
  let avgResTime = 0;
  if (resolvedIssues.length > 0) {
    const totalMs = resolvedIssues.reduce((acc, i) => acc + (new Date(i.resolved_at) - new Date(i.created_at)), 0);
    avgResTime = Math.round(totalMs / resolvedIssues.length / 3600000); // hours
  }

  return (
    <div className="space-y-4" data-testid="analytics-tab">
      <div className="grid grid-cols-3 gap-4">
        {/* Summary */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Summary</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-stone-500">Total Issues</span><span className="font-bold">{stats.total || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Open</span><span className="font-bold text-red-600">{stats.open || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">In Progress</span><span className="font-bold text-amber-600">{stats.in_progress || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Resolved</span><span className="font-bold text-emerald-600">{stats.resolved || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">SLA Breaches</span><span className="font-bold text-red-600">{stats.overdue || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Avg Resolution</span><span className="font-bold">{avgResTime}h</span></div>
          </div>
        </div>

        {/* By Category */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">By Category</h4>
          <div className="space-y-2">
            {categories.map(([cat, count]) => (
              <div key={cat}>
                <div className="flex justify-between text-xs mb-0.5"><span className="text-stone-600">{CATEGORY_CONFIG[cat]?.icon} {CATEGORY_CONFIG[cat]?.label || cat}</span><span className="font-bold">{count}</span></div>
                <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden"><div className="h-full bg-orange-400 rounded-full" style={{ width: `${(count / maxCat) * 100}%` }} /></div>
              </div>
            ))}
            {categories.length === 0 && <p className="text-xs text-stone-400">No data</p>}
          </div>
        </div>

        {/* Cost Summary */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Cost Summary</h4>
          <div className="space-y-3">
            <div className="text-center">
              <p className="text-3xl font-bold text-stone-800">£{(stats.costs?.total_actual || 0).toLocaleString()}</p>
              <p className="text-xs text-stone-500 mt-0.5">Total Actual Cost</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-stone-600">£{(stats.costs?.total_estimated || 0).toLocaleString()}</p>
              <p className="text-xs text-stone-400">Estimated</p>
            </div>
            {/* By Priority */}
            <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mt-3">By Priority</h4>
            {priorities.map(([pri, count]) => (
              <div key={pri}>
                <div className="flex justify-between text-xs mb-0.5"><span className={`font-medium ${pri === "critical" ? "text-red-600" : pri === "high" ? "text-orange-600" : "text-stone-600"}`}>{PRIORITY_CONFIG[pri]?.label || pri}</span><span className="font-bold">{count}</span></div>
                <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden"><div className={`h-full rounded-full ${pri === "critical" ? "bg-red-500" : pri === "high" ? "bg-orange-500" : pri === "medium" ? "bg-amber-400" : "bg-stone-300"}`} style={{ width: `${(count / maxPri) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ==================== TEAM TAB ==================== */
function TeamTab({ propertyId, onRefresh }) {
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", role: "technician", phone: "", email: "", specialities: [] });
  const [specInput, setSpecInput] = useState("");

  useEffect(() => {
    const load = async () => {
      try { const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); } catch {}
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  const create = async () => {
    if (!form.name) return;
    try {
      await axios.post(`${API}/maintenance/team`, { ...form, property_id: propertyId });
      toast.success("Team member added");
      setShowNew(false); setForm({ name: "", role: "technician", phone: "", email: "", specialities: [] });
      const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); onRefresh();
    } catch { toast.error("Failed"); }
  };

  const toggle = async (m) => {
    await axios.put(`${API}/maintenance/team/${m.id}`, { is_active: !m.is_active });
    const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); onRefresh();
  };

  return (
    <div className="space-y-4" data-testid="team-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">Your internal maintenance team members and their current workload</p>
        <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-add-team">
          <Plus size={13} weight="bold" /> Add Member
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {team.map(m => (
          <div key={m.id} className={`bg-white rounded-xl border ${m.is_active ? "border-stone-200" : "border-stone-100 opacity-60"} p-4`} data-testid={`team-${m.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-full bg-orange-100 flex items-center justify-center text-orange-700 font-bold text-sm">{m.name?.charAt(0)}</div>
                <div>
                  <p className="text-sm font-semibold text-stone-800">{m.name}</p>
                  <p className="text-[10px] text-stone-400 capitalize">{m.role}</p>
                </div>
              </div>
              <button onClick={() => toggle(m)} className={`text-[9px] px-2 py-0.5 rounded font-medium ${m.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                {m.is_active ? "Active" : "Inactive"}
              </button>
            </div>
            {m.specialities?.length > 0 && (
              <div className="flex gap-1 flex-wrap mb-2">
                {m.specialities.map((s, i) => <span key={i} className="text-[9px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">{s}</span>)}
              </div>
            )}
            <div className="flex gap-3 text-[10px] text-stone-500">
              <span className="text-orange-600 font-bold">{m.open_issues || 0} open</span>
              <span className="text-emerald-600">{m.total_resolved || 0} resolved</span>
              {m.phone && <span>{m.phone}</span>}
            </div>
          </div>
        ))}
        {!loading && team.length === 0 && <div className="col-span-3 p-8 text-center text-stone-400 text-sm">No team members added yet</div>}
      </div>

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-team-dialog">
          <DialogHeader><DialogTitle>Add Team Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Full name *" data-testid="team-name" />
            <Select value={form.role} onValueChange={v => setForm(p => ({ ...p, role: v }))}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="technician">Technician</SelectItem>
                <SelectItem value="supervisor">Supervisor</SelectItem>
                <SelectItem value="electrician">Electrician</SelectItem>
                <SelectItem value="plumber">Plumber</SelectItem>
                <SelectItem value="handyman">Handyman</SelectItem>
                <SelectItem value="hvac_tech">HVAC Technician</SelectItem>
              </SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="Phone" />
              <Input value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Specialities</label>
              <div className="flex gap-1 flex-wrap mb-1.5">
                {form.specialities.map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-orange-50 text-orange-700 rounded-full flex items-center gap-1">
                    {s} <button onClick={() => setForm(p => ({ ...p, specialities: p.specialities.filter((_, idx) => idx !== i) }))}><X size={8} /></button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1">
                <Input value={specInput} onChange={e => setSpecInput(e.target.value)} placeholder="e.g. Plumbing" className="h-8 text-xs" onKeyDown={(e) => { if (e.key === "Enter" && specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} />
                <button onClick={() => { if (specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} className="px-2 h-8 bg-stone-100 text-stone-600 rounded text-xs">Add</button>
              </div>
            </div>
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-team">Add Member</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==================== VENDORS TAB ==================== */
function VendorsTab({ propertyId, onRefresh }) {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ company_name: "", contact_person: "", phone: "", email: "", specialities: [], hourly_rate: 0, notes: "" });
  const [specInput, setSpecInput] = useState("");

  useEffect(() => {
    const load = async () => {
      try { const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); } catch {}
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  const create = async () => {
    if (!form.company_name) return;
    try {
      await axios.post(`${API}/maintenance/vendors`, { ...form, property_id: propertyId });
      toast.success("Vendor added");
      setShowNew(false); setForm({ company_name: "", contact_person: "", phone: "", email: "", specialities: [], hourly_rate: 0, notes: "" });
      const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); onRefresh();
    } catch { toast.error("Failed"); }
  };

  const toggle = async (v) => {
    await axios.put(`${API}/maintenance/vendors/${v.id}`, { is_active: !v.is_active });
    const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); onRefresh();
  };

  return (
    <div className="space-y-4" data-testid="vendors-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">External service providers and contractors you work with</p>
        <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-add-vendor">
          <Plus size={13} weight="bold" /> Add Vendor
        </button>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
        <div className="grid grid-cols-[1fr_120px_120px_80px_80px_80px_80px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
          <span>Vendor</span><span>Contact</span><span>Specialities</span><span>Rate</span><span>Open</span><span>Resolved</span><span>Total Cost</span>
        </div>
        {vendors.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">No vendors added yet. Add external service providers to assign maintenance tasks.</div>
        ) : vendors.map(v => (
          <div key={v.id} className={`grid grid-cols-[1fr_120px_120px_80px_80px_80px_80px] gap-2 px-4 py-3 border-b border-stone-100 items-center ${!v.is_active ? "opacity-50" : ""}`} data-testid={`vendor-${v.id}`}>
            <div>
              <p className="text-sm font-semibold text-stone-800">{v.company_name}</p>
              <p className="text-[10px] text-stone-400">{v.contact_person || "—"}</p>
            </div>
            <div className="text-[10px] text-stone-500">
              {v.phone && <p>{v.phone}</p>}
              {v.email && <p className="truncate">{v.email}</p>}
            </div>
            <div className="flex gap-1 flex-wrap">
              {(v.specialities || []).map((s, i) => <span key={i} className="text-[8px] px-1 py-0.5 bg-blue-50 text-blue-700 rounded">{s}</span>)}
            </div>
            <span className="text-xs font-medium text-stone-700">£{v.hourly_rate}/h</span>
            <span className="text-xs font-bold text-orange-600">{v.open_issues || 0}</span>
            <span className="text-xs text-emerald-600">{v.total_resolved || 0}</span>
            <span className="text-xs font-medium text-stone-700">£{(v.total_cost || 0).toLocaleString()}</span>
          </div>
        ))}
      </div>

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-vendor-dialog">
          <DialogHeader><DialogTitle>Add External Vendor</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.company_name} onChange={e => setForm(p => ({ ...p, company_name: e.target.value }))} placeholder="Company name *" data-testid="vendor-name" />
            <Input value={form.contact_person} onChange={e => setForm(p => ({ ...p, contact_person: e.target.value }))} placeholder="Contact person" />
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="Phone" />
              <Input value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Hourly Rate (£)</label>
                <Input type="number" value={form.hourly_rate} onChange={e => setForm(p => ({ ...p, hourly_rate: Number(e.target.value) }))} placeholder="0" data-testid="vendor-rate" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Specialities</label>
              <div className="flex gap-1 flex-wrap mb-1.5">
                {form.specialities.map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full flex items-center gap-1">
                    {s} <button onClick={() => setForm(p => ({ ...p, specialities: p.specialities.filter((_, idx) => idx !== i) }))}><X size={8} /></button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1">
                <Input value={specInput} onChange={e => setSpecInput(e.target.value)} placeholder="e.g. Plumbing, Electrical" className="h-8 text-xs" onKeyDown={(e) => { if (e.key === "Enter" && specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} />
                <button onClick={() => { if (specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} className="px-2 h-8 bg-stone-100 text-stone-600 rounded text-xs">Add</button>
              </div>
            </div>
            <Textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Notes (contract details, availability...)" rows={2} />
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-vendor">Add Vendor</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

