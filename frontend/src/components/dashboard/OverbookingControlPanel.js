import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Warning, Broadcast } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OverbookingControlPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    try { const { data: d } = await axios.get(`${API}/overbooking-control/${pid}?days=14`); setData(d); }
    catch { /* */ } finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const applyLimits = async () => {
    setApplying(true);
    try {
      const { data: r } = await axios.post(`${API}/overbooking-control/${pid}/apply`, { days: 14 });
      toast.success(`${r.applied_days} günün limiti kanallara uygulandı — +${r.extra_capacity} oda kapasitesi, beklenen ek gelir ${r.expected_extra_revenue}`);
      load();
    } catch { toast.error("Limitler uygulanamadı"); } finally { setApplying(false); }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="overbooking-panel">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-stone-900">Overbooking & Wash Control</h1>
          <p className="text-sm text-stone-500 mt-0.5">Kaynak bazlı no-show modeliyle günlük güvenli overbooking limiti, walk risk maliyeti ve acil stop-sell tetiği. {data.note}</p>
        </div>
        <button onClick={applyLimits} disabled={applying} data-testid="ob-apply-limits-btn"
          className="px-4 py-2 text-xs font-bold rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 inline-flex items-center gap-2">
          <Broadcast size={15} weight="fill" className={applying ? "animate-pulse" : ""} />
          {applying ? "Uygulanıyor…" : "Limitleri Kanallara Uygula (1 tık)"}
        </button>
      </div>
      {data.applied_count > 0 && (
        <div className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2 inline-block" data-testid="ob-applied-info">
          ✓ {data.applied_count} günün limiti aktif — kanallar (Direkt, Booking, Expedia, Airbnb, Agoda) güncel satış limitini kullanıyor
        </div>
      )}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="ob-adr-card"><div className="text-[10px] uppercase font-bold text-stone-400">ADR</div><div className="text-lg font-black">{data.adr}</div></div>
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200" data-testid="ob-walk-card"><div className="text-[10px] uppercase font-bold text-rose-600">Walk maliyeti / misafir</div><div className="text-lg font-black text-rose-900">{data.walk_cost_per_guest}</div></div>
        <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="ob-cap-card"><div className="text-[10px] uppercase font-bold text-stone-400">Kapasite</div><div className="text-lg font-black">{data.capacity}</div></div>
      </div>
      {data.emergency_dates.length > 0 && (
        <div className="flex items-center gap-2 bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs font-bold text-rose-700" data-testid="ob-emergency">
          <Warning size={16} weight="fill" /> ACİL STOP-SELL önerisi: {data.emergency_dates.join(", ")} (%98+ doluluk, tampon yok)
        </div>
      )}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-x-auto">
        <table className="w-full text-xs" data-testid="ob-table">
          <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]"><tr>
            <th className="px-3 py-2 text-left">Tarih</th><th className="px-3 py-2 text-right">Doluluk</th>
            <th className="px-3 py-2 text-right">Beklenen no-show</th><th className="px-3 py-2 text-right">Önerilen limit</th>
            <th className="px-3 py-2 text-right">Uygulanan</th>
            <th className="px-3 py-2 text-right">Beklenen kazanç</th><th className="px-3 py-2 text-right">Walk riski</th>
            <th className="px-3 py-2 text-right">Net</th></tr></thead>
          <tbody>{data.days.map((r) => (
            <tr key={r.date} className={`border-t border-stone-100 ${r.emergency_stop_sell ? "bg-rose-50" : ""}`}>
              <td className="px-3 py-1.5 font-semibold">{r.date}</td>
              <td className="px-3 py-1.5 text-right">%{r.occupancy_pct}</td>
              <td className="px-3 py-1.5 text-right">{r.expected_no_shows}</td>
              <td className="px-3 py-1.5 text-right font-black text-indigo-700">+{r.recommended_overbooking_limit}</td>
              <td className="px-3 py-1.5 text-right">{r.applied_limit != null
                ? <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-bold text-[10px]">✓ +{r.applied_limit}</span>
                : <span className="text-stone-300">—</span>}</td>
              <td className="px-3 py-1.5 text-right text-emerald-700">{r.expected_gain}</td>
              <td className="px-3 py-1.5 text-right text-rose-600">-{r.walk_risk_cost}</td>
              <td className={`px-3 py-1.5 text-right font-bold ${r.net_expected >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{r.net_expected}</td>
            </tr>))}
          </tbody>
        </table>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="ob-sources">
        <p className="text-[10px] font-black uppercase text-stone-500 mb-2">Kaynak bazlı no-show / iptal oranları (180g)</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.source_rates).map(([src, v]) => (
            <span key={src} className="text-[10px] px-2.5 py-1 rounded-full bg-stone-100 text-stone-700 font-bold">
              {src}: no-show %{v.no_show_pct} · iptal %{v.cancel_pct} ({v.sample})
            </span>))}
        </div>
      </div>
    </div>
  );
}
