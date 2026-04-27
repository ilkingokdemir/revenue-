/**
 * Late-Checkout Offer Engine Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Clock, RefreshCw, CheckCircle2, XCircle, Save } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LateCheckoutOfferPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [data, setData] = useState({ items: [], count: 0, accepted: 0, revenue: 0, conversion_pct: 0 });
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: o }] = await Promise.all([
        axios.get(`${API}/late-checkout/${propertyId}/config`),
        axios.get(`${API}/late-checkout/${propertyId}/offers?days=7`),
      ]);
      setCfg(c);
      setData(o);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const saveCfg = async () => {
    try {
      await axios.post(`${API}/late-checkout/config`, { property_id: propertyId, ...cfg });
      toast.success("Config saved");
    } catch { toast.error("Failed"); }
  };

  const scan = async () => {
    setScanning(true);
    try {
      const { data } = await axios.post(`${API}/late-checkout/scan`, { property_id: propertyId });
      toast.success(`${data.checkouts_today} checkouts today: ${data.generated} offers, ${data.skipped_blocked} blocked`);
      refresh();
    } catch { toast.error("Scan failed"); }
    setScanning(false);
  };

  const accept = async (offer, hours) => {
    try {
      const { data } = await axios.post(`${API}/late-checkout/offer/${offer.id}/accept`, { hours });
      toast.success(`Charged ${offer.currency} ${data.charged} for +${hours}h`);
      refresh();
    } catch { toast.error("Failed"); }
  };

  const decline = async (offer) => {
    try {
      await axios.post(`${API}/late-checkout/offer/${offer.id}/decline`, {});
      toast.success("Declined");
      refresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="late-checkout-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Late-Checkout Offers</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Auto-priced hourly offers — front desk one-click accepts and charges to folio.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Offers (7d)" value={data.count} />
        <Stat label="Accepted" value={data.accepted} highlight />
        <Stat label="Conversion" value={`${data.conversion_pct}%`} highlight={data.conversion_pct >= 30} />
        <Stat label="Revenue" value={`£${data.revenue}`} highlight />
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
          <label className="flex flex-col gap-1"><span className="text-stone-500">% per hour</span>
            <input type="number" value={cfg.pct_per_hour} onChange={(e) => setCfg({ ...cfg, pct_per_hour: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Min charge £</span>
            <input type="number" value={cfg.min_charge} onChange={(e) => setCfg({ ...cfg, min_charge: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Max hours</span>
            <input type="number" value={cfg.max_hours} onChange={(e) => setCfg({ ...cfg, max_hours: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex items-center gap-2 text-stone-300 mt-4">
            <input type="checkbox" checked={!!cfg.block_if_next_night_booked} onChange={(e) => setCfg({ ...cfg, block_if_next_night_booked: e.target.checked })} /> Block if next night booked
          </label>
          <button data-testid="lc-save-cfg-btn" onClick={saveCfg} className="px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 mt-4 flex items-center justify-center gap-1"><Save className="w-3 h-3" /> Save</button>
        </div>
      )}

      <div className="flex gap-2">
        <button data-testid="lc-scan-btn" onClick={scan} disabled={scanning} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clock className="w-4 h-4" />} Generate today's offers
        </button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">For</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Room</th><th className="px-3 py-2">Tiers</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {data.items.map((o) => (
              <tr key={o.id} className="border-t border-stone-800/60 text-stone-200" data-testid="lc-offer-row">
                <td className="px-3 py-2 text-xs">{o.for_date}</td>
                <td className="px-3 py-2">{o.guest_name}</td>
                <td className="px-3 py-2">{o.room_number}</td>
                <td className="px-3 py-2 text-xs">{o.tiers.map((t) => `${t.label} ${o.currency}${t.price}`).join(" · ")}</td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${o.status === "accepted" ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : o.status === "declined" ? "bg-rose-500/20 border-rose-500/40 text-rose-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>{o.status}{o.status === "accepted" ? ` +${o.accepted_hours}h` : ""}</span></td>
                <td className="px-3 py-2 text-right">
                  {o.status === "open" && (
                    <div className="flex gap-1 justify-end">
                      {o.tiers.map((t) => (
                        <button data-testid="lc-accept-btn" key={t.hours} onClick={() => accept(o, t.hours)} className="text-xs px-2 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />+{t.hours}h
                        </button>
                      ))}
                      <button onClick={() => decline(o)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1"><XCircle className="w-3 h-3" /></button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No offers in window. Run the scan to generate offers for today's checkouts.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
