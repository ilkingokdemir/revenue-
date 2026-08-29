import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Clock, Shield, TrendingUp, PenLine } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ICONS = { ladder: TrendingUp, guard: Shield, override: PenLine };
const COLORS = { ladder: "text-emerald-600 bg-emerald-50 border-emerald-200", guard: "text-amber-600 bg-amber-50 border-amber-200", override: "text-sky-600 bg-sky-50 border-sky-200" };

export const PriceTimelineCard = ({ propertyId }) => {
  const pid = !propertyId || propertyId === "all" ? "aldgate-flats" : propertyId;
  const [date, setDate] = useState(() => new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10));
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    axios.get(`${API}/price-timeline/${pid}?date=${date}`).then(({ data: d }) => setData(d)).catch(() => setData(null));
  }, [pid, date]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 mb-4" data-testid="price-timeline-card">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <h3 className="text-sm font-black text-stone-800 flex items-center gap-2">
          <Clock className="w-4 h-4 text-violet-600" /> Fiyat Karar Zaman Çizelgesi
        </h3>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
          data-testid="price-timeline-date" className="border border-stone-200 rounded-lg px-2 py-1 text-xs" />
        {data?.comp_median && (
          <span className="ml-auto text-[10px] font-semibold text-stone-500">
            Rakip medyanı (48s): <b className="text-stone-800">£{data.comp_median}</b> · {data.comp_count} rakip
          </span>
        )}
      </div>
      {!data || data.events.length === 0 ? (
        <p className="text-xs text-stone-400" data-testid="price-timeline-empty">Bu gece için henüz fiyat hareketi yok — merdiven kademesi, korkuluk kırpması veya elle yazım olduğunda burada gerekçesiyle görünür.</p>
      ) : (
        <div className="space-y-0" data-testid="price-timeline-events">
          {data.events.map((e, i) => {
            const Icon = ICONS[e.type] || Clock;
            return (
              <div key={i} className="flex gap-3 relative pb-3" data-testid={`price-timeline-event-${i}`}>
                {i < data.events.length - 1 && <div className="absolute left-[13px] top-7 bottom-0 w-px bg-stone-200" />}
                <div className={`w-7 h-7 rounded-full border flex items-center justify-center flex-shrink-0 ${COLORS[e.type] || "text-stone-500 bg-stone-50 border-stone-200"}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-stone-800">{e.title}</span>
                    {e.rate != null && <span className="text-xs font-black text-stone-900">£{e.rate}</span>}
                    <span className="ml-auto text-[10px] text-stone-400">{e.at ? new Date(e.at).toLocaleString("tr-TR") : ""}</span>
                  </div>
                  {e.detail && <p className="text-[11px] text-stone-500 truncate" title={e.detail}>{e.detail}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
