import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Activity, TrendingUp, TrendingDown, BarChart3, RefreshCw, Zap, PartyPopper, ArrowUpRight, ArrowDownRight, Minus, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const RANGES = [
  { value: 1, label: "Today" },
  { value: 7, label: "7 Days" },
  { value: 15, label: "15 Days" },
  { value: 30, label: "30 Days" },
  { value: 60, label: "60 Days" },
  { value: 90, label: "90 Days" },
  { value: 180, label: "180 Days" },
  { value: 365, label: "1 Year" },
];

const AI_STATUS = {
  ai: { label: "AI", bg: "bg-violet-500", text: "text-white" },
  event: { label: "EVENT", bg: "bg-red-500", text: "text-white" },
  manual: { label: "MANUAL", bg: "bg-indigo-500", text: "text-white" },
  base: { label: "BASE", bg: "bg-stone-600", text: "text-stone-300" },
};

export const MarketDemandDashboard = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState(365);
  const [occData, setOccData] = useState(null);
  const [recentBookings, setRecentBookings] = useState(null);
  const [pickupWindow, setPickupWindow] = useState("24h");

  const load = (days) => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/demand-dashboard?days=${days}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
    // Load occupancy & pickup
    axios.get(`${API}/revenue/market-robot/${propertyId}/occupancy-pickup?days=90&pickup_window=${pickupWindow}`)
      .then(r => setOccData(r.data)).catch(() => {});
    // Load recent bookings
    axios.get(`${API}/revenue/market-robot/${propertyId}/recent-bookings?days=7`)
      .then(r => setRecentBookings(r.data)).catch(() => {});
  };
  useEffect(() => { load(range); }, [propertyId, range]);
  // Reload pickup when window changes
  useEffect(() => {
    axios.get(`${API}/revenue/market-robot/${propertyId}/occupancy-pickup?days=90&pickup_window=${pickupWindow}`)
      .then(r => setOccData(r.data)).catch(() => {});
  }, [pickupWindow]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading {range}-day data...</div>;
  if (!data) return null;

  const { daily_data, kpis } = data;

  // === Chart ===
  const chartW = 1200, chartH = 310, padL = 60, padR = 20, padT = 35, padB = 55;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const allRates = daily_data.flatMap(d => [d.sell_rate, d.comp_avg, d.base_rate, d.floor_rate].filter(Boolean));
  const maxRate = Math.max(...allRates, 1) * 1.1;
  const minRate = Math.min(...allRates) * 0.9;
  const scaleX = (i) => padL + (i / Math.max(daily_data.length - 1, 1)) * innerW;
  const scaleY = (v) => padT + (1 - (v - minRate) / (maxRate - minRate)) * innerH;

  const monthLabels = [];
  let lastM = "";
  daily_data.forEach((d, i) => { if (d.month !== lastM) { monthLabels.push({ i, label: d.month }); lastM = d.month; } });

  const sellLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.sell_rate)}`).join(" ");
  const baseLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.base_rate)}`).join(" ");
  const floorLine = daily_data.map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(d.floor_rate)}`).join(" ");
  const compSegs = []; let seg = [];
  daily_data.forEach((d, i) => { if (d.comp_avg) { seg.push({ i, y: d.comp_avg }); } else if (seg.length > 1) { compSegs.push([...seg]); seg = []; } else { seg = []; } });
  if (seg.length > 1) compSegs.push(seg);

  const aboveFill = [], belowFill = [];
  daily_data.forEach((d, i) => {
    if (d.comp_avg) {
      if (d.sell_rate >= d.comp_avg) aboveFill.push({ i, top: d.sell_rate, bot: d.comp_avg });
      else belowFill.push({ i, top: d.comp_avg, bot: d.sell_rate });
    }
  });

  return (
    <div className="space-y-5" data-testid="market-demand-dashboard">
      {/* Header + Range Selector */}
      <div className="bg-gradient-to-r from-stone-900 via-stone-800 to-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center">
              <Activity className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Market Position & Demand</h2>
              <p className="text-xs text-white/40">Where do you stand? ADR &amp; Occupancy vs Market vs Competitors</p>
            </div>
          </div>
          {/* Range Selector */}
          <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5" data-testid="demand-range-selector">
            {RANGES.map(r => (
              <button key={r.value} onClick={() => setRange(r.value)}
                className={`px-2.5 py-1.5 text-[11px] font-semibold rounded-lg transition-all whitespace-nowrap ${range === r.value ? "bg-cyan-500 text-white" : "text-white/35 hover:text-white/70"}`}
                data-testid={`range-${r.value}`}>{r.label}
              </button>
            ))}
          </div>
        </div>

        {/* 3-Column Comparison: Us / Market / Competitors */}
        <div className="grid grid-cols-3 gap-3" data-testid="adr-occ-comparison">
          {/* OUR HOTEL */}
          <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-full bg-cyan-400" />
              <span className="text-sm font-bold text-cyan-300">Your Hotel</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[9px] text-white/30 uppercase">ADR</p>
                <p className="text-xl font-bold text-cyan-300">{cur(kpis.our_adr)}</p>
              </div>
              <div>
                <p className="text-[9px] text-white/30 uppercase">Occupancy</p>
                <p className="text-xl font-bold text-cyan-300">{kpis.our_occupancy}%</p>
              </div>
            </div>
            <div className="mt-2 text-[10px] text-white/30">Based on your bookings &amp; AI pricing</div>
          </div>

          {/* MARKET */}
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-full bg-amber-400" />
              <span className="text-sm font-bold text-amber-300">Market Average</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[9px] text-white/30 uppercase">Market ADR</p>
                <p className="text-xl font-bold text-amber-300">{kpis.market_adr ? cur(kpis.market_adr) : "—"}</p>
              </div>
              <div>
                <p className="text-[9px] text-white/30 uppercase">Market Occ</p>
                <p className="text-xl font-bold text-amber-300">{kpis.market_occupancy != null ? `${kpis.market_occupancy}%` : "—"}</p>
              </div>
            </div>
            <div className="mt-2 text-[10px] text-white/30">{kpis.market_data_days || 0} days of supply data from robot</div>
          </div>

          {/* COMPETITORS */}
          <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-full bg-violet-400" />
              <span className="text-sm font-bold text-violet-300">Competitors</span>
              <Badge className="bg-white/10 text-white/40 text-[8px]">{kpis.competitors_tracked} tracked</Badge>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="text-[9px] text-white/30 uppercase">Comp ADR</p>
                <p className="text-xl font-bold text-violet-300">{kpis.comp_adr ? cur(kpis.comp_adr) : "—"}</p>
              </div>
              <div>
                <p className="text-[9px] text-white/30 uppercase">Comp Occ</p>
                <p className="text-xl font-bold text-violet-300">{kpis.comp_occupancy != null ? `${kpis.comp_occupancy}%` : "—"}</p>
              </div>
            </div>
            <div className="mt-2 text-[10px] text-white/30">
              {kpis.comp_adr ? `Position: ${kpis.avg_position_pct > 0 ? "+" : ""}${kpis.avg_position_pct}% vs competitors` : "Scan competitor hotels for data"}
            </div>
          </div>
        </div>

        {/* Quick Stats Row */}
        <div className="grid grid-cols-4 md:grid-cols-8 gap-2 mt-3">
          {[
            { l: "Above Market", v: kpis.above_market_days, c: "text-emerald-300" },
            { l: "Below Market", v: kpis.below_market_days, c: "text-red-300" },
            { l: "Aligned", v: kpis.aligned_days, c: "text-white/60" },
            { l: "High Demand", v: kpis.high_demand_days, c: "text-red-300" },
            { l: "Low Demand", v: kpis.low_demand_days, c: "text-emerald-300" },
            { l: "Event Days", v: kpis.event_days, c: "text-red-300" },
            { l: "AI Managed", v: `${kpis.ai_managed_pct}%`, c: "text-cyan-300" },
            { l: "Days", v: kpis.total_days, c: "text-white/60" },
          ].map(k => (
            <div key={k.l} className="bg-white/5 rounded-lg p-2 text-center">
              <p className={`text-sm font-bold ${k.c}`}>{k.v}</p>
              <p className="text-[7px] text-white/25 uppercase leading-tight">{k.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* OCCUPANCY & PICKUP + RECENT BOOKINGS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Occupancy & Pickup Chart — 2/3 width */}
        <div className="lg:col-span-2 bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="occupancy-pickup-chart">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-white">90 Day Occupancy & Pickup</h3>
              <p className="text-[10px] text-stone-500">Occupancy trend with booking velocity overlay</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-[10px] text-stone-400">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-600" /> Base Occupancy %</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-cyan-400" /> {pickupWindow === "24h" ? "24h" : pickupWindow === "3d" ? "3 Day" : "7 Day"} Pickup %</span>
              </div>
              <div className="flex items-center gap-1 bg-white/5 rounded-lg border border-white/10 p-0.5" data-testid="pickup-window-selector">
                {[{v:"24h",l:"24H"},{v:"3d",l:"3 DAYS"},{v:"7d",l:"7 DAYS"}].map(pw => (
                  <button key={pw.v} onClick={() => setPickupWindow(pw.v)}
                    className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all ${pickupWindow === pw.v ? "bg-cyan-500 text-white" : "text-stone-500 hover:text-white/70"}`}
                    data-testid={`pickup-${pw.v}`}>{pw.l}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {occData && (() => {
            const occ = occData.daily || [];
            const cW = 800, cH = 200, pL = 35, pR = 10, pT = 10, pB = 30;
            const iW = cW - pL - pR, iH = cH - pT - pB;
            const barW = Math.max(2, Math.min(8, (iW / occ.length) - 1));
            const sx = (i) => pL + (i / Math.max(occ.length - 1, 1)) * iW;
            const sy = (v) => pT + (1 - v / 100) * iH;
            const mLabels = []; let lm = "";
            occ.forEach((d, i) => { if (d.month !== lm) { mLabels.push({ i, l: `${d.month} ${d.day}` }); lm = d.month; } });
            return (
              <div className="relative overflow-x-auto">
                <div className="absolute left-0 top-0 bottom-0 w-12 pointer-events-none z-10" style={{ minHeight: "100%" }}>
                  {[100, 75, 50, 25, 0].map(v => (
                    <div key={v}
                      className="absolute right-1 text-[11px] md:text-xs font-bold text-stone-200 tabular-nums"
                      style={{ top: `calc(${((100 - v) / 100) * (cH - pT - pB) / cH * 100}% + ${pT / cH * 100}% - 8px)`, lineHeight: 1 }}>
                      {v}%
                    </div>
                  ))}
                </div>
                <svg viewBox={`0 0 ${cW} ${cH}`} className="w-full" style={{ minWidth: "600px" }}>
                  {[0, 25, 50, 75, 100].map(v => (
                    <line key={v} x1={pL} x2={cW - pR} y1={sy(v)} y2={sy(v)} stroke="#374151" strokeWidth="0.5" />
                  ))}
                  {mLabels.map(ml => (
                    <line key={`ml${ml.i}`} x1={sx(ml.i)} x2={sx(ml.i)} y1={pT} y2={pT + iH} stroke="#4b5563" strokeWidth="0.3" strokeDasharray="2 3" opacity="0.4" />
                  ))}
                  {occ.map((d, i) => {
                    const x = sx(i) - barW / 2;
                    const occH = (d.occupancy_pct / 100) * iH;
                    const pickH = (d.pickup_pct / 100) * iH;
                    return (
                      <g key={i}>
                        <rect x={x} y={pT + iH - occH} width={barW} height={occH} fill="#4b5563" rx="1" />
                        {d.pickup_pct > 0 && <rect x={x} y={pT + iH - pickH} width={barW} height={pickH} fill="#06b6d4" rx="1" opacity="0.9" />}
                      </g>
                    );
                  })}
                  {/* Daily x-axis labels — every day with month names on change */}
                  {occ.map((d, i) => {
                    if (!d?.date) return null;
                    const dt = new Date(d.date + "T00:00:00");
                    const dayNum = dt.getDate();
                    const monthShort = dt.toLocaleDateString("en", { month: "short" });
                    const prev = i > 0 ? new Date(occ[i - 1].date + "T00:00:00") : null;
                    const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
                    return (
                      <g key={`xd${i}`}>
                        <text x={sx(i)} y={pT + iH + 10} textAnchor="middle" fontSize="6" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dayNum}</text>
                        {isMonthStart && <text x={sx(i)} y={pT + iH + 20} textAnchor="middle" fontSize="7" fill="#10b981" fontWeight="800">{monthShort}</text>}
                      </g>
                    );
                  })}
                </svg>
              </div>
            );
          })()}
        </div>

        {/* Recent Bookings Panel — 1/3 width */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="recent-bookings">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-5 h-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-white">RECENT BOOKINGS</h3>
              <p className="text-[10px] text-stone-500">Last 7 days activity</p>
            </div>
          </div>
          {recentBookings && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-700">
                    {["DATE", "BOOKINGS", "ROOM NIGHTS", "ADR", "REVENUE"].map(h => (
                      <th key={h} className="px-2 py-1.5 text-[9px] font-semibold text-stone-500 text-center whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentBookings.daily.map((d, i) => (
                    <tr key={d.date} className={`border-b border-stone-800/50 ${i === 0 ? "bg-cyan-500/5" : ""}`}>
                      <td className="px-2 py-2.5 text-stone-300 text-xs font-medium whitespace-nowrap">
                        <div className="leading-tight">
                          <div className="font-bold">{d.dow} {d.day}</div>
                          <div className="text-[10px] text-stone-500">{d.month}</div>
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-center text-white font-bold">{d.bookings}</td>
                      <td className="px-2 py-2.5 text-center text-white font-bold">{d.room_nights}</td>
                      <td className="px-2 py-2.5 text-center text-stone-300">{cur(d.adr)}</td>
                      <td className="px-2 py-2.5 text-center text-cyan-400 font-bold">{cur(d.revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {recentBookings.summary && (
                <div className="mt-3 pt-3 border-t border-stone-700 grid grid-cols-2 gap-2 text-center">
                  <div><p className="text-[9px] text-stone-500">Total Revenue</p><p className="text-sm font-bold text-cyan-400">{cur(recentBookings.summary.total_revenue)}</p></div>
                  <div><p className="text-[9px] text-stone-500">Avg ADR</p><p className="text-sm font-bold text-white">{cur(recentBookings.summary.avg_adr)}</p></div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* COMPETITIVE LANDSCAPE CHART */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-landscape-chart">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-sm font-bold text-white">COMPETITIVE LANDSCAPE</span>
            <Badge className="bg-white/10 text-white/50 text-[9px]">{daily_data.length} days</Badge>
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
        <div className="relative overflow-x-auto">
          <div className="absolute left-0 top-0 bottom-0 w-16 pointer-events-none z-10" style={{ minHeight: "100%" }}>
            {[1, 0.75, 0.5, 0.25, 0].map(frac => {
              const val = Math.round(minRate + frac * (maxRate - minRate));
              return (
                <div key={frac}
                  className="absolute right-1 text-[11px] md:text-xs font-bold text-stone-200 tabular-nums"
                  style={{ top: `calc(${((1 - frac) * innerH + padT) / chartH * 100}% - 7px)`, lineHeight: 1 }}>
                  {cur(val)}
                </div>
              );
            })}
          </div>
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: `${Math.max(600, daily_data.length * 3)}px` }}>
            {[0, 0.25, 0.5, 0.75, 1].map(frac => {
              const y = padT + (1 - frac) * innerH;
              return (<line key={frac} x1={padL} x2={chartW - padR} y1={y} y2={y} stroke="#374151" strokeWidth="0.5" />);
            })}
            {monthLabels.map(ml => (<g key={ml.i}><line x1={scaleX(ml.i)} x2={scaleX(ml.i)} y1={padT} y2={chartH - padB} stroke="#4b5563" strokeWidth="0.5" strokeDasharray="4 4" /></g>))}
            {aboveFill.map((af, idx) => <rect key={`a${idx}`} x={scaleX(af.i) - 2} y={scaleY(af.top)} width={4} height={scaleY(af.bot) - scaleY(af.top)} fill="#22c55e" opacity="0.15" />)}
            {belowFill.map((bf, idx) => <rect key={`b${idx}`} x={scaleX(bf.i) - 2} y={scaleY(bf.top)} width={4} height={scaleY(bf.bot) - scaleY(bf.top)} fill="#ef4444" opacity="0.15" />)}
            <path d={floorLine} fill="none" stroke="#f87171" strokeWidth="1" strokeDasharray="3 3" opacity="0.4" />
            <path d={baseLine} fill="none" stroke="#6b7280" strokeWidth="1" strokeDasharray="5 5" opacity="0.5" />
            {compSegs.map((s, si) => <path key={`c${si}`} d={s.map((pt, j) => `${j === 0 ? "M" : "L"} ${scaleX(pt.i)} ${scaleY(pt.y)}`).join(" ")} fill="none" stroke="#f59e0b" strokeWidth="2" opacity="0.8" />)}
            <path d={sellLine} fill="none" stroke="#06b6d4" strokeWidth="2.5" strokeLinejoin="round" />
            {daily_data.map((d, i) => d.event ? <circle key={`ev${i}`} cx={scaleX(i)} cy={scaleY(d.sell_rate)} r="4" fill="#ef4444" stroke="#000" strokeWidth="1" /> : null)}
            {/* X-axis date labels — every day + month names on change */}
            {daily_data.map((d, i) => {
              if (!d?.date) return null;
              const dt = new Date(d.date + "T00:00:00");
              const dayNum = dt.getDate();
              const monthShort = dt.toLocaleDateString("en", { month: "short" });
              const prev = i > 0 ? new Date(daily_data[i - 1].date + "T00:00:00") : null;
              const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
              return (
                <g key={`xd${i}`}>
                  <text x={scaleX(i)} y={chartH - padB + 10} textAnchor="middle" fontSize="6" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dayNum}</text>
                  {isMonthStart && <text x={scaleX(i)} y={chartH - padB + 20} textAnchor="middle" fontSize="7" fill="#10b981" fontWeight="800">{monthShort}</text>}
                </g>
              );
            })}
            {daily_data.filter((_, i) => i % Math.max(Math.floor(daily_data.length / 12), 1) === 0).map((d) => {
              const i = daily_data.indexOf(d);
              return (<g key={`lbl${i}`}><text x={scaleX(i)} y={scaleY(d.sell_rate) - 8} textAnchor="middle" fontSize="8" fill="#06b6d4" fontWeight="600">{cur(d.sell_rate)}</text>{d.comp_avg && <text x={scaleX(i)} y={scaleY(d.comp_avg) + 14} textAnchor="middle" fontSize="8" fill="#f59e0b">{cur(d.comp_avg)}</text>}</g>);
            })}
          </svg>
        </div>
      </div>

      {/* DEMAND HEATMAP */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="demand-heatmap">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-bold text-white flex items-center gap-2"><BarChart3 className="w-4 h-4 text-stone-400" /> MARKET DEMAND HEATMAP</span>
          <div className="flex items-center gap-3 text-[10px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500" />High</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500" />Moderate</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500" />Low</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-700" />No Data</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-[2px]">
          {daily_data.map((d, i) => {
            const mu = d.market_unavail;
            const color = mu == null ? "#374151" : mu >= 70 ? "#ef4444" : mu >= 40 ? "#f59e0b" : "#22c55e";
            const opacity = mu == null ? 0.3 : 0.7 + (mu / 100) * 0.3;
            return (
              <div key={i} className="relative" style={{ width: `${Math.max(3, Math.min(10, 700 / daily_data.length))}px`, height: "20px", backgroundColor: color, opacity, borderRadius: "1px" }}
                title={`${d.date} (${d.dow}) | Market: ${mu ?? "—"}% | ${d.demand_level}${d.event ? ` | ${d.event}` : ""}`}>
                {d.event && <div className="absolute -top-1 left-0 right-0 h-1 bg-red-300 rounded-full" />}
              </div>
            );
          })}
        </div>
        {/* Day labels under heatmap — every day, month name when month changes */}
        <div className="flex flex-wrap gap-[2px] mt-1">
          {daily_data.map((d, i) => {
            if (!d?.date) return null;
            const dt = new Date(d.date + "T00:00:00");
            const dayNum = dt.getDate();
            const prev = i > 0 ? new Date(daily_data[i - 1].date + "T00:00:00") : null;
            const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
            const monthShort = dt.toLocaleDateString("en", { month: "short" });
            const width = Math.max(3, Math.min(10, 700 / daily_data.length));
            return (
              <div key={`hl${i}`} style={{ width: `${width}px` }} className="text-center leading-none">
                <div className={`text-[7px] ${isMonthStart ? "text-white font-bold" : "text-stone-500"}`}>{dayNum}</div>
                {isMonthStart && <div className="text-[6px] text-emerald-400 font-black">{monthShort}</div>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Rate Grid Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl overflow-hidden" data-testid="demand-rate-table">
        <div className="px-5 py-3 border-b border-stone-700 flex items-center justify-between">
          <span className="font-bold text-white text-sm">Rate Grid — {daily_data.length} Days</span>
          <div className="flex items-center gap-3 text-[9px] text-stone-400">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cyan-400" />Our ADR</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" />Market</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-400" />Competitor</span>
          </div>
        </div>
        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-stone-800 z-10">
              <tr className="border-b border-stone-700">
                {["Date", "Day", "Status", "Our ADR", "Our Occ", "Comp ADR", "Position", "Market", "Floor", "Event"].map(h => (
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
                    <td className="px-2 py-1.5 text-center">
                      <span className={`text-xs font-semibold ${d.occupancy >= 70 ? "text-emerald-400" : d.occupancy >= 40 ? "text-amber-400" : "text-red-400"}`}>{d.occupancy}%</span>
                    </td>
                    <td className="px-2 py-1.5 text-center text-violet-400 text-xs">{d.comp_avg ? cur(d.comp_avg) : <span className="text-stone-600">—</span>}</td>
                    <td className="px-2 py-1.5 text-center">
                      {d.position ? (
                        <span className={`flex items-center justify-center gap-0.5 text-[10px] font-bold ${d.position === "above" ? "text-emerald-400" : d.position === "below" ? "text-red-400" : "text-stone-400"}`}>
                          {d.position === "above" ? <ArrowUpRight className="w-3 h-3" /> : d.position === "below" ? <ArrowDownRight className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                          {d.position_pct > 0 ? "+" : ""}{d.position_pct}%
                        </span>
                      ) : <span className="text-stone-700">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-center">
                      {d.market_unavail != null ? (
                        <span className={`text-[10px] font-bold ${d.demand_level === "high" ? "text-red-400" : d.demand_level === "moderate" ? "text-amber-400" : "text-emerald-400"}`}>{d.market_unavail}%</span>
                      ) : <span className="text-stone-600">—</span>}
                    </td>
                    <td className="px-2 py-1.5 text-center text-stone-500 text-xs">{cur(d.floor_rate)}</td>
                    <td className="px-2 py-1.5 text-center">
                      {d.event ? (
                        <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${d.event_impact === "mega" ? "bg-red-500 text-white" : d.event_impact === "large" ? "bg-orange-500 text-white" : "bg-amber-400 text-white"}`} title={d.event}>{d.event_impact?.toUpperCase()}</span>
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
