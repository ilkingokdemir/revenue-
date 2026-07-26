import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Lightning, ArrowsClockwise, Gauge } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/intraday-reprice`;

export default function IntradayRepricePanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}`);
      setData(r.data);
    } catch { toast.error("Gün-içi re-price verisi yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/scan`);
      toast.success(`${r.data.properties_scanned} tesis tarandı · ${r.data.actions} sıçrama aksiyonu`);
      load();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  }

  async function saveCfg(e) {
    e.preventDefault();
    if (propertyId === "all") { toast.error("Ayar için tesis seçin"); return; }
    const f = e.target;
    setSaving(true);
    try {
      await axios.put(`${API}/${propertyId}/config`, {
        enabled: f.enabled.checked,
        window_hours: parseInt(f.window.value, 10),
        spike_rooms: parseInt(f.spike.value, 10),
        cooldown_hours: parseInt(f.cooldown.value, 10),
      });
      toast.success("Ayarlar kaydedildi"); load();
    } catch { toast.error("Kaydedilemedi"); }
    setSaving(false);
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const { config: c, summary: s } = data;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="intraday-reprice-panel">
      <div className="bg-gradient-to-br from-stone-900 via-amber-950 to-rose-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-300">
              <Lightning size={14} /> Intraday Re-price
            </div>
            <h1 className="text-2xl font-bold mt-1">Gün-İçi Yeniden Fiyatlama</h1>
            <p className="text-sm text-stone-300 mt-1">Her 30 dakikada pickup sıçramalarını izler; sıçrama algılanınca AI fiyatlama motorunu anında tetikler. Fırsat gece cron'unu beklemez.</p>
          </div>
          <button onClick={scan} disabled={scanning} data-testid="idr-scan-btn"
            className="px-4 py-2 bg-amber-400 hover:bg-amber-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} />
            {scanning ? "Taranıyor…" : "Şimdi Tara"}
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-5">
          <Stat label="Sıçrama (24 saat)" value={s.events_24h} testid="idr-stat-24h" />
          <Stat label="Oto-uygulanan fiyat" value={s.auto_applied_total} testid="idr-stat-applied" />
          <Stat label="Toplam olay" value={s.total_events} testid="idr-stat-total" />
        </div>
      </div>

      <form onSubmit={saveCfg} className="bg-white border border-stone-200 rounded-xl p-4 flex items-end gap-4 flex-wrap" data-testid="idr-config-form">
        <div className="flex items-center gap-2 text-sm font-semibold text-stone-700"><Gauge size={16} /> Eşikler</div>
        <label className="flex items-center gap-1.5 text-sm text-stone-600">
          <input name="enabled" type="checkbox" defaultChecked={c.enabled} className="accent-amber-500" data-testid="idr-cfg-enabled" /> Aktif
        </label>
        <label className="text-[10px] uppercase text-stone-400">Pencere (saat)
          <input name="window" type="number" min="1" max="12" defaultValue={c.window_hours} data-testid="idr-cfg-window"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <label className="text-[10px] uppercase text-stone-400">Sıçrama eşiği (oda)
          <input name="spike" type="number" min="2" max="20" defaultValue={c.spike_rooms} data-testid="idr-cfg-spike"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <label className="text-[10px] uppercase text-stone-400">Cooldown (saat)
          <input name="cooldown" type="number" min="1" max="24" defaultValue={c.cooldown_hours} data-testid="idr-cfg-cooldown"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <button type="submit" disabled={saving} data-testid="idr-cfg-save"
          className="px-3 py-1.5 bg-stone-900 hover:bg-stone-700 text-white rounded-lg text-xs font-bold disabled:opacity-60">Kaydet</button>
        <span className="text-[10px] text-stone-400">Örn: {c.window_hours} saatte aynı tarihe ≥{c.spike_rooms} rezervasyon → re-price</span>
      </form>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Zaman</th><th className="text-left px-2 py-2">Tesis</th>
            <th className="text-left px-2 py-2">Konaklama tarihi</th><th className="text-center px-2 py-2">Pickup</th>
            <th className="text-center px-2 py-2">Doluluk</th><th className="text-left px-2 py-2">Aksiyon</th>
          </tr></thead>
          <tbody>
            {data.events.map(e => (
              <tr key={e.id} className="border-b border-stone-50" data-testid={`idr-event-${e.id}`}>
                <td className="px-4 py-2 text-xs text-stone-500">{new Date(e.created_at).toLocaleString("tr-TR")}</td>
                <td className="px-2 py-2 text-xs">{e.property_id}</td>
                <td className="px-2 py-2 font-mono text-xs">{e.stay_date}</td>
                <td className="px-2 py-2 text-center font-bold">{e.rooms_picked} oda<span className="text-[10px] text-stone-400 font-normal">/{e.window_hours}s</span></td>
                <td className="px-2 py-2 text-center">%{e.occupancy_pct}</td>
                <td className="px-2 py-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${e.action === "auto_applied" ? "bg-emerald-50 text-emerald-700" : "bg-sky-50 text-sky-700"}`}>
                    {e.action === "auto_applied" ? `⚡ ${e.applied_count} fiyat oto-uygulandı` : "Öneri hazırlandı"}
                  </span>
                </td>
              </tr>
            ))}
            {data.events.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-stone-400 text-sm">
                Henüz sıçrama olayı yok. Motor her 30 dakikada arka planda tarıyor; "Şimdi Tara" ile manuel de tetikleyebilirsiniz.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
