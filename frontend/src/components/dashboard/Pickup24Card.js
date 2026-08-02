import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Bed, TrendUp, TrendDown, CaretDown, CaretUp, Pulse } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const timeAgo = (iso) => {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
};

export const Pickup24Card = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const fetch = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/pulse/pickup-24h`, { params: { property_id: propertyId || "" } });
      setData(data);
    } catch (e) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { fetch(); const t = setInterval(fetch, 120000); return () => clearInterval(t); }, [fetch]);

  if (!data) return null;
  const up = data.trend >= 0;

  return (
    <div className="bg-white border border-stone-200 rounded-xl overflow-hidden mb-6" data-testid="pickup-24h-card">
      <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-60" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500" />
          </span>
          <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
            <Pulse size={15} className="text-rose-500" weight="bold" /> 24-Hour Pickup
          </h3>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold flex items-center gap-1 ${up ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}
          data-testid="pickup-trend-badge">
          {up ? <TrendUp size={11} weight="bold" /> : <TrendDown size={11} weight="bold" />}
          {up ? "+" : ""}{data.trend} vs prev 24h
        </span>
      </div>

      {data.strong_day && (
        <div className="px-4 py-1.5 bg-emerald-50 border-b border-emerald-100 text-[11px] text-emerald-700 font-semibold flex items-center gap-1.5" data-testid="pickup-strong-day-banner">
          <TrendUp size={12} weight="bold" /> Strong sales day — pickup is well above the usual pace
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-5 divide-x divide-stone-100">
        <div className="p-3 text-center">
          <div className="text-xl font-bold text-stone-900" data-testid="pickup-rooms-sold">{data.rooms_sold_24h}</div>
          <div className="text-[9px] text-stone-400 uppercase font-semibold">Rooms Sold (24h)</div>
        </div>
        <div className="p-3 text-center">
          <div className="text-xl font-bold text-rose-600" data-testid="pickup-pct">{data.pickup_pct}%</div>
          <div className="text-[9px] text-stone-400 uppercase font-semibold">Pickup % (30d cap.)</div>
        </div>
        <div className="p-3 text-center">
          <div className="text-xl font-bold text-stone-900">{data.room_nights_24h}</div>
          <div className="text-[9px] text-stone-400 uppercase font-semibold">Room Nights</div>
        </div>
        <div className="p-3 text-center">
          <div className="text-xl font-bold text-emerald-700">£{data.revenue_24h?.toLocaleString()}</div>
          <div className="text-[9px] text-stone-400 uppercase font-semibold">Revenue (24h)</div>
        </div>
        <div className="p-3 text-center">
          <div className="text-xl font-bold text-blue-700">£{data.adr_24h}</div>
          <div className="text-[9px] text-stone-400 uppercase font-semibold">Pickup ADR</div>
        </div>
      </div>

      {data.daily_trend?.length > 0 && (
        <div className="px-4 pt-2 pb-1 border-t border-stone-100" data-testid="pickup-trend-chart">
          <div className="text-[9px] text-stone-400 uppercase font-semibold mb-1">Daily pickup — last 14 days</div>
          <div className="flex items-end gap-1 h-12">
            {(() => {
              const max = Math.max(...data.daily_trend.map(d => d.rooms), 1);
              return data.daily_trend.map((d, i) => (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-0.5" title={`${d.date}: ${d.rooms} rooms`}>
                  <div className={`w-full rounded-t transition-all ${i === data.daily_trend.length - 1 ? "bg-rose-500" : "bg-rose-200 hover:bg-rose-300"}`}
                    style={{ height: `${Math.max(6, (d.rooms / max) * 100)}%` }} />
                </div>
              ));
            })()}
          </div>
          <div className="flex justify-between text-[8px] text-stone-300 mt-0.5">
            <span>{data.daily_trend[0]?.date.slice(5)}</span>
            <span className="text-rose-400 font-semibold">today</span>
          </div>
        </div>
      )}

      {data.by_source?.length > 0 && (
        <div className="px-4 py-2 border-t border-stone-100 flex flex-wrap gap-1.5">
          {data.by_source.map(s => (
            <span key={s.source} className="text-[10px] px-2 py-0.5 bg-stone-50 border border-stone-200 rounded-full text-stone-600">
              {s.source}: <b>{s.rooms}</b>
            </span>
          ))}
        </div>
      )}

      <button onClick={() => setExpanded(e => !e)}
        className="w-full px-4 py-2 border-t border-stone-100 text-[11px] text-stone-500 hover:bg-stone-50 flex items-center justify-center gap-1 font-medium"
        data-testid="pickup-expand-btn">
        {expanded ? <CaretUp size={11} /> : <CaretDown size={11} />}
        {expanded ? "Hide sold rooms" : `Show sold rooms (${data.recent_bookings?.length || 0})`}
      </button>

      {expanded && (
        <div className="border-t border-stone-100 divide-y divide-stone-50 max-h-64 overflow-y-auto" data-testid="pickup-bookings-list">
          {data.recent_bookings?.map((b, i) => (
            <div key={i} className="px-4 py-2 flex items-center justify-between text-xs hover:bg-stone-50">
              <div className="flex items-center gap-2 min-w-0">
                <Bed size={13} className="text-stone-300 shrink-0" />
                <div className="min-w-0">
                  <span className="font-mono font-semibold text-stone-700">{b.booking_ref || "—"}</span>
                  <span className="text-stone-400 mx-1">·</span>
                  <span className="text-stone-600">{b.guest_name}</span>
                  <div className="text-[10px] text-stone-400 truncate">
                    {b.check_in} → {b.check_out} · {b.rooms || 1} room · {b.source || "Direct"} · {timeAgo(b.created_at)}
                  </div>
                </div>
              </div>
              <span className="font-bold text-stone-700 shrink-0">£{b.total_price?.toFixed(0)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
