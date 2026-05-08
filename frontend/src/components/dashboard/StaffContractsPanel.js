import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  FileSignature, Search, Plus, RefreshCw, Send, Copy, X, CheckCircle2,
  Clock, AlertTriangle, Ban, Pencil, Trash2, PoundSterling, Users,
  CalendarClock, ShieldAlert, FileText, ExternalLink, Paperclip, CalendarPlus,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPES = [
  { id: "full_time",  label: "Full-time" },
  { id: "part_time",  label: "Part-time" },
  { id: "fixed_term", label: "Fixed-term" },
  { id: "casual",     label: "Casual" },
  { id: "zero_hours", label: "Zero-hours" },
  { id: "freelance",  label: "Freelance" },
];

const STATUSES = [
  { id: "draft",      label: "Draft",      color: "bg-stone-100 text-stone-700 border-stone-200" },
  { id: "sent",       label: "Sent",       color: "bg-blue-50 text-blue-700 border-blue-200" },
  { id: "signed",     label: "Signed",     color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { id: "active",     label: "Active",     color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  { id: "expired",    label: "Expired",    color: "bg-amber-50 text-amber-700 border-amber-200" },
  { id: "terminated", label: "Terminated", color: "bg-rose-50 text-rose-700 border-rose-200" },
];

const EMPTY_FORM = {
  property_id: "all", user_id: "", staff_name: "", staff_email: "", role: "",
  department: "front_desk", contract_type: "full_time", start_date: "", end_date: "",
  probation_end: "", hours_per_week: 40, hourly_rate: 0, salary_annual: 0,
  notice_period_days: 30, holiday_entitlement_days: 28, terms: "",
};

const fmt$ = (n) => `£${(Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export const StaffContractsPanel = ({ propertyId, user }) => {
  const [contracts, setContracts] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [shareLink, setShareLink] = useState(null);
  const [busy, setBusy] = useState(null);
  const [extending, setExtending] = useState(null); // { contract, new_end_date, reason }

  const pid = propertyId || "all";
  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (q) params.set("q", q);
      const [c, s] = await Promise.all([
        axios.get(`${API}/contracts/${pid}?${params}`),
        axios.get(`${API}/contracts/stats/${pid}`),
      ]);
      setContracts(c.data || []);
      setStats(s.data || {});
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, status, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, property_id: pid });
    setShowForm(true);
  };
  const openEdit = (c) => {
    setEditing(c);
    setForm({ ...EMPTY_FORM, ...c, property_id: c.property_id || pid });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.staff_name || !form.role || !form.start_date) {
      toast.error("Staff name, role and start date required"); return;
    }
    setBusy("save");
    try {
      if (editing) {
        await axios.put(`${API}/contracts/${editing.id}`, form);
        toast.success("Contract updated");
      } else {
        await axios.post(`${API}/contracts`, form);
        toast.success("Contract created — not yet signed");
      }
      setShowForm(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    }
    setBusy(null);
  };

  const send = async (c) => {
    setBusy(c.id);
    try {
      const { data } = await axios.post(`${API}/contracts/${c.id}/send`);
      setShareLink({ contract: c, url: data.sign_url });
      toast.success("Signing link ready");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };


  const uploadFile = async (c, file) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { toast.error("File too large (max 10MB)"); return; }
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/contracts/${c.id}/upload-file`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`"${file.name}" attached`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    }
  };

  const terminate = async (c) => {
    const reason = window.prompt("Termination reason (optional):", "");
    if (reason === null) return;
    setBusy(c.id);
    try {
      await axios.post(`${API}/contracts/${c.id}/terminate`, { reason });
      toast.success("Contract terminated");
      load();
    } catch (e) { toast.error("Failed"); }
    setBusy(null);
  };

  const openExtend = (c) => {
    // Suggest +12 months by default, fallback to +6 months if no end date
    const base = c.end_date ? new Date(c.end_date) : new Date();
    base.setMonth(base.getMonth() + 12);
    const iso = base.toISOString().slice(0, 10);
    setExtending({ contract: c, new_end_date: iso, reason: "" });
  };

  const submitExtend = async () => {
    if (!extending) return;
    const { contract, new_end_date, reason } = extending;
    if (!new_end_date) { toast.error("Pick a new end date"); return; }
    setBusy(contract.id);
    try {
      const { data } = await axios.post(`${API}/contracts/${contract.id}/extend`, {
        new_end_date, reason: reason || "",
      });
      toast.success(`Extended to ${data.new_end_date} (#${data.extension_count})`);
      setExtending(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Extend failed"); }
    setBusy(null);
  };

  const remove = async (c) => {
    if (!window.confirm(`Delete draft contract for ${c.staff_name}?`)) return;
    setBusy(c.id);
    try {
      await axios.delete(`${API}/contracts/${c.id}`);
      toast.success("Deleted");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };

  const statusChip = (s) => {
    const cfg = STATUSES.find(x => x.id === s) || STATUSES[0];
    return <Badge className={`text-[10px] font-bold border ${cfg.color}`}>{cfg.label.toUpperCase()}</Badge>;
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
    <div className="space-y-5" data-testid="staff-contracts">
      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-800 via-slate-700 to-stone-800 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-72 h-72 bg-white/5 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FileSignature className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Staff Contracts</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="contracts-title">Paper-free employment, signed in a tap.</h2>
            <p className="text-sm opacity-80">Draft, send for e-signature, track probation and renewals — every contract, one place.</p>
          </div>
          {isAdmin && (
            <Button size="sm" onClick={openCreate} className="bg-white text-slate-900 hover:bg-stone-100 font-bold shadow-lg" data-testid="new-contract-btn">
              <Plus className="w-4 h-4 mr-1" />New Contract
            </Button>
          )}
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Active Contracts" value={stats.active || 0} sub={`of ${stats.total || 0} total`} icon={Users} color="#10B981" testId="kpi-active" />
        <Kpi label="Expiring ≤30d" value={stats.expiring_30_days || 0} sub="renew soon" icon={CalendarClock} color="#F59E0B" testId="kpi-expiring" />
        <Kpi label="On Probation" value={stats.on_probation || 0} sub="review window" icon={ShieldAlert} color="#6366F1" testId="kpi-probation" />
        <Kpi label="Monthly Cost" value={fmt$(stats.monthly_cost || 0)} sub={`${fmt$(stats.annual_cost || 0)}/yr`} icon={PoundSterling} color="#EC4899" testId="kpi-cost" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          <button onClick={() => setStatus("")} data-testid="filter-all"
            className={`px-3 py-1.5 text-xs font-semibold rounded-md ${!status ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>All</button>
          {STATUSES.map(s => (
            <button key={s.id} onClick={() => setStatus(s.id)} data-testid={`filter-${s.id}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md ${status === s.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
              {s.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search by name, email, role..." className="pl-9 h-9" data-testid="contracts-search" />
        </div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* Upcoming Renewals — proactive alert card */}
      {(stats.upcoming_renewals || []).length > 0 && (
        <div className="bg-gradient-to-br from-amber-50 via-orange-50 to-rose-50 border border-amber-200 rounded-2xl p-5 shadow-sm" data-testid="upcoming-renewals-card">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 text-white flex items-center justify-center shadow-lg flex-shrink-0">
              <CalendarClock className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-black text-stone-900">Upcoming Renewals</h3>
                <span className="px-2 py-0.5 rounded-full bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wider">
                  {stats.upcoming_renewals.length} in next 90d
                </span>
                {stats.expiring_30_days > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold uppercase tracking-wider animate-pulse">
                    {stats.expiring_30_days} urgent ≤30d
                  </span>
                )}
              </div>
              <p className="text-[11px] text-stone-600 mt-0.5">
                Extend these before they expire — signature, pay and terms stay intact.
              </p>

              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                {stats.upcoming_renewals.slice(0, 6).map((r) => {
                  const urgent = r.days_to_end <= 30;
                  return (
                    <div key={r.id}
                      className={`flex items-center gap-3 p-2.5 rounded-lg bg-white border ${urgent ? "border-rose-200" : "border-stone-200"} hover:shadow-sm transition`}
                      data-testid={`renewal-item-${r.id}`}>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0 ${urgent ? "bg-gradient-to-br from-rose-500 to-red-600" : "bg-gradient-to-br from-amber-400 to-orange-500"}`}>
                        {(r.staff_name || "?").slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-stone-800 truncate">{r.staff_name}</p>
                        <p className="text-[10px] text-stone-500 truncate">{r.role} · ends {r.end_date}</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className={`text-[11px] font-black tabular-nums ${urgent ? "text-rose-700" : "text-amber-700"}`}>
                          {r.days_to_end === 0 ? "today" : `${r.days_to_end}d`}
                        </div>
                        {r.extension_count > 0 && (
                          <div className="text-[9px] text-stone-400">+{r.extension_count} prior</div>
                        )}
                      </div>
                      {isAdmin && (
                        <button onClick={() => openExtend(r)}
                          className="px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold inline-flex items-center gap-1 shadow-sm flex-shrink-0"
                          data-testid={`renewal-extend-${r.id}`}>
                          <CalendarPlus className="w-3 h-3" /> Extend
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              {stats.upcoming_renewals.length > 6 && (
                <p className="mt-2 text-[11px] text-stone-500">
                  + {stats.upcoming_renewals.length - 6} more. Filter by <button onClick={() => setStatus("active")} className="underline font-semibold">Active</button> or sort by end-date in the table below.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="contracts-table">
            <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Staff</th>
                <th className="px-4 py-3 text-left font-semibold">Type</th>
                <th className="px-4 py-3 text-left font-semibold">Start / End</th>
                <th className="px-4 py-3 text-right font-semibold">Pay</th>
                <th className="px-4 py-3 text-center font-semibold">Status</th>
                <th className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && !contracts.length && (
                <tr><td colSpan={6} className="py-12 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</td></tr>
              )}
              {!loading && !contracts.length && (
                <tr><td colSpan={6} className="py-16 text-center text-stone-400" data-testid="empty">
                  <FileText className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No contracts yet. Click <span className="font-bold">New Contract</span> to create your first.</p>
                </td></tr>
              )}
              {contracts.map(c => {
                const typeLabel = TYPES.find(t => t.id === c.contract_type)?.label || c.contract_type;
                return (
                  <tr key={c.id} className="hover:bg-stone-50 transition" data-testid={`contract-${c.id}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 text-white flex items-center justify-center text-[11px] font-bold flex-shrink-0">
                          {(c.staff_name || "?").slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-stone-800 truncate">{c.staff_name}</p>
                          <p className="text-[10px] text-stone-500 truncate">{c.role}{c.on_probation ? " · on probation" : ""}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-stone-700">
                      <Badge variant="outline" className="text-[10px]">{typeLabel}</Badge>
                      <div className="text-[10px] text-stone-500 mt-1">{c.hours_per_week || 0}h/week</div>
                    </td>
                    <td className="px-4 py-3 text-stone-700 text-xs">
                      <div>{c.start_date || "—"}</div>
                      {c.end_date ? (
                        <div className={c.days_to_end !== undefined && c.days_to_end <= 30 && c.days_to_end >= 0 ? "text-amber-700 font-semibold" : "text-stone-500"}>
                          → {c.end_date}
                          {c.days_to_end !== undefined && c.days_to_end >= 0 && ` (${c.days_to_end}d)`}
                        </div>
                      ) : <div className="text-[10px] text-stone-400">permanent</div>}
                    </td>
                    <td className="px-4 py-3 text-right text-stone-700 text-xs">
                      {c.salary_annual > 0 ? (
                        <div><span className="font-bold">{fmt$(c.salary_annual)}</span>/yr</div>
                      ) : (
                        <div><span className="font-bold">{fmt$(c.hourly_rate)}</span>/h</div>
                      )}
                      <div className="text-[10px] text-stone-500">{fmt$(c.monthly_cost)}/mo</div>
                    </td>
                    <td className="px-4 py-3 text-center">{statusChip(c.computed_status)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {/* File attachment button — always visible for admin/manager */}
                        <label className="p-1.5 hover:bg-indigo-50 rounded-lg text-indigo-600 cursor-pointer" title="Attach file (signed PDF, ID, visa)" data-testid={`attach-${c.id}`}>
                          <Paperclip className="w-3.5 h-3.5" />
                          <input type="file" className="hidden" onChange={e => uploadFile(c, e.target.files?.[0])} data-testid={`attach-input-${c.id}`} />
                        </label>
                        {(c.attachments?.length || 0) > 0 && (
                          <span className="text-[9px] bg-indigo-50 text-indigo-700 font-bold px-1.5 py-0.5 rounded-md" data-testid={`att-count-${c.id}`}>
                            {c.attachments.length} 📎
                          </span>
                        )}
                        {["draft"].includes(c.computed_status) && isAdmin && (
                          <>
                            <button onClick={() => openEdit(c)} className="p-1.5 hover:bg-stone-100 rounded-lg" title="Edit" data-testid={`edit-${c.id}`}>
                              <Pencil className="w-3.5 h-3.5 text-stone-500" />
                            </button>
                            <Button size="sm" disabled={busy === c.id} onClick={() => send(c)} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid={`send-${c.id}`}>
                              <Send className="w-3 h-3 mr-1" />Send to Sign
                            </Button>
                            <button onClick={() => remove(c)} className="p-1.5 hover:bg-red-50 rounded-lg text-red-500" title="Delete" data-testid={`del-${c.id}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        {c.computed_status === "sent" && (
                          <Button size="sm" variant="outline" onClick={() => setShareLink({ contract: c, url: `${process.env.REACT_APP_BACKEND_URL}/contract/sign/${c.sign_token}` })} data-testid={`link-${c.id}`}>
                            <ExternalLink className="w-3 h-3 mr-1" />View Link
                          </Button>
                        )}
                        {["signed", "active", "expired"].includes(c.computed_status) && isAdmin && (
                          <Button size="sm" variant="outline" onClick={() => openExtend(c)} className="text-emerald-700 hover:bg-emerald-50 border-emerald-200" data-testid={`extend-${c.id}`}>
                            <CalendarPlus className="w-3 h-3 mr-1" />Extend
                          </Button>
                        )}
                        {["signed", "active"].includes(c.computed_status) && isAdmin && (
                          <Button size="sm" variant="outline" onClick={() => terminate(c)} className="text-red-600 hover:bg-red-50" data-testid={`term-${c.id}`}>
                            <Ban className="w-3 h-3 mr-1" />Terminate
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="contract-form">
          <DialogHeader>
            <DialogTitle className="text-lg font-black">{editing ? "Edit Contract" : "New Staff Contract"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div className="col-span-2">
              <Label className="text-xs">Staff full name *</Label>
              <Input value={form.staff_name} onChange={e => setForm({ ...form, staff_name: e.target.value })} data-testid="f-name" />
            </div>
            <div>
              <Label className="text-xs">Email</Label>
              <Input type="email" value={form.staff_email} onChange={e => setForm({ ...form, staff_email: e.target.value })} data-testid="f-email" />
            </div>
            <div>
              <Label className="text-xs">Role / Job title *</Label>
              <Input value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} placeholder="e.g. Receptionist" data-testid="f-role" />
            </div>
            <div>
              <Label className="text-xs">Department</Label>
              <Select value={form.department} onValueChange={v => setForm({ ...form, department: v })}>
                <SelectTrigger data-testid="f-dept"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["front_desk", "housekeeping", "maintenance", "food_beverage", "management", "admin"].map(d => (
                    <SelectItem key={d} value={d}>{d.replace("_", " ")}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Contract type *</Label>
              <Select value={form.contract_type} onValueChange={v => setForm({ ...form, contract_type: v })}>
                <SelectTrigger data-testid="f-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPES.map(t => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Start date *</Label>
              <Input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} data-testid="f-start" />
            </div>
            <div>
              <Label className="text-xs">End date (blank = permanent)</Label>
              <Input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} data-testid="f-end" />
            </div>
            <div>
              <Label className="text-xs">Probation ends</Label>
              <Input type="date" value={form.probation_end} onChange={e => setForm({ ...form, probation_end: e.target.value })} data-testid="f-probation" />
            </div>
            <div>
              <Label className="text-xs">Hours / week</Label>
              <Input type="number" value={form.hours_per_week} onChange={e => setForm({ ...form, hours_per_week: e.target.value })} data-testid="f-hours" />
            </div>
            <div>
              <Label className="text-xs">Hourly rate (£)</Label>
              <Input type="number" step="0.01" value={form.hourly_rate} onChange={e => setForm({ ...form, hourly_rate: e.target.value })} data-testid="f-rate" />
            </div>
            <div>
              <Label className="text-xs">Annual salary (£) — optional</Label>
              <Input type="number" value={form.salary_annual} onChange={e => setForm({ ...form, salary_annual: e.target.value })} data-testid="f-salary" />
            </div>
            <div>
              <Label className="text-xs">Notice period (days)</Label>
              <Input type="number" value={form.notice_period_days} onChange={e => setForm({ ...form, notice_period_days: e.target.value })} data-testid="f-notice" />
            </div>
            <div>
              <Label className="text-xs">Holiday entitlement (days)</Label>
              <Input type="number" value={form.holiday_entitlement_days} onChange={e => setForm({ ...form, holiday_entitlement_days: e.target.value })} data-testid="f-holiday" />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Terms & Conditions (shown to staff before signing)</Label>
              <Textarea rows={5} value={form.terms} onChange={e => setForm({ ...form, terms: e.target.value })}
                placeholder="Duties, confidentiality, data protection, code of conduct..." data-testid="f-terms" />
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t">
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button onClick={save} disabled={busy === "save"} className="bg-slate-800 hover:bg-slate-700 text-white" data-testid="f-save">
              {busy === "save" ? "Saving..." : editing ? "Update" : "Create Draft"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Extend End Date Dialog */}
      {extending && (
        <Dialog open={true} onOpenChange={() => setExtending(null)}>
          <DialogContent className="max-w-md" data-testid="extend-dialog">
            <DialogHeader>
              <DialogTitle className="text-base font-black flex items-center gap-2">
                <CalendarPlus className="w-4 h-4 text-emerald-600" />
                Extend Contract
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-[11px] text-emerald-900">
                Extending <b>{extending.contract.staff_name}</b>'s contract. The original signature and terms stay intact — only the end date changes.
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-[10px] uppercase tracking-wider text-stone-500">Current end date</Label>
                  <Input value={extending.contract.end_date || "— permanent —"} disabled className="mt-1 bg-stone-50" />
                </div>
                <div>
                  <Label className="text-[10px] uppercase tracking-wider text-stone-500">New end date *</Label>
                  <Input type="date"
                    value={extending.new_end_date}
                    onChange={(e) => setExtending({ ...extending, new_end_date: e.target.value })}
                    data-testid="extend-new-date"
                    className="mt-1" />
                </div>
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-wider text-stone-500">Reason / Note</Label>
                <Textarea rows={2}
                  value={extending.reason}
                  onChange={(e) => setExtending({ ...extending, reason: e.target.value })}
                  data-testid="extend-reason"
                  className="mt-1"
                  placeholder="e.g. Renewed for another 12 months after successful probation." />
              </div>
              {((extending.contract.extensions?.length) ?? extending.contract.extension_count ?? 0) > 0 && (
                <div className="text-[10px] text-stone-500">
                  Previously extended {(extending.contract.extensions?.length) ?? extending.contract.extension_count} time{((extending.contract.extensions?.length) ?? extending.contract.extension_count) === 1 ? "" : "s"}.
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t">
              <Button variant="outline" onClick={() => setExtending(null)}>Cancel</Button>
              <Button onClick={submitExtend} disabled={busy === extending.contract.id}
                className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="extend-submit">
                {busy === extending.contract.id ? "Extending..." : "Extend Contract"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Share Link Dialog */}
      {shareLink && (
        <Dialog open={true} onOpenChange={() => setShareLink(null)}>
          <DialogContent className="max-w-md" data-testid="share-dialog">
            <DialogHeader>
              <DialogTitle>Share signing link</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-stone-600 mb-3">
              Send this link to <span className="font-semibold">{shareLink.contract.staff_name}</span>. They'll review and e-sign on their device.
            </p>
            <div className="flex items-center gap-2 bg-stone-100 rounded-lg p-2 mb-3">
              <code className="flex-1 text-[11px] text-stone-700 truncate">{shareLink.url}</code>
              <button onClick={() => { navigator.clipboard.writeText(shareLink.url); toast.success("Copied"); }}
                className="p-1.5 hover:bg-white rounded" data-testid="copy-sign-link"><Copy className="w-3.5 h-3.5" /></button>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button size="sm" variant="outline" onClick={() => setShareLink(null)}>Close</Button>
              <a href={shareLink.url} target="_blank" rel="noreferrer" className="inline-flex">
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white">
                  <ExternalLink className="w-3.5 h-3.5 mr-1" />Open Preview
                </Button>
              </a>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};
