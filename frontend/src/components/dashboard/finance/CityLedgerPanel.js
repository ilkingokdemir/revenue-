import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Building2, RefreshCw, Plus, TrendingDown, Receipt, X,
  Mail, Phone, Printer, Trash2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const EMPTY_COMPANY = { name: "", contact_name: "", email: "", phone: "", address: "", tax_id: "",
  credit_limit: 0, payment_terms_days: 30, notes: "", active: true };
const EMPTY_INVOICE = { company_id: "", booking_ids: [], issue_date: "", due_date: "", amount: 0, currency: "GBP", notes: "", lines: [] };
const EMPTY_LINE = { description: "", amount: 0, currency: "GBP", quantity: 1 };

export const CityLedgerPanel = () => {
  const [tab, setTab] = useState("companies");
  const [companies, setCompanies] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [aging, setAging] = useState(null);
  const [loading, setLoading] = useState(false);
  const [companyForm, setCompanyForm] = useState(null);   // null = hidden, {} = new, {id,...} = edit
  const [invoiceForm, setInvoiceForm] = useState(null);
  const [payFor, setPayFor] = useState(null);             // invoice being paid
  const [emailFor, setEmailFor] = useState(null);          // invoice to email
  const [availableCurrencies, setAvailableCurrencies] = useState(["GBP", "USD", "EUR"]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [c, i, a, fx] = await Promise.all([
        axios.get(`${API}/city-ledger/companies`),
        axios.get(`${API}/city-ledger/invoices`),
        axios.get(`${API}/city-ledger/aging`),
        axios.get(`${API}/currency-fx/settings`).catch(() => ({ data: null })),
      ]);
      setCompanies(c.data || []);
      setInvoices(i.data || []);
      setAging(a.data || null);
      if (fx.data?.available_codes?.length) setAvailableCurrencies(fx.data.available_codes);
    } catch (e) { toast.error("Failed to load city ledger"); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadAll(); }, []);

  const saveCompany = async () => {
    try {
      if (companyForm.id) {
        await axios.put(`${API}/city-ledger/companies/${companyForm.id}`, companyForm);
        toast.success("Company updated");
      } else {
        await axios.post(`${API}/city-ledger/companies`, companyForm);
        toast.success("Company created");
      }
      setCompanyForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const deleteCompany = async (id) => {
    if (!window.confirm("Delete this company?")) return;
    try { await axios.delete(`${API}/city-ledger/companies/${id}`); toast.success("Deleted"); loadAll(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  const saveInvoice = async () => {
    const hasLines = (invoiceForm.lines || []).length > 0;
    if (!invoiceForm.company_id) return toast.error("Company required");
    if (!hasLines && !invoiceForm.amount) return toast.error("Amount or line items required");
    try {
      await axios.post(`${API}/city-ledger/invoices`, invoiceForm);
      toast.success("Invoice created");
      setInvoiceForm(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const recordPayment = async (amt, method = "bank_transfer", reference = "") => {
    try {
      await axios.post(`${API}/city-ledger/invoices/${payFor.id}/pay`, { amount: parseFloat(amt), method, reference });
      toast.success("Payment recorded");
      setPayFor(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const openInvoicePdf = async (inv) => {
    try {
      const { data } = await axios.get(`${API}/city-ledger/invoices/${inv.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch { toast.error("Could not open PDF"); }
  };

  const sendInvoiceEmail = async (to, subject, message) => {
    try {
      const { data } = await axios.post(`${API}/city-ledger/invoices/${emailFor.id}/email`, { to, subject, message });
      toast.success(`Invoice emailed to ${(data.sent_to || []).join(", ")}`);
      setEmailFor(null); loadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Send failed"); }
  };

  const totalOpen = companies.reduce((s, c) => s + (c.open_balance || 0), 0);
  const totalOverdue = (invoices || []).filter(i => i.is_overdue).reduce((s, i) => s + (i.balance || 0), 0);

  return (
    <div className="p-6 space-y-6" data-testid="city-ledger-panel">
      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-stone-900 rounded-2xl p-6 text-white shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-300">
              <Building2 className="w-4 h-4" /> Corporate AR · City Ledger
            </div>
            <h1 className="text-3xl font-black mt-2">B2B Deferred Billing</h1>
            <p className="text-sm text-stone-300 mt-1">Companies and travel agents · 30/60/90-day terms · aged receivables</p>
          </div>
          <button onClick={loadAll} data-testid="ledger-refresh" className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-semibold">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <KPI label="Total Open AR" value={cur(totalOpen)} tint="emerald" />
          <KPI label="Overdue" value={cur(totalOverdue)} tint={totalOverdue > 0 ? "rose" : "stone"} />
          <KPI label="Companies" value={companies.length} tint="sky" />
          <KPI label="Open Invoices" value={invoices.filter(i => i.status !== "paid").length} tint="amber" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-stone-200">
        {[{ id: "companies", label: "Companies", icon: Building2 },
          { id: "invoices", label: "Invoices", icon: Receipt },
          { id: "aging", label: "Aging Report", icon: TrendingDown }].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`ledger-tab-${t.id}`}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-semibold border-b-2 -mb-px
              ${tab === t.id ? "border-amber-500 text-stone-900" : "border-transparent text-stone-400 hover:text-stone-700"}`}>
            <t.icon className="w-3.5 h-3.5" />{t.label}
          </button>
        ))}
      </div>

      {tab === "companies" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setCompanyForm({ ...EMPTY_COMPANY })} data-testid="ledger-new-company"
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" /> New Company
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr><th className="p-3 text-left">Name</th><th className="p-3 text-left">Contact</th><th className="p-3 text-right">Credit Limit</th><th className="p-3 text-right">Terms</th><th className="p-3 text-right">Open AR</th><th className="p-3 text-center">Actions</th></tr>
              </thead>
              <tbody>
                {companies.length === 0 && <tr><td colSpan={6} className="p-8 text-center text-stone-400">No companies yet. Create your first B2B account.</td></tr>}
                {companies.map(c => (
                  <tr key={c.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`ledger-company-${c.id}`}>
                    <td className="p-3 font-semibold text-stone-800">{c.name}{!c.active && <span className="ml-2 text-[10px] text-stone-400">INACTIVE</span>}</td>
                    <td className="p-3 text-xs text-stone-500">
                      {c.contact_name && <div>{c.contact_name}</div>}
                      {c.email && <div className="flex items-center gap-1"><Mail className="w-3 h-3" />{c.email}</div>}
                      {c.phone && <div className="flex items-center gap-1"><Phone className="w-3 h-3" />{c.phone}</div>}
                    </td>
                    <td className="p-3 text-right text-stone-700">{cur(c.credit_limit)}</td>
                    <td className="p-3 text-right text-stone-700">{c.payment_terms_days}d</td>
                    <td className={`p-3 text-right font-bold ${c.open_balance > 0 ? "text-amber-600" : "text-stone-400"}`}>{cur(c.open_balance)}{c.open_invoices > 0 && <span className="ml-1 text-[10px] text-stone-400">({c.open_invoices})</span>}</td>
                    <td className="p-3 text-center">
                      <button onClick={() => setCompanyForm({ ...c })} className="text-xs text-sky-600 hover:underline mr-2">Edit</button>
                      <button onClick={() => setCompanyForm({ ...EMPTY_INVOICE, company_id: c.id }) || setInvoiceForm({ ...EMPTY_INVOICE, company_id: c.id }) || setTab("invoices")} className="text-xs text-emerald-600 hover:underline mr-2">+ Invoice</button>
                      <button onClick={() => deleteCompany(c.id)} className="text-xs text-rose-600 hover:underline">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "invoices" && (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setInvoiceForm({ ...EMPTY_INVOICE })} data-testid="ledger-new-invoice"
              className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-semibold">
              <Plus className="w-4 h-4" /> New Invoice
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr><th className="p-3 text-left">Invoice #</th><th className="p-3 text-left">Company</th><th className="p-3 text-left">Issued</th><th className="p-3 text-left">Due</th><th className="p-3 text-right">Amount</th><th className="p-3 text-right">Balance</th><th className="p-3 text-center">Status</th><th className="p-3 text-center"></th></tr>
              </thead>
              <tbody>
                {invoices.length === 0 && <tr><td colSpan={8} className="p-8 text-center text-stone-400">No invoices yet.</td></tr>}
                {invoices.map(i => (
                  <tr key={i.id} className="border-t border-stone-100 hover:bg-stone-50" data-testid={`ledger-invoice-${i.id}`}>
                    <td className="p-3 font-mono text-xs text-stone-700">{i.invoice_number}</td>
                    <td className="p-3 text-stone-800">{i.company_name}</td>
                    <td className="p-3 text-xs text-stone-500">{i.issue_date}</td>
                    <td className="p-3 text-xs"><span className={i.is_overdue ? "text-rose-600 font-semibold" : "text-stone-500"}>{i.due_date}</span>{i.is_overdue && <span className="block text-[10px] text-rose-500">{i.days_overdue}d overdue</span>}</td>
                    <td className="p-3 text-right text-stone-700">{cur(i.amount)}</td>
                    <td className={`p-3 text-right font-bold ${i.balance > 0 ? (i.is_overdue ? "text-rose-600" : "text-amber-600") : "text-emerald-600"}`}>{cur(i.balance)}</td>
                    <td className="p-3 text-center">
                      <span className={`inline-block px-2 py-0.5 text-[10px] font-bold uppercase rounded-full ${
                        i.status === "paid" ? "bg-emerald-100 text-emerald-700" :
                        i.status === "partial" ? "bg-amber-100 text-amber-700" :
                        i.is_overdue ? "bg-rose-100 text-rose-700" : "bg-stone-100 text-stone-600"}`}>{i.status}</span>
                    </td>
                    <td className="p-3 text-center">
                      {i.status !== "paid" && <button onClick={() => setPayFor(i)} data-testid={`ledger-pay-${i.id}`} className="text-xs text-emerald-600 hover:underline">Record payment</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "aging" && aging && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[{ k: "current", label: "Current", tint: "emerald" },
              { k: "d30", label: "1-30 days", tint: "sky" },
              { k: "d60", label: "31-60 days", tint: "amber" },
              { k: "d90", label: "61-90 days", tint: "orange" },
              { k: "over90", label: "90+ days", tint: "rose" }].map(b => (
              <KPI key={b.k} label={b.label} value={cur(aging.buckets[b.k])} tint={b.tint} />
            ))}
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
                <tr><th className="p-3 text-left">Company</th><th className="p-3 text-right">Current</th><th className="p-3 text-right">1-30d</th><th className="p-3 text-right">31-60d</th><th className="p-3 text-right">61-90d</th><th className="p-3 text-right">90+d</th><th className="p-3 text-right">Total Open</th></tr>
              </thead>
              <tbody>
                {(aging.by_company || []).length === 0 && <tr><td colSpan={7} className="p-8 text-center text-stone-400">No open AR across companies.</td></tr>}
                {(aging.by_company || []).map(r => (
                  <tr key={r.company_id} className="border-t border-stone-100 hover:bg-stone-50">
                    <td className="p-3 font-semibold text-stone-800">{r.company_name}</td>
                    <td className="p-3 text-right">{cur(r.current)}</td>
                    <td className="p-3 text-right">{cur(r.d30)}</td>
                    <td className="p-3 text-right text-amber-700">{cur(r.d60)}</td>
                    <td className="p-3 text-right text-orange-700">{cur(r.d90)}</td>
                    <td className="p-3 text-right text-rose-700 font-bold">{cur(r.over90)}</td>
                    <td className="p-3 text-right font-black text-stone-900">{cur(r.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-stone-400 text-right">As of {aging.as_of}</p>
        </div>
      )}

      {/* Company form modal */}
      {companyForm && (
        <Modal title={companyForm.id ? "Edit Company" : "New Company"} onClose={() => setCompanyForm(null)}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name *"><input value={companyForm.name} onChange={e => setCompanyForm({ ...companyForm, name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="ledger-form-name" /></Field>
            <Field label="Tax ID"><input value={companyForm.tax_id} onChange={e => setCompanyForm({ ...companyForm, tax_id: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Contact Name"><input value={companyForm.contact_name} onChange={e => setCompanyForm({ ...companyForm, contact_name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Email"><input value={companyForm.email} onChange={e => setCompanyForm({ ...companyForm, email: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Phone"><input value={companyForm.phone} onChange={e => setCompanyForm({ ...companyForm, phone: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Address"><input value={companyForm.address} onChange={e => setCompanyForm({ ...companyForm, address: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Credit Limit (£)"><input type="number" value={companyForm.credit_limit} onChange={e => setCompanyForm({ ...companyForm, credit_limit: parseFloat(e.target.value) || 0 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <Field label="Payment Terms (days)"><input type="number" value={companyForm.payment_terms_days} onChange={e => setCompanyForm({ ...companyForm, payment_terms_days: parseInt(e.target.value) || 30 })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
            <div className="col-span-2"><Field label="Notes"><textarea value={companyForm.notes} onChange={e => setCompanyForm({ ...companyForm, notes: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" rows={2} /></Field></div>
            <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={companyForm.active} onChange={e => setCompanyForm({ ...companyForm, active: e.target.checked })} /> Active</label>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setCompanyForm(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={saveCompany} data-testid="ledger-save-company" className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold">Save</button>
          </div>
        </Modal>
      )}

      {/* Invoice form modal */}
      {invoiceForm && (
        <Modal title="New Invoice" onClose={() => setInvoiceForm(null)}>
          <div className="space-y-3">
            <Field label="Company *">
              <select value={invoiceForm.company_id} onChange={e => setInvoiceForm({ ...invoiceForm, company_id: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="ledger-inv-company">
                <option value="">— Select —</option>
                {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Issue Date"><input type="date" value={invoiceForm.issue_date} onChange={e => setInvoiceForm({ ...invoiceForm, issue_date: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
              <Field label="Due Date (auto if empty)"><input type="date" value={invoiceForm.due_date} onChange={e => setInvoiceForm({ ...invoiceForm, due_date: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" /></Field>
              <Field label={(invoiceForm.lines || []).length > 0 ? `Amount (auto from lines)` : "Amount *"}>
                <input type="number" step="0.01" value={invoiceForm.amount}
                  disabled={(invoiceForm.lines || []).length > 0}
                  onChange={e => setInvoiceForm({ ...invoiceForm, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm disabled:bg-stone-50 disabled:text-stone-500"
                  data-testid="ledger-inv-amount" />
              </Field>
              <Field label="Invoice Currency">
                <select value={invoiceForm.currency} onChange={e => setInvoiceForm({ ...invoiceForm, currency: e.target.value })}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="ledger-inv-currency">
                  {availableCurrencies.map(c => <option key={c}>{c}</option>)}
                </select>
              </Field>
            </div>

            {/* Multi-currency line items */}
            <div className="border border-stone-200 rounded-lg p-3 bg-stone-50">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-xs font-bold text-stone-700">Line Items (multi-currency)</div>
                  <div className="text-[10px] text-stone-500">Each line can be in its own currency; totals roll up to the invoice currency using latest FX.</div>
                </div>
                <button type="button"
                  onClick={() => setInvoiceForm({ ...invoiceForm, lines: [...(invoiceForm.lines || []), { ...EMPTY_LINE, currency: invoiceForm.currency }] })}
                  data-testid="ledger-add-line"
                  className="flex items-center gap-1 px-2 py-1 text-xs font-semibold bg-white border border-stone-200 hover:border-stone-400 rounded-md">
                  <Plus className="w-3 h-3" />Add line
                </button>
              </div>
              {(invoiceForm.lines || []).length === 0 ? (
                <p className="text-[11px] text-stone-400 text-center py-2">No line items. Using flat amount above.</p>
              ) : (
                <div className="space-y-2">
                  {(invoiceForm.lines || []).map((li, idx) => (
                    <div key={idx} className="grid grid-cols-12 gap-2 items-center" data-testid={`ledger-line-${idx}`}>
                      <input placeholder="Description" value={li.description}
                        onChange={e => {
                          const lines = [...invoiceForm.lines];
                          lines[idx] = { ...lines[idx], description: e.target.value };
                          setInvoiceForm({ ...invoiceForm, lines });
                        }}
                        className="col-span-5 border border-stone-200 rounded-md px-2 py-1.5 text-xs bg-white" />
                      <input type="number" step="0.01" value={li.quantity} title="Quantity"
                        onChange={e => {
                          const lines = [...invoiceForm.lines];
                          lines[idx] = { ...lines[idx], quantity: parseFloat(e.target.value) || 0 };
                          setInvoiceForm({ ...invoiceForm, lines });
                        }}
                        className="col-span-1 border border-stone-200 rounded-md px-2 py-1.5 text-xs bg-white text-right" />
                      <input type="number" step="0.01" value={li.amount} title="Rate per unit"
                        onChange={e => {
                          const lines = [...invoiceForm.lines];
                          lines[idx] = { ...lines[idx], amount: parseFloat(e.target.value) || 0 };
                          setInvoiceForm({ ...invoiceForm, lines });
                        }}
                        className="col-span-3 border border-stone-200 rounded-md px-2 py-1.5 text-xs bg-white text-right" />
                      <select value={li.currency}
                        onChange={e => {
                          const lines = [...invoiceForm.lines];
                          lines[idx] = { ...lines[idx], currency: e.target.value };
                          setInvoiceForm({ ...invoiceForm, lines });
                        }}
                        className="col-span-2 border border-stone-200 rounded-md px-1 py-1.5 text-xs bg-white">
                        {availableCurrencies.map(c => <option key={c}>{c}</option>)}
                      </select>
                      <button type="button"
                        onClick={() => setInvoiceForm({ ...invoiceForm, lines: invoiceForm.lines.filter((_, i) => i !== idx) })}
                        className="col-span-1 p-1 text-rose-500 hover:bg-rose-50 rounded flex justify-center">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  <div className="text-right text-[11px] text-stone-500 pt-1 border-t border-stone-200 mt-2">
                    Lines will roll up to <b>{invoiceForm.currency}</b> on save using current FX rates.
                  </div>
                </div>
              )}
            </div>
            <Field label="Notes"><textarea value={invoiceForm.notes} onChange={e => setInvoiceForm({ ...invoiceForm, notes: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" rows={2} /></Field>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setInvoiceForm(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={saveInvoice} data-testid="ledger-save-invoice" className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-semibold">Create Invoice</button>
          </div>
        </Modal>
      )}

      {/* Email Invoice modal — YOU write to/subject/message, then click Send */}
      {emailFor && (
        <EmailInvoiceModal
          invoice={emailFor}
          onClose={() => setEmailFor(null)}
          onSend={sendInvoiceEmail}
        />
      )}

      {/* Payment modal */}
      {payFor && (
        <Modal title={`Record Payment · ${payFor.invoice_number}`} onClose={() => setPayFor(null)}>
          <p className="text-sm text-stone-500 mb-3">Outstanding balance: <strong className="text-stone-900">{cur(payFor.balance)}</strong></p>
          <Field label="Amount (£)"><input type="number" step="0.01" defaultValue={payFor.balance} id="pay-amount" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="ledger-pay-amount" /></Field>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <Field label="Method"><select id="pay-method" defaultValue="bank_transfer" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"><option value="bank_transfer">Bank transfer</option><option value="cheque">Cheque</option><option value="card">Card</option><option value="cash">Cash</option></select></Field>
            <Field label="Reference"><input id="pay-ref" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g. BACS-2026-04-19" /></Field>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setPayFor(null)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={() => {
              const amt = document.getElementById("pay-amount").value;
              const method = document.getElementById("pay-method").value;
              const ref = document.getElementById("pay-ref").value;
              recordPayment(amt, method, ref);
            }} data-testid="ledger-pay-submit" className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold">Record</button>
          </div>
        </Modal>
      )}
    </div>
  );
};

const KPI = ({ label, value, tint = "stone" }) => {
  const tints = {
    emerald: "from-emerald-500 to-teal-600", rose: "from-rose-500 to-red-600",
    sky: "from-sky-500 to-blue-600", amber: "from-amber-500 to-orange-600",
    orange: "from-orange-500 to-rose-600", stone: "from-stone-400 to-stone-600",
  };
  return (
    <div className={`rounded-xl p-4 text-white bg-gradient-to-br ${tints[tint]}`}>
      <div className="text-[10px] font-bold uppercase opacity-80">{label}</div>
      <div className="text-2xl font-black mt-1">{value}</div>
    </div>
  );
};

const Field = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</label>
    {children}
  </div>
);

const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-stone-900">{title}</h2>
        <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
      </div>
      {children}
    </div>
  </div>
);

// --- Email Invoice modal: user composes recipient / subject / message manually ---
const EmailInvoiceModal = ({ invoice, onClose, onSend }) => {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState(`Invoice ${invoice.invoice_number}`);
  const [message, setMessage] = useState(
    `Dear ${invoice.company_name || "Accounts team"},\n\nPlease find attached invoice ${invoice.invoice_number} for your review.\n\nAmount due: £${Number(invoice.balance).toFixed(2)}\nDue date: ${invoice.due_date}\n\nKindly arrange settlement within the agreed payment terms.\n\nThank you.`
  );
  const [sending, setSending] = useState(false);

  const submit = async () => {
    if (!to.trim()) return toast.error("Please enter at least one recipient");
    if (!subject.trim() || !message.trim()) return toast.error("Subject and message required");
    setSending(true);
    try {
      // Send message as HTML with newlines → <br>
      await onSend(to, subject, message.replace(/\n/g, "<br>"));
    } finally { setSending(false); }
  };

  return (
    <Modal title={`Email Invoice · ${invoice.invoice_number}`} onClose={onClose}>
      <div className="space-y-3">
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">To *</label>
          <input value={to} onChange={e => setTo(e.target.value)} placeholder="accounts@company.com (comma-separated for multiple)"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="email-inv-to" autoFocus />
          <p className="text-[10px] text-stone-400 mt-1">You write the recipient yourself. Hint: company contact email is <strong>{invoice.company_name}</strong>.</p>
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Subject *</label>
          <input value={subject} onChange={e => setSubject(e.target.value)}
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="email-inv-subject" />
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Message *</label>
          <textarea value={message} onChange={e => setMessage(e.target.value)} rows={8}
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-sans" data-testid="email-inv-message" />
        </div>
        <p className="text-[11px] text-stone-500 bg-stone-50 border border-stone-200 rounded-lg p-2 flex items-center gap-1.5">
          <Receipt className="w-3.5 h-3.5" />Invoice PDF will be attached automatically
        </p>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-4 py-2 text-sm">Cancel</button>
        <button onClick={submit} disabled={sending} data-testid="email-inv-send"
          className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5">
          <Mail className="w-3.5 h-3.5" />{sending ? "Sending…" : "Send"}
        </button>
      </div>
    </Modal>
  );
};

export default CityLedgerPanel;
