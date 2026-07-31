/**
 * Nightly Recap — "What happened last night?" digest. Pairs with the existing
 * Morning Brief (which is forward-looking) by giving owners + revenue managers
 * a 9 AM look-back at last night's KPIs vs same night last year.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Moon, RefreshCw, ArrowUp, ArrowDown, Minus, Sparkles, BedDouble,
  TrendingUp, DoorOpen, DoorClosed, AlertCircle, UserPlus,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

function deltaClass(v, inverted = false) {
  if (v == null || v === 0) return { color: "text-stone-400", icon: Minus };
  const positive = v > 0;
  const isGood = inverted ? !positive : positive;
  return {
    color: isGood ? "text-emerald-300" : "text-rose-300",
    icon: positive ? ArrowUp : ArrowDown,
  };
}

export default function NightlyRecapPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [date, setDate] = useState("");

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = `${API}/nightly-recap/${propertyId}${date ? `?date_str=${date}&yoy=true` : "?yoy=true"}`;
      const { data } = await axios.get(url);
      setData(data);
    } catch { toast.error("Failed to load recap"); }
    setLoading(false);
  }, [propertyId, date]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); }, [propertyId]);

  if (loading && !data) return (
    <div className="p-5 space-y-5" data-testid="recap-skeleton">
      <div className="h-28 rounded-2xl bg-stone-200 animate-pulse" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map(i => <div key={i} className="h-24 rounded-2xl bg-stone-200 animate-pulse" />)}
      </div>
      <div className="h-20 rounded-2xl bg-stone-200 animate-pulse" />
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[0, 1, 2, 3, 4].map(i => <div key={i} className="h-16 rounded-2xl bg-stone-200 animate-pulse" />)}
      </div>
      <p className="text-xs text-stone-400 text-center">Gece özeti ve AI yorumu hazırlanıyor…</p>
    </div>
  );

  const yoy = data?.yoy;
  const occDelta = yoy?.occ_delta_pp;
  const revDelta = yoy?.rev_delta_pct;
  const adrDelta = yoy?.adr_delta_pct;

  const targetDateLbl = data?.date ? new Date(data.date).toLocaleDateString("en", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "—";

  return (
    <div className="p-5 space-y-5" data-testid="nightly-recap-panel">
      {/* Header */}
      <div className="bg-stone-950 border border-indigo-500/30 rounded-2xl p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-indigo-300">
              <Moon className="w-4 h-4" />Nightly Recap
            </div>
            <h1 className="text-3xl font-black text-stone-100 mt-1">{targetDateLbl}</h1>
            <p className="text-sm text-stone-300 mt-1">{hotelName ? `${hotelName} · ` : ""}What happened last night</p>
          </div>
          <div className="flex items-center gap-2">
            <input type="date" value={date} onChange={e => setDate(e.target.value)}
              className="bg-white/10 border border-white/20 text-white text-xs rounded-lg px-2 py-1.5"
              data-testid="recap-date-picker" />
            <button onClick={load} disabled={loading} data-testid="recap-refresh"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs font-bold">
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
            </button>
          </div>
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="recap-kpis">
        <Kpi label="Occupancy"  value={`${data?.occupancy_pct ?? 0}%`}     sub={`${data?.rooms_sold ?? 0}/${data?.total_rooms ?? 0} rooms`} delta={occDelta != null ? `${occDelta > 0 ? "+" : ""}${occDelta}pp` : null} deltaSign={occDelta} />
        <Kpi label="Revenue"     value={cur(data?.revenue ?? 0)}              sub="Last night"                                                  delta={revDelta != null ? `${revDelta > 0 ? "+" : ""}${revDelta}%` : null} deltaSign={revDelta} />
        <Kpi label="ADR"         value={cur(data?.adr ?? 0)}                  sub="Avg daily rate"                                              delta={adrDelta != null ? `${adrDelta > 0 ? "+" : ""}${adrDelta}%` : null} deltaSign={adrDelta} />
        <Kpi label="RevPAR"      value={cur(data?.revpar ?? 0)}               sub="Revenue / room"                                              delta={null} />
      </div>

      {/* AI commentary */}
      {data?.commentary && (
        <div className="bg-stone-950 border border-violet-500/30 rounded-2xl p-4" data-testid="recap-commentary">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-violet-300 font-bold mb-2">
            <Sparkles className="w-3 h-3" />AI commentary (GPT-5.2)
          </div>
          <p className="text-sm text-stone-100 leading-relaxed">{data.commentary}</p>
        </div>
      )}

      {/* Movements */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="recap-movements">
        <Tile icon={DoorOpen}   label="Arrivals"      value={data?.arrivals ?? 0}      color="text-cyan-300" />
        <Tile icon={DoorClosed} label="Departures"    value={data?.departures ?? 0}    color="text-amber-300" />
        <Tile icon={UserPlus}   label="Walk-ins"      value={data?.walk_ins ?? 0}      color="text-emerald-300" />
        <Tile icon={AlertCircle} label="No-shows"     value={data?.no_shows ?? 0}      color="text-rose-300" />
        <Tile icon={AlertCircle} label="Cancelled"    value={data?.cancellations ?? 0} color="text-rose-300" />
      </div>

      {/* Top room types */}
      {data?.top_rooms?.length > 0 && (
        <div className="bg-stone-950 border border-stone-800 rounded-2xl p-4" data-testid="recap-top-rooms">
          <h3 className="text-sm font-bold text-stone-100 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />Top performing room types
          </h3>
          <table className="w-full text-xs">
            <thead><tr className="text-stone-400 border-b border-stone-800">
              <th className="text-left py-1.5 px-2">Room type</th>
              <th className="text-right py-1.5 px-2">Sold</th>
              <th className="text-right py-1.5 px-2">Revenue</th>
            </tr></thead>
            <tbody>
              {data.top_rooms.map((r, i) => (
                <tr key={i} className="border-b border-stone-800/50">
                  <td className="py-1.5 px-2 font-bold text-stone-200">{r.room_type}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-stone-300">{r.rooms_sold}</td>
                  <td className="py-1.5 px-2 text-right tabular-nums text-emerald-300 font-bold">{cur(r.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* YoY block */}
      {yoy && (
        <div className="bg-stone-950 border border-stone-800 rounded-2xl p-4" data-testid="recap-yoy">
          <h3 className="text-sm font-bold text-stone-100 mb-3">vs Same night last year — {new Date(yoy.date).toLocaleDateString("en", { day: "numeric", month: "short", year: "numeric" })}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <YoyRow label="Occupancy" cur={`${data.occupancy_pct}%`}  ly={`${yoy.occupancy_pct}%`} delta={occDelta} suffix="pp" />
            <YoyRow label="Revenue"   cur={cur(data.revenue)}          ly={cur(yoy.revenue)}        delta={revDelta} suffix="%" />
            <YoyRow label="ADR"       cur={cur(data.adr)}              ly={cur(yoy.adr)}            delta={adrDelta} suffix="%" />
            <YoyRow label="Rooms sold" cur={data.rooms_sold}           ly={yoy.rooms_sold}          delta={data.rooms_sold - yoy.rooms_sold} suffix="" />
          </div>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, sub, delta, deltaSign }) {
  const dc = delta != null ? deltaClass(deltaSign) : null;
  const DI = dc?.icon;
  return (
    <div className="bg-stone-950 border border-stone-800 rounded-2xl p-4">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</div>
      <div className="text-3xl font-black text-stone-100 tabular-nums">{value}</div>
      <div className="flex items-center justify-between text-[10px] mt-1">
        <span className="text-stone-500">{sub}</span>
        {delta && DI && <span className={`flex items-center gap-0.5 font-bold ${dc.color}`}><DI className="w-3 h-3" />{delta}</span>}
      </div>
    </div>
  );
}

function Tile({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-stone-950 border border-stone-800 rounded-2xl p-3">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
        <Icon className="w-3 h-3" />{label}
      </div>
      <div className={`text-2xl font-black tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function YoyRow({ label, cur, ly, delta, suffix }) {
  const dc = delta != null ? deltaClass(delta) : null;
  const DI = dc?.icon;
  return (
    <div className="bg-stone-800 rounded-xl p-3">
      <div className="text-[9px] uppercase tracking-widest text-stone-500 font-bold mb-0.5">{label}</div>
      <div className="text-base font-black text-stone-200 tabular-nums">{cur}</div>
      <div className="flex items-center justify-between text-[10px] mt-0.5">
        <span className="text-stone-500">LY: {ly}</span>
        {delta != null && DI && <span className={`flex items-center gap-0.5 font-bold ${dc.color}`}>
          <DI className="w-3 h-3" />{delta > 0 ? "+" : ""}{Math.abs(delta).toFixed(1)}{suffix}
        </span>}
      </div>
    </div>
  );
}
