import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Zap, CheckCircle, XCircle, ArrowUpRight, ArrowDownRight, RefreshCw, Check, X, CheckCheck } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

const PRIORITY_STYLES = {
  critical: { bg: "bg-red-50", border: "border-red-200", badge: "bg-red-500 text-white" },
  high: { bg: "bg-amber-50", border: "border-amber-200", badge: "bg-amber-500 text-white" },
  medium: { bg: "bg-blue-50", border: "border-blue-200", badge: "bg-blue-500 text-white" },
  low: { bg: "bg-stone-50", border: "border-stone-200", badge: "bg-stone-400 text-white" },
};

export const RateRecommendations = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accepted, setAccepted] = useState(new Set());
  const [applyingAll, setApplyingAll] = useState(false);

  const load = () => { setLoading(true); axios.get(`${API}/revenue/intelligence/${propertyId}/recommendations`).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false)); };
  useEffect(() => { load(); }, [propertyId]);

  const accept = async (rec) => {
    try {
      await axios.post(`${API}/revenue/intelligence/${propertyId}/recommendations/accept`, { date: rec.date, rate: rec.recommended_rate });
      setAccepted(prev => new Set([...prev, rec.id]));
      toast.success(`Rate for ${rec.date} set to ${cur(rec.recommended_rate)}`);
    } catch { toast.error("Failed"); }
  };

  const acceptAll = async () => {
    if (!data?.recommendations?.length) return;
    setApplyingAll(true);
    try {
      const pending = data.recommendations.filter(r => !accepted.has(r.id));
      const { data: result } = await axios.post(`${API}/revenue/intelligence/${propertyId}/recommendations/accept-all`, { recommendations: pending });
      setAccepted(new Set(data.recommendations.map(r => r.id)));
      toast.success(result.message);
    } catch { toast.error("Failed"); }
    setApplyingAll(false);
  };

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Analyzing rates...</div>;
  if (!data) return null;

  const { recommendations, kpis } = data;

  return (
    <div className="space-y-5" data-testid="rate-recommendations">
      <div className="bg-gradient-to-r from-violet-900 via-purple-900 to-violet-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Zap className="w-5 h-5 text-amber-300" /></div>
            <div><h2 className="text-lg font-bold">AI Rate Recommendations</h2><p className="text-xs text-white/40">Daily to-do list | One-click accept or let AI handle all</p></div>
          </div>
          <button onClick={acceptAll} disabled={applyingAll || recommendations.length === 0}
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="accept-all-recs">
            {applyingAll ? <RefreshCw className="w-4 h-4 animate-spin" /> : <CheckCheck className="w-4 h-4" />}
            Accept All ({recommendations.length})
          </button>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-xl font-bold">{kpis.total_actions}</p><p className="text-[8px] text-white/30">Actions</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-xl font-bold text-emerald-300">{kpis.increases}</p><p className="text-[8px] text-white/30">Increases</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-xl font-bold text-red-300">{kpis.decreases}</p><p className="text-[8px] text-white/30">Decreases</p></div>
          <div className="bg-white/5 rounded-xl p-3 text-center"><p className="text-xl font-bold text-amber-300">{kpis.critical}</p><p className="text-[8px] text-white/30">Critical</p></div>
        </div>
      </div>

      {/* Recommendation Cards */}
      <div className="space-y-2">
        {recommendations.map(rec => {
          const ps = PRIORITY_STYLES[rec.priority] || PRIORITY_STYLES.low;
          const done = accepted.has(rec.id);
          return (
            <div key={rec.id} className={`${ps.bg} border ${ps.border} rounded-xl p-4 ${done ? "opacity-50" : ""}`} data-testid={`rec-${rec.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-center min-w-[60px]">
                    <p className="text-xs font-bold text-stone-800">{rec.dow}</p>
                    <p className="text-lg font-bold text-stone-800">{new Date(rec.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div>
                      <p className="text-xs text-stone-400">Current</p>
                      <p className="text-sm font-bold text-stone-600">{cur(rec.current_rate)}</p>
                    </div>
                    <div className={`flex items-center gap-1 text-lg font-bold ${rec.action === "increase" ? "text-emerald-600" : "text-red-500"}`}>
                      {rec.action === "increase" ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownRight className="w-5 h-5" />}
                    </div>
                    <div>
                      <p className="text-xs text-stone-400">Recommended</p>
                      <p className="text-sm font-bold text-violet-700">{cur(rec.recommended_rate)}</p>
                    </div>
                    <Badge className={`text-[9px] ${ps.badge}`}>{rec.priority}</Badge>
                    <span className={`text-xs font-bold ${rec.diff > 0 ? "text-emerald-600" : "text-red-500"}`}>{rec.diff > 0 ? "+" : ""}{cur(rec.diff)} ({rec.diff_pct > 0 ? "+" : ""}{rec.diff_pct}%)</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {rec.event && <Badge className="bg-red-100 text-red-700 text-[9px]">{rec.event}</Badge>}
                  {done ? (
                    <Badge className="bg-emerald-100 text-emerald-700 text-xs">Applied</Badge>
                  ) : (
                    <button onClick={() => accept(rec)} className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold" data-testid={`accept-${rec.id}`}>
                      <Check className="w-3 h-3" /> Accept
                    </button>
                  )}
                </div>
              </div>
              {rec.reasons?.length > 0 && <div className="mt-2 flex items-center gap-2 flex-wrap">{rec.reasons.map((r, i) => <span key={i} className="text-[10px] text-stone-500 bg-white/50 px-2 py-0.5 rounded">{r}</span>)}</div>}
            </div>
          );
        })}
        {recommendations.length === 0 && <div className="text-center py-12 text-stone-400"><CheckCircle className="w-10 h-10 mx-auto mb-2 text-emerald-300" /><p className="font-medium">All rates are optimized!</p><p className="text-sm">No recommendations needed right now.</p></div>}
      </div>
    </div>
  );
};
