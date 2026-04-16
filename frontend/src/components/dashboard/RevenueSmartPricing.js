import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Zap, RefreshCw, TrendingUp, Activity, AlertTriangle, Info } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueSmartPricing = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [selectedRoomType, setSelectedRoomType] = useState("");

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/smart-pricing/${propertyId}`).then(r => { setData(r.data); setLoading(false); }).catch(() => { toast.error("Failed"); setLoading(false); });
  }, [propertyId]);

  const recalculate = async () => {
    setRecalculating(true);
    try {
      const { data: r } = await axios.post(`${API}/revenue/smart-pricing/${propertyId}/recalculate`);
      toast.success(r.message);
    } catch { toast.error("Recalculation failed"); }
    setRecalculating(false);
  };

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><Activity className="w-5 h-5 animate-spin mr-2" />Loading Smart Pricing...</div>;
  if (!data) return null;

  const { kpis, price_evolution, recommendation_calendar, ai_insights, room_types } = data;

  // SVG Chart for Price Evolution
  const chartW = 900, chartH = 200, padL = 50, padR = 20, padT = 20, padB = 30;
  const innerW = chartW - padL - padR, innerH = chartH - padT - padB;
  const prices = price_evolution.map(e => e.recommended);
  const maxP = Math.max(...prices, ...price_evolution.map(e => e.max_limit)) * 1.1;
  const minP = Math.min(...prices, ...price_evolution.map(e => e.min_limit)) * 0.9;
  const scaleX = (i) => padL + (i / Math.max(prices.length - 1, 1)) * innerW;
  const scaleY = (v) => padT + (1 - (v - minP) / (maxP - minP)) * innerH;
  const linePath = prices.map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(p)}`).join(" ");
  const minLine = price_evolution.map((e, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(e.min_limit)}`).join(" ");
  const maxLine = price_evolution.map((e, i) => `${i === 0 ? "M" : "L"} ${scaleX(i)} ${scaleY(e.max_limit)}`).join(" ");

  return (
    <div className="space-y-6" data-testid="rev-smart-pricing">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Smart Pricing Dashboard</h2>
          <p className="text-sm text-stone-500">AI-driven revenue management and price optimization. <span className="text-xs text-stone-400">Currency: GBP (£)</span></p>
        </div>
        <div className="flex items-center gap-3">
          {data.system_active && <Badge className="bg-emerald-100 text-emerald-700 text-xs"><span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 inline-block" />System Active</Badge>}
          <button onClick={recalculate} disabled={recalculating}
            className="flex items-center gap-2 bg-stone-800 hover:bg-stone-900 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="rev-recalculate">
            <RefreshCw className={`w-4 h-4 ${recalculating ? "animate-spin" : ""}`} />{recalculating ? "Calculating..." : "Recalculate Prices"}
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
        Smart Pricing creates <strong>draft recommendations only</strong>. Accept and publish via the Approvals hub to keep audit and resolver snapshots intact.
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="rev-sp-kpis">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 font-medium uppercase tracking-wider">Avg. Daily Rate (30D)</p>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-2xl font-bold text-stone-800">{cur(kpis.avg_daily_rate)}</p>
            <span className={`flex items-center text-xs font-semibold ${kpis.adr_change >= 0 ? "text-emerald-600" : "text-red-500"}`}>
              <TrendingUp className="w-3 h-3 mr-0.5" />{Math.abs(kpis.adr_change)}%
            </span>
          </div>
          <p className="text-[10px] text-stone-400 mt-1">vs. previous 30 days</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 font-medium uppercase tracking-wider">Occupancy Forecast</p>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-2xl font-bold text-stone-800">{kpis.occupancy_forecast}%</p>
            <Badge className="text-[10px] bg-blue-100 text-blue-700">{kpis.occ_trend}</Badge>
          </div>
          <div className="w-full bg-stone-100 rounded-full h-2 mt-2">
            <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${kpis.occupancy_forecast}%` }} />
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 font-medium uppercase tracking-wider">Projected Revenue</p>
          <p className="text-2xl font-bold text-stone-800 mt-1">{cur(kpis.projected_revenue)}</p>
          <p className="text-[10px] text-stone-400 mt-1">Next 30 days based on recommendations</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 font-medium uppercase tracking-wider">Strategy Mode</p>
          <p className="text-2xl font-bold text-violet-700 mt-1">{kpis.strategy_mode}</p>
          <p className="text-[10px] text-stone-400 mt-1">Aggressiveness Factor: {kpis.aggressiveness}x</p>
        </div>
      </div>

      {/* Price Evolution Chart */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-price-evolution">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-stone-800">Price Evolution Forecast</h3>
          {room_types.length > 0 && (
            <Select value={selectedRoomType || room_types[0]?.id} onValueChange={setSelectedRoomType}>
              <SelectTrigger className="w-48 h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>{room_types.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent>
            </Select>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-stone-400 mb-3">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-violet-600 inline-block" /> Recommended Rate</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-stone-300 inline-block border-dashed" /> Min Limit</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-stone-300 inline-block" /> Max Limit</span>
        </div>
        <div className="overflow-x-auto">
          <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full" style={{ minWidth: "700px" }}>
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map(frac => {
              const y = padT + (1 - frac) * innerH;
              const val = Math.round(minP + frac * (maxP - minP));
              return (
                <g key={frac}>
                  <line x1={padL} x2={chartW - padR} y1={y} y2={y} stroke="#e5e7eb" strokeWidth="1" />
                  <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[9px]" fill="#9ca3af">£{val}</text>
                </g>
              );
            })}
            {/* Min/Max bands */}
            <path d={maxLine} fill="none" stroke="#d1d5db" strokeWidth="1" strokeDasharray="4 4" />
            <path d={minLine} fill="none" stroke="#d1d5db" strokeWidth="1" strokeDasharray="4 4" />
            {/* Main price line */}
            <path d={linePath} fill="none" stroke="#7c3aed" strokeWidth="2.5" strokeLinejoin="round" />
            {/* Data points */}
            {prices.map((p, i) => (
              <g key={i}>
                <circle cx={scaleX(i)} cy={scaleY(p)} r="3" fill="#7c3aed" />
                {(i % 3 === 0 || i === prices.length - 1) && (
                  <text x={scaleX(i)} y={scaleY(p) - 8} textAnchor="middle" className="text-[8px]" fill="#7c3aed" fontWeight="600">£{Math.round(p)}</text>
                )}
              </g>
            ))}
            {/* X-axis labels */}
            {price_evolution.map((e, i) => i % 3 === 0 && (
              <text key={i} x={scaleX(i)} y={chartH - 5} textAnchor="middle" className="text-[8px]" fill="#9ca3af">
                {new Date(e.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}
              </text>
            ))}
          </svg>
        </div>
      </div>

      {/* Recommendation Calendar + AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl p-5" data-testid="rev-rec-calendar">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-stone-800">Recommendation Calendar</h3>
            <div className="flex items-center gap-3 text-xs text-stone-400">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-50 border border-red-200" /> High</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-white border border-stone-200" /> Normal</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-50 border border-emerald-200" /> Low</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-stone-500">Room Category</th>
                  {recommendation_calendar[0]?.days.map(d => (
                    <th key={d.date} className={`px-2 py-2 text-center text-xs font-semibold ${d.is_today ? "text-violet-700 bg-violet-50/50" : "text-stone-500"}`}>
                      <div>{d.dow}</div>
                      <div className="text-[10px] text-stone-400">{d.day}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recommendation_calendar.map(rc => (
                  <tr key={rc.room_type_id} className="border-b border-stone-50">
                    <td className="px-3 py-3 font-medium text-stone-700 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${rc.base_rate > 120 ? "bg-amber-400" : rc.base_rate > 100 ? "bg-emerald-400" : "bg-blue-400"}`} />
                        {rc.room_type_name}
                      </div>
                    </td>
                    {rc.days.map(d => (
                      <td key={d.date} className={`px-2 py-2 text-center ${
                        d.level === "HIGH" ? "bg-red-50" : d.level === "LOW" ? "bg-emerald-50" : ""
                      }`}>
                        <div className="font-bold text-stone-800 text-sm">{cur(d.price)}</div>
                        <div className={`text-[9px] font-semibold mt-0.5 ${
                          d.level === "HIGH" ? "text-red-500" : d.level === "LOW" ? "text-emerald-600" : "text-stone-400"
                        }`}>{d.level}</div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Insights */}
        <div className="bg-stone-800 rounded-2xl p-5 text-white" data-testid="rev-ai-insights">
          <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" /> AI Insights
          </h3>
          <div className="space-y-4">
            {ai_insights.map((insight, i) => (
              <div key={i} className={`rounded-xl p-4 ${
                insight.type === "demand" ? "bg-emerald-900/30 border border-emerald-700/30" :
                insight.type === "alert" ? "bg-amber-900/30 border border-amber-700/30" :
                "bg-stone-700/50 border border-stone-600/30"
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {insight.type === "demand" ? <Zap className="w-4 h-4 text-amber-400" /> :
                   insight.type === "alert" ? <AlertTriangle className="w-4 h-4 text-amber-400" /> :
                   <Info className="w-4 h-4 text-blue-400" />}
                  <span className="font-semibold text-sm">{insight.title}</span>
                </div>
                <p className="text-xs text-stone-300 leading-relaxed">{insight.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
