import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  Bug, Search, Plus, X, RefreshCw, AlertTriangle, CheckCircle2,
  MessageSquare, Send, Trash2, Sparkles, Zap, HelpCircle, Clock,
  UserCircle2, Filter, ChevronRight, Flag,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_META = {
  new:         { label: "New",         cls: "bg-sky-100 text-sky-800 border-sky-200" },
  triaged:     { label: "Triaged",     cls: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  in_progress: { label: "In Progress", cls: "bg-amber-100 text-amber-800 border-amber-200" },
  resolved:    { label: "Resolved",    cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  closed:      { label: "Closed",      cls: "bg-stone-200 text-stone-700 border-stone-300" },
  wont_fix:    { label: "Won't fix",   cls: "bg-rose-100 text-rose-700 border-rose-200" },
};

const PRIORITY_META = {
  low:      { label: "Low",      cls: "bg-stone-100 text-stone-700 border-stone-200",   dot: "bg-stone-400" },
  medium:   { label: "Medium",   cls: "bg-sky-100 text-sky-800 border-sky-200",         dot: "bg-sky-500" },
  high:     { label: "High",     cls: "bg-amber-100 text-amber-800 border-amber-200",   dot: "bg-amber-500" },
  critical: { label: "Critical", cls: "bg-rose-100 text-rose-800 border-rose-200",      dot: "bg-rose-500" },
};

const TYPE_META = {
  bug:             { label: "Bug",             icon: Bug,         cls: "bg-rose-50 text-rose-700" },
  feedback:        { label: "Feedback",        icon: MessageSquare, cls: "bg-indigo-50 text-indigo-700" },
  feature_request: { label: "Feature request", icon: Sparkles,    cls: "bg-violet-50 text-violet-700" },
  question:        { label: "Question",        icon: HelpCircle,  cls: "bg-amber-50 text-amber-700" },
};

const AREAS = [
  "Bookings", "Payroll", "Rate Matrix", "Integrations", "Arrivals",
  "Onboarding", "Legal Docs", "Reports", "Finance", "Marketplace",
  "Guest Messaging", "Mobile View", "Other",
];

const STATUS_FILTER_TABS = ["all", "new", "triaged", "in_progress", "resolved", "closed"];

export const BugTrackerPanel = ({ user }) => {
  const [data, setData] = useState({ tickets: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusTab, setStatusTab] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [detail, setDetail] = useState(null);
  const [assignees, setAssignees] = useState([]);
  const [saving, setSaving] = useState(false);

  const isTriage = user?.role === "admin" || user?.role === "manager";
  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusTab && statusTab !== "all") params.set("status", statusTab);
      if (priorityFilter) params.set("priority", priorityFilter);
      if (typeFilter) params.set("type", typeFilter);
      if (q) params.set("q", q);
      const { data: d } = await axios.get(`${API}/bug-tracker?${params}`);
      setData(d);
    } catch (e) {
      /* silent */
    }
    setLoading(false);
  }, [statusTab, priorityFilter, typeFilter, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    if (!isTriage) return;
    axios.get(`${API}/bug-tracker-meta/assignees`)
      .then(r => setAssignees(r.data || []))
      .catch(() => setAssignees([]));
  }, [isTriage]);

  const openDetail = async (t) => {
    try {
      const { data: full } = await axios.get(`${API}/bug-tracker/${t.id}`);
      setDetail(full);
    } catch {
      toast.error("Could not load ticket");
    }
  };

  return (
    <div className="space-y-5" data-testid="bug-tracker">
      {/* Hero */}
      <div className="bg-gradient-to-br from-indigo-700 via-fuchsia-700 to-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/5 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Bug className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Bug Tracker · System Feedback</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="bug-title">Break things, report things, fix things.</h2>
            <p className="text-sm opacity-85">
              Any team member can log a bug or feedback. {isTriage ? "Triage, prioritise, assign and resolve from here." : "Admins will triage and respond."}
            </p>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <KPI label="Open" value={(data.stats.new || 0) + (data.stats.triaged || 0) + (data.stats.in_progress || 0)} />
            <KPI label="Critical" value={data.stats.critical || 0} accent="text-rose-200" />
            <KPI label="Resolved" value={data.stats.resolved || 0} accent="text-emerald-200" />
            <Button size="sm" className="bg-white text-slate-900 hover:bg-stone-100 font-bold" onClick={() => setShowNew(true)} data-testid="bug-new">
              <Plus className="w-4 h-4 mr-1" />Report
            </Button>
          </div>
        </div>
      </div>

      {/* Status tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto" data-testid="bug-tabs">
        {STATUS_FILTER_TABS.map(s => {
          const count = s === "all" ? (data.stats.total || 0) : (data.stats.by_status?.[s] || 0);
          const active = statusTab === s;
          return (
            <button key={s}
                    onClick={() => setStatusTab(s)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition whitespace-nowrap ${active
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"}`}
                    data-testid={`tab-${s}`}>
              {s === "all" ? "All" : STATUS_META[s]?.label}
              <span className={`ml-1.5 text-[10px] ${active ? "opacity-80" : "text-stone-400"}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search title or description..." className="pl-9 h-9" data-testid="bug-search" />
        </div>
        <Select value={priorityFilter || "all"} onValueChange={v => setPriorityFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-40 h-9" data-testid="bug-priority-filter"><SelectValue placeholder="All priorities" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            {Object.keys(PRIORITY_META).map(k => <SelectItem key={k} value={k}>{PRIORITY_META[k].label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={typeFilter || "all"} onValueChange={v => setTypeFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-44 h-9" data-testid="bug-type-filter"><SelectValue placeholder="All types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {Object.keys(TYPE_META).map(k => <SelectItem key={k} value={k}>{TYPE_META[k].label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* List */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden" data-testid="bug-list">
        {loading && !data.tickets.length && (
          <div className="py-16 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</div>
        )}
        {!loading && !data.tickets.length && (
          <div className="py-20 text-center text-stone-400" data-testid="bug-empty">
            <Bug className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p className="font-semibold text-stone-500 mb-1">No tickets match your filters</p>
            <p className="text-xs">Nothing to triage — or nothing's been reported yet.</p>
            <Button className="mt-4" size="sm" onClick={() => setShowNew(true)}>
              <Plus className="w-4 h-4 mr-1" />File the first one
            </Button>
          </div>
        )}
        <ul className="divide-y divide-stone-100">
          {data.tickets.map(t => {
            const TypeIcon = TYPE_META[t.type]?.icon || Bug;
            const pMeta = PRIORITY_META[t.priority] || PRIORITY_META.medium;
            const sMeta = STATUS_META[t.status] || STATUS_META.new;
            return (
              <li key={t.id}
                  onClick={() => openDetail(t)}
                  className="px-4 py-3 hover:bg-stone-50 cursor-pointer transition flex items-center gap-3"
                  data-testid={`ticket-${t.id}`}>
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${TYPE_META[t.type]?.cls || ""}`}>
                  <TypeIcon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-semibold text-stone-800 text-sm truncate">{t.title}</p>
                    <Badge className={`text-[9px] font-bold ${sMeta.cls}`}>{sMeta.label}</Badge>
                    <Badge className={`text-[9px] font-bold ${pMeta.cls}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${pMeta.dot} mr-1`} />{pMeta.label}
                    </Badge>
                    {t.area && <Badge className="text-[9px] font-medium bg-stone-100 text-stone-600 border-stone-200">{t.area}</Badge>}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px] text-stone-500 flex-wrap">
                    <span className="flex items-center gap-1"><UserCircle2 className="w-3 h-3" />{t.created_by_name}</span>
                    <span>·</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{new Date(t.created_at).toLocaleDateString()}</span>
                    {t.assigned_to_name && <>
                      <span>·</span>
                      <span className="flex items-center gap-1"><Flag className="w-3 h-3" />assigned to {t.assigned_to_name}</span>
                    </>}
                    {(t.comments?.length || 0) > 0 && <>
                      <span>·</span>
                      <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" />{t.comments.length}</span>
                    </>}
                  </div>
                </div>
                <ChevronRight className="w-4 h-4 text-stone-300 flex-shrink-0" />
              </li>
            );
          })}
        </ul>
      </div>

      {/* Report dialog */}
      {showNew && (
        <NewTicketDialog onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); }} />
      )}

      {/* Detail drawer */}
      {detail && (
        <TicketDetail t={detail}
                      user={user}
                      isTriage={isTriage}
                      isAdmin={isAdmin}
                      assignees={assignees}
                      saving={saving}
                      setSaving={setSaving}
                      onClose={() => setDetail(null)}
                      onUpdated={(nt) => { setDetail(nt); load(); }}
                      onDeleted={() => { setDetail(null); load(); }} />
      )}
    </div>
  );
};

const KPI = ({ label, value, accent = "" }) => (
  <div>
    <p className={`text-2xl font-black ${accent}`}>{value}</p>
    <p className="text-[10px] opacity-80 uppercase tracking-wider">{label}</p>
  </div>
);

const NewTicketDialog = ({ onClose, onSaved }) => {
  const [form, setForm] = useState({
    title: "", description: "", type: "bug", priority: "medium", area: "",
    url_context: typeof window !== "undefined" ? window.location.href : "",
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.title.trim() || form.title.trim().length < 3) {
      toast.error("Add a short title first"); return;
    }
    setBusy(true);
    try {
      await axios.post(`${API}/bug-tracker`, {
        ...form,
        area: form.area || null,
      });
      toast.success("Ticket submitted — thank you!");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Submit failed");
    }
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto" data-testid="bug-new-dialog">
        <div className="bg-gradient-to-br from-indigo-700 to-fuchsia-800 text-white rounded-t-2xl p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest opacity-80">Report</p>
              <h3 className="text-xl font-black">File a ticket</h3>
              <p className="text-[11px] opacity-80 mt-1">Describe what happened. Attach context. The team will triage it.</p>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-white/10 rounded"><X className="w-4 h-4" /></button>
          </div>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Title *</label>
            <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Short, sharp summary" className="mt-1" data-testid="bug-title-input" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Type</label>
              <Select value={form.type} onValueChange={v => setForm({ ...form, type: v })}>
                <SelectTrigger className="mt-1" data-testid="bug-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(TYPE_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Priority</label>
              <Select value={form.priority} onValueChange={v => setForm({ ...form, priority: v })}>
                <SelectTrigger className="mt-1" data-testid="bug-priority-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(PRIORITY_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Area</label>
            <Select value={form.area || "none"} onValueChange={v => setForm({ ...form, area: v === "none" ? "" : v })}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="Which module?" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                {AREAS.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Description</label>
            <Textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={5} placeholder="Steps to reproduce, expected vs actual, notes..." className="mt-1" data-testid="bug-desc-input" />
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Page URL</label>
            <Input value={form.url_context} onChange={e => setForm({ ...form, url_context: e.target.value })} className="mt-1 text-xs" />
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t bg-stone-50 rounded-b-2xl">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={submit} disabled={busy} className="bg-indigo-700 hover:bg-indigo-800 text-white font-bold" data-testid="bug-submit">
            <Send className="w-3.5 h-3.5 mr-1" />Submit
          </Button>
        </div>
      </div>
    </div>
  );
};

const TicketDetail = ({ t, user, isTriage, isAdmin, assignees, saving, setSaving, onClose, onUpdated, onDeleted }) => {
  const [comment, setComment] = useState("");
  const sMeta = STATUS_META[t.status] || STATUS_META.new;
  const pMeta = PRIORITY_META[t.priority] || PRIORITY_META.medium;
  const TypeIcon = TYPE_META[t.type]?.icon || Bug;

  const patch = async (updates) => {
    setSaving(true);
    try {
      const { data: nt } = await axios.put(`${API}/bug-tracker/${t.id}`, updates);
      toast.success("Updated");
      onUpdated(nt);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Update failed");
    }
    setSaving(false);
  };

  const addComment = async () => {
    if (!comment.trim()) return;
    setSaving(true);
    try {
      await axios.post(`${API}/bug-tracker/${t.id}/comments`, { body: comment.trim() });
      const { data: nt } = await axios.get(`${API}/bug-tracker/${t.id}`);
      setComment("");
      onUpdated(nt);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
    setSaving(false);
  };

  const del = async () => {
    if (!window.confirm("Delete this ticket permanently?")) return;
    try {
      await axios.delete(`${API}/bug-tracker/${t.id}`);
      toast.success("Deleted");
      onDeleted();
    } catch (e) {
      toast.error("Failed");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end p-0 sm:p-4 bg-black/60" onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
           className="bg-white rounded-none sm:rounded-2xl shadow-2xl w-full sm:max-w-2xl h-full sm:h-auto sm:max-h-[94vh] overflow-y-auto"
           data-testid="bug-detail">
        <div className="bg-slate-900 text-white p-5 sticky top-0 z-10 sm:rounded-t-2xl">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${TYPE_META[t.type]?.cls}`}>
                <TypeIcon className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">#{t.id.slice(0, 8)} · {TYPE_META[t.type]?.label}</p>
                <h3 className="text-lg font-black">{t.title}</h3>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <Badge className={`text-[9px] font-bold ${sMeta.cls}`}>{sMeta.label}</Badge>
                  <Badge className={`text-[9px] font-bold ${pMeta.cls}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${pMeta.dot} mr-1`} />{pMeta.label}
                  </Badge>
                  {t.area && <Badge className="text-[9px] font-medium bg-white/10 text-white border-white/10">{t.area}</Badge>}
                </div>
              </div>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-white/10 rounded"><X className="w-4 h-4" /></button>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <MetaRow label="Reported by" value={`${t.created_by_name} (${t.created_by_role})`} />
            <MetaRow label="Reported on" value={new Date(t.created_at).toLocaleString()} />
            <MetaRow label="Assigned to" value={t.assigned_to_name || "—"} />
            <MetaRow label="Updated" value={new Date(t.updated_at).toLocaleString()} />
            {t.resolved_at && <MetaRow label="Resolved" value={`${new Date(t.resolved_at).toLocaleString()} by ${t.resolved_by_name || ""}`} />}
            {t.url_context && <MetaRow label="Page" value={t.url_context} mono />}
          </div>

          {/* Description */}
          {t.description && (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1">Description</p>
              <p className="text-sm text-stone-700 whitespace-pre-wrap">{t.description}</p>
            </div>
          )}

          {/* Resolution note */}
          {t.resolution_note && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-1 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />Resolution</p>
              <p className="text-sm text-emerald-900 whitespace-pre-wrap">{t.resolution_note}</p>
            </div>
          )}

          {/* Triage actions */}
          {isTriage && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 space-y-3" data-testid="bug-triage">
              <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-700 flex items-center gap-1"><Zap className="w-3 h-3" />Triage</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold uppercase text-stone-500">Status</label>
                  <Select value={t.status} onValueChange={v => patch({ status: v })} disabled={saving}>
                    <SelectTrigger className="mt-1 h-9" data-testid="bug-status-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(STATUS_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase text-stone-500">Priority</label>
                  <Select value={t.priority} onValueChange={v => patch({ priority: v })} disabled={saving}>
                    <SelectTrigger className="mt-1 h-9"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(PRIORITY_META).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-2">
                  <label className="text-[10px] font-bold uppercase text-stone-500">Assign to</label>
                  <Select value={t.assigned_to_id || "none"}
                          onValueChange={v => patch({ assigned_to_id: v === "none" ? "" : v })}
                          disabled={saving}>
                    <SelectTrigger className="mt-1 h-9" data-testid="bug-assignee-select"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Unassigned</SelectItem>
                      {assignees.map(a => <SelectItem key={a.id} value={a.id}>{a.name} · {a.role}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {t.status === "resolved" && (
                <div>
                  <label className="text-[10px] font-bold uppercase text-stone-500">Resolution note</label>
                  <Textarea rows={2} defaultValue={t.resolution_note || ""}
                            onBlur={e => {
                              const v = e.target.value.trim();
                              if (v !== (t.resolution_note || "")) patch({ resolution_note: v });
                            }}
                            className="mt-1" placeholder="What was done to fix it?" data-testid="bug-resolution" />
                </div>
              )}
            </div>
          )}

          {/* Comments */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />Comments ({t.comments?.length || 0})
            </p>
            <ul className="space-y-2 mb-3">
              {(t.comments || []).map(c => (
                <li key={c.id} className="bg-white border border-stone-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1 text-[11px] text-stone-500">
                    <span className="font-semibold text-stone-700">{c.author_name}</span>
                    <span className="text-[9px] uppercase tracking-wider opacity-70">{c.author_role}</span>
                    <span>·</span>
                    <span>{new Date(c.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-sm text-stone-700 whitespace-pre-wrap">{c.body}</p>
                </li>
              ))}
              {!(t.comments || []).length && (
                <li className="text-xs text-stone-400 italic">No comments yet.</li>
              )}
            </ul>
            <div className="flex items-start gap-2">
              <Textarea value={comment} onChange={e => setComment(e.target.value)} rows={2} placeholder="Add a comment..." className="flex-1 text-sm" data-testid="bug-comment-input" />
              <Button onClick={addComment} size="sm" disabled={saving || !comment.trim()} className="bg-slate-900 hover:bg-slate-800 text-white font-bold" data-testid="bug-comment-send">
                <Send className="w-3.5 h-3.5 mr-1" />Send
              </Button>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 p-4 border-t bg-stone-50 sm:rounded-b-2xl sticky bottom-0">
          {isAdmin ? (
            <Button variant="outline" size="sm" onClick={del} className="text-red-600 hover:bg-red-50" data-testid="bug-delete">
              <Trash2 className="w-3.5 h-3.5 mr-1" />Delete
            </Button>
          ) : <div />}
          <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
};

const MetaRow = ({ label, value, mono = false }) => (
  <div className="bg-stone-50 rounded-lg px-3 py-2 border border-stone-200">
    <p className="text-[9px] font-bold uppercase tracking-wider text-stone-400">{label}</p>
    <p className={`text-xs text-stone-700 truncate ${mono ? "font-mono" : ""}`} title={value}>{value}</p>
  </div>
);
