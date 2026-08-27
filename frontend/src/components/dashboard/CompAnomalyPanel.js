import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldWarning } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;

export default function CompAnomalyPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/comp-anomaly/${pid}?days=90`);
      setData(r.data);
    } catch { toast.error("Anomali verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function ignoreOne(a) {
    try {
      await axios.post(`${B}/api/comp-anomaly/${pid}/ignore`, { key: a.key, reason: a.reason });
      toast.success("Kayıt yoksayıldı — medyan hesaplarından düşülecek"); load();
    } catch { toast.error("İşlem başarısız"); }
  }

  async function ignoreAll() {
    setBusy("all");
    try {
      const r = await axios.post(`${B}/api/comp-anomaly/${pid}/ignore-all`);
      toast.success(`${r.data.ignored} sapkın kayıt yoksayıldı`); load();
    } catch { toast.error("İşlem başarısız"); }
    setBusy("");
  }

  async function saveCfg(e) {
    e.preventDefault(); setBusy("cfg");
    try {
      await axios.put(`${B}/api/comp-anomaly/${pid}/config`, {
        z_threshold: parseFloat(e.target.z.value),
        low_pct: parseFloat(e.target.lo.value),
        high_pct: parseFloat(e.target.hi.value),
      });
      toast.success("Anomali kuralları güncellendi"); load();
    } catch { toast.error("Kaydedilemedi"); }
    setBusy("");
  }

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="anomaly-loading">Rakip verisi taranıyor…</p>;

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-4" data-testid="comp-anomaly-panel">
      <div className="bg-gradient-to-br from-amber-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldWarning size={22} className="text-amber-400" /> Rakip Veri Anomali Düzeltme
        </h1>
        <p className="text-sm text-stone-300 mt-1">Sapkın rakip fiyatları (tek oda kalıntısı, suit karışması, hatalı tarama) fiyat motoruna girmeden ayıklanır (IDeaS paritesi).</p>
        <div className="flex gap-6 mt-3 text-sm">
          <span data-testid="anomaly-active-count"><b className="text-amber-400 text-xl">{data.active}</b> aktif sapkın</span>
          <span><b className="text-stone-300 text-xl">{data.ignored}</b> yoksayıldı</span>
          <span><b className="text-stone-300 text-xl">{data.total}</b> toplam tespit</span>
        </div>
      </div>

      <form onSubmit={saveCfg} className="bg-white rounded-2xl border border-stone-200 p-4 flex flex-wrap items-end gap-3" data-testid="anomaly-config-card">
        <label className="text-xs text-stone-500">Z-eşiği<input name="z" type="number" step="0.5" min="1.5" max="6" defaultValue={data.config.z_threshold} data-testid="anomaly-z-input" className="block border rounded-lg px-2 py-1.5 text-sm w-24 mt-1" /></label>
        <label className="text-xs text-stone-500">Alt bant (%)<input name="lo" type="number" min="10" max="90" defaultValue={data.config.low_pct} data-testid="anomaly-lo-input" className="block border rounded-lg px-2 py-1.5 text-sm w-24 mt-1" /></label>
        <label className="text-xs text-stone-500">Üst bant (%)<input name="hi" type="number" min="120" max="500" defaultValue={data.config.high_pct} data-testid="anomaly-hi-input" className="block border rounded-lg px-2 py-1.5 text-sm w-24 mt-1" /></label>
        <button type="submit" disabled={busy === "cfg"} data-testid="anomaly-cfg-save-btn" className="px-4 py-2 rounded-full bg-stone-900 text-white text-xs font-bold disabled:opacity-50">Kuralları Kaydet</button>
        {data.active > 0 && (
          <button type="button" onClick={ignoreAll} disabled={busy === "all"} data-testid="anomaly-ignore-all-btn"
            className="ml-auto px-4 py-2 rounded-full bg-amber-500 text-stone-950 text-xs font-bold disabled:opacity-50">Tümünü Yoksay ({data.active})</button>
        )}
      </form>

      <div className="bg-white rounded-2xl border border-stone-200 overflow-x-auto">
        {data.anomalies.length === 0 ? (
          <p className="p-5 text-sm text-stone-400" data-testid="anomaly-empty">Sapkın rakip fiyatı tespit edilmedi — veri temiz görünüyor. ✓</p>
        ) : (
          <table className="w-full text-sm" data-testid="anomaly-table">
            <thead><tr className="text-left text-[11px] text-stone-400 border-b">
              <th className="p-3">Rakip</th><th className="p-3">Tarih</th><th className="p-3">Fiyat</th><th className="p-3">Medyan</th><th className="p-3">Z</th><th className="p-3">Neden</th><th className="p-3">Kaynak</th><th className="p-3"></th>
            </tr></thead>
            <tbody>
              {data.anomalies.map((a, i) => (
                <tr key={a.key} className={`border-t border-stone-100 ${a.ignored ? "opacity-40" : ""}`} data-testid={`anomaly-row-${i}`}>
                  <td className="p-3 font-semibold">{a.comp_name}</td>
                  <td className="p-3 font-mono text-[12px]">{a.date}</td>
                  <td className="p-3 font-black text-rose-600">£{a.rate}</td>
                  <td className="p-3">£{a.median}</td>
                  <td className="p-3 font-mono">{a.z}</td>
                  <td className="p-3 text-[11px] text-stone-500 max-w-[280px]">{a.reason}</td>
                  <td className="p-3 text-[11px]">{a.source}</td>
                  <td className="p-3">{a.ignored ? <span className="text-[10px] font-bold text-stone-400">YOKSAYILDI</span> : (
                    <button onClick={() => ignoreOne(a)} data-testid={`anomaly-ignore-${i}`}
                      className="px-2.5 py-1 rounded-full border border-amber-300 text-amber-700 text-[10px] font-bold">Yoksay</button>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-[11px] text-stone-400">{data.note}</p>
    </div>
  );
}
