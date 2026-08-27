import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Trophy } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;
const MEDAL = ["🥇", "🥈", "🥉"];

export default function ProfitBenchmarkPanel() {
  const [data, setData] = useState(null);
  const [months, setMonths] = useState(3);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/profit-benchmark?months=${months}`);
      setData(r.data);
    } catch { toast.error("Benchmark verisi yüklenemedi"); }
  }, [months]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="benchmark-loading">Kârlılık ligi hesaplanıyor…</p>;

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-4" data-testid="profit-benchmark-panel">
      <div className="bg-gradient-to-br from-yellow-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Trophy size={22} className="text-yellow-400" /> Kâr Benchmark — GOPPAR Ligi
            </h1>
            <p className="text-sm text-stone-300 mt-1">Otelleriniz brüt işletme kârı bazında kıyaslanıyor. Portföy GOPPAR: <b className="text-yellow-300">£{data.portfolio_goppar}</b> · pencere: {data.window_start} → bugün ({data.window_days} gün)</p>
          </div>
          <select value={months} onChange={(e) => setMonths(+e.target.value)} data-testid="benchmark-months-select"
            className="bg-stone-900 border border-stone-700 text-stone-200 text-sm rounded-lg px-3 py-2">
            <option value={1}>Son 1 ay</option><option value={3}>Son 3 ay</option><option value={6}>Son 6 ay</option><option value={12}>Son 12 ay</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 overflow-x-auto">
        <table className="w-full text-sm" data-testid="benchmark-table">
          <thead><tr className="text-left text-[11px] text-stone-400 border-b">
            <th className="p-3">#</th><th className="p-3">Otel</th><th className="p-3">GOPPAR</th><th className="p-3">TRevPAR</th><th className="p-3">RevPAR</th><th className="p-3">ADR</th><th className="p-3">Doluluk</th><th className="p-3">vs Portföy</th><th className="p-3">İçgörü</th>
          </tr></thead>
          <tbody>
            {data.properties.map((p, i) => (
              <tr key={p.property_id} className={`border-t border-stone-100 ${i === 0 ? "bg-yellow-50/50" : ""}`} data-testid={`benchmark-row-${p.property_id}`}>
                <td className="p-3 text-lg">{MEDAL[i] || p.rank}</td>
                <td className="p-3 font-bold">{p.name}<div className="text-[10px] text-stone-400">{p.rooms} oda · CPOR £{p.cpor}</div></td>
                <td className={`p-3 font-black text-base ${p.goppar >= data.portfolio_goppar ? "text-emerald-600" : "text-rose-500"}`}>£{p.goppar}</td>
                <td className="p-3">£{p.trevpar}</td>
                <td className="p-3">£{p.revpar}</td>
                <td className="p-3">£{p.adr}</td>
                <td className="p-3">%{p.occ_pct}</td>
                <td className={`p-3 font-semibold ${p.vs_portfolio_pct >= 0 ? "text-emerald-600" : "text-rose-500"}`}>{p.vs_portfolio_pct >= 0 ? "+" : ""}{p.vs_portfolio_pct}%</td>
                <td className="p-3 text-[11px] text-stone-500 max-w-[240px]">{p.insight}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-stone-400">{data.note}</p>
    </div>
  );
}
