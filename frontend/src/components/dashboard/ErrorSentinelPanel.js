import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldWarning, CheckCircle, ArrowsClockwise } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ErrorSentinelPanel() {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

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
