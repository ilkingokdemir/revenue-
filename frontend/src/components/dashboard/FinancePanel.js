import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const currency = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/* ── FINANCE DASHBOARD ── */
const DashboardTab = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [fromDate, setFromDate] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`; });
  const [toDate, setToDate] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${new Date(d.getFullYear(), d.getMonth()+1, 0).getDate()}`; });

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/finance/dashboard/${propertyId}?from_date=${fromDate}&to_date=${toDate}`);
      setData(d);
    } catch { toast.error("Failed to load finance data"); }
  }, [propertyId, fromDate, toDate]);
  useEffect(() => { load(); }, [load]);

  const o = data?.overview || {};
  const kpis = [
    { label: "GROSS", value: currency(o.gross), color: "text-stone-800" },
    { label: "ROOM", value: currency(o.room_revenue), color: "text-blue-600" },
    { label: "ADR", value: currency(o.adr), color: "text-stone-600" },
    { label: "COMM.", value: currency(o.commission), color: "text-violet-600" },
    { label: "EXPENSES", value: currency(o.expenses), color: "text-orange-600" },
    { label: "PAYROLL", value: currency(o.payroll), color: "text-red-500" },
    { label: "TOTAL COSTS", value: currency(o.total_costs), color: "text-stone-700" },
    { label: "NET", value: `${o.net >= 0 ? "+" : ""}${currency(o.net)}`, color: o.net >= 0 ? "text-emerald-600" : "text-red-600" },
  ];

  return (
    <div data-testid="finance-dashboard-tab">
      <div className="bg-gradient-to-br from-rose-50 to-orange-50 border border-rose-100 rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-2 mb-1"><span className="w-2 h-2 rounded-full bg-red-500" /><span className="text-[11px] font-bold uppercase tracking-wider text-red-600">Finance Dashboard</span></div>
        <h2 className="text-2xl font-bold text-stone-900 mb-1">Canonical profit overview</h2>
        <p className="text-sm text-stone-500 mb-4">Room revenue stays canonical across finance and reports.</p>
        <div className="flex items-center gap-3 flex-wrap">
          <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-40 h-9 text-sm bg-white" data-testid="fin-from-date" />
          <span className="text-stone-400">to</span>
          <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-40 h-9 text-sm bg-white" data-testid="fin-to-date" />
          <button onClick={load} className="px-4 py-2 bg-white border border-stone-200 rounded-lg text-sm font-medium text-stone-600 hover:bg-stone-50" data-testid="fin-apply-btn">Apply</button>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center"><svg className="w-5 h-5 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg></div>
          <div><h3 className="font-bold text-stone-800">Overview</h3><p className="text-xs text-stone-400">Revenue and cost snapshot for the selected period</p></div>
        </div>
        <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
          {kpis.map(k => (
            <div key={k.label} className="text-center" data-testid={`fin-kpi-${k.label.toLowerCase().replace(/[^a-z]/g, '')}`}>
              <div className="text-[10px] font-bold text-stone-400 uppercase tracking-wider mb-1">{k.label}</div>
              <div className={`text-lg font-bold ${k.color}`}>{data ? k.value : "..."}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-stone-200 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center"><svg className="w-5 h-5 text-red-600" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg></div>
            <div>
              <h3 className="font-bold text-stone-800 text-sm">OPERATING COSTS</h3>
              <p className="text-xs text-stone-400">{data?.operating_costs?.length || 0} items &middot; {currency(o.total_costs)}</p>
            </div>
          </div>
          {(data?.operating_costs || []).length === 0 ? <p className="text-sm text-stone-400 text-center py-4">No expenses recorded</p> : (
            <div className="space-y-2">{data.operating_costs.map((c, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0">
                <div className="flex items-center gap-2">
                  <Badge className="text-[10px] bg-orange-50 text-orange-600 capitalize">{c.category}</Badge>
                  <span className="text-xs text-stone-400">{c.count} items</span>
                </div>
                <span className="text-sm font-semibold text-stone-700">{currency(c.total)}</span>
              </div>
            ))}</div>
          )}
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center"><svg className="w-5 h-5 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg></div>
            <div>
              <h3 className="font-bold text-stone-800 text-sm">ROOM REVENUE</h3>
              <p className="text-xs text-stone-400">{data?.revenue_sources?.length || 0} sources &middot; {currency(o.room_revenue)}</p>
            </div>
          </div>
          {(data?.revenue_sources || []).length === 0 ? <p className="text-sm text-stone-400 text-center py-4">No revenue data</p> : (
            <div className="space-y-2">{data.revenue_sources.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-stone-700 font-medium">{s.source}</span>
                  <span className="text-xs text-stone-400">{s.count} bookings</span>
                </div>
                <span className="text-sm font-semibold text-emerald-600">{currency(s.revenue)}</span>
              </div>
            ))}</div>
          )}
        </div>
      </div>
      {data && <div className="mt-4 text-center"><span className="text-sm font-semibold text-stone-600">Operating Profit/Loss: <span className={o.net >= 0 ? "text-emerald-600" : "text-red-600"}>{currency(o.net)}</span> (Margin: {o.margin}%)</span></div>}
    </div>
  );
};

/* ── EARNED SALARIES ── */
const EarnedSalariesTab = ({ propertyId }) => {
  const [data, setData] = useState({ entries: [], stats: {} });
  const [fromDate, setFromDate] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`; });
  const [toDate, setToDate] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${new Date(d.getFullYear(), d.getMonth()+1, 0).getDate()}`; });

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/finance/earned-salaries/${propertyId}?from_date=${fromDate}&to_date=${toDate}`);
      setData(d);
    } catch { toast.error("Failed"); }
  }, [propertyId, fromDate, toDate]);
  useEffect(() => { load(); }, [load]);

  const s = data.stats;
  const stats = [
    { label: "Staff Count", value: s.staff_count || 0, color: "text-blue-600" },
    { label: "Working Days", value: s.working_days || 0, color: "text-stone-700" },
    { label: "Total Rows", value: s.total_rows || 0, color: "text-stone-500" },
    { label: "Total Earned", value: currency(s.total_earned), color: "text-emerald-600" },
  ];

  // Group entries by staff
  const staffMap = {};
  for (const e of data.entries) {
    const k = e.staff_id || e.staff_name;
    if (!staffMap[k]) staffMap[k] = { name: e.staff_name, role: e.role, property_id: e.property_id, days: {}, total: 0 };
    staffMap[k].days[e.date] = (staffMap[k].days[e.date] || 0) + e.amount;
    staffMap[k].total += e.amount;
  }

  // Get unique dates
  const allDates = [...new Set(data.entries.map(e => e.date))].sort();

  return (
    <div data-testid="earned-salaries-tab">
      <h2 className="text-lg font-bold text-stone-800 mb-1">Earned Salaries</h2>
      <p className="text-sm text-stone-500 mb-4">Day-by-day salary accrual breakdown</p>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-36 h-9 text-sm" data-testid="sal-from" />
        <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-36 h-9 text-sm" data-testid="sal-to" />
        <button onClick={load} className="px-3 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="sal-filter-btn">Filter</button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {stats.map(st => (
          <div key={st.label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`sal-stat-${st.label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="text-xs text-stone-400 uppercase font-semibold">{st.label}</div>
            <div className={`text-xl font-bold mt-1 ${st.color}`}>{st.value}</div>
          </div>
        ))}
      </div>
      {Object.keys(staffMap).length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No salary records for this period</div> : (
        <div className="border border-stone-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="bg-stone-50 border-b">
                <th className="px-3 py-2 text-left font-semibold text-stone-500 sticky left-0 bg-stone-50 z-10 min-w-[140px]">STAFF</th>
                <th className="px-3 py-2 text-left font-semibold text-stone-500">ROLE</th>
                <th className="px-3 py-2 text-left font-semibold text-stone-500">BRANCH</th>
                {allDates.map(d => <th key={d} className="px-2 py-2 text-center font-semibold text-stone-400 min-w-[60px]">{new Date(d + "T00:00:00").toLocaleDateString("en", { weekday: "short", day: "numeric" })}</th>)}
                <th className="px-3 py-2 text-right font-bold text-stone-700">TOTAL</th>
              </tr></thead>
              <tbody>{Object.entries(staffMap).map(([k, v]) => (
                <tr key={k} className="border-b border-stone-100 hover:bg-stone-50/50">
                  <td className="px-3 py-2 font-medium text-stone-800 sticky left-0 bg-white z-10">{v.name}</td>
                  <td className="px-3 py-2"><Badge className="text-[9px] bg-blue-50 text-blue-600 capitalize">{v.role}</Badge></td>
                  <td className="px-3 py-2 text-stone-500 text-[10px]">{v.property_id}</td>
                  {allDates.map(d => <td key={d} className="px-2 py-2 text-center text-stone-600">{v.days[d] ? `${v.days[d].toFixed(2)}` : ""}</td>)}
                  <td className="px-3 py-2 text-right font-bold text-stone-800">{currency(v.total)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

/* ── PAYROLL RUNS ── */
const PayrollRunsTab = ({ propertyId }) => {
  const [data, setData] = useState({ runs: [], config: {} });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ period_start: "", period_end: "", staff_count: 0, gross_total: 0, deductions: 0, notes: "" });

  const load = useCallback(async () => {
    try { const { data: d } = await axios.get(`${API}/finance/payroll-runs/${propertyId}`); setData(d); } catch { toast.error("Failed"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/finance/payroll-runs`, { ...form, property_id: propertyId, net_total: form.gross_total - form.deductions });
      toast.success("Payroll run created"); setShowCreate(false); load();
    } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status) => {
    try { await axios.put(`${API}/finance/payroll-runs/${id}`, { status }); toast.success("Updated"); load(); } catch { toast.error("Failed"); }
  };

  const cfg = data.config || {};
  const statusColors = { draft: "bg-stone-100 text-stone-500", pending: "bg-amber-100 text-amber-700", approved: "bg-blue-100 text-blue-700", paid: "bg-emerald-100 text-emerald-700" };

  return (
    <div data-testid="payroll-runs-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Payroll Runs</h2><p className="text-sm text-stone-500">Manage payroll periods and automation</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-payroll-btn">+ New Run</button>
      </div>
      <div className="bg-gradient-to-r from-stone-800 to-stone-900 rounded-2xl p-5 mb-6 text-white">
        <h3 className="text-sm font-bold mb-3">Payroll Automation</h3>
        <div className="flex items-center gap-6 text-sm">
          <div><span className="text-stone-400 text-xs">Mode</span><div className="font-semibold capitalize">{cfg.mode || "Pause"}</div></div>
          <div><span className="text-stone-400 text-xs">Frequency</span><div className="font-semibold capitalize">{cfg.frequency || "Monthly"}</div></div>
          <div><span className="text-stone-400 text-xs">Next Run</span><div className="font-semibold">{cfg.next_run || "Not scheduled"}</div></div>
        </div>
      </div>
      {data.runs.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No payroll runs yet</div> : (
        <div className="border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="bg-stone-50 border-b"><th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Period</th><th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Staff</th><th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Gross</th><th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Net</th><th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Status</th><th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Source</th><th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Actions</th></tr></thead>
            <tbody>{data.runs.map(r => (
              <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`payroll-row-${r.id}`}>
                <td className="px-4 py-2.5 text-stone-700 font-medium">{r.period_start} — {r.period_end}</td>
                <td className="px-4 py-2.5 text-stone-600">{r.staff_count}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-stone-700">{currency(r.gross_total)}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-emerald-600">{currency(r.net_total)}</td>
                <td className="px-4 py-2.5"><Badge className={`text-[10px] ${statusColors[r.status] || "bg-stone-100"}`}>{r.status}</Badge></td>
                <td className="px-4 py-2.5 text-stone-500 text-xs capitalize">{r.source}</td>
                <td className="px-4 py-2.5 flex gap-1">
                  {r.status === "draft" && <button onClick={() => updateStatus(r.id, "approved")} className="text-xs text-blue-600 hover:underline">Approve</button>}
                  {r.status === "approved" && <button onClick={() => updateStatus(r.id, "paid")} className="text-xs text-emerald-600 hover:underline">Pay</button>}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="payroll-dialog"><DialogHeader><DialogTitle>New Payroll Run</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Period Start</label><Input type="date" value={form.period_start} onChange={e => setForm({...form, period_start: e.target.value})} data-testid="pr-start" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Period End</label><Input type="date" value={form.period_end} onChange={e => setForm({...form, period_end: e.target.value})} data-testid="pr-end" /></div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Staff</label><Input type="number" value={form.staff_count} onChange={e => setForm({...form, staff_count: parseInt(e.target.value)||0})} data-testid="pr-staff" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Gross</label><Input type="number" value={form.gross_total} onChange={e => setForm({...form, gross_total: parseFloat(e.target.value)||0})} data-testid="pr-gross" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Deductions</label><Input type="number" value={form.deductions} onChange={e => setForm({...form, deductions: parseFloat(e.target.value)||0})} data-testid="pr-deduct" /></div>
            </div>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="pr-save">Create Run</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── ADJUSTMENTS ── */
const AdjustmentsTab = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ employee_name: "", type: "addition", category: "bonus", amount: 0, schedule: "one-time" });
  const [filterType, setFilterType] = useState("");

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/finance/adjustments/${propertyId}${filterType ? `?adj_type=${filterType}` : ""}`); setItems(data); } catch { toast.error("Failed"); }
  }, [propertyId, filterType]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/finance/adjustments`, { ...form, property_id: propertyId }); toast.success("Adjustment created"); setShowCreate(false); load(); } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/finance/adjustments/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div data-testid="adjustments-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Payroll Adjustments</h2><p className="text-sm text-stone-500">Employee bonuses, allowances and deductions</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-adj-btn">+ New Adjustment</button>
      </div>
      <div className="flex gap-2 mb-4">
        {["", "addition", "deduction"].map(t => (
          <button key={t} onClick={() => setFilterType(t)} className={`px-3 py-1.5 text-xs font-medium rounded-lg ${filterType === t ? "bg-stone-800 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`adj-filter-${t||"all"}`}>{t || "All"}</button>
        ))}
      </div>
      {items.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No adjustments</div> : (
        <div className="border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm"><thead><tr className="bg-stone-50 border-b">
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Employee</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Type</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Category</th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Amount</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Schedule</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Status</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Actions</th>
          </tr></thead><tbody>{items.map(a => (
            <tr key={a.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`adj-row-${a.id}`}>
              <td className="px-4 py-2.5 font-medium text-stone-800">{a.employee_name}</td>
              <td className="px-4 py-2.5"><Badge className={`text-[10px] ${a.type === "addition" ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-600"}`}>{a.type}</Badge></td>
              <td className="px-4 py-2.5 text-stone-600 capitalize">{a.category}</td>
              <td className="px-4 py-2.5 text-right font-semibold">{currency(a.amount)}</td>
              <td className="px-4 py-2.5 text-stone-500 capitalize text-xs">{a.schedule}</td>
              <td className="px-4 py-2.5"><Badge className="text-[10px] bg-emerald-50 text-emerald-600">{a.status}</Badge></td>
              <td className="px-4 py-2.5"><button onClick={() => del(a.id)} className="text-xs text-red-500 hover:underline">Delete</button></td>
            </tr>
          ))}</tbody></table>
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="adj-dialog"><DialogHeader><DialogTitle>New Adjustment</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.employee_name} onChange={e => setForm({...form, employee_name: e.target.value})} placeholder="Employee name" data-testid="adj-employee" />
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.type} onValueChange={v => setForm({...form, type: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="addition">Addition</SelectItem><SelectItem value="deduction">Deduction</SelectItem></SelectContent></Select>
              <Select value={form.category} onValueChange={v => setForm({...form, category: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="bonus">Bonus</SelectItem><SelectItem value="transport">Transport</SelectItem><SelectItem value="meal">Meal</SelectItem><SelectItem value="overtime">Overtime</SelectItem><SelectItem value="holiday">Holiday</SelectItem><SelectItem value="tips">Tips</SelectItem><SelectItem value="deduction">Deduction</SelectItem></SelectContent></Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input type="number" value={form.amount} onChange={e => setForm({...form, amount: parseFloat(e.target.value)||0})} placeholder="Amount" data-testid="adj-amount" />
              <Select value={form.schedule} onValueChange={v => setForm({...form, schedule: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="one-time">One-time</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="weekly">Weekly</SelectItem></SelectContent></Select>
            </div>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="adj-save">Create Adjustment</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── CASH ADVANCES ── */
const CashAdvancesTab = ({ propertyId }) => {
  const [data, setData] = useState({ advances: [], stats: {} });
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ employee_name: "", amount: 0, notes: "" });

  const load = useCallback(async () => {
    try { const { data: d } = await axios.get(`${API}/finance/cash-advances/${propertyId}`); setData(d); } catch { toast.error("Failed"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/finance/cash-advances`, { ...form, property_id: propertyId }); toast.success("Cash advance created"); setShowCreate(false); load(); } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status) => {
    try { await axios.put(`${API}/finance/cash-advances/${id}`, { status }); toast.success("Updated"); load(); } catch { toast.error("Failed"); }
  };

  const s = data.stats || {};
  const statCards = [
    { label: "Total Pending", value: currency(s.total_pending), color: "text-orange-600" },
    { label: "Total Deducted", value: currency(s.total_deducted), color: "text-red-600" },
    { label: "Total Cancelled", value: currency(s.total_cancelled), color: "text-stone-500" },
  ];

  return (
    <div data-testid="cash-advances-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Cash Advances</h2><p className="text-sm text-stone-500">Manage employee cash advances and repayments</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-advance-btn">+ New Advance</button>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-6">
        {statCards.map(c => (<div key={c.label} className="bg-white border border-stone-200 rounded-xl p-4"><div className="text-xs text-stone-400 uppercase font-semibold">{c.label}</div><div className={`text-xl font-bold mt-1 ${c.color}`}>{c.value}</div></div>))}
      </div>
      {data.advances.length === 0 ? (
        <div className="text-center py-16 text-stone-400"><svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/></svg><p className="font-medium">No cash advances</p></div>
      ) : (
        <div className="border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm"><thead><tr className="bg-stone-50 border-b">
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Employee</th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Amount</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Date</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Status</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Notes</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Actions</th>
          </tr></thead><tbody>{data.advances.map(a => (
            <tr key={a.id} className="border-b border-stone-100" data-testid={`advance-row-${a.id}`}>
              <td className="px-4 py-2.5 font-medium text-stone-800">{a.employee_name}</td>
              <td className="px-4 py-2.5 text-right font-semibold">{currency(a.amount)}</td>
              <td className="px-4 py-2.5 text-stone-600">{a.date}</td>
              <td className="px-4 py-2.5"><Badge className={`text-[10px] ${a.status === "pending" ? "bg-amber-100 text-amber-700" : a.status === "deducted" ? "bg-red-100 text-red-700" : "bg-stone-100 text-stone-500"}`}>{a.status}</Badge></td>
              <td className="px-4 py-2.5 text-stone-500 text-xs">{a.notes}</td>
              <td className="px-4 py-2.5 flex gap-1">
                {a.status === "pending" && <><button onClick={() => updateStatus(a.id, "deducted")} className="text-xs text-red-600 hover:underline">Deduct</button><button onClick={() => updateStatus(a.id, "cancelled")} className="text-xs text-stone-400 hover:underline ml-2">Cancel</button></>}
              </td>
            </tr>
          ))}</tbody></table>
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm" data-testid="advance-dialog"><DialogHeader><DialogTitle>New Cash Advance</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.employee_name} onChange={e => setForm({...form, employee_name: e.target.value})} placeholder="Employee name" data-testid="adv-employee" />
            <Input type="number" value={form.amount} onChange={e => setForm({...form, amount: parseFloat(e.target.value)||0})} placeholder="Amount" data-testid="adv-amount" />
            <Textarea value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Notes" rows={2} data-testid="adv-notes" />
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="adv-save">Create Advance</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── ADJUSTMENT CATEGORIES ── */
const CategoriesTab = () => {
  const [cats, setCats] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", calc_type: "fixed", type: "addition" });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/finance/adjustment-categories`); setCats(data); } catch { toast.error("Failed"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/finance/adjustment-categories`, { ...form, order: cats.length + 1 }); toast.success("Category created"); setShowCreate(false); load(); } catch { toast.error("Failed"); }
  };

  const toggle = async (id, status) => {
    try { await axios.put(`${API}/finance/adjustment-categories/${id}`, { status: status === "active" ? "disabled" : "active" }); load(); } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/finance/adjustment-categories/${id}`); toast.success("Deleted"); load(); } catch (e) { toast.error(e.response?.data?.detail || "Cannot delete"); } };

  const additions = cats.filter(c => c.type === "addition");
  const deductions = cats.filter(c => c.type === "deduction");

  const CatTable = ({ title, items, color }) => (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3"><span className={`w-2.5 h-2.5 rounded-full ${color}`} /><span className="font-bold text-stone-800">{title}</span></div>
      <div className="border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm"><thead><tr className="bg-stone-50 border-b">
          <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Code</th>
          <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Name</th>
          <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500">Calc. Type</th>
          <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500">Status</th>
          <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500">Order</th>
          <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Actions</th>
        </tr></thead><tbody>{items.map(c => (
          <tr key={c.id} className="border-b border-stone-100" data-testid={`cat-row-${c.id}`}>
            <td className="px-4 py-2.5"><code className="bg-stone-100 px-2 py-0.5 rounded text-xs">{c.code}</code></td>
            <td className="px-4 py-2.5 font-medium text-stone-800">{c.name} {c.is_system && <span className="text-[10px] text-blue-500">(System)</span>}</td>
            <td className="px-4 py-2.5 text-center"><span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-600 inline-flex items-center justify-center text-xs font-bold">£</span></td>
            <td className="px-4 py-2.5 text-center"><Badge className={`text-[10px] ${c.status === "active" ? "bg-emerald-50 text-emerald-600" : "bg-stone-100 text-stone-400"}`}>{c.status}</Badge></td>
            <td className="px-4 py-2.5 text-center text-stone-500">{c.order}</td>
            <td className="px-4 py-2.5 text-right space-x-2">
              {!c.is_system && <><button onClick={() => toggle(c.id, c.status)} className="text-xs text-blue-600 hover:underline">{c.status === "active" ? "Disable" : "Enable"}</button><button onClick={() => del(c.id)} className="text-xs text-red-500 hover:underline">Delete</button></>}
              {c.is_system && <span className="text-xs text-stone-400">Edit</span>}
            </td>
          </tr>
        ))}</tbody></table>
      </div>
    </div>
  );

  return (
    <div data-testid="categories-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Adjustment Categories</h2><p className="text-sm text-stone-500">Manage payroll addition and deduction categories</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-category-btn">+ New Category</button>
      </div>
      <CatTable title="Additions" items={additions} color="bg-emerald-500" />
      {deductions.length > 0 && <CatTable title="Deductions" items={deductions} color="bg-red-500" />}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-sm" data-testid="cat-dialog"><DialogHeader><DialogTitle>New Category</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.code} onChange={e => setForm({...form, code: e.target.value})} placeholder="Code (e.g. transport)" data-testid="cat-code" />
            <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Display name" data-testid="cat-name" />
            <Select value={form.type} onValueChange={v => setForm({...form, type: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="addition">Addition</SelectItem><SelectItem value="deduction">Deduction</SelectItem></SelectContent></Select>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="cat-save">Create Category</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── EXPENSES ── */
const ExpensesTab = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ date: "", category: "other", details: "", vendor: "", amount: 0, status: "pending" });
  const [filterStatus, setFilterStatus] = useState("");
  const [month, setMonth] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; });

  const load = useCallback(async () => {
    try {
      const [y, m] = month.split("-");
      const from = `${y}-${m}-01`;
      const to = `${y}-${m}-${new Date(parseInt(y), parseInt(m), 0).getDate()}`;
      const params = new URLSearchParams({ from_date: from, to_date: to });
      if (filterStatus) params.append("status", filterStatus);
      const { data } = await axios.get(`${API}/finance/expenses/${propertyId}?${params}`);
      setItems(data);
    } catch { toast.error("Failed"); }
  }, [propertyId, month, filterStatus]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/finance/expenses`, { ...form, property_id: propertyId }); toast.success("Expense added"); setShowCreate(false); load(); } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status) => { try { await axios.put(`${API}/finance/expenses/${id}`, { status }); toast.success("Updated"); load(); } catch { toast.error("Failed"); } };
  const del = async (id) => { try { await axios.delete(`${API}/finance/expenses/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  const navMonth = (dir) => {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 1 + dir, 1);
    setMonth(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
  };

  const catColors = { commission: "bg-blue-100 text-blue-700", rent: "bg-red-100 text-red-700", laundry: "bg-violet-100 text-violet-700", cleaning_products: "bg-emerald-100 text-emerald-700", complementary: "bg-amber-100 text-amber-700", other: "bg-stone-100 text-stone-600" };

  return (
    <div data-testid="expenses-tab">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div><h2 className="text-lg font-bold text-stone-800">Expenses</h2><p className="text-sm text-stone-500">Track business expenses</p></div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => navMonth(-1)} className="p-1.5 hover:bg-stone-100 rounded-lg text-stone-500"><svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg></button>
          <span className="text-sm font-semibold text-stone-700 px-2" data-testid="expenses-month">{new Date(month + "-01").toLocaleDateString("en", { month: "long", year: "numeric" })}</span>
          <button onClick={() => navMonth(1)} className="p-1.5 hover:bg-stone-100 rounded-lg text-stone-500"><svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg></button>
          {["", "pending", "paid", "overdue"].map(s => (
            <button key={s} onClick={() => setFilterStatus(s)} className={`px-2.5 py-1 text-xs font-medium rounded-lg ${filterStatus === s ? "bg-stone-800 text-white" : "border border-stone-200 text-stone-500 hover:bg-stone-50"}`} data-testid={`exp-filter-${s||"all"}`}>{s || "All"}</button>
          ))}
          <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-expense-btn">+ Add Expense</button>
        </div>
      </div>
      {items.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No expenses for this month</div> : (
        <div className="border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm"><thead><tr className="bg-stone-50 border-b">
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Date</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Branch</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Category</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Details</th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Amount</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500">Status</th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500">Actions</th>
          </tr></thead><tbody>{items.map(e => (
            <tr key={e.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`exp-row-${e.id}`}>
              <td className="px-4 py-2.5 text-stone-700">{e.date}</td>
              <td className="px-4 py-2.5 text-stone-500 text-xs">{e.property_id}</td>
              <td className="px-4 py-2.5"><Badge className={`text-[10px] capitalize ${catColors[e.category] || catColors.other}`}>{e.category}</Badge></td>
              <td className="px-4 py-2.5 text-stone-600 text-xs">{e.vendor || e.details || "—"}</td>
              <td className="px-4 py-2.5 text-right font-semibold text-stone-800">{currency(e.amount)}</td>
              <td className="px-4 py-2.5"><Badge className={`text-[10px] ${e.status === "paid" ? "bg-emerald-50 text-emerald-600" : e.status === "pending" ? "bg-amber-50 text-amber-600" : "bg-red-50 text-red-600"}`}>{e.status}</Badge></td>
              <td className="px-4 py-2.5 text-right space-x-1">
                {e.status === "pending" && <button onClick={() => updateStatus(e.id, "paid")} className="px-2 py-1 bg-emerald-500 text-white text-xs rounded">Pay</button>}
                <button onClick={() => del(e.id)} className="text-xs text-red-500 hover:underline">Delete</button>
              </td>
            </tr>
          ))}</tbody></table>
        </div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="expense-dialog"><DialogHeader><DialogTitle>Add Expense</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input type="date" value={form.date} onChange={e => setForm({...form, date: e.target.value})} data-testid="exp-date" />
            <Select value={form.category} onValueChange={v => setForm({...form, category: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent>
              <SelectItem value="rent">Rent</SelectItem><SelectItem value="commission">Commission</SelectItem><SelectItem value="laundry">Laundry</SelectItem>
              <SelectItem value="cleaning_products">Cleaning Products</SelectItem><SelectItem value="complementary">Complementary</SelectItem><SelectItem value="insurance">Insurance</SelectItem><SelectItem value="utilities">Utilities</SelectItem><SelectItem value="other">Other</SelectItem>
            </SelectContent></Select>
            <Input value={form.vendor} onChange={e => setForm({...form, vendor: e.target.value})} placeholder="Vendor / Supplier" data-testid="exp-vendor" />
            <Input type="number" value={form.amount} onChange={e => setForm({...form, amount: parseFloat(e.target.value)||0})} placeholder="Amount" data-testid="exp-amount" />
            <Input value={form.details} onChange={e => setForm({...form, details: e.target.value})} placeholder="Details / Notes" data-testid="exp-details" />
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="exp-save">Add Expense</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── RECURRING EXPENSES ── */
const RecurringExpensesTab = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", amount: 0, frequency: "monthly", category: "rent", next_run: "" });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/finance/recurring-expenses/${propertyId}`); setItems(data); } catch { toast.error("Failed"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try { await axios.post(`${API}/finance/recurring-expenses`, { ...form, property_id: propertyId }); toast.success("Created"); setShowCreate(false); load(); } catch { toast.error("Failed"); }
  };

  const toggle = async (id, mode) => {
    try { await axios.put(`${API}/finance/recurring-expenses/${id}`, { mode: mode === "play" ? "pause" : "play" }); load(); } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/finance/recurring-expenses/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div data-testid="recurring-expenses-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Recurring Expenses</h2><p className="text-sm text-stone-500">Manage automatically generated expenses (rent, insurance, contracts)</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-recurring-btn">+ Add Recurring Expense</button>
      </div>
      {items.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No recurring expenses</div> : (
        <div className="space-y-4">{items.map(r => (
          <div key={r.id} className="bg-white border border-stone-200 rounded-xl p-5" data-testid={`recurring-card-${r.id}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-stone-400 uppercase font-bold mb-1">{r.name}</div>
                <div className="flex items-center gap-3 flex-wrap">
                  <Badge className={`text-[10px] ${r.mode === "play" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{r.mode === "play" ? "Play Mode" : "Paused"}</Badge>
                  {r.started && <Badge className="text-[10px] bg-blue-50 text-blue-600">Started ({r.started})</Badge>}
                </div>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <div className="text-right"><div className="text-xs text-stone-400">Amount</div><div className="font-bold">{currency(r.amount)}</div></div>
                <div className="text-right"><div className="text-xs text-stone-400">Frequency</div><div className="capitalize">{r.frequency}</div></div>
                <div className="text-right"><div className="text-xs text-stone-400">Category</div><div className="capitalize">{r.category}</div></div>
                <div className="text-right"><div className="text-xs text-stone-400">Next Run</div><div>{r.next_run || "—"}</div></div>
                <Badge className="text-[10px] bg-emerald-50 text-emerald-600">{r.status}</Badge>
              </div>
            </div>
            <div className="flex gap-2 mt-3 justify-end">
              <button onClick={() => toggle(r.id, r.mode)} className={`p-2 rounded-lg ${r.mode === "play" ? "bg-amber-100 text-amber-600" : "bg-emerald-100 text-emerald-600"}`} title={r.mode === "play" ? "Pause" : "Play"}>
                {r.mode === "play" ? <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z"/></svg> : <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/></svg>}
              </button>
              <button onClick={() => del(r.id)} className="p-2 rounded-lg bg-red-100 text-red-600" title="Delete">
                <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9z"/></svg>
              </button>
            </div>
          </div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="recurring-dialog"><DialogHeader><DialogTitle>Add Recurring Expense</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Name (e.g. Office Rent)" data-testid="rec-name" />
            <div className="grid grid-cols-2 gap-3">
              <Input type="number" value={form.amount} onChange={e => setForm({...form, amount: parseFloat(e.target.value)||0})} placeholder="Amount" data-testid="rec-amount" />
              <Select value={form.frequency} onValueChange={v => setForm({...form, frequency: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="quarterly">Quarterly</SelectItem><SelectItem value="annually">Annually</SelectItem></SelectContent></Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.category} onValueChange={v => setForm({...form, category: v})}><SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="rent">Rent</SelectItem><SelectItem value="laundry">Laundry</SelectItem><SelectItem value="insurance">Insurance</SelectItem><SelectItem value="utilities">Utilities</SelectItem><SelectItem value="other">Other</SelectItem></SelectContent></Select>
              <Input type="date" value={form.next_run} onChange={e => setForm({...form, next_run: e.target.value})} data-testid="rec-next-run" />
            </div>
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="rec-save">Create</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ── MAIN FINANCE PANEL ── */
const financeTabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "salaries", label: "Earned Salaries" },
  { id: "payroll", label: "Payroll Runs" },
  { id: "adjustments", label: "Adjustments" },
  { id: "advances", label: "Cash Advances" },
  { id: "categories", label: "Categories" },
  { id: "expenses", label: "Expenses" },
  { id: "recurring", label: "Recurring" },
];

export const FinancePanel = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("dashboard");
  const pid = activePropertyId || "all";

  return (
    <div className="p-5" data-testid="finance-panel">
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {financeTabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              tab === t.id ? "text-emerald-700 border-emerald-500 bg-emerald-50/50" : "text-stone-400 border-transparent hover:text-stone-600"
            }`} data-testid={`fin-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
          {tab === "dashboard" && <DashboardTab propertyId={pid} />}
          {tab === "salaries" && <EarnedSalariesTab propertyId={pid} />}
          {tab === "payroll" && <PayrollRunsTab propertyId={pid} />}
          {tab === "adjustments" && <AdjustmentsTab propertyId={pid} />}
          {tab === "advances" && <CashAdvancesTab propertyId={pid} />}
          {tab === "categories" && <CategoriesTab />}
          {tab === "expenses" && <ExpensesTab propertyId={pid} />}
          {tab === "recurring" && <RecurringExpensesTab propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
