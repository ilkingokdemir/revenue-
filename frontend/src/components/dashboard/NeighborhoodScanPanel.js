/**
 * NeighborhoodScanPanel — Market Robot geo-radius scan with:
 *   • Manual scan (postcode/address + radius)
 *   • Auto-scan toggle (runs every N minutes independently from city scan)
 *   • Price data: avg/min/max market prices for the neighborhood
 *   • Charts: demand bars + price trend (same style as Demand Radar)
 *   • Parallel execution — city scan + geo scan can both run
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import {
  MapPin, Radar, Loader2, Clock, Building2, TrendingUp, Timer,
  PoundSterling, Activity, ToggleLeft, ToggleRight, Save,
} from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const cur = (v) => "£" + (Number(v) || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 });

export default function NeighborhoodScanPanel({ propertyId }) {
  const [location, setLocation] = useState("");
  const [radiusKm, setRadiusKm] = useState(3.2);
  const [days, setDays] = useState(30);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [scanning, setScanning] = useState(false);
  const [summary, setSummary] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [lastResult, setLastResult] = useState(null);
  const [autoCfg, setAutoCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [highlightDate, setHighlightDate] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [{ data: supply }, { data: cfg }] = await Promise.all([
        axios.get(`${API}/revenue/market-robot/${propertyId}/geo-supply?days=${days}`),
        axios.get(`${API}/revenue/market-robot/${propertyId}/geo-config`),
      ]);
      setSummary(supply.summary || null);
      setSnapshots(supply.snapshots || []);
      setAutoCfg(cfg);
      if (cfg && !location && cfg.location) {
        setLocation(cfg.location);
        setRadiusKm(cfg.radius_km || 3.2);
        if (cfg.latitude) setLatitude(cfg.latitude);
        if (cfg.longitude) setLongitude(cfg.longitude);
      }
    } catch { /* noop */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId, days]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const runScan = async () => {
    if (!location.trim() && !(latitude && longitude)) { toast.error("Enter a postcode/address OR coordinates"); return; }
    setScanning(true);
    try {
      const payload = { location: location.trim(), radius_km: Number(radiusKm), days_ahead: Number(days) };
      if (latitude && longitude) { payload.latitude = Number(latitude); payload.longitude = Number(longitude); }
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/scan-geo`, payload);
      if (data.status === "busy") { toast.error(data.error || "Another geo scan in progress"); }
      else {
        setLastResult(data);
        toast.success(`Scanned ${data.dates_scanned} dates · ${data.location}`);
        loadAll();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Scan failed");
    }
    setScanning(false);
  };

  const saveAutoCfg = async () => {
    setSaving(true);
    try {
      const payload = {
        enabled: autoCfg?.enabled || false,
        location: location.trim(),
        radius_km: Number(radiusKm),
        days_ahead: Number(days),
        scan_interval_minutes: Number(autoCfg?.scan_interval_minutes || 120),
        latitude: latitude ? Number(latitude) : null,
        longitude: longitude ? Number(longitude) : null,
      };
      const { data } = await axios.put(`${API}/revenue/market-robot/${propertyId}/geo-config`, payload);
      setAutoCfg(data);
      toast.success("Auto-scan settings saved");
    } catch (e) {
      toast.error("Save failed");
    }
    setSaving(false);
  };

  const toggleAuto = async () => {
    if (!location.trim() && !(latitude && longitude)) { toast.error("Set a location first, then save before enabling"); return; }
    const next = !(autoCfg?.enabled);
    setAutoCfg({ ...(autoCfg || {}), enabled: next });
    try {
      await axios.put(`${API}/revenue/market-robot/${propertyId}/geo-config`, {
        ...(autoCfg || {}),
        enabled: next,
        location: location.trim(),
        radius_km: Number(radiusKm),
        days_ahead: Number(days),
        scan_interval_minutes: Number(autoCfg?.scan_interval_minutes || 120),
        latitude: latitude ? Number(latitude) : null,
        longitude: longitude ? Number(longitude) : null,
      });
      toast.success(next ? "Auto-scan enabled" : "Auto-scan paused");
    } catch { toast.error("Toggle failed"); }
  };

  // Chart derivation
  const chart = useMemo(() => {
    if (!snapshots.length) return null;
    const pad = { l: 55, r: 10, t: 38, b: 32 };
    const W = 1000, H = 270;
    const iW = W - pad.l - pad.r, iH = H - pad.t - pad.b;
    const n = snapshots.length;
    const sx = (i) => pad.l + (i / Math.max(n - 1, 1)) * iW;
    const prices = snapshots.map(s => s.avg_price || 0).filter(v => v > 0);
    const pMin = prices.length ? Math.min(...prices) * 0.9 : 0;
    const pMax = prices.length ? Math.max(...prices) * 1.05 : 1;
    const syP = (v) => pad.t + iH - ((v - pMin) / Math.max(pMax - pMin, 1)) * iH;
    const syD = (v) => pad.t + iH - (v / 100) * iH;
    const linePath = snapshots.map((s, i) => {
      const x = sx(i), y = syP(s.avg_price || 0);
      return `${i === 0 ? "M" : "L"} ${x} ${y}`;
    }).join(" ");
    return { pad, W, H, iW, iH, sx, syP, syD, linePath, pMin, pMax };
  }, [snapshots]);

  const miles = (radiusKm * 0.621371).toFixed(1);

  // TOP 3 biggest absolute % changes vs previous day
  const top3Changes = useMemo(() => {
    const deltas = [];
    for (let i = 1; i < snapshots.length; i++) {
      const p = snapshots[i - 1].avg_price;
      const c = snapshots[i].avg_price;
      if (p > 0 && c > 0) {
        const pct = ((c - p) / p) * 100;
        deltas.push({ date: snapshots[i].date, pct, price: c, prevPrice: p });
      }
    }
    return deltas.sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)).slice(0, 3);
  }, [snapshots]);

  const scrollToDate = (date) => {
    setHighlightDate(date);
    const row = document.querySelector(`[data-row-date="${date}"]`);
    if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => setHighlightDate(null), 2500);
  };

  return (
    <div className="space-y-5" data-testid="neighborhood-scan-panel">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/70 via-teal-950/40 to-stone-900 p-6">
        <div className="absolute -top-10 -right-10 w-48 h-48 rounded-full bg-emerald-500/20 blur-3xl pointer-events-none" />
        <div className="relative flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center shrink-0">
              <MapPin className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-black text-emerald-300">Neighborhood Scan</h2>
              <p className="text-xs text-stone-400 mt-1">
                Booking.com hotels within <span className="text-emerald-300 font-semibold">{miles} miles</span> · runs <span className="text-amber-300 font-semibold">in parallel</span> with city scan.
              </p>
            </div>
          </div>
          {autoCfg && (
            <button onClick={toggleAuto}
              className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all ${autoCfg.enabled ? "bg-emerald-500 text-black shadow-lg shadow-emerald-500/30" : "bg-stone-800 text-stone-400 hover:bg-stone-700"}`}
              data-testid="geo-auto-toggle">
              {autoCfg.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
              Auto-Scan {autoCfg.enabled ? "ON" : "OFF"}
            </button>
          )}
        </div>
      </div>

      {/* Config form */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Location (Postcode / Address)</label>
            <input value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. E1 6AN"
              className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-emerald-500" data-testid="geo-location" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Radius · <span className="text-emerald-400">{radiusKm} km ({miles} mi)</span></label>
            <input type="range" min="0.5" max="10" step="0.1" value={radiusKm} onChange={e => setRadiusKm(e.target.value)} className="w-full accent-emerald-500" data-testid="geo-radius" />
            <div className="flex justify-between text-[9px] text-stone-500 mt-0.5"><span>0.5km</span><span>5km</span><span>10km</span></div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Days Ahead</label>
            <select value={days} onChange={e => setDays(e.target.value)} className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" data-testid="geo-days">
              {[7,14,30,60,90].map(d => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Auto Interval (min)</label>
            <select value={autoCfg?.scan_interval_minutes || 120} onChange={e => setAutoCfg(c => ({ ...(c || {}), scan_interval_minutes: Number(e.target.value) }))} className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" data-testid="geo-interval">
              {[30,60,120,240,480,1440].map(m => <option key={m} value={m}>{m >= 60 ? (m/60)+"h" : m+"m"}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Latitude</label>
            <input value={latitude} onChange={e => setLatitude(e.target.value)} placeholder="51.5074" className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-400 mb-1.5 tracking-wider">Longitude</label>
            <input value={longitude} onChange={e => setLongitude(e.target.value)} placeholder="-0.1278" className="w-full px-3 py-2.5 text-sm bg-stone-950 border border-stone-700 rounded-lg text-stone-100" />
          </div>
        </div>

        <div className="flex gap-2">
          <button onClick={runScan} disabled={scanning}
            className="flex-1 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black font-black rounded-xl flex items-center justify-center gap-2 disabled:opacity-60 shadow-lg shadow-emerald-500/30"
            data-testid="geo-scan-btn">
            {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Radar className="w-5 h-5" />}
            {scanning ? "Scanning Booking.com…" : `Scan Now (${miles} mi)`}
          </button>
          <button onClick={saveAutoCfg} disabled={saving}
            className="px-5 py-3 bg-stone-800 hover:bg-stone-700 text-stone-100 font-bold rounded-xl flex items-center gap-2 disabled:opacity-60 border border-stone-700"
            data-testid="geo-save-cfg">
            {saving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Save className="w-5 h-5" />}
            Save
          </button>
        </div>
        {autoCfg?.last_scan && (
          <p className="text-[11px] text-stone-500 flex items-center gap-1.5"><Timer className="w-3 h-3" /> Last auto-scan: <span className="text-emerald-300 font-semibold">{new Date(autoCfg.last_scan).toLocaleString()}</span> · Total: <span className="text-emerald-300 font-semibold">{autoCfg.total_scans || 0}</span></p>
        )}
      </div>

      {/* Last scan result */}
      {lastResult && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-4" data-testid="geo-last-result">
          <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
            <TrendingUp className="w-4 h-4" /> Scan completed
          </div>
          <p className="text-xs text-stone-300 mt-1">
            <span className="text-emerald-400 font-semibold">{lastResult.dates_scanned}</span> dates · {lastResult.location}
          </p>
        </div>
      )}

      {/* Summary cards */}
      {summary && summary.total_snapshots > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="geo-summary">
          <KPI label="Snapshots" value={summary.total_snapshots} tone="slate" icon={Activity} />
          <KPI label="Avg Unavail" value={`${summary.avg_unavailable_pct}%`} tone="amber" icon={Building2} />
          <KPI label="Market Avg" value={cur(summary.avg_price)} tone="emerald" icon={PoundSterling} testId="geo-avg-price" />
          <KPI label="Market Low" value={cur(summary.min_price)} tone="emerald" />
          <KPI label="Market High" value={cur(summary.max_price)} tone="rose" />
        </div>
      )}

      {/* Chart — Avg Price + Demand */}
      {chart && snapshots.length > 2 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="geo-chart">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-stone-100">Neighborhood Market · Demand & Price Trend</h3>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[10px] text-stone-400" data-testid="geo-chart-legend">
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-emerald-500" /> Demand %</span>
              <span className="flex items-center gap-1.5"><span className="w-4 h-[2px] bg-amber-400" /> Avg Price</span>
              <span className="flex items-center gap-1.5 border-l border-stone-700 pl-3">
                <span className="text-rose-300 font-black text-[11px]">▲</span>
                <span className="text-stone-300">Rakip fiyatı <span className="text-rose-300 font-semibold">artırdı</span> · siz de artırın</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="text-emerald-300 font-black text-[11px]">▼</span>
                <span className="text-stone-300">Rakip fiyatı <span className="text-emerald-300 font-semibold">düşürdü</span> · fırsat</span>
              </span>
            </div>
          </div>

          <div className="relative overflow-x-auto">
            {/* Y-axis left (demand %) */}
            <div className="absolute left-0 top-0 bottom-0 w-12 pointer-events-none z-10">
              {[100,75,50,25,0].map(v => (
                <div key={v} className="absolute right-1 text-[11px] font-bold text-stone-200 tabular-nums"
                  style={{ top: `calc(${((100-v)/100)*(chart.H-chart.pad.t-chart.pad.b)/chart.H*100}% + ${chart.pad.t/chart.H*100}% - 7px)`, lineHeight: 1 }}>{v}%</div>
              ))}
            </div>
            {/* Y-axis right (price £) */}
            <div className="absolute right-0 top-0 bottom-0 w-14 pointer-events-none z-10">
              {[1,0.75,0.5,0.25,0].map(f => {
                const val = Math.round(chart.pMin + f * (chart.pMax - chart.pMin));
                return <div key={f} className="absolute left-1 text-[11px] font-bold text-amber-300 tabular-nums"
                  style={{ top: `calc(${((1-f)*chart.iH + chart.pad.t)/chart.H*100}% - 7px)`, lineHeight: 1 }}>{cur(val)}</div>;
              })}
            </div>

            <svg viewBox={`0 0 ${chart.W} ${chart.H}`} className="w-full" style={{ minWidth: `${Math.max(600, snapshots.length * 18)}px` }}>
              {/* Grid */}
              {[0,25,50,75,100].map(v => (
                <line key={v} x1={chart.pad.l} x2={chart.W - chart.pad.r} y1={chart.syD(v)} y2={chart.syD(v)} stroke="#374151" strokeWidth="0.5" />
              ))}
              {/* Demand bars + % label above each bar */}
              {snapshots.map((s, i) => {
                const h = (s.unavailable_pct / 100) * chart.iH;
                const x = chart.sx(i) - 5;
                const y = chart.pad.t + chart.iH - h;
                const hot = s.unavailable_pct >= 80;
                const labelStep = snapshots.length > 30 ? 5 : snapshots.length > 14 ? 3 : 2;
                const showLabel = i % labelStep === 0;
                return (
                  <g key={`bar-${i}`}>
                    <rect x={x} y={y} width={10} height={h} rx={2}
                      fill={hot ? "#ef4444" : s.unavailable_pct >= 60 ? "#14b8a6" : "#10b981"} opacity="0.75" />
                    {showLabel && s.unavailable_pct > 0 && (
                      <text x={chart.sx(i)} y={Math.max(y - 3, chart.pad.t + 8)} textAnchor="middle" fontSize="9" fontWeight="900"
                        fill={hot ? "#fca5a5" : "#6ee7b7"}>{s.unavailable_pct}%</text>
                    )}
                  </g>
                );
              })}
              {/* Price line */}
              <path d={chart.linePath} fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="6 3" opacity="0.95" />
              {/* Price dots + £ value label (with Δ% vs previous day) above each dot */}
              {snapshots.map((s, i) => {
                const labelStep = snapshots.length > 30 ? 5 : snapshots.length > 14 ? 3 : 2;
                const showLabel = i % labelStep === 0;
                const cy = chart.syP(s.avg_price || 0);
                const prev = i > 0 ? snapshots[i - 1] : null;
                const prevPrice = prev && prev.avg_price > 0 ? prev.avg_price : null;
                const delta = prevPrice && s.avg_price > 0
                  ? ((s.avg_price - prevPrice) / prevPrice) * 100
                  : null;
                const showDelta = delta !== null && Math.abs(delta) >= 2;
                const up = delta !== null && delta > 0;
                const deltaColor = up ? "#f87171" : "#34d399"; // rising prices = rose (demand), falling = mint (opportunity)
                return (
                  <g key={`dot-${i}`}>
                    <circle cx={chart.sx(i)} cy={cy} r="3" fill="#fbbf24" stroke="#0a0a0a" strokeWidth="1" />
                    {showLabel && s.avg_price > 0 && (
                      <>
                        <rect x={chart.sx(i) - 22} y={cy - 22} width={44} height={15} rx={3} fill="#0a0a0a" opacity="0.9" stroke="#fbbf24" strokeWidth="0.6" />
                        <text x={chart.sx(i)} y={cy - 11} textAnchor="middle" fontSize="11" fontWeight="900" fill="#fbbf24" fontFamily="'Inter', system-ui, sans-serif">
                          £{Math.round(s.avg_price)}
                        </text>
                        {showDelta && (
                          <text x={chart.sx(i)} y={cy - 25} textAnchor="middle" fontSize="8.5" fontWeight="800" fill={deltaColor} fontFamily="'Inter', system-ui, sans-serif">
                            {up ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}%
                          </text>
                        )}
                      </>
                    )}
                  </g>
                );
              })}
              {/* Date labels */}
              {snapshots.map((s, i) => {
                if (!s?.date) return null;
                const dt = new Date(s.date + "T00:00:00");
                const prev = i > 0 ? new Date(snapshots[i-1].date + "T00:00:00") : null;
                const isMonthStart = !prev || prev.getMonth() !== dt.getMonth();
                const step = snapshots.length > 30 ? 3 : 1;
                if (i % step !== 0 && !isMonthStart) return null;
                return (
                  <g key={`xd${i}`}>
                    <text x={chart.sx(i)} y={chart.H - 12} textAnchor="middle" fontSize="7" fill={isMonthStart ? "#ffffff" : "#9ca3af"} fontWeight={isMonthStart ? "700" : "500"}>{dt.getDate()}</text>
                    {isMonthStart && <text x={chart.sx(i)} y={chart.H - 2} textAnchor="middle" fontSize="8" fill="#10b981" fontWeight="800">{dt.toLocaleDateString("en",{month:"short"})}</text>}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      )}

      {/* Snapshots table */}
      {snapshots.length > 0 && (
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-5" data-testid="geo-snapshots">
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-stone-100">Neighborhood Supply & Prices · Next {days} days</h3>
            </div>
            {top3Changes.length > 0 && (
              <div className="flex flex-wrap items-center gap-2" data-testid="top3-changes">
                <span className="text-[10px] text-stone-400 uppercase tracking-widest font-bold flex items-center gap-1">
                  <span className="text-amber-400">🔥</span> TOP 3 Değişim
                </span>
                {top3Changes.map((t, i) => {
                  const up = t.pct > 0;
                  return (
                    <button
                      key={t.date}
                      onClick={() => scrollToDate(t.date)}
                      data-testid={`top3-pill-${i}`}
                      className={`group flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold transition-all border ${
                        up
                          ? "bg-rose-500/15 border-rose-500/40 text-rose-200 hover:bg-rose-500/25 hover:border-rose-400"
                          : "bg-emerald-500/15 border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/25 hover:border-emerald-400"
                      }`}
                      title={`£${Math.round(t.prevPrice)} → £${Math.round(t.price)}`}
                    >
                      <span className="text-stone-300 tabular-nums">{t.date.slice(5)}</span>
                      <span>{up ? "▲" : "▼"}{Math.abs(t.pct).toFixed(1)}%</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <div className="overflow-x-auto rounded-xl border border-stone-800">
            <table className="w-full text-xs">
              <thead className="bg-stone-950/80">
                <tr className="text-[11px] text-stone-100 border-b-2 border-emerald-500/40">
                  <th className="text-left py-3 pl-3 pr-2 font-bold tracking-wide">
                    <div className="flex flex-col leading-tight">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Tarih</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Check-in günü</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Bölge</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Tarama lokasyonu</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Otel</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Toplam rakip</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Doluluk %</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Rezerve olan oran</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-amber-300 uppercase text-[10px] tracking-widest">Ort. Fiyat</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Rakip ortalaması</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-violet-300 uppercase text-[10px] tracking-widest">Δ Değişim</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">Bir önceki güne göre</span>
                    </div>
                  </th>
                  <th className="text-right px-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-emerald-300 uppercase text-[10px] tracking-widest">Min £</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">En ucuz oda</span>
                    </div>
                  </th>
                  <th className="text-right pr-3 pl-2 font-bold">
                    <div className="flex flex-col leading-tight items-end">
                      <span className="text-rose-300 uppercase text-[10px] tracking-widest">Max £</span>
                      <span className="text-[9px] text-stone-400 font-normal normal-case">En pahalı oda</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s, idx) => {
                  const hot = (s.unavailable_pct || 0) >= 80;
                  const prev = idx > 0 ? snapshots[idx - 1] : null;
                  const prevPrice = prev && prev.avg_price > 0 ? prev.avg_price : null;
                  const delta = prevPrice && s.avg_price > 0
                    ? ((s.avg_price - prevPrice) / prevPrice) * 100 : null;
                  const up = delta !== null && delta > 0;
                  return (
                    <tr key={s.date}
                      data-row-date={s.date}
                      className={`border-b border-stone-800/40 transition-all duration-500 ${
                        highlightDate === s.date
                          ? "bg-amber-400/20 ring-2 ring-amber-400 ring-inset"
                          : "hover:bg-emerald-500/5"
                      }`}>
                      <td className="py-2.5 pl-3 pr-2 text-stone-100 font-semibold tabular-nums">{s.date}</td>
                      <td className="text-right px-2 text-stone-400 truncate max-w-[120px]">{s.location}</td>
                      <td className="text-right px-2 text-stone-300 tabular-nums">{s.total_properties || "—"}</td>
                      <td className="text-right px-2 tabular-nums">
                        <span className={`inline-block px-2 py-0.5 rounded font-bold ${hot ? "bg-rose-500/20 text-rose-200" : (s.unavailable_pct||0) >= 60 ? "bg-amber-500/20 text-amber-200" : "bg-emerald-500/15 text-emerald-200"}`}>
                          {s.unavailable_pct}%
                        </span>
                      </td>
                      <td className="text-right px-2 text-amber-300 font-bold tabular-nums">{s.avg_price ? cur(s.avg_price) : "—"}</td>
                      <td className="text-right px-2 tabular-nums">
                        {delta === null ? <span className="text-stone-600">—</span> : (
                          <span className={`font-bold ${Math.abs(delta) < 2 ? "text-stone-400" : up ? "text-rose-300" : "text-emerald-300"}`}>
                            {up ? "▲" : delta < 0 ? "▼" : ""}{delta.toFixed(1)}%
                          </span>
                        )}
                      </td>
                      <td className="text-right px-2 text-stone-300 tabular-nums">{s.min_price ? cur(s.min_price) : "—"}</td>
                      <td className="text-right pr-3 pl-2 text-stone-300 tabular-nums">{s.max_price ? cur(s.max_price) : "—"}</td>
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
          <p className="text-xs text-stone-500 mt-1">Enter a postcode above and hit Scan to see supply & price data around your target area.</p>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, tone, icon: Icon, testId }) {
  const tones = {
    emerald: "border-emerald-500/30 text-emerald-300",
    amber: "border-amber-500/30 text-amber-300",
    rose: "border-rose-500/30 text-rose-300",
    slate: "border-stone-700 text-stone-200",
  };
  return (
    <div className={`bg-stone-900/60 border ${tones[tone] || tones.slate} rounded-xl p-3 relative overflow-hidden`} data-testid={testId}>
      {Icon && <Icon className="absolute -right-2 -bottom-2 w-10 h-10 opacity-10" />}
      <p className="text-[9px] font-bold uppercase tracking-widest opacity-70">{label}</p>
      <p className="text-xl font-black tabular-nums mt-1">{value}</p>
    </div>
  );
}
