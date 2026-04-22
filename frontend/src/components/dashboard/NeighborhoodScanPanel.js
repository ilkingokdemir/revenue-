/**
 * NeighborhoodScanPanel — Market Robot geo-radius sub-tab.
 * User enters a postcode / address + radius → Booking.com scan within that circle,
 * runs in PARALLEL with the city-wide scan.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { MapPin, Radar, Loader2, Clock, Building2, TrendingUp } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function NeighborhoodScanPanel({ propertyId }) {
  const [location, setLocation] = useState("");
  const [radiusKm, setRadiusKm] = useState(3.2); // ~2 miles
  const [days, setDays] = useState(30);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [scanning, setScanning] = useState(false);
  const [summary, setSummary] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [lastResult, setLastResult] = useState(null);

  const loadSupply = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/${propertyId}/geo-supply?days=${days}`);
      setSummary(data.summary || null);
      setSnapshots(data.snapshots || []);
    } catch { /* noop */ }
  }, [propertyId, days]);

  useEffect(() => { loadSupply(); }, [loadSupply]);

  const runScan = async () => {
    if (!location.trim() && !(latitude && longitude)) {
      toast.error("Enter a postcode/address OR coordinates");
      return;
    }
    setScanning(true);
    try {
      const payload = { location: location.trim(), radius_km: Number(radiusKm), days_ahead: Number(days) };
      if (latitude && longitude) { payload.latitude = Number(latitude); payload.longitude = Number(longitude); }
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/scan-geo`, payload);
      if (data.status === "busy") {
        toast.error(data.error || "Another geo scan in progress");
      } else {
        setLastResult(data);
        toast.success(`Scanned ${data.dates_scanned} dates · ${data.location}`);
        loadSupply();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Scan failed");
    }
    setScanning(false);
  };

  // Convert km to miles for display
  const miles = (radiusKm * 0.621371).toFixed(1);

  return (
    <div className="space-y-5" data-testid="neighborhood-scan-panel">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/70 via-teal-950/40 to-stone-900 p-6">
        <div className="absolute -top-10 -right-10 w-48 h-48 rounded-full bg-emerald-500/20 blur-3xl pointer-events-none" />
        <div className="relative flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center shrink-0">
            <MapPin className="w-6 h-6 text-emerald-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-black text-emerald-300">Neighborhood Scan</h2>
            <p className="text-xs text-stone-400 mt-1">
              Scan Booking.com hotels within a <span className="text-emerald-300 font-semibold">{miles} miles</span> radius around a specific postcode or address. Runs <span className="text-amber-300 font-semibold">in parallel</span> with the city-wide scan.
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Location (Postcode / Address)</label>
            <input
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="e.g. SW1A 1AA or 221B Baker Street"
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="geo-location"
            />
            <p className="text-[10px] text-stone-500 mt-1">Postcode works best. Leave empty to use coordinates.</p>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">
              Radius · <span className="text-emerald-400">{radiusKm} km ({miles} mi)</span>
            </label>
            <input
              type="range" min="0.5" max="10" step="0.1"
              value={radiusKm}
              onChange={e => setRadiusKm(e.target.value)}
              className="w-full accent-emerald-500"
              data-testid="geo-radius"
            />
            <div className="flex justify-between text-[9px] text-stone-500 mt-0.5"><span>0.5km</span><span>5km</span><span>10km</span></div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Days Ahead</label>
            <select value={days} onChange={e => setDays(e.target.value)}
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100"
              data-testid="geo-days">
              <option value="7">7 days</option>
              <option value="14">14 days</option>
              <option value="30">30 days</option>
              <option value="60">60 days</option>
              <option value="90">90 days</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Latitude (opt)</label>
            <input value={latitude} onChange={e => setLatitude(e.target.value)}
              placeholder="51.5074"
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Longitude (opt)</label>
            <input value={longitude} onChange={e => setLongitude(e.target.value)}
              placeholder="-0.1278"
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
        </div>

        <button
          onClick={runScan}
          disabled={scanning}
          className="w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black font-black rounded-xl flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/30"
          data-testid="geo-scan-btn">
          {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Radar className="w-5 h-5" />}
          {scanning ? "Scanning Booking.com…" : `Scan Hotels Within ${miles} Miles`}
        </button>
      </div>

      {/* Last scan result */}
      {lastResult && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4" data-testid="geo-last-result">
          <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
            <TrendingUp className="w-4 h-4" /> Scan completed
          </div>
          <p className="text-xs text-stone-300 mt-1">
            <span className="text-emerald-400 font-semibold">{lastResult.dates_scanned}</span> dates scanned ·
            Location: <span className="font-semibold">{lastResult.location}</span> ·
            Scan ID: <code className="text-[10px] bg-stone-900 px-1 py-0.5 rounded">{lastResult.scan_id}</code>
          </p>
        </div>
      )}

      {/* Summary cards */}
      {summary && summary.total_snapshots > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="geo-summary">
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4">
            <p className="text-[10px] font-bold uppercase text-stone-500 tracking-widest">Snapshots</p>
            <p className="text-2xl font-black text-stone-100 tabular-nums mt-1">{summary.total_snapshots}</p>
          </div>
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4">
            <p className="text-[10px] font-bold uppercase text-stone-500 tracking-widest">Avg Unavailable</p>
            <p className="text-2xl font-black text-amber-400 tabular-nums mt-1">{summary.avg_unavailable_pct}%</p>
          </div>
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4">
            <p className="text-[10px] font-bold uppercase text-stone-500 tracking-widest">Last Radius</p>
            <p className="text-2xl font-black text-emerald-400 tabular-nums mt-1">{summary.last_radius_km}km</p>
          </div>
          <div className="bg-stone-900 border border-stone-800 rounded-xl p-4">
            <p className="text-[10px] font-bold uppercase text-stone-500 tracking-widest">Last Scan</p>
            <p className="text-xs font-bold text-stone-200 mt-2 tabular-nums">{summary.last_scan ? new Date(summary.last_scan).toLocaleString() : "—"}</p>
          </div>
        </div>
      )}

      {/* Snapshots table */}
      {snapshots.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="geo-snapshots">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-stone-100">Neighborhood Supply · Next {days} days</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[9px] uppercase text-stone-500 border-b border-stone-700">
                  <th className="text-left py-2 pr-2 font-bold tracking-widest">Date</th>
                  <th className="text-right px-2 font-bold tracking-widest">Location</th>
                  <th className="text-right px-2 font-bold tracking-widest">Radius</th>
                  <th className="text-right px-2 font-bold tracking-widest">Total Hotels</th>
                  <th className="text-right px-2 font-bold tracking-widest">Unavailable %</th>
                  <th className="text-right px-2 font-bold tracking-widest">Available</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map(s => {
                  const hot = (s.unavailable_pct || 0) >= 80;
                  return (
                    <tr key={s.date} className="border-b border-stone-800/40 hover:bg-emerald-500/5">
                      <td className="py-2 pr-2 text-stone-200 font-semibold tabular-nums">{s.date}</td>
                      <td className="text-right px-2 text-stone-400 truncate max-w-[160px]">{s.location}</td>
                      <td className="text-right px-2 text-stone-400 tabular-nums">{s.radius_km}km</td>
                      <td className="text-right px-2 text-stone-300 tabular-nums">{s.total_properties || "—"}</td>
                      <td className="text-right px-2 tabular-nums">
                        <span className={`inline-block px-1.5 py-0.5 rounded font-bold ${hot ? "bg-rose-500/20 text-rose-300" : (s.unavailable_pct || 0) >= 50 ? "bg-amber-500/20 text-amber-300" : "bg-emerald-500/15 text-emerald-300"}`}>
                          {s.unavailable_pct}%
                        </span>
                      </td>
                      <td className="text-right px-2 text-stone-300 tabular-nums">{s.available_est || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {snapshots.length === 0 && !lastResult && (
        <div className="text-center py-10 bg-stone-900/40 border border-dashed border-stone-700 rounded-xl">
          <Clock className="w-10 h-10 text-stone-600 mx-auto mb-2" />
          <p className="text-sm text-stone-400">No neighborhood scans yet</p>
          <p className="text-xs text-stone-500 mt-1">Enter a postcode above and hit Scan to see supply data around your target area.</p>
        </div>
      )}
    </div>
  );
}
