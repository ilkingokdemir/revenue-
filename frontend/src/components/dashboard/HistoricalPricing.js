import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { History, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, RefreshCw, CheckCircle, Calendar, BarChart3, Target, Zap, Download } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const SEASON_STYLES = {
  peak: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", label: "Peak (Jun-Aug)" },
  holiday: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-600", label: "Holiday (Dec-Jan)" },
  shoulder: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600", label: "Shoulder (Mar-May, Sep-Oct)" },
  low: { bg: "bg-stone-50", border: "border-stone-200", text: "text-stone-500", label: "Low (Feb, Nov)" },
};

export const HistoricalPricing = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/revenue/historical-pricing/${propertyId}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setLoading(false); });
  };
  useEffect(() => { load(); }, [propertyId]);

  const applyFloors = async () => {
    if (!data?.min_price_suggestions) return;
    setApplying(true);
    try {
      const floors = data.min_price_suggestions.map(s => ({
        month: s.month,
        min_price: s.suggested_min,
      }));
      const { data: r } = await axios.post(`${API}/revenue/historical-pricing/${propertyId}/apply-floors`, { floors });
      toast.success(r.message);
    } catch { toast.error("Failed to apply"); }
    setApplying(false);
  };

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Analyzing 2 years of pricing data...</div>;
  if (!data) return null;

  const { kpis, monthly_stats, dow_stats, season_stats, min_price_suggestions } = data;

  // Chart dimensions
  const chartW = 900, chartH = 220, padL = 55, padR = 20, padT = 25, padB = 35;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const maxR = Math.max(...monthly_stats.map(m => m.max_rate)) * 1.1;
  const minR = Math.min(...monthly_stats.map(m => m.min_rate)) * 0.9;
  const scaleX = (i) => padL + (i / Math.max(monthly_stats.length - 1, 1)) * innerW;
  const scaleY = (v) => padT + (1 - (v - minR) / (maxR - minR)) * innerH;

  const avgLine = monthly_stats.map((m, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(m.avg_rate)}`).join(" ");
  const minLine = monthly_stats.map((m, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(m.min_rate)}`).join(" ");
  const maxLine = monthly_stats.map((m, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(m.max_rate)}`).join(" ");

  return (
    <div className="space-y-6" data-testid="historical-pricing">
      {/* Header */}
      <div className="bg-gradient-to-r from-stone-800 via-stone-900 to-stone-800 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center">
              <History className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Historical Price Analysis</h2>
              <p className="text-sm text-white/60">2-year pricing data | AI minimum price suggestions</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge className="bg-white/10 text-white/70 text-xs">{kpis.total_data_points} days analyzed</Badge>
            <Badge className="bg-white/10 text-white/70 text-xs">{kpis.date_range}</Badge>
          </div>
        </div>

        {/* Year-over-Year KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4">
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">2yr Avg Rate</p>
            <p className="text-lg font-bold">{cur(kpis.overall_avg_rate)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">2yr Lowest</p>
            <p className="text-lg font-bold text-red-300">{cur(kpis.overall_min_rate)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">2yr Highest</p>
            <p className="text-lg font-bold text-emerald-300">{cur(kpis.overall_max_rate)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">Year 1 Avg</p>
            <p className="text-lg font-bold">{cur(kpis.year1_avg)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">Year 2 Avg</p>
            <p className="text-lg font-bold">{cur(kpis.year2_avg)}</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-[10px] text-white/40">YoY Change</p>
            <p className={`text-lg font-bold flex items-center justify-center gap-1 ${kpis.yoy_change_pct >= 0 ? "text-emerald-300" : "text-red-300"}`}>
              {kpis.yoy_change_pct >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
              {kpis.yoy_change_pct > 0 ? "+" : ""}{kpis.yoy_change_pct}%
            </p>
          </div>
        </div>
      </div>

      {/* Monthly Price Chart */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="hp-monthly-chart">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-stone-800">Monthly Rate Range (2 Years)</h3>
          <div className="flex items-center gap-4 text-xs text-stone-400">
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-violet-600 inline-block" /> Average</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-400 inline-block" /> Max</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-400 inline-block" /> Min</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: "700px" }}>
            {[0, 0.25, 0.5, 0.75, 1].map(frac => {
              const y = padT + (1 - frac) * innerH;
              const val = Math.round(minR + frac * (maxR - minR));
              return (
                <g key={frac}>
                  <line x1={padL} x2={chartW - padR} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />
                  <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[9px]" fill="#9ca3af">{cur(val)}</text>
                </g>
              );
            })}
            {/* Range fill */}
            <path d={`${maxLine} ${monthly_stats.map((m, i) => `L ${scaleX(monthly_stats.length - 1 - i)} ${scaleY(monthly_stats[monthly_stats.length - 1 - i].min_rate)}`).join(" ")} Z`}
              fill="#7c3aed" fillOpacity="0.06" />
            <path d={maxLine} fill="none" stroke="#34d399" strokeWidth="1.5" strokeDasharray="4 4" />
            <path d={minLine} fill="none" stroke="#f87171" strokeWidth="1.5" strokeDasharray="4 4" />
            <path d={avgLine} fill="none" stroke="#7c3aed" strokeWidth="2.5" strokeLinejoin="round" />
            {monthly_stats.map((m, i) => (
              <g key={i}>
                <circle cx={scaleX(i)} cy={scaleY(m.avg_rate)} r="4" fill="#7c3aed" />
                <text x={scaleX(i)} y={scaleY(m.avg_rate) - 10} textAnchor="middle" className="text-[8px]" fill="#7c3aed" fontWeight="600">{cur(m.avg_rate)}</text>
                <text x={scaleX(i)} y={chartH - 8} textAnchor="middle" className="text-[9px]" fill="#9ca3af">{m.month_name}</text>
              </g>
            ))}
          </svg>
        </div>
      </div>

      {/* AI Minimum Price Suggestions */}
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5" data-testid="hp-price-floors">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-amber-600" />
            <h3 className="font-bold text-amber-900">Unified AI Price Suggestions</h3>
            <Badge className="bg-amber-100 text-amber-700 text-[10px]">Historical + Robot + Events + Competitors</Badge>
          </div>
          <button onClick={applyFloors} disabled={applying}
            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-5 py-2 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="hp-apply-floors">
            {applying ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            {applying ? "Applying..." : "Apply All Floors to Strategy"}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-amber-200">
                {["Month", "AI Suggested", "Floor", "Hist Avg", "Market", "Events", "Competitors", "Occ %", "Sources"].map(h => (
                  <th key={h} className="px-3 py-2 text-xs font-semibold text-amber-800 text-center">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {min_price_suggestions.map(s => (
                <tr key={s.month} className="border-b border-amber-100">
                  <td className="px-3 py-2 font-bold text-amber-900">{s.month_name}</td>
                  <td className="px-3 py-2 text-center">
                    <span className="bg-amber-600 text-white px-2 py-1 rounded-lg font-bold text-sm">{cur(s.ai_suggested_rate || s.suggested_min)}</span>
                  </td>
                  <td className="px-3 py-2 text-center text-stone-600 text-xs">{cur(s.suggested_min)}</td>
                  <td className="px-3 py-2 text-center text-stone-700 font-semibold">{cur(s.historical_avg)}</td>
                  <td className="px-3 py-2 text-center">
                    {s.market_signal ? (
                      <div>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                          s.market_signal === "high_demand" ? "bg-red-100 text-red-700" : s.market_signal === "low_demand" ? "bg-emerald-100 text-emerald-700" : "bg-stone-100 text-stone-500"
                        }`}>{s.market_unavail}% unavail</span>
                        {s.market_boost !== 0 && <div className={`text-[10px] font-semibold mt-0.5 ${s.market_boost > 0 ? "text-emerald-600" : "text-red-500"}`}>{s.market_boost > 0 ? "+" : ""}{s.market_boost}%</div>}
                      </div>
                    ) : <span className="text-[10px] text-stone-300">No data</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {s.mega_events > 0 ? (
                      <div>
                        <span className="text-[9px] font-bold bg-red-100 text-red-700 px-1.5 py-0.5 rounded">{s.mega_events} major</span>
                        <div className="text-[10px] font-semibold text-red-500 mt-0.5">+{s.event_boost}%</div>
                      </div>
                    ) : s.events_count > 0 ? (
                      <span className="text-[9px] text-amber-600">{s.events_count} events</span>
                    ) : <span className="text-[10px] text-stone-300">None</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {s.competitor_avg ? (
                      <div>
                        <span className="text-xs font-semibold text-stone-700">{cur(s.competitor_avg)}</span>
                        {s.competitor_boost !== 0 && <div className={`text-[10px] font-semibold ${s.competitor_boost > 0 ? "text-emerald-600" : "text-red-500"}`}>{s.competitor_boost > 0 ? "+" : ""}{s.competitor_boost}%</div>}
                      </div>
                    ) : <span className="text-[10px] text-stone-300">No data</span>}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`font-semibold ${s.avg_occupancy >= 70 ? "text-emerald-600" : s.avg_occupancy >= 40 ? "text-amber-500" : "text-red-400"}`}>{s.avg_occupancy}%</span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <div className="flex items-center justify-center gap-0.5">
                      {s.data_sources?.historical && <span className="w-2 h-2 rounded-full bg-violet-500" title="Historical" />}
                      {s.data_sources?.market_robot && <span className="w-2 h-2 rounded-full bg-indigo-500" title="Market Robot" />}
                      {s.data_sources?.events && <span className="w-2 h-2 rounded-full bg-red-500" title="Events" />}
                      {s.data_sources?.competitors && <span className="w-2 h-2 rounded-full bg-amber-500" title="Competitors" />}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 text-[10px] text-stone-400">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-violet-500" />Historical (2yr)</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-500" />Market Robot</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />Event Intelligence</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" />Competitor Prices</span>
        </div>
      </div>

      {/* Season & DOW Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Season Analysis */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="hp-season">
          <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2"><Calendar className="w-4 h-4 text-stone-400" /> Season Analysis</h3>
          <div className="space-y-3">
            {Object.entries(season_stats).map(([key, s]) => {
              const style = SEASON_STYLES[key] || SEASON_STYLES.low;
              return (
                <div key={key} className={`${style.bg} ${style.border} border rounded-xl p-4`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`font-bold text-sm ${style.text}`}>{style.label}</span>
                    <Badge className={`text-[9px] ${style.bg} ${style.text}`}>{s.avg_occupancy}% avg occ</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <p className="text-[10px] text-stone-400">Avg Rate</p>
                      <p className="font-bold text-stone-800">{cur(s.avg_rate)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-stone-400">Min Rate</p>
                      <p className="font-bold text-red-500">{cur(s.min_rate)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-stone-400">Max Rate</p>
                      <p className="font-bold text-emerald-600">{cur(s.max_rate)}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* DOW Analysis */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="hp-dow">
          <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-stone-400" /> Day-of-Week Analysis</h3>
          <div className="space-y-2">
            {dow_stats.map(d => {
              const maxDow = Math.max(...dow_stats.map(x => x.avg_rate));
              const pct = (d.avg_rate / maxDow) * 100;
              const isWeekend = d.dow >= 4;
              return (
                <div key={d.dow} className="flex items-center gap-3">
                  <span className={`w-10 text-xs font-bold ${isWeekend ? "text-violet-700" : "text-stone-600"}`}>{d.dow_name}</span>
                  <div className="flex-1 bg-stone-100 rounded-full h-6 overflow-hidden relative">
                    <div className={`h-6 rounded-full transition-all ${isWeekend ? "bg-violet-500" : "bg-indigo-400"}`} style={{ width: `${pct}%` }} />
                    <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mix-blend-difference">{cur(d.avg_rate)}</span>
                  </div>
                  <div className="w-20 text-right text-[10px] text-stone-400">
                    {cur(d.min_rate)} - {cur(d.max_rate)}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-stone-400 mt-3">Purple bars = Weekend (Fri-Sat). Based on 2 years of sold rates.</p>
        </div>
      </div>

      {/* Monthly Stats Table */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="hp-monthly-table">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Monthly Pricing Summary (2 Years)</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-stone-50/50">
                {["Month", "Avg Rate", "Min Rate", "P25 Rate", "Median", "Max Rate", "Avg Occ", "Revenue", "Data Points"].map(h => (
                  <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {monthly_stats.map(m => (
                <tr key={m.month} className="border-b border-stone-50">
                  <td className="px-3 py-2 font-bold text-stone-800">{m.month_name}</td>
                  <td className="px-3 py-2 text-center font-semibold text-violet-700">{cur(m.avg_rate)}</td>
                  <td className="px-3 py-2 text-center text-red-500">{cur(m.min_rate)}</td>
                  <td className="px-3 py-2 text-center text-stone-600">{cur(m.p25_rate)}</td>
                  <td className="px-3 py-2 text-center text-stone-600">{cur(m.median_rate)}</td>
                  <td className="px-3 py-2 text-center text-emerald-600">{cur(m.max_rate)}</td>
                  <td className="px-3 py-2 text-center">
                    <span className={`font-semibold ${m.avg_occupancy >= 70 ? "text-emerald-600" : m.avg_occupancy >= 40 ? "text-amber-500" : "text-red-400"}`}>{m.avg_occupancy}%</span>
                  </td>
                  <td className="px-3 py-2 text-center text-stone-600">{cur(m.total_revenue)}</td>
                  <td className="px-3 py-2 text-center text-stone-400 text-xs">{m.data_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
