import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  RefreshCw, Users, Bed, DollarSign, LogIn, LogOut, Sparkles, Clock,
  TrendingUp, BarChart3, CreditCard
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export const EnhancedDashboard = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/dashboard/enhanced/${pid}`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pid]);

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
                    <td className="py-2 px-2 text-right text-stone-400">{cur(fo.previous_month[row.key])}</td>
                    <td className={`py-2 px-2 text-right font-bold ${row.color || "text-stone-800"}`}>{cur(fo.this_month[row.key])}</td>
                    <td className="py-2 px-2 text-right text-stone-400">{cur(fo.next_month[row.key])}</td>
                    <td className="py-2 px-2 text-right text-stone-300">{cur(fo.same_month_last_year[row.key])}</td>
                  </tr>
                ))}
                <tr>
                  <td className="py-2 px-2 font-medium text-stone-700">Bookings</td>
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
