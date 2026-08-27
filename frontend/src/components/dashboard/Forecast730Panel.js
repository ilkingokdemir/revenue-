import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarBlank } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;

export default function Forecast730Panel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [data, setData] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/forecast-730/${pid}`);
      setData(r.data);
    } catch { toast.error("Tahmin verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="f730-loading">730 gün tahmini hesaplanıyor…</p>;
  const maxIdx = Math.max(...data.months.map((m) => m.seasonality_idx), 1.2);

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-4" data-testid="forecast-730-panel">
      <div className="bg-gradient-to-br from-sky-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CalendarBlank size={22} className="text-sky-400" /> 730 Gün Tahmin Ufku
        </h1>
        <p className="text-sm text-stone-300 mt-1">24 ay ileriye mevsimsellik bazlı talep eğrisi + defterdeki OTB (Atomize paritesi). {data.capacity} oda · {data.history_months} ay tarihsel veri.</p>
      </div>
      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Aylık mevsimsellik endeksi & projeksiyon</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2" data-testid="f730-months-grid">
          {data.months.map((m) => (
            <div key={m.month} data-testid={`f730-month-${m.month}`}
              className={`rounded-xl p-3 border ${m.seasonality_idx >= 1.15 ? "bg-emerald-50 border-emerald-200" : m.seasonality_idx <= 0.85 ? "bg-rose-50 border-rose-200" : "bg-stone-50 border-stone-200"}`}>
              <div className="text-xs font-mono text-stone-500">{m.month}</div>
              <div className="text-lg font-black">{m.seasonality_idx}×</div>
              <div className="h-1.5 bg-stone-200 rounded-full mt-1 overflow-hidden">
                <div className={`h-1.5 rounded-full ${m.seasonality_idx >= 1.15 ? "bg-emerald-500" : m.seasonality_idx <= 0.85 ? "bg-rose-400" : "bg-stone-400"}`}
                  style={{ width: `${(m.seasonality_idx / maxIdx) * 100}%` }} />
              </div>
              <div className="text-[11px] text-stone-500 mt-1.5">Proj. doluluk <b>%{m.projected_occ_pct}</b></div>
              <div className="text-[11px] text-stone-500">OTB <b>%{m.otb_occ_pct}</b> ({m.otb_room_nights} og)</div>
              <div className="text-[10px] text-stone-400 mt-1 leading-tight">{m.stance}</div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-stone-400 mt-3">{data.note}</p>
      </div>
    </div>
  );
}
