/**
 * Chargeback Defense Panel
 * Open dispute cases, auto-build evidence packages and track win/loss rate.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Shield, FileSearch, Plus, RefreshCw, Trophy } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (n, c = "GBP") => new Intl.NumberFormat("en-GB", { style: "currency", currency: c }).format(Number(n || 0));

export default function ChargebackPanel({ propertyId, hotelName = "" }) {
  const [list, setList] = useState({ items: [], won: 0, lost: 0, win_rate: 0 });
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState({ status: "", days: 90 });
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ booking_id: "", amount: 0, reason: "fraudulent", card_last4: "", issuer: "" });
  const [active, setActive] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [evLoading, setEvLoading] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ days: filter.days });
      if (filter.status) params.append("status", filter.status);
      const { data } = await axios.get(`${API}/chargebacks/${propertyId}?${params}`);
      setList(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, filter]);

  useEffect(() => { load(); }, [load]);

  const open = async () => {
    if (!form.booking_id || !form.amount) return toast.error("Booking ID + amount required");
    try {
      await axios.post(`${API}/chargebacks`, { property_id: propertyId, ...form });
      toast.success("Case opened");
      setAdding(false);
      load();
    } catch { toast.error("Failed"); }
  };

  const buildEvidence = async (caseId) => {
    setEvLoading(true);
    try {
      const { data } = await axios.get(`${API}/chargebacks/case/${caseId}/evidence`);
      setEvidence(data);
      toast.success(`Evidence score: ${data.evidence_score}%`);
    } catch { toast.error("Build failed"); }
    setEvLoading(false);
  };

  const setStatus = async (caseId, status) => {
    try {
      await axios.post(`${API}/chargebacks/case/${caseId}/status`, { status });
      toast.success(`Marked ${status}`);
      load();
    } catch { toast.error("Failed"); }
  };

  const addNote = async () => {
    if (!note.trim() || !active) return;
    try {
      await axios.post(`${API}/chargebacks/case/${active.id}/note`, { text: note });
      toast.success("Note added");
      setNote("");
    } catch { toast.error("Failed"); }
  };

  const downloadEvidence = () => {
    if (!evidence) return;
    const blob = new Blob([JSON.stringify(evidence, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chargeback-${evidence.case_ref}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6" data-testid="chargeback-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Chargeback Defense</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}One-click evidence packages: folio, lock entries, comms, ID, registration card.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Cases" value={list.count || 0} />
        <Stat label="Won" value={list.won} highlight />
        <Stat label="Lost" value={list.lost} />
        <Stat label="Win rate" value={`${list.win_rate}%`} highlight={list.win_rate >= 50} />
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <select value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          <option value="">All statuses</option>{["pending", "submitted", "won", "lost", "accepted"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filter.days} onChange={(e) => setFilter({ ...filter, days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          {[30, 90, 180, 365].map((d) => <option key={d} value={d}>{d}d</option>)}
        </select>
        <button data-testid="cb-refresh-btn" onClick={load} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
        <button data-testid="cb-add-btn" onClick={() => setAdding(true)} className="ml-auto text-xs px-3 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 flex items-center gap-1">
          <Plus className="w-3 h-3" /> Open case
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
          <input data-testid="cb-form-booking" placeholder="Booking ID" value={form.booking_id} onChange={(e) => setForm({ ...form, booking_id: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 col-span-2" />
          <input data-testid="cb-form-amount" type="number" placeholder="Disputed amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
            {["fraudulent", "not_received", "duplicate", "not_described"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <input placeholder="Card last4" value={form.card_last4} onChange={(e) => setForm({ ...form, card_last4: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input placeholder="Issuer (Visa, MC...)" value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <button data-testid="cb-save-btn" onClick={open} className="col-span-2 md:col-span-3 px-2 py-2 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs">Open case</button>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          {loading ? <div className="p-6"><Loader2 className="w-5 h-5 animate-spin text-stone-500" /></div> : (
            <table className="min-w-full text-sm">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr><th className="px-3 py-2">Case</th><th className="px-3 py-2">Reason</th><th className="px-3 py-2 text-right">Amount</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
              </thead>
              <tbody>
                {list.items.map((c) => (
                  <tr key={c.id} onClick={() => { setActive(c); setEvidence(null); }} className={`border-t border-stone-800/60 cursor-pointer hover:bg-stone-800/40 ${active?.id === c.id ? "bg-stone-800/60" : ""}`} data-testid="cb-row">
                    <td className="px-3 py-2 text-stone-100 font-mono text-xs">{c.case_ref}</td>
                    <td className="px-3 py-2 text-stone-300 text-xs">{c.reason_code}</td>
                    <td className="px-3 py-2 text-right">{fmt(c.amount, c.currency)}</td>
                    <td className="px-3 py-2"><StatusPill status={c.status} /></td>
                    <td className="px-3 py-2 text-right text-xs text-stone-400">{(c.deadline || "").slice(0, 10)}</td>
                  </tr>
                ))}
                {list.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-500">No cases.</td></tr>}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          {!active ? (
            <div className="text-center text-stone-500 py-12"><Shield className="w-8 h-8 mx-auto mb-2 opacity-60" />Select a case to build the evidence package.</div>
          ) : (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-stone-100 font-mono">{active.case_ref}</div>
                  <div className="text-xs text-stone-400">Booking {active.booking_id?.slice(0, 8)} · {fmt(active.amount, active.currency)}</div>
                </div>
                <StatusPill status={active.status} />
              </div>
              <div className="flex flex-wrap gap-2">
                <button data-testid="cb-build-btn" onClick={() => buildEvidence(active.id)} className="text-xs px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-1">
                  {evLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileSearch className="w-3 h-3" />} Build evidence
                </button>
                <button onClick={() => setStatus(active.id, "submitted")} className="text-xs px-3 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200">Mark submitted</button>
                <button data-testid="cb-mark-won-btn" onClick={() => setStatus(active.id, "won")} className="text-xs px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-1">
                  <Trophy className="w-3 h-3" /> Won
                </button>
                <button onClick={() => setStatus(active.id, "lost")} className="text-xs px-3 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200">Lost</button>
              </div>
              {evidence && (
                <div className="rounded-lg border border-stone-800 bg-stone-950/50 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-stone-300 text-xs uppercase tracking-wider">Evidence score</div>
                    <div className={`text-2xl font-semibold ${evidence.evidence_score >= 70 ? "text-emerald-300" : evidence.evidence_score >= 40 ? "text-amber-300" : "text-rose-300"}`}>{evidence.evidence_score}%</div>
                  </div>
                  <ul className="text-xs space-y-1">
                    {Object.entries(evidence.checks).map(([k, v]) => (
                      <li key={k} className={`flex items-center gap-2 ${v ? "text-emerald-300" : "text-stone-500"}`}>
                        <span>{v ? "✓" : "○"}</span>{k.replace(/_/g, " ")}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-3 text-xs text-stone-400 italic border-l-2 border-stone-700 pl-2">{evidence.narrative_summary}</div>
                  <button onClick={downloadEvidence} className="mt-3 w-full text-xs px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200">Download manifest (.json)</button>
                </div>
              )}
              <div>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add note…" rows={2} className="w-full text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
                <button onClick={addNote} className="mt-1 text-xs px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-200">Append note</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    pending: "bg-stone-800 border-stone-700 text-stone-300",
    submitted: "bg-amber-500/20 border-amber-500/40 text-amber-200",
    won: "bg-emerald-500/20 border-emerald-500/40 text-emerald-200",
    lost: "bg-rose-500/20 border-rose-500/40 text-rose-200",
    accepted: "bg-stone-800 border-stone-700 text-stone-400",
  };
  return <span className={`text-[10px] px-2 py-0.5 rounded border ${map[status] || ""}`}>{status}</span>;
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
