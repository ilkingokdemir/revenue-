import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Warning } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OverbookingControlPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try { const { data: d } = await axios.get(`${API}/overbooking-control/${pid}?days=14`); setData(d); }
    catch { /* */ } finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="overbooking-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900">Overbooking & Wash Control</h1>
        <p className="text-sm text-stone-500 mt-0.5">Kaynak bazlı no-show modeliyle günlük güvenli overbooking limiti, walk risk maliyeti ve acil stop-sell tetiği. {data.note}</p>
      </div>
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
            <th className="px-3 py-2 text-right">Beklenen kazanç</th><th className="px-3 py-2 text-right">Walk riski</th>
            <th className="px-3 py-2 text-right">Net</th></tr></thead>
          <tbody>{data.days.map((r) => (
            <tr key={r.date} className={`border-t border-stone-100 ${r.emergency_stop_sell ? "bg-rose-50" : ""}`}>
              <td className="px-3 py-1.5 font-semibold">{r.date}</td>
              <td className="px-3 py-1.5 text-right">%{r.occupancy_pct}</td>
              <td className="px-3 py-1.5 text-right">{r.expected_no_shows}</td>
              <td className="px-3 py-1.5 text-right font-black text-indigo-700">+{r.recommended_overbooking_limit}</td>
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
