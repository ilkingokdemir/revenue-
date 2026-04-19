/**
 * Iter 156 — Top-10 Competitor Gap Features · Compact multi-panel module.
 * Each panel is a self-contained component. They are wired into App.js via the
 * sidebar under existing sections (Finance, Guests, Operations, Settings).
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import {
  Lock, Unlock, Receipt, Wallet, Gift, Sparkles, Users, Wrench, Package, Banknote,
  Shield, CheckCircle, AlertTriangle, Plus, Trash2, RefreshCw, Copy, QrCode,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v, c = "GBP") => `${c === "GBP" ? "£" : c === "USD" ? "$" : c === "EUR" ? "€" : ""}${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/* ═══════════ 1. NIGHT AUDIT CLOSE-DAY ═══════════ */
export const NightAuditClosePanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [{ data: s }, { data: h }] = await Promise.all([
        axios.get(`${API}/night-audit/close-status/${pid}?business_date=${date}`),
        axios.get(`${API}/night-audit/close-history/${pid}?limit=30`),
      ]);
      setStatus(s); setHistory(h);
    } catch { /* silent */ }
  }, [pid, date]);
  useEffect(() => { load(); }, [load]);

  const closeDay = async () => {
    if (!window.confirm(`Close day ${date}? Folios for this date will be locked.`)) return;
    setBusy(true);
    try {
      await axios.post(`${API}/night-audit/close-day/${pid}`, { business_date: date, notes });
      toast.success(`Day ${date} closed`); load(); setNotes("");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  const reopenDay = async (bd) => {
    const reason = prompt("Reason to reopen (audit log):");
    if (!reason) return;
    try {
      await axios.post(`${API}/night-audit/reopen-day/${pid}`, { business_date: bd, reason });
      toast.success("Day reopened"); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const closedRec = status?.close_record;
  return (
    <div data-testid="night-audit-close-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-stone-900 to-stone-800 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Lock className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-70">Night Audit · Close Day</span></div>
        <h2 className="text-2xl font-bold mb-1">Lock business-date books</h2>
        <p className="text-sm opacity-70">Freeze all folio activity for the chosen date. Produces an immutable end-of-day record.</p>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
            data-testid="na-close-date" className="border border-stone-200 rounded-lg px-3 py-2 text-sm" />
          {status?.closed ? (
            <Badge className="bg-rose-100 text-rose-700 flex items-center gap-1"><Lock className="w-3 h-3" />Closed</Badge>
          ) : (
            <Badge className="bg-emerald-100 text-emerald-700 flex items-center gap-1"><Unlock className="w-3 h-3" />Open</Badge>
          )}
        </div>

        {closedRec ? (
          <div className="bg-stone-50 rounded-xl p-4 space-y-2">
            <div className="text-xs text-stone-500">Closed {new Date(closedRec.closed_at).toLocaleString()} by <strong>{closedRec.closed_by}</strong></div>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div><div className="text-[10px] uppercase text-stone-400 font-bold">Charges</div><div className="font-mono font-bold">{cur(closedRec.totals?.charges)}</div></div>
              <div><div className="text-[10px] uppercase text-stone-400 font-bold">Payments</div><div className="font-mono font-bold text-emerald-600">{cur(closedRec.totals?.payments)}</div></div>
              <div><div className="text-[10px] uppercase text-stone-400 font-bold">Net</div><div className="font-mono font-bold">{cur(closedRec.totals?.net)}</div></div>
              <div><div className="text-[10px] uppercase text-stone-400 font-bold">In-house</div><div className="font-bold">{closedRec.counts?.in_house}</div></div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Close-day notes (optional)"
              data-testid="na-close-notes" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm min-h-[60px]" />
            <button onClick={closeDay} disabled={busy}
              data-testid="na-close-btn"
              className="px-5 py-2.5 bg-stone-800 hover:bg-stone-900 text-white rounded-lg text-sm font-bold flex items-center gap-2 disabled:opacity-60">
              <Lock className="w-4 h-4" />{busy ? "Closing…" : `Close ${date}`}
            </button>
          </div>
        )}
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-4">Close-Day History</h3>
        <div className="divide-y divide-stone-100">
          {history.map(r => (
            <div key={r.id} className="py-3 flex items-center justify-between" data-testid={`na-history-${r.business_date}`}>
              <div>
                <div className="font-semibold text-sm flex items-center gap-2">
                  {r.business_date}
                  {r.status === "reopened" && <Badge className="bg-amber-100 text-amber-700 text-[9px]">REOPENED</Badge>}
                </div>
                <div className="text-xs text-stone-400">by {r.closed_by} · {cur(r.totals?.payments)} collected · {r.counts?.in_house} in-house</div>
              </div>
              {r.status === "closed" && <button onClick={() => reopenDay(r.business_date)} className="text-xs text-rose-600 hover:underline" data-testid={`na-reopen-${r.business_date}`}>Reopen</button>}
            </div>
          ))}
          {history.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No closures yet</p>}
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 2. DEPOSIT LIABILITY LEDGER ═══════════ */
export const DepositLedgerPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/deposit-ledger/${pid}`).then(({ data: d }) => setData(d)).catch(() => {});
  }, [pid]);

  if (!data) return <div className="p-8 text-center text-stone-400" data-testid="deposit-ledger-loading">Loading…</div>;
  return (
    <div data-testid="deposit-ledger-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-sky-600 to-indigo-700 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Wallet className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Deposit / Advance-Payment Ledger</span></div>
        <div className="flex items-end justify-between mt-3">
          <div>
            <h2 className="text-3xl font-black">{cur(data.total_liability)}</h2>
            <p className="text-sm opacity-80">Unearned revenue held across {data.count} future bookings as of {data.as_of}</p>
          </div>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-3">By Arrival Month</h3>
        <div className="space-y-2">
          {data.by_month.map(m => (
            <div key={m.month} className="flex items-center gap-3" data-testid={`dep-month-${m.month}`}>
              <div className="w-20 text-sm font-mono font-semibold">{m.month}</div>
              <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
                <div className="h-full bg-gradient-to-r from-sky-500 to-indigo-600" style={{ width: `${Math.min(100, (m.liability / Math.max(data.total_liability, 1)) * 100)}%` }} />
              </div>
              <div className="w-24 text-right font-mono font-bold">{cur(m.liability)}</div>
              <div className="w-16 text-right text-xs text-stone-400">{m.count} bks</div>
            </div>
          ))}
          {data.by_month.length === 0 && <p className="text-center text-sm text-stone-400 py-4">No future deposits</p>}
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold text-stone-800 mb-3">Deposits On File ({data.by_booking.length})</h3>
        <div className="divide-y divide-stone-100 max-h-[500px] overflow-y-auto">
          {data.by_booking.map(b => (
            <div key={b.id} className="py-2.5 flex items-center justify-between text-sm" data-testid={`dep-booking-${b.id}`}>
              <div className="flex-1 min-w-0">
                <div className="font-semibold truncate">{b.guest_name} <span className="text-[10px] font-mono text-stone-400">#{String(b.booking_ref).slice(-5)}</span></div>
                <div className="text-xs text-stone-400">{b.check_in} → {b.check_out} · {b.source}</div>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold text-sky-700">{cur(b.liability)}</div>
                <div className="text-[10px] text-stone-400">of {cur(b.total_price)}</div>
              </div>
            </div>
          ))}
          {data.by_booking.length === 0 && <p className="text-center text-sm text-stone-400 py-4">No deposits held</p>}
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 3. COMMISSION RECONCILIATION ═══════════ */
export const CommissionReconPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [rows, setRows] = useState([]);
  const [showUpload, setShowUpload] = useState(false);
  const [channel, setChannel] = useState("Booking.com");
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [csv, setCsv] = useState("");
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/commission-recon/statements/${pid}`); setRows(data); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const upload = async () => {
    // CSV: booking_ref,gross,commission
    const lines = csv.trim().split(/\r?\n/).filter(Boolean).filter(l => !l.toLowerCase().startsWith("booking_ref"))
      .map(l => { const [ref, gross, comm] = l.split(","); return { booking_ref: ref?.trim(), gross: parseFloat(gross), commission: parseFloat(comm) }; });
    if (!lines.length) return toast.error("Add at least one row (booking_ref,gross,commission)");
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/commission-recon/upload/${pid}`, { channel, period, lines });
      toast.success(`Statement reconciled: ${data.summary.matched} matched, ${data.summary.variance} variance, ${data.summary.unmatched} unmatched`);
      setShowUpload(false); setCsv(""); load(); setActive(data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this statement?")) return;
    try { await axios.delete(`${API}/commission-recon/statements/${id}`); load(); } catch { /* */ }
  };

  return (
    <div data-testid="commission-recon-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-fuchsia-600 to-pink-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Receipt className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Commission Reconciliation</span></div>
          <h2 className="text-2xl font-bold">Match OTA invoices to your ledger</h2>
          <p className="text-sm opacity-80 mt-1">Upload Booking.com, Expedia, Airbnb statements → auto-match to folio records.</p>
        </div>
        <button onClick={() => setShowUpload(true)} data-testid="cr-upload-btn"
          className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" />Upload Statement</button>
      </div>

      {showUpload && (
        <div className="bg-white border-2 border-fuchsia-300 rounded-2xl p-6" data-testid="cr-upload-form">
          <h3 className="font-bold mb-3">Upload OTA Statement</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-[10px] font-bold uppercase text-stone-500">Channel</label>
              <select value={channel} onChange={e => setChannel(e.target.value)} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="cr-channel">
                <option>Booking.com</option><option>Expedia</option><option>Airbnb</option><option>Agoda</option><option>Hotels.com</option><option>Trip.com</option><option>Vrbo</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase text-stone-500">Period (YYYY-MM)</label>
              <input value={period} onChange={e => setPeriod(e.target.value)} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono" data-testid="cr-period" />
            </div>
          </div>
          <label className="text-[10px] font-bold uppercase text-stone-500">CSV Lines (booking_ref,gross,commission)</label>
          <textarea value={csv} onChange={e => setCsv(e.target.value)} rows={8} data-testid="cr-csv"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-xs font-mono" placeholder="BKG-1234,150.00,22.50&#10;BKG-5678,280.00,42.00" />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowUpload(false)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={upload} disabled={busy} data-testid="cr-submit" className="px-4 py-2 bg-fuchsia-600 text-white rounded-lg text-sm font-bold">{busy ? "Reconciling…" : "Reconcile"}</button>
          </div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="font-bold mb-3">Past Statements</h3>
        <div className="divide-y divide-stone-100">
          {rows.map(s => (
            <div key={s.id} className="py-3" data-testid={`cr-stmt-${s.id}`}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-sm flex items-center gap-2">{s.channel} <Badge className="bg-stone-100 text-stone-700 text-[10px]">{s.period}</Badge></div>
                  <div className="text-xs text-stone-400">Gross {cur(s.summary?.statement_gross)} · Comm {cur(s.summary?.statement_commission)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">✓ {s.summary?.matched}</Badge>
                  <Badge className="bg-amber-100 text-amber-700 text-[10px]">Δ {s.summary?.variance}</Badge>
                  <Badge className="bg-rose-100 text-rose-700 text-[10px]">? {s.summary?.unmatched}</Badge>
                  <button onClick={() => setActive(s)} className="text-xs text-fuchsia-600 hover:underline" data-testid={`cr-view-${s.id}`}>View</button>
                  <button onClick={() => del(s.id)} className="text-rose-600" data-testid={`cr-del-${s.id}`}><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            </div>
          ))}
          {rows.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No statements uploaded yet</p>}
        </div>
      </div>

      {active && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setActive(null)} data-testid="cr-detail-modal">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="bg-fuchsia-600 text-white p-4 flex justify-between items-center">
              <div><div className="font-bold">{active.channel} · {active.period}</div><div className="text-xs opacity-80">{active.lines?.length} lines</div></div>
              <button onClick={() => setActive(null)} className="text-white">✕</button>
            </div>
            <div className="overflow-y-auto flex-1 p-4">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 sticky top-0"><tr className="text-left"><th className="p-2">Ref</th><th className="p-2">Guest</th><th className="p-2 text-right">Stmt Gross</th><th className="p-2 text-right">Our Gross</th><th className="p-2 text-right">Variance</th><th className="p-2">Status</th></tr></thead>
                <tbody>
                  {active.lines?.map((l, i) => (
                    <tr key={i} className="border-b border-stone-100">
                      <td className="p-2 font-mono">{l.booking_ref}</td>
                      <td className="p-2">{l.guest_name || "—"}</td>
                      <td className="p-2 text-right font-mono">{cur(l.statement_gross)}</td>
                      <td className="p-2 text-right font-mono">{cur(l.our_gross)}</td>
                      <td className={`p-2 text-right font-mono ${Math.abs(l.variance) > 0.01 ? "text-amber-600 font-bold" : "text-stone-400"}`}>{cur(l.variance)}</td>
                      <td className="p-2"><Badge className={l.status === "match" ? "bg-emerald-100 text-emerald-700" : l.status === "variance" ? "bg-amber-100 text-amber-700" : "bg-rose-100 text-rose-700"}>{l.status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ═══════════ 4. GIFT CARDS ═══════════ */
export const GiftCardsPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [cards, setCards] = useState([]);
  const [summary, setSummary] = useState({});
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ amount: 50, recipient_name: "", recipient_email: "", purchaser_name: "", message: "", expires_days: 365 });

  const load = useCallback(async () => {
    try {
      const [{ data: c }, { data: s }] = await Promise.all([
        axios.get(`${API}/gift-cards${pid ? `?property_id=${pid}` : ""}`),
        axios.get(`${API}/gift-cards/summary/${pid}`),
      ]);
      setCards(c); setSummary(s);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const issue = async () => {
    if (!form.amount || form.amount <= 0) return toast.error("Amount required");
    try {
      const { data } = await axios.post(`${API}/gift-cards`, { ...form, property_id: pid });
      toast.success(`Gift card issued: ${data.code}`);
      setShowNew(false); setForm({ amount: 50, recipient_name: "", recipient_email: "", purchaser_name: "", message: "", expires_days: 365 }); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const cancel = async (id) => {
    const reason = prompt("Cancel reason?"); if (!reason) return;
    try { await axios.post(`${API}/gift-cards/${id}/cancel`, { reason }); load(); } catch { /* */ }
  };

  return (
    <div data-testid="gift-cards-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-rose-600 to-red-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Gift className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Gift Cards & Vouchers</span></div>
          <h2 className="text-2xl font-bold">Hotel-branded prepaid vouchers</h2>
        </div>
        <button onClick={() => setShowNew(true)} data-testid="gc-new-btn"
          className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" />Issue Card</button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white border rounded-2xl p-4" data-testid="gc-sold"><div className="text-[10px] font-bold text-stone-400 uppercase">Total Sold</div><div className="text-2xl font-bold text-emerald-600">{cur(summary.total_sold)}</div><div className="text-xs text-stone-400">{summary.count} cards</div></div>
        <div className="bg-white border rounded-2xl p-4" data-testid="gc-outstanding"><div className="text-[10px] font-bold text-stone-400 uppercase">Outstanding Liability</div><div className="text-2xl font-bold text-amber-600">{cur(summary.total_outstanding)}</div><div className="text-xs text-stone-400">{summary.counts?.active || 0} active</div></div>
        <div className="bg-white border rounded-2xl p-4" data-testid="gc-redeemed"><div className="text-[10px] font-bold text-stone-400 uppercase">Redeemed</div><div className="text-2xl font-bold text-stone-700">{cur(summary.total_redeemed)}</div><div className="text-xs text-stone-400">{summary.counts?.redeemed || 0} fully used</div></div>
      </div>

      {showNew && (
        <div className="bg-white border-2 border-rose-300 rounded-2xl p-6" data-testid="gc-form">
          <h3 className="font-bold mb-3">Issue Gift Card</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Amount (£)</label><input type="number" value={form.amount} onChange={e => setForm({ ...form, amount: parseFloat(e.target.value) })} className="w-full border rounded px-3 py-2 text-sm" data-testid="gc-amount" /></div>
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Expires in (days)</label><input type="number" value={form.expires_days} onChange={e => setForm({ ...form, expires_days: parseInt(e.target.value) })} className="w-full border rounded px-3 py-2 text-sm" data-testid="gc-expires" /></div>
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Recipient Name</label><input value={form.recipient_name} onChange={e => setForm({ ...form, recipient_name: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" data-testid="gc-recipient" /></div>
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Recipient Email</label><input value={form.recipient_email} onChange={e => setForm({ ...form, recipient_email: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" /></div>
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Purchaser</label><input value={form.purchaser_name} onChange={e => setForm({ ...form, purchaser_name: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" /></div>
          </div>
          <textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} placeholder="Gift message" className="w-full border rounded px-3 py-2 text-sm mb-3" />
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={issue} className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-bold" data-testid="gc-issue">Issue & Generate Code</button>
          </div>
        </div>
      )}

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Cards ({cards.length})</h3>
        <div className="space-y-2">
          {cards.map(c => (
            <div key={c.id} className="flex items-center gap-3 p-3 bg-stone-50 rounded-xl" data-testid={`gc-${c.id}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${c.status === "active" ? "bg-emerald-100 text-emerald-700" : c.status === "redeemed" ? "bg-stone-200 text-stone-500" : "bg-rose-100 text-rose-700"}`}><Gift className="w-5 h-5" /></div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2"><code className="text-xs font-mono font-bold">{c.code}</code><button onClick={() => { navigator.clipboard.writeText(c.code); toast.success("Code copied"); }} className="text-stone-400 hover:text-stone-600"><Copy className="w-3 h-3" /></button></div>
                <div className="text-xs text-stone-400">{c.recipient_name || "—"} · expires {c.expires_at?.slice(0, 10)}</div>
              </div>
              <div className="text-right">
                <div className="font-mono font-bold">{cur(c.balance, c.currency)}</div>
                <div className="text-[10px] text-stone-400">of {cur(c.initial_amount, c.currency)}</div>
              </div>
              <Badge className={c.status === "active" ? "bg-emerald-100 text-emerald-700" : c.status === "redeemed" ? "bg-stone-100 text-stone-600" : "bg-rose-100 text-rose-700"}>{c.status}</Badge>
              {c.status === "active" && <button onClick={() => cancel(c.id)} className="text-rose-600 text-xs" data-testid={`gc-cancel-${c.id}`}>Cancel</button>}
            </div>
          ))}
          {cards.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No cards issued yet</p>}
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 5. REVIEW SENTIMENT AI ═══════════ */
export const ReviewSentimentPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/reviews/sentiment/summary/${pid}`); setData(data); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const analyze = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/reviews/sentiment/analyze`, { property_id: pid, limit: 50 });
      toast.success(`Analyzed ${data.analyzed} new reviews (${data.already_done} already done)`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const sd = data?.sentiment_distribution || {};
  const total = (sd.positive || 0) + (sd.neutral || 0) + (sd.negative || 0);
  return (
    <div data-testid="sentiment-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-violet-600 to-purple-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Sparkles className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Review Sentiment · Claude Sonnet 4.5</span></div>
          <h2 className="text-2xl font-bold">AI theme extraction</h2>
          <p className="text-sm opacity-80 mt-1">Auto-tags each review with sentiment and themes (dirty_bathroom, friendly_staff, …)</p>
        </div>
        <button onClick={analyze} disabled={busy} data-testid="sent-analyze-btn"
          className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2 disabled:opacity-60"><Sparkles className="w-4 h-4" />{busy ? "Analyzing…" : "Analyze New"}</button>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-white border rounded-2xl p-4" data-testid="sent-total"><div className="text-[10px] font-bold text-stone-400 uppercase">Analyzed</div><div className="text-2xl font-bold">{data.total_analyzed}/{data.total_reviews}</div></div>
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4"><div className="text-[10px] font-bold text-emerald-700 uppercase">Positive</div><div className="text-2xl font-bold text-emerald-700">{sd.positive || 0}</div><div className="text-[10px] text-emerald-500">{total ? Math.round((sd.positive / total) * 100) : 0}%</div></div>
            <div className="bg-stone-50 border border-stone-200 rounded-2xl p-4"><div className="text-[10px] font-bold text-stone-600 uppercase">Neutral</div><div className="text-2xl font-bold text-stone-600">{sd.neutral || 0}</div></div>
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4"><div className="text-[10px] font-bold text-rose-700 uppercase">Negative</div><div className="text-2xl font-bold text-rose-700">{sd.negative || 0}</div></div>
          </div>

          <div className="bg-white border rounded-2xl p-6">
            <h3 className="font-bold mb-3">Top Themes</h3>
            <div className="space-y-2">
              {data.theme_counts.map(t => (
                <div key={t.theme} className="flex items-center gap-3" data-testid={`sent-theme-${t.theme}`}>
                  <Badge className={t.polarity === "positive" ? "bg-emerald-100 text-emerald-700" : t.polarity === "negative" ? "bg-rose-100 text-rose-700" : "bg-stone-100 text-stone-600"}>{t.label}</Badge>
                  <div className="flex-1 bg-stone-100 rounded-full h-2 overflow-hidden">
                    <div className={`h-full ${t.polarity === "positive" ? "bg-emerald-500" : t.polarity === "negative" ? "bg-rose-500" : "bg-stone-500"}`} style={{ width: `${Math.min(100, (t.count / Math.max(...data.theme_counts.map(x => x.count))) * 100)}%` }} />
                  </div>
                  <div className="w-12 text-right font-bold">{t.count}</div>
                </div>
              ))}
              {data.theme_counts.length === 0 && <p className="text-center text-sm text-stone-400 py-4">No themes yet — click Analyze New</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

/* ═══════════ 6. GUEST RFM SEGMENTATION ═══════════ */
export const GuestRfmPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/guests/rfm/${pid}`).then(({ data }) => setData(data)).catch(() => {});
  }, [pid]);

  if (!data) return <div className="p-8 text-center text-stone-400" data-testid="rfm-loading">Loading…</div>;
  return (
    <div data-testid="rfm-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-emerald-600 to-teal-700 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Users className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Guest RFM Segmentation</span></div>
        <h2 className="text-2xl font-bold">{data.summary.total.toLocaleString()} guests · {cur(data.summary.total_revenue)}</h2>
        <p className="text-sm opacity-80 mt-1">Recency × Frequency × Monetary scoring · avg {data.summary.avg_stays} stays per guest</p>
      </div>

      <div className="grid grid-cols-5 gap-3">
        {data.segments.map(s => (
          <div key={s.name} className={`${s.color} text-white rounded-2xl p-4`} data-testid={`rfm-seg-${s.name.toLowerCase().replace(/ /g, '-')}`}>
            <div className="text-[10px] font-bold uppercase opacity-80">{s.name}</div>
            <div className="text-3xl font-black mt-1">{s.count}</div>
            <div className="text-xs opacity-80">{cur(s.revenue)}</div>
            <div className="text-[9px] opacity-60">score {s.range}</div>
          </div>
        ))}
      </div>

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Top Guests (by composite score)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-stone-50"><tr className="text-left"><th className="p-2">Guest</th><th className="p-2">Segment</th><th className="p-2 text-right">Recency</th><th className="p-2 text-right">Stays</th><th className="p-2 text-right">Spent</th><th className="p-2 text-center">R/F/M</th><th className="p-2 text-center">Score</th></tr></thead>
            <tbody>
              {data.guests.slice(0, 100).map(g => (
                <tr key={g.key || g.guest_email} className="border-b border-stone-100" data-testid={`rfm-guest-${g.guest_email || g.guest_name}`}>
                  <td className="p-2 font-medium">{g.guest_name || g.guest_email}</td>
                  <td className="p-2"><Badge className="text-[10px]">{g.segment}</Badge></td>
                  <td className="p-2 text-right">{g.recency_days}d ago</td>
                  <td className="p-2 text-right">{g.frequency}</td>
                  <td className="p-2 text-right font-mono">{cur(g.monetary)}</td>
                  <td className="p-2 text-center font-mono">{g.r_score}/{g.f_score}/{g.m_score}</td>
                  <td className="p-2 text-center font-bold">{g.composite}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 7. PREVENTIVE MAINTENANCE ═══════════ */
export const PreventiveMaintenancePanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [data, setData] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", category: "hvac", location: "", instructions: "", frequency: "monthly", first_due: new Date().toISOString().slice(0, 10), assigned_to: "" });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/preventive-maintenance/${pid}`); setData(data); }
    catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name) return toast.error("Name required");
    try { await axios.post(`${API}/preventive-maintenance`, { ...form, property_id: pid }); setShowNew(false); load(); toast.success("Plan created"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const complete = async (id) => {
    const notes = prompt("Completion notes (optional):") || "";
    try { await axios.post(`${API}/preventive-maintenance/${id}/complete`, { notes }); load(); toast.success("Marked complete"); }
    catch { toast.error("Failed"); }
  };

  if (!data) return <div className="p-8 text-center" data-testid="pm-loading">Loading…</div>;
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div data-testid="preventive-maintenance-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-amber-600 to-orange-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Wrench className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Preventive Maintenance</span></div>
          <h2 className="text-2xl font-bold">{data.total} recurring plans</h2>
          <p className="text-sm opacity-80">{data.overdue_count} overdue · {data.due_soon_count} due this week</p>
        </div>
        <button onClick={() => setShowNew(true)} data-testid="pm-new-btn" className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" />New Plan</button>
      </div>

      {showNew && (
        <div className="bg-white border-2 border-amber-300 rounded-2xl p-6" data-testid="pm-form">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="Task name (e.g. Replace smoke alarm batteries)" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="pm-name" />
            <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="pm-category">
              <option value="hvac">HVAC</option><option value="plumbing">Plumbing</option><option value="electrical">Electrical</option><option value="fire_safety">Fire Safety</option><option value="general">General</option>
            </select>
            <input placeholder="Location" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <select value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="pm-frequency">
              <option>daily</option><option>weekly</option><option>biweekly</option><option>monthly</option><option>quarterly</option><option>semiannual</option><option>annual</option>
            </select>
            <input type="date" value={form.first_due} onChange={e => setForm({ ...form, first_due: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Assigned to" value={form.assigned_to} onChange={e => setForm({ ...form, assigned_to: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          </div>
          <textarea placeholder="Instructions" value={form.instructions} onChange={e => setForm({ ...form, instructions: e.target.value })} className="w-full border rounded px-3 py-2 text-sm mt-3" />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={create} data-testid="pm-create" className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-bold">Create Plan</button>
          </div>
        </div>
      )}

      <div className="bg-white border rounded-2xl p-6">
        <div className="divide-y divide-stone-100">
          {data.plans.map(p => {
            const overdue = p.next_due < today && p.active;
            return (
              <div key={p.id} className={`py-3 flex items-center gap-3 ${overdue ? "bg-rose-50 -mx-6 px-6" : ""}`} data-testid={`pm-plan-${p.id}`}>
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${overdue ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}><Wrench className="w-5 h-5" /></div>
                <div className="flex-1">
                  <div className="font-semibold text-sm flex items-center gap-2">{p.name} {overdue && <Badge className="bg-rose-500 text-white text-[9px]">OVERDUE</Badge>}</div>
                  <div className="text-xs text-stone-400">{p.category} · {p.location} · every {p.frequency}</div>
                </div>
                <div className="text-right text-sm">
                  <div className="font-mono font-bold">{p.next_due}</div>
                  <div className="text-[10px] text-stone-400">assigned: {p.assigned_to || "—"}</div>
                </div>
                <button onClick={() => complete(p.id)} data-testid={`pm-complete-${p.id}`} className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-bold">Complete</button>
              </div>
            );
          })}
          {data.plans.length === 0 && <p className="text-center text-sm text-stone-400 py-6">No plans yet</p>}
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 8. ASSET REGISTER ═══════════ */
export const AssetRegisterPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({});
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", category: "appliance", location: "", serial_number: "", supplier: "", purchase_date: new Date().toISOString().slice(0, 10), purchase_price: 0, useful_life_years: 5, warranty_expires: "" });

  const load = useCallback(async () => {
    try {
      const [{ data: a }, { data: s }] = await Promise.all([
        axios.get(`${API}/assets/${pid}`),
        axios.get(`${API}/assets/summary/${pid}`),
      ]);
      setRows(a); setSummary(s);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name) return toast.error("Name required");
    try { await axios.post(`${API}/assets`, { ...form, property_id: pid }); setShowNew(false); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div data-testid="asset-register-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-indigo-600 to-purple-700 text-white rounded-2xl p-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1"><Package className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Asset Register</span></div>
          <h2 className="text-2xl font-bold">{summary.count || 0} assets · {cur(summary.total_book_value)} book value</h2>
          <p className="text-sm opacity-80">Purchased {cur(summary.total_purchase_value)} · depreciated {cur(summary.total_depreciation)}</p>
        </div>
        <button onClick={() => setShowNew(true)} data-testid="ar-new-btn" className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-bold flex items-center gap-2"><Plus className="w-4 h-4" />Add Asset</button>
      </div>

      {summary.warranty_expiring_soon > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /><strong>{summary.warranty_expiring_soon}</strong> warranties expiring in next 60 days</div>
      )}

      {showNew && (
        <div className="bg-white border-2 border-indigo-300 rounded-2xl p-6" data-testid="ar-form">
          <div className="grid grid-cols-3 gap-3">
            <input placeholder="Asset name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="ar-name" />
            <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="ar-category">
              <option value="tv">TV</option><option value="appliance">Appliance</option><option value="hvac">HVAC</option><option value="mattress">Mattress</option><option value="furniture">Furniture</option><option value="it">IT Equipment</option><option value="other">Other</option>
            </select>
            <input placeholder="Location (room/area)" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Serial #" value={form.serial_number} onChange={e => setForm({ ...form, serial_number: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input placeholder="Supplier" value={form.supplier} onChange={e => setForm({ ...form, supplier: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input type="date" value={form.purchase_date} onChange={e => setForm({ ...form, purchase_date: e.target.value })} className="border rounded px-3 py-2 text-sm" />
            <input type="number" placeholder="Purchase £" value={form.purchase_price} onChange={e => setForm({ ...form, purchase_price: parseFloat(e.target.value) })} className="border rounded px-3 py-2 text-sm" data-testid="ar-price" />
            <input type="number" placeholder="Life (yrs)" value={form.useful_life_years} onChange={e => setForm({ ...form, useful_life_years: parseFloat(e.target.value) })} className="border rounded px-3 py-2 text-sm" />
            <input type="date" placeholder="Warranty expires" value={form.warranty_expires} onChange={e => setForm({ ...form, warranty_expires: e.target.value })} className="border rounded px-3 py-2 text-sm" />
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm">Cancel</button>
            <button onClick={create} data-testid="ar-create" className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold">Add Asset</button>
          </div>
        </div>
      )}

      <div className="bg-white border rounded-2xl p-6">
        <table className="w-full text-xs">
          <thead className="bg-stone-50"><tr className="text-left"><th className="p-2">Name</th><th className="p-2">Category</th><th className="p-2">Location</th><th className="p-2 text-right">Purchased</th><th className="p-2 text-right">Age</th><th className="p-2 text-right">Book Value</th><th className="p-2">Warranty</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-stone-100" data-testid={`ar-row-${r.id}`}>
                <td className="p-2 font-medium">{r.name}<div className="text-[10px] text-stone-400">{r.serial_number}</div></td>
                <td className="p-2"><Badge className="text-[10px]">{r.category}</Badge></td>
                <td className="p-2">{r.location}</td>
                <td className="p-2 text-right font-mono">{cur(r.purchase_price, r.currency)}</td>
                <td className="p-2 text-right">{r.age_years}yr<div className="text-[10px] text-stone-400">{r.depreciation_pct}%</div></td>
                <td className="p-2 text-right font-mono font-bold">{cur(r.depreciated_value, r.currency)}</td>
                <td className="p-2">{r.warranty_expires ? (r.warranty_active ? <Badge className="bg-emerald-100 text-emerald-700 text-[9px]">✓ {r.warranty_expires}</Badge> : <Badge className="bg-rose-100 text-rose-700 text-[9px]">✗ expired</Badge>) : "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-stone-400">No assets registered</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ═══════════ 9. CASH DRAWER ═══════════ */
export const CashDrawerPanel = ({ activePropertyId }) => {
  const pid = activePropertyId || "aldgate-flats";
  const [active, setActive] = useState(null);
  const [history, setHistory] = useState([]);
  const [openForm, setOpenForm] = useState({ opening_float: 100, notes: "" });
  const [tx, setTx] = useState({ direction: "in", amount: 0, description: "", booking_ref: "" });
  const [close, setClose] = useState({ counted_cash: 0, notes: "" });

  const load = useCallback(async () => {
    try {
      const [{ data: a }, { data: h }] = await Promise.all([
        axios.get(`${API}/cash-drawer/active/${pid}`),
        axios.get(`${API}/cash-drawer/sessions/${pid}?limit=20`),
      ]);
      setActive(a.session); setHistory(h);
    } catch { /* */ }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const openDrawer = async () => {
    try { await axios.post(`${API}/cash-drawer/open/${pid}`, openForm); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const addTx = async () => {
    if (!tx.amount || tx.amount <= 0) return toast.error("Amount required");
    try { await axios.post(`${API}/cash-drawer/sessions/${active.id}/transaction`, tx); setTx({ direction: "in", amount: 0, description: "", booking_ref: "" }); load(); }
    catch { toast.error("Failed"); }
  };
  const closeDrawer = async () => {
    if (!window.confirm(`Close drawer? Counted: ${cur(close.counted_cash)}`)) return;
    try { await axios.post(`${API}/cash-drawer/sessions/${active.id}/close`, close); setClose({ counted_cash: 0, notes: "" }); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const txs = active?.transactions || [];
  const cashIn = txs.filter(t => t.direction === "in").reduce((s, t) => s + t.amount, 0);
  const cashOut = txs.filter(t => t.direction === "out").reduce((s, t) => s + t.amount, 0);
  const expected = (active?.opening_float || 0) + cashIn - cashOut;

  return (
    <div data-testid="cash-drawer-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-emerald-600 to-green-700 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Banknote className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Cash Drawer · Reception Float</span></div>
        <h2 className="text-2xl font-bold">{active ? "Drawer Open" : "Drawer Closed"}</h2>
      </div>

      {active ? (
        <>
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-white border rounded-2xl p-4"><div className="text-[10px] font-bold text-stone-400 uppercase">Opening Float</div><div className="text-xl font-bold">{cur(active.opening_float)}</div></div>
            <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4"><div className="text-[10px] font-bold text-emerald-700 uppercase">Cash In</div><div className="text-xl font-bold text-emerald-700">+{cur(cashIn)}</div></div>
            <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4"><div className="text-[10px] font-bold text-rose-700 uppercase">Cash Out</div><div className="text-xl font-bold text-rose-700">−{cur(cashOut)}</div></div>
            <div className="bg-stone-900 text-white rounded-2xl p-4"><div className="text-[10px] font-bold uppercase opacity-70">Expected in Drawer</div><div className="text-xl font-bold">{cur(expected)}</div></div>
          </div>

          <div className="bg-white border rounded-2xl p-6">
            <h3 className="font-bold mb-3">Add Transaction</h3>
            <div className="grid grid-cols-4 gap-2">
              <select value={tx.direction} onChange={e => setTx({ ...tx, direction: e.target.value })} className="border rounded px-3 py-2 text-sm" data-testid="cd-direction"><option value="in">Cash In</option><option value="out">Cash Out</option></select>
              <input type="number" placeholder="£" value={tx.amount || ""} onChange={e => setTx({ ...tx, amount: parseFloat(e.target.value) })} className="border rounded px-3 py-2 text-sm" data-testid="cd-amount" />
              <input placeholder="Description" value={tx.description} onChange={e => setTx({ ...tx, description: e.target.value })} className="border rounded px-3 py-2 text-sm" />
              <button onClick={addTx} className="px-4 py-2 bg-stone-800 text-white rounded-lg text-sm font-bold" data-testid="cd-add-tx">Log</button>
            </div>
          </div>

          <div className="bg-white border rounded-2xl p-6">
            <h3 className="font-bold mb-3">Transactions ({txs.length})</h3>
            <div className="divide-y divide-stone-100 max-h-[300px] overflow-y-auto">
              {txs.map(t => (
                <div key={t.id} className="py-2 flex items-center gap-3 text-sm">
                  <Badge className={t.direction === "in" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}>{t.direction === "in" ? "IN" : "OUT"}</Badge>
                  <span className="flex-1">{t.description}</span>
                  <span className="text-[10px] text-stone-400">{new Date(t.at).toLocaleTimeString()}</span>
                  <span className={`font-mono font-bold ${t.direction === "in" ? "text-emerald-600" : "text-rose-600"}`}>{t.direction === "in" ? "+" : "−"}{cur(t.amount)}</span>
                </div>
              ))}
              {txs.length === 0 && <p className="text-center text-sm text-stone-400 py-4">No transactions yet</p>}
            </div>
          </div>

          <div className="bg-white border-2 border-stone-300 rounded-2xl p-6">
            <h3 className="font-bold mb-3">Close Drawer</h3>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-[10px] font-bold uppercase text-stone-500">Counted Cash (£)</label><input type="number" value={close.counted_cash || ""} onChange={e => setClose({ ...close, counted_cash: parseFloat(e.target.value) })} className="w-full border rounded px-3 py-2 text-sm font-mono font-bold" data-testid="cd-counted" /></div>
              <div><label className="text-[10px] font-bold uppercase text-stone-500">Notes</label><input value={close.notes} onChange={e => setClose({ ...close, notes: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" /></div>
            </div>
            <div className="text-sm text-stone-500 mt-2">Variance: <strong className={Math.abs(close.counted_cash - expected) > 0.01 ? "text-amber-600" : "text-emerald-600"}>{cur(close.counted_cash - expected)}</strong></div>
            <button onClick={closeDrawer} data-testid="cd-close-btn" className="mt-3 px-5 py-2.5 bg-stone-800 text-white rounded-lg text-sm font-bold">Close Drawer</button>
          </div>
        </>
      ) : (
        <div className="bg-white border-2 border-emerald-300 rounded-2xl p-6" data-testid="cd-open-form">
          <h3 className="font-bold mb-3">Open New Drawer Session</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Opening Float (£)</label><input type="number" value={openForm.opening_float} onChange={e => setOpenForm({ ...openForm, opening_float: parseFloat(e.target.value) })} className="w-full border rounded px-3 py-2 text-sm font-mono font-bold" data-testid="cd-opening-float" /></div>
            <div><label className="text-[10px] font-bold uppercase text-stone-500">Notes</label><input value={openForm.notes} onChange={e => setOpenForm({ ...openForm, notes: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" /></div>
          </div>
          <button onClick={openDrawer} data-testid="cd-open-btn" className="px-5 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-bold">Open Drawer</button>
        </div>
      )}

      <div className="bg-white border rounded-2xl p-6">
        <h3 className="font-bold mb-3">Past Sessions</h3>
        <div className="divide-y divide-stone-100">
          {history.map(h => (
            <div key={h.id} className="py-2 flex items-center gap-3 text-sm" data-testid={`cd-past-${h.id}`}>
              <div className="flex-1">
                <div className="font-semibold">{new Date(h.opened_at).toLocaleString()} - {h.opened_by}</div>
                <div className="text-xs text-stone-400">{h.status} · float {cur(h.opening_float)} · counted {cur(h.counted_cash || 0)}</div>
              </div>
              {h.variance_flagged && <Badge className="bg-amber-100 text-amber-700">Variance {cur(h.variance)}</Badge>}
            </div>
          ))}
          {history.length === 0 && <p className="text-center text-sm text-stone-400 py-4">No history</p>}
        </div>
      </div>
    </div>
  );
};

/* ═══════════ 10. 2FA TOTP ═══════════ */
export const TwoFactorAuthPanel = () => {
  const [status, setStatus] = useState(null);
  const [enroll, setEnroll] = useState(null);
  const [code, setCode] = useState("");
  const [backup, setBackup] = useState(null);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/2fa/status`); setStatus(data); }
    catch { /* */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  const doEnroll = async () => {
    try { const { data } = await axios.post(`${API}/2fa/enroll`); setEnroll(data); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const doVerify = async () => {
    if (code.length !== 6) return toast.error("Enter 6-digit code");
    try {
      const { data } = await axios.post(`${API}/2fa/verify`, { code });
      if (data.backup_codes) setBackup(data.backup_codes);
      toast.success("2FA enabled ✓");
      setCode(""); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Invalid"); }
  };
  const disable = async () => {
    if (code.length !== 6) return toast.error("Enter 6-digit code to confirm");
    try { await axios.post(`${API}/2fa/disable`, { code }); toast.success("2FA disabled"); setCode(""); setEnroll(null); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const otpauth = enroll?.otpauth_url || "";
  const qrSrc = otpauth ? `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(otpauth)}` : "";

  return (
    <div data-testid="two-factor-panel" className="space-y-4">
      <div className="bg-gradient-to-br from-stone-900 to-indigo-900 text-white rounded-2xl p-6">
        <div className="flex items-center gap-2 mb-1"><Shield className="w-4 h-4" /><span className="text-[11px] font-bold uppercase tracking-wider opacity-80">Two-Factor Authentication</span></div>
        <h2 className="text-2xl font-bold">{status?.enabled ? "2FA is active ✓" : "Protect your account"}</h2>
        <p className="text-sm opacity-70">{status?.enabled ? "Future logins will require a 6-digit code from your authenticator app." : "Enroll with Google Authenticator, 1Password, or Authy."}</p>
      </div>

      {!status?.enabled && !enroll && (
        <div className="bg-white border rounded-2xl p-6 text-center">
          <p className="text-stone-600 mb-4">Enable 2FA to add an extra layer of security to your admin account.</p>
          <button onClick={doEnroll} data-testid="tf-enroll" className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 mx-auto"><QrCode className="w-4 h-4" />Enroll now</button>
        </div>
      )}

      {enroll && !status?.enabled && (
        <div className="bg-white border-2 border-indigo-300 rounded-2xl p-6" data-testid="tf-enroll-step">
          <h3 className="font-bold mb-3">Step 1 · Scan QR</h3>
          <div className="flex gap-6 items-start">
            <img src={qrSrc} alt="QR" className="border-4 border-stone-200 rounded-lg" data-testid="tf-qr" />
            <div className="flex-1 space-y-2">
              <p className="text-sm text-stone-600">Can't scan? Enter this secret manually:</p>
              <code className="block bg-stone-100 px-3 py-2 rounded font-mono text-xs break-all">{enroll.secret}</code>
              <p className="text-xs text-stone-400 mt-3">Issuer: <strong>{enroll.issuer}</strong> · Account: <strong>{enroll.account}</strong></p>
            </div>
          </div>
          <h3 className="font-bold mt-6 mb-2">Step 2 · Verify</h3>
          <div className="flex gap-2">
            <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="123456" data-testid="tf-code-input"
              className="border-2 border-stone-300 rounded-lg px-4 py-3 text-center text-2xl font-mono font-bold tracking-widest w-48" />
            <button onClick={doVerify} data-testid="tf-verify" className="px-5 py-3 bg-emerald-600 text-white rounded-lg text-sm font-bold">Verify & Enable</button>
          </div>
        </div>
      )}

      {backup && (
        <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-6" data-testid="tf-backup-codes">
          <h3 className="font-bold mb-2 text-amber-800">⚠ Save these backup codes</h3>
          <p className="text-xs text-amber-700 mb-3">Store these somewhere safe. Each can be used once if you lose your authenticator device.</p>
          <div className="grid grid-cols-4 gap-2">
            {backup.map((b, i) => <code key={i} className="bg-white px-3 py-2 rounded text-xs font-mono border">{b}</code>)}
          </div>
        </div>
      )}

      {status?.enabled && (
        <div className="bg-white border rounded-2xl p-6" data-testid="tf-disable-card">
          <h3 className="font-bold mb-3">Disable 2FA</h3>
          <p className="text-sm text-stone-600 mb-3">Enter your current 6-digit code to turn off 2FA (not recommended).</p>
          <div className="flex gap-2">
            <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="123456" className="border rounded-lg px-3 py-2 font-mono w-40" />
            <button onClick={disable} data-testid="tf-disable" className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-bold">Disable</button>
          </div>
        </div>
      )}
    </div>
  );
};
