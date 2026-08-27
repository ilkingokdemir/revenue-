import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ChartLineUp } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;

export default function RmsUpliftPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [data, setData] = useState(null);
  const [months, setMonths] = useState(12);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/rms-uplift/${pid}?months=${months}`);
      setData(r.data);
    } catch { toast.error("Uplift verisi yüklenemedi"); }
  }, [pid, months]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="uplift-loading">Uplift raporu hesaplanıyor…</p>;
  const maxRevpar = Math.max(...data.months.map((m) => m.revpar), 1);

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="rms-uplift-panel">
      <div className="bg-gradient-to-br from-emerald-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ChartLineUp size={22} className="text-emerald-400" /> RMS Etki Ölçer (Uplift Raporu)
        </h1>
        <p className="text-sm text-stone-300 mt-1">Fiyat motorunun baz senaryoya göre yarattığı gelir artışının kanıtı.</p>
        <div className="flex flex-wrap gap-6 mt-4">
          <div data-testid="uplift-total">
            <div className="text-3xl font-black text-emerald-400">{data.total_uplift_gbp >= 0 ? "+" : ""}£{Number(data.total_uplift_gbp).toLocaleString("en-GB")}</div>
            <div className="text-xs text-stone-400">toplam ek gelir ({data.robot_months} robot ayı)</div>
          </div>
          <div data-testid="uplift-pct">
            <div className="text-3xl font-black">{data.uplift_pct != null ? `${data.uplift_pct >= 0 ? "+" : ""}%${data.uplift_pct}` : "—"}</div>
            <div className="text-xs text-stone-400">RevPAR etkisi (baz £{data.baseline_revpar})</div>
          </div>
          <div>
            <div className="text-3xl font-black">{data.capacity}</div>
            <div className="text-xs text-stone-400">oda · robot başlangıcı: {data.robot_start || "—"}</div>
          </div>
        </div>
        <p className="text-sm mt-3 text-emerald-200/90" data-testid="uplift-verdict">{data.verdict}</p>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Aylık RevPAR — baz vs robot dönemi</h2>
          <select value={months} onChange={(e) => setMonths(+e.target.value)} data-testid="uplift-months-select"
            className="border rounded-lg px-2 py-1.5 text-sm">
            <option value={6}>6 ay</option><option value={12}>12 ay</option><option value={18}>18 ay</option><option value={24}>24 ay</option>
          </select>
        </div>
        <div className="space-y-1.5" data-testid="uplift-months-list">
          {data.months.map((m) => (
            <div key={m.month} className="flex items-center gap-2 text-xs" data-testid={`uplift-month-${m.month}`}>
              <span className="w-16 font-mono text-stone-500">{m.month}</span>
              <div className="flex-1 bg-stone-100 rounded-full h-5 relative overflow-hidden">
                <div className={`h-5 rounded-full ${m.phase === "robot" ? "bg-emerald-500" : "bg-stone-400"}`}
                  style={{ width: `${(m.revpar / maxRevpar) * 100}%` }} />
                {data.baseline_revpar > 0 && (
                  <div className="absolute top-0 h-5 w-0.5 bg-rose-500" style={{ left: `${Math.min((data.baseline_revpar / maxRevpar) * 100, 99)}%` }} />
                )}
              </div>
              <span className="w-20 text-right font-semibold">£{m.revpar}</span>
              <span className={`w-24 text-right font-mono ${m.uplift_gbp > 0 ? "text-emerald-600" : m.uplift_gbp < 0 ? "text-rose-500" : "text-stone-400"}`}>
                {m.uplift_gbp != null ? `${m.uplift_gbp >= 0 ? "+" : ""}£${Number(m.uplift_gbp).toLocaleString("en-GB")}` : m.phase}
              </span>
              <span className="w-14 text-right text-stone-400">%{m.occ_pct}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-4 mt-3 text-[11px] text-stone-500">
          <span><span className="inline-block w-3 h-3 rounded-sm bg-stone-400 mr-1" />baz dönem</span>
          <span><span className="inline-block w-3 h-3 rounded-sm bg-emerald-500 mr-1" />robot dönemi</span>
          <span><span className="inline-block w-0.5 h-3 bg-rose-500 mr-1 align-middle" />baz RevPAR çizgisi</span>
        </div>
        <p className="text-[11px] text-stone-400 mt-2">{data.note}</p>
      </div>
    </div>
  );
}
