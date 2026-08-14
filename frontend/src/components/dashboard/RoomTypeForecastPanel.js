import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RoomTypeForecastPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try { const { data: d } = await axios.get(`${API}/room-type-forecast/${pid}?days=14`); setData(d); }
    catch { /* */ } finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  const heat = (p) => p >= 80 ? "bg-rose-100 text-rose-700" : p >= 50 ? "bg-amber-100 text-amber-700" : p > 0 ? "bg-emerald-50 text-emerald-700" : "bg-stone-50 text-stone-400";
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="rtf-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900">Oda Tipi Bazlı Forecast</h1>
        <p className="text-sm text-stone-500 mt-0.5">Her oda tipi için bağımsız tahmin (IDeaS paritesi). {data.note}</p>
      </div>
      {data.room_types.map((rt) => (
        <div key={rt.room_type_id} className="bg-white border border-stone-200 rounded-2xl p-4" data-testid={`rtf-${rt.room_type_id}`}>
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-sm font-black text-stone-900">{rt.name}</h2>
            <span className="text-[11px] text-stone-500">{rt.capacity} oda · Ø tahmini doluluk %{rt.avg_forecast_occ_pct}</span>
          </div>
          <div className="flex gap-1 overflow-x-auto">
            {rt.days.map((d) => (
              <div key={d.date} className={`min-w-[64px] rounded-lg p-1.5 text-center ${heat(d.forecast_occ_pct)}`} title={`OTB ${d.otb} · 8h Ø ${d.same_dow_avg}`}>
                <p className="text-[9px] font-bold">{d.date.slice(5)}</p>
                <p className="text-sm font-black">{d.forecast}</p>
                <p className="text-[9px]">%{d.forecast_occ_pct}</p>
              </div>))}
          </div>
        </div>))}
    </div>
  );
}
