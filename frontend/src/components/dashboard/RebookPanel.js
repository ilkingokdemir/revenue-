/**
 * Quick Re-booking CTA Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Send, RefreshCw, MousePointer } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RebookPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState({ items: [], count: 0, clicked: 0, click_rate: 0 });
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [pct, setPct] = useState(10);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/rebook/${propertyId}/dispatches?days=60`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const sweep = async () => {
    try {
      const { data: r } = await axios.post(`${API}/rebook/sweep`, { property_id: propertyId, days_after_checkout: days, loyalty_discount_pct: pct });
      toast.success(`Queued ${r.queued} (target ${r.target_date}, scanned ${r.scanned})`);
      refresh();
    } catch { toast.error("Sweep failed"); }
  };

  return (
    <div className="space-y-6" data-testid="rebook-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Quick Re-booking CTA</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Check-out'tan N gün sonra misafire tek kullanımlık kuponlu "tekrar bekliyoruz" e-postası gönderilir. Günlük otomatik tarama aktif (Scheduler → rebook_sweep).</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="Dispatches (60d)" value={data.count} />
        <Stat label="Clicks" value={data.clicked} highlight />
        <Stat label="Click rate" value={`${data.click_rate}%`} highlight={data.click_rate >= 15} />
        <Stat label="Redeemed" value={data.redeemed || 0} highlight={(data.redeemed || 0) > 0} />
        <Stat label="Conversion" value={`${data.conversion_rate || 0}%`} highlight={(data.conversion_rate || 0) > 0} />
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        <label className="flex flex-col gap-1"><span className="text-stone-500">Days after checkout</span><input type="number" value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
        <label className="flex flex-col gap-1"><span className="text-stone-500">Loyalty discount %</span><input type="number" value={pct} onChange={(e) => setPct(parseFloat(e.target.value))} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
        <button data-testid="rb-sweep-btn" onClick={sweep} className="px-2 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 mt-4 flex items-center justify-center gap-1"><Send className="w-3 h-3" /> Run sweep</button>
        <button onClick={refresh} className="px-2 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 mt-4 flex items-center justify-center gap-1">{loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh</button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Sent</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Coupon</th><th className="px-3 py-2 text-right">Disc %</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Clicked</th></tr>
          </thead>
          <tbody>
            {data.items.map((d) => (
              <tr key={d.id} className="border-t border-stone-800/60 text-stone-200" data-testid="rb-row">
                <td className="px-3 py-2 text-xs text-stone-400">{(d.scheduled_for || "").slice(0, 16)}</td>
                <td className="px-3 py-2"><div>{d.guest_name}</div><div className="text-[10px] text-stone-500">{d.guest_email}</div></td>
                <td className="px-3 py-2 font-mono text-[11px] text-cyan-300">{d.coupon_code || `/rebook/${d.token?.slice(0, 12)}…`}</td>
                <td className="px-3 py-2 text-right">{d.loyalty_discount_pct}%</td>
                <td className="px-3 py-2 text-xs">
                  {d.status === "sent" ? <span className="text-emerald-300">gönderildi{d.email_result === "mock" ? " (mock)" : ""}</span>
                    : d.status === "failed" ? <span className="text-rose-300">hata</span>
                    : <span className="text-stone-400">bekliyor</span>}
                </td>
                <td className="px-3 py-2">{d.clicked ? <span className="text-emerald-300 flex items-center gap-1 text-xs"><MousePointer className="w-3 h-3" /> {(d.clicked_at || "").slice(11, 16)}</span> : <span className="text-xs text-stone-500">—</span>}</td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No dispatches yet. Run sweep — it queues for guests whose checkout was exactly N days ago.</td></tr>}
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
