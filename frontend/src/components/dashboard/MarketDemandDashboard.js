import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Activity, TrendingUp, TrendingDown, BarChart3, RefreshCw, Calendar, Zap, PartyPopper, Eye, ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const AI_STATUS = {
  ai: { label: "AI", bg: "bg-violet-500", text: "text-white" },
  event: { label: "EVENT", bg: "bg-red-500", text: "text-white" },
  manual: { label: "MANUAL", bg: "bg-indigo-500", text: "text-white" },
  base: { label: "BASE", bg: "bg-stone-600", text: "text-stone-300" },
};

export const MarketDemandDashboard = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nightsRange, setNightsRange] = useState(365);

  const load = (nights) => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/demand-dashboard?days=${nights}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setLoading(false); });
  };
  useEffect(() => { load(nightsRange); }, [propertyId, nightsRange]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading {nightsRange}-day market data...</div>;
  if (!data) return null;

  const { daily_data, kpis } = data;

  // === COMPETITIVE POSITION CHART ===
  const chartW = 1200, chartH = 320, padL = 60, padR = 20, padT = 35, padB = 55;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const hasComp = daily_data.some(d => d.comp_avg);

  // Rate range for chart
  const allRates = daily_data.flatMap(d => [d.sell_rate, d.comp_avg, d.base_rate, d.floor_rate].filter(Boolean));
  const maxRate = Math.max(...allRates, 1) * 1.1;
  const minRate = Math.min(...allRates) * 0.9;
  const scaleX = (i) => padL + (i / Math.max(daily_data.length - 1, 1)) * innerW;
  const scaleY = (v) => padT + (1 - (v - minRate) / (maxRate - minRate)) * innerH;

  // Monthly labels
  const monthLabels = [];
  let lastMonth = "";
  daily_data.forEach((d, i) => {
    if (d.month !== lastMonth) { monthLabels.push({ i, label: `${d.month}` }); lastMonth = d.month; }
  });

  // Build SVG lines
  const sellLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.sell_rate)}`).join(" ");
  const baseLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.base_rate)}`).join(" ");
  const floorLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.floor_rate)}`).join(" ");

  // Competitor line (skip gaps)
  const compSegments = [];
  let seg = [];
  daily_data.forEach((d, i) => {
    if (d.comp_avg) { seg.push({ i, y: d.comp_avg }); }
    else if (seg.length > 1) { compSegments.push([...seg]); seg = []; }
    else { seg = []; }
  });
  if (seg.length > 1) compSegments.push(seg);

  // Fill area between sell and comp (above = green, below = red)
  const aboveFill = [];
  const belowFill = [];
  daily_data.forEach((d, i) => {
    if (d.comp_avg) {
      if (d.sell_rate >= d.comp_avg) {
        aboveFill.push({ i, top: d.sell_rate, bot: d.comp_avg });
      } else {
        belowFill.push({ i, top: d.comp_avg, bot: d.sell_rate });
      }
    }
  });

  return (
    <div className="space-y-5" data-testid="market-demand-dashboard">
      {/* Header */}
      <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-stone-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center">
              <Activity className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Market Position & Demand</h2>
              <p className="text-sm text-white/50">Your rates vs market | Demand landscape | {nightsRange} days</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5" data-testid="demand-nights-selector">
              {[30, 60, 90, 180, 365].map(n => (
                <button key={n} onClick={() => setNightsRange(n)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${nightsRange === n ? "bg-cyan-500 text-white" : "text-white/40 hover:text-white/70"}`}
                  data-testid={`demand-nights-${n}`}>{n === 365 ? "1 Year" : `${n}N`}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Position KPIs */}
        <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-12 gap-2 mt-4">
          {[
            { l: "Our Avg Rate", v: cur(kpis.avg_sell_rate), c: "text-cyan-300" },
            { l: "Comp Avg Rate", v: kpis.avg_competitor_rate ? cur(kpis.avg_competitor_rate) : "—", c: "text-amber-300" },
            { l: "Position", v: `${kpis.avg_position_pct > 0 ? "+" : ""}${kpis.avg_position_pct}%`, c: kpis.avg_position_pct > 0 ? "text-emerald-300" : kpis.avg_position_pct < 0 ? "text-red-300" : "text-white" },
            { l: "Above Market", v: kpis.above_market_days, c: "text-emerald-300" },
            { l: "Below Market", v: kpis.below_market_days, c: "text-red-300" },
            { l: "Aligned", v: kpis.aligned_days, c: "text-white" },
            { l: "Avg Occupancy", v: `${kpis.avg_occupancy}%`, c: kpis.avg_occupancy >= 60 ? "text-emerald-300" : "text-amber-300" },
            { l: "High Demand", v: kpis.high_demand_days, c: "text-red-300" },
            { l: "Low Demand", v: kpis.low_demand_days, c: "text-emerald-300" },
            { l: "Event Days", v: kpis.event_days, c: "text-red-300" },
            { l: "AI Managed", v: `${kpis.ai_managed_pct}%`, c: "text-cyan-300" },
            { l: "Days", v: kpis.total_days, c: "text-white" },
          ].map(k => (
            <div key={k.l} className="bg-white/5 rounded-lg p-2 text-center">
              <p className={`text-sm font-bold ${k.c}`}>{k.v}</p>
              <p className="text-[8px] text-white/30 uppercase leading-tight">{k.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* COMPETITIVE LANDSCAPE CHART */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-landscape-chart">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-sm font-bold text-white">COMPETITIVE LANDSCAPE</span>
            <Badge className="bg-white/10 text-white/50 text-[9px]">{nightsRange} days</Badge>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-cyan-400 inline-block" /> Our Rate</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-amber-400 inline-block" /> Competitor Avg</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-stone-500 inline-block border-dashed" /> Base Rate</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-red-400/50 inline-block border-dashed" /> Floor</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/20 inline-block" /> Above</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/20 inline-block" /> Below</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: `${Math.max(800, daily_data.length * 3)}px` }}>
            {/* Y-axis grid */}
            {[0, 0.25, 0.5, 0.75, 1].map(frac => {
              const y = padT + (1 - frac) * innerH;
              const val = Math.round(minRate + frac * (maxRate - minRate));
              return (
                <g key={frac}>
                  <line x1={padL} x2={chartW - padR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" />
                  <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[8px]" fill="#6b7280">{cur(val)}</text>
                </g>
              );
            })}

            {/* Month labels */}
            {monthLabels.map(ml => (
              <g key={ml.i}>
                <line x1={scaleX(ml.i)} x2={scaleX(ml.i)} y1={padT} y2={chartH - padB} stroke="#4b5563" strokeWidth="0.5" strokeDasharray="4 4" />
                <text x={scaleX(ml.i) + 4} y={chartH - 18} textAnchor="start" className="text-[10px]" fill="#9ca3af" fontWeight="600">{ml.label}</text>
              </g>
            ))}

            {/* Above market fill (green) */}
            {aboveFill.map((af, idx) => (
              <rect key={`a${idx}`} x={scaleX(af.i) - 2} y={scaleY(af.top)} width={4} height={scaleY(af.bot) - scaleY(af.top)} fill="#22c55e" opacity="0.15" />
            ))}

            {/* Below market fill (red) */}
            {belowFill.map((bf, idx) => (
              <rect key={`b${idx}`} x={scaleX(bf.i) - 2} y={scaleY(bf.top)} width={4} height={scaleY(bf.bot) - scaleY(bf.top)} fill="#ef4444" opacity="0.15" />
            ))}

            {/* Floor rate line */}
            <path d={floorLine} fill="none" stroke="#f87171" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />

            {/* Base rate line */}
            <path d={baseLine} fill="none" stroke="#6b7280" strokeWidth="1" strokeDasharray="5 5" opacity="0.5" />

            {/* Competitor lines */}
            {compSegments.map((seg, si) => (
              <path key={`c${si}`} d={seg.map((pt, j) => `${j === 0 ? "M" : "L"} ${scaleX(pt.i)} ${scaleY(pt.y)}`).join(" ")}
                fill="none" stroke="#f59e0b" strokeWidth="2" opacity="0.8" />
            ))}

            {/* Our sell rate line */}
            <path d={sellLine} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinejoin="round" />

            {/* Event markers */}
            {daily_data.map((d, i) => {
              if (!d.event) return null;
              return <circle key={`ev${i}`} cx={scaleX(i)} cy={scaleY(d.sell_rate)} r="4" fill="#ef4444" stroke="#000" strokeWidth="1" />;
            })}

            {/* Rate labels on key points (every ~30 days) */}
            {daily_data.filter((_, i) => i % Math.max(Math.floor(daily_data.length / 12), 1) === 0).map((d, idx) => {
              const i = daily_data.indexOf(d);
              return (
                <g key={`lbl${idx}`}>
                  <text x={scaleX(i)} y={scaleY(d.sell_rate) - 8} textAnchor="middle" className="text-[7px]" fill="#06b6d4" fontWeight="600">{cur(d.sell_rate)}</text>
                  {d.comp_avg && <text x={scaleX(i)} y={scaleY(d.comp_avg) + 14} textAnchor="middle" className="text-[7px]" fill="#f59e0b">{cur(d.comp_avg)}</text>}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* DEMAND HEATMAP — Market Unavailability across year */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-heatmap">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-stone-400" /> MARKET DEMAND HEATMAP
          </span>
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" />High (&gt;70%)</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500" />Moderate</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" />Low (&lt;30%)</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-700" />No Data</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-[2px]">
          {daily_data.map((d, i) => {
            const mu = d.market_unavail;
            const color = mu === null || mu === undefined ? "#374151" : mu >= 70 ? "#ef4444" : mu >= 40 ? "#f59e0b" : "#22c55e";
            const opacity = mu === null || mu === undefined ? 0.3 : 0.7 + (mu / 100) * 0.3;
            return (
              <div key={i} className="group relative"
                style={{ width: `${Math.max(3, Math.min(10, 700 / daily_data.length))}px`, height: "20px", backgroundColor: color, opacity, borderRadius: "1px" }}
                title={`${d.date} (${d.dow}) | Market: ${mu ?? "—"}% | Demand: ${d.demand_level}${d.event ? ` | Event: ${d.event}` : ""}`}>
                {d.event && <div className="absolute -top-1 left-0 right-0 h-1 bg-red-300 rounded-full" />}
              </div>
            );
          })}
        </div>
        <div className="flex items-center justify-between mt-2 text-[9px] text-stone-500">
          <span>{daily_data[0]?.date}</span>
          <span>{daily_data[Math.floor(daily_data.length / 2)]?.date}</span>
          <span>{daily_data[daily_data.length - 1]?.date}</span>
        </div>
      </div>

      {/* Rate Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl overflow-hidden" data-testid="demand-rate-table">
        <div className="px-5 py-3 border-b border-stone-700 flex items-center justify-between">
          <span className="font-bold text-white text-sm">Rate Grid — {nightsRange} Nights</span>
          <div className="flex items-center gap-3 text-[9px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-400" />Our Rate</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" />Competitor</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-400" />Above</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" />Below</span>
          </div>
        </div>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-stone-800 z-10">
              <tr className="border-b border-stone-700">
                {["Date", "Day", "Status", "Our Rate", "Comp Avg", "Position", "Occ %", "Market", "Floor", "Event"].map(h => (
                  <th key={h} className="px-2 py-2 text-[10px] font-semibold text-stone-400 text-center whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {daily_data.map((d, i) => {
                const ais = AI_STATUS[d.ai_status] || AI_STATUS.base;
                return (
                  <tr key={d.date} className={`border-b border-stone-800/50 ${d.event ? "bg-red-900/10" : d.position === "below" ? "bg-red-900/5" : d.position === "above" ? "bg-emerald-900/5" : i % 2 === 0 ? "bg-stone-900" : "bg-stone-800/30"}`}>
                    <td className="px-2 py-1.5 text-stone-300 text-xs whitespace-nowrap font-medium">
                      {new Date(d.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}
                    </td>
                    <td className="px-2 py-1.5 text-center text-stone-500 text-xs">{d.dow}</td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${ais.bg} ${ais.text}`}>{ais.label}</span>
                    </td>
                    <td className="px-2 py-1.5 text-center text-cyan-400 font-bold text-xs">{cur(d.sell_rate)}</td>
                    <td className="px-2 py-1.5 text-center text-amber-400 text-xs">{d.comp_avg ? cur(d.comp_avg) : <span className="text-stone-600">—</span>}</td>
                    <td className="px-2 py-1.5 text-center">
                      {d.position ? (
                        <span className={`flex items-center justify-center gap-0.5 text-[10px] font-bold ${d.position === "above" ? "text-emerald-400" : d.position === "below" ? "text-red-400" : "text-stone-400"}`}>
                          {d.position === "above" ? <ArrowUpRight className="w-3 h-3" /> : d.position === "below" ? <ArrowDownRight className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                          {d.position_pct > 0 ? "+" : ""}{d.position_pct}%
                        </span>
                      ) : <span className="text-stone-700">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      <span className={`text-xs font-semibold ${d.occupancy >= 70 ? "text-emerald-400" : d.occupancy >= 40 ? "text-amber-400" : "text-red-400"}`}>{d.occupancy}%</span>
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      {d.market_unavail !== null && d.market_unavail !== undefined ? (
                        <span className={`text-[10px] font-bold ${d.demand_level === "high" ? "text-red-400" : d.demand_level === "moderate" ? "text-amber-400" : "text-emerald-400"}`}>{d.market_unavail}%</span>
                      ) : <span className="text-stone-600">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-center text-violet-400 text-xs">{cur(d.floor_rate)}</td>
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
