import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import JobQueueCard from "./JobQueueCard";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_UI = {
  healthy: ["bg-emerald-50 border-emerald-200 text-emerald-700", "🟢 SAĞLIKLI", "Tüm sistemler normal çalışıyor"],
  degraded: ["bg-amber-50 border-amber-200 text-amber-700", "🟡 YAVAŞLAMA", "Bazı uçlarda yavaşlık veya artan hata var"],
  unhealthy: ["bg-rose-50 border-rose-200 text-rose-700", "🔴 SORUNLU", "Kritik hata oranı veya DB erişim sorunu"],
};

const fmtUp = (s) => {
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d > 0 ? `${d}g ${h}s` : h > 0 ? `${h}s ${m}dk` : `${m}dk`;
};

export default function SystemHealthPanel() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/system-health/status`);
      setD(r.data); setErr(false);
    } catch { setErr(true); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (err) return <div className="p-6 text-sm text-rose-600 font-bold" data-testid="health-error">Durum servisi yanıt vermiyor 🔴</div>;
  if (!d) return <div className="p-6 text-sm text-stone-400">Yükleniyor...</div>;
  const [cls, badge, desc] = STATUS_UI[d.status] || STATUS_UI.degraded;

  return (
    <div className="p-5 lg:p-7 max-w-[1100px] mx-auto space-y-4" data-testid="system-health-page">
      <JobQueueCard />
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-2xl font-semibold text-stone-900">🩺 Sistem Sağlığı</h1>
        <span className="text-[11px] text-stone-400">30 sn'de bir yenilenir · pencere: {d.window}</span>
      </div>

      <div className={`flex flex-wrap items-center gap-3 border rounded-2xl p-4 ${cls}`} data-testid="health-status-banner">
        <span className="text-lg font-black">{badge}</span>
        <span className="flex-1 text-xs font-bold">{desc}</span>
        <span className="text-[11px] font-bold">Çalışma süresi: {fmtUp(d.uptime_s)}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {[["İstek (1s)", d.requests, "text-stone-800"],
          ["Ort. Yanıt", `${d.avg_ms} ms`, "text-sky-600"],
          ["P95 Yanıt", `${d.p95_ms} ms`, d.p95_ms > 3000 ? "text-rose-600" : "text-indigo-600"],
          ["4xx Hata", d.errors_4xx, "text-amber-600"],
          ["5xx Hata", d.errors_5xx, d.errors_5xx > 0 ? "text-rose-600" : "text-emerald-600"],
          ["DB Ping", d.db_ping_ms === null ? "—" : `${d.db_ping_ms} ms`, d.db_ping_ms > 250 ? "text-rose-600" : "text-emerald-600"]].map(([l, v, c]) => (
          <div key={l} className="bg-white border border-stone-200 rounded-xl px-3 py-2.5" data-testid={`health-metric-${l}`}>
            <div className={`text-lg font-black ${c}`}>{v}</div>
            <div className="text-[10px] font-bold text-stone-500 uppercase">{l}</div>
          </div>
        ))}
      </div>

      <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="health-slowest">
        <h2 className="text-sm font-black text-stone-800 mb-2">🐢 En Yavaş Uçlar (ort. süreye göre)</h2>
        {d.slowest_endpoints.length === 0 ? <p className="text-xs text-stone-400">Son 1 saatte kayıtlı istek yok.</p> : (
          <div className="space-y-1">
            {d.slowest_endpoints.map((e) => (
              <div key={e.endpoint} className="flex items-center gap-2 text-xs bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5">
                <code className="flex-1 min-w-[200px] text-[11px] text-stone-700 truncate">{e.endpoint}</code>
                <span className="text-stone-400">{e.count}×</span>
                <span className={`font-black ${e.avg_ms > 2000 ? "text-rose-600" : e.avg_ms > 800 ? "text-amber-600" : "text-stone-700"}`}>{e.avg_ms} ms ort</span>
                <span className="text-stone-400">max {e.max_ms} ms</span>
                {e.errors > 0 && <span className="text-rose-500 font-bold">{e.errors} hata</span>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="health-recent-errors">
        <h2 className="text-sm font-black text-stone-800 mb-2">⚠️ Son Hatalar</h2>
        {d.recent_errors.length === 0 ? <p className="text-xs text-emerald-600 font-bold">Kayıtlı hata yok 🎉</p> : (
          <div className="space-y-1">
            {d.recent_errors.map((e, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-rose-50/50 border border-rose-100 rounded-lg px-2.5 py-1.5">
                <span className={`px-1.5 py-0.5 rounded font-black text-[10px] ${e.status >= 500 ? "bg-rose-600 text-white" : "bg-amber-100 text-amber-700"}`}>{e.status}</span>
                <code className="flex-1 min-w-[180px] text-[11px] text-stone-600 truncate">{e.method} {e.path}</code>
                <span className="text-stone-400">{e.dur_ms} ms</span>
                <span className="text-[10px] text-stone-400">{new Date(e.ts).toLocaleTimeString("tr-TR")}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
