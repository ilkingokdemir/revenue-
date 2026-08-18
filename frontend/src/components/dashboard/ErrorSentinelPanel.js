import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldWarning, CheckCircle, ArrowsClockwise } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ErrorSentinelPanel() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState(null);
  const [scanning, setScanning] = useState(false);

  const loadHealth = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/health-sentinel/status`, { withCredentials: true });
      setHealth(r.data);
    } catch { /* silent */ }
  }, []);

  const runScan = async () => {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/api/health-sentinel/run`, {}, { withCredentials: true });
      r.data.fail_count > 0
        ? toast.warning(`🩺 ${r.data.fail_count} modül API'sinde sorun bulundu — bildirim gönderildi`)
        : toast.success(`🩺 ${r.data.ok_count} modül API'sinin tamamı sağlıklı ✓`);
      loadHealth();
    } catch { toast.error("Tarama çalıştırılamadı"); }
    finally { setScanning(false); }
  };

  useEffect(() => { loadHealth(); }, [loadHealth]);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/client-errors`, { withCredentials: true });
      setItems(r.data.items || []);
    } catch { toast.error("Hatalar yüklenemedi"); } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resolve = async (id) => {
    try {
      await axios.post(`${API}/api/client-errors/${id}/resolve`, {}, { withCredentials: true });
      toast.success("Çözüldü olarak işaretlendi");
      load();
    } catch { toast.error("İşaretlenemedi"); }
  };

  return (
    <div className="p-5 max-w-[1100px] mx-auto" data-testid="error-sentinel-panel">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ShieldWarning size={13} weight="fill" className="text-rose-500" /><span>Sistem Sağlığı</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Hata Nöbetçisi</h1>
          <p className="text-sm text-stone-500 mt-1">Kullanıcı ekranlarında yakalanan hatalar referans koduyla otomatik buraya düşer — kullanıcı bildirmeden haberiniz olur.</p>
        </div>
        <button onClick={load} disabled={busy} data-testid="sentinel-refresh-btn"
          className="px-3 py-2 text-xs rounded-md bg-stone-900 text-white hover:bg-stone-700 inline-flex items-center gap-1.5 font-medium">
          <ArrowsClockwise size={13} className={busy ? "animate-spin" : ""} /> Yenile
        </button>
      </div>

      {/* Sağlık Nöbetçisi */}
      <div className="bg-white border-2 border-emerald-200 rounded-xl p-5 mb-5" data-testid="health-sentinel-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-black text-stone-800">🩺 Sağlık Nöbetçisi</h2>
            <p className="text-xs text-stone-500 mt-0.5">Her gece {health?.endpoints || 29} modül API'sini yoklar — sorun bulursa zil bildirimine düşer.</p>
            {health?.last_run ? (
              <div className="flex items-center gap-3 mt-2 text-xs" data-testid="health-sentinel-last">
                <span className={`font-black px-2 py-0.5 rounded-full ${health.last_run.fail_count > 0 ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"}`}>
                  {health.last_run.fail_count > 0 ? `${health.last_run.fail_count} sorun` : "Tümü sağlıklı ✓"}
                </span>
                <span className="text-stone-400">{health.last_run.ok_count}/{health.last_run.ok_count + health.last_run.fail_count} OK · son tarama {new Date(health.last_run.at).toLocaleString("tr-TR")} · {health.last_run.duration_ms}ms</span>
              </div>
            ) : (
              <p className="text-[11px] text-stone-400 mt-2" data-testid="health-sentinel-none">Henüz tarama yapılmadı — robot gece çalışacak veya şimdi başlatabilirsiniz.</p>
            )}
          </div>
          <button onClick={runScan} disabled={scanning} data-testid="health-sentinel-run-btn"
            className="px-4 py-2 text-xs rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-bold disabled:opacity-50">
            {scanning ? "Taranıyor…" : "🩺 Şimdi Tara"}
          </button>
        </div>
        {health?.last_run?.failures?.length > 0 && (
          <div className="mt-3 space-y-1" data-testid="health-sentinel-failures">
            {health.last_run.failures.map((f) => (
              <div key={f.path} className="flex items-center justify-between text-[11px] bg-rose-50 border border-rose-100 rounded-lg px-3 py-1.5">
                <span className="font-bold text-rose-800">{f.module}</span>
                <span className="text-rose-500 font-mono">{f.path}</span>
                <span className="font-black text-rose-600">{f.status || "zaman aşımı"}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="bg-white border border-stone-200 rounded-xl p-10 text-center" data-testid="sentinel-empty">
          <CheckCircle size={32} weight="fill" className="text-emerald-500 mx-auto mb-2" />
          <div className="text-sm font-semibold text-stone-700">Açık hata yok 🎉</div>
          <div className="text-xs text-stone-400 mt-1">Yeni bir ekran hatası yakalanırsa bildirim alır ve burada görürsünüz.</div>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((e) => (
            <div key={e.id} className="bg-white border border-rose-100 rounded-xl p-4" data-testid={`sentinel-error-${e.id}`}>
              <div className="flex flex-wrap items-start gap-3">
                <div className="flex-1 min-w-[280px]">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-[10px] bg-rose-50 text-rose-700 border border-rose-200 rounded px-1.5 py-0.5">{e.last_ref || e.ref}</span>
                    <span className="text-[10px] text-stone-400">{(e.last_seen || "").replace("T", " ").slice(0, 16)}</span>
                    {e.count > 1 && <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">{e.count}× tekrarlandı</span>}
                  </div>
                  <div className="text-sm font-semibold text-stone-900 mt-1.5">{e.message}</div>
                  <div className="text-[11px] text-stone-500 mt-0.5 font-mono truncate">{e.url}</div>
                  {e.stack && (
                    <details className="mt-1.5">
                      <summary className="text-[10px] text-stone-400 cursor-pointer">stack trace</summary>
                      <pre className="text-[9px] bg-stone-50 border border-stone-100 rounded p-2 mt-1 overflow-x-auto max-h-32">{e.stack}</pre>
                    </details>
                  )}
                </div>
                <button onClick={() => resolve(e.id)} data-testid={`sentinel-resolve-${e.id}`}
                  className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700">
                  Çözüldü
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
