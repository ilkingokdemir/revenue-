import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const OPTS = [
  ["balanced", "⚖️ Dengeli"], ["high_season", "🔥 Yoğun Sezon"],
  ["low_occupancy", "🌙 Düşük Doluluk"], ["group_heavy", "👥 Grup Ağırlıklı"],
];
const label = (k) => (OPTS.find((o) => o[0] === k) || ["", k])[1];
const fmt = (v, c) => `${c === "CHF" ? "CHF" : c === "GBP" ? "£" : c === "EUR" ? "€" : c} ${Math.round(v).toLocaleString("tr-TR")}`;

export const ScenarioComparePanel = ({ propertyId, onClose }) => {
  const [a, setA] = useState("high_season");
  const [b, setB] = useState("low_occupancy");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/demo-seeder/compare/${propertyId}?a=${a}&b=${b}`);
      setData(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "Karşılaştırılamadı"); }
    finally { setBusy(false); }
  };

  const maxRev = data ? Math.max(1, ...data.a.daily_rev, ...data.b.daily_rev) : 1;

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/60 p-4" data-testid="scenario-compare-modal" onClick={onClose}>
      <div className="w-full max-w-3xl bg-white rounded-2xl shadow-2xl p-5 max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="flex-1 text-base font-black text-stone-900">⚖️ Senaryo Karşılaştırma — 30 günlük simülasyon</h2>
          <button onClick={onClose} data-testid="scenario-compare-close" className="text-stone-400 hover:text-stone-700 text-lg font-bold">✕</button>
        </div>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <select value={a} onChange={(e) => setA(e.target.value)} data-testid="scenario-a-select"
            className="border border-indigo-300 bg-indigo-50 rounded-lg px-2.5 py-2 text-xs font-bold text-indigo-800">
            {OPTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <span className="text-xs font-black text-stone-400">vs</span>
          <select value={b} onChange={(e) => setB(e.target.value)} data-testid="scenario-b-select"
            className="border border-amber-300 bg-amber-50 rounded-lg px-2.5 py-2 text-xs font-bold text-amber-800">
            {OPTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <button onClick={run} disabled={busy || a === b} data-testid="scenario-compare-run"
            className="px-4 py-2 rounded-lg bg-stone-900 text-white text-xs font-black disabled:opacity-40">
            {busy ? "Hesaplanıyor..." : "Karşılaştır →"}
          </button>
          {a === b && <span className="text-[10px] text-rose-500 font-bold">Farklı iki senaryo seçin</span>}
          <span className="text-[10px] text-stone-400">Veritabanına yazılmaz — anlık simülasyon</span>
        </div>

        {data && (
          <div className="space-y-4" data-testid="scenario-compare-result">
            <div className="grid grid-cols-3 gap-2">
              {[["Toplam Gelir (30g)", fmt(data.a.total_rev, data.currency), fmt(data.b.total_rev, data.currency),
                 data.a.total_rev - data.b.total_rev, (v) => fmt(Math.abs(v), data.currency)],
                ["Ort. Doluluk", `%${data.a.avg_occ_pct}`, `%${data.b.avg_occ_pct}`,
                 data.a.avg_occ_pct - data.b.avg_occ_pct, (v) => `%${Math.abs(v).toFixed(1)}`],
                ["ADR", fmt(data.a.adr, data.currency), fmt(data.b.adr, data.currency),
                 data.a.adr - data.b.adr, (v) => fmt(Math.abs(v), data.currency)]].map(([l, va, vb, delta, df]) => (
                <div key={l} className="bg-stone-50 border border-stone-200 rounded-xl p-3">
                  <div className="text-[10px] font-bold text-stone-500 uppercase mb-1">{l}</div>
                  <div className="text-xs"><span className="font-black text-indigo-700">{va}</span>
                    <span className="text-stone-400 mx-1">vs</span>
                    <span className="font-black text-amber-700">{vb}</span></div>
                  <div className={`text-[10px] font-black mt-0.5 ${delta >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                    {delta >= 0 ? "▲" : "▼"} {df(delta)} fark
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">Günlük Gelir — {label(a)} vs {label(b)}</div>
              <div className="flex items-end gap-[2px] h-32">
                {data.days.map((d, i) => (
                  <div key={d} className="flex-1 h-full flex items-end gap-[1px]" title={`${d}: ${fmt(data.a.daily_rev[i], data.currency)} vs ${fmt(data.b.daily_rev[i], data.currency)}`}>
                    <div className="flex-1 bg-indigo-500 rounded-t-sm" style={{ height: `${(data.a.daily_rev[i] / maxRev) * 100}%`, minHeight: data.a.daily_rev[i] ? 2 : 0 }} />
                    <div className="flex-1 bg-amber-400 rounded-t-sm" style={{ height: `${(data.b.daily_rev[i] / maxRev) * 100}%`, minHeight: data.b.daily_rev[i] ? 2 : 0 }} />
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-[9px] text-stone-400 mt-1">
                <span>{data.days[0]}</span><span>{data.days[14]}</span><span>{data.days[29]}</span>
              </div>
            </div>

            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">Günlük Doluluk %</div>
              <svg viewBox="0 0 300 60" className="w-full h-20" preserveAspectRatio="none">
                <polyline fill="none" stroke="#6366f1" strokeWidth="1.6"
                  points={data.a.daily_occ_pct.map((v, i) => `${(i / 29) * 300},${60 - (v / 100) * 58}`).join(" ")} />
                <polyline fill="none" stroke="#f59e0b" strokeWidth="1.6"
                  points={data.b.daily_occ_pct.map((v, i) => `${(i / 29) * 300},${60 - (v / 100) * 58}`).join(" ")} />
              </svg>
              <div className="flex gap-3 text-[10px] text-stone-500">
                <span><span className="inline-block w-2 h-2 bg-indigo-500 rounded-sm mr-1" />{label(a)}</span>
                <span><span className="inline-block w-2 h-2 bg-amber-400 rounded-sm mr-1" />{label(b)}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScenarioComparePanel;
