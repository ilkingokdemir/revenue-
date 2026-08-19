import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { TrendUp, Lightning, Play, ShieldCheck } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PriceGuardsPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [poba, setPoba] = useState({ enabled: false, occ_threshold_pct: 80, uplift_pct: 10, days_ahead: 30 });
  const [surge, setSurge] = useState({ enabled: false, pickup_threshold: 5, horizon_days: 30, cap_multiplier: 1.3, action: "alert_and_cap" });
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/price-guards/${pid}`);
      if (data.config?.poba) setPoba(data.config.poba);
      if (data.config?.surge) setSurge(data.config.surge);
      setLog(data.log || []);
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const savePoba = async (next) => {
    setPoba(next);
    try { await axios.post(`${API}/price-guards/${pid}/poba`, next); toast.success("POBA kaydedildi"); }
    catch { toast.error("Kaydedilemedi"); }
  };
  const saveSurge = async (next) => {
    setSurge(next);
    try { await axios.post(`${API}/price-guards/${pid}/surge`, next); toast.success("Surge koruması kaydedildi"); }
    catch { toast.error("Kaydedilemedi"); }
  };
  const runNow = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/price-guards/${pid}/run`);
      toast.success(data.count > 0 ? `${data.count} aksiyon uygulandı` : "Eşik aşan tarih yok — aksiyon gerekmedi");
      load();
    } catch { toast.error("Çalıştırılamadı"); }
    setBusy(false);
  };

  const numIn = "w-20 rounded border border-stone-200 px-2 py-1 text-xs";

  return (
    <div className="p-6 max-w-4xl" data-testid="price-guards-panel">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-stone-800">Fiyat Bekçileri</h2>
          <p className="text-xs text-stone-500 mt-1">POBA (portföy doluluk zammı) ve Surge Koruması — saatte bir otomatik tarar; bekçiler guardrail'lerinize saygı duyar.</p>
        </div>
        <button onClick={runNow} disabled={busy} data-testid="guards-run-now-btn"
          className="px-4 py-2 rounded-lg bg-stone-900 text-white text-xs font-bold hover:bg-stone-700 disabled:opacity-50 flex items-center gap-1.5">
          <Play size={13} weight="fill" /> Şimdi Çalıştır
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid="poba-card">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendUp size={18} weight="bold" className="text-emerald-600" />
              <h3 className="text-sm font-bold text-stone-800">Portföy Doluluk Zammı (POBA)</h3>
            </div>
            <button onClick={() => savePoba({ ...poba, enabled: !poba.enabled })} data-testid="poba-toggle"
              className={`w-10 h-5.5 rounded-full p-0.5 transition-colors ${poba.enabled ? "bg-emerald-500" : "bg-stone-300"}`}>
              <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${poba.enabled ? "translate-x-5" : ""}`} />
            </button>
          </div>
          <p className="text-[11px] text-stone-500 mb-3">Doluluk eşiği aşılan tarihlerde kalan odalara otomatik zam (PriceLabs paritesi).</p>
          <div className="space-y-2 text-xs text-stone-700">
            <div className="flex items-center justify-between">Doluluk eşiği (%)
              <input type="number" value={poba.occ_threshold_pct} data-testid="poba-threshold-input"
                onChange={(e) => setPoba({ ...poba, occ_threshold_pct: parseFloat(e.target.value) || 0 })}
                onBlur={() => savePoba(poba)} className={numIn} /></div>
            <div className="flex items-center justify-between">Zam oranı (%)
              <input type="number" value={poba.uplift_pct} data-testid="poba-uplift-input"
                onChange={(e) => setPoba({ ...poba, uplift_pct: parseFloat(e.target.value) || 0 })}
                onBlur={() => savePoba(poba)} className={numIn} /></div>
            <div className="flex items-center justify-between">İleri bakış (gün)
              <input type="number" value={poba.days_ahead} data-testid="poba-days-input"
                onChange={(e) => setPoba({ ...poba, days_ahead: parseInt(e.target.value) || 30 })}
                onBlur={() => savePoba(poba)} className={numIn} /></div>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid="surge-card">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Lightning size={18} weight="fill" className="text-amber-500" />
              <h3 className="text-sm font-bold text-stone-800">Surge Koruması</h3>
            </div>
            <button onClick={() => saveSurge({ ...surge, enabled: !surge.enabled })} data-testid="surge-toggle"
              className={`w-10 h-5.5 rounded-full p-0.5 transition-colors ${surge.enabled ? "bg-amber-500" : "bg-stone-300"}`}>
              <div className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${surge.enabled ? "translate-x-5" : ""}`} />
            </button>
          </div>
          <p className="text-[11px] text-stone-500 mb-3">Ani talep sıçramasında alarm + fiyatı koruma tavanına çeker (RoomPriceGenie paritesi).</p>
          <div className="space-y-2 text-xs text-stone-700">
            <div className="flex items-center justify-between">24s pickup eşiği (rez.)
              <input type="number" value={surge.pickup_threshold} data-testid="surge-threshold-input"
                onChange={(e) => setSurge({ ...surge, pickup_threshold: parseInt(e.target.value) || 5 })}
                onBlur={() => saveSurge(surge)} className={numIn} /></div>
            <div className="flex items-center justify-between">Koruma çarpanı (× baz)
              <input type="number" step="0.05" value={surge.cap_multiplier} data-testid="surge-mult-input"
                onChange={(e) => setSurge({ ...surge, cap_multiplier: parseFloat(e.target.value) || 1.3 })}
                onBlur={() => saveSurge(surge)} className={numIn} /></div>
            <div className="flex items-center justify-between">Aksiyon
              <select value={surge.action} data-testid="surge-action-select"
                onChange={(e) => saveSurge({ ...surge, action: e.target.value })}
                className="rounded border border-stone-200 px-2 py-1 text-xs">
                <option value="alert_and_cap">Alarm + Fiyat Koruması</option>
                <option value="alert_only">Sadece Alarm</option>
              </select></div>
          </div>
        </div>
      </div>

      <div className="mt-5 bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid="guards-log">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck size={16} weight="bold" className="text-stone-500" />
          <h3 className="text-sm font-bold text-stone-800">Bekçi Günlüğü</h3>
        </div>
        {log.length === 0 && <p className="text-[11px] text-stone-400">Henüz aksiyon yok. Bekçileri açın ve "Şimdi Çalıştır" deyin.</p>}
        <div className="space-y-1.5">
          {log.map((l) => (
            <div key={l.id} className="flex items-center gap-2 text-xs bg-stone-50 rounded-lg px-3 py-2" data-testid={`guard-log-${l.id}`}>
              <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded ${l.guard === "poba" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{l.guard}</span>
              <span className="font-mono text-stone-500">{l.date}</span>
              <span className="flex-1 text-stone-600">
                {l.guard === "poba"
                  ? `Doluluk %${l.occ_pct} → £${l.old_rate} ⇒ £${l.new_rate}`
                  : `24s pickup: ${l.pickup_24h} rez → koruma £${l.protect_rate}`}
              </span>
              <span className="text-[9px] text-stone-400">{(l.created_at || "").slice(0, 16).replace("T", " ")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
