import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import {
  RefreshCw, TrendingUp, TrendingDown, DollarSign, AlertTriangle,
  Calendar, ArrowDownCircle, ArrowUpCircle, Activity, Wallet,
  Sparkles, Clock, CheckCircle2, TrendingUp as Boost, Shield, Zap,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ITEM_KIND_STYLE = {
  booking:            { color: "#10b981", label: "Booking",   bg: "bg-emerald-100 text-emerald-700" },
  recurring_invoice:  { color: "#06b6d4", label: "Invoice",   bg: "bg-cyan-100 text-cyan-700" },
  recurring_expense:  { color: "#f59e0b", label: "Recurring", bg: "bg-amber-100 text-amber-700" },
  expense:            { color: "#ef4444", label: "Expense",   bg: "bg-red-100 text-red-700" },
  payroll_estimate:   { color: "#8b5cf6", label: "Payroll",   bg: "bg-violet-100 text-violet-700" },
};

export const CashFlowForecast = ({ propertyId, user }) => {
  const [days, setDays] = useState(30);
  const [opening, setOpening] = useState(10000);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedDate, setExpandedDate] = useState(null);
  const [aiRecs, setAiRecs] = useState([]);
  const [aiAt, setAiAt] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);

  const pid = propertyId || "all";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/finance/cash-flow-forecast/${pid}?days=${days}&opening_balance=${opening}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, days, opening]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  // Load cached AI recs on mount
  useEffect(() => {
    axios.get(`${API}/finance/cash-flow-forecast/${pid}/ai-recommendations/latest`)
      .then(r => {
        setAiRecs(r.data.recommendations || []);
        setAiAt(r.data.generated_at);
      })
      .catch(() => {});
  }, [pid]);

  const generateAI = async () => {
    if (!data) return;
    setAiLoading(true);
    try {
      const { data: r } = await axios.post(`${API}/finance/cash-flow-forecast/${pid}/ai-recommendations`, { forecast: data });
      if (r.error) {
        toast.error(r.error);
      } else {
        setAiRecs(r.recommendations || []);
        setAiAt(r.generated_at);
        toast.success(`Generated ${r.recommendations?.length || 0} recommendations`);
      }
    } catch (e) {
      toast.error("AI generation failed");
    }
    setAiLoading(false);
  };

  if (loading && !data) return (
    <div className="flex items-center justify-center py-20 text-stone-400" data-testid="cashflow-forecast">
      <RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading forecast...
    </div>
  );
  if (!data) return null;

  const fmt = (n) => `£${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  const chartData = data.days.map(d => ({
    date: d.date.slice(5),  // MM-DD
    balance: d.running_balance,
    inflow: d.inflows,
    outflow: -d.outflows,
  }));

  // Find significant event dates (top 5 by magnitude)
  const significant = [...data.days]
    .filter(d => d.inflows > 0 || d.outflows > 0)
    .sort((a, b) => (b.inflows + b.outflows) - (a.inflows + a.outflows))
    .slice(0, 8);

  return (
    <div className="space-y-5" data-testid="cashflow-forecast">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="cashflow-title">Cash Flow Forecast</h2>
          <Badge className="bg-stone-100 text-stone-600 text-[10px]">{data.start} → {data.end}</Badge>
          {data.at_risk && (
            <Badge className="bg-red-100 text-red-700 text-[10px] flex items-center gap-1" data-testid="at-risk-badge">
              <AlertTriangle className="w-2.5 h-2.5" />Goes negative on {data.lowest_date}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <label className="text-xs font-semibold text-stone-600">Opening £</label>
            <Input type="number" value={opening} onChange={e => setOpening(parseFloat(e.target.value) || 0)} className="h-8 w-28 text-xs" data-testid="opening-balance-input" />
          </div>
          <div className="flex items-center gap-1 bg-stone-100 rounded-lg p-0.5">
            {[30, 60, 90].map(d => (
              <button key={d} onClick={() => setDays(d)} data-testid={`period-${d}`}
                className={`px-3 py-1 text-[11px] font-semibold rounded-md ${days === d ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-5 gap-3" data-testid="cashflow-kpis">
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center">
          <Wallet className="w-4 h-4 mx-auto mb-1 text-stone-500" />
          <p className="text-xl font-black text-stone-700">{fmt(data.opening_balance)}</p>
          <p className="text-[10px] text-stone-500">Opening</p>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
          <ArrowUpCircle className="w-4 h-4 mx-auto mb-1 text-emerald-600" />
          <p className="text-xl font-black text-emerald-700">{fmt(data.total_inflows)}</p>
          <p className="text-[10px] text-emerald-600">Inflows ({data.counts.bookings + data.counts.recurring_invoices})</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
          <ArrowDownCircle className="w-4 h-4 mx-auto mb-1 text-red-600" />
          <p className="text-xl font-black text-red-700">{fmt(data.total_outflows)}</p>
          <p className="text-[10px] text-red-600">Outflows</p>
        </div>
        <div className={`border-2 rounded-xl p-4 text-center ${data.ending_balance >= data.opening_balance ? "bg-emerald-50 border-emerald-300" : "bg-amber-50 border-amber-300"}`}>
          <DollarSign className={`w-4 h-4 mx-auto mb-1 ${data.ending_balance >= data.opening_balance ? "text-emerald-600" : "text-amber-600"}`} />
          <p className={`text-xl font-black ${data.ending_balance >= data.opening_balance ? "text-emerald-700" : "text-amber-700"}`}>{fmt(data.ending_balance)}</p>
          <p className="text-[10px] text-stone-500">Ending (Day {days})</p>
        </div>
        <div className={`border-2 rounded-xl p-4 text-center ${data.at_risk ? "bg-red-50 border-red-300" : "bg-blue-50 border-blue-200"}`}>
          <AlertTriangle className={`w-4 h-4 mx-auto mb-1 ${data.at_risk ? "text-red-600" : "text-blue-600"}`} />
          <p className={`text-xl font-black ${data.at_risk ? "text-red-700" : "text-blue-700"}`}>{fmt(data.lowest_balance)}</p>
          <p className="text-[10px] text-stone-500">Lowest · {data.lowest_date?.slice(5)}</p>
        </div>
      </div>

      {/* Running Balance Chart */}
      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="balance-chart">
        <h3 className="text-sm font-bold text-stone-800 mb-2">Projected Running Balance</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="balGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={v => `£${(v/1000).toFixed(0)}k`} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={v => fmt(v)} />
            <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" />
            <Area type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={2} fill="url(#balGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Daily In/Out Bars */}
      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="flows-chart">
        <h3 className="text-sm font-bold text-stone-800 mb-2">Daily Inflows vs Outflows</h3>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} stackOffset="sign">
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={v => `£${(v/1000).toFixed(0)}k`} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} formatter={v => fmt(Math.abs(v))} />
            <ReferenceLine y={0} stroke="#64748b" />
            <Bar dataKey="inflow" fill="#10b981" stackId="stack" />
            <Bar dataKey="outflow" fill="#ef4444" stackId="stack" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Upcoming Events Table */}
      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="events-table">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-stone-800">Top Cash Events (Next {days} Days)</h3>
          <Badge className="bg-stone-100 text-stone-600 text-[9px]">
            {data.counts.bookings} bookings · {data.counts.recurring_expenses} recurring · {data.counts.future_expenses} expenses
          </Badge>
        </div>
        {significant.length === 0 ? (
          <p className="text-center text-sm text-stone-400 py-8">No scheduled cash events in this window. Add recurring expenses or confirm future bookings.</p>
        ) : (
          <div className="space-y-2">
            {significant.map(d => (
              <div key={d.date} className="border border-stone-100 rounded-lg" data-testid={`event-day-${d.date}`}>
                <button onClick={() => setExpandedDate(expandedDate === d.date ? null : d.date)} className="w-full flex items-center justify-between p-3 hover:bg-stone-50/60">
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4 text-stone-400" />
                    <span className="text-sm font-semibold text-stone-700">{d.date}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {d.inflows > 0 && <span className="text-emerald-700 font-mono font-semibold">+{fmt(d.inflows)}</span>}
                    {d.outflows > 0 && <span className="text-red-600 font-mono font-semibold">−{fmt(d.outflows)}</span>}
                    <span className={`font-mono font-bold ${d.running_balance < 0 ? "text-red-700" : "text-stone-800"}`}>{fmt(d.running_balance)}</span>
                  </div>
                </button>
                {expandedDate === d.date && (
                  <div className="px-3 pb-3 pt-1 border-t border-stone-100 bg-stone-50/40">
                    {[...d.items.in, ...d.items.out].map((it, i) => {
                      const style = ITEM_KIND_STYLE[it.kind] || ITEM_KIND_STYLE.expense;
                      const isIn = d.items.in.includes(it);
                      return (
                        <div key={i} className="flex items-center justify-between py-1 text-xs">
                          <div className="flex items-center gap-2">
                            <Badge className={`${style.bg} text-[9px]`}>{style.label}</Badge>
                            <span className="text-stone-700">{it.label}</span>
                          </div>
                          <span className={`font-mono font-semibold ${isIn ? "text-emerald-700" : "text-red-600"}`}>
                            {isIn ? "+" : "−"}{fmt(it.amount)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* AI Recommendations */}
      <div className="bg-gradient-to-br from-violet-50 to-blue-50 border-2 border-violet-200 rounded-xl p-4" data-testid="ai-recommendations">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-600" />
            <h3 className="text-sm font-bold text-stone-800">AI CFO Recommendations</h3>
            {aiAt && (
              <Badge className="bg-white text-stone-600 text-[9px] border border-stone-200">
                <Clock className="w-2.5 h-2.5 inline mr-1" />
                Generated {new Date(aiAt).toLocaleString()}
              </Badge>
            )}
          </div>
          <Button
            size="sm"
            onClick={generateAI}
            disabled={aiLoading || !data}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="generate-ai-btn"
          >
            {aiLoading ? (
              <><RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />Analysing...</>
            ) : (
              <><Sparkles className="w-3.5 h-3.5 mr-1.5" />{aiRecs.length > 0 ? "Regenerate" : "Generate Insights"}</>
            )}
          </Button>
        </div>
        {aiRecs.length === 0 ? (
          <div className="text-center py-8 text-stone-500">
            <Sparkles className="w-8 h-8 mx-auto mb-2 text-violet-300" />
            <p className="text-xs">Click "Generate Insights" to get GPT-5.2 prescriptive actions — specific ways to improve cash flow, avoid shortfalls, and time payments better.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5" data-testid="ai-recs-list">
            {aiRecs.map((r, i) => {
              const KIND_STYLE = {
                save_cost:     { icon: Shield,  color: "text-emerald-600", bg: "bg-emerald-50 border-emerald-200" },
                boost_revenue: { icon: Boost,   color: "text-blue-600",    bg: "bg-blue-50 border-blue-200" },
                timing:        { icon: Clock,   color: "text-amber-600",   bg: "bg-amber-50 border-amber-200" },
                risk_alert:    { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50 border-red-200" },
                efficiency:    { icon: Zap,     color: "text-violet-600",  bg: "bg-violet-50 border-violet-200" },
              };
              const style = KIND_STYLE[r.kind] || KIND_STYLE.efficiency;
              const Icon = style.icon;
              const PRI = { high: "bg-red-500 text-white", medium: "bg-amber-500 text-white", low: "bg-stone-400 text-white" };
              return (
                <div key={i} className={`${style.bg} border rounded-lg p-3 relative`} data-testid={`ai-rec-${i}`}>
                  <div className="flex items-start gap-2">
                    <Icon className={`w-4 h-4 flex-shrink-0 mt-0.5 ${style.color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <h4 className="text-xs font-bold text-stone-800">{r.title}</h4>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <Badge className={`${PRI[r.priority] || PRI.medium} text-[8px] uppercase`}>{r.priority || "med"}</Badge>
                        </div>
                      </div>
                      <p className="text-[11px] text-stone-600 leading-snug">{r.rationale}</p>
                      {r.impact && <p className="text-[11px] font-mono font-bold mt-1.5 text-stone-800">{r.impact}</p>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer note about payroll estimate */}
      {data.payroll_estimate_monthly > 0 && (
        <div className="text-[10px] text-stone-400 italic">
          Payroll estimate £{data.payroll_estimate_monthly.toFixed(0)}/month (avg of last {Math.min(3, 3)} approved/paid runs).
          Add or approve payroll runs to sharpen the forecast.
        </div>
      )}
    </div>
  );
};
