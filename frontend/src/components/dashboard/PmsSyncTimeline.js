import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const HEALTH = { healthy: ["Sağlıklı", "bg-emerald-100 text-emerald-700"], degraded: ["Hatalı", "bg-rose-100 text-rose-700"], no_data: ["Veri yok", "bg-stone-100 text-stone-500"] };
const fmt = (s) => (s ? String(s).slice(0, 16).replace("T", " ") : "—");

export default function PmsSyncTimeline({ pid, provider, lastLogId, onResynced }) {
  const [tl, setTl] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/api/pms-connect/${provider}/sync-timeline/${pid}?days=30`, { withCredentials: true }); setTl(r.data); } catch { setTl(null); }
    try { const a = await axios.get(`${API}/api/pms-connect/sync-alerts/${pid}?provider=${provider}`, { withCredentials: true }); setAlerts(a.data); } catch { setAlerts(null); }
  }, [pid, provider]);
  const saveCfg = async (patch) => {
    try { const r = await axios.put(`${API}/api/pms-connect/sync-alerts/config/${pid}`, { ...(alerts?.config || {}), ...patch }, { withCredentials: true }); setAlerts((a) => ({ ...a, config: r.data })); toast.success("Uyarı ayarı kaydedildi"); }
    catch { toast.error("Kaydedilemedi"); }
  };
  useEffect(() => { load(); }, [load, lastLogId]);

  const resync = async (logId) => {
    setBusy(logId);
    try {
      const r = await axios.post(`${API}/api/pms-connect/${provider}/resync/${pid}/${logId}`, {}, { withCredentials: true });
      toast.success(`${r.data.pushed_days} gün yeniden gönderildi (${r.data.mocked ? "MOCK" : "CANLI"})`); load(); if (onResynced) onResynced();
    } catch (e) { toast.error(e.response?.data?.detail || "Yeniden senkron başarısız"); load(); }
    finally { setBusy(""); }
  };

  if (!tl) return null;
  const [hl, hc] = HEALTH[tl.health] || HEALTH.no_data;
  const max = Math.max(1, ...tl.timeline.map((d) => d.ok + d.failed + d.mocked));
  return (
    <section className="bg-white border border-stone-200 rounded-xl p-4 mb-4" data-testid="pms-sync-timeline">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <h2 className="text-base font-bold text-stone-800">Senkron Zaman Çizelgesi (30 gün)</h2>
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${hc}`} data-testid="pms-sync-health">{hl}</span>
        <span className="text-[11px] text-stone-500">{tl.totals.ok} başarılı · <b className={tl.totals.failed ? "text-rose-600" : ""}>{tl.totals.failed} hata</b> · {tl.totals.mocked} mock</span>
        <span className="ml-auto text-[11px] text-stone-500" data-testid="pms-sync-last-success">Son başarılı: {fmt(tl.last_success_at)}</span>
        {lastLogId && <button disabled={!!busy} onClick={() => resync(lastLogId)} className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[11px] font-bold disabled:opacity-50" data-testid="pms-resync-last">↻ Son push'u yeniden gönder</button>}
      </div>
      {tl.timeline.length > 0 && (
        <div className="flex items-end gap-[3px] h-14 mb-2" data-testid="pms-sync-bars">
          {tl.timeline.map((d) => { const tot = d.ok + d.failed + d.mocked; return (
            <div key={d.date} title={`${d.date}: ${d.ok} ok · ${d.failed} hata · ${d.mocked} mock`} className="flex-1 flex flex-col justify-end min-w-[6px]" style={{ height: "100%" }}>
              <div className="w-full bg-emerald-500 rounded-t-sm" style={{ height: `${(d.ok / max) * 100}%` }} />
              <div className="w-full bg-amber-300" style={{ height: `${(d.mocked / max) * 100}%` }} />
              <div className="w-full bg-rose-500 rounded-b-sm" style={{ height: `${(d.failed / max) * 100}%`, minHeight: d.failed ? 3 : 0 }} />
              <span className="sr-only">{tot}</span>
            </div>); })}
        </div>
      )}
      {alerts?.open?.length > 0 && (
        <div className="text-[11px] text-rose-800 bg-rose-100 border border-rose-200 rounded-lg px-2 py-1.5 mb-2 font-bold" data-testid="pms-sync-alert-banner">
          🚨 {alerts.open[0].streak} ardışık başarısız push — yöneticilere e-posta gönderildi ({fmt(alerts.open[0].created_at)}). Başarılı bir push uyarıyı kapatır.
        </div>
      )}
      {alerts?.config && (
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-stone-600 mb-2" data-testid="pms-sync-alert-config">
          <label className="flex items-center gap-1"><input type="checkbox" checked={alerts.config.enabled !== false} onChange={(e) => saveCfg({ enabled: e.target.checked })} data-testid="pms-sync-alert-enabled" />Kesinti e-postası</label>
          <label className="flex items-center gap-1">eşik<input type="number" min={2} max={20} defaultValue={alerts.config.threshold || 3} onBlur={(e) => saveCfg({ threshold: Number(e.target.value) })} className="w-12 border border-stone-300 rounded px-1 py-0.5" data-testid="pms-sync-alert-threshold" /> ardışık hata</label>
          <span className="text-stone-400">{alerts.config.emails?.length ? alerts.config.emails.join(", ") : "alıcı: tüm admin/manager"}</span>
          {alerts.alerts?.length ? <span className="ml-auto text-stone-400" data-testid="pms-sync-alert-count">{alerts.alerts.length} uyarı geçmişi</span> : null}
        </div>
      )}
      {tl.last_error && <div className="text-[11px] text-rose-700 bg-rose-50 border border-rose-100 rounded-lg px-2 py-1.5 mb-2" data-testid="pms-sync-last-error">Son hata ({fmt(tl.last_error.at)}): {tl.last_error.error}</div>}
      {tl.failed_entries.length > 0 && (
        <div className="space-y-1" data-testid="pms-sync-failed-list">
          {tl.failed_entries.map((f) => (
            <div key={f.id} className="flex items-center gap-2 text-[11px] bg-stone-50 rounded-lg px-2 py-1.5" data-testid={`pms-sync-failed-${f.id}`}>
              <span className="text-stone-500">{fmt(f.at)}</span><span className="font-bold">{f.rows} gün</span><span className="text-rose-600 truncate flex-1">{f.error}</span>
              <button disabled={busy === f.id} onClick={() => resync(f.id)} className="px-2 py-1 rounded-md bg-emerald-600 text-white text-[10px] font-bold disabled:opacity-50" data-testid={`pms-resync-${f.id}`}>Yeniden senkronla</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
