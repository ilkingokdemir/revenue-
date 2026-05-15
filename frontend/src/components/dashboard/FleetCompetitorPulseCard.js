/**
 * FleetCompetitorPulseCard — Cross-branch pazar pozisyonu özeti.
 * Owner/CEO bakış açısı: tüm filomun pazara karşı durumu.
 * KPI strip + per-branch bar chart (vs_market_pct) + tablo.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ReferenceLine, CartesianGrid } from "recharts";
import { TrendingUp, TrendingDown, RefreshCw, Loader2, Building2, ArrowRight, Zap, Undo2, Sparkles } from "lucide-react";
import useLivePolling from "../../hooks/useLivePolling";
import GapCloseModal from "./GapCloseModal";
import FleetGapCloseModal from "./FleetGapCloseModal";
import AiFleetOptimizeModal from "./AiFleetOptimizeModal";
import GapPerformanceMiniWidget from "./GapPerformanceMiniWidget";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function FleetCompetitorPulseCard({ onSelectProperty }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [gapTarget, setGapTarget] = useState(null);  // {property_id, property_name}
  const [fleetGapOpen, setFleetGapOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [lastBatch, setLastBatch] = useState(null);  // {batch_id, applied_at, branches, days, undone}
  const [fleetResetting, setFleetResetting] = useState(false);

  const runFleetReset = async () => {
    if (!window.confirm(
      "Tüm filo için: her property'nin eski rakiplerini sileceğim, auto-geocode edeceğim, " +
      "gerçek komşuları bulup top 5'i otomatik rakip olarak ekleyeceğim. " +
      "48 property için 2-4 dakika sürebilir. Devam?"
    )) return;
    setFleetResetting(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/fleet-reset-neighbors`,
        { radius_km: 2.0, max_results: 15, auto_add: true, auto_add_top: 5 });
      const okN = data.ok_count || 0;
      const tot = data.total_properties || 0;
      const added = data.auto_added || 0;
      const failed = (data.results || []).filter(r => r.status !== "ok").length;
      if (okN === tot) {
        toast.success(`Filo sıfırlandı: ${okN}/${tot} property · ${added} rakip auto-eklendi`);
      } else {
        toast.warning(`${okN}/${tot} başarılı (${added} auto-eklendi), ${failed} hata.`);
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Filo sıfırlama başarısız");
    }
    setFleetResetting(false);
  };

  const loadLastBatch = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/gap-history?limit=1`);
      const latest = data.items?.[0];
      setLastBatch(latest && !latest.undone ? latest : null);
    } catch { /* noop */ }
  }, []);

  useEffect(() => { loadLastBatch(); }, [loadLastBatch]);

  const undoLastBatch = async () => {
    if (!lastBatch) return;
    try {
      const r = await axios.post(`${API}/revenue/market-robot/gap-history/${lastBatch.batch_id}/undo`);
      toast.success(`${r.data.deleted_overrides} fiyat geri alındı`);
      setLastBatch(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Geri alma başarısız");
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/fleet-pulse?days=${days}`);
      setData(data);
    } catch { /* noop */ }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);
  useLivePolling(load, { intervalMs: 90000 });

  if (!data) {
    return (
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-6 text-center" data-testid="fleet-pulse-loading">
        <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
      </div>
    );
  }

  const fs = data.fleet_summary;
  const hasData = fs.live_branches > 0;

  // Chart data — sıralı vs_market_pct'e göre
  const chartData = [...data.branches]
    .filter(b => b.vs_market_pct !== null)
    .sort((a, b) => a.vs_market_pct - b.vs_market_pct)
    .map(b => ({
      name: b.property_name.length > 16 ? b.property_name.slice(0, 14) + "…" : b.property_name,
      full_name: b.property_name,
      property_id: b.property_id,
      vs_pct: b.vs_market_pct,
      market: b.market_avg,
      ours: b.our_avg,
    }));

  return (
    <div className="bg-stone-900/60 border border-cyan-500/30 rounded-2xl p-5 space-y-4" data-testid="fleet-pulse-card">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-cyan-500/20">
            <Building2 className="w-5 h-5 text-cyan-300" />
          </div>
          <div>
            <h3 className="text-sm font-black text-cyan-300">Filo Pazar Pulse · {days} gün</h3>
            <p className="text-[11px] text-stone-400 mt-0.5">
              {fs.live_branches}/{fs.total_branches} şube canlı veri ·
              {" "}{fs.above_market} üst · {fs.aligned} hizalı · {fs.below_market} alt
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[14, 30, 60].map(n => (
            <button key={n} onClick={() => setDays(n)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition ${days === n ? "bg-cyan-500/30 text-cyan-200 ring-1 ring-cyan-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
              data-testid={`fleet-days-${n}`}>
              {n}g
            </button>
          ))}
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300 disabled:opacity-50"
            data-testid="fleet-refresh">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          </button>
          <button onClick={runFleetReset} disabled={fleetResetting}
            title="Tüm filo için: eski rakipleri sil + auto-geocode + gerçek komşuları yeniden bul"
            data-testid="fleet-reset-neighbors-btn"
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold border transition ${fleetResetting ? "bg-orange-500/15 border-orange-500/40 text-orange-300 cursor-wait" : "bg-stone-800 border-orange-500/30 text-orange-300 hover:bg-orange-500/15"}`}>
            {fleetResetting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {fleetResetting ? "Sıfırlanıyor..." : "Filo Komşuları Sıfırla"}
          </button>
        </div>
      </div>

      {/* Fleet KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <FleetKpi label="Filo Pazar Avg" value={fs.fleet_market_avg} prefix="£" testid="fleet-kpi-market" />
        <FleetKpi label="Filo Bizim Avg" value={fs.fleet_our_avg} prefix="£" testid="fleet-kpi-our" />
        <div className="bg-stone-950/40 rounded-xl p-3 border border-stone-800" data-testid="fleet-kpi-vs">
          <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">Filo Pazara Karşı</p>
          {fs.fleet_vs_pct === null
            ? <p className="text-lg font-black text-stone-400 mt-1">—</p>
            : (
              <div className="flex items-center gap-1.5 mt-1">
                {fs.fleet_vs_pct > 0 ? <TrendingUp className="w-4 h-4 text-amber-400" />
                  : <TrendingDown className="w-4 h-4 text-emerald-400" />}
                <span className={`text-lg font-black ${fs.fleet_vs_pct > 0 ? "text-amber-300" : "text-emerald-300"}`}>
                  {fs.fleet_vs_pct > 0 ? "+" : ""}{fs.fleet_vs_pct}%
                </span>
              </div>
            )}
        </div>
        <div className="bg-stone-950/40 rounded-xl p-3 border border-stone-800" data-testid="fleet-kpi-distribution">
          <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">Dağılım</p>
          <div className="flex items-baseline gap-2 mt-1 text-sm font-black">
            <span className="text-amber-300">{fs.above_market}↑</span>
            <span className="text-stone-400">{fs.aligned}=</span>
            <span className="text-emerald-300">{fs.below_market}↓</span>
          </div>
          <p className="text-[10px] text-stone-500 mt-0.5">üst · hizalı · alt</p>
        </div>
      </div>

      {/* Tüm filoda gap kapat — sadece below_market > 0 ise göster */}
      {fs.below_market > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <button onClick={() => setFleetGapOpen(true)}
            className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-emerald-500/20 via-cyan-500/20 to-emerald-500/20 hover:from-emerald-500/35 hover:via-cyan-500/35 hover:to-emerald-500/35 border border-cyan-500/40 text-cyan-100 text-sm font-black transition group"
            data-testid="fleet-gap-cta">
            <Zap className="w-5 h-5 group-hover:scale-110 transition" />
            <span>Manuel Gap Kapat</span>
            <span className="text-stone-400 text-xs">·</span>
            <span className="text-emerald-200">{fs.below_market} şube</span>
          </button>
          <button onClick={() => setAiOpen(true)}
            className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-purple-500/20 via-fuchsia-500/20 to-purple-500/20 hover:from-purple-500/35 hover:via-fuchsia-500/35 hover:to-purple-500/35 border border-fuchsia-500/40 text-fuchsia-100 text-sm font-black transition group"
            data-testid="ai-optimize-cta">
            <Sparkles className="w-5 h-5 group-hover:scale-110 transition" />
            <span>AI Optimize</span>
            <span className="text-stone-400 text-xs">·</span>
            <span className="text-fuchsia-200">her şubeye özel strateji</span>
          </button>
        </div>
      )}

      {/* Son işlem → Geri al */}
      {lastBatch && (
        <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-stone-950/60 border border-stone-800" data-testid="fleet-last-batch">
          <div className="flex items-center gap-2 text-[11px]">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-stone-400">Son işlem:</span>
            <span className="text-stone-200 font-bold">
              {lastBatch.strategy} · {lastBatch.branches_with_apply} şube × {lastBatch.total_days_applied} gün
            </span>
            <span className="text-emerald-400">+{lastBatch.fleet_avg_uplift_pct}%</span>
            <span className="text-stone-500 text-[10px]">
              {new Date(lastBatch.applied_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
          <button onClick={undoLastBatch}
            className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-500/15 hover:bg-amber-500/30 text-amber-300 text-[10px] font-bold transition"
            data-testid="fleet-undo-last">
            <Undo2 className="w-3 h-3" /> Geri Al
          </button>
        </div>
      )}

      {/* Performans tracker — son N batch'in gerçek etkisi */}
      <GapPerformanceMiniWidget />

      {/* Per-branch bar chart */}
      {hasData ? (
        <div className="bg-stone-950/30 rounded-xl p-3 border border-stone-800/50">
          <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Şube bazında pazara karşı %</p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 40 }}>
              <CartesianGrid stroke="#3a3030" strokeDasharray="3 6" opacity={0.4} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#a8a29e" }} angle={-25} textAnchor="end" />
              <YAxis tick={{ fontSize: 10, fill: "#a8a29e" }} tickFormatter={v => `${v}%`} />
              <Tooltip content={<FleetTooltip />} />
              <ReferenceLine y={0} stroke="#666" strokeDasharray="2 4" />
              <Bar dataKey="vs_pct" name="Pazara karşı %" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.vs_pct > 5 ? "#f59e0b" : entry.vs_pct < -5 ? "#10b981" : "#a8a29e"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="bg-stone-950/40 rounded-xl p-6 border border-dashed border-stone-700 text-center" data-testid="fleet-pulse-empty">
          <p className="text-sm text-stone-300">Henüz filo verisi yok</p>
          <p className="text-[11px] text-stone-500 mt-1">
            Her şube için Market Robot'tan rakip eklenmiş ve scan edilmiş olmalı.
          </p>
        </div>
      )}

      {/* Branch table */}
      {hasData && (
        <div className="overflow-x-auto rounded-xl border border-stone-800">
          <table className="w-full text-xs">
            <thead className="bg-stone-950/80">
              <tr className="border-b-2 border-cyan-500/30 text-[10px] text-stone-300 uppercase tracking-widest">
                <th className="text-left py-2.5 pl-3 pr-2 font-bold">Şube</th>
                <th className="text-right px-2 font-bold">Pazar Avg</th>
                <th className="text-right px-2 font-bold">Bizim</th>
                <th className="text-right px-2 font-bold">vs Pazar</th>
                <th className="text-right pr-3 pl-2 font-bold">Detay</th>
              </tr>
            </thead>
            <tbody>
              {data.branches.map(b => {
                const pct = b.vs_market_pct;
                const tone = pct === null ? "text-stone-500"
                  : pct > 5 ? "text-amber-300"
                  : pct < -5 ? "text-emerald-300"
                  : "text-stone-200";
                return (
                  <tr key={b.property_id} className="border-b border-stone-800/40 hover:bg-cyan-500/5"
                      data-testid={`fleet-row-${b.property_id}`}>
                    <td className="py-2.5 pl-3 pr-2 font-semibold text-stone-100">{b.property_name}</td>
                    <td className="text-right px-2 tabular-nums text-stone-300">
                      {b.market_avg ? `£${b.market_avg}` : "—"}
                    </td>
                    <td className="text-right px-2 tabular-nums text-stone-300">£{b.our_avg}</td>
                    <td className={`text-right px-2 tabular-nums font-bold ${tone}`}>
                      {pct === null ? "—" : `${pct > 0 ? "+" : ""}${pct}%`}
                    </td>
                    <td className="text-right pr-3 pl-2">
                      <div className="inline-flex items-center gap-1">
                        {pct !== null && pct < -2 && (
                          <button onClick={() => setGapTarget({ property_id: b.property_id, property_name: b.property_name })}
                            className="inline-flex items-center gap-0.5 px-2 py-1 rounded bg-emerald-500/15 hover:bg-emerald-500/30 text-emerald-300 text-[10px] font-black transition"
                            data-testid={`fleet-gap-${b.property_id}`}
                            title="Pazar gap'ini kapat">
                            <Zap className="w-3 h-3" /> Gap
                          </button>
                        )}
                        {onSelectProperty && (
                          <button onClick={() => onSelectProperty(b.property_id)}
                            className="inline-flex items-center gap-0.5 px-2 py-1 rounded bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 text-[10px] font-bold transition"
                            data-testid={`fleet-detail-${b.property_id}`}>
                            Aç <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {gapTarget && (
        <GapCloseModal
          propertyId={gapTarget.property_id}
          propertyName={gapTarget.property_name}
          onClose={() => { setGapTarget(null); load(); }}
        />
      )}
      {fleetGapOpen && (
        <FleetGapCloseModal onClose={() => { setFleetGapOpen(false); load(); loadLastBatch(); }} />
      )}
      {aiOpen && (
        <AiFleetOptimizeModal onClose={() => { setAiOpen(false); load(); loadLastBatch(); }} />
      )}
    </div>
  );
}

function FleetKpi({ label, value, prefix = "", testid }) {
  return (
    <div className="bg-stone-950/40 rounded-xl p-3 border border-stone-800" data-testid={testid}>
      <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className="text-lg font-black mt-1 text-stone-100">
        {value === null || value === undefined ? "—" : `${prefix}${value}`}
      </p>
    </div>
  );
}

function FleetTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <div className="bg-stone-950/95 border border-cyan-500/40 rounded-lg p-2.5 text-[11px] shadow-xl">
      <div className="text-cyan-300 font-bold mb-1">{row.full_name}</div>
      <div className="text-stone-300">Pazar avg: <strong className="text-stone-100">£{row.market}</strong></div>
      <div className="text-stone-300">Bizim: <strong className="text-emerald-200">£{row.ours}</strong></div>
      <div className={`mt-1 font-bold ${row.vs_pct > 0 ? "text-amber-300" : "text-emerald-300"}`}>
        vs Pazar: {row.vs_pct > 0 ? "+" : ""}{row.vs_pct}%
      </div>
    </div>
  );
}
