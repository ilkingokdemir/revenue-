import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Car, FloppyDisk } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ParkingRmsPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [data, setData] = useState(null);
  const [spaces, setSpaces] = useState(20);
  const [baseRate, setBaseRate] = useState(15);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/parking-rms/${pid}`, { withCredentials: true });
      setData(r.data);
      setSpaces(r.data.spaces);
      setBaseRate(r.data.base_rate);
    } catch { toast.error("Otopark verisi alınamadı"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await axios.post(`${API}/api/parking-rms/${pid}/settings`, { spaces, base_rate: baseRate }, { withCredentials: true });
      toast.success("Otopark ayarları kaydedildi");
      load();
    } catch { toast.error("Kaydedilemedi"); }
  };

  return (
    <div className="p-5 max-w-[1100px] mx-auto" data-testid="parking-rms-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Car size={13} weight="fill" className="text-cyan-600" /><span>Total Revenue Management</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Otopark RMS</h1>
        <p className="text-sm text-stone-500 mt-1">Otel doluluğuna göre otopark alanı için dinamik fiyat önerisi — RevPAS metriğiyle (park yeri başına gelir).</p>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4 mb-4 flex flex-wrap items-end gap-4">
        <label className="text-xs text-stone-600">Park yeri sayısı
          <input type="number" value={spaces} onChange={(e) => setSpaces(Number(e.target.value))} data-testid="parking-spaces-input"
            className="block mt-1 border border-stone-300 rounded-lg px-3 py-2 text-sm w-28" />
        </label>
        <label className="text-xs text-stone-600">Baz fiyat (gece, £)
          <input type="number" value={baseRate} onChange={(e) => setBaseRate(Number(e.target.value))} data-testid="parking-rate-input"
            className="block mt-1 border border-stone-300 rounded-lg px-3 py-2 text-sm w-28" />
        </label>
        <button onClick={save} data-testid="parking-save-btn"
          className="px-3 py-2 text-xs font-bold rounded-lg bg-cyan-600 text-white hover:bg-cyan-700 inline-flex items-center gap-1.5">
          <FloppyDisk size={13} weight="fill" /> Kaydet
        </button>
        {data && <div className="ml-auto text-right">
          <div className="text-lg font-black text-cyan-700" data-testid="parking-revpas">£{data.avg_revpas}</div>
          <div className="text-[10px] text-stone-400">14 gün ort. RevPAS</div>
        </div>}
      </div>

      {data && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <table className="w-full text-xs" data-testid="parking-table">
            <thead><tr className="text-left text-stone-400 border-b border-stone-100">
              <th className="py-1.5">Tarih</th><th className="text-right">Otel Doluluk</th>
              <th className="text-right">Baz</th><th className="text-right">Önerilen</th>
              <th className="text-right">Δ</th><th className="text-right">Beklenen Kullanım</th><th className="text-right">RevPAS</th>
            </tr></thead>
            <tbody>
              {data.days.map((d) => (
                <tr key={d.date} className="border-b border-stone-50" data-testid={`parking-row-${d.date}`}>
                  <td className="py-1.5 font-semibold text-stone-700">{d.date}</td>
                  <td className="text-right">%{d.hotel_occ}</td>
                  <td className="text-right text-stone-400">£{d.current_price}</td>
                  <td className="text-right font-bold text-stone-900">£{d.suggested_price}</td>
                  <td className={`text-right font-bold ${d.delta_pct > 0 ? "text-emerald-600" : d.delta_pct < 0 ? "text-rose-600" : "text-stone-400"}`}>
                    {d.delta_pct > 0 ? "+" : ""}{d.delta_pct}%</td>
                  <td className="text-right">%{d.expected_utilization}</td>
                  <td className="text-right font-semibold">£{d.revpas}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-stone-400 mt-3">{data.note}</p>
        </div>
      )}
    </div>
  );
}
