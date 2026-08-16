import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Trophy, Medal, TrendUp, TrendDown, Lightning } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/chain`;

const RANK_STYLE = {
  1: "bg-amber-400 text-stone-900",
  2: "bg-stone-300 text-stone-800",
  3: "bg-orange-300 text-stone-900",
};
const METRIC_SHORT = { occupancy: "Doluluk", revpar: "RevPAR", review: "Puan", quality: "Kalite", automation: "Otomasyon" };

export default function ChainBenchmarkPanel({ onNavigate }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [consent, setConsent] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/benchmark?days=${days}`);
      setData(r.data);
    } catch { toast.error("Benchmark yüklenemedi"); }
  }, [days]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    axios.get(`${API}/benchmark/consent`).then((r) => setConsent(r.data)).catch(() => {});
  }, []);

  const toggleConsent = async (pid, share) => {
    try {
      await axios.put(`${API}/benchmark/consent/${pid}`, { share_data: share });
      setConsent((c) => ({ ...c, properties: c.properties.map((p) => p.id === pid ? { ...p, share_data: share } : p) }));
      toast.success(share ? "Tesis havuz kıyasına dahil edildi" : "Tesis havuz kıyasından ÇIKARILDI — verisi paylaşılmaz");
      load();
    } catch { toast.error("İzin güncellenemedi"); }
  };

  if (!data) return <div className="p-8 text-center text-stone-400">Tesisler kıyaslanıyor…</div>;
  const rows = data.properties || [];
  const c = data.chain || {};

  return (
    <div className="p-5 max-w-[1300px] mx-auto space-y-4" data-testid="chain-benchmark-panel">
      <div className="bg-gradient-to-br from-stone-900 via-amber-950 to-stone-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-amber-300">
              <Trophy size={14} weight="fill" /> Chain Benchmark
            </div>
            <h1 className="text-2xl font-bold mt-1">Zincir Benchmark Panosu</h1>
            <p className="text-sm text-stone-300 mt-1">Tesisleriniz doluluk, RevPAR, misafir puanı, rezervasyon kalitesi ve otomasyon aktivitesine göre kompozit skorla sıralanır.</p>
          </div>
          <select value={days} onChange={e => setDays(Number(e.target.value))} data-testid="benchmark-days"
            className="px-3 py-2 text-xs rounded-lg bg-white/10 border border-white/20 text-white">
            <option value={7} className="text-stone-900">Son 7 gün</option>
            <option value={30} className="text-stone-900">Son 30 gün</option>
            <option value={90} className="text-stone-900">Son 90 gün</option>
          </select>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          <Stat label="Tesis" value={c.properties || 0} testid="cb-stat-props" />
          <Stat label="Zincir doluluk" value={`%${c.occupancy ?? 0}`} testid="cb-stat-occ" />
          <Stat label="Zincir ADR" value={`£${(c.adr ?? 0).toLocaleString()}`} testid="cb-stat-adr" />
          <Stat label="Zincir RevPAR" value={`£${(c.revpar ?? 0).toLocaleString()}`} testid="cb-stat-revpar" />
          <Stat label="Toplam gelir" value={`£${(c.total_revenue ?? 0).toLocaleString()}`} testid="cb-stat-rev" />
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="benchmark-table">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2.5">#</th>
            <th className="text-left px-2 py-2.5">Tesis</th>
            <th className="text-center px-2 py-2.5">Tesis Skoru</th>
            <th className="text-right px-2 py-2.5">Doluluk</th>
            <th className="text-right px-2 py-2.5">ADR</th>
            <th className="text-right px-2 py-2.5">RevPAR</th>
            <th className="text-right px-2 py-2.5">Puan ★</th>
            <th className="text-right px-2 py-2.5">Kalite</th>
            <th className="text-right px-2 py-2.5">Otomasyon</th>
            <th className="text-left px-4 py-2.5">Rozetler</th>
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.property_id} className="border-b border-stone-50 hover:bg-stone-50/60" data-testid={`benchmark-row-${r.property_id}`}>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-black ${RANK_STYLE[r.rank] || "bg-stone-100 text-stone-500"}`}>
                    {r.rank <= 3 ? <Medal size={14} weight="fill" /> : r.rank}
                  </span>
                </td>
                <td className="px-2 py-3">
                  <div className="font-semibold text-stone-800">{r.name}</div>
                  <div className="text-[10px] text-stone-400">{r.nights_sold} gece · £{r.total_revenue.toLocaleString()} gelir</div>
                </td>
                <td className="px-2 py-3">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-16 h-2 bg-stone-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${r.score >= 60 ? "bg-emerald-500" : r.score >= 40 ? "bg-amber-400" : "bg-rose-400"}`}
                        style={{ width: `${r.score}%` }} />
                    </div>
                    <span className="text-sm font-black text-stone-800">{r.score}</span>
                  </div>
                </td>
                <td className="px-2 py-3 text-right font-mono text-xs">%{r.occupancy}</td>
                <td className="px-2 py-3 text-right font-mono text-xs">£{r.adr.toLocaleString()}</td>
                <td className="px-2 py-3 text-right font-mono text-xs font-bold">£{r.revpar.toLocaleString()}</td>
                <td className="px-2 py-3 text-right font-mono text-xs">{r.review ? `${r.review} (${r.review_count})` : "—"}</td>
                <td className="px-2 py-3 text-right font-mono text-xs">%{r.quality}</td>
                <td className="px-2 py-3 text-right font-mono text-xs">{r.automation}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {r.badges.best.map(m => (
                      <span key={m} className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-bold">
                        <TrendUp size={9} /> En iyi {METRIC_SHORT[m]}
                      </span>
                    ))}
                    {r.badges.worst.map(m => (
                      <span key={m} className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 bg-rose-50 text-rose-600 rounded-full font-bold">
                        <TrendDown size={9} /> En zayıf {METRIC_SHORT[m]}
                      </span>
                    ))}
                  </div>
                  {(r.actions || []).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {r.actions.map(a => (
                        <button key={a.metric} title={a.text} onClick={() => onNavigate && onNavigate(a.view)}
                          data-testid={`benchmark-action-${r.property_id}-${a.metric}`}
                          className="inline-flex items-center gap-1 text-[9px] px-2 py-1 bg-stone-900 text-white rounded-full font-semibold hover:bg-stone-700 transition-colors">
                          <Lightning size={9} weight="fill" className="text-amber-400" /> {a.label} →
                        </button>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-10 text-center text-stone-400 text-sm">Tesis bulunamadı.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-stone-400">Tesis Skoru = doluluk %30 + RevPAR %30 + misafir puanı %20 + rezervasyon kalitesi %10 + otomasyon aktivitesi %10 (zincir içi göreli normalize, {data.start} → {data.end}).</p>

      {consent && (
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="pool-consent-section">
          <div className="text-sm font-bold text-stone-800 mb-1">🔒 Havuz Veri İzinleri</div>
          <p className="text-[11px] text-stone-500 mb-3">{consent.note}</p>
          <div className="flex flex-wrap gap-2">
            {consent.properties.map((p) => (
              <label key={p.id} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[12px] font-bold cursor-pointer ${p.share_data ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-600"}`} data-testid={`pool-consent-${p.id}`}>
                <input type="checkbox" checked={p.share_data} onChange={(e) => toggleConsent(p.id, e.target.checked)} data-testid={`pool-consent-toggle-${p.id}`} />
                {p.name}
              </label>
            ))}
          </div>
        </div>
      )}
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
