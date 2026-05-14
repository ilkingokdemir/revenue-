/**
 * GapPerformanceMiniWidget — Son N batch'in gerçek performansı (apply sonrası).
 * Strategy-bazında revenue uplift karşılaştırması.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { TrendingUp, TrendingDown, Award, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GapPerformanceMiniWidget() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/revenue/market-robot/gap-history/performance-summary?limit=15`);
        if (!cancelled) setData(data);
      } catch { /* noop */ }
      if (!cancelled) setLoading(false);
    };
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="bg-stone-900/40 border border-stone-800 rounded-xl p-3 flex items-center gap-2 text-xs text-stone-500" data-testid="gap-perf-loading">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Performans hesaplanıyor...
      </div>
    );
  }

  if (!data || data.summary.total_batches === 0) return null;

  const { summary, by_strategy } = data;
  const totalUplift = summary.total_revenue_uplift;
  const positive = totalUplift > 0;

  // Best strategy (highest revenue_uplift)
  const best = by_strategy[0];

  return (
    <div className="bg-stone-900/40 border border-stone-800 rounded-xl p-3 space-y-2.5" data-testid="gap-perf-widget">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-amber-400" />
          <span className="text-[11px] font-bold text-stone-200">Gap-Close Performans</span>
          <span className="text-[10px] text-stone-500">son {summary.total_batches} batch</span>
        </div>
        <div className="flex items-center gap-1">
          {positive ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> : <TrendingDown className="w-3.5 h-3.5 text-amber-400" />}
          <span className={`text-xs font-black tabular-nums ${positive ? "text-emerald-300" : "text-amber-300"}`}>
            £{totalUplift >= 0 ? "+" : ""}{totalUplift.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-stone-950/60 rounded-lg p-2" data-testid="gap-perf-bookings">
          <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">Yeni Rez.</p>
          <p className="text-sm font-black text-stone-100 mt-0.5">{summary.total_bookings_after}</p>
        </div>
        <div className="bg-stone-950/60 rounded-lg p-2" data-testid="gap-perf-best-strategy">
          <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">En İyi</p>
          <p className="text-sm font-black text-emerald-300 mt-0.5 capitalize">{best?.strategy || "—"}</p>
        </div>
        <div className="bg-stone-950/60 rounded-lg p-2" data-testid="gap-perf-best-avg">
          <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">Avg/Rez.</p>
          <p className={`text-sm font-black mt-0.5 tabular-nums ${best?.avg_uplift_per_booking >= 0 ? "text-emerald-300" : "text-amber-300"}`}>
            £{best?.avg_uplift_per_booking >= 0 ? "+" : ""}{(best?.avg_uplift_per_booking || 0).toFixed(2)}
          </p>
        </div>
      </div>

      {/* Strategy breakdown */}
      {by_strategy.length > 1 && (
        <div className="space-y-1 pt-1 border-t border-stone-800/60">
          {by_strategy.map(s => (
            <div key={s.strategy} className="flex items-center justify-between text-[10px]" data-testid={`gap-perf-strat-${s.strategy}`}>
              <span className="text-stone-400 capitalize">{s.strategy}</span>
              <div className="flex gap-3 items-center">
                <span className="text-stone-500">{s.bookings} rez.</span>
                <span className={`font-bold tabular-nums ${s.revenue_uplift >= 0 ? "text-emerald-400" : "text-amber-400"}`}>
                  £{s.revenue_uplift >= 0 ? "+" : ""}{s.revenue_uplift.toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
