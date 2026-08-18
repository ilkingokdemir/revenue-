/**
 * Multi-Property Roll-up Dashboard
 * --------------------------------
 * Chain-wide KPI summary across all properties.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Building2, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function MultiPropertyRollupPanel({ hotelName = "" }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/multi-property/rollup?days=${days}`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6" data-testid="multi-rollup-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-indigo-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Multi-Property Roll-up</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">Chain-wide KPIs across all your properties.</p>
        </div>
        <div className="flex gap-2">
          <select data-testid="rollup-days" value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{`${d}d`}</option>)}
          </select>
          <button data-testid="rollup-refresh" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        </div>
      </div>

      {loading || !data ? (
        <div className="flex items-center justify-center py-12 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Stat label="Properties" value={data.property_count} />
            <Stat label="Bookings" value={data.chain_bookings} />
            <Stat label="Chain revenue" value={`£${data.chain_revenue.toFixed(2)}`} highlight />
            <Stat label="No-shows" value={data.chain_no_shows} />
            <Stat label="Complaints" value={data.chain_complaints} />
          </div>

          <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr>
                  <th className="px-3 py-2">Property</th>
                  <th className="px-3 py-2 text-right">Rooms</th>
                  <th className="px-3 py-2 text-right">Bookings</th>
                  <th className="px-3 py-2 text-right">Revenue</th>
                  <th className="px-3 py-2 text-right">ADR</th>
                  <th className="px-3 py-2 text-right">RevPAR</th>
                  <th className="px-3 py-2 text-right">Occ. today</th>
                  <th className="px-3 py-2 text-right">No-shows</th>
                  <th className="px-3 py-2 text-right">Complaints</th>
                </tr>
              </thead>
              <tbody>
                {data.properties.map((p) => (
                  <tr key={p.property_id} className="border-t border-stone-800/60 text-stone-200" data-testid="rollup-row">
                    <td className="px-3 py-2">
                      <div className="text-stone-100 font-medium">{p.name}</div>
                      <div className="text-[10px] text-stone-500">{p.property_id}</div>
                    </td>
                    <td className="px-3 py-2 text-right">{p.rooms}</td>
                    <td className="px-3 py-2 text-right">{p.bookings}</td>
                    <td className="px-3 py-2 text-right text-emerald-300">£{p.revenue.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">£{p.adr.toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">£{p.revpar.toFixed(2)}</td>
                    <td className={`px-3 py-2 text-right ${p.occupancy_today_pct >= 80 ? "text-emerald-300" : p.occupancy_today_pct >= 50 ? "text-amber-300" : "text-stone-300"}`}>{p.occupancy_today_pct}%</td>
                    <td className="px-3 py-2 text-right text-rose-300">{p.no_shows}</td>
                    <td className="px-3 py-2 text-right text-orange-300">{p.complaints}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-indigo-500/10 border-indigo-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-indigo-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
