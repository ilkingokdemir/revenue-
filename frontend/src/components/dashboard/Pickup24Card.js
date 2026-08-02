import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Bed, TrendUp, TrendDown, CaretDown, CaretUp, Pulse, PencilSimple, Target } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const timeAgo = (iso) => {
  const mins = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  return `${Math.round(mins / 60)}h ago`;
};

export const Pickup24Card = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [editTarget, setEditTarget] = useState(false);
  const [targetVal, setTargetVal] = useState("");
  const [targetHistory, setTargetHistory] = useState([]);
  const [channels, setChannels] = useState(null);

  const toggleExpand = async () => {
    const next = !expanded;
    setExpanded(next);
    if (next && !channels) {
      try {
        const { data } = await axios.get(`${API}/pulse/pickup-by-channel`, {
          params: { property_id: propertyId || "", weeks: 4 },
        });
        setChannels(data);
      } catch (e) { /* silent */ }
    }
  };

  const fetch = useCallback(async () => {
    try {
      const [d, h] = await Promise.all([
        axios.get(`${API}/pulse/pickup-24h`, { params: { property_id: propertyId || "" } }),
        axios.get(`${API}/pulse/pickup-target/history`, { params: { property_id: propertyId || "", months: 6 } }),
      ]);
      setData(d.data);
      setTargetHistory(h.data);
    } catch (e) { /* silent */ }
  }, [propertyId]);

  const saveTarget = async () => {
    try {
      await axios.put(`${API}/pulse/pickup-target`, {
        property_id: propertyId || "all", target_rooms: parseInt(targetVal || "0", 10),
      });
      toast.success("Monthly target saved");
      setEditTarget(false);
      fetch();
    } catch (e) { toast.error("Failed to save target"); }
  };

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

      {/* Monthly target progress */}
      <div className="px-4 py-2 border-t border-stone-100" data-testid="pickup-target-section">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[9px] text-stone-400 uppercase font-semibold flex items-center gap-1">
            <Target size={11} className="text-indigo-500" /> Monthly target — {data.target?.month}
          </span>
          {editTarget ? (
            <span className="flex items-center gap-1">
              <input type="number" min="0" value={targetVal} onChange={e => setTargetVal(e.target.value)}
                className="w-20 border border-stone-200 rounded px-1.5 py-0.5 text-[11px]" data-testid="pickup-target-input" />
              <button onClick={saveTarget} className="text-[10px] px-2 py-0.5 bg-indigo-600 text-white rounded font-semibold" data-testid="pickup-target-save">Save</button>
              <button onClick={() => setEditTarget(false)} className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded">✕</button>
            </span>
          ) : (
            <button onClick={() => { setTargetVal(String(data.target?.target_rooms || "")); setEditTarget(true); }}
              className="text-[10px] text-stone-400 hover:text-indigo-600 flex items-center gap-0.5" data-testid="pickup-target-edit">
              <PencilSimple size={10} /> {data.target?.target_rooms ? "Edit" : "Set target"}
            </button>
          )}
        </div>
        {data.target?.target_rooms > 0 ? (
          <div data-testid="pickup-target-bar">
            <div className="flex justify-between text-[10px] text-stone-500 mb-0.5">
              <span><b className="text-stone-700">{data.target.mtd_rooms}</b> / {data.target.target_rooms} rooms MTD</span>
              <span className="flex items-center gap-2">
                <span className={`px-1.5 py-0 rounded-full font-semibold ${data.target.on_track ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"}`}
                  data-testid="pickup-forecast-chip" title="Month-end forecast at current pace">
                  Forecast: ~{data.target.forecast_rooms}
                </span>
                <span className={`font-semibold ${data.target.progress_pct >= 100 ? "text-emerald-600" : "text-indigo-600"}`}>{data.target.progress_pct}%</span>
              </span>
            </div>
            <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${data.target.progress_pct >= 100 ? "bg-emerald-500" : "bg-indigo-500"}`}
                style={{ width: `${Math.min(100, data.target.progress_pct)}%` }} />
            </div>
          </div>
        ) : (
          <div className="text-[10px] text-stone-300">No target set for this month</div>
        )}
        {targetHistory.length > 1 && (
          <div className="mt-2" data-testid="pickup-target-history">
            <div className="flex items-end gap-1.5 h-10">
              {(() => {
                const max = Math.max(...targetHistory.map(h => Math.max(h.actual_rooms, h.target_rooms)), 1);
                return targetHistory.map(h => (
                  <div key={h.month} className="flex-1 relative flex flex-col justify-end h-full"
                    title={`${h.month}: ${h.actual_rooms} actual / ${h.target_rooms || "—"} target`}>
                    {h.target_rooms > 0 && (
                      <div className="absolute left-0 right-0 border-t border-dashed border-stone-400"
                        style={{ bottom: `${(h.target_rooms / max) * 100}%` }} />
                    )}
                    <div className={`w-full rounded-t ${h.target_rooms > 0 && h.actual_rooms >= h.target_rooms ? "bg-emerald-400" : "bg-indigo-300"}`}
                      style={{ height: `${Math.max(4, (h.actual_rooms / max) * 100)}%` }} />
                  </div>
                ));
              })()}
            </div>
            <div className="flex justify-between text-[8px] text-stone-300 mt-0.5">
              {targetHistory.map(h => <span key={h.month}>{h.month.slice(5)}</span>)}
            </div>
          </div>
        )}
      </div>

      <button onClick={toggleExpand}
        className="w-full px-4 py-2 border-t border-stone-100 text-[11px] text-stone-500 hover:bg-stone-50 flex items-center justify-center gap-1 font-medium"
        data-testid="pickup-expand-btn">
        {expanded ? <CaretUp size={11} /> : <CaretDown size={11} />}
        {expanded ? "Hide details" : `Show details — sold rooms & channels (${data.recent_bookings?.length || 0})`}
      </button>

      {expanded && channels?.channels?.length > 0 && (
        <div className="border-t border-stone-100 px-4 py-2" data-testid="pickup-channel-trend">
          <div className="text-[9px] text-stone-400 uppercase font-semibold mb-1">Channel pickup — last 4 weeks (rooms/week)</div>
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-stone-400">
                <td className="py-0.5">Channel</td>
                {channels.weeks.map(w => <td key={w} className="text-right" title={`Week of ${w}`}>{w.slice(5)}</td>)}
                <td className="text-right font-semibold">Total</td>
              </tr>
            </thead>
            <tbody>
              {channels.channels.map(c => {
                const trendUp = c.weekly[c.weekly.length - 1] >= c.weekly[0];
                return (
                  <tr key={c.source} className="border-t border-stone-50">
                    <td className="py-1 font-medium text-stone-700 flex items-center gap-1">
                      {trendUp ? <TrendUp size={10} className="text-emerald-500" /> : <TrendDown size={10} className="text-red-400" />}
                      {c.source}
                    </td>
                    {c.weekly.map((v, i) => <td key={i} className="text-right text-stone-500">{v}</td>)}
                    <td className="text-right font-bold text-stone-700">{c.total}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

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
