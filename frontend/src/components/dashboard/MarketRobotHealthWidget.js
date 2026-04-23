/**
 * MarketRobotHealthWidget — Cross-branch scanner health dashboard.
 * Shows city + geo scanner status for every property, 24h scan counts,
 * stale-scan warnings, and auto-refreshes every 30 s.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { Activity, CheckCircle2, AlertTriangle, MapPin, Globe2, Loader2, Radio, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function MarketRobotHealthWidget() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/health`);
      setData(data);
    } catch { /* noop */ }
    setLoading(false);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  if (!data) {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-6 text-center">
        <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
      </div>
    );
  }

  const { summary, branches } = data;
  const allHealthy = summary.unhealthy === 0;

  return (
    <div className="bg-stone-900/60 border border-emerald-500/30 rounded-2xl p-5 space-y-4" data-testid="market-robot-health-widget">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${allHealthy ? "bg-emerald-500/20" : "bg-amber-500/20"}`}>
            <Activity className={`w-5 h-5 ${allHealthy ? "text-emerald-400" : "text-amber-400"}`} />
          </div>
          <div>
            <h3 className="text-sm font-black text-emerald-300">Cross-Branch Scanner Health</h3>
            <p className="text-[11px] text-stone-400 mt-0.5">
              {summary.active_scanners} aktif · {summary.total_snapshots_24h.toLocaleString("en-GB")} snapshot son 24h
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${allHealthy ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"}`}>
            {allHealthy ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
            {allHealthy ? `Tüm ${summary.total_branches} şube sağlıklı` : `${summary.unhealthy}/${summary.total_branches} uyarı`}
          </div>
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300 disabled:opacity-50"
            data-testid="health-refresh">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Yenile
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-stone-800">
        <table className="w-full text-xs">
          <thead className="bg-stone-950/80">
            <tr className="border-b-2 border-emerald-500/40 text-[10px] text-stone-300 uppercase tracking-widest">
              <th className="text-left py-2.5 pl-3 pr-2 font-bold">Şube</th>
              <th className="text-center px-2 font-bold"><span className="flex items-center justify-center gap-1"><Globe2 className="w-3 h-3" /> City</span></th>
              <th className="text-center px-2 font-bold"><span className="flex items-center justify-center gap-1"><MapPin className="w-3 h-3" /> Geo</span></th>
              <th className="text-right px-2 font-bold">24h Snaps</th>
              <th className="text-right px-2 font-bold">Son Tarama</th>
              <th className="text-right pr-3 pl-2 font-bold">Uyarı</th>
            </tr>
          </thead>
          <tbody>
            {branches.map(b => {
              const c = b.city_scanner;
              const g = b.geo_scanner;
              const cityStat = c.scanner_active
                ? (c.in_memory_running ? "running" : "stale")
                : (c.enabled ? "enabled" : "off");
              const cityColor = { running: "bg-emerald-500/20 text-emerald-200 border-emerald-500/40",
                                  enabled: "bg-blue-500/15 text-blue-200 border-blue-500/40",
                                  stale:   "bg-amber-500/20 text-amber-200 border-amber-500/40",
                                  off:     "bg-stone-700/30 text-stone-400 border-stone-700/50" }[cityStat];
              const cityLabel = { running: "CANLI", enabled: "Zamanlı", stale: "Duraklamış", off: "Kapalı" }[cityStat];
              const geoColor = g.enabled ? "bg-emerald-500/15 text-emerald-200 border-emerald-500/40" : "bg-stone-700/30 text-stone-400 border-stone-700/50";
              return (
                <tr key={b.property_id} className={`border-b border-stone-800/40 hover:bg-emerald-500/5 ${b.healthy ? "" : "bg-amber-500/5"}`} data-testid={`health-row-${b.property_id}`}>
                  <td className="py-2.5 pl-3 pr-2 font-semibold">
                    <div className="flex items-center gap-2">
                      {b.healthy
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        : <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />}
                      <span className="text-stone-100">{b.property_name}</span>
                    </div>
                  </td>
                  <td className="text-center px-2">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold border ${cityColor}`}>
                        {cityStat === "running" && <Radio className="w-2.5 h-2.5 animate-pulse" />}
                        {cityLabel}
                      </span>
                      {c.city && <span className="text-[9px] text-stone-500 mt-0.5">{c.city}</span>}
                    </div>
                  </td>
                  <td className="text-center px-2">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold border ${geoColor}`}>
                        {g.enabled ? "Aktif" : "Kapalı"}
                      </span>
                      {g.location && <span className="text-[9px] text-stone-500 mt-0.5">{g.location}</span>}
                    </div>
                  </td>
                  <td className="text-right px-2 tabular-nums">
                    <span className={`font-bold ${b.snapshots_24h > 100 ? "text-emerald-300" : b.snapshots_24h > 30 ? "text-stone-300" : "text-stone-500"}`}>
                      {b.snapshots_24h.toLocaleString("en-GB")}
                    </span>
                  </td>
                  <td className="text-right px-2 text-[10px] text-stone-400 tabular-nums">
                    {c.last_scan_age_min !== null && c.last_scan_age_min !== undefined
                      ? `${c.last_scan_age_min} dk önce`
                      : "—"}
                  </td>
                  <td className="text-right pr-3 pl-2">
                    {b.warnings.length === 0
                      ? <span className="text-[10px] text-emerald-400">—</span>
                      : (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-200 border border-amber-500/40" title={b.warnings.join(" · ")}>
                          <AlertTriangle className="w-2.5 h-2.5" /> {b.warnings.length}
                        </span>
                      )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-stone-500">
        💡 "CANLI" = Smart Scanner backend task'ı şu an çalışıyor · "Duraklamış" = DB'de aktif ama in-memory down (watchdog en fazla 60 sn içinde yeniden başlatır)
      </p>
    </div>
  );
}
