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
  RefreshCw, Plus, Receipt, Repeat, Layers, Trash2, Edit3, PlayCircle,
  DollarSign, Calendar, ExternalLink, Zap, Package, Wrench, Megaphone,
  Users, Home, Utensils, Cpu, MoreHorizontal, AlertCircle, Settings2, Shirt,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CAT_ICON = { zap: Zap, package: Package, wrench: Wrench, megaphone: Megaphone, users: Users, home: Home, utensils: Utensils, cpu: Cpu, more: MoreHorizontal };
const TABS = [
  { id: "expenses",  label: "Expenses",   icon: Receipt },
  { id: "recurring", label: "Recurring",  icon: Repeat },
  { id: "budgets",   label: "Categories & Budgets", icon: Layers },
];
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export const ExpenseManagement = ({ propertyId, user, permissions }) => {
  const [tab, setTab] = useState("expenses");
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [cats, setCats] = useState([]);
  const [data, setData] = useState({ expenses: [], kpis: {}, by_category: {} });
  const [recurring, setRecurring] = useState({ recurring: [], due_count: 0 });
  const [laundry, setLaundry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expOpen, setExpOpen] = useState(false);
  const [recOpen, setRecOpen] = useState(false);
  const [budgetOpen, setBudgetOpen] = useState(null);
  const [budgetAmt, setBudgetAmt] = useState(0);
  const [editing, setEditing] = useState(null);
  const [expForm, setExpForm] = useState({ vendor: "", category: "other", description: "", amount: 0, date: new Date().toISOString().slice(0,10), payment_method: "bank", receipt_url: "", reference: "", notes: "" });
  const [recForm, setRecForm] = useState({ vendor: "", category: "other", description: "", amount: 0, frequency: "monthly", next_due: new Date().toISOString().slice(0,10), payment_method: "bank", auto_post: false });
  const [categoryFilter, setCategoryFilter] = useState("");

  const pid = propertyId || "all";
  const isManager = user?.role === "admin" || user?.role === "manager";
  const canSeeLaundryCosts = !!permissions?.is_legacy_admin
                          || !!permissions?.permissions?.has?.("view_laundry_costs");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const baseCalls = [
        axios.get(`${API}/expenses/categories/${pid}?year=${year}&month=${month}`),
        axios.get(`${API}/expenses/${pid}?year=${year}&month=${month}${categoryFilter ? `&category=${categoryFilter}` : ""}`),
        axios.get(`${API}/expenses/recurring/${pid}`),
      ];
      const [c, e, r] = await Promise.all(baseCalls);
      setCats(c.data.categories || []);
      setData(e.data);
      setRecurring(r.data);
      // Only fetch laundry summary if user is allowed to see costs (saves a 403 network call)
      if (canSeeLaundryCosts) {
        try {
          const l = await axios.get(`${API}/expenses/laundry-summary/${pid}?year=${year}&month=${month}`);
          setLaundry(l.data);
        } catch { setLaundry(null); }
      } else {
        setLaundry(null);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, year, month, categoryFilter, canSeeLaundryCosts]);

  useEffect(() => { load(); }, [load]);

  const openNewExp = () => { setEditing(null); setExpForm({ vendor: "", category: categoryFilter || "other", description: "", amount: 0, date: new Date().toISOString().slice(0,10), payment_method: "bank", receipt_url: "", reference: "", notes: "" }); setExpOpen(true); };
  const openEditExp = (e) => { setEditing(e); setExpForm({ ...e }); setExpOpen(true); };

  const submitExp = async () => {
    if (expForm.amount <= 0) { toast.error("Amount must be positive"); return; }
    try {
      if (editing) { await axios.put(`${API}/expenses/${pid}/${editing.id}`, expForm); toast.success("Updated"); }
      else { await axios.post(`${API}/expenses/${pid}`, expForm); toast.success("Created"); }
      setExpOpen(false); load();
    } catch { toast.error("Failed"); }
  };
  const deleteExp = async (id) => {
    if (!window.confirm("Delete this expense?")) return;
    try { await axios.delete(`${API}/expenses/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  const submitRec = async () => {
    if (recForm.amount <= 0) { toast.error("Amount must be positive"); return; }
    try {
      await axios.post(`${API}/expenses/recurring/${pid}`, recForm);
      toast.success("Recurring created");
      setRecOpen(false);
      setRecForm({ vendor: "", category: "other", description: "", amount: 0, frequency: "monthly", next_due: new Date().toISOString().slice(0,10), payment_method: "bank", auto_post: false });
      load();
    } catch { toast.error("Failed"); }
  };
  const postRec = async (id) => {
    try { await axios.post(`${API}/expenses/recurring/${pid}/${id}/post`); toast.success("Posted"); load(); } catch { toast.error("Failed"); }
  };
  const toggleRec = async (r) => {
    try { await axios.put(`${API}/expenses/recurring/${pid}/${r.id}`, { enabled: !r.enabled }); load(); } catch { toast.error("Failed"); }
  };
  const deleteRec = async (id) => {
    if (!window.confirm("Delete this recurring template?")) return;
    try { await axios.delete(`${API}/expenses/recurring/${pid}/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };
  const runDue = async () => {
    if (!window.confirm(`Post all ${recurring.due_count} due recurring expenses now?`)) return;
    try {
      const { data: r } = await axios.post(`${API}/expenses/recurring/${pid}/run-due`);
      toast.success(`Posted ${r.posted} recurring expense(s)`);
      load();
    } catch { toast.error("Failed"); }
  };

  const saveBudget = async () => {
    try {
      await axios.put(`${API}/expenses/categories/${pid}/${budgetOpen.id}/budget`, { year, month, amount: parseFloat(budgetAmt) || 0 });
      toast.success("Budget saved");
      setBudgetOpen(null);
      load();
    } catch { toast.error("Failed"); }
  };

  const k = data.kpis || {};

  return (
    <div className="space-y-5" data-testid="expense-management">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Receipt className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="expenses-title">Expense Management</h2>
          {recurring.due_count > 0 && (
            <Badge className="bg-amber-100 text-amber-700 text-[9px] flex items-center gap-1" data-testid="due-badge">
              <AlertCircle className="w-2.5 h-2.5" />{recurring.due_count} recurring due
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select value={String(month)} onValueChange={v => setMonth(parseInt(v))}>
            <SelectTrigger className="h-8 w-24 text-xs" data-testid="month-select"><SelectValue /></SelectTrigger>
            <SelectContent>{MONTHS.map((m, i) => <SelectItem key={i+1} value={String(i+1)}>{m}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={String(year)} onValueChange={v => setYear(parseInt(v))}>
            <SelectTrigger className="h-8 w-20 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>{[2024, 2025, 2026, 2027].map(y => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-4 gap-3" data-testid="expense-kpis">
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><DollarSign className="w-4 h-4 mx-auto mb-1 text-violet-600" /><p className="text-2xl font-black text-violet-700">£{(k.total || 0).toFixed(0)}</p><p className="text-[10px] text-violet-600">Total Spent</p></div>
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><Receipt className="w-4 h-4 mx-auto mb-1 text-stone-500" /><p className="text-2xl font-black text-stone-700">{k.count || 0}</p><p className="text-[10px] text-stone-500">Transactions</p></div>
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><p className="text-2xl font-black text-blue-700">£{(k.avg || 0).toFixed(0)}</p><p className="text-[10px] text-blue-600">Avg / Expense</p></div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><Repeat className="w-4 h-4 mx-auto mb-1 text-amber-600" /><p className="text-2xl font-black text-amber-700">{recurring.recurring.length}</p><p className="text-[10px] text-amber-600">Recurring</p></div>
      </div>

      {/* Laundry Spend Summary (gated by `view_laundry_costs` permission) */}
      {canSeeLaundryCosts && laundry && (
        <div className="bg-gradient-to-br from-sky-50 to-white border border-sky-200 rounded-xl p-4" data-testid="laundry-spend-card">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Shirt className="w-4 h-4 text-sky-700" />
              <h3 className="text-sm font-bold text-sky-900">Laundry Spend — {MONTHS[month - 1]} {year}</h3>
            </div>
            <div className="text-right">
              <p className="text-2xl font-black text-sky-900" data-testid="laundry-spend-total">£{(laundry.total || 0).toFixed(2)}</p>
              <p className="text-[10px] text-sky-600">Total this month</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {(laundry.breakdown || []).map(b => (
              <div key={b.key} className="bg-white border border-sky-100 rounded-lg p-3" data-testid={`laundry-breakdown-${b.key}`}>
                <p className="text-[10px] font-semibold uppercase text-sky-500">{b.label}</p>
                <p className="text-lg font-black text-stone-800">£{(b.amount || 0).toFixed(2)}</p>
                <p className="text-[10px] text-stone-500">
                  {b.count || 0} {b.key === "dispatches" ? "dispatches" : b.key === "deliveries" ? "deliveries" : "events"}
                  {b.pieces ? ` · ${b.pieces} pcs` : ""}
                  {b.deductions ? ` · £${b.deductions.toFixed(2)} deducted` : ""}
                </p>
              </div>
            ))}
          </div>
          {laundry.contracts?.active > 0 && (
            <div className="mt-3 pt-3 border-t border-sky-100 flex items-center justify-between text-xs">
              <span className="text-sky-700">
                <b>{laundry.contracts.active}</b> active contract{laundry.contracts.active !== 1 ? "s" : ""}
              </span>
              <span className="text-stone-600">
                Monthly flat fees: <b className="text-stone-800">£{(laundry.contracts.monthly_flat_fees || 0).toFixed(2)}</b>
              </span>
            </div>
          )}
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
          {tab === "expenses" && (
            <Button size="sm" onClick={openNewExp} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-expense-btn">
              <Plus className="w-4 h-4 mr-1.5" />New Expense
            </Button>
          )}
          {tab === "recurring" && (
            <>
              {recurring.due_count > 0 && (
                <Button size="sm" onClick={runDue} variant="outline" className="text-amber-700 border-amber-300" data-testid="run-due-btn">
                  <PlayCircle className="w-4 h-4 mr-1.5" />Run {recurring.due_count} Due
                </Button>
              )}
              <Button size="sm" onClick={() => setRecOpen(true)} className="bg-stone-800 hover:bg-stone-700 text-white" data-testid="new-recurring-btn">
                <Plus className="w-4 h-4 mr-1.5" />New Recurring
              </Button>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>
      ) : (
        <>
          {/* EXPENSES TAB */}
          {tab === "expenses" && (
            <>
              {/* Category filter */}
              <div className="flex items-center gap-2 flex-wrap">
                <button onClick={() => setCategoryFilter("")} data-testid="cat-filter-all"
                  className={`px-3 py-1 text-[11px] font-semibold rounded-full border ${!categoryFilter ? "bg-stone-800 text-white border-stone-800" : "bg-white text-stone-500 border-stone-200"}`}>
                  All
                </button>
                {cats.map(c => {
                  const Icon = CAT_ICON[c.icon] || MoreHorizontal;
                  const sel = categoryFilter === c.id;
                  return (
                    <button key={c.id} onClick={() => setCategoryFilter(sel ? "" : c.id)}
                      className={`px-3 py-1 text-[11px] font-semibold rounded-full border flex items-center gap-1 ${sel ? "text-white border-transparent" : "bg-white border-stone-200"}`}
                      style={sel ? { backgroundColor: c.color } : { color: c.color }}>
                      <Icon className="w-3 h-3" />{c.name} £{c.spent.toFixed(0)}
                    </button>
                  );
                })}
              </div>

              <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="expenses-table">
                {data.expenses.length === 0 ? (
                  <p className="text-center text-sm text-stone-400 py-12">No expenses for this period.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead className="bg-stone-50 border-b border-stone-200">
                      <tr>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Date</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Vendor</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Category</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Description</th>
                        <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Amount</th>
                        <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Method</th>
                        <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.expenses.map(e => {
                        const c = cats.find(x => x.id === e.category);
                        return (
                          <tr key={e.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`exp-row-${e.id}`}>
                            <td className="py-2 px-3 text-stone-600">{e.date}</td>
                            <td className="py-2 px-3 font-semibold text-stone-700">{e.vendor || "—"}</td>
                            <td className="py-2 px-3">
                              {c && <Badge className="text-[9px]" style={{ backgroundColor: `${c.color}20`, color: c.color }}>{c.name}</Badge>}
                            </td>
                            <td className="py-2 px-3 text-stone-600 max-w-xs truncate">{e.description || "—"}</td>
                            <td className="py-2 px-3 text-right font-mono font-semibold text-violet-700">£{e.amount.toFixed(2)}</td>
                            <td className="py-2 px-3 text-stone-500 capitalize text-[10px]">{e.payment_method}</td>
                            <td className="py-2 px-3 text-right">
                              <div className="inline-flex gap-0.5">
                                {e.receipt_url && <a href={e.receipt_url} target="_blank" rel="noopener noreferrer" className="p-1 hover:bg-stone-100 rounded"><ExternalLink className="w-3 h-3 text-blue-500" /></a>}
                                {isManager && (
                                  <>
                                    <button onClick={() => openEditExp(e)} className="p-1 hover:bg-stone-100 rounded"><Edit3 className="w-3 h-3 text-stone-500" /></button>
                                    <button onClick={() => deleteExp(e.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}

          {/* RECURRING TAB */}
          {tab === "recurring" && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="recurring-table">
              {recurring.recurring.length === 0 ? (
                <p className="text-center text-sm text-stone-400 py-12">No recurring templates yet.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 border-b border-stone-200">
                    <tr>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Vendor</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Category</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Amount</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Frequency</th>
                      <th className="text-left py-2.5 px-3 font-semibold text-stone-600">Next Due</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Posted</th>
                      <th className="text-center py-2.5 px-3 font-semibold text-stone-600">Status</th>
                      <th className="text-right py-2.5 px-3 font-semibold text-stone-600">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recurring.recurring.map(r => {
                      const c = cats.find(x => x.id === r.category);
                      const isDue = r.next_due && r.next_due <= new Date().toISOString().slice(0, 10);
                      return (
                        <tr key={r.id} className={`border-b border-stone-100 hover:bg-stone-50/50 ${isDue && r.enabled ? "bg-amber-50/30" : ""}`} data-testid={`rec-row-${r.id}`}>
                          <td className="py-2 px-3 font-semibold text-stone-700">{r.vendor}</td>
                          <td className="py-2 px-3">{c && <Badge className="text-[9px]" style={{ backgroundColor: `${c.color}20`, color: c.color }}>{c.name}</Badge>}</td>
                          <td className="py-2 px-3 text-right font-mono font-semibold text-violet-700">£{r.amount.toFixed(2)}</td>
                          <td className="py-2 px-3 text-stone-600 capitalize">{r.frequency}</td>
                          <td className={`py-2 px-3 ${isDue && r.enabled ? "text-amber-700 font-semibold" : "text-stone-600"}`}>{r.next_due}</td>
                          <td className="py-2 px-3 text-center text-stone-600">{r.total_posted || 0}</td>
                          <td className="py-2 px-3 text-center">
                            <button onClick={() => toggleRec(r)} className={`px-2 py-0.5 text-[9px] font-semibold rounded-full ${r.enabled ? "bg-emerald-100 text-emerald-700" : "bg-stone-200 text-stone-500"}`}>
                              {r.enabled ? "Active" : "Paused"}
                            </button>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <div className="inline-flex gap-0.5">
                              {isDue && r.enabled && (
                                <button onClick={() => postRec(r.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 font-semibold" data-testid={`post-${r.id}`}>
                                  <PlayCircle className="w-3 h-3 inline mr-0.5" />Post Now
                                </button>
                              )}
                              {isManager && <button onClick={() => deleteRec(r.id)} className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3 h-3 text-red-500" /></button>}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* BUDGETS TAB */}
          {tab === "budgets" && (
            <div className="grid grid-cols-3 gap-3" data-testid="budgets-grid">
              {cats.map(c => {
                const Icon = CAT_ICON[c.icon] || MoreHorizontal;
                const over = c.budget > 0 && c.spent > c.budget;
                const nearly = c.budget > 0 && c.usage_pct >= 80 && c.usage_pct <= 100;
                return (
                  <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`budget-card-${c.id}`}>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${c.color}20` }}>
                          <Icon className="w-4 h-4" style={{ color: c.color }} />
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-stone-800">{c.name}</h4>
                          <p className="text-[10px] text-stone-500">{MONTHS[month-1]} {year}</p>
                        </div>
                      </div>
                      {isManager && (
                        <button onClick={() => { setBudgetOpen(c); setBudgetAmt(c.budget); }} className="p-1 hover:bg-stone-100 rounded">
                          <Settings2 className="w-3.5 h-3.5 text-stone-400" />
                        </button>
                      )}
                    </div>
                    <div className="flex items-baseline justify-between">
                      <p className="text-xl font-black text-stone-800">£{c.spent.toFixed(0)}</p>
                      <p className="text-[11px] text-stone-500">of £{c.budget.toFixed(0)}</p>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-stone-100 overflow-hidden">
                      <div className={`h-full transition-all ${over ? "bg-red-500" : nearly ? "bg-amber-400" : "bg-emerald-400"}`}
                        style={{ width: `${Math.min(c.usage_pct, 100)}%` }} />
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[10px] text-stone-400">{c.usage_pct}% used</span>
                      {over && <span className="text-[10px] text-red-600 font-semibold">Over budget</span>}
                      {nearly && !over && <span className="text-[10px] text-amber-600 font-semibold">Near limit</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Expense Dialog */}
      <Dialog open={expOpen} onOpenChange={setExpOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit" : "New"} Expense</DialogTitle>
            <DialogDescription>Log a one-off cost. For repeating bills, use Recurring.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Vendor</label>
                <Input value={expForm.vendor} onChange={e => setExpForm({ ...expForm, vendor: e.target.value })} data-testid="exp-vendor-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Date</label>
                <Input type="date" value={expForm.date} onChange={e => setExpForm({ ...expForm, date: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Category</label>
                <Select value={expForm.category} onValueChange={v => setExpForm({ ...expForm, category: v })}>
                  <SelectTrigger data-testid="exp-cat-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{cats.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Amount (£)</label>
                <Input type="number" step="0.01" value={expForm.amount} onChange={e => setExpForm({ ...expForm, amount: parseFloat(e.target.value) || 0 })} data-testid="exp-amount-input" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Payment Method</label>
                <Select value={expForm.payment_method} onValueChange={v => setExpForm({ ...expForm, payment_method: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bank">Bank Transfer</SelectItem>
                    <SelectItem value="card">Card</SelectItem>
                    <SelectItem value="cash">Cash</SelectItem>
                    <SelectItem value="direct_debit">Direct Debit</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Reference</label>
                <Input value={expForm.reference} onChange={e => setExpForm({ ...expForm, reference: e.target.value })} placeholder="Invoice #" />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Description</label>
              <Input value={expForm.description} onChange={e => setExpForm({ ...expForm, description: e.target.value })} />
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Receipt URL</label>
              <Input value={expForm.receipt_url} onChange={e => setExpForm({ ...expForm, receipt_url: e.target.value })} placeholder="https://..." />
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Notes</label>
              <Textarea value={expForm.notes} onChange={e => setExpForm({ ...expForm, notes: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setExpOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitExp} data-testid="exp-submit-btn">{editing ? "Update" : "Create"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Recurring Dialog */}
      <Dialog open={recOpen} onOpenChange={setRecOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Recurring Expense</DialogTitle>
            <DialogDescription>Template to auto-post repeating bills like rent, utilities, subscriptions.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Vendor</label>
                <Input value={recForm.vendor} onChange={e => setRecForm({ ...recForm, vendor: e.target.value })} data-testid="rec-vendor-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Category</label>
                <Select value={recForm.category} onValueChange={v => setRecForm({ ...recForm, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{cats.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-xs font-semibold text-stone-600">Amount (£)</label>
                <Input type="number" step="0.01" value={recForm.amount} onChange={e => setRecForm({ ...recForm, amount: parseFloat(e.target.value) || 0 })} data-testid="rec-amount-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Frequency</label>
                <Select value={recForm.frequency} onValueChange={v => setRecForm({ ...recForm, frequency: v })}>
                  <SelectTrigger data-testid="rec-freq-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="biweekly">Bi-Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="quarterly">Quarterly</SelectItem>
                    <SelectItem value="annual">Annual</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-semibold text-stone-600">Next Due</label>
                <Input type="date" value={recForm.next_due} onChange={e => setRecForm({ ...recForm, next_due: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-stone-600">Description</label>
              <Input value={recForm.description} onChange={e => setRecForm({ ...recForm, description: e.target.value })} />
            </div>
            <label className="flex items-center gap-2 text-xs text-stone-600">
              <input type="checkbox" checked={recForm.auto_post} onChange={e => setRecForm({ ...recForm, auto_post: e.target.checked })} />
              Auto-post when due (reminder only if unchecked)
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setRecOpen(false)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={submitRec} data-testid="rec-submit-btn">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Budget Dialog */}
      <Dialog open={!!budgetOpen} onOpenChange={o => !o && setBudgetOpen(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Set Budget — {budgetOpen?.name}</DialogTitle>
            <DialogDescription>Monthly budget for {MONTHS[month-1]} {year}. Bar turns red when exceeded.</DialogDescription>
          </DialogHeader>
          <div>
            <label className="text-xs font-semibold text-stone-600">Amount (£)</label>
            <Input type="number" step="0.01" value={budgetAmt} onChange={e => setBudgetAmt(e.target.value)} data-testid="budget-amount-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setBudgetOpen(null)}>Cancel</Button>
            <Button size="sm" className="bg-stone-800 hover:bg-stone-700 text-white" onClick={saveBudget} data-testid="budget-submit-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
