import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Zap, Play, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Minus, CheckCircle, AlertTriangle, BarChart3, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const DynamicPricingEngine = ({ propertyId }) => {
  const [preview, setPreview] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [selectedRT, setSelectedRT] = useState(0);

  const calculate = async () => {
    setCalculating(true);
    setApplied(false);
    try {
      const { data } = await axios.post(`${API}/revenue/dynamic-pricing/${propertyId}/calculate`, { days: 90 });
      setPreview(data);
      toast.success(`Calculated ${data.summary.total_days} days x ${data.summary.total_room_types} room types`);
    } catch { toast.error("Calculation failed"); }
    setCalculating(false);
  };

  const apply = async () => {
    setApplying(true);
    try {
      const { data } = await axios.post(`${API}/revenue/dynamic-pricing/${propertyId}/apply`, { days: 90 });
      toast.success(data.message);
      setApplied(true);
    } catch { toast.error("Failed to apply"); }
    setApplying(false);
  };

  const s = preview?.summary || {};
  const ds = preview?.data_sources || {};
  const rtData = preview?.room_types?.[selectedRT];
  const prices = rtData?.prices || [];

  return (
    <div className="space-y-6" data-testid="dynamic-pricing-engine">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-900 via-violet-900 to-purple-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center backdrop-blur-sm">
              <Zap className="w-6 h-6 text-amber-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">AI Dynamic Pricing Engine</h2>
              <p className="text-sm text-white/60">Combines market supply, competitors, occupancy, seasonality, lead time & event intelligence for optimal pricing across 90 days</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={calculate} disabled={calculating}
              className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-5 py-2.5 rounded-xl text-sm font-semibold backdrop-blur-sm disabled:opacity-50 transition-all" data-testid="dp-calculate">
              {calculating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
              {calculating ? "Calculating 90 days..." : "Preview Prices"}
            </button>
            {preview && (
              <button onClick={apply} disabled={applying || applied}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                  applied ? "bg-emerald-500 text-white" : "bg-amber-500 hover:bg-amber-600 text-white"
                } disabled:opacity-50`} data-testid="dp-apply">
                {applying ? <RefreshCw className="w-4 h-4 animate-spin" /> : applied ? <CheckCircle className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                {applying ? "Applying..." : applied ? "Applied to Calendar" : "Apply to Calendar"}
              </button>
            )}
          </div>
        </div>

        {/* Data Sources */}
        {preview && (
          <div className="flex items-center gap-4 mt-4 text-xs">
            <span className={`flex items-center gap-1 ${ds.market_supply_dates > 0 ? "text-emerald-300" : "text-red-300"}`}>
              {ds.market_supply_dates > 0 ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              Market Supply: {ds.market_supply_dates} dates
            </span>
            <span className={`flex items-center gap-1 ${ds.competitors_with_prices > 0 ? "text-emerald-300" : "text-amber-300"}`}>
              {ds.competitors_with_prices > 0 ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              Competitor Prices: {ds.competitors_with_prices} dates
            </span>
            <span className={`flex items-center gap-1 ${ds.strategy_configured ? "text-emerald-300" : "text-amber-300"}`}>
              {ds.strategy_configured ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              Pricing Strategy: {ds.strategy_configured ? "Configured" : "Not set"}
            </span>
            <span className={`flex items-center gap-1 ${ds.events_loaded > 0 ? "text-emerald-300" : "text-amber-300"}`}>
              {ds.events_loaded > 0 ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              Event Intelligence: {ds.events_loaded || 0} event days
            </span>
          </div>
        )}
      </div>

      {!preview && !calculating && (
        <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
          <Zap className="w-16 h-16 text-stone-200 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-stone-700 mb-2">Ready to Optimize Your Revenue</h3>
          <p className="text-sm text-stone-400 max-w-md mx-auto mb-6">Click "Preview Prices" to calculate AI-optimized rates for every day across the next 90 days, using all available market data.</p>
          <div className="bg-stone-50 rounded-xl p-4 max-w-lg mx-auto text-left space-y-2 text-xs text-stone-500">
            <p className="font-semibold text-stone-700">The AI combines these data sources:</p>
            <div className="grid grid-cols-2 gap-2">
              {["Market Supply (Booking.com)", "Competitor Hotel Prices", "Your Occupancy Levels", "Day-of-Week Patterns", "Monthly Seasonality", "Lead Time to Check-in", "Event Intelligence (GPT-5.2)", "Aggressiveness Setting", "Min/Max Guardrails"].map(s => (
                <span key={s} className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-emerald-500 flex-shrink-0" />{s}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Summary KPIs */}
      {preview && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="dp-summary">
            <div className="bg-white border border-stone-200 rounded-2xl p-4 text-center">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Days Priced</p>
              <p className="text-2xl font-bold text-stone-800 mt-1">{s.total_days}</p>
            </div>
            <div className="bg-white border border-emerald-100 rounded-2xl p-4 text-center">
              <p className="text-[10px] text-emerald-600 uppercase tracking-wider font-medium">Price Increases</p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{s.increases}</p>
            </div>
            <div className="bg-white border border-red-100 rounded-2xl p-4 text-center">
              <p className="text-[10px] text-red-500 uppercase tracking-wider font-medium">Price Decreases</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{s.decreases}</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl p-4 text-center">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Avg Change</p>
              <p className={`text-2xl font-bold mt-1 ${s.avg_change_pct > 0 ? "text-emerald-600" : s.avg_change_pct < 0 ? "text-red-500" : "text-stone-500"}`}>{s.avg_change_pct > 0 ? "+" : ""}{s.avg_change_pct}%</p>
            </div>
            <div className="bg-white border border-violet-100 rounded-2xl p-4 text-center">
              <p className="text-[10px] text-violet-600 uppercase tracking-wider font-medium">Avg AI Price</p>
              <p className="text-2xl font-bold text-violet-700 mt-1">{cur(s.avg_ai_price)}</p>
            </div>
          </div>

          {/* Room Type Selector */}
          {preview.room_types.length > 1 && (
            <div className="flex items-center gap-2">
              {preview.room_types.map((rt, i) => (
                <button key={rt.room_type_id} onClick={() => setSelectedRT(i)}
                  className={`px-4 py-2 text-sm font-medium rounded-lg ${selectedRT === i ? "bg-violet-600 text-white" : "text-stone-500 bg-white border border-stone-200 hover:bg-stone-50"}`}>
                  {rt.room_type_name} (Base: {cur(rt.base_rate)})
                </button>
              ))}
            </div>
          )}

          {/* 90-Day Price Grid */}
          <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="dp-price-grid">
            <div className="px-5 py-3 bg-stone-50 border-b flex items-center justify-between">
              <span className="font-bold text-stone-800 text-sm">90-Day AI Price Recommendations — {rtData?.room_type_name}</span>
              <div className="flex items-center gap-3 text-[10px] text-stone-400">
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-50 border border-emerald-200" />Increase</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-50 border border-red-200" />Decrease</span>
                <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-white border border-stone-200" />No change</span>
              </div>
            </div>
            <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white z-10">
                  <tr className="border-b">
                    {["Date","Day","Ahead","Base","Current","AI Price","Change","Occ","Market","Comps","Event","Factors"].map(h =>
                      <th key={h} className="px-2 py-2 text-[10px] font-semibold text-stone-500 text-center whitespace-nowrap">{h}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {prices.map(p => {
                    const isUp = p.change_pct > 0;
                    const isDown = p.change_pct < 0;
                    return (
                      <tr key={p.date} className={`border-b border-stone-50 ${
                        p.is_today ? "bg-violet-50/50" : isUp ? "bg-emerald-50/30" : isDown ? "bg-red-50/30" : ""
                      }`}>
                        <td className="px-2 py-1.5 text-stone-700 font-medium whitespace-nowrap text-xs">
                          {new Date(p.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}
                          {p.is_today && <Badge className="ml-1 text-[7px] bg-violet-600 text-white">Today</Badge>}
                        </td>
                        <td className="px-2 py-1.5 text-center text-stone-400 text-xs">{p.dow}</td>
                        <td className="px-2 py-1.5 text-center text-stone-400 text-[10px]">{p.days_ahead}d</td>
                        <td className="px-2 py-1.5 text-center text-stone-400 text-xs">{cur(p.base_rate)}</td>
                        <td className="px-2 py-1.5 text-center text-stone-500 text-xs">{cur(p.current_rate)}</td>
                        <td className="px-2 py-1.5 text-center font-bold text-violet-700">{cur(p.ai_price)}</td>
                        <td className="px-2 py-1.5 text-center">
                          <span className={`flex items-center justify-center gap-0.5 text-xs font-bold ${isUp ? "text-emerald-600" : isDown ? "text-red-500" : "text-stone-400"}`}>
                            {isUp ? <ArrowUpRight className="w-3 h-3" /> : isDown ? <ArrowDownRight className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                            {p.change_pct > 0 ? "+" : ""}{p.change_pct}%
                          </span>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          <span className={`text-[10px] font-semibold ${p.our_occupancy >= 70 ? "text-emerald-600" : p.our_occupancy >= 40 ? "text-amber-500" : "text-red-400"}`}>{p.our_occupancy}%</span>
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          {p.market_unavail !== null ? (
                            <span className={`text-[10px] font-semibold ${p.market_unavail >= 70 ? "text-red-500" : p.market_unavail >= 40 ? "text-amber-500" : "text-emerald-500"}`}>{p.market_unavail}%</span>
                          ) : <span className="text-[10px] text-stone-300">—</span>}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          {p.competitor_avg ? <span className="text-[10px] text-stone-600">{cur(p.competitor_avg)}</span> : <span className="text-[10px] text-stone-300">—</span>}
                        </td>
                        <td className="px-2 py-1.5 text-center">
                          {p.event ? <span className="text-[9px] font-bold text-red-500" title={p.event}>{p.event_impact?.toUpperCase()}</span> : <span className="text-[10px] text-stone-300">—</span>}
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex flex-wrap gap-0.5">
                            {Object.entries(p.breakdown || {}).filter(([k]) => k !== "base").map(([k, v]) => (
                              <span key={k} className="text-[8px] bg-stone-100 text-stone-500 px-1 py-0.5 rounded">{k}: {v}</span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
