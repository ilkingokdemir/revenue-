import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Activity, TrendingUp, TrendingDown, BarChart3, RefreshCw, Calendar, Zap, PartyPopper, Eye } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const DEMAND_COLORS = { high: "#ef4444", moderate: "#f59e0b", low: "#22c55e" };
const AI_STATUS = {
  ai: { label: "AI", bg: "bg-violet-500", text: "text-white" },
  event: { label: "EVENT", bg: "bg-red-500", text: "text-white" },
  manual: { label: "MANUAL", bg: "bg-indigo-500", text: "text-white" },
  base: { label: "BASE", bg: "bg-stone-300", text: "text-stone-600" },
};

export const MarketDemandDashboard = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nightsRange, setNightsRange] = useState(365);

  const load = (nights) => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/demand-dashboard?days=${nights}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { toast.error("Failed to load demand data"); setLoading(false); });
  };
  useEffect(() => { load(nightsRange); }, [propertyId, nightsRange]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading market demand for {nightsRange} days...</div>;
  if (!data) return null;

  const { daily_data, kpis } = data;

  // Chart: Show occupancy bars + AI rate dots + min rate line
  const chartW = 1200, chartH = 280, padL = 55, padR = 20, padT = 30, padB = 50;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const barW = Math.max(1, Math.min(8, (innerW / daily_data.length) - 1));
  const maxRate = Math.max(...daily_data.map(d => Math.max(d.sell_rate, d.ai_rate || 0, d.base_rate)), 1);
  const scaleX = (i) => padL + (i / Math.max(daily_data.length - 1, 1)) * innerW;
  const scaleYOcc = (v) => padT + (1 - v / 100) * innerH;
  const scaleYRate = (v) => padT + (1 - v / maxRate) * innerH;

  // Monthly labels for x-axis
  const monthLabels = [];
  let lastMonth = "";
  daily_data.forEach((d, i) => {
    const m = d.month;
    if (m !== lastMonth) { monthLabels.push({ i, label: `${m} ${d.date.slice(0, 4)}` }); lastMonth = m; }
  });

  return (
    <div className="space-y-6" data-testid="market-demand-dashboard">
      {/* Header */}
      <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-stone-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center">
              <Activity className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Market Demand & Rates</h2>
              <p className="text-sm text-white/50">Occupancy, AI rates, events & market demand across {nightsRange} days</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Nights Selector */}
            <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5" data-testid="demand-nights-selector">
              {[30, 60, 90, 180, 365].map(n => (
                <button key={n} onClick={() => setNightsRange(n)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${nightsRange === n ? "bg-cyan-500 text-white" : "text-white/40 hover:text-white/70"}`}
                  data-testid={`demand-nights-${n}`}>{n === 365 ? "1 Year" : `${n} Nights`}
                </button>
              ))}
            </div>
            <button onClick={() => load(nightsRange)} className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-4 py-2 rounded-xl text-sm font-medium">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mt-4">
          {[
            { label: "Days", value: kpis.total_days, color: "text-white" },
            { label: "Avg Occupancy", value: `${kpis.avg_occupancy}%`, color: kpis.avg_occupancy >= 60 ? "text-emerald-300" : "text-amber-300" },
            { label: "Avg Rate", value: cur(kpis.avg_sell_rate), color: "text-white" },
            { label: "Base Rate", value: cur(kpis.base_rate), color: "text-white/60" },
            { label: "High Demand", value: kpis.high_demand_days, color: "text-red-300" },
            { label: "Low Demand", value: kpis.low_demand_days, color: "text-emerald-300" },
            { label: "Event Days", value: kpis.event_days, color: "text-red-300" },
            { label: "AI Managed", value: `${kpis.ai_managed_pct}%`, color: "text-cyan-300" },
          ].map(k => (
            <div key={k.label} className="bg-white/5 rounded-xl p-2.5 text-center">
              <p className={`text-lg font-bold ${k.color}`}>{k.value}</p>
              <p className="text-[9px] text-white/30 uppercase">{k.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* FLOWCAST Chart */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-flowcast">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-bold text-white">FLOWCAST</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-600" />Occupancy</span>
            <span className="flex items-center gap-1"><span className="w-3 h-1.5 rounded bg-cyan-400" />Pickup</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-white" />AI Rate</span>
            <span className="flex items-center gap-1"><span className="w-6 h-0 border-t border-dashed border-red-400" />Min Rate</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: `${Math.max(800, daily_data.length * 4)}px` }}>
            {/* Grid */}
            {[0, 25, 50, 75, 100].map(v => (
              <g key={v}>
                <line x1={padL} x2={chartW - padR} y1={scaleYOcc(v)} y2={scaleYOcc(v)} stroke="#374151" strokeWidth="0.5" />
                <text x={padL - 8} y={scaleYOcc(v) + 4} textAnchor="end" className="text-[8px]" fill="#6b7280">{v}%</text>
              </g>
            ))}

            {/* Month labels */}
            {monthLabels.map(ml => (
              <g key={ml.i}>
                <line x1={scaleX(ml.i)} x2={scaleX(ml.i)} y1={padT} y2={chartH - padB} stroke="#4b5563" strokeWidth="0.5" strokeDasharray="4 4" />
                <text x={scaleX(ml.i)} y={chartH - 15} textAnchor="start" className="text-[9px]" fill="#9ca3af" fontWeight="600">{ml.label}</text>
              </g>
            ))}

            {/* Min rate line */}
            {daily_data.length > 1 && (
              <path d={daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleYRate(d.min_rate)}`).join(" ")}
                fill="none" stroke="#f87171" strokeWidth="1" strokeDasharray="4 3" opacity="0.6" />
            )}

            {/* Occupancy bars */}
            {daily_data.map((d, i) => {
              const x = scaleX(i) - barW / 2;
              const barH = (d.occupancy / 100) * innerH;
              const color = d.event ? "#ef4444" : d.demand_level === "high" ? "#6b7280" : d.demand_level === "moderate" ? "#4b5563" : "#374151";
              return (
                <g key={i}>
                  <rect x={x} y={padT + innerH - barH} width={barW} height={barH} fill={color} rx="1" opacity="0.8" />
                  {/* Pickup indicator (cyan top) */}
                  {d.occupancy > 0 && <rect x={x} y={padT + innerH - barH} width={barW} height={Math.min(3, barH)} fill="#06b6d4" rx="1" />}
                </g>
              );
            })}

            {/* AI Rate dots */}
            {daily_data.map((d, i) => {
              if (!d.ai_rate) return null;
              const dotColor = d.ai_status === "event" ? "#ef4444" : d.ai_status === "ai" ? "#ffffff" : "#9ca3af";
              return <circle key={`r${i}`} cx={scaleX(i)} cy={scaleYRate(d.ai_rate)} r={daily_data.length > 180 ? 1.5 : 2.5} fill={dotColor} opacity="0.9" />;
            })}
          </svg>
        </div>
      </div>

      {/* Rate Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl overflow-hidden" data-testid="demand-rate-table">
        <div className="px-5 py-3 border-b border-stone-700 flex items-center justify-between">
          <span className="font-bold text-white text-sm">Rate Grid — {nightsRange} Nights</span>
          <div className="flex items-center gap-3 text-[9px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-400" /> ADR</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /> Occupancy</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" /> Min Rate</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-400" /> Floor Rate</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400" /> Sell Rate</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-pink-400" /> Target Rate</span>
          </div>
        </div>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-stone-800 z-10">
              <tr className="border-b border-stone-700">
                {["Date", "Day", "AI Status", "ADR", "Occupancy", "Min Rate", "Floor Rate", "Sell Rate", "Target Rate", "Market", "Event"].map(h => (
                  <th key={h} className="px-2 py-2 text-[10px] font-semibold text-stone-400 text-center whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {daily_data.slice(0, nightsRange).map((d, i) => {
                const ais = AI_STATUS[d.ai_status] || AI_STATUS.base;
                return (
                  <tr key={d.date} className={`border-b border-stone-800/50 ${d.event ? "bg-red-900/10" : i % 2 === 0 ? "bg-stone-900" : "bg-stone-800/30"}`}>
                    <td className="px-2 py-1.5 text-stone-300 text-xs whitespace-nowrap font-medium">
                      {new Date(d.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}
                    </td>
                    <td className="px-2 py-1.5 text-center text-stone-500 text-xs">{d.dow}</td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${ais.bg} ${ais.text}`}>{ais.label}</span>
                    </td>
                    <td className="px-2 py-1.5 text-center text-cyan-400 font-bold text-xs">{cur(d.sell_rate)}</td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`text-xs font-semibold ${d.occupancy >= 70 ? "text-emerald-400" : d.occupancy >= 40 ? "text-amber-400" : "text-red-400"}`}>{d.occupancy}%</span>
                    </td>
                    <td className="px-2 py-1.5 text-center text-red-400 text-xs">{cur(d.min_rate)}</td>
                    <td className="px-2 py-1.5 text-center text-violet-400 text-xs">{cur(d.floor_rate)}</td>
                    <td className="px-2 py-1.5 text-center text-emerald-400 font-bold text-xs">{cur(d.sell_rate)}</td>
                    <td className="px-2 py-1.5 text-center text-pink-400 text-xs">{cur(d.target_rate)}</td>
                    <td className="px-2 py-1.5 text-center">
                      {d.market_unavail !== null && d.market_unavail !== undefined ? (
                        <span className={`text-[10px] font-bold ${d.demand_level === "high" ? "text-red-400" : d.demand_level === "moderate" ? "text-amber-400" : "text-emerald-400"}`}>{d.market_unavail}%</span>
                      ) : <span className="text-stone-600">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      {d.event ? (
                        <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${d.event_impact === "mega" ? "bg-red-500 text-white" : d.event_impact === "large" ? "bg-orange-500 text-white" : "bg-amber-400 text-white"}`}
                          title={d.event}>{d.event_impact?.toUpperCase()}</span>
                      ) : <span className="text-stone-700">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
