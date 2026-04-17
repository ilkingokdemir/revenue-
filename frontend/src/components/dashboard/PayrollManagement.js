import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  RefreshCw, Plus, DollarSign, TrendingUp, TrendingDown, Wallet,
  CheckCircle2, XCircle, Trash2, Calendar, Users, PlayCircle, FileText,
  ArrowUpRight, ArrowDownRight,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "earnings",    label: "Earned Salaries", icon: DollarSign },
  { id: "runs",        label: "Payroll Runs",    icon: FileText },
  { id: "adjustments", label: "Adjustments",     icon: TrendingUp },
  { id: "advances",    label: "Cash Advances",   icon: Wallet },
];

const RUN_STATUS_STYLE = {
  draft:    "bg-stone-100 text-stone-600",
  approved: "bg-blue-100 text-blue-700",
  paid:     "bg-emerald-100 text-emerald-700",
};
const ADV_STATUS_STYLE = {
  pending:  "bg-amber-100 text-amber-700",
  approved: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700",
  repaid:   "bg-emerald-100 text-emerald-700",
};
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

export const PayrollManagement = ({ propertyId, user }) => {
  const [tab, setTab] = useState("earnings");
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [earnings, setEarnings] = useState(null);
  const [runs, setRuns] = useState([]);
  const [adjustments, setAdjustments] = useState([]);
  const [advances, setAdvances] = useState({ advances: [], kpis: {} });
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adjOpen, setAdjOpen] = useState(false);
  const [advOpen, setAdvOpen] = useState(false);
  const [adjForm, setAdjForm] = useState({ staff_id: "", staff_name: "", type: "bonus", amount: 0, reason: "" });
  const [advForm, setAdvForm] = useState({ staff_id: "", staff_name: "", amount: 0, reason: "" });

  const pid = propertyId || "all";
  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [e, r, a, adv, u] = await Promise.all([
        axios.get(`${API}/payroll/earnings/${pid}?year=${year}&month=${month}`),
        axios.get(`${API}/payroll/runs/${pid}`),
        axios.get(`${API}/payroll/adjustments/${pid}?year=${year}&month=${month}`),
        axios.get(`${API}/payroll/advances/${pid}`),
        axios.get(`${API}/users`).catch(() => ({ data: [] })),
      ]);
      setEarnings(e.data);
      setRuns(r.data.runs || []);
      setAdjustments(a.data.adjustments || []);
      setAdvances(adv.data);
      setStaffList(u.data || []);
    } catch (err) { /* silent */ }
    setLoading(false);
  }, [pid, year, month]);

  useEffect(() => { load(); }, [load]);

  const createRun = async () => {
    if (!window.confirm(`Create payroll run for ${MONTHS[month-1]} ${year}?`)) return;
    try {
      await axios.post(`${API}/payroll/runs/${pid}`, { year, month });
      toast.success("Payroll run created");
      setTab("runs");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create run");
    }
  };
  const approveRun = async (id) => {
    try { await axios.post(`${API}/payroll/runs/${pid}/${id}/approve`); toast.success("Approved"); load(); }
    catch { toast.error("Failed"); }
  };
  const markPaid = async (id) => {
    if (!window.confirm("Mark this run as paid? This will also clear any linked cash advances as repaid.")) return;
    try { await axios.post(`${API}/payroll/runs/${pid}/${id}/mark-paid`); toast.success("Marked paid"); load(); }
    catch { toast.error("Failed"); }
  };
  const deleteRun = async (id) => {
    if (!window.confirm("Delete this draft run?")) return;
    try { await axios.delete(`${API}/payroll/runs/${pid}/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const submitAdj = async () => {
    if (!adjForm.staff_id) { toast.error("Pick staff"); return; }
    if (!adjForm.amount || adjForm.amount <= 0) { toast.error("Amount required"); return; }
    try {
      await axios.post(`${API}/payroll/adjustments/${pid}`, { ...adjForm, year, month });
      toast.success("Adjustment added");
      setAdjOpen(false);
      setAdjForm({ staff_id: "", staff_name: "", type: "bonus", amount: 0, reason: "" });
      load();
    } catch { toast.error("Failed"); }
  };
  const deleteAdj = async (id) => {
    if (!window.confirm("Delete?")) return;
    try { await axios.delete(`${API}/payroll/adjustments/${pid}/${id}`); toast.success("Deleted"); load(); }
    catch { toast.error("Failed"); }
  };

  const submitAdv = async () => {
    if (!advForm.staff_id) { toast.error("Pick staff"); return; }
    if (!advForm.amount || advForm.amount <= 0) { toast.error("Amount required"); return; }
    try {
      await axios.post(`${API}/payroll/advances/${pid}`, advForm);
      toast.success("Advance requested");
      setAdvOpen(false);
      setAdvForm({ staff_id: "", staff_name: "", amount: 0, reason: "" });
      load();
    } catch { toast.error("Failed"); }
  };
  const approveAdv = async (id) => {
    try { await axios.post(`${API}/payroll/advances/${pid}/${id}/approve`); toast.success("Approved"); load(); }
    catch { toast.error("Failed"); }
  };
  const rejectAdv = async (id) => {
    try { await axios.post(`${API}/payroll/advances/${pid}/${id}/reject`); toast.success("Rejected"); load(); }
    catch { toast.error("Failed"); }
  };
  const repaidAdv = async (id) => {
    try { await axios.post(`${API}/payroll/advances/${pid}/${id}/mark-repaid`); toast.success("Marked repaid"); load(); }
    catch { toast.error("Failed"); }
  };

  const staffOptions = staffList.filter(s => ["receptionist","housekeeper","maintenance","manager","admin"].includes(s.role));

  return (
    <div className="space-y-5" data-testid="payroll-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="payroll-title">Payroll</h2>
        </div>
        <div className="flex items-center gap-2">
          <Select value={String(month)} onValueChange={v => setMonth(parseInt(v))}>
            <SelectTrigger className="h-8 w-32 text-xs" data-testid="month-select"><SelectValue /></SelectTrigger>
            <SelectContent>{MONTHS.map((m, i) => <SelectItem key={i+1} value={String(i+1)}>{m}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={String(year)} onValueChange={v => setYear(parseInt(v))}>
            <SelectTrigger className="h-8 w-24 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[2024, 2025, 2026, 2027].map(y => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* KPIs */}
      {earnings && (
        <div className="grid grid-cols-5 gap-3" data-testid="payroll-kpis">
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><Users className="w-4 h-4 mx-auto mb-1 text-stone-500" /><p className="text-2xl font-black text-stone-700">{earnings.total_staff}</p><p className="text-[10px] text-stone-500">Staff</p></div>
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><ArrowUpRight className="w-4 h-4 mx-auto mb-1 text-emerald-600" /><p className="text-2xl font-black text-emerald-700">£{earnings.total_gross.toFixed(0)}</p><p className="text-[10px] text-emerald-600">Gross</p></div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><TrendingUp className="w-4 h-4 mx-auto mb-1 text-blue-600" /><p className="text-2xl font-black text-blue-700">£{earnings.total_adjustments.toFixed(0)}</p><p className="text-[10px] text-blue-600">Adjustments</p></div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><ArrowDownRight className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">£{earnings.total_advances.toFixed(0)}</p><p className="text-[10px] text-amber-600">Advances</p></div>
          <div className="bg-violet-50 border-2 border-violet-300 rounded-xl p-4 text-center"><DollarSign className="w-4 h-4 mx-auto mb-1 text-violet-600" /><p className="text-2xl font-black text-violet-700">£{earnings.grand_total.toFixed(0)}</p><p className="text-[10px] text-violet-600">Net Payable</p></div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md ${tab === t.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
                <Icon className="w-3.5 h-3.5" />{t.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          {tab === "earnings" && (
            <Button size="sm" onClick={createRun} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="create-run-btn">
              <FileText className="w-4 h-4 mr-1.5" />Create Run for {MONTHS[month-1]}
            </Button>
          )}
          {tab === "adjustments" && (
            <Button size="sm" onClick={() => setAdjOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-adjustment-btn">
              <Plus className="w-4 h-4 mr-1.5" />New Adjustment
            </Button>
          )}
          {tab === "advances" && (
            <Button size="sm" onClick={() => setAdvOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-advance-btn">
              <Plus className="w-4 h-4 mr-1.5" />Request Advance
            </Button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>
      ) : (
        <>
          {/* EARNINGS TAB */}
          {tab === "earnings" && earnings && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="earnings-table">
              {earnings.rows.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No shifts recorded for {earnings.period}. Schedule shifts first.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Staff</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Role</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Days</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Rate</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-emerald-600">Gross</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-blue-600">Adj</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-amber-600">Adv</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-violet-600">Net</th>
                    </tr>
                  </thead>
                  <tbody>
                    {earnings.rows.map(r => (
                      <tr key={r.staff_id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`earn-row-${r.staff_id}`}>
                        <td className="py-2.5 px-3 font-semibold text-stone-700">{r.name}</td>
                        <td className="py-2.5 px-3 text-stone-600 capitalize">{r.role}</td>
                        <td className="py-2.5 px-3 text-center text-stone-700">{r.days_worked}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-stone-600">£{r.daily_rate}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-semibold text-emerald-700">£{r.gross.toFixed(2)}</td>
                        <td className={`py-2.5 px-3 text-right font-mono ${r.adjustments >= 0 ? "text-blue-700" : "text-red-600"}`}>£{r.adjustments.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-amber-700">£{r.advances.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-violet-700">£{r.net.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* RUNS TAB */}
          {tab === "runs" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="runs-table">
              {runs.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No payroll runs yet. Click "Create Run" from the Earnings tab.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Period</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Staff</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Gross</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Net</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Created</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map(r => (
                      <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`run-row-${r.id}`}>
                        <td className="py-2.5 px-3 font-semibold text-stone-700">{r.period}</td>
                        <td className="py-2.5 px-3 text-center text-stone-600">{r.total_staff}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-emerald-700">£{r.total_gross.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-violet-700">£{r.grand_total.toFixed(2)}</td>
                        <td className="py-2.5 px-3 text-center">
                          <Badge className={`${RUN_STATUS_STYLE[r.status]} text-[9px] capitalize`}>{r.status}</Badge>
                        </td>
                        <td className="py-2.5 px-3 text-[10px] text-stone-500">{r.created_at?.slice(0, 10)}</td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="inline-flex gap-0.5">
                            {r.status === "draft" && (
                              <button onClick={() => approveRun(r.id)} className="text-[10px] px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 font-semibold" data-testid={`approve-${r.id}`}>Approve</button>
                            )}
                            {r.status === "approved" && isAdmin && (
                              <button onClick={() => markPaid(r.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold" data-testid={`pay-${r.id}`}>Mark Paid</button>
                            )}
                            {r.status === "draft" && isAdmin && (
                              <button onClick={() => deleteRun(r.id)} className="p-1.5 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* ADJUSTMENTS TAB */}
          {tab === "adjustments" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="adjustments-table">
              {adjustments.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No adjustments for {MONTHS[month-1]} {year}.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Staff</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Type</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Amount</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Reason</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {adjustments.map(a => {
                      const isNeg = a.type === "deduction" || a.type === "tax";
                      return (
                        <tr key={a.id} className="border-b border-stone-100 hover:bg-stone-50/50">
                          <td className="py-2 px-3 font-semibold text-stone-700">{a.staff_name || a.staff_id}</td>
                          <td className="py-2 px-3"><Badge className={`text-[9px] capitalize ${isNeg ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>{a.type}</Badge></td>
                          <td className={`py-2 px-3 text-right font-mono font-semibold ${isNeg ? "text-red-600" : "text-emerald-700"}`}>{isNeg ? "-" : "+"}£{a.amount.toFixed(2)}</td>
                          <td className="py-2 px-3 text-stone-600">{a.reason}</td>
                          <td className="py-2 px-3 text-[10px] text-stone-500">{a.created_at?.slice(0, 10)}</td>
                          <td className="py-2 px-3 text-right"><button onClick={() => deleteAdj(a.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* ADVANCES TAB */}
          {tab === "advances" && (
            <>
              <div className="grid grid-cols-5 gap-3 mb-3">
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-center"><p className="text-xl font-black text-amber-700">{advances.kpis.pending || 0}</p><p className="text-[9px] text-amber-600">Pending</p></div>
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-center"><p className="text-xl font-black text-blue-700">{advances.kpis.approved || 0}</p><p className="text-[9px] text-blue-600">Approved</p></div>
                <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center"><p className="text-xl font-black text-red-700">{advances.kpis.rejected || 0}</p><p className="text-[9px] text-red-600">Rejected</p></div>
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center"><p className="text-xl font-black text-emerald-700">{advances.kpis.repaid || 0}</p><p className="text-[9px] text-emerald-600">Repaid</p></div>
                <div className="bg-violet-50 border border-violet-200 rounded-xl p-3 text-center"><p className="text-xl font-black text-violet-700">£{(advances.kpis.total_outstanding || 0).toFixed(0)}</p><p className="text-[9px] text-violet-600">Outstanding</p></div>
              </div>
              <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="advances-table">
                {advances.advances.length === 0 ? (
                  <p className="text-center text-sm text-stone-400 py-12">No advances yet.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50 border-b border-stone-200">
                      <tr>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Staff</th>
                        <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Amount</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Reason</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Requested</th>
                        <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                        <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {advances.advances.map(a => (
                        <tr key={a.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`adv-row-${a.id}`}>
                          <td className="py-2 px-3 font-semibold text-stone-700">{a.staff_name || a.staff_id}</td>
                          <td className="py-2 px-3 text-right font-mono font-semibold text-amber-700">£{a.amount.toFixed(2)}</td>
                          <td className="py-2 px-3 text-stone-600 max-w-xs truncate">{a.reason}</td>
                          <td className="py-2 px-3 text-[10px] text-stone-500">{a.requested_at?.slice(0, 10)}</td>
                          <td className="py-2 px-3 text-center"><Badge className={`${ADV_STATUS_STYLE[a.status]} text-[9px] capitalize`}>{a.status}</Badge></td>
                          <td className="py-2 px-3 text-right">
                            <div className="inline-flex gap-0.5">
                              {a.status === "pending" && (
                                <>
                                  <button onClick={() => approveAdv(a.id)} className="text-[10px] px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 font-semibold" data-testid={`approve-adv-${a.id}`}>Approve</button>
                                  <button onClick={() => rejectAdv(a.id)} className="text-[10px] px-2 py-1 bg-red-50 text-red-700 rounded hover:bg-red-100 font-semibold">Reject</button>
                                </>
                              )}
                              {a.status === "approved" && !a.repaid && (
                                <button onClick={() => repaidAdv(a.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold">Mark Repaid</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* Adjustment Dialog */}
      <Dialog open={adjOpen} onOpenChange={setAdjOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>New Adjustment</DialogTitle>
            <DialogDescription>Add a bonus, overtime, commission, deduction, or tax line to a staff member for {MONTHS[month-1]} {year}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-stone-600">Staff</label>
              <Select value={adjForm.staff_id} onValueChange={v => {
                const s = staffOptions.find(x => x.id === v);
                setAdjForm({ ...adjForm, staff_id: v, staff_name: s?.name || "" });
              }}>
                <SelectTrigger data-testid="adj-staff-select"><SelectValue placeholder="Select staff" /></SelectTrigger>
                <SelectContent>
                  {staffOptions.map(s => <SelectItem key={s.id} value={s.id}>{s.name} ({s.role})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Type</label>
                <Select value={adjForm.type} onValueChange={v => setAdjForm({ ...adjForm, type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bonus">Bonus</SelectItem>
                    <SelectItem value="overtime">Overtime</SelectItem>
                    <SelectItem value="commission">Commission</SelectItem>
                    <SelectItem value="benefit">Benefit</SelectItem>
                    <SelectItem value="deduction">Deduction (−)</SelectItem>
                    <SelectItem value="tax">Tax (−)</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Amount (£)</label>
                <Input type="number" step="0.01" value={adjForm.amount} onChange={e => setAdjForm({ ...adjForm, amount: parseFloat(e.target.value) || 0 })} data-testid="adj-amount-input" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Reason</label>
              <Textarea value={adjForm.reason} onChange={e => setAdjForm({ ...adjForm, reason: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setAdjOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitAdj} data-testid="adj-submit-btn">Add</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Advance Dialog */}
      <Dialog open={advOpen} onOpenChange={setAdvOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Request Cash Advance</DialogTitle>
            <DialogDescription>Approved advances are automatically deducted from the next payroll run.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-stone-600">Staff</label>
              <Select value={advForm.staff_id} onValueChange={v => {
                const s = staffOptions.find(x => x.id === v);
                setAdvForm({ ...advForm, staff_id: v, staff_name: s?.name || "" });
              }}>
                <SelectTrigger data-testid="adv-staff-select"><SelectValue placeholder="Select staff" /></SelectTrigger>
                <SelectContent>
                  {staffOptions.map(s => <SelectItem key={s.id} value={s.id}>{s.name} ({s.role})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Amount (£)</label>
              <Input type="number" step="0.01" value={advForm.amount} onChange={e => setAdvForm({ ...advForm, amount: parseFloat(e.target.value) || 0 })} data-testid="adv-amount-input" />
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Reason</label>
              <Textarea value={advForm.reason} onChange={e => setAdvForm({ ...advForm, reason: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setAdvOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitAdv} data-testid="adv-submit-btn">Request</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
