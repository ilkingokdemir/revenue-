import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Radar, TrendingUp, TrendingDown, AlertTriangle, Zap, RefreshCw, Calendar, BarChart3, Activity } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const INSIGHT_ICONS = { trending: TrendingUp, compress: Zap, low: AlertTriangle, event: Calendar };
const INSIGHT_COLORS = { opportunity: "border-emerald-500/30 bg-emerald-900/20", warning: "border-amber-500/30 bg-amber-900/20", event: "border-red-500/30 bg-red-900/20" };
const DOT_COLORS = { underpriced: "#22c55e", overpriced: "#ef4444", peak: "#f59e0b", fair: "#06b6d4" };

export const DemandRadar = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [behavior, setBehavior] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(90);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      axios.get(`${API}/revenue/demand-radar/${propertyId}?days=${days}`),
      axios.get(`${API}/revenue/demand-radar/${propertyId}/booking-behavior`),
    ]).then(([r1, r2]) => { setData(r1.data); setBehavior(r2.data); setLoading(false); }).catch(() => setLoading(false));
  }, [propertyId, days]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Demand Radar...</div>;
  if (!data) return null;

  const { status, status_text, demand_change_pp, wap_change, kpis, insights, daily, pickup_change, opportunity_map, supply_dynamics } = data;
  const statusColor = status === "rising" ? "text-emerald-400" : status === "falling" ? "text-red-400" : "text-amber-400";

  // Demand chart
  const demandDays = daily.filter(d => d.demand !== null);
  const cW = 1100, cH = 240, pL = 60, pR = 10, pT = 50, pB = 30;
  const iW = cW - pL - pR, iH = cH - pT - pB;
  const barW = Math.max(2, Math.min(10, (iW / Math.max(demandDays.length, 1)) - 1));
  const sx = (i) => pL + (i / Math.max(demandDays.length - 1, 1)) * iW;
  const sy = (v) => pT + (1 - v / 100) * iH;

  // Event labels
  const eventDays = demandDays.filter(d => d.event).map(d => ({ i: demandDays.indexOf(d), name: d.event, impact: d.event_impact }));

  // 7d trend line
  const trendLine = demandDays.map((d, i) => {
    const window = demandDays.slice(Math.max(0, i - 3), i + 4);
    const avg = window.reduce((s, w) => s + (w.demand || 0), 0) / window.length;
    return { x: sx(i), y: sy(avg) };
  });
  const trendPath = trendLine.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  // Opportunity map dimensions
  const omW = 1100, omH = 320, omPL = 50, omPR = 30, omPT = 20, omPB = 50;
  const omIW = omW - omPL - omPR, omIH = omH - omPT - omPB;
  const omMaxP = Math.max(...opportunity_map.map(o => o.price), 1) * 1.1;
  const omMinP = Math.min(...opportunity_map.map(o => o.price)) * 0.9;
  const omSX = (d) => omPL + (d / 100) * omIW;
  const omSY = (p) => omPT + (1 - (p - omMinP) / (omMaxP - omMinP)) * omIH;

  return (
    <div className="space-y-5" data-testid="demand-radar">
      {/* Header */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Radar className="w-5 h-5 text-amber-400" /></div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2">Demand Radar <Badge className="bg-amber-500/20 text-amber-300 text-[9px]">v2</Badge></h2>
              <p className="text-xs text-white/40">{days}-day forward market intelligence • Live data</p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5">
            {[30, 60, 90, 180, 365].map(d => (
              <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${days === d ? "bg-amber-500 text-white" : "text-white/35 hover:text-white/70"}`}>{d === 365 ? "1yr" : `${d}d`}</button>
            ))}
          </div>
        </div>

        {/* Status Banner */}
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className={`w-3 h-3 rounded-full ${status === "stable" ? "bg-amber-400" : status === "rising" ? "bg-emerald-400" : "bg-red-400"}`} />
            <span className={`font-bold ${statusColor}`}>{status_text}</span>
            <span className="text-xs text-white/30">Based on {kpis.total_days} days of forward data</span>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right"><p className={`text-lg font-bold ${demand_change_pp >= 0 ? "text-emerald-400" : "text-red-400"}`}>{demand_change_pp > 0 ? "+" : ""}{demand_change_pp}pp</p><p className="text-[9px] text-white/30">demand vs 30d ago</p></div>
            <div className="text-right"><p className={`text-lg font-bold ${wap_change >= 0 ? "text-emerald-400" : "text-red-400"}`}>{wap_change >= 0 ? "+" : ""}{cur(wap_change)}</p><p className="text-[9px] text-white/30">avg rate vs 30d ago</p></div>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-6 gap-3">
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">Avg Demand</p><p className="text-xl font-bold text-emerald-400">{kpis.avg_demand ?? "—"}%</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">Avg WAP</p><p className="text-xl font-bold text-white">{cur(kpis.avg_wap)}</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">Avg Supply</p><p className="text-xl font-bold text-cyan-400">{kpis.avg_supply?.toLocaleString() ?? "—"}</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">High Demand Days</p><p className="text-xl font-bold text-red-400">{kpis.high_demand_days}</p><p className="text-[9px] text-white/20">of {days} above 70%</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">Peak Date</p><p className="text-lg font-bold text-red-400">{kpis.peak_date ? new Date(kpis.peak_date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" }) : "—"}</p><p className="text-[9px] text-white/20">{kpis.peak_demand}% - {cur(kpis.peak_wap)}</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-[8px] text-white/30 uppercase">Quietest Date</p><p className="text-lg font-bold text-emerald-400">{kpis.quietest_date ? new Date(kpis.quietest_date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" }) : "—"}</p><p className="text-[9px] text-white/20">{kpis.quietest_demand}% - {cur(kpis.quietest_wap)}</p></div>
        </div>
      </div>

      {/* Smart Insights */}
      {insights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {insights.slice(0, 3).map((ins, i) => {
            const Icon = INSIGHT_ICONS[ins.icon] || Zap;
            return (
              <div key={i} className={`bg-stone-900 border rounded-xl p-4 ${INSIGHT_COLORS[ins.type] || "border-stone-700"}`}>
                <div className="flex items-center gap-2 mb-1"><Icon className="w-4 h-4 text-emerald-400" /><span className="text-sm font-bold text-white">{ins.title}</span></div>
                <p className="text-[11px] text-stone-400">{ins.desc}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* Demand Chart — How Busy Is the Market? */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-chart">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-2">
          <div>
            <p className="text-[10px] text-stone-500 uppercase">{days}-Day Forward View</p>
            <h3 className="text-sm font-bold text-white">How Busy Is the Market?</h3>
            <p className="text-[10px] text-stone-500">Market demand score — higher means busier, fewer rooms available</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-emerald-500" /> Pazar Talep</span>
            <span className="flex items-center gap-1.5 pl-3 border-l border-stone-700">
              <span className="w-3 h-[2px] bg-cyan-400" />
              <span className="text-cyan-200 font-semibold">BİZ · Doluluk</span>
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-teal-500" /> Demand</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0 border-t border-dashed border-teal-300" /> 7d trend</span>
          </div>
        </div>
        <div className="relative overflow-x-auto">
          {/* Y-axis labels as HTML (more reliable than SVG text for Tailwind projects) */}
          <div className="absolute left-0 top-0 bottom-0 w-12 pointer-events-none z-10" style={{ minHeight: "100%" }}>
            {[100, 75, 50, 25, 0].map(v => (
              <div key={v}
                className="absolute right-1 text-[11px] md:text-xs font-bold text-stone-200 tabular-nums"
                style={{ top: `calc(${((100 - v) / 100) * (240 - 50 - 30) / 240 * 100}% + ${50 / 240 * 100}% - 8px)`, lineHeight: 1 }}>
                {v}%
              </div>
            ))}
          </div>
          <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: `${Math.max(600, demandDays.length * 5)}px` }}>
            {/* Event labels */}
            {eventDays.map(ev => (
              <text key={ev.i} x={sx(ev.i)} y={pT - 5} textAnchor="start" transform={`rotate(-45, ${sx(ev.i)}, ${pT - 5})`} fontSize="8" fill="#9ca3af">{ev.name?.slice(0, 25)}</text>
            ))}
            {/* Grid */}
            {[0, 25, 50, 75, 100].map(v => (<line key={v} x1={pL} x2={cW - pR} y1={sy(v)} y2={sy(v)} stroke="#374151" strokeWidth="0.5" />))}
            {/* Bars */}
            {demandDays.map((d, i) => {
              const h = ((d.demand || 0) / 100) * iH;
              const isEvent = d.event;
              const color = isEvent ? "#ef4444" : (d.demand || 0) >= 70 ? "#ef4444" : (d.demand || 0) >= 40 ? "#14b8a6" : "#0d9488";
              return <rect key={i} x={sx(i) - barW / 2} y={pT + iH - h} width={barW} height={h} fill={color} rx="1" opacity="0.85" />;
            })}
            {/* === BIZ: Occupancy overlay — cyan horizontal markers + labels === */}
            {demandDays.map((d, i) => {
              if (d.occupancy == null) return null;
              const y = pT + iH - (d.occupancy / 100) * iH;
              const labelStep = demandDays.length > 60 ? 7 : demandDays.length > 30 ? 4 : 2;
              const showLabel = i % labelStep === 0;
              return (
                <g key={`our-occ-${i}`}>
                  <line x1={sx(i) - barW / 2 - 2} x2={sx(i) + barW / 2 + 2} y1={y} y2={y} stroke="#22d3ee" strokeWidth="1.8" opacity="0.95" />
                  {showLabel && d.occupancy > 0 && (
                    <text x={sx(i) + barW / 2 + 4} y={y + 3} textAnchor="start" fontSize="6" fontWeight="700" fill="#22d3ee">{d.occupancy}%</text>
                  )}
                </g>
              );
            })}
            {/* === BIZ: Occupancy line (dotted connect for easier tracking) === */}
            <path
              d={demandDays.filter(d => d.occupancy != null).map((d, i, arr) => {
                const idx = demandDays.indexOf(d);
                const y = pT + iH - (d.occupancy / 100) * iH;
                return `${i === 0 ? "M" : "L"} ${sx(idx)} ${y}`;
              }).join(" ")}
              fill="none" stroke="#22d3ee" strokeWidth="1.2" strokeDasharray="2 3" opacity="0.7"
            />
            {/* X-axis date labels — every day, month label when month changes */}
            {demandDays.map((d, i) => {
              if (!d?.date) return null;
              const dt = new Date(d.date + "T00:00:00");
              const dayNum = dt.getDate();
              const monthShort = dt.toLocaleDateString("en", { month: "short" });
              const prev = i > 0 ? new Date(demandDays[i - 1].date + "T00:00:00") : null;
              const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
              return (
                <g key={`tick-${i}`}>
                  <text x={sx(i)} y={pT + iH + 10} textAnchor="middle" fontSize="6" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dayNum}</text>
                  {isMonthStart && (
                    <text x={sx(i)} y={pT + iH + 20} textAnchor="middle" fontSize="7" fill="#10b981" fontWeight="800">{monthShort}</text>
                  )}
                </g>
              );
            })}
            {/* 7d trend */}
            <path d={trendPath} fill="none" stroke="#5eead4" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.7" />
          </svg>
        </div>
      </div>

      {/* WAP Chart */}
      {(() => {
        const wapDays = daily.filter(d => d.wap);
        if (wapDays.length < 2) return null;
        // Include our_rate in scale so our line is visible
        const ourRates = wapDays.map(d => d.our_rate || 0).filter(v => v > 0);
        const maxW = Math.max(...wapDays.map(d => d.wap), ...ourRates) * 1.05;
        const minW = Math.min(...wapDays.map(d => d.wap), ...ourRates) * 0.95;
        const wSX = (i) => pL + (i / Math.max(wapDays.length - 1, 1)) * iW;
        const wSY = (v) => pT + (1 - (v - minW) / (maxW - minW)) * iH;
        const wLine = wapDays.map((d, i) => `${i === 0 ? "M" : "L"} ${wSX(i)} ${wSY(d.wap)}`).join(" ");
        const ourLine = wapDays.filter(d => d.our_rate > 0).map((d, i, arr) => {
          const idx = wapDays.indexOf(d);
          return `${i === 0 ? "M" : "L"} ${wSX(idx)} ${wSY(d.our_rate)}`;
        }).join(" ");
        return (
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="wap-chart">
            <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
              <div>
                <p className="text-[10px] text-stone-500 uppercase">Market Pricing</p>
                <h3 className="text-sm font-bold text-white">Weighted Average Price</h3>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-stone-400">
                <span className="flex items-center gap-1.5"><span className="w-4 h-[2px] bg-white" /> Pazar WAP</span>
                <span className="flex items-center gap-1.5 pl-3 border-l border-stone-700">
                  <span className="w-4 h-[2px] bg-violet-400" />
                  <span className="text-violet-200 font-semibold">BİZ · Fiyat</span>
                </span>
              </div>
            </div>
            <div className="relative overflow-x-auto">
              {/* HTML Y-axis price labels */}
              <div className="absolute left-0 top-0 bottom-0 w-14 pointer-events-none z-10" style={{ minHeight: "100%" }}>
                {[1, 0.75, 0.5, 0.25, 0].map(f => {
                  const v = Math.round(minW + f * (maxW - minW));
                  return (
                    <div key={f}
                      className="absolute right-1 text-[11px] md:text-xs font-bold text-stone-200 tabular-nums"
                      style={{ top: `calc(${((1 - f) * (iH - 10) + 10) / cH * 100}% - 7px)`, lineHeight: 1 }}>
                      {cur(v)}
                    </div>
                  );
                })}
              </div>
              <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: "600px" }}>
                {[0, 0.25, 0.5, 0.75, 1].map(f => { const y = 10 + (1 - f) * (iH - 10); return <line key={f} x1={pL} x2={cW - pR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" />; })}
                <path d={wLine} fill="none" stroke="#ffffff" strokeWidth="2" />
                {/* BIZ · Our rate — violet solid line + dots */}
                {ourLine && <path d={ourLine} fill="none" stroke="#a78bfa" strokeWidth="2.2" opacity="0.95" />}
                {wapDays.map((d, i) => {
                  if (!d.our_rate || d.our_rate <= 0) return null;
                  const x = wSX(i), y = wSY(d.our_rate);
                  const labelStep = wapDays.length > 60 ? 7 : wapDays.length > 30 ? 4 : 2;
                  const showLabel = i % labelStep === 0;
                  return (
                    <g key={`our-rate-${i}`}>
                      <circle cx={x} cy={y} r="2.5" fill="#a78bfa" stroke="#0a0a0a" strokeWidth="1" />
                      {showLabel && (
                        <text x={x} y={y - 6} textAnchor="middle" fontSize="7.5" fontWeight="800" fill="#c4b5fd">£{Math.round(d.our_rate)}</text>
                      )}
                    </g>
                  );
                })}
                {/* X-axis date labels — every day */}
                {wapDays.map((d, i) => {
                  if (!d?.date) return null;
                  const dt = new Date(d.date + "T00:00:00");
                  const dayNum = dt.getDate();
                  const monthShort = dt.toLocaleDateString("en", { month: "short" });
                  const prev = i > 0 ? new Date(wapDays[i - 1].date + "T00:00:00") : null;
                  const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
                  const x = wSX(i);
                  return (
                    <g key={`wtick-${i}`}>
                      <text x={x} y={pT + iH + 10} textAnchor="middle" fontSize="6" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dayNum}</text>
                      {isMonthStart && (
                        <text x={x} y={pT + iH + 20} textAnchor="middle" fontSize="7" fill="#10b981" fontWeight="800">{monthShort}</text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>
        );
      })()}

      {/* 7-Day Pickup Change */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="pickup-change">
        <p className="text-[10px] text-stone-500 uppercase">7-Day Change</p>
        <h3 className="text-sm font-bold text-white mb-1">Recent Pickup</h3>
        <p className="text-[10px] text-stone-500 mb-3">How demand and price shifted vs the same dates 7 days ago</p>
        <div className="flex items-center gap-4 mb-2 text-[10px] text-stone-400">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" /> Demand up</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" /> Demand down</span>
          <span className="flex items-center gap-1"><span className="w-4 h-0 border-t border-dashed border-amber-400" /> Price change</span>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${cW} 140`} className="w-full" style={{ minWidth: "600px" }}>
            <line x1={pL} x2={cW - pR} y1={70} y2={70} stroke="#4b5563" strokeWidth="0.5" />
            {pickup_change.slice(0, days).map((p, i) => {
              const x = pL + (i / Math.max(pickup_change.length - 1, 1)) * iW;
              const h = Math.abs(p.demand_change) * 2;
              const y = p.demand_change >= 0 ? 70 - h : 70;
              const color = p.demand_change >= 0 ? "#22c55e" : "#ef4444";
              return <rect key={i} x={x - 2} y={y} width={4} height={h} fill={color} rx="1" />;
            })}
            {/* Price change line */}
            <path d={pickup_change.slice(0, days).map((p, i) => { const x = pL + (i / Math.max(pickup_change.length - 1, 1)) * iW; return `${i === 0 ? "M" : "L"} ${x} ${70 - p.price_change * 2}`; }).join(" ")} fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 3" />
            {/* X-axis date labels — every day + month names on change */}
            {pickup_change.slice(0, days).map((p, i) => {
              const ds = p.date || daily[i]?.date;
              if (!ds) return null;
              const dt = new Date(ds + "T00:00:00");
              const dayNum = dt.getDate();
              const monthShort = dt.toLocaleDateString("en", { month: "short" });
              const prevDs = i > 0 ? (pickup_change[i - 1]?.date || daily[i - 1]?.date) : null;
              const isMonthStart = !prevDs || new Date(prevDs + "T00:00:00").getMonth() !== dt.getMonth();
              const x = pL + (i / Math.max(pickup_change.length - 1, 1)) * iW;
              return (
                <g key={`pxtick-${i}`}>
                  <text x={x} y={125} textAnchor="middle" fontSize="6" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dayNum}</text>
                  {isMonthStart && <text x={x} y={135} textAnchor="middle" fontSize="7" fill="#10b981" fontWeight="800">{monthShort}</text>}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* PRICING OPPORTUNITY MAP */}
      {opportunity_map.length > 0 && (
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="opportunity-map">
          <div className="flex items-center justify-between mb-1">
            <div><p className="text-[10px] text-stone-500 uppercase">Pricing Opportunity Map</p><h3 className="text-sm font-bold text-white">Where is the market mispriced?</h3><p className="text-[10px] text-stone-500">Each dot is a check-in date, plotted by demand (x) vs price (y)</p></div>
            <div className="flex items-center gap-4 text-[10px] text-stone-400">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Under-priced</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> Over-priced</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-500" /> Fairly priced</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Peak dates</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <svg viewBox={`0 0 ${omW} ${omH}`} className="w-full" style={{ minWidth: "700px" }}>
              {/* Grid */}
              {[0, 25, 50, 75, 100].map(v => (<g key={v}><line x1={omPL} x2={omW - omPR} y1={omSY(omMinP + (v / 100) * (omMaxP - omMinP))} y2={omSY(omMinP + (v / 100) * (omMaxP - omMinP))} stroke="#374151" strokeWidth="0.5" /></g>))}
              {[0, 25, 50, 75, 100].map(v => (<text key={`x${v}`} x={omSX(v)} y={omH - 15} textAnchor="middle" fontSize="9" fill="#9ca3af">{v}%</text>))}
              {[0, 0.25, 0.5, 0.75, 1].map(f => { const p = Math.round(omMinP + f * (omMaxP - omMinP)); return <text key={`y${f}`} x={omPL - 8} y={omSY(p) + 4} textAnchor="end" fontSize="9" fill="#9ca3af">{cur(p)}</text>; })}
              {/* Quadrant labels */}
              <text x={omPL + 5} y={omPT + 15} fontSize="10" fill="#ef4444" fontWeight="bold">OVERPRICED</text>
              <text x={omW - omPR - 80} y={omPT + 15} fontSize="10" fill="#f59e0b" fontWeight="bold">PEAK DATES</text>
              <text x={omPL + 5} y={omH - omPB - 5} fontSize="9" fill="#9ca3af">QUIET DATES</text>
              <text x={omW - omPR - 100} y={omH - omPB - 5} fontSize="9" fill="#22c55e" fontWeight="bold">OPPORTUNITY</text>
              {/* Dots */}
              {opportunity_map.map((o, i) => (
                <circle key={i} cx={omSX(o.demand)} cy={omSY(o.price)} r={o.event ? 6 : 4} fill={DOT_COLORS[o.color] || "#06b6d4"} opacity="0.8" />
              ))}
              {/* Axis labels */}
              <text x={omW / 2} y={omH - 2} textAnchor="middle" fontSize="9" fill="#9ca3af">Quiet market → Busy market →</text>
            </svg>
          </div>
        </div>
      )}

      {/* Booking Behavior — Lead Time + LOS */}
      {behavior && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Lead Time Distribution */}
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="lead-time-dist">
            <p className="text-[10px] text-stone-500 uppercase">Booking Behavior</p>
            <h3 className="text-sm font-bold text-white mb-1">Lead Time Distribution</h3>
            <p className="text-[10px] text-stone-500 mb-4">From {behavior.total_bookings} bookings (last 90 days)</p>
            <div className="flex items-end justify-around gap-2 h-32">
              {behavior.lead_time.distribution.map(lt => (
                <div key={lt.label} className="flex flex-col items-center gap-1 flex-1">
                  <span className="text-sm font-bold" style={{ color: lt.color }}>{lt.pct}%</span>
                  <div className="w-full rounded-t-lg" style={{ backgroundColor: lt.color, height: `${Math.max(lt.pct, 5)}%`, minHeight: "8px" }} />
                  <span className="text-[10px] text-stone-400">{lt.label}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between mt-3 text-[10px] text-stone-400">
              <span>Avg lead time: <strong className="text-white">{behavior.lead_time.avg_lead_time} days</strong></span>
              <span>Last-minute (0-7d): <strong className="text-red-400">{behavior.lead_time.last_minute_pct}%</strong></span>
            </div>
          </div>

          {/* Length of Stay */}
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="los-dist">
            <p className="text-[10px] text-stone-500 uppercase">Booking Behavior</p>
            <h3 className="text-sm font-bold text-white mb-1">Length of Stay</h3>
            <p className="text-[10px] text-stone-500 mb-4">Guest stay patterns from real booking data</p>
            <div className="flex items-end justify-around gap-2 h-32">
              {behavior.length_of_stay.distribution.map(ls => (
                <div key={ls.label} className="flex flex-col items-center gap-1 flex-1">
                  <span className="text-sm font-bold" style={{ color: ls.color }}>{ls.pct}%</span>
                  <div className="w-full rounded-t-lg" style={{ backgroundColor: ls.color, height: `${Math.max(ls.pct, 5)}%`, minHeight: "8px" }} />
                  <span className="text-[10px] text-stone-400">{ls.label}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between mt-3 text-[10px] text-stone-400">
              <span>Avg LOS: <strong className="text-white">{behavior.length_of_stay.avg_los} nights</strong></span>
              <span>3+ nights: <strong className="text-violet-400">{behavior.length_of_stay.long_stay_pct}%</strong></span>
            </div>
          </div>
        </div>
      )}

      {/* Demand by Lead Time + DOW Patterns */}
      {behavior && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Demand by Lead Time */}
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-by-lt">
            <p className="text-[10px] text-stone-500 uppercase">Booking Window</p>
            <h3 className="text-sm font-bold text-white mb-4">Demand by Lead Time</h3>
            <div className="space-y-3">
              {behavior.demand_by_lead_time.map(w => (
                <div key={w.label} className="border border-stone-700 rounded-xl p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white">{w.label}</span>
                      <Badge className="text-[8px]" style={{ backgroundColor: w.color + "30", color: w.color }}>{w.tag}</Badge>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="font-bold text-cyan-400">{w.avg_demand ?? "—"}%</span>
                      <span className="text-stone-400">{cur(w.avg_wap)}</span>
                      <span className="text-stone-500">{w.avg_supply?.toLocaleString() ?? "—"}</span>
                      {w.hot_dates > 0 && <Badge className="bg-red-500 text-white text-[8px]">{w.hot_dates} hot</Badge>}
                    </div>
                  </div>
                  <div className="mt-2 bg-stone-800 rounded-full h-2 overflow-hidden">
                    <div className="h-2 rounded-full" style={{ width: `${w.avg_demand || 0}%`, backgroundColor: w.color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* DOW Patterns */}
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="dow-patterns">
            <p className="text-[10px] text-stone-500 uppercase">Weekly Rhythm</p>
            <h3 className="text-sm font-bold text-white mb-4">Day-of-Week Patterns</h3>
            <div className="flex items-end justify-around gap-2 h-40">
              {behavior.dow_patterns.map(d => {
                const maxD = Math.max(...behavior.dow_patterns.map(x => x.avg_demand), 1);
                const h = (d.avg_demand / maxD) * 100;
                const isWeekend = d.dow >= 5;
                return (
                  <div key={d.dow} className="flex flex-col items-center gap-1 flex-1">
                    <span className="text-[10px] text-white font-bold">{cur(d.avg_wap)}</span>
                    <div className="w-full flex flex-col items-center">
                      <div className="w-full rounded-t-lg" style={{ height: `${Math.max(h, 10)}%`, minHeight: "12px", backgroundColor: isWeekend ? "#f59e0b" : "#14b8a6" }} />
                    </div>
                    <span className="text-[10px] text-stone-400">{d.label}</span>
                    <span className="text-[9px] text-stone-500">{d.avg_demand}%</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
