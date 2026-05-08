/**
 * OTA Stop-Sell Forecast Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, RefreshCw, AlertTriangle, BellOff, Save } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OTAStopSellForecastPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [data, setData] = useState({ items: [], recommended_count: 0, avg_last7_pickup_per_day: 0 });
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: f }] = await Promise.all([
        axios.get(`${API}/ota-forecast/${propertyId}/config`),
        axios.get(`${API}/ota-forecast/${propertyId}?days=14`),
      ]);
      setCfg(c);
      setData(f);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const saveCfg = async () => {
    try {
      await axios.post(`${API}/ota-forecast/config`, { property_id: propertyId, ...cfg });
      toast.success("Config saved");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const snooze = async (date) => {
    try {
      await axios.post(`${API}/ota-forecast/${propertyId}/${date}/snooze`, {});
      toast.success(`Snoozed ${date}`);
      refresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="ota-forecast-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">OTA Stop-Sell Forecast</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}When to pull rooms off Booking.com / Expedia and sell direct only — saves the OTA commission on the last few rooms.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Stop-sell dates (next 14d)" value={data.recommended_count} highlight={data.recommended_count > 0} />
        <Stat label="Avg pickup last 7d / day" value={data.avg_last7_pickup_per_day} />
        <Stat label="Commission %" value={`${cfg?.commission_pct_default || 17}%`} />
        <Stat label="Threshold ≤" value={`${cfg?.rooms_left_threshold_pct || 25}%`} />
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <label className="flex flex-col gap-1"><span className="text-stone-500">OTA commission %</span>
            <input type="number" value={cfg.commission_pct_default} onChange={(e) => setCfg({ ...cfg, commission_pct_default: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Horizon (days)</span>
            <input type="number" value={cfg.horizon_days} onChange={(e) => setCfg({ ...cfg, horizon_days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Rooms-left threshold %</span>
            <input type="number" value={cfg.rooms_left_threshold_pct} onChange={(e) => setCfg({ ...cfg, rooms_left_threshold_pct: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <button data-testid="ota-save-cfg-btn" onClick={saveCfg} className="px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 mt-4 flex items-center justify-center gap-1"><Save className="w-3 h-3" /> Save</button>
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr>
              <th className="px-3 py-2">Date</th>
              <th className="px-3 py-2 text-right">Total</th>
              <th className="px-3 py-2 text-right">Occupied</th>
              <th className="px-3 py-2 text-right">Left</th>
              <th className="px-3 py-2 text-right">Forecast pickup</th>
              <th className="px-3 py-2">Recommendation</th>
              <th className="px-3 py-2 text-right">Commission saved</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((d) => (
              <tr key={d.date} className={`border-t border-stone-800/60 ${d.stop_sell_recommended ? "bg-amber-500/5" : ""}`} data-testid="ota-forecast-row">
                <td className="px-3 py-2 text-stone-100 text-xs">{d.date}</td>
                <td className="px-3 py-2 text-right text-stone-300">{d.rooms_total}</td>
                <td className="px-3 py-2 text-right text-stone-300">{d.rooms_occupied}</td>
                <td className="px-3 py-2 text-right"><div>{d.rooms_left}</div><div className="text-[10px] text-stone-500">{d.rooms_left_pct}%</div></td>
                <td className="px-3 py-2 text-right text-stone-400">{d.forecast_pickup_remaining}</td>
                <td className="px-3 py-2">
                  {d.stop_sell_recommended ? (
                    <span className="text-[10px] px-2 py-0.5 rounded border bg-amber-500/20 border-amber-500/40 text-amber-200 flex items-center gap-1 w-fit"><AlertTriangle className="w-3 h-3" /> Stop-sell</span>
                  ) : d.snoozed ? (
                    <span className="text-[10px] px-2 py-0.5 rounded border bg-stone-800 border-stone-700 text-stone-400">snoozed</span>
                  ) : (
                    <span className="text-[10px] text-stone-500">keep open</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-emerald-300">£{d.estimated_commission_savings}</td>
                <td className="px-3 py-2 text-right">
                  {d.stop_sell_recommended && !d.snoozed && (
                    <button data-testid="ota-snooze-btn" onClick={() => snooze(d.date)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1 ml-auto">
                      <BellOff className="w-3 h-3" /> Snooze
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><td colSpan={8} className="px-3 py-6 text-center text-stone-500">No forecast data.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-amber-500/10 border-amber-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-amber-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
