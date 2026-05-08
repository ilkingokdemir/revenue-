import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, DollarSign, TrendingUp, TrendingDown, BarChart3, ArrowRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const FinancePL = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    Promise.all([
      axios.get(`${API}/finance/pl/${pid}`),
      axios.get(`${API}/finance/pl/${pid}/trend?months=6`),
    ]).then(([pl, tr]) => {
      setData(pl.data); setTrend(tr.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [pid]);

  if (loading || !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Finance...</div>;

  const k = data.kpis;
  const maxTrend = trend ? Math.max(...trend.trend.map(t => Math.max(t.revenue, t.costs)), 1) : 1;

  return (
    <div className="space-y-5" data-testid="finance-pl">
      {/* KPI Row */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <h2 className="text-lg font-bold mb-4" data-testid="finance-title">Canonical Profit Overview</h2>
        <div className="flex flex-wrap gap-4 text-xs">
          <div className="flex items-center gap-2"><span className="text-white/40">Gross</span><span className="font-bold">{cur(k.gross)}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/40">Room</span><span className="font-bold">{cur(k.room_revenue)}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/40">ADR</span><span className="font-bold">{cur(k.adr)}</span></div>
          <div className="flex items-center gap-2"><span className="text-red-400">Comm</span><span className="font-bold text-red-400">{cur(k.commission)}</span></div>
          <div className="flex items-center gap-2"><span className="text-red-400">Expenses</span><span className="font-bold text-red-400">{cur(k.total_costs)}</span></div>
          <div className="flex items-center gap-2"><span className="text-white/40">Payroll</span><span className="font-bold">{cur(k.payroll)}</span></div>
          <div className="flex items-center gap-2"><span className={k.operating_profit >= 0 ? "text-emerald-400" : "text-red-400"}>Net</span><span className={`font-bold ${k.operating_profit >= 0 ? "text-emerald-400" : "text-red-400"}`}>{k.operating_profit >= 0 ? "+" : ""}{cur(k.operating_profit)}</span></div>
        </div>
      </div>

      {/* Operating Ledger */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Costs */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="cost-ledger">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Operating Costs</h3>
          <p className="text-[10px] text-stone-400 mb-3">{data.cost_items.length} items — {cur(k.total_costs)}</p>
          <div className="space-y-2">
            {data.cost_items.map((c, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-stone-50">
                <div>
                  <p className="text-xs font-medium text-stone-700">{c.description || c.category}</p>
                  <Badge className={`text-[8px] ${c.status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{c.status}</Badge>
                </div>
                <span className="text-sm font-bold text-red-600">{cur(c.amount)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Revenue */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="revenue-ledger">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Room Revenue</h3>
          <p className="text-[10px] text-stone-400 mb-3">{data.revenue_items.length} sources — {cur(k.room_revenue)}</p>
          <div className="space-y-2">
            {data.revenue_items.map((r, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-stone-50">
                <div>
                  <p className="text-xs font-medium text-stone-700">{r.source}</p>
                  <p className="text-[10px] text-stone-400">{r.bookings} bookings</p>
                </div>
                <span className="text-sm font-bold text-emerald-600">{cur(r.revenue)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Operating Profit Box */}
      <div className={`rounded-2xl p-6 text-center ${k.operating_profit >= 0 ? "bg-emerald-50 border border-emerald-200" : "bg-red-50 border border-red-200"}`} data-testid="profit-box">
        <p className="text-[10px] text-stone-500 uppercase font-bold">Operating Profit / Loss</p>
        <p className={`text-4xl font-black ${k.operating_profit >= 0 ? "text-emerald-600" : "text-red-600"}`}>{k.operating_profit >= 0 ? "+" : ""}{cur(k.operating_profit)}</p>
        <p className="text-xs text-stone-500 mt-1">Gross revenue minus expenses, payroll and commission. Margin: {k.margin_pct}%</p>
      </div>

      {/* 6-Month Trend */}
      {trend && trend.trend.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="financial-trend">
          <h3 className="text-sm font-bold text-stone-800 mb-4">6-Month Financial Overview</h3>
          <div className="flex items-center gap-4 text-[10px] text-stone-400 mb-3">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-cyan-500" /> Revenue</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-400" /> Costs</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-blue-500" /> Profit</span>
          </div>
          <div className="flex items-end gap-3 h-48">
            {trend.trend.map(t => (
              <div key={t.month} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex gap-0.5 items-end" style={{ height: "160px" }}>
                  <div className="flex-1 bg-cyan-500 rounded-t-sm" style={{ height: `${(t.revenue / maxTrend) * 100}%` }} title={`Revenue: ${cur(t.revenue)}`} />
                  <div className="flex-1 bg-red-400 rounded-t-sm" style={{ height: `${(t.costs / maxTrend) * 100}%` }} title={`Costs: ${cur(t.costs)}`} />
                  <div className={`flex-1 rounded-t-sm ${t.profit >= 0 ? "bg-blue-500" : "bg-orange-500"}`} style={{ height: `${(Math.abs(t.profit) / maxTrend) * 100}%` }} title={`Profit: ${cur(t.profit)}`} />
                </div>
                <span className="text-[8px] text-stone-400">{t.label.slice(0, 3)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
