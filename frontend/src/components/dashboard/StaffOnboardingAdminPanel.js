import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  UserCheck, Search, RefreshCw, Eye, CheckCircle2, XCircle, Home,
  FileText, Receipt, FileSignature, ShieldCheck, Circle, Ban,
  ExternalLink, Users, Clock,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUSES = [
  { id: "",           label: "All" },
  { id: "pending",    label: "Pending activation" },
  { id: "complete",   label: "Docs complete" },
  { id: "incomplete", label: "Incomplete" },
  { id: "activated",  label: "Activated" },
];

const STEPS = [
  { key: "passport", icon: UserCheck,     label: "ID" },
  { key: "address",  icon: Home,          label: "Address" },
  { key: "hmrc",     icon: Receipt,       label: "HMRC" },
  { key: "contract", icon: FileSignature, label: "Contract" },
];

const fmtDate = (s) => s ? String(s).slice(0, 16).replace("T", " ") : "—";

export const StaffOnboardingAdminPanel = ({ user }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      const { data } = await axios.get(`${API}/staff-onboarding/list?${params}`);
      setRows(data || []);
    } catch { /* silent */ }
    setLoading(false);
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const filtered = rows.filter(r => {
    if (!q) return true;
    const s = q.toLowerCase();
    return (r.user_name || "").toLowerCase().includes(s)
        || (r.user_email || "").toLowerCase().includes(s)
        || (r.user_role || "").toLowerCase().includes(s);
  });

  const counts = {
    total: rows.length,
    pending: rows.filter(r => !r.activated).length,
    activated: rows.filter(r => r.activated).length,
    complete: rows.filter(r => r.progress?.complete).length,
  };

  const activate = async (r) => {
    setBusy(r.user_id);
    try {
      await axios.post(`${API}/staff-onboarding/admin-activate/${r.user_id}`);
      toast.success(`${r.user_name} activated`);
      setSelected(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    setBusy(null);
  };
  const deactivate = async (r) => {
    if (!window.confirm(`Deactivate ${r.user_name}? They'll need to redo onboarding.`)) return;
    setBusy(r.user_id);
    try {
      await axios.post(`${API}/staff-onboarding/admin-deactivate/${r.user_id}`);
      toast.success(`${r.user_name} deactivated`);
      setSelected(null);
      load();
    } catch (e) { toast.error("Failed"); }
    setBusy(null);
  };

  const StepDot = ({ done, Icon, title }) => (
    <div title={title} className={`w-6 h-6 rounded-full flex items-center justify-center ${done ? "bg-emerald-500 text-white" : "bg-stone-100 text-stone-400"}`}>
      <Icon className="w-3 h-3" />
    </div>
  );

  const Kpi = ({ label, value, color, testId }) => (
    <div className="bg-white rounded-xl border border-stone-200 p-4" data-testid={testId}>
      <p className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">{label}</p>
      <p className="text-2xl font-black" style={{ color }}>{value}</p>
    </div>
  );

  return (
    <div className="space-y-5" data-testid="onboarding-admin">
      {/* Hero */}
      <div className="bg-gradient-to-br from-teal-800 via-emerald-900 to-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-400/10 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5" />
            <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Onboarding Review</span>
          </div>
          <h2 className="text-3xl font-black mb-1" data-testid="onboard-admin-title">Right-to-Work evidence, one-click activation.</h2>
          <p className="text-sm opacity-85">Review uploaded IDs, address proof, HMRC checklists and contract signatures — then activate or reject.</p>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Total Staff"     value={counts.total}     color="#0F172A" testId="kpi-total" />
        <Kpi label="Pending"         value={counts.pending}   color="#F59E0B" testId="kpi-pending" />
        <Kpi label="Docs Complete"   value={counts.complete}  color="#10B981" testId="kpi-complete" />
        <Kpi label="Activated"       value={counts.activated} color="#6366F1" testId="kpi-activated" />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {STATUSES.map(s => (
            <button key={s.id || "all"} onClick={() => setStatus(s.id)} data-testid={`oa-filter-${s.id || "all"}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${status === s.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}>
              {s.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search by name, email, role..." className="pl-9 h-9" data-testid="oa-search" />
        </div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="oa-table">
            <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Staff</th>
                <th className="px-4 py-3 text-left font-semibold">Role</th>
                <th className="px-4 py-3 text-left font-semibold">Progress</th>
                <th className="px-4 py-3 text-center font-semibold">Status</th>
                <th className="px-4 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && !rows.length && (
                <tr><td colSpan={5} className="py-12 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</td></tr>
              )}
              {!loading && !filtered.length && (
                <tr><td colSpan={5} className="py-16 text-center text-stone-400" data-testid="oa-empty">
                  <Users className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No staff onboarding records yet.</p>
                </td></tr>
              )}
              {filtered.map(r => {
                const p = r.progress || { done: 0, total: 4, tasks: {} };
                return (
                  <tr key={r.user_id} className="hover:bg-stone-50 transition" data-testid={`oa-row-${r.user_id}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 text-white flex items-center justify-center text-[11px] font-bold flex-shrink-0">
                          {(r.user_name || "?").slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-stone-800 truncate">{r.user_name || "—"}</p>
                          <p className="text-[10px] text-stone-500 truncate">{r.user_email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline" className="text-[10px] capitalize">{r.user_role || "—"}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-0.5">
                          {STEPS.map(s => <StepDot key={s.key} done={p.tasks?.[s.key]} Icon={s.icon} title={s.label} />)}
                        </div>
                        <span className="text-[11px] font-semibold text-stone-600">{p.done}/{p.total}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {r.activated ? (
                        <Badge className="text-[10px] font-bold bg-emerald-50 text-emerald-700 border-emerald-200">ACTIVATED</Badge>
                      ) : p.complete ? (
                        <Badge className="text-[10px] font-bold bg-amber-50 text-amber-700 border-amber-200">READY</Badge>
                      ) : (
                        <Badge className="text-[10px] font-bold bg-stone-100 text-stone-600 border-stone-200">WAITING</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button size="sm" variant="outline" onClick={() => setSelected(r)} data-testid={`oa-view-${r.user_id}`}>
                          <Eye className="w-3 h-3 mr-1" />Review
                        </Button>
                        {isAdmin && !r.activated && p.complete && (
                          <Button size="sm" onClick={() => activate(r)} disabled={busy === r.user_id} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid={`oa-activate-${r.user_id}`}>
                            <CheckCircle2 className="w-3 h-3 mr-1" />Activate
                          </Button>
                        )}
                        {isAdmin && r.activated && (
                          <button onClick={() => deactivate(r)} disabled={busy === r.user_id} className="p-1.5 hover:bg-red-50 rounded-lg" title="Deactivate" data-testid={`oa-deact-${r.user_id}`}>
                            <Ban className="w-3.5 h-3.5 text-red-500" />
                          </button>
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

      {/* Detail drawer */}
      {selected && (
        <Dialog open={true} onOpenChange={() => setSelected(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="oa-detail">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 text-white flex items-center justify-center text-[11px] font-bold">
                  {(selected.user_name || "?").slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <p className="text-base font-black">{selected.user_name}</p>
                  <p className="text-[11px] text-stone-500 font-normal">{selected.user_email} · {selected.user_role}</p>
                </div>
              </DialogTitle>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-4 mt-3">
              {/* Passport */}
              <div className="bg-stone-50 rounded-xl border border-stone-200 p-4" data-testid="oa-passport-card">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-blue-600" />
                    <h3 className="text-xs font-bold text-stone-800">ID / Passport</h3>
                  </div>
                  {selected.passport_uploaded
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-stone-300" />}
                </div>
                {selected.passport_uploaded ? (
                  <>
                    <a href={`${process.env.REACT_APP_BACKEND_URL}${selected.passport_url}`} target="_blank" rel="noreferrer">
                      <img src={`${process.env.REACT_APP_BACKEND_URL}${selected.passport_url}`}
                           alt="passport" className="w-full h-36 object-cover rounded-lg border border-stone-200 cursor-pointer hover:opacity-80 transition" />
                    </a>
                    <p className="text-[10px] text-stone-500 mt-1.5 truncate">{selected.passport_filename}</p>
                    <p className="text-[10px] text-stone-400">Uploaded {fmtDate(selected.passport_uploaded_at)}</p>
                  </>
                ) : (
                  <div className="h-36 flex items-center justify-center text-stone-400 text-xs">Not uploaded</div>
                )}
              </div>

              {/* Address */}
              <div className="bg-stone-50 rounded-xl border border-stone-200 p-4" data-testid="oa-address-card">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Home className="w-4 h-4 text-purple-600" />
                    <h3 className="text-xs font-bold text-stone-800">Address Proof</h3>
                  </div>
                  {selected.address_proof_uploaded
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-stone-300" />}
                </div>
                {selected.address_proof_uploaded ? (
                  <>
                    <a href={`${process.env.REACT_APP_BACKEND_URL}${selected.address_proof_url}`} target="_blank" rel="noreferrer">
                      <img src={`${process.env.REACT_APP_BACKEND_URL}${selected.address_proof_url}`}
                           alt="address" className="w-full h-36 object-cover rounded-lg border border-stone-200 cursor-pointer hover:opacity-80 transition"
                           onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.insertAdjacentHTML("afterend", "<div class='h-36 flex items-center justify-center text-stone-400 text-xs border border-stone-200 rounded-lg'><span>PDF · click to view</span></div>"); }} />
                    </a>
                    <p className="text-[10px] text-stone-500 mt-1.5 truncate">{selected.address_proof_filename}</p>
                    <p className="text-[10px] text-stone-400">Uploaded {fmtDate(selected.address_proof_uploaded_at)}</p>
                  </>
                ) : (
                  <div className="h-36 flex items-center justify-center text-stone-400 text-xs">Not uploaded</div>
                )}
              </div>

              {/* HMRC */}
              <div className="bg-stone-50 rounded-xl border border-stone-200 p-4 col-span-2" data-testid="oa-hmrc-card">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Receipt className="w-4 h-4 text-amber-600" />
                    <h3 className="text-xs font-bold text-stone-800">HMRC Starter Checklist</h3>
                  </div>
                  {selected.hmrc_submitted
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-stone-300" />}
                </div>
                {selected.hmrc_submitted && selected.hmrc_data ? (
                  <div className="grid grid-cols-3 gap-2 text-[11px]">
                    <Row label="Last name" value={selected.hmrc_data.last_name || "—"} />
                    <Row label="First names" value={selected.hmrc_data.first_names || selected.hmrc_data.first_name || "—"} />
                    <Row label="Sex" value={selected.hmrc_data.sex || selected.hmrc_data.gender || "—"} />
                    <Row label="DOB" value={selected.hmrc_data.dob} />
                    <Row label="NI Number" value={selected.hmrc_data.ni_number || "not provided"} mono />
                    <Row label="Start Date" value={selected.hmrc_data.start_date} />
                    <Row label="Postcode" value={selected.hmrc_data.postcode} />
                    <Row label="Country" value={selected.hmrc_data.country || "UK"} />
                    <Row label="Statement" value={`Statement ${selected.hmrc_data.statement}`} />
                    <Row label="Another job" value={selected.hmrc_data.q8_another_job ? "yes" : "no"} />
                    <Row label="Pension income" value={selected.hmrc_data.q9_receives_pension ? "yes" : "no"} />
                    <Row label="Recent payments" value={selected.hmrc_data.q10_recent_payments ? "yes" : "no"} />
                    <Row label="Has loan" value={selected.hmrc_data.has_loan ? "yes" : "no"} />
                    <Row label="Still studying" value={selected.hmrc_data.still_studying ? "yes" : "no"} />
                    <Row label="Loan plans" value={(selected.hmrc_data.student_loan_plans || []).join(", ") || "—"} />
                    <div className="col-span-3"><Row label="Home address" value={selected.hmrc_data.home_address || selected.hmrc_data.address || "—"} /></div>
                    <div className="col-span-3"><Row label="Signed as" value={`${selected.hmrc_data.declaration_full_name || "—"} · ${selected.hmrc_data.declaration_date || "—"}`} /></div>
                    <div className="col-span-3"><Row label="Submitted" value={fmtDate(selected.hmrc_data.submitted_at)} /></div>
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">Not submitted</p>
                )}
              </div>

              {/* Contract */}
              <div className="bg-stone-50 rounded-xl border border-stone-200 p-4 col-span-2" data-testid="oa-contract-card">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <FileSignature className="w-4 h-4 text-indigo-600" />
                    <h3 className="text-xs font-bold text-stone-800">Employment Contract</h3>
                  </div>
                  {selected.contract_signed
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    : <XCircle className="w-4 h-4 text-stone-300" />}
                </div>
                {selected.contract_signed ? (
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-stone-600">Signed employment contract on file.</p>
                    {selected.contract_id && (
                      <code className="text-[10px] text-stone-500">Ref: {String(selected.contract_id).slice(0, 8)}</code>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">Awaiting signature — ensure a contract is sent from the Staff Contracts module.</p>
                )}
              </div>
            </div>

            {/* Footer actions */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t mt-4">
              <Button variant="outline" onClick={() => setSelected(null)}>Close</Button>
              {isAdmin && !selected.activated && (
                <Button onClick={() => activate(selected)} disabled={busy === selected.user_id} className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="oa-detail-activate">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  {selected.progress?.complete ? "Activate Account" : "Activate anyway (override)"}
                </Button>
              )}
              {isAdmin && selected.activated && (
                <Button onClick={() => deactivate(selected)} disabled={busy === selected.user_id} variant="outline" className="text-red-600 hover:bg-red-50" data-testid="oa-detail-deact">
                  <Ban className="w-3.5 h-3.5 mr-1" />Deactivate
                </Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

const Row = ({ label, value, mono }) => (
  <div className="bg-white rounded-md border border-stone-200 p-2">
    <p className="text-[9px] text-stone-400 uppercase tracking-wider">{label}</p>
    <p className={`text-[11px] font-semibold text-stone-800 ${mono ? "font-mono" : ""}`}>{value}</p>
  </div>
);
