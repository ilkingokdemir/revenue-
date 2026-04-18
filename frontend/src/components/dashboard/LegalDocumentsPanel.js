import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Scale, Plus, Search, RefreshCw, Pencil, Trash2, GitBranch, Users,
  FileText, CheckCircle2, ShieldAlert, CalendarClock, X, Type, List,
  CheckSquare, Feather, Calendar as CalIcon, ChevronsUpDown, Heading,
  GripVertical, Eye,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DOC_TYPES = [
  { id: "privacy_policy",   label: "Privacy Policy",   color: "bg-blue-100 text-blue-700 border-blue-200" },
  { id: "terms_conditions", label: "Terms & Conditions", color: "bg-violet-100 text-violet-700 border-violet-200" },
  { id: "gdpr_consent",     label: "GDPR Consent",     color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
  { id: "code_of_conduct",  label: "Code of Conduct",  color: "bg-amber-100 text-amber-700 border-amber-200" },
  { id: "health_safety",    label: "Health & Safety",  color: "bg-rose-100 text-rose-700 border-rose-200" },
  { id: "nda",              label: "NDA",              color: "bg-slate-100 text-slate-700 border-slate-200" },
  { id: "other",            label: "Other",            color: "bg-stone-100 text-stone-700 border-stone-200" },
];

const STATUS_CONFIG = {
  active:    { label: "ACTIVE",    color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  draft:     { label: "DRAFT",     color: "bg-stone-100 text-stone-700 border-stone-200" },
  scheduled: { label: "SCHEDULED", color: "bg-blue-50 text-blue-700 border-blue-200" },
  expired:   { label: "EXPIRED",   color: "bg-amber-50 text-amber-700 border-amber-200" },
};

const FIELD_KINDS = [
  { type: "heading",   icon: Heading,         label: "Heading" },
  { type: "text",      icon: Type,            label: "Text input" },
  { type: "textarea",  icon: FileText,        label: "Long text" },
  { type: "checkbox",  icon: CheckSquare,     label: "Checkbox" },
  { type: "select",    icon: ChevronsUpDown,  label: "Dropdown" },
  { type: "date",      icon: CalIcon,         label: "Date" },
  { type: "signature", icon: Feather,         label: "Signature" },
];

const EMPTY_FORM = {
  title: "", code: "", description: "", doc_type: "other",
  version: "1.0", effective_date: "", expiry_date: "",
  active: true, required: false, fields: [],
};

export const LegalDocumentsPanel = ({ user }) => {
  const [docs, setDocs] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [docTypeFilter, setDocTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [acceptances, setAcceptances] = useState(null);
  const [busy, setBusy] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (docTypeFilter) params.set("doc_type", docTypeFilter);
      if (statusFilter) params.set("status", statusFilter);
      if (q) params.set("q", q);
      const [d, s] = await Promise.all([
        axios.get(`${API}/legal-documents?${params}`),
        axios.get(`${API}/legal-documents/stats`),
      ]);
      setDocs(d.data || []);
      setStats(s.data || {});
    } catch { /* silent */ }
    setLoading(false);
  }, [docTypeFilter, statusFilter, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };
  const openEdit = (d) => {
    setEditing(d);
    setForm({ ...EMPTY_FORM, ...d });
    setShowForm(true);
  };
  const save = async () => {
    if (!form.title) { toast.error("Title is required"); return; }
    setBusy("save");
    try {
      if (editing) {
        await axios.put(`${API}/legal-documents/${editing.id}`, form);
        toast.success("Document updated");
      } else {
        await axios.post(`${API}/legal-documents`, form);
        toast.success("Document created");
      }
      setShowForm(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
    setBusy(null);
  };
  const newVersion = async (d) => {
    setBusy(d.id);
    try {
      await axios.post(`${API}/legal-documents/${d.id}/new-version`);
      toast.success("New draft version created");
      load();
    } catch (e) { toast.error("Failed"); }
    setBusy(null);
  };
  const remove = async (d) => {
    if (!window.confirm(`Delete "${d.title}" v${d.version}?`)) return;
    try {
      await axios.delete(`${API}/legal-documents/${d.id}`);
      toast.success("Deleted");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const viewAcceptances = async (d) => {
    try {
      const { data } = await axios.get(`${API}/legal-documents/${d.id}/acceptances`);
      setAcceptances({ doc: d, rows: data });
    } catch { toast.error("Failed"); }
  };

  const addField = (kind) => {
    const id = `f_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const base = { id, type: kind, label: kind === "heading" ? "Section heading" : "Field label", required: false };
    if (kind === "select") base.options = ["Option 1", "Option 2"];
    setForm(f => ({ ...f, fields: [...(f.fields || []), base] }));
  };
  const updateField = (idx, patch) => {
    setForm(f => ({ ...f, fields: f.fields.map((ff, i) => i === idx ? { ...ff, ...patch } : ff) }));
  };
  const removeField = (idx) => {
    setForm(f => ({ ...f, fields: f.fields.filter((_, i) => i !== idx) }));
  };
  const moveField = (idx, dir) => {
    const j = idx + dir;
    if (j < 0 || j >= form.fields.length) return;
    const arr = [...form.fields];
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    setForm(f => ({ ...f, fields: arr }));
  };

  const typeBadge = (t) => {
    const cfg = DOC_TYPES.find(x => x.id === t) || DOC_TYPES[DOC_TYPES.length - 1];
    return <Badge className={`text-[10px] font-bold border ${cfg.color}`}>{cfg.label.toUpperCase()}</Badge>;
  };
  const statusBadge = (s) => {
    const cfg = STATUS_CONFIG[s] || STATUS_CONFIG.draft;
    return <Badge className={`text-[10px] font-bold border ${cfg.color}`}>{cfg.label}</Badge>;
  };

  const Kpi = ({ label, value, sub, icon: Icon, color, testId }) => (
    <div className="bg-white rounded-xl border border-stone-200 p-4" data-testid={testId}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{label}</span>
        <Icon className="w-3.5 h-3.5" style={{ color }} />
      </div>
      <p className="text-2xl font-black text-stone-800">{value}</p>
      {sub && <p className="text-[10px] text-stone-500 mt-0.5">{sub}</p>}
    </div>
  );

  return (
    <div className="space-y-5" data-testid="legal-documents">
      {/* Hero */}
      <div className="bg-gradient-to-br from-indigo-900 via-blue-900 to-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-blue-500/10 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Scale className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Legal Documents & Consents</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="legal-title">Policies in, signatures tracked, compliance proven.</h2>
            <p className="text-sm opacity-85">Privacy Policy, T&C, GDPR, Code of Conduct — versioned and auditable.</p>
          </div>
          {isAdmin && (
            <Button size="sm" onClick={openCreate} className="bg-white text-slate-900 hover:bg-stone-100 font-bold shadow-lg" data-testid="new-doc-btn">
              <Plus className="w-4 h-4 mr-1" />New Document
            </Button>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Active Documents" value={stats.active || 0} sub={`of ${stats.total_documents || 0} total`} icon={CheckCircle2} color="#10B981" testId="kpi-active" />
        <Kpi label="Required & Live" value={stats.required_active || 0} sub="users must accept" icon={ShieldAlert} color="#EF4444" testId="kpi-required" />
        <Kpi label="Expiring ≤30d" value={stats.expiring_30_days || 0} sub="renew soon" icon={CalendarClock} color="#F59E0B" testId="kpi-expiring" />
        <Kpi label="Total Acceptances" value={stats.total_acceptances || 0} sub={`${stats.total_users || 0} users`} icon={Users} color="#6366F1" testId="kpi-acceptances" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={docTypeFilter || "all"} onValueChange={v => setDocTypeFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-48 h-9" data-testid="type-filter"><SelectValue placeholder="All types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {DOC_TYPES.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          <button onClick={() => setStatusFilter("")} data-testid="status-all" className={`px-3 py-1.5 text-xs font-semibold rounded-md ${!statusFilter ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>All</button>
          {Object.entries(STATUS_CONFIG).map(([k, v]) => (
            <button key={k} onClick={() => setStatusFilter(k)} data-testid={`status-${k}`} className={`px-3 py-1.5 text-xs font-semibold rounded-md ${statusFilter === k ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {v.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search by title, code..." className="pl-9 h-9" data-testid="docs-search" />
        </div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="docs-table">
            <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Document</th>
                <th className="px-4 py-3 text-left font-semibold">Type</th>
                <th className="px-4 py-3 text-left font-semibold">Version</th>
                <th className="px-4 py-3 text-left font-semibold">Valid</th>
                <th className="px-4 py-3 text-left font-semibold">Acceptance</th>
                <th className="px-4 py-3 text-center font-semibold">Status</th>
                <th className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && !docs.length && (
                <tr><td colSpan={7} className="py-12 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</td></tr>
              )}
              {!loading && !docs.length && (
                <tr><td colSpan={7} className="py-16 text-center text-stone-400" data-testid="empty-docs">
                  <Scale className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No legal documents yet.</p>
                </td></tr>
              )}
              {docs.map(d => (
                <tr key={d.id} className="hover:bg-stone-50 transition" data-testid={`doc-${d.id}`}>
                  <td className="px-4 py-3">
                    <p className="font-semibold text-stone-800">{d.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <code className="text-[10px] text-stone-500">{d.code}</code>
                      <span className="text-[10px] text-stone-400">· {d.field_count || 0} fields</span>
                      {d.required && <Badge className="text-[9px] bg-red-50 text-red-700 border border-red-200">REQUIRED</Badge>}
                    </div>
                  </td>
                  <td className="px-4 py-3">{typeBadge(d.doc_type)}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className="text-[10px] font-mono">v{d.version}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-stone-600">
                    <div>{d.effective_date || "—"}</div>
                    <div className="text-stone-400">→ {d.expiry_date || "∞"}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 min-w-[100px]">
                      <div className="flex-1 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${d.acceptance_pct || 0}%` }} />
                      </div>
                      <span className="text-[11px] font-semibold text-stone-700">{d.acceptance_count || 0}/{d.total_users || 0}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">{statusBadge(d.computed_status)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => viewAcceptances(d)} className="p-1.5 hover:bg-stone-100 rounded-lg" title="View acceptances" data-testid={`view-${d.id}`}>
                        <Eye className="w-3.5 h-3.5 text-stone-500" />
                      </button>
                      {isAdmin && (
                        <>
                          <button onClick={() => openEdit(d)} className="p-1.5 hover:bg-stone-100 rounded-lg" title="Edit" data-testid={`edit-${d.id}`}>
                            <Pencil className="w-3.5 h-3.5 text-stone-500" />
                          </button>
                          <button onClick={() => newVersion(d)} disabled={busy === d.id} className="p-1.5 hover:bg-blue-50 rounded-lg" title="New version" data-testid={`version-${d.id}`}>
                            <GitBranch className="w-3.5 h-3.5 text-blue-600" />
                          </button>
                          <button onClick={() => remove(d)} className="p-1.5 hover:bg-red-50 rounded-lg" title="Delete" data-testid={`del-${d.id}`}>
                            <Trash2 className="w-3.5 h-3.5 text-red-500" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="doc-form">
          <DialogHeader>
            <DialogTitle className="text-lg font-black">{editing ? `Edit: ${form.title}` : "Create New Document"}</DialogTitle>
          </DialogHeader>

          {/* Basic Information */}
          <div className="space-y-4 mt-2">
            <h4 className="text-sm font-bold text-stone-800">Basic Information</h4>
            <div>
              <Label className="text-xs">Title *</Label>
              <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g., Privacy Policy" data-testid="f-title" />
            </div>
            <div>
              <Label className="text-xs">Code</Label>
              <Input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="AUTO-GENERATED IF LEFT EMPTY" data-testid="f-code" />
              <p className="text-[10px] text-stone-400 mt-0.5">Leave empty to auto-generate</p>
            </div>
            <div>
              <Label className="text-xs">Description</Label>
              <Textarea rows={2} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Brief description..." data-testid="f-desc" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Type *</Label>
                <Select value={form.doc_type} onValueChange={v => setForm({ ...form, doc_type: v })}>
                  <SelectTrigger data-testid="f-type"><SelectValue /></SelectTrigger>
                  <SelectContent>{DOC_TYPES.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Version</Label>
                <Input value={form.version} onChange={e => setForm({ ...form, version: e.target.value })} data-testid="f-version" />
              </div>
              <div>
                <Label className="text-xs">Effective Date</Label>
                <Input type="date" value={form.effective_date} onChange={e => setForm({ ...form, effective_date: e.target.value })} data-testid="f-effective" />
              </div>
              <div>
                <Label className="text-xs">Expiry Date</Label>
                <Input type="date" value={form.expiry_date} onChange={e => setForm({ ...form, expiry_date: e.target.value })} data-testid="f-expiry" />
              </div>
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 cursor-pointer" data-testid="f-active-wrap">
                <Switch checked={form.active} onCheckedChange={v => setForm({ ...form, active: v })} data-testid="f-active" />
                <span className="text-sm font-medium">Active</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="f-required-wrap">
                <Switch checked={form.required} onCheckedChange={v => setForm({ ...form, required: v })} data-testid="f-required" />
                <span className="text-sm font-medium">Required (users must accept)</span>
              </label>
            </div>
          </div>

          {/* Dynamic Field Builder */}
          <div className="border-t pt-4 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold text-stone-800">Contract Content</h4>
            </div>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {FIELD_KINDS.map(k => (
                <button key={k.type} onClick={() => addField(k.type)}
                  className="flex items-center gap-1 px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 text-[11px] font-semibold rounded-lg border border-blue-200 transition"
                  data-testid={`add-field-${k.type}`}>
                  <k.icon className="w-3 h-3" />
                  + {k.label}
                </button>
              ))}
            </div>

            {form.fields.length === 0 ? (
              <div className="border-2 border-dashed border-stone-200 rounded-xl p-8 text-center text-stone-400" data-testid="empty-fields">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No fields added yet. Click a field type above to start building.</p>
              </div>
            ) : (
              <div className="space-y-2" data-testid="fields-list">
                {form.fields.map((f, idx) => {
                  const kind = FIELD_KINDS.find(k => k.type === f.type) || FIELD_KINDS[0];
                  return (
                    <div key={f.id} className="bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid={`field-${idx}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <GripVertical className="w-3.5 h-3.5 text-stone-400" />
                        <kind.icon className="w-3.5 h-3.5 text-blue-600" />
                        <span className="text-[11px] font-bold text-stone-500 uppercase">{kind.label}</span>
                        <div className="ml-auto flex items-center gap-1">
                          <button onClick={() => moveField(idx, -1)} className="text-[10px] px-1.5 py-0.5 bg-white rounded border border-stone-200">↑</button>
                          <button onClick={() => moveField(idx, +1)} className="text-[10px] px-1.5 py-0.5 bg-white rounded border border-stone-200">↓</button>
                          <button onClick={() => removeField(idx)} className="p-1 hover:bg-red-100 text-red-500 rounded" data-testid={`del-field-${idx}`}>
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <Input placeholder="Label" value={f.label || ""} onChange={e => updateField(idx, { label: e.target.value })} className="h-8 text-xs" />
                        {!["heading", "checkbox"].includes(f.type) && (
                          <Input placeholder="Placeholder" value={f.placeholder || ""} onChange={e => updateField(idx, { placeholder: e.target.value })} className="h-8 text-xs" />
                        )}
                        {f.type === "select" && (
                          <Input placeholder="Option1,Option2,Option3" value={(f.options || []).join(",")} onChange={e => updateField(idx, { options: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })} className="h-8 text-xs col-span-2" />
                        )}
                        {f.type === "heading" && (
                          <Textarea rows={2} placeholder="Section content text..." value={f.content || ""} onChange={e => updateField(idx, { content: e.target.value })} className="text-xs col-span-2" />
                        )}
                        {f.type !== "heading" && (
                          <label className="flex items-center gap-1.5 text-[11px] text-stone-600 col-span-2">
                            <input type="checkbox" checked={!!f.required} onChange={e => updateField(idx, { required: e.target.checked })} />
                            Required
                          </label>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy === "save"} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="f-save">
              {busy === "save" ? "Saving..." : editing ? "Update" : "Create Document"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Acceptances Viewer */}
      {acceptances && (
        <Dialog open={true} onOpenChange={() => setAcceptances(null)}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="acceptances-dialog">
            <DialogHeader>
              <DialogTitle>Acceptances · {acceptances.doc.title} v{acceptances.doc.version}</DialogTitle>
            </DialogHeader>
            {acceptances.rows.length === 0 ? (
              <p className="text-center text-stone-400 py-10">No acceptances recorded yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-3 py-2 text-left">User</th>
                    <th className="px-3 py-2 text-left">Role</th>
                    <th className="px-3 py-2 text-left">Version</th>
                    <th className="px-3 py-2 text-right">Accepted</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {acceptances.rows.map(r => (
                    <tr key={r.id}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-stone-800">{r.user_name || r.user_email}</p>
                        <p className="text-[10px] text-stone-500">{r.user_email}</p>
                      </td>
                      <td className="px-3 py-2"><Badge variant="outline" className="text-[10px]">{r.user_role || "—"}</Badge></td>
                      <td className="px-3 py-2"><code className="text-[10px]">v{r.document_version}</code></td>
                      <td className="px-3 py-2 text-right text-[11px] text-stone-600">
                        {String(r.accepted_at).slice(0, 16).replace("T", " ")}
                        <div className="text-[9px] text-stone-400">{r.ip_address}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};
