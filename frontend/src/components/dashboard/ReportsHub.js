import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  RefreshCw, BarChart3, Bed, DollarSign, TrendingUp, PieChart, Calendar
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const TAB_COLORS = { overview: "bg-blue-500", revenue: "bg-emerald-500", occupancy: "bg-violet-500", commission: "bg-red-500" };

export const ReportsHub = ({ propertyId }) => {
  const [tab, setTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [occupancy, setOccupancy] = useState(null);
  const [commission, setCommission] = useState(null);
  const [loading, setLoading] = useState(true);
  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    Promise.all([
      axios.get(`${API}/reports/overview/${pid}`),
      axios.get(`${API}/reports/revenue/${pid}`),
      axios.get(`${API}/reports/occupancy/${pid}`),
      axios.get(`${API}/reports/commission/${pid}`),
    ]).then(([ov, rv, oc, cm]) => {
      setOverview(ov.data); setRevenue(rv.data); setOccupancy(oc.data); setCommission(cm.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [pid]);

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Reports...</div>;

  return (
    <div className="space-y-5" data-testid="reports-hub">
      {/* Tab Bar */}
      <div className="flex gap-1 bg-stone-100 rounded-xl p-1">
        {[
          { id: "overview", label: "Overview", icon: BarChart3 },
          { id: "revenue", label: "Revenue Report", icon: DollarSign },
          { id: "occupancy", label: "Occupancy Report", icon: Bed },
          { id: "commission", label: "Commission Report", icon: PieChart },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`report-tab-${t.id}`}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-semibold rounded-lg ${tab === t.id ? `${TAB_COLORS[t.id]} text-white` : "text-stone-500"}`}>
            <t.icon className="w-3.5 h-3.5" />{t.label}
          </button>
        ))}
      </div>

      {/* OVERVIEW */}
      {tab === "overview" && overview && (<>
        <div className="grid grid-cols-5 gap-3" data-testid="overview-kpis">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-emerald-700">{cur(overview.kpis.room_revenue)}</p><p className="text-[9px] text-emerald-500">Room Revenue</p></div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-blue-700">{overview.kpis.sold_room_nights}</p><p className="text-[9px] text-blue-500">Sold Room Nights</p></div>
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-violet-700">{overview.kpis.occupancy_rate}%</p><p className="text-[9px] text-violet-500">Occupancy Rate</p></div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-amber-700">{cur(overview.kpis.adr)}</p><p className="text-[9px] text-amber-500">ADR</p></div>
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-red-700">{cur(overview.kpis.total_commission)}</p><p className="text-[9px] text-red-500">Commission</p></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="revenue-by-source">
            <h3 className="text-sm font-bold text-stone-800 mb-3">Revenue by Source</h3>
            <div className="space-y-2">
              {overview.revenue_by_source.map(s => (
                <div key={s.source} className="flex items-center justify-between">
                  <span className="text-xs text-stone-600">{s.source}</span>
                  <span className="text-xs font-bold text-stone-800">{cur(s.revenue)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="avail-by-category">
            <h3 className="text-sm font-bold text-stone-800 mb-3">Availability by Category</h3>
            <div className="space-y-2">
              {overview.availability_by_category.map(c => (
                <div key={c.category}>
                  <div className="flex items-center justify-between text-xs mb-0.5"><span className="text-stone-600">{c.category}</span><span className="font-bold">{c.occupancy_pct}%</span></div>
                  <div className="w-full bg-stone-100 rounded-full h-2"><div className="h-2 bg-violet-500 rounded-full" style={{ width: `${Math.min(c.occupancy_pct, 100)}%` }} /></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </>)}

      {/* REVENUE */}
      {tab === "revenue" && revenue && (<>
        <div className="grid grid-cols-4 gap-3" data-testid="revenue-kpis">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-emerald-700">{cur(revenue.kpis.room_revenue)}</p><p className="text-[9px] text-emerald-500">Room Revenue</p></div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-blue-700">{cur(revenue.kpis.avg_period)}</p><p className="text-[9px] text-blue-500">Avg/Day</p></div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-amber-700">{revenue.kpis.top_source}</p><p className="text-[9px] text-amber-500">{cur(revenue.kpis.top_source_revenue)}</p></div>
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-stone-700">{revenue.daily_timeline.length}</p><p className="text-[9px] text-stone-500">Days</p></div>
        </div>
        {/* Revenue Timeline Chart */}
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="revenue-timeline">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Revenue Timeline</h3>
          <div className="overflow-x-auto">
            <svg viewBox={`0 0 ${Math.max(revenue.daily_timeline.length * 35, 600)} 180`} className="w-full" style={{ minWidth: "500px" }}>
              {(() => { const maxR = Math.max(...revenue.daily_timeline.map(d => d.revenue), 1); return revenue.daily_timeline.map((d, i) => {
                const x = 30 + i * 35; const h = (d.revenue / maxR) * 130;
                return <g key={d.date}><rect x={x} y={150 - h} width="24" height={h} rx="3" fill="#3b82f6" opacity="0.8" /><text x={x + 12} y={168} textAnchor="middle" className="text-[6px]" fill="#9ca3af">{d.dow}</text></g>;
              }); })()}
            </svg>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white border border-stone-200 rounded-xl p-5"><h3 className="text-sm font-bold text-stone-800 mb-3">Revenue by Category</h3>{revenue.revenue_by_category.map(c => <div key={c.category} className="flex justify-between text-xs py-1 border-b border-stone-50"><span className="text-stone-600">{c.category}</span><span className="font-bold">{cur(c.revenue)}</span></div>)}</div>
          <div className="bg-white border border-stone-200 rounded-xl p-5"><h3 className="text-sm font-bold text-stone-800 mb-3">Revenue by Source</h3>{revenue.revenue_by_source.map(s => <div key={s.source} className="flex justify-between text-xs py-1 border-b border-stone-50"><span className="text-stone-600">{s.source}</span><span className="font-bold">{cur(s.revenue)}</span></div>)}</div>
        </div>
      </>)}

      {/* OCCUPANCY */}
      {tab === "occupancy" && occupancy && (<>
        <div className="grid grid-cols-4 gap-3" data-testid="occ-kpis">
          <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-violet-700">{occupancy.kpis.avg_occupancy}%</p><p className="text-[9px] text-violet-500">Avg Occupancy</p></div>
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-emerald-700">{occupancy.kpis.sold_room_nights}</p><p className="text-[9px] text-emerald-500">Sold Nights</p></div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-blue-700">{occupancy.kpis.available_nights}</p><p className="text-[9px] text-blue-500">Available</p></div>
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center"><p className="text-xl font-black text-red-700">100%</p><p className="text-[9px] text-red-500">Peak: {occupancy.kpis.peak_day?.slice(5) || "N/A"}</p></div>
        </div>
        {/* Daily Occupancy Table */}
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="occ-daily-table">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Daily Breakdown</h3>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-white"><tr className="text-stone-400 border-b border-stone-200"><th className="text-left py-2 px-2">Date</th><th className="text-left py-2 px-1">Day</th><th className="text-right py-2 px-2">Rooms</th><th className="text-right py-2 px-2">Sold</th><th className="text-right py-2 px-2">Occupancy</th></tr></thead>
              <tbody>
                {occupancy.daily.map(d => {
                  const color = d.occupancy_pct >= 80 ? "text-emerald-600" : d.occupancy_pct >= 50 ? "text-amber-600" : "text-red-500";
                  return (
                    <tr key={d.date} className="border-b border-stone-50">
                      <td className="py-1.5 px-2 font-medium text-stone-700">{d.date.slice(5)}</td>
                      <td className="py-1.5 px-1 text-stone-400">{d.dow}</td>
                      <td className="py-1.5 px-2 text-right text-stone-400">{d.total_rooms}</td>
                      <td className="py-1.5 px-2 text-right text-stone-600">{d.sold}</td>
                      <td className={`py-1.5 px-2 text-right font-bold ${color}`}>{d.occupancy_pct}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="occ-by-category">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Occupancy by Category</h3>
          {occupancy.by_category.map(c => (
            <div key={c.category} className="mb-2">
              <div className="flex justify-between text-xs mb-0.5"><span className="text-stone-600">{c.category}</span><span className="font-bold">{c.occupancy_pct}%</span></div>
              <div className="w-full bg-stone-100 rounded-full h-2.5"><div className={`h-2.5 rounded-full ${c.occupancy_pct >= 70 ? "bg-emerald-500" : c.occupancy_pct >= 40 ? "bg-amber-500" : "bg-red-400"}`} style={{ width: `${Math.min(c.occupancy_pct, 100)}%` }} /></div>
            </div>
          ))}
        </div>
      </>)}

      {/* COMMISSION */}
      {tab === "commission" && commission && (<>
        <div className="grid grid-cols-5 gap-3" data-testid="comm-kpis">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-emerald-700">{cur(commission.kpis.gross_bookings)}</p><p className="text-[9px] text-emerald-500">Gross</p></div>
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-blue-700">{cur(commission.kpis.net_after_commission)}</p><p className="text-[9px] text-blue-500">Net After Comm</p></div>
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-red-700">{cur(commission.kpis.total_commission)}</p><p className="text-[9px] text-red-500">Total Commission</p></div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-amber-700">{cur(commission.kpis.pending)}</p><p className="text-[9px] text-amber-500">Pending</p></div>
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center"><p className="text-lg font-black text-stone-700">{commission.kpis.collection_rate}%</p><p className="text-[9px] text-stone-500">Collection Rate</p></div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="comm-by-source">
          <h3 className="text-sm font-bold text-stone-800 mb-3">Commission Summary by Source</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-stone-400 border-b border-stone-200"><th className="text-left py-2 px-2">Source</th><th className="text-right py-2 px-2">Gross</th><th className="text-right py-2 px-2">Rate</th><th className="text-right py-2 px-2">Commission</th><th className="text-right py-2 px-2">Paid</th><th className="text-right py-2 px-2">Pending</th><th className="text-right py-2 px-2">Net</th></tr></thead>
              <tbody>
                {commission.by_source.map(s => (
                  <tr key={s.source} className="border-b border-stone-50">
                    <td className="py-1.5 px-2 font-medium text-stone-700">{s.source}</td>
                    <td className="py-1.5 px-2 text-right">{cur(s.gross)}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{s.rate_pct}%</td>
                    <td className="py-1.5 px-2 text-right text-red-500 font-bold">{cur(s.commission)}</td>
                    <td className="py-1.5 px-2 text-right text-emerald-500">{cur(s.paid)}</td>
                    <td className="py-1.5 px-2 text-right text-amber-500">{cur(s.pending)}</td>
                    <td className="py-1.5 px-2 text-right font-bold text-stone-800">{cur(s.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </>)}
    </div>
  );
};
