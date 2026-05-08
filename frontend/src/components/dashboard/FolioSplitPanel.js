/**
 * Folio Split-Billing Panel
 * Configure payer splits per booking, preview allocation, settle, print per-payer folio.
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Split, Plus, Printer, RefreshCw, Lock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CATEGORIES = ["room", "tax", "food", "minibar", "spa", "parking", "telephone", "laundry", "late_checkout", "other"];
const TYPES = ["company", "agent", "event", "guest"];

export default function FolioSplitPanel({ propertyId, hotelName = "" }) {
  const [bookingId, setBookingId] = useState("");
  const [alloc, setAlloc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ payer_name: "", payer_email: "", payer_type: "company", categories: ["room"], cap_amount: "", cap_pct: "" });

  const fmt = (n, c = "GBP") => `${c} ${Number(n || 0).toFixed(2)}`;

  const load = async () => {
    if (!bookingId.trim()) return toast.error("Booking ID required");
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/folio-split/${bookingId.trim()}`);
      setAlloc(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Not found"); setAlloc(null); }
    setLoading(false);
  };

  const addPayer = async () => {
    if (!form.payer_name) return toast.error("Payer name required");
    try {
      const payload = { ...form };
      if (!payload.cap_amount) delete payload.cap_amount; else payload.cap_amount = parseFloat(payload.cap_amount);
      if (!payload.cap_pct) delete payload.cap_pct; else payload.cap_pct = parseFloat(payload.cap_pct);
      await axios.post(`${API}/folio-split/${bookingId.trim()}/configure`, payload);
      toast.success("Payer configured");
      setAdding(false);
      load();
    } catch { toast.error("Failed"); }
  };

  const settle = async () => {
    if (!window.confirm("Settle splits? This locks the allocation.")) return;
    try {
      await axios.post(`${API}/folio-split/${bookingId.trim()}/settle`, {});
      toast.success("Allocation settled");
    } catch { toast.error("Failed"); }
  };

  const printPayer = (payer) => {
    window.open(`${API}/folio-split/${bookingId.trim()}/payer/${payer.payer_id}/html`, "_blank");
  };

  const toggleCat = (c) => setForm({ ...form, categories: form.categories.includes(c) ? form.categories.filter((x) => x !== c) : [...form.categories, c] });

  return (
    <div className="space-y-6" data-testid="folio-split-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Folio Split-Billing</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Split a single booking's folio between guest, employer, agent, or event organiser.</p>
      </div>

      <div className="flex gap-2">
        <input data-testid="fs-booking-input" value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="Booking ID" className="flex-1 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm font-mono" />
        <button data-testid="fs-load-btn" onClick={load} disabled={loading} className="px-4 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Load
        </button>
        {alloc && (
          <>
            <button data-testid="fs-add-btn" onClick={() => setAdding(true)} className="px-4 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm flex items-center gap-2"><Plus className="w-4 h-4" /> Add payer</button>
            <button data-testid="fs-settle-btn" onClick={settle} className="px-4 py-2 rounded bg-violet-500/20 border border-violet-500/40 text-violet-200 text-sm flex items-center gap-2"><Lock className="w-4 h-4" /> Settle</button>
          </>
        )}
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2 text-xs">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input data-testid="fs-form-name" placeholder="Payer name (e.g. Acme Corp)" value={form.payer_name} onChange={(e) => setForm({ ...form, payer_name: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
            <input placeholder="Payer email" value={form.payer_email} onChange={(e) => setForm({ ...form, payer_email: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
            <select value={form.payer_type} onChange={(e) => setForm({ ...form, payer_type: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100">
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="text-stone-400">Pays for categories:</div>
          <div className="flex flex-wrap gap-1">
            {CATEGORIES.map((c) => (
              <label key={c} className={`text-xs px-2 py-1 rounded border cursor-pointer ${form.categories.includes(c) ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>
                <input type="checkbox" className="hidden" checked={form.categories.includes(c)} onChange={() => toggleCat(c)} />{c}
              </label>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input type="number" placeholder="Cap amount £ (optional)" value={form.cap_amount} onChange={(e) => setForm({ ...form, cap_amount: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
            <input type="number" placeholder="Cap % of total (optional)" value={form.cap_pct} onChange={(e) => setForm({ ...form, cap_pct: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setAdding(false)} className="px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300">Cancel</button>
            <button data-testid="fs-save-payer-btn" onClick={addPayer} className="px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200">Save payer</button>
          </div>
        </div>
      )}

      {alloc && (
        <div className="space-y-4" data-testid="fs-alloc-box">
          <div className="text-sm text-stone-400">Total charges: <span className="text-stone-100 font-medium">{fmt(alloc.total_charges, alloc.currency)}</span></div>
          <div className="grid lg:grid-cols-2 gap-4">
            {alloc.payers.map((p) => (
              <div key={p.payer_id} className="rounded-xl border border-stone-800 bg-stone-900/60 p-4" data-testid="fs-payer-card">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-stone-100 font-medium flex items-center gap-2"><Split className="w-3 h-3" />{p.payer_name || "Guest (default)"}</div>
                    <div className="text-[10px] text-stone-500">{p.payer_type} · {p.payer_email || "—"}</div>
                  </div>
                  <button onClick={() => printPayer(p)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1"><Printer className="w-3 h-3" /> PDF</button>
                </div>
                <div className="text-xs text-stone-400 mb-2">Categories: <span className="text-stone-300">{p.categories.join(", ")}</span></div>
                <table className="min-w-full text-xs mb-2">
                  <thead><tr className="text-left text-[10px] text-stone-500"><th className="py-1">Date</th><th className="py-1">Item</th><th className="py-1 text-right">Amount</th></tr></thead>
                  <tbody>
                    {p.items.map((it, i) => (
                      <tr key={i} className="border-t border-stone-800/60 text-stone-200">
                        <td className="py-1 text-stone-400">{(it.posted_at || "").slice(0, 10)}</td>
                        <td className="py-1">{it.description || it.category}</td>
                        <td className="py-1 text-right">{fmt(it.amount, alloc.currency)}</td>
                      </tr>
                    ))}
                    {p.items.length === 0 && <tr><td colSpan={3} className="py-2 text-center text-stone-500">No items.</td></tr>}
                  </tbody>
                </table>
                <div className="flex justify-between pt-2 border-t border-stone-800 text-stone-100 font-semibold">
                  <span>Subtotal</span><span>{fmt(p.subtotal, alloc.currency)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
