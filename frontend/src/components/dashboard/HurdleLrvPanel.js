import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldCheck, Gauge, Bed, FloppyDisk, ArrowsClockwise } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const BAND_STYLE = {
  low: "bg-sky-50 text-sky-700 border-sky-200",
  moderate: "bg-stone-50 text-stone-600 border-stone-200",
  healthy: "bg-emerald-50 text-emerald-700 border-emerald-200",
  high: "bg-amber-50 text-amber-700 border-amber-200",
  peak: "bg-rose-50 text-rose-700 border-rose-200",
};
const BAND_TR = { low: "Düşük", moderate: "Orta", healthy: "Sağlıklı", high: "Yüksek", peak: "Zirve" };

export default function HurdleLrvPanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [minRate, setMinRate] = useState("");
  const [obCap, setObCap] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/revenue/hurdle/${propertyId}?days=30`);
      setData(res.data);
      setMinRate(String(res.data.config?.min_rate ?? 0));
      setObCap(String(res.data.config?.overbooking_cap ?? 3));
    } catch (e) {
      toast.error("Hurdle verisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/api/revenue/hurdle/${propertyId}/config`, {
        min_rate: parseFloat(minRate) || 0,
        overbooking_cap: parseInt(obCap) || 3,
      });
      toast.success("Konfigürasyon kaydedildi");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kaydetme başarısız");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="hurdle-loading">LRV hesaplanıyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const withActions = data.days.filter((d) => d.actions.length > 0);

  return (
    <div className="space-y-5" data-testid="hurdle-lrv-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ShieldCheck size={12} weight="fill" className="text-violet-500" />
          <span>Yield Guard</span>
        </div>
        <h2 className="text-xl font-semibold text-stone-900">Hurdle Rate & Last Room Value</h2>
        <p className="text-sm text-stone-500 mt-1">
          Her gün için minimum kabul edilebilir fiyat (LRV), talep bandı ve no-show tahminli overbooking önerisi.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-4 py-2.5">
          <Gauge size={18} className="text-violet-600" />
          <div>
            <div className="text-lg font-semibold text-stone-900" data-testid="hurdle-base-adr">£{data.base_adr}</div>
            <div className="text-[11px] text-stone-500">Baz ADR</div>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-4 py-2.5">
          <Bed size={18} className="text-cyan-600" />
          <div>
            <div className="text-lg font-semibold text-stone-900">{data.capacity}</div>
            <div className="text-[11px] text-stone-500">Toplam oda</div>
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-lg px-4 py-2">
          <label className="text-[10px] uppercase tracking-wide text-stone-500 block">Min. Fiyat Tabanı</label>
          <input value={minRate} onChange={(e) => setMinRate(e.target.value)} data-testid="hurdle-min-rate-input"
            className="w-20 text-sm font-medium text-stone-900 outline-none" />
        </div>
        <div className="bg-white border border-stone-200 rounded-lg px-4 py-2">
          <label className="text-[10px] uppercase tracking-wide text-stone-500 block">Overbooking Limiti</label>
          <input value={obCap} onChange={(e) => setObCap(e.target.value)} data-testid="hurdle-ob-cap-input"
            className="w-20 text-sm font-medium text-stone-900 outline-none" />
        </div>
        <button onClick={saveConfig} disabled={saving} data-testid="hurdle-save-config-btn"
          className="inline-flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg px-4 py-2.5 transition-colors">
          <FloppyDisk size={14} /> {saving ? "Kaydediliyor…" : "Kaydet"}
        </button>
        <button onClick={load} data-testid="hurdle-refresh-btn"
          className="ml-auto inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-2.5 bg-white transition-colors">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      {withActions.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4" data-testid="hurdle-actions-box">
          <div className="text-xs font-semibold text-amber-800 mb-2">Önerilen Aksiyonlar ({withActions.length} gün)</div>
          <ul className="space-y-1">
            {withActions.slice(0, 6).map((d) => (
              <li key={d.date} className="text-xs text-amber-900">
                <span className="font-medium">{d.date} ({d.dow}):</span> {d.actions.join(" · ")}
              </li>
            ))}
            {withActions.length > 6 && <li className="text-[11px] text-amber-700">+{withActions.length - 6} gün daha</li>}
          </ul>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-lg overflow-x-auto">
        <table className="w-full text-xs" data-testid="hurdle-table">
          <thead>
            <tr className="border-b border-stone-200 text-left text-[10px] uppercase tracking-wide text-stone-500">
              <th className="px-3 py-2.5">Tarih</th>
              <th className="px-3 py-2.5">Doluluk</th>
              <th className="px-3 py-2.5">Kalan Oda</th>
              <th className="px-3 py-2.5">7g Pickup</th>
              <th className="px-3 py-2.5">Talep Bandı</th>
              <th className="px-3 py-2.5">LRV (Hurdle)</th>
              <th className="px-3 py-2.5">No-show</th>
              <th className="px-3 py-2.5">Overbooking</th>
            </tr>
          </thead>
          <tbody>
            {data.days.map((d) => (
              <tr key={d.date} className="border-b border-stone-100 hover:bg-stone-50" data-testid={`hurdle-row-${d.date}`}>
                <td className="px-3 py-2 font-medium text-stone-800">{d.date} <span className="text-stone-400">{d.dow}</span></td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-stone-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${d.occupancy >= 80 ? "bg-rose-500" : d.occupancy >= 60 ? "bg-amber-500" : "bg-emerald-500"}`}
                        style={{ width: `${d.occupancy}%` }} />
                    </div>
                    <span className="text-stone-700">{d.occupancy}%</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-stone-600">{d.rooms_left}</td>
                <td className="px-3 py-2 text-stone-600">{d.pickup_7d > 0 ? `+${d.pickup_7d}` : "—"}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block border rounded-full px-2 py-0.5 text-[10px] font-medium ${BAND_STYLE[d.band]}`}>{BAND_TR[d.band]}</span>
                </td>
                <td className="px-3 py-2 font-semibold text-violet-700">£{d.lrv}</td>
                <td className="px-3 py-2 text-stone-600">{(d.noshow_rate * 100).toFixed(1)}%</td>
                <td className="px-3 py-2">
                  {d.overbooking_suggested > 0
                    ? <span className="text-emerald-700 font-medium">+{d.overbooking_suggested} oda</span>
                    : <span className="text-stone-400">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
