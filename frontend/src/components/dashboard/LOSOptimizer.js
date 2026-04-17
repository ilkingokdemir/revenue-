import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, BarChart3, Calendar, TrendingUp, Clock, Lightbulb } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PRIORITY_COLORS = { high: "bg-red-500/20 text-red-400 border-red-500/30", medium: "bg-amber-500/20 text-amber-400 border-amber-500/30", low: "bg-stone-700 text-stone-400 border-stone-600" };

export const LOSOptimizer = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/los-optimizer/${propertyId || "all"}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading LOS Analysis...</div>;
  if (!data || data.error) return <div className="text-center py-20 text-stone-400">No booking data available</div>;

  const { total_bookings, avg_los, avg_rate, distribution, dow_analysis, source_analysis, recommendations } = data;

  // Chart for distribution
  const maxBk = Math.max(...distribution.map(d => d.bookings), 1);

  return (
    <div className="space-y-5" data-testid="los-optimizer">
      {/* Header KPIs */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Clock className="w-5 h-5 text-cyan-400" /></div>
          <div>
            <h2 className="text-lg font-bold" data-testid="los-title">Length of Stay Optimizer</h2>
            <p className="text-xs text-white/40">Analyze stay patterns to maximize RevPAR</p>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-2xl font-black text-cyan-400">{avg_los}</p>
            <p className="text-[8px] text-white/30 uppercase">Avg LOS (nights)</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-2xl font-black text-white">£{avg_rate}</p>
            <p className="text-[8px] text-white/30 uppercase">Avg Rate/Night</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-2xl font-black text-white">{total_bookings}</p>
            <p className="text-[8px] text-white/30 uppercase">Total Bookings</p>
          </div>
          <div className="bg-white/5 rounded-xl p-3 text-center">
            <p className="text-2xl font-black text-amber-400">{recommendations.length}</p>
            <p className="text-[8px] text-white/30 uppercase">Recommendations</p>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="space-y-3" data-testid="los-recommendations">
          <h3 className="text-sm font-bold text-stone-800 flex items-center gap-1.5"><Lightbulb className="w-4 h-4 text-amber-500" />Recommendations</h3>
          {recommendations.map((r, i) => (
            <div key={i} className={`bg-stone-900 border rounded-xl p-4 ${PRIORITY_COLORS[r.priority]}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-white">{r.title}</span>
                <Badge className={`text-[9px] ${r.priority === "high" ? "bg-red-500 text-white" : r.priority === "medium" ? "bg-amber-500 text-white" : "bg-stone-600 text-white"}`}>{r.priority}</Badge>
              </div>
              <p className="text-xs text-stone-400">{r.description}</p>
              <p className="text-[10px] text-stone-500 mt-1">{r.metric}</p>
            </div>
          ))}
        </div>
      )}

      {/* LOS Distribution */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="los-distribution">
        <h3 className="text-sm font-bold text-white mb-3">Stay Length Distribution</h3>
        <div className="space-y-2">
          {distribution.filter(d => d.bookings > 0).map(d => (
            <div key={d.nights} className="flex items-center gap-3">
              <span className="text-xs text-stone-400 w-16 text-right">{d.nights} night{d.nights > 1 ? "s" : ""}</span>
              <div className="flex-1 bg-stone-800 rounded-full h-6 overflow-hidden relative">
                <div className="h-full bg-cyan-500 rounded-full flex items-center px-2"
                  style={{ width: `${Math.max((d.bookings / maxBk) * 100, 8)}%` }}>
                  <span className="text-[10px] font-bold text-white">{d.bookings}</span>
                </div>
              </div>
              <span className="text-[10px] text-stone-500 w-10 text-right">{d.pct_of_total}%</span>
              <span className="text-[10px] text-stone-500 w-14 text-right">£{d.avg_rate_per_night}/n</span>
            </div>
          ))}
        </div>
      </div>

      {/* DOW + Source side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* DOW Analysis */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="dow-analysis">
          <h3 className="text-sm font-bold text-white mb-3">Check-in Day Analysis</h3>
          <table className="w-full text-xs">
            <thead><tr className="text-stone-500 border-b border-stone-700"><th className="text-left py-1.5">Day</th><th className="text-right py-1.5">Avg LOS</th><th className="text-right py-1.5">Bookings</th><th className="text-right py-1.5">Common</th></tr></thead>
            <tbody>
              {dow_analysis.map(d => (
                <tr key={d.dow} className="border-b border-stone-800/50">
                  <td className="py-1.5 text-white font-medium">{d.dow}</td>
                  <td className="py-1.5 text-right text-cyan-400 font-bold">{d.avg_los}n</td>
                  <td className="py-1.5 text-right text-stone-400">{d.bookings}</td>
                  <td className="py-1.5 text-right text-stone-400">{d.most_common}n</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Source Analysis */}
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="source-analysis">
          <h3 className="text-sm font-bold text-white mb-3">LOS by Booking Source</h3>
          <table className="w-full text-xs">
            <thead><tr className="text-stone-500 border-b border-stone-700"><th className="text-left py-1.5">Source</th><th className="text-right py-1.5">Avg LOS</th><th className="text-right py-1.5">Bookings</th><th className="text-right py-1.5">Room Nights</th></tr></thead>
            <tbody>
              {source_analysis.map(s => (
                <tr key={s.source} className="border-b border-stone-800/50">
                  <td className="py-1.5 text-white font-medium">{s.source}</td>
                  <td className="py-1.5 text-right text-cyan-400 font-bold">{s.avg_los}n</td>
                  <td className="py-1.5 text-right text-stone-400">{s.bookings}</td>
                  <td className="py-1.5 text-right text-stone-400">{s.total_room_nights}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
