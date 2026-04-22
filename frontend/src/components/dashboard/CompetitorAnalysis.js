import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Minus, Lightbulb, Target, AlertTriangle, CheckCircle, RefreshCw, Users, Zap } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const POSITION_STYLES = {
  premium: { bg: "bg-violet-50", border: "border-violet-200", text: "text-violet-700", label: "Premium" },
  above_avg: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-700", label: "Above Avg" },
  competitive: { bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-700", label: "Competitive" },
  undercut: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", label: "Undercut" },
  unknown: { bg: "bg-stone-50", border: "border-stone-200", text: "text-stone-500", label: "No Data" },
};

const INSIGHT_STYLES = {
  opportunity: { bg: "bg-emerald-900/30", border: "border-emerald-700/30", icon: TrendingUp, iconColor: "text-emerald-400" },
  warning: { bg: "bg-amber-900/30", border: "border-amber-700/30", icon: AlertTriangle, iconColor: "text-amber-400" },
  success: { bg: "bg-blue-900/30", border: "border-blue-700/30", icon: CheckCircle, iconColor: "text-blue-400" },
  info: { bg: "bg-stone-700/50", border: "border-stone-600/30", icon: Lightbulb, iconColor: "text-stone-400" },
};

export const CompetitorAnalysis = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/competitor-analysis`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setLoading(false); });
  };
  useEffect(() => { load(); }, [propertyId]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Analysis...</div>;
  if (!data) return null;

  const { comparison, insights, kpis, competitors_count } = data;

  // Chart: Our price vs comp avg as horizontal bars
  const chartData = comparison.filter(c => c.comp_avg);
  const maxPrice = Math.max(...chartData.map(c => Math.max(c.our_price, c.comp_avg || 0)), 1);

  return (
    <div className="space-y-6" data-testid="competitor-analysis">
      {/* Empty State CTA when no competitors tracked */}
      {competitors_count === 0 && (
        <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-400/30 rounded-2xl p-5 flex items-center justify-between gap-4" data-testid="no-competitors-cta">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-500/20 rounded-lg flex items-center justify-center shrink-0">
              <BarChart3 className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="font-bold text-amber-900 text-sm">No competitors linked yet</p>
              <p className="text-xs text-amber-700/80 mt-0.5">Add Booking.com hotels to unlock competitor pricing, Comp Avg/Min/Max and rate positioning.</p>
            </div>
          </div>
          <button onClick={() => window.dispatchEvent(new CustomEvent("market-robot-goto", { detail: { tab: "competitors-tab" } }))}
            className="shrink-0 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold rounded-lg whitespace-nowrap" data-testid="analysis-add-competitor">
            + Add Competitor
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-stone-800">Competitor Analysis</h3>
            <p className="text-xs text-stone-400">Deep insights from competitors, market data & event intelligence</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-2 border border-stone-200 text-stone-600 px-4 py-2 rounded-xl text-sm font-medium hover:bg-stone-50" data-testid="analysis-refresh">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="analysis-kpis">
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Our Avg Rate</p>
          <p className="text-2xl font-bold text-stone-800 mt-1">{cur(kpis.our_avg_rate)}</p>
          <p className="text-xs text-stone-400 mt-1">Next 14 days</p>
        </div>
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">Competitor Avg</p>
          <p className="text-2xl font-bold text-stone-800 mt-1">{kpis.competitor_avg_rate ? cur(kpis.competitor_avg_rate) : "No data"}</p>
          <p className="text-xs text-stone-400 mt-1">{competitors_count} hotels tracked</p>
        </div>
        <div className={`rounded-2xl p-5 border ${POSITION_STYLES[kpis.position_label?.toLowerCase()?.replace(" ", "_")]?.bg || "bg-white"} ${POSITION_STYLES[kpis.position_label?.toLowerCase()?.replace(" ", "_")]?.border || "border-stone-200"}`}>
          <p className="text-[10px] text-stone-500 uppercase tracking-wider font-medium">Price Position</p>
          <p className={`text-2xl font-bold mt-1 ${POSITION_STYLES[kpis.position_label?.toLowerCase()?.replace(" ", "_")]?.text || "text-stone-700"}`}>
            {kpis.position_label}
          </p>
          <p className="text-xs text-stone-400 mt-1">{kpis.price_position_pct > 0 ? "+" : ""}{kpis.price_position_pct}% vs competitors</p>
        </div>
        <div className={`rounded-2xl p-5 border ${kpis.high_priority_insights > 0 ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200"}`}>
          <p className="text-[10px] text-stone-500 uppercase tracking-wider font-medium">Action Items</p>
          <p className={`text-2xl font-bold mt-1 ${kpis.high_priority_insights > 0 ? "text-red-500" : "text-emerald-600"}`}>{kpis.high_priority_insights}</p>
          <p className="text-xs text-stone-400 mt-1">High priority insights</p>
        </div>
      </div>

      {/* Price Comparison Chart */}
      {chartData.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="analysis-chart">
          <h4 className="font-bold text-stone-800 mb-1">Your Rate vs Competitor Average</h4>
          <div className="flex items-center gap-4 text-xs text-stone-400 mb-4">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-indigo-500" /> Your Rate</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-stone-300" /> Competitor Avg</span>
            <span className="flex items-center gap-1"><span className="w-3 h-1 bg-red-400 rounded" /> Demand Level</span>
          </div>
          <div className="space-y-2">
            {chartData.map(c => {
              const ourW = (c.our_price / maxPrice) * 100;
              const compW = ((c.comp_avg || 0) / maxPrice) * 100;
              const ps = POSITION_STYLES[c.position] || POSITION_STYLES.unknown;
              return (
                <div key={c.date} className="flex items-center gap-3">
                  <span className="w-14 text-xs text-stone-500 font-medium flex-shrink-0">
                    {new Date(c.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", day: "numeric" })}
                  </span>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-stone-100 rounded-full h-4 overflow-hidden relative">
                        <div className="h-4 rounded-full bg-indigo-500 transition-all" style={{ width: `${ourW}%` }} />
                      </div>
                      <span className="text-xs font-bold text-indigo-700 w-14 text-right">{cur(c.our_price)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-stone-100 rounded-full h-3 overflow-hidden relative">
                        <div className="h-3 rounded-full bg-stone-300 transition-all" style={{ width: `${compW}%` }} />
                      </div>
                      <span className="text-[10px] text-stone-500 w-14 text-right">{cur(c.comp_avg)}</span>
                    </div>
                  </div>
                  <Badge className={`text-[8px] w-16 justify-center ${ps.bg} ${ps.text} ${ps.border}`}>{ps.label}</Badge>
                  <div className={`w-2 h-8 rounded-full ${c.demand_level === "high" ? "bg-red-400" : c.demand_level === "moderate" ? "bg-amber-400" : "bg-emerald-400"}`} title={`${c.demand_level} demand`} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Detailed Comparison Table */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="analysis-table">
        <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Detailed Price Comparison</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-stone-50/50">
                {["Date", "Our Rate", "Comp Avg", "Comp Min", "Comp Max", "# Comps", "Diff", "Position", "Demand"].map(h => (
                  <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparison.map(c => {
                const ps = POSITION_STYLES[c.position] || POSITION_STYLES.unknown;
                return (
                  <tr key={c.date} className={`border-b border-stone-50 ${c.demand_level === "high" ? "bg-red-50/20" : ""}`}>
                    <td className="px-3 py-2 font-medium text-stone-700 text-xs whitespace-nowrap">
                      {new Date(c.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
                    </td>
                    <td className="px-3 py-2 text-center font-bold text-indigo-700">{cur(c.our_price)}</td>
                    <td className="px-3 py-2 text-center text-stone-600">{c.comp_avg ? cur(c.comp_avg) : "—"}</td>
                    <td className="px-3 py-2 text-center text-stone-400 text-xs">{c.comp_min ? cur(c.comp_min) : "—"}</td>
                    <td className="px-3 py-2 text-center text-stone-400 text-xs">{c.comp_max ? cur(c.comp_max) : "—"}</td>
                    <td className="px-3 py-2 text-center text-stone-400 text-xs">{c.comp_count}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-xs font-bold flex items-center justify-center gap-0.5 ${c.diff_pct > 0 ? "text-violet-600" : c.diff_pct < 0 ? "text-red-500" : "text-stone-400"}`}>
                        {c.diff_pct > 0 ? <ArrowUpRight className="w-3 h-3" /> : c.diff_pct < 0 ? <ArrowDownRight className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                        {c.diff_pct > 0 ? "+" : ""}{c.diff_pct}%
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <Badge className={`text-[9px] ${ps.bg} ${ps.text}`}>{ps.label}</Badge>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] font-bold ${c.demand_level === "high" ? "text-red-500" : c.demand_level === "moderate" ? "text-amber-500" : "text-emerald-500"}`}>
                        {c.demand_level?.toUpperCase()}
                      </span>
                      {c.market_unavail !== null && c.market_unavail !== undefined && (
                        <span className="text-[9px] text-stone-400 ml-1">({c.market_unavail}%)</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI Insights */}
      <div className="bg-stone-800 rounded-2xl p-6 text-white" data-testid="analysis-insights">
        <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-400" /> Robot Intelligence Insights
          <Badge className="bg-white/10 text-white/70 text-[10px]">{insights.length} findings</Badge>
        </h3>
        <div className="space-y-3">
          {insights.map((insight, i) => {
            const style = INSIGHT_STYLES[insight.type] || INSIGHT_STYLES.info;
            const Icon = style.icon;
            return (
              <div key={i} className={`rounded-xl p-4 ${style.bg} border ${style.border}`}>
                <div className="flex items-start gap-3">
                  <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${style.iconColor}`} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{insight.title}</span>
                      <Badge className={`text-[8px] ${insight.priority === "high" ? "bg-red-500/30 text-red-300" : insight.priority === "medium" ? "bg-amber-500/30 text-amber-300" : "bg-stone-500/30 text-stone-300"}`}>
                        {insight.priority}
                      </Badge>
                    </div>
                    <p className="text-xs text-stone-300 mt-1">{insight.desc}</p>
                    {insight.action && (
                      <div className="flex items-center gap-1.5 mt-2 text-xs text-amber-300">
                        <Target className="w-3 h-3" />
                        <span>{insight.action}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
