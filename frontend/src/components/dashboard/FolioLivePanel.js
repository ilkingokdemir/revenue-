/**
 * In-stay Folio Live Panel
 * Look up a booking by ID and surface a live folio + a print/PDF link.
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, FileText, Printer, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function FolioLivePanel({ propertyId, hotelName = "" }) {
  const [bookingId, setBookingId] = useState("");
  const [folio, setFolio] = useState(null);
  const [loading, setLoading] = useState(false);

  const fmt = (n, c = "GBP") => `${c} ${Number(n || 0).toFixed(2)}`;

  const load = async () => {
    if (!bookingId.trim()) return toast.error("Enter a booking ID");
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/folio-live/${bookingId.trim()}`);
      setFolio(data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Not found");
      setFolio(null);
    }
    setLoading(false);
  };

  const print = () => {
    if (!folio) return;
    window.open(`${API}/folio-live/${folio.booking.id}/html`, "_blank");
  };

  return (
    <div className="space-y-6" data-testid="folio-live-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">In-stay Folio</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Pull a guest's running folio at any moment of the stay — printable PDF for the guest portal.</p>
      </div>

      <div className="flex gap-2">
        <input data-testid="folio-booking-input" value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="Booking ID" className="flex-1 px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm font-mono" />
        <button data-testid="folio-load-btn" onClick={load} disabled={loading} className="px-4 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Load
        </button>
        {folio && (
          <button data-testid="folio-print-btn" onClick={print} className="px-4 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm flex items-center gap-2">
            <Printer className="w-4 h-4" /> Print / PDF
          </button>
        )}
      </div>

      {folio && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-4" data-testid="folio-detail">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div><div className="text-[10px] uppercase tracking-wider text-stone-500">Guest</div><div className="text-stone-100">{folio.booking.guest_name}</div></div>
            <div><div className="text-[10px] uppercase tracking-wider text-stone-500">Room</div><div className="text-stone-100">{folio.booking.room_number}</div></div>
            <div><div className="text-[10px] uppercase tracking-wider text-stone-500">Stay</div><div className="text-stone-100 text-xs">{folio.booking.check_in?.slice(0, 10)} → {folio.booking.check_out?.slice(0, 10)}</div></div>
            <div><div className="text-[10px] uppercase tracking-wider text-stone-500">Currency</div><div className="text-stone-100">{folio.booking.currency}</div></div>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1 flex items-center gap-1"><FileText className="w-3 h-3" /> Charges ({folio.charges.length})</div>
            <table className="min-w-full text-xs">
              <thead><tr className="text-left text-[10px] text-stone-500"><th className="px-2 py-1">Posted</th><th className="px-2 py-1">Description</th><th className="px-2 py-1 text-right">Amount</th></tr></thead>
              <tbody>
                {folio.charges.map((c, i) => (
                  <tr key={i} className="border-t border-stone-800/60 text-stone-200" data-testid="folio-charge-row">
                    <td className="px-2 py-1 text-stone-400">{(c.posted_at || "").slice(0, 10)}</td>
                    <td className="px-2 py-1">{c.description || c.category}</td>
                    <td className="px-2 py-1 text-right">{fmt(c.amount, folio.booking.currency)}</td>
                  </tr>
                ))}
                {folio.charges.length === 0 && <tr><td colSpan={3} className="px-2 py-2 text-center text-stone-500">No charges posted.</td></tr>}
              </tbody>
            </table>
          </div>

          <div>
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1">Payments ({folio.payments.length})</div>
            <table className="min-w-full text-xs">
              <thead><tr className="text-left text-[10px] text-stone-500"><th className="px-2 py-1">Paid</th><th className="px-2 py-1">Method</th><th className="px-2 py-1 text-right">Amount</th></tr></thead>
              <tbody>
                {folio.payments.map((p, i) => (
                  <tr key={i} className="border-t border-stone-800/60 text-stone-200" data-testid="folio-payment-row">
                    <td className="px-2 py-1 text-stone-400">{(p.paid_at || "").slice(0, 10)}</td>
                    <td className="px-2 py-1">{p.method} {p.reference}</td>
                    <td className="px-2 py-1 text-right">−{fmt(p.amount, folio.booking.currency)}</td>
                  </tr>
                ))}
                {folio.payments.length === 0 && <tr><td colSpan={3} className="px-2 py-2 text-center text-stone-500">No payments received.</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-3 border-t border-stone-800">
            <Stat label="Charges" value={fmt(folio.totals.charges, folio.booking.currency)} />
            <Stat label="Payments" value={fmt(folio.totals.payments, folio.booking.currency)} />
            <Stat label="Balance due" value={fmt(folio.totals.balance_due, folio.booking.currency)} highlight={folio.totals.balance_due > 0} ok={folio.totals.balance_due <= 0} />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, highlight = false, ok = false }) {
  const cls = ok ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-200" :
                  highlight ? "bg-rose-500/10 border-rose-500/40 text-rose-200" :
                  "bg-stone-800/60 border-stone-800 text-stone-100";
  return (
    <div className={`p-3 rounded-lg border ${cls}`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
