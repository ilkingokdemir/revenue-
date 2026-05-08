import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, DollarSign, RefreshCw, BarChart3, Calendar } from "lucide-react";
import useLivePolling, { LiveBadge } from "../../hooks/useLivePolling";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const RevenueForecast = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(90);

  const load = useCallback((d) => {
    setLoading(true);
    axios.get(`${API}/revenue/intelligence/${propertyId}/forecast?days=${d}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [propertyId]);
  useEffect(() => { load(days); }, [load, days]);
  // ⚡ Refreshes as new bookings land in the pipeline
  useLivePolling(() => load(days), { intervalMs: 90000 });

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Forecasting revenue...</div>;
  if (!data) return null;

  const { kpis, monthly_forecast, forecast_daily } = data;

  const maxRev = Math.max(...monthly_forecast.map(m => m.projected_revenue), 1);

  return (
    <div className="space-y-5" data-testid="revenue-forecast">
      <div className="bg-gradient-to-r from-emerald-900 via-teal-900 to-emerald-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><DollarSign className="w-5 h-5 text-emerald-300" /></div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2">
                Revenue Forecast Engine
                <LiveBadge seconds={90} color="violet" />
              </h2>
              <p className="text-xs text-white/40">AI-powered projection | {days}-day outlook · auto-updates</p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-white/5 rounded-xl border border-white/10 p-0.5">
            {[30, 60, 90, 180, 365].map(d => (
              <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${days === d ? "bg-emerald-500 text-white" : "text-white/35 hover:text-white/70"}`} data-testid={`forecast-days-${d}`}>{d === 365 ? "1yr" : `${d}d`}</button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white/5 rounded-xl p-4 text-center"><p className="text-[9px] text-white/30 uppercase">Projected Revenue</p><p className="text-2xl font-bold text-emerald-300">{cur(kpis.projected_revenue)}</p><p className="text-[10px] text-emerald-400">+{kpis.yoy_change_pct}% vs last year</p></div>
          <div className="bg-white/5 rounded-xl p-4 text-center"><p className="text-[9px] text-white/30 uppercase">Projected ADR</p><p className="text-2xl font-bold text-white">{cur(kpis.projected_avg_adr)}</p><p className="text-[10px] text-stone-400">Historical: {cur(kpis.historical_adr)}</p></div>
          <div className="bg-white/5 rounded-xl p-4 text-center"><p className="text-[9px] text-white/30 uppercase">Projected Occupancy</p><p className="text-2xl font-bold text-white">{kpis.projected_avg_occ}%</p><p className="text-[10px] text-stone-400">Historical: {kpis.historical_occupancy}%</p></div>
          <div className="bg-white/5 rounded-xl p-4 text-center"><p className="text-[9px] text-white/30 uppercase">RevPAR</p><p className="text-2xl font-bold text-amber-300">{cur(kpis.projected_revpar)}</p><p className="text-[10px] text-stone-400">{kpis.event_days} event days</p></div>
        </div>
      </div>

      {/* Monthly Revenue Bars */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="forecast-monthly">
        <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2"><Calendar className="w-4 h-4 text-stone-400" /> Monthly Revenue Projection</h3>
        <div className="space-y-2">
          {monthly_forecast.map(m => (
            <div key={m.month} className="flex items-center gap-3">
              <span className="w-16 text-xs font-bold text-stone-600">{m.label}</span>
              <div className="flex-1 bg-stone-100 rounded-full h-7 overflow-hidden relative">
                <div className="h-7 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all" style={{ width: `${(m.projected_revenue / maxRev) * 100}%` }} />
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mix-blend-difference">{cur(m.projected_revenue)}</span>
              </div>
              <div className="w-16 text-right"><span className="text-xs text-stone-400">{m.avg_occupancy}% occ</span></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
