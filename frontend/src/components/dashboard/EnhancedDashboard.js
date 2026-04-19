import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  RefreshCw, Users, Bed, DollarSign, LogIn, LogOut, Sparkles, Clock,
  TrendingUp, BarChart3, CreditCard, ArrowUpRight, ArrowDownRight,
  Wallet, Receipt, Banknote, Target,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const curCompact = (v) => {
  const n = Number(v || 0);
  if (Math.abs(n) >= 1_000_000) return `£${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `£${(n / 1_000).toFixed(1)}k`;
  return `£${n.toFixed(0)}`;
};

export const EnhancedDashboard = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState(null);
  const [historyRange, setHistoryRange] = useState("last_12m");
  const [historyLoading, setHistoryLoading] = useState(false);
  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/dashboard/enhanced/${pid}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pid]);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const { data: h } = await axios.get(`${API}/dashboard/financial-history`, { params: { property_id: pid, range: historyRange } });
      setHistory(h);
    } catch {
      /* silent */
    }
    setHistoryLoading(false);
  }, [pid, historyRange]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  if (loading || !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Dashboard...</div>;

  const { kpis, financial_overview, daily_revenue_7d, total_7d_revenue, avg_daily_revenue, staff_on_duty, housekeeping, recent_bookings, stayovers } = data;
  const fo = financial_overview;
  const maxRev = Math.max(...daily_revenue_7d.map(d => d.revenue), 1);

  return (
    <div className="space-y-5 p-6" data-testid="enhanced-dashboard">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3" data-testid="dashboard-kpis">
        <div className="bg-blue-500 rounded-2xl p-4 text-white">
          <Users className="w-5 h-5 mb-2 opacity-70" />
          <p className="text-3xl font-black">{kpis.in_house_guests}</p>
          <p className="text-xs opacity-70">In-House Guests</p>
        </div>
        <div className="bg-emerald-500 rounded-2xl p-4 text-white">
          <Bed className="w-5 h-5 mb-2 opacity-70" />
          <p className="text-3xl font-black">{kpis.occupancy_pct}%</p>
          <p className="text-xs opacity-70">Occupancy Rate</p>
        </div>
        <div className="bg-violet-500 rounded-2xl p-4 text-white">
          <LogIn className="w-5 h-5 mb-2 opacity-70" />
          <p className="text-3xl font-black">{kpis.arrivals_today}</p>
          <p className="text-xs opacity-70">Arrivals Today</p>
        </div>
        <div className="bg-amber-500 rounded-2xl p-4 text-white">
          <LogOut className="w-5 h-5 mb-2 opacity-70" />
          <p className="text-3xl font-black">{kpis.departures_today}</p>
          <p className="text-xs opacity-70">Departures Today</p>
        </div>
        <div className="bg-red-500 rounded-2xl p-4 text-white">
          <DollarSign className="w-5 h-5 mb-2 opacity-70" />
          <p className="text-3xl font-black">{cur(kpis.daily_income)}</p>
          <p className="text-xs opacity-70">Daily Income</p>
        </div>
      </div>

      {/* Financial Overview — Historical (Last Month / 3M / 12M / 3 Years) */}
      <FinancialHistorySection
        history={history}
        range={historyRange}
        onRangeChange={setHistoryRange}
        loading={historyLoading}
      />

      {/* Financial Overview + 7-Day Revenue */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Financial Overview Table */}
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl p-5" data-testid="financial-overview">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Financial Overview</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-stone-400 border-b border-stone-100">
                  <th className="text-left py-2 px-2"></th>
                  <th className="text-right py-2 px-2 bg-emerald-50/60 text-emerald-800 font-bold rounded-tl">Last 3 Years</th>
                  <th className="text-right py-2 px-2">Previous Month</th>
                  <th className="text-right py-2 px-2 font-bold text-stone-700">This Month</th>
                  <th className="text-right py-2 px-2">Next Month</th>
                  <th className="text-right py-2 px-2 text-stone-400">Same Month LY</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "Gross Revenue", key: "gross" },
                  { label: "Room Revenue", key: "room_revenue" },
                  { label: "ADR", key: "adr" },
                  { label: "Commission", key: "commission", color: "text-red-500" },
                  { label: "Net Revenue", key: "net", color: "text-emerald-600" },
                ].map(row => (
                  <tr key={row.key} className="border-b border-stone-50">
                    <td className="py-2 px-2 font-medium text-stone-700">{row.label}</td>
                    <td className="py-2 px-2 text-right font-bold text-emerald-700 bg-emerald-50/40" data-testid={`fo-3y-${row.key}`}>{cur((fo.last_3_years || {})[row.key])}</td>
                    <td className="py-2 px-2 text-right text-stone-400">{cur(fo.previous_month[row.key])}</td>
                    <td className={`py-2 px-2 text-right font-bold ${row.color || "text-stone-800"}`}>{cur(fo.this_month[row.key])}</td>
                    <td className="py-2 px-2 text-right text-stone-400">{cur(fo.next_month[row.key])}</td>
                    <td className="py-2 px-2 text-right text-stone-300">{cur(fo.same_month_last_year[row.key])}</td>
                  </tr>
                ))}
                <tr>
                  <td className="py-2 px-2 font-medium text-stone-700">Bookings</td>
                  <td className="py-2 px-2 text-right font-bold text-emerald-700 bg-emerald-50/40" data-testid="fo-3y-bookings">{(fo.last_3_years || {}).bookings || 0}</td>
                  <td className="py-2 px-2 text-right text-stone-400">{fo.previous_month.bookings}</td>
                  <td className="py-2 px-2 text-right font-bold">{fo.this_month.bookings}</td>
                  <td className="py-2 px-2 text-right text-stone-400">{fo.next_month.bookings}</td>
                  <td className="py-2 px-2 text-right text-stone-300">{fo.same_month_last_year.bookings}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 7-Day Revenue Chart */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="revenue-7d-chart">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-stone-800">Daily Gross Revenue</h3>
            <span className="text-[10px] text-stone-400">7 days</span>
          </div>
          <p className="text-2xl font-black text-stone-800 mb-1">{cur(total_7d_revenue)}</p>
          <p className="text-[10px] text-stone-400 mb-3">Avg: {cur(avg_daily_revenue)}/day</p>
          <div className="flex items-end gap-1.5 h-28">
            {daily_revenue_7d.map(d => (
              <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full bg-blue-400 rounded-t-md transition-all hover:bg-blue-500" style={{ height: `${Math.max((d.revenue / maxRev) * 100, 4)}%` }} title={`${d.dow}: ${cur(d.revenue)}`} />
                <span className="text-[8px] text-stone-400">{d.dow}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Staff + HK + Reservations */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Staff On Duty */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="staff-on-duty">
          <h3 className="text-sm font-bold text-stone-800 mb-3 flex items-center gap-1.5"><Clock className="w-4 h-4 text-stone-400" />Staff On Duty</h3>
          {staff_on_duty.length === 0 ? <p className="text-xs text-stone-400">No staff data</p> : (
            <div className="space-y-2">
              {staff_on_duty.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-stone-50">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-stone-100 flex items-center justify-center text-[10px] font-bold text-stone-600">{s.name?.[0] || "?"}</div>
                    <span className="text-xs font-medium text-stone-700">{s.name}</span>
                  </div>
                  <Badge className="text-[8px] bg-stone-100 text-stone-600">{s.role}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Housekeeping */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="hk-widget">
          <h3 className="text-sm font-bold text-stone-800 mb-3 flex items-center gap-1.5"><Sparkles className="w-4 h-4 text-stone-400" />Housekeeping</h3>
          <div className="text-center mb-3">
            <p className="text-4xl font-black text-stone-800">{housekeeping.completion_pct}%</p>
            <p className="text-[10px] text-stone-400">Completion</p>
          </div>
          <div className="w-full bg-stone-100 rounded-full h-3 mb-3 overflow-hidden">
            <div className="h-3 bg-emerald-500 rounded-full" style={{ width: `${housekeeping.completion_pct}%` }} />
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div><p className="text-lg font-bold text-emerald-600">{housekeeping.clean}</p><p className="text-[8px] text-stone-400">Clean</p></div>
            <div><p className="text-lg font-bold text-red-500">{housekeeping.dirty}</p><p className="text-[8px] text-stone-400">Dirty</p></div>
            <div><p className="text-lg font-bold text-blue-500">{housekeeping.total}</p><p className="text-[8px] text-stone-400">Total</p></div>
          </div>
        </div>

        {/* Recent Bookings */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="recent-bookings">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-stone-800">Reservations</h3>
            <div className="flex items-center gap-2 text-[9px] text-stone-400">
              <span>Last 24h: <strong className="text-stone-600">{recent_bookings.length}</strong></span>
              <span>Stayovers: <strong className="text-stone-600">{stayovers}</strong></span>
              <span>Pending: <strong className="text-red-500">{kpis.pending_payment}</strong></span>
            </div>
          </div>
          <div className="space-y-1.5 max-h-[180px] overflow-y-auto">
            {recent_bookings.length === 0 ? <p className="text-xs text-stone-400 text-center py-4">No recent bookings</p> : (
              recent_bookings.map(b => (
                <div key={b.id} className="flex items-center justify-between py-1.5 border-b border-stone-50 text-xs">
                  <div>
                    <p className="font-medium text-stone-700">{b.guest_name}</p>
                    <p className="text-[10px] text-stone-400">{b.check_in} — {b.nights}n — {b.source}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-stone-800">{cur(b.total_price)}</p>
                    <Badge className={`text-[7px] ${b.status === "confirmed" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"}`}>{b.status}</Badge>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ======================== Financial History Section ========================
const RANGES = [
  { id: "last_month", label: "Last Month" },
  { id: "last_3m",    label: "Last 3 Months" },
  { id: "last_6m",    label: "Last 6 Months" },
  { id: "ytd",        label: "YTD" },
  { id: "last_12m",   label: "Last 12 Months" },
  { id: "last_3y",    label: "Last 3 Years" },
  { id: "last_5y",    label: "Last 5 Years" },
];

const FinancialHistorySection = ({ history, range, onRangeChange, loading }) => {
  if (!history && !loading) return null;

  const series = history?.series || [];
  const totals = history?.totals || {};
  const delta = history?.delta || {};
  const maxAbs = Math.max(
    1,
    ...series.map(s => Math.max(s.gross_revenue || 0, Math.abs(s.net_profit || 0), (s.expenses || 0) + (s.payroll || 0)))
  );

  const tiles = [
    { key: "gross_revenue", label: "Gross Revenue",  icon: DollarSign, accent: "from-sky-500 to-blue-700",     value: totals.gross_revenue },
    { key: "commission",    label: "Commission",     icon: Receipt,    accent: "from-amber-500 to-orange-600", value: totals.commission, negative: true },
    { key: "net_revenue",   label: "Net Revenue",    icon: Banknote,   accent: "from-emerald-500 to-teal-700", value: totals.net_revenue, deltaPct: delta.net_revenue_pct },
    { key: "expenses",      label: "Expenses",       icon: Receipt,    accent: "from-rose-500 to-red-700",     value: totals.expenses,   negative: true },
    { key: "payroll",       label: "Payroll",        icon: Wallet,     accent: "from-violet-500 to-indigo-700",value: totals.payroll,    negative: true },
    { key: "net_profit",    label: "Net Profit",     icon: Target,     accent: "from-emerald-600 to-emerald-900", value: totals.net_profit, hero: true },
  ];

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="financial-history-section">
      <div className="flex items-center flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-600 to-teal-800 flex items-center justify-center shadow">
            <BarChart3 className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-stone-800 text-base leading-tight">Financial Overview · History</h3>
            <p className="text-[11px] text-stone-500">{history?.start} → {history?.end} · {history?.window_months || 0} months</p>
          </div>
        </div>
        {/* Range pills */}
        <div className="flex flex-wrap gap-1 ml-auto bg-stone-100 p-1 rounded-lg" data-testid="fh-range-tabs">
          {RANGES.map(r => (
            <button
              key={r.id}
              onClick={() => onRangeChange(r.id)}
              data-testid={`fh-range-${r.id}`}
              className={`px-3 py-1 text-[11px] font-semibold rounded-md transition-all ${range === r.id ? "bg-white text-emerald-700 shadow-sm" : "text-stone-500 hover:text-stone-700"}`}
            >{r.label}</button>
          ))}
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 mb-5">
        {tiles.map(t => (
          <div key={t.key} className={`rounded-xl p-3 relative overflow-hidden ${t.hero ? "bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-emerald-200" : "bg-stone-50 border border-stone-100"}`} data-testid={`fh-tile-${t.key}`}>
            <div className={`absolute top-0 right-0 w-16 h-16 rounded-full bg-gradient-to-br ${t.accent} opacity-10 -mr-5 -mt-5`}></div>
            <div className="flex items-center gap-1.5 mb-1 relative">
              <div className={`w-6 h-6 rounded-md bg-gradient-to-br ${t.accent} flex items-center justify-center`}>
                <t.icon className="w-3 h-3 text-white" />
              </div>
              <span className="text-[9px] font-bold text-stone-500 uppercase tracking-wider">{t.label}</span>
            </div>
            <div className={`${t.hero ? "text-xl" : "text-lg"} font-black ${t.hero ? "text-emerald-700" : t.negative ? "text-stone-700" : "text-stone-900"} tabular-nums relative`}>
              {t.negative && (t.value || 0) > 0 ? "-" : ""}{curCompact(t.value)}
            </div>
            {t.deltaPct !== undefined && Math.abs(t.deltaPct) > 0.01 && (
              <div className={`text-[10px] font-bold flex items-center gap-0.5 mt-0.5 ${t.deltaPct >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                {t.deltaPct >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(t.deltaPct).toFixed(1)}% vs prev period
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Monthly bar chart */}
      {series.length > 0 && (
        <div data-testid="fh-chart">
          <div className="flex items-end gap-0.5 h-32 border-b border-stone-100 pb-1 relative">
            {series.map((m) => {
              const posH = Math.max(0, (m.gross_revenue / maxAbs) * 100);
              const costH = Math.max(0, ((m.expenses + m.payroll + m.commission) / maxAbs) * 100);
              const profit = m.net_profit;
              const profitPositive = profit >= 0;
              return (
                <div key={m.month} className="flex-1 relative group flex flex-col justify-end min-w-0" title={`${m.label}\nGross: ${cur(m.gross_revenue)}\nCommission: ${cur(m.commission)}\nExpenses: ${cur(m.expenses)}\nPayroll: ${cur(m.payroll)}\nNet Profit: ${cur(profit)}\nBookings: ${m.bookings}`}>
                  <div className="relative w-full flex flex-col justify-end" style={{ height: "100%" }}>
                    {/* Gross (sky bar) */}
                    <div className="absolute bottom-0 inset-x-0 bg-sky-200 rounded-t-sm" style={{ height: `${posH}%` }}></div>
                    {/* Costs stacked (amber/rose/violet) */}
                    <div className="absolute bottom-0 inset-x-0" style={{ height: `${costH}%` }}>
                      <div className="bg-gradient-to-t from-rose-500 via-amber-400 to-amber-300 opacity-90 w-full h-full rounded-t-sm"></div>
                    </div>
                    {/* Net profit overlay (emerald vertical marker) */}
                    <div className="absolute inset-x-0 bottom-0 pointer-events-none flex items-end justify-center">
                      <div className={`w-1 rounded-full ${profitPositive ? "bg-emerald-500" : "bg-rose-600"}`} style={{ height: `${Math.abs((profit / maxAbs) * 100)}%` }}></div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between mt-2 text-[9px] text-stone-400">
            <span>{series[0]?.label}</span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-sky-200"></span>Gross</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-400"></span>Costs</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500"></span>Net Profit</span>
            </span>
            <span>{series[series.length - 1]?.label}</span>
          </div>
        </div>
      )}

      {loading && (
        <div className="text-center py-4 text-stone-400 text-xs flex items-center justify-center gap-1.5"><RefreshCw className="w-3 h-3 animate-spin" /> Loading history…</div>
      )}
    </div>
  );
};
