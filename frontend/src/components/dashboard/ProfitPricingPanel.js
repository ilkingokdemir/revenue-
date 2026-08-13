import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Coins, TrendUp, TrendDown, Warning, FloppyDisk, Robot, Play } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ProfitPricingPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [auto, setAuto] = useState(null);
  const [running, setRunning] = useState(false);

  const loadAuto = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/profit-pricing/${pid}/autopilot`);
      setAuto(d);
    } catch { /* silent */ }
  }, [pid]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/profit-pricing/${pid}?days=14`);
      setData(d);
      setSettings({ cpor: d.settings.cpor, payment_fee_pct: d.settings.payment_fee_pct,
        direct_acquisition_cost: d.settings.direct_acquisition_cost,
        ancillary: { ...d.settings.ancillary }, refund_risk_pct: { ...d.settings.refund_risk_pct },
        promo_funding_pct: { ...d.settings.promo_funding_pct } });
    } catch (e) { toast.error(e?.response?.data?.detail || "Yüklenemedi"); }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadAuto(); }, [loadAuto]);

  const toggleAuto = async () => {
    const next = !auto?.enabled;
    await axios.post(`${API}/profit-pricing/${pid}/autopilot`, { enabled: next });
    toast.success(next ? "Kâr Otopilotu AÇIK — her gece yarısı çalışacak" : "Kâr Otopilotu kapatıldı");
    loadAuto();
  };
  const runNow = async () => {
    setRunning(true);
    try {
      const { data: r } = await axios.post(`${API}/profit-pricing/${pid}/autopilot/run`);
      const n = (r.actions || []).length;
      toast.success(n ? `${n} kanal aksiyonu alındı` : "Aksiyon gerekmedi — tüm kanallar net pozitif");
      loadAuto();
    } catch { toast.error("Çalıştırılamadı"); }
    finally { setRunning(false); }
  };

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/profit-pricing/${pid}/settings`, settings);
      toast.success("Ayarlar kaydedildi");
      load();
    } catch { toast.error("Kaydedilemedi"); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  const labels = data.channel_labels || {};
  const channels = Object.keys(data.channel_net_avg || {});
  const netColor = (v) => v <= 0 ? "text-rose-700 bg-rose-50" : v < data.channel_net_avg.direct * 0.85 ? "text-amber-700 bg-amber-50" : "text-emerald-700 bg-emerald-50";

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="profit-pricing-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <Coins size={22} weight="fill" className="text-amber-600" /> Kâr-Öncelikli Fiyatlama
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          BEONx tarzı net katkı analizi: fiyat − OTA komisyonu − CPOR + beklenen ekstra harcama.
          Aynı fiyatlı iki rezervasyon farklı kâr bırakır — kanal kararını net kârla verin.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200" data-testid="pp-best-channel">
          <div className="flex items-center gap-1 text-[10px] uppercase font-bold text-emerald-600"><TrendUp size={12} /> En kârlı kanal</div>
          <div className="text-lg font-black text-emerald-900">{data.summary.best_channel.label}</div>
          <div className="text-xs text-emerald-700">Ø net {data.summary.best_channel.net_avg} / oda-gece</div>
        </div>
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200" data-testid="pp-worst-channel">
          <div className="flex items-center gap-1 text-[10px] uppercase font-bold text-rose-600"><TrendDown size={12} /> En düşük net</div>
          <div className="text-lg font-black text-rose-900">{data.summary.worst_channel.label}</div>
          <div className="text-xs text-rose-700">Ø net {data.summary.worst_channel.net_avg} · direktten {data.summary.direct_premium} geride</div>
        </div>
        <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="pp-cpor-card">
          <div className="text-[10px] uppercase font-bold text-stone-400">CPOR (dolu oda maliyeti)</div>
          <div className="text-lg font-black text-stone-900">{data.settings.cpor}</div>
          <div className="text-xs text-stone-500">temizlik + amenity + enerji / gece</div>
        </div>
      </div>

      {/* Kâr Otopilotu */}
      <div className={`rounded-2xl border p-5 ${auto?.enabled ? "bg-emerald-50 border-emerald-200" : "bg-white border-stone-200"}`} data-testid="pp-autopilot-card">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Robot size={26} weight="fill" className={auto?.enabled ? "text-emerald-600" : "text-stone-400"} />
            <div>
              <h2 className="text-sm font-black text-stone-900">Kâr Otopilotu</h2>
              <p className="text-[11px] text-stone-500">
                Her gece yarısı net katkısı negatif OTA kanallarını otomatik stop-sell'e alır, pozitife dönenleri açar.
                {auto?.last_run && <> Son çalışma: {new Date(auto.last_run).toLocaleString("tr-TR")}</>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={runNow} disabled={running} data-testid="pp-autopilot-run"
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-300 hover:bg-stone-50 text-xs font-bold text-stone-700 disabled:opacity-50">
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play size={13} weight="fill" />} Şimdi çalıştır
            </button>
            <button onClick={toggleAuto} data-testid="pp-autopilot-toggle"
              className={`px-4 py-2 rounded-xl text-xs font-bold ${auto?.enabled ? "bg-emerald-600 text-white" : "bg-stone-900 text-white hover:bg-stone-700"}`}>
              {auto?.enabled ? "AÇIK — Kapat" : "Otopilotu Aç"}
            </button>
          </div>
        </div>
        {(auto?.active_stop_sells || []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2" data-testid="pp-active-stopsells">
            {auto.active_stop_sells.map((s) => (
              <span key={s.id} className="px-2.5 py-1 rounded-full bg-rose-100 text-rose-700 text-[10px] font-bold">
                🚫 {auto.channel_labels?.[s.channel] || s.channel} · {s.from_date} → {s.to_date} (net {s.net_avg})
              </span>
            ))}
          </div>
        )}
        {(auto?.log || []).length > 0 && (
          <div className="mt-3 text-[11px] text-stone-500 space-y-1" data-testid="pp-autopilot-log">
            {auto.log.slice(0, 3).map((l) => (
              <p key={l.id}>· {new Date(l.run_at).toLocaleString("tr-TR")} ({l.trigger}) — {(l.actions || []).length ? l.actions.map((x) => `${x.channel}:${x.action}`).join(", ") : "aksiyon yok"}</p>
            ))}
          </div>
        )}
      </div>

      {/* Findings */}
      {data.findings.length > 0 && (
        <div className="space-y-2" data-testid="pp-findings">
          {data.findings.map((f) => (
            <div key={f.channel} className={`flex items-start gap-3 p-3.5 rounded-xl border ${f.severity === "critical" ? "bg-rose-50 border-rose-200" : "bg-amber-50 border-amber-200"}`} data-testid={`pp-finding-${f.channel}`}>
              <Warning size={18} weight="fill" className={f.severity === "critical" ? "text-rose-500" : "text-amber-500"} />
              <p className="text-xs text-stone-700 leading-relaxed">{f.suggestion}</p>
            </div>
          ))}
        </div>
      )}

      {/* Matrix */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-x-auto">
        <table className="w-full text-xs" data-testid="pp-matrix">
          <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
            <tr>
              <th className="px-3 py-2 text-left">Tarih</th>
              <th className="px-3 py-2 text-right">Brüt fiyat</th>
              {channels.map((ch) => <th key={ch} className="px-3 py-2 text-right">{labels[ch] || ch}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.matrix.map((r) => (
              <tr key={r.date} className="border-t border-stone-100">
                <td className="px-3 py-1.5 font-semibold text-stone-800">{r.date}</td>
                <td className="px-3 py-1.5 text-right text-stone-500">{r.gross}</td>
                {channels.map((ch) => (
                  <td key={ch} className="px-3 py-1.5 text-right">
                    <span className={`px-1.5 py-0.5 rounded font-bold ${netColor(r.channels[ch].net)}`}>{r.channels[ch].net}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Settings */}
      {settings && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="pp-settings">
          <h2 className="text-sm font-black text-stone-900 mb-3">Maliyet & Ancillary Ayarları <span className="text-[10px] font-normal text-stone-400">(net = fiyat − komisyon − ödeme ücreti − CPOR − iade riski − promo fonlama + ekstra harcama)</span></h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end mb-3">
            <div>
              <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">CPOR</label>
              <input type="number" min="0" value={settings.cpor}
                onChange={(e) => setSettings({ ...settings, cpor: parseFloat(e.target.value) || 0 })}
                data-testid="pp-cpor-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Ödeme ücreti %</label>
              <input type="number" min="0" max="10" step="0.1" value={settings.payment_fee_pct}
                onChange={(e) => setSettings({ ...settings, payment_fee_pct: parseFloat(e.target.value) || 0 })}
                data-testid="pp-payfee-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Direct edinim maliyeti</label>
              <input type="number" min="0" value={settings.direct_acquisition_cost}
                onChange={(e) => setSettings({ ...settings, direct_acquisition_cost: parseFloat(e.target.value) || 0 })}
                data-testid="pp-dac-input" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end mb-3">
            {Object.keys(settings.ancillary).map((ch) => (
              <div key={ch}>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">{labels[ch] || ch} ekstra</label>
                <input type="number" min="0" value={settings.ancillary[ch]}
                  onChange={(e) => setSettings({ ...settings, ancillary: { ...settings.ancillary, [ch]: parseFloat(e.target.value) || 0 } })}
                  data-testid={`pp-anc-${ch}`} className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
            {Object.keys(settings.refund_risk_pct || {}).map((ch) => (
              <div key={ch}>
                <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">{labels[ch] || ch} iade riski %</label>
                <input type="number" min="0" max="50" step="0.5" value={settings.refund_risk_pct[ch]}
                  onChange={(e) => setSettings({ ...settings, refund_risk_pct: { ...settings.refund_risk_pct, [ch]: parseFloat(e.target.value) || 0 } })}
                  data-testid={`pp-refund-${ch}`} className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
              </div>
            ))}
          </div>
          <button onClick={save} disabled={saving} data-testid="pp-save-settings"
            className="mt-4 flex items-center gap-2 px-4 py-2 rounded-xl bg-stone-900 hover:bg-stone-700 text-white text-xs font-bold disabled:opacity-50">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FloppyDisk size={14} />} Kaydet & Yeniden Hesapla
          </button>
        </div>
      )}
    </div>
  );
}
