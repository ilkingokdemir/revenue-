import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { ArrowsClockwise, ChartLine, CalendarBlank } from "@phosphor-icons/react";
import { TrendingUp, BarChart3, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function ForecastPanel({ properties, activePropertyId }) {
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewRange, setViewRange] = useState(30);

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchForecast = useCallback(async () => {
    setLoading(true);
    try { const { data } = await axios.get(`${API}/forecast/occupancy/${propertyId}?days=90`); setForecast(data); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchForecast(); }, [fetchForecast]);

  if (loading) return <div className="flex items-center justify-center h-96"><ArrowsClockwise size={24} className="animate-spin text-blue-300" /></div>;
  if (!forecast) return null;

  const days = forecast.forecast?.slice(0, viewRange) || [];
  const maxOcc = Math.max(...days.map(d => d.occupancy_pct), 10);
  const s = forecast.summary || {};

  return (
    <div className="h-full flex flex-col" data-testid="forecast-panel">
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center"><ChartLine size={18} className="text-white" weight="fill" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Occupancy Forecast</h2><p className="text-[11px] text-stone-500">30/60/90-day occupancy, revenue & rate forecast</p></div>
        </div>
        <div className="flex gap-1">
          {[7, 30, 60, 90].map(r => (
            <button key={r} onClick={() => setViewRange(r)}
              className={`text-[10px] px-3 py-1.5 rounded-lg font-bold ${viewRange === r ? "bg-blue-600 text-white" : "bg-stone-100 text-stone-500"}`}
              data-testid={`range-${r}`}>{r}d</button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="bg-white border-b border-stone-200 px-6 py-4 flex-shrink-0">
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "7-Day Forecast", occ: `${s["7_day"]?.avg_occupancy || 0}%`, rev: `£${s["7_day"]?.total_revenue?.toLocaleString() || 0}`, color: "bg-emerald-50 border-emerald-200 text-emerald-700" },
            { label: "30-Day Forecast", occ: `${s["30_day"]?.avg_occupancy || 0}%`, rev: `£${s["30_day"]?.total_revenue?.toLocaleString() || 0}`, color: "bg-blue-50 border-blue-200 text-blue-700" },
            { label: "90-Day Forecast", occ: `${s["90_day"]?.avg_occupancy || 0}%`, rev: `£${s["90_day"]?.total_revenue?.toLocaleString() || 0}`, color: "bg-purple-50 border-purple-200 text-purple-700" },
          ].map((c, i) => (
            <div key={i} className={`rounded-xl border p-4 ${c.color}`} data-testid={`summary-${i}`}>
              <div className="text-[10px] font-bold uppercase tracking-wider opacity-60">{c.label}</div>
              <div className="flex items-end justify-between mt-2">
                <div><div className="text-2xl font-black">{c.occ}</div><div className="text-[9px] opacity-60">Avg Occupancy</div></div>
                <div className="text-right"><div className="text-lg font-bold">{c.rev}</div><div className="text-[9px] opacity-60">Revenue</div></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50 p-6">
        <div className="max-w-5xl mx-auto space-y-5">
          {/* Occupancy Bar Chart */}
          <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid="occupancy-chart">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-stone-800 flex items-center gap-1.5"><BarChart3 size={14} className="text-blue-600" /> Occupancy Forecast ({viewRange} days)</h3>
              <span className="text-[10px] text-stone-400">{forecast.total_rooms} total rooms</span>
            </div>
            <div className="flex items-end gap-px h-40">
              {days.map((d, i) => {
                const height = Math.max(2, (d.occupancy_pct / maxOcc) * 100);
                const isWeekend = d.day_of_week === "Sat" || d.day_of_week === "Sun";
                const color = d.occupancy_pct >= 80 ? "bg-red-400" : d.occupancy_pct >= 50 ? "bg-blue-400" : "bg-emerald-400";
                return (
                  <motion.div key={i} initial={{ height: 0 }} animate={{ height: `${height}%` }} transition={{ duration: 0.5, delay: i * 0.01 }}
                    className={`flex-1 rounded-t-sm cursor-pointer hover:opacity-80 ${color} ${isWeekend ? "opacity-70" : ""}`}
                    title={`${d.date}: ${d.occupancy_pct}% (${d.bookings}/${d.total_rooms})`} />
                );
              })}
            </div>
            <div className="flex justify-between mt-1.5 text-[8px] text-stone-400">
              <span>{days[0]?.date}</span>
              <span>{days[Math.floor(days.length / 2)]?.date}</span>
              <span>{days[days.length - 1]?.date}</span>
            </div>
            <div className="flex gap-4 mt-2 text-[9px] text-stone-400">
              <span className="flex items-center gap-1"><div className="w-3 h-2 bg-emerald-400 rounded" /> &lt;50%</span>
              <span className="flex items-center gap-1"><div className="w-3 h-2 bg-blue-400 rounded" /> 50-80%</span>
              <span className="flex items-center gap-1"><div className="w-3 h-2 bg-red-400 rounded" /> &gt;80%</span>
            </div>
          </div>

          {/* Daily Breakdown Table */}
          <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm" data-testid="daily-table">
            <div className="px-5 py-3 border-b border-stone-100"><h3 className="text-sm font-bold text-stone-800 flex items-center gap-1.5"><Calendar size={14} className="text-stone-500" /> Daily Breakdown</h3></div>
            <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-stone-50">
                  <tr className="border-b border-stone-100">
                    <th className="text-left px-4 py-2 font-semibold text-stone-500">Date</th>
                    <th className="text-left px-2 py-2 font-semibold text-stone-500">Day</th>
                    <th className="text-center px-2 py-2 font-semibold text-stone-500">Booked</th>
                    <th className="text-center px-2 py-2 font-semibold text-stone-500">Available</th>
                    <th className="text-center px-2 py-2 font-semibold text-stone-500">Occupancy</th>
                    <th className="text-right px-4 py-2 font-semibold text-stone-500">Est. Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {days.map((d, i) => {
                    const isWeekend = d.day_of_week === "Sat" || d.day_of_week === "Sun";
                    return (
                      <tr key={i} className={`border-b border-stone-50 ${isWeekend ? "bg-stone-50/50" : ""}`}>
                        <td className="px-4 py-2 font-medium text-stone-700">{d.date}</td>
                        <td className="px-2 py-2 text-stone-500">{d.day_of_week}</td>
                        <td className="text-center px-2 py-2 font-bold text-stone-800">{d.bookings}</td>
                        <td className="text-center px-2 py-2 text-stone-500">{d.available}</td>
                        <td className="text-center px-2 py-2">
                          <div className="inline-flex items-center gap-1">
                            <div className="w-12 h-2 bg-stone-100 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${d.occupancy_pct >= 80 ? "bg-red-400" : d.occupancy_pct >= 50 ? "bg-blue-400" : "bg-emerald-400"}`}
                                style={{ width: `${Math.min(100, d.occupancy_pct)}%` }} />
                            </div>
                            <span className="font-bold text-stone-700">{d.occupancy_pct}%</span>
                          </div>
                        </td>
                        <td className="text-right px-4 py-2 font-bold text-emerald-600">£{d.estimated_revenue?.toLocaleString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
