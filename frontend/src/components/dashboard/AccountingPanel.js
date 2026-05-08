import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  CurrencyGbp, Plus, ArrowsClockwise, TrendUp, TrendDown,
  ChartBar, Receipt, Wallet, ChartPie, ArrowDown, ArrowUp, Trash,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { BarChart3, CreditCard, BookOpen, Scale, TrendingUp, Repeat, History, Sun, FileText, Building2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const INCOME_CATS = ["room_revenue","food_beverage","spa_wellness","events_meetings","parking","laundry","minibar","late_checkout","cancellation_fees","other"];
const EXPENSE_CATS = ["staff_wages","food_cost","beverage_cost","utilities","maintenance","marketing","insurance","rent_lease","supplies","technology","commissions","taxes","depreciation","other"];
const DEPARTMENTS = ["rooms","food_beverage","spa","events","front_office","housekeeping","maintenance","admin","marketing","other"];
const PAYMENT_METHODS = ["bank_transfer","credit_card","debit_card","cash","cheque","online","other"];

// ---- Invoices Tab ----
function InvoicesTab({ propertyId, month }) {
  const [invoices, setInvoices] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newInv, setNewInv] = useState({ invoice_type: "receivable", counterparty: "", due_date: "", items: [{ description: "", quantity: 1, unit_price: 0, vat_rate: 20 }] });
  const fetch = useCallback(async () => { const r = await axios.get(`${API}/accounting/invoices/${propertyId}`); setInvoices(r.data); }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);
  const createInv = async () => { await axios.post(`${API}/accounting/invoices`, { ...newInv, property_id: propertyId }); setShowCreate(false); fetch(); toast.success("Invoice created"); };
  const markPaid = async (id) => { await axios.put(`${API}/accounting/invoices/${id}`, { status: "paid" }); fetch(); toast.success("Marked as paid"); };
  return (
    <div className="space-y-3" data-testid="invoices-tab">
      <div className="flex justify-end"><button onClick={() => setShowCreate(true)} className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium" data-testid="new-invoice-btn"><Plus size={12} className="inline mr-1" />New Invoice</button></div>
      {invoices.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No invoices yet</div> :
        invoices.map(inv => (
          <div key={inv.id} className="bg-white border border-stone-200 rounded-xl p-3 flex justify-between items-center" data-testid={`invoice-${inv.id}`}>
            <div>
              <div className="text-xs font-semibold text-stone-800">{inv.invoice_number} — {inv.counterparty}</div>
              <div className="text-[10px] text-stone-400">{inv.invoice_type} · Due: {inv.due_date} · Items: {inv.items?.length || 0}</div>
            </div>
            <div className="flex items-center gap-2">
              <div className="text-right">
                <div className="text-sm font-bold text-stone-800">£{inv.total}</div>
                <div className="text-[9px] text-stone-400">£{inv.subtotal} + £{inv.vat_amount} VAT</div>
              </div>
              <Badge className={`text-[9px] ${inv.status === "paid" ? "bg-emerald-100 text-emerald-700" : inv.status === "overdue" ? "bg-red-100 text-red-700" : inv.status === "partially_paid" ? "bg-blue-100 text-blue-700" : "bg-amber-100 text-amber-700"}`}>{inv.status}</Badge>
              {inv.status !== "paid" && <button onClick={() => markPaid(inv.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-600 rounded" data-testid={`mark-paid-${inv.id}`}>Mark Paid</button>}
              <a href={`${API}/accounting/invoices/${inv.id}/pdf`} target="_blank" rel="noreferrer" className="text-[10px] px-2 py-1 bg-indigo-50 text-indigo-600 rounded" data-testid={`pdf-${inv.id}`}>PDF</a>
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
            <Input placeholder="Counterparty (guest/supplier)" value={newInv.counterparty} onChange={e => setNewInv(p => ({...p, counterparty: e.target.value}))} data-testid="inv-counterparty" />
            <Input type="date" value={newInv.due_date} onChange={e => setNewInv(p => ({...p, due_date: e.target.value}))} />
            {newInv.items.map((item, i) => (
              <div key={i} className="grid grid-cols-4 gap-1">
                <Input placeholder="Description" className="col-span-2 text-xs" value={item.description} onChange={e => { const items = [...newInv.items]; items[i].description = e.target.value; setNewInv(p => ({...p, items})); }} />
                <Input type="number" placeholder="Qty" className="text-xs" value={item.quantity || ""} onChange={e => { const items = [...newInv.items]; items[i].quantity = parseFloat(e.target.value) || 0; setNewInv(p => ({...p, items})); }} />
                <Input type="number" placeholder="£" className="text-xs" value={item.unit_price || ""} onChange={e => { const items = [...newInv.items]; items[i].unit_price = parseFloat(e.target.value) || 0; setNewInv(p => ({...p, items})); }} />
              </div>
            ))}
            <button onClick={() => setNewInv(p => ({...p, items: [...p.items, { description: "", quantity: 1, unit_price: 0, vat_rate: 20 }]}))} className="text-[10px] text-blue-600">+ Add line</button>
            <button onClick={createInv} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium" data-testid="create-invoice-btn">Create Invoice</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- AR/AP Aging ----
function AgingReport({ propertyId, type }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/accounting/${type === "ar" ? "ar-aging" : "ap-aging"}/${propertyId}`)
      .then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, [propertyId, type]);

  if (loading) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;
  if (!data) return null;

  const bucketLabels = { current: "Current", "30": "1-30 Days", "60": "31-60 Days", "90": "61-90 Days", "120_plus": "90+ Days" };
  const bucketColors = { current: "bg-emerald-500", "30": "bg-amber-400", "60": "bg-orange-500", "90": "bg-red-400", "120_plus": "bg-red-600" };
  const isAR = type === "ar";

  return (
    <div className="space-y-4" data-testid={`${type}-aging-tab`}>
      <div className={`rounded-xl p-5 border ${isAR ? "bg-blue-50 border-blue-200" : "bg-orange-50 border-orange-200"}`}>
        <div className={`text-xs font-semibold uppercase ${isAR ? "text-blue-600" : "text-orange-600"}`}>Total {isAR ? "Receivable" : "Payable"} Outstanding</div>
        <div className={`text-3xl font-black mt-1 ${isAR ? "text-blue-800" : "text-orange-800"}`}>£{data.total_outstanding?.toLocaleString()}</div>
        <div className="text-[10px] text-stone-500 mt-1">As of {data.as_of}</div>
      </div>

      {/* Aging Bar */}
      <div className="bg-white rounded-xl border border-stone-200 p-4">
        <div className="text-sm font-semibold text-stone-800 mb-3">Aging Distribution</div>
        <div className="flex h-6 rounded-lg overflow-hidden">
          {Object.entries(data.totals || {}).map(([bucket, amount]) => {
            const pct = data.total_outstanding ? (amount / data.total_outstanding) * 100 : 0;
            return pct > 0 ? <div key={bucket} className={`${bucketColors[bucket]} transition-all`} style={{ width: `${pct}%` }} title={`${bucketLabels[bucket]}: £${amount}`} /> : null;
          })}
        </div>
        <div className="grid grid-cols-5 gap-2 mt-3">
          {Object.entries(data.totals || {}).map(([bucket, amount]) => (
            <div key={bucket} className="text-center">
              <div className={`w-3 h-3 rounded-full mx-auto mb-1 ${bucketColors[bucket]}`} />
              <div className="text-[10px] text-stone-500">{bucketLabels[bucket]}</div>
              <div className="text-xs font-bold text-stone-800">£{amount?.toLocaleString()}</div>
              <div className="text-[9px] text-stone-400">{data.counts?.[bucket] || 0} inv</div>
            </div>
          ))}
        </div>
      </div>

      {/* Invoice List */}
      {Object.entries(data.buckets || {}).map(([bucket, invoices]) => invoices.length > 0 && (
        <div key={bucket} className="bg-white rounded-xl border border-stone-200 p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2.5 h-2.5 rounded-full ${bucketColors[bucket]}`} />
            <span className="text-xs font-semibold text-stone-700">{bucketLabels[bucket]} ({invoices.length})</span>
            <span className="text-xs text-stone-500 ml-auto">£{data.totals?.[bucket]?.toLocaleString()}</span>
          </div>
          <div className="space-y-1.5">
            {invoices.map(inv => (
              <div key={inv.id} className="flex items-center justify-between text-xs bg-stone-50 rounded-lg px-3 py-2">
                <div>
                  <span className="font-semibold text-stone-700">{inv.invoice_number}</span>
                  <span className="text-stone-400 ml-2">{inv.counterparty}</span>
                </div>
                <div className="flex items-center gap-3">
                  {inv.days_overdue > 0 && <span className="text-[10px] text-red-600 font-medium">{inv.days_overdue}d overdue</span>}
                  <span className="font-bold text-stone-800">£{inv.balance_due}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
      {data.total_outstanding === 0 && <div className="text-center py-8 text-stone-400 text-sm">No outstanding {isAR ? "receivables" : "payables"}</div>}
    </div>
  );
}

// ---- Night Audit / Daily Revenue ----
function NightAuditTab({ propertyId }) {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [report, setReport] = useState(null);
  const [week, setWeek] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      axios.get(`${API}/accounting/night-audit/${propertyId}?date=${date}`),
      axios.get(`${API}/accounting/night-audit-week/${propertyId}`),
    ]).then(([r, w]) => { setReport(r.data); setWeek(w.data); }).catch(() => {}).finally(() => setLoading(false));
  }, [propertyId, date]);

  if (loading) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="space-y-4" data-testid="night-audit-tab">
      <div className="flex items-center gap-3">
        <Sun size={16} className="text-amber-500" />
        <span className="text-sm font-semibold text-stone-800">Daily Revenue Report</span>
        <Input type="date" value={date} onChange={e => setDate(e.target.value)} className="h-8 text-xs w-40 ml-auto" data-testid="audit-date-picker" />
      </div>

      {report && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
              <div className="text-xl font-bold text-emerald-700">£{report.total_revenue?.toLocaleString()}</div>
              <div className="text-[10px] text-emerald-600">Total Revenue</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-center">
              <div className="text-xl font-bold text-blue-700">£{report.room_revenue?.toLocaleString()}</div>
              <div className="text-[10px] text-blue-600">{report.rooms_occupied} Rooms</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center">
              <div className="text-xl font-bold text-red-600">£{report.total_expenses?.toLocaleString()}</div>
              <div className="text-[10px] text-red-500">{report.expense_entries} Expenses</div>
            </div>
            <div className={`border rounded-xl p-3 text-center ${report.net_revenue >= 0 ? "bg-indigo-50 border-indigo-200" : "bg-red-50 border-red-200"}`}>
              <div className={`text-xl font-bold ${report.net_revenue >= 0 ? "text-indigo-700" : "text-red-600"}`}>£{report.net_revenue?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">Net Revenue</div>
            </div>
          </div>

          {Object.keys(report.other_income || {}).length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-xs font-semibold text-stone-700 mb-2">Revenue Breakdown</div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs"><span className="text-stone-600">Room Revenue</span><span className="font-bold text-emerald-600">£{report.room_revenue}</span></div>
                {Object.entries(report.other_income).map(([cat, amt]) => (
                  <div key={cat} className="flex justify-between text-xs"><span className="text-stone-600">{cat.replace(/_/g, " ")}</span><span className="font-bold text-emerald-600">£{amt}</span></div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="text-xs font-semibold text-stone-700 mb-2">Payments & Invoices</div>
            <div className="flex gap-6 text-xs">
              <span className="text-stone-600">Payments Received: <strong className="text-emerald-600">£{report.payments_received}</strong></span>
              <span className="text-stone-600">Invoices Created: <strong>{report.invoices_created}</strong></span>
            </div>
          </div>
        </>
      )}

      {/* 7-Day Trend */}
      {week.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-xs font-semibold text-stone-700 mb-3">7-Day Revenue Trend</div>
          <div className="flex items-end gap-1.5 h-28">
            {week.map((d, i) => {
              const maxRev = Math.max(...week.map(w => w.total_revenue || 1), 1);
              const h = ((d.total_revenue || 0) / maxRev) * 100;
              const isToday = d.date === date;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1" onClick={() => setDate(d.date)}>
                  <span className="text-[9px] text-stone-500 font-medium">£{d.total_revenue || 0}</span>
                  <div className={`w-full rounded-t-lg cursor-pointer transition-all ${isToday ? "bg-indigo-500" : "bg-stone-200 hover:bg-stone-300"}`} style={{ height: `${Math.max(h, 4)}%` }} />
                  <span className={`text-[8px] ${isToday ? "text-indigo-600 font-bold" : "text-stone-400"}`}>{new Date(d.date).toLocaleDateString("en-GB", { weekday: "short" })}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Cash Flow Statement ----
function CashFlowTab({ propertyId, month }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/accounting/cash-flow/${propertyId}?period=${month}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId, month]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  const sections = [
    { title: "Operating Activities", color: "emerald", items: [
      { label: "Revenue", value: data.operating.revenue, positive: true },
      { label: "Expenses", value: -data.operating.expenses, positive: false },
      { label: "AR Collections", value: data.operating.ar_collected, positive: true },
      { label: "AP Payments", value: -data.operating.ap_paid, positive: false },
    ], net: data.operating.net },
    { title: "Investing Activities", color: "blue", items: [
      { label: "Capital Expenditure", value: -data.investing.capex, positive: false },
    ], net: data.investing.net },
    { title: "Financing Activities", color: "purple", items: [
      { label: "Lease & Insurance", value: data.financing.net, positive: data.financing.net >= 0 },
    ], net: data.financing.net },
  ];

  return (
    <div className="space-y-4" data-testid="cash-flow-tab">
      <div className={`rounded-xl p-5 border ${data.net_cash_flow >= 0 ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
        <div className="text-xs font-semibold uppercase text-stone-600">Net Cash Flow — {data.period}</div>
        <div className={`text-3xl font-black mt-1 ${data.net_cash_flow >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{data.net_cash_flow?.toLocaleString()}</div>
      </div>
      {sections.map(s => (
        <div key={s.title} className="bg-white rounded-xl border border-stone-200 p-4">
          <div className={`text-xs font-semibold uppercase mb-3 text-${s.color}-600`}>{s.title}</div>
          <div className="space-y-1.5">
            {s.items.map(item => (
              <div key={item.label} className="flex justify-between text-xs">
                <span className="text-stone-600">{item.label}</span>
                <span className={`font-bold ${item.value >= 0 ? "text-emerald-600" : "text-red-500"}`}>{item.value >= 0 ? "+" : ""}£{Math.abs(item.value).toLocaleString()}</span>
              </div>
            ))}
            <div className="flex justify-between text-xs pt-2 border-t border-stone-100">
              <span className="font-semibold text-stone-700">Net</span>
              <span className={`font-bold ${s.net >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{s.net?.toLocaleString()}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Payment Tracking ----
function PaymentsTab({ propertyId, month }) {
  const [payments, setPayments] = useState([]);
  const [showRecord, setShowRecord] = useState(false);
  const [form, setForm] = useState({ amount: 0, method: "bank_transfer", payment_type: "received", counterparty: "", reference: "", invoice_id: "", date: new Date().toISOString().slice(0, 10) });

  const fetch = useCallback(async () => { const r = await axios.get(`${API}/accounting/payments/${propertyId}?month=${month}`); setPayments(r.data); }, [propertyId, month]);
  useEffect(() => { fetch(); }, [fetch]);

  const record = async () => {
    if (!form.amount) return toast.error("Amount required");
    await axios.post(`${API}/accounting/payments`, { ...form, property_id: propertyId });
    setShowRecord(false); setForm({ amount: 0, method: "bank_transfer", payment_type: "received", counterparty: "", reference: "", invoice_id: "", date: new Date().toISOString().slice(0, 10) });
    fetch(); toast.success("Payment recorded");
  };

  const totalReceived = payments.filter(p => p.payment_type === "received").reduce((s, p) => s + (p.amount || 0), 0);
  const totalMade = payments.filter(p => p.payment_type === "made").reduce((s, p) => s + (p.amount || 0), 0);

  return (
    <div className="space-y-3" data-testid="payments-tab">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-emerald-700">£{totalReceived.toLocaleString()}</div>
          <div className="text-[10px] text-emerald-600">Received</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center">
          <div className="text-lg font-bold text-red-600">£{totalMade.toLocaleString()}</div>
          <div className="text-[10px] text-red-500">Paid Out</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className={`text-lg font-bold ${totalReceived - totalMade >= 0 ? "text-indigo-700" : "text-red-600"}`}>£{(totalReceived - totalMade).toLocaleString()}</div>
          <div className="text-[10px] text-stone-500">Net</div>
        </div>
      </div>
      <div className="flex justify-end"><button onClick={() => setShowRecord(true)} className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium" data-testid="record-payment-btn"><CreditCard size={12} className="inline mr-1" /> Record Payment</button></div>
      {payments.length === 0 ? <div className="text-center py-10 text-stone-400 text-sm">No payments recorded for {month}</div> :
        payments.map(p => (
          <div key={p.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between" data-testid={`payment-${p.id}`}>
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${p.payment_type === "received" ? "bg-emerald-50" : "bg-red-50"}`}>
                {p.payment_type === "received" ? <ArrowDown size={14} className="text-emerald-500" /> : <ArrowUp size={14} className="text-red-500" />}
              </div>
              <div>
                <div className="text-xs font-semibold text-stone-800">{p.counterparty || "N/A"}</div>
                <div className="text-[10px] text-stone-400">{p.date} · {p.method?.replace(/_/g, " ")} {p.reference && `· Ref: ${p.reference}`}</div>
              </div>
            </div>
            <span className={`text-sm font-bold ${p.payment_type === "received" ? "text-emerald-600" : "text-red-500"}`}>{p.payment_type === "received" ? "+" : "-"}£{p.amount}</span>
          </div>
        ))}
      <Dialog open={showRecord} onOpenChange={setShowRecord}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Record Payment</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={form.payment_type} onValueChange={v => setForm(p => ({...p, payment_type: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="received">Payment Received</SelectItem><SelectItem value="made">Payment Made</SelectItem></SelectContent>
            </Select>
            <Input placeholder="From / To (counterparty)" value={form.counterparty} onChange={e => setForm(p => ({...p, counterparty: e.target.value}))} data-testid="payment-counterparty" />
            <div className="grid grid-cols-2 gap-2">
              <Input type="number" placeholder="Amount (£)" value={form.amount || ""} onChange={e => setForm(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="payment-amount" />
              <Input type="date" value={form.date} onChange={e => setForm(p => ({...p, date: e.target.value}))} />
            </div>
            <Select value={form.method} onValueChange={v => setForm(p => ({...p, method: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{PAYMENT_METHODS.map(m => <SelectItem key={m} value={m}>{m.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
            </Select>
            <Input placeholder="Reference / Cheque No." value={form.reference} onChange={e => setForm(p => ({...p, reference: e.target.value}))} />
            <button onClick={record} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium" data-testid="save-payment-btn">Save Payment</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- Journal Entries ----
function JournalEntriesTab({ propertyId, month }) {
  const [entries, setEntries] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ description: "", date: new Date().toISOString().slice(0, 10), lines: [{ account: "", description: "", debit: 0, credit: 0 }, { account: "", description: "", debit: 0, credit: 0 }] });

  const fetch = useCallback(async () => { const r = await axios.get(`${API}/accounting/journal-entries/${propertyId}?month=${month}`); setEntries(r.data); }, [propertyId, month]);
  useEffect(() => { fetch(); }, [fetch]);

  const create = async () => {
    try {
      await axios.post(`${API}/accounting/journal-entries`, { ...form, property_id: propertyId });
      setShowCreate(false); fetch(); toast.success("Journal entry posted");
    } catch (e) { toast.error(e.response?.data?.detail || "Debit must equal credit"); }
  };

  const totalDebit = form.lines.reduce((s, l) => s + (l.debit || 0), 0);
  const totalCredit = form.lines.reduce((s, l) => s + (l.credit || 0), 0);
  const balanced = Math.abs(totalDebit - totalCredit) < 0.01;

  return (
    <div className="space-y-3" data-testid="journal-entries-tab">
      <div className="flex justify-end"><button onClick={() => setShowCreate(true)} className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium" data-testid="new-journal-btn"><BookOpen size={12} className="inline mr-1" /> New Entry</button></div>
      {entries.length === 0 ? <div className="text-center py-10 text-stone-400 text-sm">No journal entries for {month}</div> :
        entries.map(e => (
          <div key={e.id} className={`bg-white border rounded-xl p-3 ${e.status === "voided" ? "border-red-200 opacity-60" : "border-stone-200"}`} data-testid={`je-${e.id}`}>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-indigo-700 font-mono">{e.entry_number}</span>
                <span className="text-xs text-stone-600">{e.description}</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`text-[9px] ${e.status === "posted" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{e.status}</Badge>
                <span className="text-[10px] text-stone-400">{e.date}</span>
              </div>
            </div>
            <div className="text-[10px] space-y-0.5">
              {e.lines?.map((line, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-stone-500 w-24 truncate">{line.account || "—"}</span>
                  <span className="text-stone-600 flex-1">{line.description}</span>
                  <span className="w-16 text-right font-mono text-emerald-600">{line.debit ? `£${line.debit}` : ""}</span>
                  <span className="w-16 text-right font-mono text-red-500">{line.credit ? `£${line.credit}` : ""}</span>
                </div>
              ))}
              <div className="flex items-center gap-3 pt-1 border-t border-stone-100 font-semibold">
                <span className="flex-1" /><span className="w-16 text-right font-mono text-emerald-700">£{e.total_debit}</span><span className="w-16 text-right font-mono text-red-600">£{e.total_credit}</span>
              </div>
            </div>
          </div>
        ))}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg"><DialogHeader><DialogTitle>New Journal Entry</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="Description" value={form.description} onChange={e => setForm(p => ({...p, description: e.target.value}))} data-testid="je-description" />
              <Input type="date" value={form.date} onChange={e => setForm(p => ({...p, date: e.target.value}))} />
            </div>
            <div className="text-[10px] grid grid-cols-[1fr_1fr_80px_80px] gap-1 font-semibold text-stone-500 px-1"><span>Account</span><span>Description</span><span className="text-right">Debit</span><span className="text-right">Credit</span></div>
            {form.lines.map((line, i) => (
              <div key={i} className="grid grid-cols-[1fr_1fr_80px_80px_24px] gap-1 items-center">
                <Input placeholder="Account" className="text-xs h-8" value={line.account} onChange={e => { const lines = [...form.lines]; lines[i].account = e.target.value; setForm(p => ({...p, lines})); }} />
                <Input placeholder="Desc" className="text-xs h-8" value={line.description} onChange={e => { const lines = [...form.lines]; lines[i].description = e.target.value; setForm(p => ({...p, lines})); }} />
                <Input type="number" placeholder="0" className="text-xs h-8 text-right" value={line.debit || ""} onChange={e => { const lines = [...form.lines]; lines[i].debit = parseFloat(e.target.value) || 0; setForm(p => ({...p, lines})); }} />
                <Input type="number" placeholder="0" className="text-xs h-8 text-right" value={line.credit || ""} onChange={e => { const lines = [...form.lines]; lines[i].credit = parseFloat(e.target.value) || 0; setForm(p => ({...p, lines})); }} />
                {form.lines.length > 2 && <button onClick={() => setForm(p => ({...p, lines: p.lines.filter((_, j) => j !== i)}))} className="text-stone-300 hover:text-red-400"><Trash size={12} /></button>}
              </div>
            ))}
            <button onClick={() => setForm(p => ({...p, lines: [...p.lines, { account: "", description: "", debit: 0, credit: 0 }]}))} className="text-[10px] text-blue-600">+ Add line</button>
            <div className={`flex justify-between text-xs px-1 py-2 rounded-lg ${balanced ? "bg-emerald-50" : "bg-red-50"}`}>
              <span>Debit: £{totalDebit} | Credit: £{totalCredit}</span>
              <span className={`font-semibold ${balanced ? "text-emerald-600" : "text-red-600"}`}>{balanced ? "Balanced" : "Unbalanced"}</span>
            </div>
            <button onClick={create} disabled={!balanced} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium disabled:opacity-40" data-testid="post-je-btn">Post Entry</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- Balance Sheet ----
function BalanceSheetTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/accounting/balance-sheet/${propertyId}`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="space-y-4" data-testid="balance-sheet-tab">
      <div className="text-[10px] text-stone-400 text-right">As of {data.as_of}</div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Assets */}
        <div className="bg-white rounded-xl border border-emerald-200 p-4">
          <div className="text-xs font-semibold text-emerald-700 uppercase mb-3">Assets</div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-stone-600">Cash & Equivalents</span><span className="font-bold text-stone-800">£{data.assets?.cash_and_equivalents?.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-stone-600">Accounts Receivable</span><span className="font-bold text-stone-800">£{data.assets?.accounts_receivable?.toLocaleString()}</span></div>
            <div className="flex justify-between pt-2 border-t border-emerald-100 font-bold"><span className="text-emerald-700">Total Assets</span><span className="text-emerald-800">£{data.assets?.total_assets?.toLocaleString()}</span></div>
          </div>
        </div>
        {/* Liabilities */}
        <div className="bg-white rounded-xl border border-red-200 p-4">
          <div className="text-xs font-semibold text-red-600 uppercase mb-3">Liabilities</div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-stone-600">Accounts Payable</span><span className="font-bold text-stone-800">£{data.liabilities?.accounts_payable?.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-stone-600">VAT Liability</span><span className="font-bold text-stone-800">£{data.liabilities?.vat_liability?.toLocaleString()}</span></div>
            <div className="flex justify-between pt-2 border-t border-red-100 font-bold"><span className="text-red-600">Total Liabilities</span><span className="text-red-700">£{data.liabilities?.total_liabilities?.toLocaleString()}</span></div>
          </div>
        </div>
      </div>
      {/* Equity */}
      <div className={`rounded-xl border p-4 ${data.equity?.total_equity >= 0 ? "bg-indigo-50 border-indigo-200" : "bg-red-50 border-red-200"}`}>
        <div className="text-xs font-semibold text-indigo-700 uppercase mb-2">Owner's Equity</div>
        <div className="flex justify-between text-xs">
          <span className="text-stone-600">Retained Earnings</span>
          <span className={`text-xl font-black ${data.equity?.total_equity >= 0 ? "text-indigo-800" : "text-red-600"}`}>£{data.equity?.total_equity?.toLocaleString()}</span>
        </div>
      </div>
      <div className={`text-center text-xs font-medium py-2 rounded-lg ${data.balanced ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
        {data.balanced ? "Assets = Liabilities + Equity (Balanced)" : "Warning: Balance sheet is not balanced"}
      </div>
    </div>
  );
}

// ---- Revenue Forecasting ----
function ForecastTab({ propertyId }) {
  const [data, setData] = useState(null);
  useEffect(() => { axios.get(`${API}/accounting/forecast/${propertyId}?months=3`).then(r => setData(r.data)).catch(() => {}); }, [propertyId]);
  if (!data) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  const confColors = { high: "bg-emerald-100 text-emerald-700", medium: "bg-amber-100 text-amber-700", low: "bg-red-100 text-red-700" };

  return (
    <div className="space-y-4" data-testid="forecast-tab">
      <div className="bg-white rounded-xl border border-stone-200 p-4">
        <div className="text-xs font-semibold text-stone-700 mb-1">Historical Average (6 months)</div>
        <div className="text-2xl font-bold text-stone-800">£{data.historical_avg_monthly?.toLocaleString()}/month</div>
        <div className="text-[10px] text-stone-400">Monthly trend: {data.monthly_trend >= 0 ? "+" : ""}£{data.monthly_trend?.toLocaleString()}</div>
      </div>
      {data.forecasts?.map(f => (
        <div key={f.month} className="bg-white rounded-xl border border-stone-200 p-4" data-testid={`forecast-${f.month}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-stone-800">{new Date(f.month + "-01").toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</span>
            <Badge className={`text-[9px] ${confColors[f.confidence]}`}>{f.confidence} confidence</Badge>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-lg font-bold text-emerald-700">£{f.projected_revenue?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">Projected</div>
            </div>
            <div>
              <div className="text-lg font-bold text-blue-700">£{f.confirmed_revenue?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">{f.confirmed_bookings} Bookings</div>
            </div>
            <div>
              <div className="text-lg font-bold text-stone-600">£{f.historical_avg?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">Historical Avg</div>
            </div>
          </div>
          <div className="mt-2">
            <Progress value={f.confirmed_revenue && f.projected_revenue ? Math.min(100, (f.confirmed_revenue / f.projected_revenue) * 100) : 0} className="h-2" />
            <div className="text-[9px] text-stone-400 mt-0.5">{f.confirmed_revenue && f.projected_revenue ? Math.round((f.confirmed_revenue / f.projected_revenue) * 100) : 0}% of projection confirmed</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Recurring Invoices ----
function RecurringTab({ propertyId }) {
  const [recs, setRecs] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ invoice_type: "receivable", counterparty: "", frequency: "monthly", start_date: "", end_date: "", items: [{ description: "", quantity: 1, unit_price: 0, vat_rate: 20 }] });

  const fetch = useCallback(async () => { const r = await axios.get(`${API}/accounting/recurring-invoices/${propertyId}`); setRecs(r.data); }, [propertyId]);
  useEffect(() => { fetch(); }, [fetch]);

  const create = async () => {
    if (!form.counterparty || !form.start_date) return toast.error("Counterparty and start date required");
    await axios.post(`${API}/accounting/recurring-invoices`, { ...form, property_id: propertyId });
    setShowCreate(false); fetch(); toast.success("Recurring invoice created");
  };
  const generate = async () => {
    const r = await axios.post(`${API}/accounting/recurring-invoices/generate/${propertyId}`);
    toast.success(`Generated ${r.data.generated} invoice(s)`); fetch();
  };
  const toggle = async (id, enabled) => { await axios.put(`${API}/accounting/recurring-invoices/${id}`, { enabled: !enabled }); fetch(); };
  const del = async (id) => { await axios.delete(`${API}/accounting/recurring-invoices/${id}`); fetch(); toast.success("Deleted"); };

  return (
    <div className="space-y-3" data-testid="recurring-tab">
      <div className="flex justify-end gap-2">
        <button onClick={generate} className="text-xs px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg font-medium" data-testid="generate-recurring-btn"><ArrowsClockwise size={12} className="inline mr-1" /> Generate Due</button>
        <button onClick={() => setShowCreate(true)} className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium" data-testid="new-recurring-btn"><Plus size={12} className="inline mr-1" /> New Recurring</button>
      </div>
      {recs.length === 0 ? <div className="text-center py-10 text-stone-400 text-sm">No recurring invoices</div> :
        recs.map(r => (
          <div key={r.id} className={`bg-white border border-stone-200 rounded-xl p-3 ${!r.enabled ? "opacity-50" : ""}`} data-testid={`rec-${r.id}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold text-stone-800">{r.counterparty}</div>
                <div className="text-[10px] text-stone-400">{r.invoice_type} · {r.frequency} · Next: {r.next_date} · Generated: {r.times_generated}x</div>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={r.enabled} onCheckedChange={() => toggle(r.id, r.enabled)} className="scale-75" />
                <button onClick={() => del(r.id)} className="text-stone-300 hover:text-red-400"><Trash size={13} /></button>
              </div>
            </div>
          </div>
        ))}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>New Recurring Invoice</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={form.invoice_type} onValueChange={v => setForm(p => ({...p, invoice_type: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="receivable">Receivable</SelectItem><SelectItem value="payable">Payable</SelectItem></SelectContent>
            </Select>
            <Input placeholder="Counterparty" value={form.counterparty} onChange={e => setForm(p => ({...p, counterparty: e.target.value}))} data-testid="rec-counterparty" />
            <Select value={form.frequency} onValueChange={v => setForm(p => ({...p, frequency: v}))}>
              <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="quarterly">Quarterly</SelectItem></SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="text-[10px] text-stone-500">Start Date</label><Input type="date" value={form.start_date} onChange={e => setForm(p => ({...p, start_date: e.target.value}))} /></div>
              <div><label className="text-[10px] text-stone-500">End Date (optional)</label><Input type="date" value={form.end_date} onChange={e => setForm(p => ({...p, end_date: e.target.value}))} /></div>
            </div>
            {form.items.map((item, i) => (
              <div key={i} className="grid grid-cols-3 gap-1">
                <Input placeholder="Description" className="text-xs" value={item.description} onChange={e => { const items = [...form.items]; items[i].description = e.target.value; setForm(p => ({...p, items})); }} />
                <Input type="number" placeholder="Qty" className="text-xs" value={item.quantity || ""} onChange={e => { const items = [...form.items]; items[i].quantity = parseFloat(e.target.value) || 0; setForm(p => ({...p, items})); }} />
                <Input type="number" placeholder="£" className="text-xs" value={item.unit_price || ""} onChange={e => { const items = [...form.items]; items[i].unit_price = parseFloat(e.target.value) || 0; setForm(p => ({...p, items})); }} />
              </div>
            ))}
            <button onClick={create} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium" data-testid="create-recurring-btn">Create</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- Bank Reconciliation Tab ----
function BankReconciliationTab({ propertyId, month }) {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showImport, setShowImport] = useState(false);
  const [showAddTx, setShowAddTx] = useState(false);
  const [matching, setMatching] = useState(false);
  const [filterMatched, setFilterMatched] = useState("");
  const [newTx, setNewTx] = useState({ date: new Date().toISOString().slice(0, 10), description: "", reference: "", amount: 0 });
  const [importData, setImportData] = useState("");

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t, a] = await Promise.all([
        axios.get(`${API}/accounting/bank-reconciliation/summary/${propertyId}?month=${month}`),
        axios.get(`${API}/accounting/bank-transactions/${propertyId}?month=${month}${filterMatched ? `&matched=${filterMatched}` : ""}`),
        axios.get(`${API}/accounting/bank-accounts/${propertyId}`),
      ]);
      setSummary(s.data); setTransactions(t.data); setAccounts(a.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId, month, filterMatched]);

  useEffect(() => { fetch(); }, [fetch]);

  const autoMatch = async () => {
    setMatching(true);
    try {
      const { data } = await axios.post(`${API}/accounting/bank-reconciliation/auto-match/${propertyId}`);
      toast.success(`Matched ${data.matched} transactions (${data.remaining_unmatched} remaining)`);
      fetch();
    } catch (e) { toast.error("Auto-match failed"); }
    finally { setMatching(false); }
  };

  const addTransaction = async () => {
    if (!newTx.amount) return toast.error("Amount required");
    const accountId = accounts[0]?.id || "";
    await axios.post(`${API}/accounting/bank-transactions/manual`, { ...newTx, property_id: propertyId, account_id: accountId });
    setShowAddTx(false); setNewTx({ date: new Date().toISOString().slice(0, 10), description: "", reference: "", amount: 0 });
    fetch(); toast.success("Transaction added");
  };

  const importTransactions = async () => {
    try {
      const lines = importData.trim().split("\n").filter(Boolean);
      const txns = lines.map(line => {
        const parts = line.split(",").map(p => p.trim());
        return { date: parts[0] || "", description: parts[1] || "", amount: parseFloat(parts[2]) || 0, reference: parts[3] || "" };
      });
      const accountId = accounts[0]?.id || "";
      const { data } = await axios.post(`${API}/accounting/bank-transactions/import`, { property_id: propertyId, account_id: accountId, transactions: txns });
      toast.success(`Imported ${data.imported} transactions (${data.duplicates} duplicates skipped)`);
      setShowImport(false); setImportData("");
      fetch();
    } catch (e) { toast.error("Import failed"); }
  };

  const unmatch = async (txId) => {
    await axios.post(`${API}/accounting/bank-reconciliation/unmatch/${txId}`);
    fetch();
  };

  const deleteTx = async (txId) => {
    await axios.delete(`${API}/accounting/bank-transactions/${txId}`);
    fetch();
  };

  if (loading) return <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="space-y-4" data-testid="bank-recon-tab">
      {/* Summary */}
      {summary && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className={`rounded-xl p-4 border text-center ${summary.reconciled ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`}>
              <div className={`text-xl font-bold ${summary.reconciled ? "text-emerald-700" : "text-amber-700"}`}>{summary.match_rate}%</div>
              <div className="text-[10px] text-stone-500">Match Rate</div>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <div className="text-xl font-bold text-stone-800">{summary.total_transactions}</div>
              <div className="text-[10px] text-stone-500">{summary.matched} matched / {summary.unmatched} unmatched</div>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4 text-center">
              <div className="text-xl font-bold text-blue-700">£{summary.bank_net?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">Bank Net</div>
            </div>
            <div className={`rounded-xl p-4 border text-center ${Math.abs(summary.discrepancy) < 0.02 ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>
              <div className={`text-xl font-bold ${Math.abs(summary.discrepancy) < 0.02 ? "text-emerald-700" : "text-red-600"}`}>£{summary.discrepancy?.toLocaleString()}</div>
              <div className="text-[10px] text-stone-500">Discrepancy</div>
            </div>
          </div>

          {/* Bank vs System comparison */}
          <div className="bg-white rounded-xl border border-stone-200 p-4">
            <div className="text-xs font-semibold text-stone-700 mb-2">Bank vs System Comparison</div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <div className="text-[10px] text-stone-400 uppercase mb-1">Bank Statement</div>
                <div className="flex justify-between"><span>Credits (In)</span><span className="font-bold text-emerald-600">£{summary.bank_credits?.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Debits (Out)</span><span className="font-bold text-red-500">£{summary.bank_debits?.toLocaleString()}</span></div>
                <div className="flex justify-between pt-1 border-t border-stone-100"><span className="font-semibold">Net</span><span className="font-bold">£{summary.bank_net?.toLocaleString()}</span></div>
              </div>
              <div>
                <div className="text-[10px] text-stone-400 uppercase mb-1">System Records</div>
                <div className="flex justify-between"><span>Income</span><span className="font-bold text-emerald-600">£{summary.system_income?.toLocaleString()}</span></div>
                <div className="flex justify-between"><span>Expenses</span><span className="font-bold text-red-500">£{summary.system_expenses?.toLocaleString()}</span></div>
                <div className="flex justify-between pt-1 border-t border-stone-100"><span className="font-semibold">Net</span><span className="font-bold">£{summary.system_net?.toLocaleString()}</span></div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={autoMatch} disabled={matching}
          className="text-xs px-3 py-1.5 bg-indigo-500 text-white rounded-lg font-medium disabled:opacity-50" data-testid="auto-match-btn">
          <ArrowsClockwise size={12} className={`inline mr-1 ${matching ? "animate-spin" : ""}`} /> {matching ? "Matching..." : "Auto-Match"}
        </button>
        <button onClick={() => setShowAddTx(true)} className="text-xs px-3 py-1.5 bg-emerald-50 text-emerald-700 rounded-lg font-medium" data-testid="add-bank-tx-btn">
          <Plus size={12} className="inline mr-1" /> Add Transaction
        </button>
        <button onClick={() => setShowImport(true)} className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg font-medium" data-testid="import-btn">
          <ArrowDown size={12} className="inline mr-1" /> Import CSV
        </button>
        <div className="ml-auto flex gap-1">
          {["", "true", "false"].map(v => (
            <button key={v} onClick={() => setFilterMatched(v)}
              className={`text-[10px] px-2 py-1 rounded-full ${filterMatched === v ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-500"}`}>
              {v === "" ? "All" : v === "true" ? "Matched" : "Unmatched"}
            </button>
          ))}
        </div>
      </div>

      {/* Transaction List */}
      {transactions.length === 0 ? (
        <div className="text-center py-10 text-stone-400 text-sm">No bank transactions for {month}. Import a statement or add manually.</div>
      ) : (
        <div className="space-y-1.5">
          {transactions.map(tx => (
            <div key={tx.id} className={`bg-white border rounded-lg px-3 py-2 flex items-center justify-between ${tx.matched ? "border-emerald-200" : "border-stone-200"}`} data-testid={`bank-tx-${tx.id}`}>
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${tx.matched ? "bg-emerald-500" : "bg-amber-400"}`} />
                <div>
                  <div className="text-xs font-medium text-stone-800">{tx.description || "—"}</div>
                  <div className="text-[10px] text-stone-400">{tx.date} {tx.reference && `· Ref: ${tx.reference}`}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {tx.matched && (
                  <span className="text-[9px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-medium">
                    {tx.match_confidence}% · {tx.matched_type}
                  </span>
                )}
                <span className={`text-sm font-bold ${tx.amount >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                  {tx.amount >= 0 ? "+" : ""}£{Math.abs(tx.amount).toLocaleString()}
                </span>
                <div className="flex gap-1">
                  {tx.matched && <button onClick={() => unmatch(tx.id)} className="text-[10px] text-amber-600 hover:text-amber-700">Unmatch</button>}
                  <button onClick={() => deleteTx(tx.id)} className="text-stone-300 hover:text-red-400"><Trash size={12} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Transaction Dialog */}
      <Dialog open={showAddTx} onOpenChange={setShowAddTx}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Add Bank Transaction</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Input type="date" value={newTx.date} onChange={e => setNewTx(p => ({...p, date: e.target.value}))} />
            <Input placeholder="Description" value={newTx.description} onChange={e => setNewTx(p => ({...p, description: e.target.value}))} data-testid="bank-tx-desc" />
            <Input type="number" placeholder="Amount (+ for credit, - for debit)" value={newTx.amount || ""} onChange={e => setNewTx(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="bank-tx-amount" />
            <Input placeholder="Reference" value={newTx.reference} onChange={e => setNewTx(p => ({...p, reference: e.target.value}))} />
            <button onClick={addTransaction} className="w-full text-xs py-2 bg-indigo-500 text-white rounded-lg font-medium" data-testid="save-bank-tx-btn">Add Transaction</button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Import Dialog */}
      <Dialog open={showImport} onOpenChange={setShowImport}>
        <DialogContent className="max-w-lg"><DialogHeader><DialogTitle>Import Bank Statement (CSV)</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-stone-500">Paste CSV data: one transaction per line. Format: date, description, amount, reference</p>
            <Textarea rows={8} placeholder={"2026-04-01, Room payment, 450, REF001\n2026-04-02, Supplier payment, -120, INV-445"} value={importData} onChange={e => setImportData(e.target.value)} className="text-xs font-mono" data-testid="import-csv-data" />
            <button onClick={importTransactions} className="w-full text-xs py-2 bg-blue-600 text-white rounded-lg font-medium" data-testid="import-csv-btn">Import Transactions</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- Audit Trail ----
function AuditTrailTab({ propertyId }) {
  const [trail, setTrail] = useState([]);
  useEffect(() => { axios.get(`${API}/accounting/audit-trail/${propertyId}?limit=50`).then(r => setTrail(r.data)).catch(() => {}); }, [propertyId]);

  return (
    <div className="space-y-2" data-testid="audit-trail-tab">
      <div className="text-sm font-semibold text-stone-700 flex items-center gap-1.5"><History size={14} /> Audit Trail</div>
      {trail.length === 0 ? <div className="text-center py-10 text-stone-400 text-sm">No audit entries yet</div> :
        trail.map(e => (
          <div key={e.id} className="bg-white border border-stone-200 rounded-lg px-3 py-2 flex items-start gap-3 text-xs" data-testid={`audit-${e.id}`}>
            <div className="w-2 h-2 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-stone-700">{e.user_name}</span>
                <span className="text-stone-400">{e.action?.replace(/_/g, " ")}</span>
                <span className="text-[10px] text-stone-400 ml-auto">{new Date(e.timestamp).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
              </div>
              {e.details && <p className="text-[10px] text-stone-500 mt-0.5">{e.details}</p>}
            </div>
          </div>
        ))}
    </div>
  );
}

// ---- VAT Tab ----
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
        <div className={`border rounded-xl p-4 text-center ${vat.net_vat_payable >= 0 ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200"}`}><div className={`text-xl font-bold ${vat.net_vat_payable >= 0 ? "text-red-600" : "text-emerald-600"}`}>£{vat.net_vat_payable}</div><div className="text-[10px] text-stone-500 uppercase">{vat.net_vat_payable >= 0 ? "VAT Payable" : "VAT Refund"}</div></div>
      </div>
      <div className="text-[11px] text-stone-400 text-center">Period: {vat.period} · {vat.invoice_count} invoices processed</div>
    </div>
  );
}

// ---- Trends Tab ----
function TrendsTab({ propertyId }) {
  const [trends, setTrends] = useState([]);
  useEffect(() => { axios.get(`${API}/accounting/trends/${propertyId}?months=6`).then(r => setTrends(r.data)); }, [propertyId]);
  const maxVal = Math.max(...trends.map(t => Math.max(t.income, t.expenses)), 1);
  return (
    <div className="space-y-3" data-testid="trends-tab">
      <div className="text-sm font-semibold text-stone-700">6-Month P&L Trend</div>
      {trends.map(t => (
        <div key={t.month} className="bg-white border border-stone-200 rounded-lg p-3">
          <div className="flex justify-between text-xs mb-1.5"><span className="font-semibold text-stone-700">{new Date(t.month + "-01").toLocaleDateString("en-GB", { month: "short", year: "numeric" })}</span><span className={`font-bold ${t.net_profit >= 0 ? "text-emerald-600" : "text-red-600"}`}>£{t.net_profit} ({t.margin}%)</span></div>
          <div className="space-y-1">
            <div className="flex items-center gap-2"><span className="text-[9px] w-12 text-right text-stone-400">Income</span><div className="flex-1 bg-stone-100 rounded-full h-2"><div className="bg-emerald-400 h-2 rounded-full" style={{ width: `${(t.income / maxVal) * 100}%` }} /></div><span className="text-[10px] text-stone-500 w-16 text-right">£{t.income}</span></div>
            <div className="flex items-center gap-2"><span className="text-[9px] w-12 text-right text-stone-400">Expense</span><div className="flex-1 bg-stone-100 rounded-full h-2"><div className="bg-red-400 h-2 rounded-full" style={{ width: `${(t.expenses / maxVal) * 100}%` }} /></div><span className="text-[10px] text-stone-500 w-16 text-right">£{t.expenses}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Chart of Accounts ----
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
          {accts.map(a => (<div key={a.id} className="flex justify-between text-xs py-1 border-b border-stone-50"><span className="text-stone-500 font-mono">{a.code}</span><span className="text-stone-700">{a.name}</span></div>))}
        </div>
      ))}
    </div>
  );
}

// ==================== MAIN PANEL ====================

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
  const syncRevenue = async () => { await axios.post(`${API}/accounting/sync-revenue/${propertyId}?month=${month}`); fetchData(); toast.success("Revenue synced"); };
  const deleteIncome = async (id) => { await axios.delete(`${API}/accounting/income/${id}`); fetchData(); };
  const deleteExpense = async (id) => { await axios.delete(`${API}/accounting/expenses/${id}`); fetchData(); };

  const TABS = [
    { id: "overview", label: "P&L", icon: ChartPie },
    { id: "night-audit", label: "Night Audit", icon: Sun },
    { id: "income", label: `Income`, icon: TrendUp },
    { id: "expenses", label: `Expenses`, icon: TrendDown },
    { id: "invoices", label: "Invoices", icon: Receipt },
    { id: "payments", label: "Payments", icon: CreditCard },
    { id: "journal", label: "Journal", icon: BookOpen },
    { id: "ar-aging", label: "AR Aging", icon: FileText },
    { id: "ap-aging", label: "AP Aging", icon: FileText },
    { id: "cash-flow", label: "Cash Flow", icon: BarChart3 },
    { id: "balance-sheet", label: "Balance Sheet", icon: Scale },
    { id: "forecast", label: "Forecast", icon: TrendingUp },
    { id: "vat", label: "VAT", icon: CurrencyGbp },
    { id: "recurring", label: "Recurring", icon: Repeat },
    { id: "trends", label: "Trends", icon: ChartBar },
    { id: "budgets", label: "Budget", icon: ChartBar },
    { id: "accounts", label: "CoA", icon: Wallet },
    { id: "audit", label: "Audit Trail", icon: History },
    { id: "bank-recon", label: "Bank Recon", icon: Building2 },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="accounting-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="accounting-title">
            <Wallet size={22} className="text-indigo-600" weight="fill" /> Hotel Accounting
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Full-service hotel financial management</p>
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

      {/* Tabs - scrollable */}
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="flex gap-0.5 border-b border-stone-200 min-w-max">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} className={`px-2.5 py-2 text-[11px] font-medium flex items-center gap-1 border-b-2 whitespace-nowrap ${tab === t.id ? "border-indigo-500 text-indigo-700" : "border-transparent text-stone-400 hover:text-stone-600"}`} data-testid={`tab-${t.id}`}>
              <t.icon size={12} /> {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading && tab === "overview" ? <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div> : (<>
        {tab === "overview" && pnl && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5" data-testid="pnl-overview">
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5"><TrendUp size={14} className="text-emerald-500" /> Income Breakdown</div>
              {Object.entries(pnl.income_breakdown || {}).map(([cat, data]) => (
                <div key={cat} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-xs"><div className="flex items-center gap-2"><span className="text-stone-600">{cat.replace(/_/g, " ")}</span>{data.source === "auto_booking_engine" && <Badge className="text-[8px] bg-blue-50 text-blue-600">auto</Badge>}</div><span className="font-bold text-emerald-600">£{data.total}</span></div>
              ))}
              <div className="flex justify-between pt-2 text-sm font-bold"><span>Total Income</span><span className="text-emerald-700">£{pnl.total_income}</span></div>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5"><TrendDown size={14} className="text-red-500" /> Expense Breakdown</div>
              {Object.entries(pnl.expense_breakdown || {}).map(([cat, data]) => (
                <div key={cat} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-xs"><span className="text-stone-600">{cat.replace(/_/g, " ")}</span><span className="font-bold text-red-500">£{data.total}</span></div>
              ))}
              <div className="flex justify-between pt-2 text-sm font-bold"><span>Total Expenses</span><span className="text-red-600">£{pnl.total_expenses}</span></div>
            </div>
            {Object.keys(pnl.departments || {}).length > 0 && (
              <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
                <div className="text-sm font-semibold text-stone-800 mb-3">Department P&L</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {Object.entries(pnl.departments).map(([dept, d]) => (
                    <div key={dept} className={`rounded-lg p-3 border text-center ${d.net >= 0 ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}><div className="text-[10px] text-stone-500 uppercase">{dept.replace(/_/g, " ")}</div><div className={`text-sm font-bold ${d.net >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{d.net}</div><div className="text-[9px] text-stone-400">In: £{d.income} | Out: £{d.expenses}</div></div>
                  ))}
                </div>
              </div>
            )}
            <div className="lg:col-span-2 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-xl p-4 flex items-center justify-between">
              <div><div className="text-xs text-indigo-600 font-semibold uppercase">Net Profit — {pnl.period}</div><div className={`text-3xl font-black ${pnl.net_profit >= 0 ? "text-emerald-700" : "text-red-600"}`}>£{pnl.net_profit}</div></div>
              <div className="text-right"><div className="text-sm font-bold text-stone-700">{pnl.profit_margin}%</div><div className="text-[10px] text-stone-500">Profit Margin</div></div>
            </div>
          </div>
        )}

        {tab === "night-audit" && <NightAuditTab propertyId={propertyId} />}
        {tab === "income" && (
          <div className="space-y-2" data-testid="income-list">
            <div className="flex justify-end"><button onClick={() => setShowIncome(true)} className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg font-medium" data-testid="add-income-btn"><Plus size={12} className="inline mr-1" /> Add Income</button></div>
            {income.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No income entries for {month}</div> :
              income.map(e => (
                <div key={e.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3"><div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center"><ArrowDown size={14} className="text-emerald-500" /></div><div><div className="text-xs font-semibold text-stone-800">{e.description || e.category.replace(/_/g, " ")}</div><div className="text-[10px] text-stone-400">{e.date} · {e.department} · {e.source === "booking_engine" ? "Auto" : "Manual"}</div></div></div>
                  <div className="flex items-center gap-2"><span className="text-sm font-bold text-emerald-600">£{e.amount}</span>{e.source !== "booking_engine" && <button onClick={() => deleteIncome(e.id)} className="text-stone-300 hover:text-red-400"><Trash size={13} /></button>}</div>
                </div>
              ))}
          </div>
        )}
        {tab === "expenses" && (
          <div className="space-y-2" data-testid="expenses-list">
            <div className="flex justify-end"><button onClick={() => setShowExpense(true)} className="text-xs px-3 py-1.5 bg-red-500 text-white rounded-lg font-medium" data-testid="add-expense-btn"><Plus size={12} className="inline mr-1" /> Add Expense</button></div>
            {expenses.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No expense entries for {month}</div> :
              expenses.map(e => (
                <div key={e.id} className="bg-white border border-stone-200 rounded-xl p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3"><div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center"><ArrowUp size={14} className="text-red-500" /></div><div><div className="text-xs font-semibold text-stone-800">{e.description || e.category.replace(/_/g, " ")}</div><div className="text-[10px] text-stone-400">{e.date} · {e.department}{e.vendor ? ` · ${e.vendor}` : ""}</div></div></div>
                  <div className="flex items-center gap-2"><span className="text-sm font-bold text-red-500">£{e.amount}</span><button onClick={() => deleteExpense(e.id)} className="text-stone-300 hover:text-red-400"><Trash size={13} /></button></div>
                </div>
              ))}
          </div>
        )}
        {tab === "invoices" && <InvoicesTab propertyId={propertyId} month={month} />}
        {tab === "payments" && <PaymentsTab propertyId={propertyId} month={month} />}
        {tab === "journal" && <JournalEntriesTab propertyId={propertyId} month={month} />}
        {tab === "ar-aging" && <AgingReport propertyId={propertyId} type="ar" />}
        {tab === "ap-aging" && <AgingReport propertyId={propertyId} type="ap" />}
        {tab === "cash-flow" && <CashFlowTab propertyId={propertyId} month={month} />}
        {tab === "balance-sheet" && <BalanceSheetTab propertyId={propertyId} />}
        {tab === "forecast" && <ForecastTab propertyId={propertyId} />}
        {tab === "vat" && <VATTab propertyId={propertyId} month={month} />}
        {tab === "recurring" && <RecurringTab propertyId={propertyId} />}
        {tab === "trends" && <TrendsTab propertyId={propertyId} />}
        {tab === "budgets" && (
          <div className="space-y-2" data-testid="budgets-list">
            {budgets.length === 0 ? <div className="text-center py-12 text-stone-400 text-sm">No budgets set for {month}.</div> :
              budgets.map(b => (
                <div key={b.id} className="bg-white border border-stone-200 rounded-xl p-3">
                  <div className="flex justify-between text-xs mb-1.5"><span className="font-semibold text-stone-700">{b.department} — {b.category?.replace(/_/g, " ")}</span><Badge className={`text-[9px] ${b.status === "under_budget" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{b.status?.replace(/_/g, " ")}</Badge></div>
                  <div className="flex items-center gap-2"><Progress value={Math.min(100, (b.actual_amount / b.budgeted_amount) * 100)} className="h-2 flex-1" /><span className="text-[10px] text-stone-500">£{b.actual_amount} / £{b.budgeted_amount}</span></div>
                  <div className="text-[10px] text-stone-400 mt-0.5">Variance: £{b.variance} ({b.variance_pct}%)</div>
                </div>
              ))}
          </div>
        )}
        {tab === "accounts" && <ChartOfAccountsTab propertyId={propertyId} />}
        {tab === "audit" && <AuditTrailTab propertyId={propertyId} />}
        {tab === "bank-recon" && <BankReconciliationTab propertyId={propertyId} month={month} />}
      </>)}

      {/* Add Income Dialog */}
      <Dialog open={showIncome} onOpenChange={setShowIncome}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Add Income</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newIncome.category} onValueChange={v => setNewIncome(p => ({...p, category: v}))}><SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger><SelectContent>{INCOME_CATS.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <div className="grid grid-cols-2 gap-2"><Input type="number" placeholder="Amount (£)" value={newIncome.amount || ""} onChange={e => setNewIncome(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="income-amount" /><Input type="date" value={newIncome.date} onChange={e => setNewIncome(p => ({...p, date: e.target.value}))} /></div>
            <Select value={newIncome.department} onValueChange={v => setNewIncome(p => ({...p, department: v}))}><SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger><SelectContent>{DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <Input placeholder="Description" value={newIncome.description} onChange={e => setNewIncome(p => ({...p, description: e.target.value}))} />
            <button onClick={addIncome} className="w-full text-xs py-2 bg-emerald-500 text-white rounded-lg font-medium" data-testid="save-income">Save Income</button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={showExpense} onOpenChange={setShowExpense}>
        <DialogContent className="max-w-md"><DialogHeader><DialogTitle>Add Expense</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Select value={newExpense.category} onValueChange={v => setNewExpense(p => ({...p, category: v}))}><SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger><SelectContent>{EXPENSE_CATS.map(c => <SelectItem key={c} value={c}>{c.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <div className="grid grid-cols-2 gap-2"><Input type="number" placeholder="Amount (£)" value={newExpense.amount || ""} onChange={e => setNewExpense(p => ({...p, amount: parseFloat(e.target.value) || 0}))} data-testid="expense-amount" /><Input type="date" value={newExpense.date} onChange={e => setNewExpense(p => ({...p, date: e.target.value}))} /></div>
            <Select value={newExpense.department} onValueChange={v => setNewExpense(p => ({...p, department: v}))}><SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger><SelectContent>{DEPARTMENTS.map(d => <SelectItem key={d} value={d}>{d.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
            <Input placeholder="Vendor" value={newExpense.vendor} onChange={e => setNewExpense(p => ({...p, vendor: e.target.value}))} />
            <Input placeholder="Description" value={newExpense.description} onChange={e => setNewExpense(p => ({...p, description: e.target.value}))} />
            <button onClick={addExpense} className="w-full text-xs py-2 bg-red-500 text-white rounded-lg font-medium" data-testid="save-expense">Save Expense</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
