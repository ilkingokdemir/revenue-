import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  CurrencyGbp, Plus, ArrowsClockwise, TrendUp, TrendDown,
  ChartBar, Receipt, Wallet, ChartPie, ArrowDown, ArrowUp, Trash,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const INCOME_CATS = ["room_revenue","food_beverage","spa_wellness","events_meetings","parking","laundry","minibar","late_checkout","cancellation_fees","other"];
const EXPENSE_CATS = ["staff_wages","food_cost","beverage_cost","utilities","maintenance","marketing","insurance","rent_lease","supplies","technology","commissions","taxes","depreciation","other"];
const DEPARTMENTS = ["rooms","food_beverage","spa","events","front_office","housekeeping","maintenance","admin","marketing","other"];

function InvoicesTab({ propertyId, month }) {
  const [invoices, setInvoices] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newInv, setNewInv] = useState({ invoice_type: "receivable", counterparty: "", due_date: "", items: [{ description: "", quantity: 1, unit_price: 0, vat_rate: 20 }] });
  const fetch = useCallback(async () => {
    const r = await axios.get(`${API}/accounting/invoices/${propertyId}`);
    setInvoices(r.data);
  }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);
  const createInv = async () => {
    await axios.post(`${API}/accounting/invoices`, { ...newInv, property_id: propertyId });
    setShowCreate(false); fetch();
  };
  const markPaid = async (id) => { await axios.put(`${API}/accounting/invoices/${id}`, { status: "paid" }); fetch(); };
  return (
    <div className="space-y-3" data-testid="invoices-tab">
      <div className="flex justify-end"><button onClick={() => setShowCreate(true)} className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium"><Plus size={12} className="inline mr-1" />New Invoice</button></div>
      {invoices.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No invoices yet</div> :
        invoices.map(inv => (
          <div key={inv.id} className="bg-white border border-stone-200 rounded-xl p-3 flex justify-between items-center">
            <div>
              <div className="text-xs font-semibold text-stone-800">{inv.invoice_number} — {inv.counterparty}</div>
              <div className="text-[10px] text-stone-400">{inv.invoice_type} · Due: {inv.due_date} · Items: {inv.items?.length || 0}</div>
            </div>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <div className="text-sm font-bold text-stone-800">£{inv.total}</div>
                <div className="text-[9px] text-stone-400">£{inv.subtotal} + £{inv.vat_amount} VAT</div>
              </div>
              <Badge className={`text-[9px] ${inv.status === "paid" ? "bg-emerald-100 text-emerald-700" : inv.status === "overdue" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}>{inv.status}</Badge>
              {inv.status !== "paid" && <button onClick={() => markPaid(inv.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-600 rounded">Mark Paid</button>}
            </div>
          </div>
        ))}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>New Invoice</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newInv.invoice_type} onValueChange={v => setNewInv(p => ({...p, invoice_type: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="receivable">Receivable (Guest owes us)</SelectItem><SelectItem value="payable">Payable (We owe supplier)</SelectItem></SelectContent>
            </Select>
            <Input placeholder="Counterparty (guest/supplier)" value={newInv.counterparty} onChange={e => setNewInv(p => ({...p, counterparty: e.target.value}))} />
            <Input type="date" placeholder="Due date" value={newInv.due_date} onChange={e => setNewInv(p => ({...p, due_date: e.target.value}))} />
            {newInv.items.map((item, i) => (
              <div key={i} className="grid grid-cols-4 gap-1">
                <Input placeholder="Description" className="col-span-2 text-xs" value={item.description} onChange={e => { const items = [...newInv.items]; items[i].description = e.target.value; setNewInv(p => ({...p, items})); }} />
                <Input type="number" placeholder="Qty" className="text-xs" value={item.quantity || ""} onChange={e => { const items = [...newInv.items]; items[i].quantity = parseFloat(e.target.value) || 0; setNewInv(p => ({...p, items})); }} />
                <Input type="number" placeholder="£ price" className="text-xs" value={item.unit_price || ""} onChange={e => { const items = [...newInv.items]; items[i].unit_price = parseFloat(e.target.value) || 0; setNewInv(p => ({...p, items})); }} />
              </div>
            ))}
            <button onClick={() => setNewInv(p => ({...p, items: [...p.items, { description: "", quantity: 1, unit_price: 0, vat_rate: 20 }]}))} className="text-[10px] text-blue-600">+ Add line</button>
            <button onClick={createInv} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium">Create Invoice</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function VATTab({ propertyId, month }) {
  const [vat, setVat] = useState(null);
  useEffect(() => { axios.get(`${API}/accounting/vat-report/${propertyId}?period=${month}`).then(r => setVat(r.data)); }, [propertyId, month]);
  if (!vat) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  return (
    <div className="space-y-4" data-testid="vat-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center"><div className="text-xl font-bold text-stone-800">£{vat.output_sales}</div><div className="text-[10px] text-stone-500 uppercase">Sales (Net)</div></div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center"><div className="text-xl font-bold text-red-500">£{vat.output_vat}</div><div className="text-[10px] text-stone-500 uppercase">Output VAT</div></div>
        <div className="bg-white border border-stone-200 rounded-xl p-4 text-center"><div className="text-xl font-bold text-emerald-600">£{vat.input_vat}</div><div className="text-[10px] text-stone-500 uppercase">Input VAT</div></div>
        <div className={`border rounded-xl p-4 text-center ${vat.net_vat_payable >= 0 ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200"}`}>
          <div className={`text-xl font-bold ${vat.net_vat_payable >= 0 ? "text-red-600" : "text-emerald-600"}`}>£{vat.net_vat_payable}</div>
          <div className="text-[10px] text-stone-500 uppercase">{vat.net_vat_payable >= 0 ? "VAT Payable" : "VAT Refund"}</div>
        </div>
      </div>
      <div className="text-[11px] text-stone-400 text-center">Period: {vat.period} · {vat.invoice_count} invoices processed</div>
    </div>
  );
}

function TrendsTab({ propertyId }) {
  const [trends, setTrends] = useState([]);
  useEffect(() => { axios.get(`${API}/accounting/trends/${propertyId}?months=6`).then(r => setTrends(r.data)); }, [propertyId]);
  const maxVal = Math.max(...trends.map(t => Math.max(t.income, t.expenses)), 1);
  return (
    <div className="space-y-3" data-testid="trends-tab">
      <div className="text-sm font-semibold text-stone-700">6-Month P&L Trend</div>
      {trends.map(t => (
        <div key={t.month} className="bg-white border border-stone-200 rounded-lg p-3">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="font-semibold text-stone-700">{new Date(t.month + "-01").toLocaleDateString("en-GB", { month: "short", year: "numeric" })}</span>
            <span className={`font-bold ${t.net_profit >= 0 ? "text-emerald-600" : "text-red-600"}`}>£{t.net_profit} ({t.margin}%)</span>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2"><span className="text-[9px] w-12 text-right text-stone-400">Income</span><div className="flex-1 bg-stone-100 rounded-full h-2"><div className="bg-emerald-400 h-2 rounded-full" style={{ width: `${(t.income / maxVal) * 100}%` }} /></div><span className="text-[10px] text-stone-500 w-16 text-right">£{t.income}</span></div>
            <div className="flex items-center gap-2"><span className="text-[9px] w-12 text-right text-stone-400">Expense</span><div className="flex-1 bg-stone-100 rounded-full h-2"><div className="bg-red-400 h-2 rounded-full" style={{ width: `${(t.expenses / maxVal) * 100}%` }} /></div><span className="text-[10px] text-stone-500 w-16 text-right">£{t.expenses}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ChartOfAccountsTab({ propertyId }) {
  const [accounts, setAccounts] = useState([]);
  useEffect(() => { axios.get(`${API}/accounting/chart-of-accounts/${propertyId}`).then(r => setAccounts(r.data)); }, [propertyId]);
  const grouped = accounts.reduce((acc, a) => { (acc[a.account_type] = acc[a.account_type] || []).push(a); return acc; }, {});
  const typeColors = { revenue: "text-emerald-600", cost_of_sales: "text-red-500", operating_expenses: "text-amber-600", payroll: "text-blue-600" };
  return (
    <div className="space-y-4" data-testid="accounts-tab">
      <div className="text-sm font-semibold text-stone-700">USALI Chart of Accounts ({accounts.length})</div>
      {Object.entries(grouped).map(([type, accts]) => (
        <div key={type} className="bg-white border border-stone-200 rounded-xl p-4">
          <div className={`text-xs font-semibold uppercase mb-2 ${typeColors[type] || "text-stone-600"}`}>{type.replace(/_/g, " ")}</div>
          {accts.map(a => (
            <div key={a.id} className="flex justify-between text-xs py-1 border-b border-stone-50">
              <span className="text-stone-500 font-mono">{a.code}</span>
              <span className="text-stone-700">{a.name}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export function AccountingPanel({ properties, activePropertyId }) {
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState({});
  const [pnl, setPnl] = useState(null);
  const [income, setIncome] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [budgets, setBudgets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [showIncome, setShowIncome] = useState(false);
  const [showExpense, setShowExpense] = useState(false);
  const [newIncome, setNewIncome] = useState({ category: "room_revenue", amount: 0, department: "rooms", date: new Date().toISOString().slice(0, 10), description: "" });
  const [newExpense, setNewExpense] = useState({ category: "staff_wages", amount: 0, department: "admin", date: new Date().toISOString().slice(0, 10), description: "", vendor: "" });

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [stR, pnlR, incR, expR, budR] = await Promise.all([
        axios.get(`${API}/accounting/stats/${propertyId}`),
        axios.get(`${API}/accounting/pnl/${propertyId}?period=${month}`),
        axios.get(`${API}/accounting/income/${propertyId}?month=${month}`),
        axios.get(`${API}/accounting/expenses/${propertyId}?month=${month}`),
        axios.get(`${API}/accounting/budget-vs-actual/${propertyId}?month=${month}`),
      ]);
      setStats(stR.data); setPnl(pnlR.data); setIncome(incR.data); setExpenses(expR.data); setBudgets(budR.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId, month]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const addIncome = async () => {
    if (!newIncome.amount) return;
    await axios.post(`${API}/accounting/income`, { ...newIncome, property_id: propertyId });
    setShowIncome(false); setNewIncome({ category: "room_revenue", amount: 0, department: "rooms", date: new Date().toISOString().slice(0, 10), description: "" });
    fetchData();
  };
  const addExpense = async () => {
    if (!newExpense.amount) return;
    await axios.post(`${API}/accounting/expenses`, { ...newExpense, property_id: propertyId });
    setShowExpense(false); setNewExpense({ category: "staff_wages", amount: 0, department: "admin", date: new Date().toISOString().slice(0, 10), description: "", vendor: "" });
    fetchData();
  };
  const syncRevenue = async () => {
    await axios.post(`${API}/accounting/sync-revenue/${propertyId}?month=${month}`);
    fetchData();
  };
  const deleteIncome = async (id) => { await axios.delete(`${API}/accounting/income/${id}`); fetchData(); };
  const deleteExpense = async (id) => { await axios.delete(`${API}/accounting/expenses/${id}`); fetchData(); };

  const TABS = [
    { id: "overview", label: "P&L Overview", icon: ChartPie },
    { id: "income", label: `Income (${income.length})`, icon: TrendUp },
    { id: "expenses", label: `Expenses (${expenses.length})`, icon: TrendDown },
    { id: "invoices", label: "Invoices", icon: Receipt },
    { id: "vat", label: "VAT", icon: CurrencyGbp },
    { id: "trends", label: "Trends", icon: ChartBar },
    { id: "budgets", label: "Budget vs Actual", icon: ChartBar },
    { id: "accounts", label: "Chart of Accounts", icon: Wallet },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="accounting-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="accounting-title">
            <Wallet size={22} className="text-indigo-600" weight="fill" /> Hotel Accounting
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Income, expenses & profit/loss</p>
        </div>
        <div className="flex gap-2 items-center">
          <Input type="month" value={month} onChange={e => setMonth(e.target.value)} className="h-8 text-xs w-36" data-testid="month-picker" />
          <button onClick={syncRevenue} className="text-xs px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg font-medium" data-testid="sync-revenue-btn">
            <ArrowsClockwise size={12} className="inline mr-1" /> Sync Bookings
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-gradient-to-br from-emerald-50 to-green-50 border border-emerald-200 rounded-xl p-4">
          <div className="text-[10px] text-emerald-600 uppercase font-semibold">Total Income</div>
          <div className="text-2xl font-bold text-emerald-700">£{stats.income || 0}</div>
          {stats.booking_revenue > 0 && <div className="text-[10px] text-emerald-500 mt-0.5">incl. £{stats.booking_revenue} bookings</div>}
        </div>
        <div className="bg-gradient-to-br from-red-50 to-orange-50 border border-red-200 rounded-xl p-4">
          <div className="text-[10px] text-red-600 uppercase font-semibold">Total Expenses</div>
          <div className="text-2xl font-bold text-red-600">£{stats.expenses || 0}</div>
        </div>
        <div className={`bg-gradient-to-br border rounded-xl p-4 ${(stats.net_profit || 0) >= 0 ? "from-blue-50 to-indigo-50 border-blue-200" : "from-red-50 to-pink-50 border-red-200"}`}>
          <div className="text-[10px] uppercase font-semibold text-stone-600">Net Profit</div>
          <div className={`text-2xl font-bold ${(stats.net_profit || 0) >= 0 ? "text-blue-700" : "text-red-600"}`}>£{stats.net_profit || 0}</div>
          <div className="text-[10px] text-stone-500 mt-0.5">{stats.margin || 0}% margin</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-[10px] text-stone-500 uppercase font-semibold">Previous Month</div>
          <div className="text-lg font-bold text-stone-700">£{stats.prev_month?.net || 0}</div>
          <div className="text-[10px] text-stone-400">Inc: £{stats.prev_month?.income || 0} | Exp: £{stats.prev_month?.expenses || 0}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`px-3 py-2.5 text-xs font-medium flex items-center gap-1.5 border-b-2 ${tab === t.id ? "border-indigo-500 text-indigo-700" : "border-transparent text-stone-400 hover:text-stone-600"}`} data-testid={`tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div> : (<>
        {tab === "overview" && pnl && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" data-testid="pnl-overview">
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5"><TrendUp size={14} className="text-emerald-500" /> Income Breakdown</div>
              {Object.entries(pnl.income_breakdown || {}).map(([cat, data]) => (
                <div key={cat} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-stone-600">{cat.replace(/_/g, " ")}</span>
                    {data.source === "auto_booking_engine" && <Badge className="text-[8px] bg-blue-50 text-blue-600">auto</Badge>}
                  </div>
                  <span className="font-bold text-emerald-600">£{data.total}</span>
                </div>
              ))}
              <div className="flex justify-between pt-2 text-sm font-bold">
                <span>Total Income</span><span className="text-emerald-700">£{pnl.total_income}</span>
              </div>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5"><TrendDown size={14} className="text-red-500" /> Expense Breakdown</div>
              {Object.entries(pnl.expense_breakdown || {}).map(([cat, data]) => (
                <div key={cat} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-xs">
                  <span className="text-stone-600">{cat.replace(/_/g, " ")}</span>
                  <span className="font-bold text-red-500">£{data.total}</span>
                </div>
              ))}
              <div className="flex justify-between pt-2 text-sm font-bold">
                <span>Total Expenses</span><span className="text-red-600">£{pnl.total_expenses}</span>
              </div>
            </div>
            {Object.keys(pnl.departments || {}).length > 0 && (
              <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-sm font-semibold text-stone-800 mb-3">Department P&L</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {Object.entries(pnl.departments).map(([dept, d]) => (
                    <div key={dept} className={`rounded-lg p-3 border text-center ${d.net >= 0 ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
                      <div className="text-[10px] text-stone-500 uppercase">{dept.replace(/_/g, " ")}</div>
                      <div className={`text-sm font-bold ${d.net >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{d.net}</div>
                      <div className="text-[9px] text-stone-400">In: £{d.income} | Out: £{d.expenses}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="lg:col-span-2 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-xs text-indigo-600 font-semibold uppercase">Net Profit — {pnl.period}</div>
                <div className={`text-3xl font-black ${pnl.net_profit >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{pnl.net_profit}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-stone-700">{pnl.profit_margin}%</div>
                <div className="text-[10px] text-stone-500">Profit Margin</div>
              </div>
            </div>
          </div>
        )}

        {tab === "income" && (
          <div className="space-y-2" data-testid="income-list">
            <div className="flex justify-end">
              <button onClick={() => setShowIncome(true)} className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg font-medium" data-testid="add-income-btn">
                <Plus size={12} className="inline mr-1" /> Add Income
              </button>
            </div>
            {income.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No income entries for {month}</div> :
              income.map(e => (
                <div key={e.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center"><ArrowDown size={14} className="text-emerald-500" /></div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{e.description || e.category.replace(/_/g, " ")}</div>
                      <div className="text-[10px] text-stone-400">{e.date} · {e.department} · {e.source === "booking_engine" ? "Auto (bookings)" : "Manual"}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-emerald-600">£{e.amount}</span>
                    {e.source !== "booking_engine" && <button onClick={() => deleteIncome(e.id)} className="text-stone-300 hover:text-red-400"><Trash size={13} /></button>}
                  </div>
                </div>
              ))}
          </div>
        )}

        {tab === "expenses" && (
          <div className="space-y-2" data-testid="expenses-list">
            <div className="flex justify-end">
              <button onClick={() => setShowExpense(true)} className="text-xs px-3 py-1.5 bg-red-500 text-white rounded-lg font-medium" data-testid="add-expense-btn">
                <Plus size={12} className="inline mr-1" /> Add Expense
              </button>
            </div>
            {expenses.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No expense entries for {month}</div> :
              expenses.map(e => (
                <div key={e.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center"><ArrowUp size={14} className="text-red-500" /></div>
                    <div>
                      <div className="text-xs font-semibold text-stone-800">{e.description || e.category.replace(/_/g, " ")}</div>
                      <div className="text-[10px] text-stone-400">{e.date} · {e.department}{e.vendor ? ` · ${e.vendor}` : ""}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-red-500">£{e.amount}</span>
                    <button onClick={() => deleteExpense(e.id)} className="text-stone-300 hover:text-red-400"><Trash size={13} /></button>
                  </div>
                </div>
              ))}
          </div>
        )}

        {tab === "invoices" && (
          <InvoicesTab propertyId={propertyId} month={month} />
        )}

        {tab === "vat" && (
          <VATTab propertyId={propertyId} month={month} />
        )}

        {tab === "trends" && (
          <TrendsTab propertyId={propertyId} />
        )}

        {tab === "budgets" && (
          <div className="space-y-2" data-testid="budgets-list">
            {budgets.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No budgets set for {month}. Create budgets to compare.</div> :
              budgets.map(b => (
                <div key={b.id} className="bg-white border border-stone-200 rounded-xl p-3">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="font-semibold text-stone-700">{b.department} — {b.category?.replace(/_/g, " ")}</span>
                    <Badge className={`text-[9px] ${b.status === "under_budget" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{b.status?.replace(/_/g, " ")}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={Math.min(100, (b.actual_amount / b.budgeted_amount) * 100)} className="h-2 flex-1" />
                    <span className="text-[10px] text-stone-500">£{b.actual_amount} / £{b.budgeted_amount}</span>
                  </div>
                  <div className="text-[10px] text-stone-400 mt-0.5">Variance: £{b.variance} ({b.variance_pct}%)</div>
                </div>
              ))}
          </div>
        )}
        {tab === "accounts" && (
          <ChartOfAccountsTab propertyId={propertyId} />
        )}
      </>)}

      {/* Add Income Dialog */}
      <Dialog open={showIncome} onOpenChange={setShowIncome}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Income</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newIncome.category} onValueChange={v => setNewIncome(p => ({...p, category: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{INCOME_CATS.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-2">
              <Input type="number" placeholder="Amount (£)" value={newIncome.amount || ""} onChange={e => setNewIncome(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="income-amount" />
              <Input type="date" value={newIncome.date} onChange={e => setNewIncome(p => ({...p, date: e.target.value}))} />
            </div>
            <Select value={newIncome.department} onValueChange={v => setNewIncome(p => ({...p, department: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <Input placeholder="Description" value={newIncome.description} onChange={e => setNewIncome(p => ({...p, description: e.target.value}))} />
            <button onClick={addIncome} className="w-full text-xs py-2 bg-emerald-500 text-white rounded-lg font-medium" data-testid="save-income">Save Income</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Expense Dialog */}
      <Dialog open={showExpense} onOpenChange={setShowExpense}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Add Expense</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newExpense.category} onValueChange={v => setNewExpense(p => ({...p, category: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{EXPENSE_CATS.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-2">
              <Input type="number" placeholder="Amount (£)" value={newExpense.amount || ""} onChange={e => setNewExpense(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="expense-amount" />
              <Input type="date" value={newExpense.date} onChange={e => setNewExpense(p => ({...p, date: e.target.value}))} />
            </div>
            <Select value={newExpense.department} onValueChange={v => setNewExpense(p => ({...p, department: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <Input placeholder="Vendor" value={newExpense.vendor} onChange={e => setNewExpense(p => ({...p, vendor: e.target.value}))} />
            <Input placeholder="Description" value={newExpense.description} onChange={e => setNewExpense(p => ({...p, description: e.target.value}))} />
            <button onClick={addExpense} className="w-full text-xs py-2 bg-red-500 text-white rounded-lg font-medium" data-testid="save-expense">Save Expense</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
