import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Zap, AlertTriangle, CheckCircle, RefreshCw, ArrowUpRight, ArrowDownRight, Minus, Activity } from "lucide-react";
import useLivePolling, { LiveBadge } from "../../hooks/useLivePolling";
import ChartLegend from "./ChartLegend";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const BookingPace = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const load = useCallback((d) => {
    setLoading(true);
    axios.get(`${API}/revenue/intelligence/${propertyId}/booking-pace?days=${d}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId]);
  useEffect(() => { load(days); }, [load, days]);
  // ⚡ Live refresh: fresh bookings flip the chart without reload
  useLivePolling(() => load(days), { intervalMs: 60000 });

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Analyzing booking pace...</div>;
  if (!data) return null;

  const { daily_pace, kpis, alerts } = data;
  const paceColor = kpis.pace_status === "ahead" ? "text-emerald-400" : kpis.pace_status === "behind" ? "text-red-400" : "text-white";

  // Chart
  const cW = 900, cH = 220, pL = 50, pR = 10, pT = 20, pB = 35;
  const iW = cW - pL - pR, iH = cH - pT - pB;
  const maxB = Math.max(...daily_pace.flatMap(d => [d.this_year.bookings, d.last_year.bookings]), 1);
  const sx = (i) => pL + (i / Math.max(daily_pace.length - 1, 1)) * iW;
  const sy = (v) => pT + (1 - v / maxB) * iH;
  const tyLine = daily_pace.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.this_year.bookings)}`).join(" ");
  const lyLine = daily_pace.map((d, i) => `${i === 0 ? "M" : "L"} ${sx(i)} ${sy(d.last_year.bookings)}`).join(" ");

  return (
    <div className="space-y-5" data-testid="booking-pace">
      <div className="bg-gradient-to-r from-indigo-900 via-blue-900 to-indigo-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Activity className="w-5 h-5 text-blue-300" /></div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2">
                Booking Pace & Pickup Velocity
                <LiveBadge seconds={60} color="cyan" />
              </h2>
              <p className="text-xs text-white/40">How fast bookings come in vs last year · auto-updates</p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5">
            {[7, 14, 30, 60, 90].map(d => (
              <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${days === d ? "bg-blue-500 text-white" : "text-white/35 hover:text-white/70"}`} data-testid={`pace-days-${d}`}>{d}d</button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-lg font-bold text-cyan-300">{kpis.total_this_year}</p><p className="text-[8px] text-white/30">This Year</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-lg font-bold text-stone-400">{kpis.total_last_year}</p><p className="text-[8px] text-white/30">Last Year</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className={`text-lg font-bold ${paceColor}`}>{kpis.diff > 0 ? "+" : ""}{kpis.diff} ({kpis.diff_pct > 0 ? "+" : ""}{kpis.diff_pct}%)</p><p className="text-[8px] text-white/30">Difference</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-lg font-bold text-amber-300">{kpis.pickup_24h}</p><p className="text-[8px] text-white/30">24h Pickup</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className={`text-lg font-bold ${kpis.velocity_change_pct >= 0 ? "text-emerald-300" : "text-red-300"}`}>{kpis.velocity_change_pct > 0 ? "+" : ""}{kpis.velocity_change_pct}%</p><p className="text-[8px] text-white/30">Velocity Change</p></div>
        </div>
      </div>

      {/* Alerts */}
      {alerts?.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className={`flex items-center gap-3 rounded-xl p-3 border ${a.type === "positive" ? "bg-emerald-50 border-emerald-200" : a.type === "warning" ? "bg-amber-50 border-amber-200" : "bg-blue-50 border-blue-200"}`}>
              {a.type === "positive" ? <TrendingUp className="w-5 h-5 text-emerald-600 flex-shrink-0" /> : a.type === "warning" ? <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0" /> : <CheckCircle className="w-5 h-5 text-blue-600 flex-shrink-0" />}
              <p className="text-sm text-stone-700 font-medium">{a.message}</p>
            </div>
          ))}
        </div>
      )}

      {/* Chart */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5">
        <ChartLegend
          testId="bookingpace-legend"
          items={[
            { color: "#06b6d4", label: "Bu Yıl (TY) — kümülatif rezv.", kind: "line", testId: "legend-bp-ty" },
            { color: "#6b7280", label: "Geçen Yıl (LY)", kind: "dashed", testId: "legend-bp-ly" },
          ]}
        />
        <div className="overflow-x-auto mt-3">
          <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: "600px" }}>
            {[0, 0.25, 0.5, 0.75, 1].map(f => { const y = pT + (1 - f) * iH; return <g key={f}><line x1={pL} x2={cW - pR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" /><text x={pL - 5} y={y + 4} textAnchor="end" className="text-[7px]" fill="#6b7280">{Math.round(maxB * f)}</text></g>; })}
            <path d={lyLine} fill="none" stroke="#6b7280" strokeWidth="1.5" strokeDasharray="4 4" />
            <path d={tyLine} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinejoin="round" />
            {daily_pace.filter((_, i) => i % Math.max(Math.floor(daily_pace.length / 10), 1) === 0).map(d => { const i = daily_pace.indexOf(d); return <text key={i} x={sx(i)} y={cH - 10} textAnchor="middle" className="text-[8px]" fill="#6b7280">{d.dow} {d.date.slice(8)}</text>; })}
          </svg>
        </div>
      </div>
    </div>
  );
};
