/**
 * AiFleetOptimizeModal — AI-Adaptive fleet optimization.
 * GPT-4o-mini her şube için en uygun stratejiyi öner + uygula.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Sparkles, Loader2, CheckCircle2, AlertCircle, TrendingUp, Brain } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STRATEGY_BADGE = {
  full:  { label: "Pazara Yetiş", color: "bg-amber-500/20 text-amber-200 border-amber-500/40" },
  half:  { label: "Yarıyolda",     color: "bg-emerald-500/20 text-emerald-200 border-emerald-500/40" },
  value: { label: "Value",         color: "bg-cyan-500/20 text-cyan-200 border-cyan-500/40" },
  floor: { label: "Güvenli Min",  color: "bg-violet-500/20 text-violet-200 border-violet-500/40" },
};

export default function AiFleetOptimizeModal({ onClose }) {
  const [days, setDays] = useState(14);
  const [minGap, setMinGap] = useState(5);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const { data } = await axios.post(`${API}/revenue/market-robot/ai-fleet-optimize`, {
          days, dry_run: true, min_gap_pct: minGap,
        });
        if (!cancelled) setPreview(data);
      } catch (e) {
        if (!cancelled) toast.error(e?.response?.data?.detail || "AI önizleme başarısız");
      }
      if (!cancelled) setLoading(false);
    };
    run();
    return () => { cancelled = true; };
  }, [days, minGap]);

  const apply = async () => {
    if (!preview?.ok || preview.fleet_summary.total_days_applied === 0) return;
    setApplying(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/ai-fleet-optimize`, {
        days, dry_run: false, min_gap_pct: minGap,
      });
      const fs = data.fleet_summary;
      const batchId = data.batch_id;
      toast.success(
        `🧠 AI Optimize uygulandı · ${fs.branches_with_apply} şube × ${fs.total_days_applied} gün · +${fs.fleet_avg_uplift_pct}%`,
        {
          duration: 12000,
          action: batchId ? {
            label: "↶ Geri Al",
            onClick: async () => {
              try {
                const r = await axios.post(`${API}/revenue/market-robot/gap-history/${batchId}/undo`);
                toast.success(`${r.data.deleted_overrides} fiyat geri alındı`);
              } catch { toast.error("Geri alma başarısız"); }
            }
          } : undefined,
        }
      );
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Uygulama başarısız");
    }
    setApplying(false);
  };

  const fs = preview?.fleet_summary;
  const recs = preview?.ai_recommendations || [];
  const branchesByPid = Object.fromEntries((preview?.branches || []).map(b => [b.property_id, b]));

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/85 backdrop-blur-sm flex items-center justify-center p-4" data-testid="ai-optimize-modal">
      <div className="bg-stone-900 border border-fuchsia-500/40 rounded-2xl max-w-3xl w-full max-h-[92vh] overflow-y-auto shadow-2xl">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-stone-800 bg-gradient-to-r from-purple-950/30 to-fuchsia-950/30">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-purple-500/30 to-fuchsia-500/30">
              <Brain className="w-5 h-5 text-fuchsia-200" />
            </div>
            <div>
              <h2 className="text-sm font-black text-fuchsia-200">AI Fleet Optimize</h2>
              <p className="text-[11px] text-stone-400 mt-0.5">GPT-4o-mini her şube için en uygun stratejiyi seçer ve Türkçe gerekçe verir</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400" data-testid="ai-modal-x">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Süre</p>
              <div className="flex gap-2 flex-wrap">
                {[7, 14, 30, 60].map(n => (
                  <button key={n} onClick={() => setDays(n)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${days === n ? "bg-fuchsia-500/30 text-fuchsia-200 ring-1 ring-fuchsia-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
                    data-testid={`ai-days-${n}`}>
                    {n} gün
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Min Gap %</p>
              <div className="flex gap-2 flex-wrap">
                {[2, 5, 10, 15].map(n => (
                  <button key={n} onClick={() => setMinGap(n)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${minGap === n ? "bg-fuchsia-500/30 text-fuchsia-200 ring-1 ring-fuchsia-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
                    data-testid={`ai-mingap-${n}`}>
                    ≥{n}%
                  </button>
                ))}
              </div>
            </div>
          </div>

          {loading && !preview ? (
            <div className="bg-stone-950/40 rounded-xl p-8 text-center" data-testid="ai-loading">
              <Loader2 className="w-6 h-6 text-fuchsia-400 animate-spin mx-auto mb-3" />
              <p className="text-xs text-stone-400">GPT-4o-mini her şubeyi analiz ediyor...</p>
            </div>
          ) : preview && !preview.ok ? (
            <div className="bg-stone-950/40 rounded-xl p-6 border border-amber-500/40 text-center">
              <AlertCircle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
              <p className="text-xs text-stone-300">{preview.error}</p>
            </div>
          ) : fs && fs.total_days_applied > 0 ? (
            <>
              <div className="grid grid-cols-3 gap-2">
                <AiKpi label="Şube" value={`${fs.branches_with_apply}/${fs.total_branches}`} testid="ai-kpi-branches" />
                <AiKpi label="Gün" value={fs.total_days_applied} testid="ai-kpi-days" />
                <AiKpi label="Ort. Uplift" value={`+${fs.fleet_avg_uplift_pct}%`} tone="emerald" testid="ai-kpi-uplift" />
              </div>
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {recs.map(r => {
                  const badge = STRATEGY_BADGE[r.strategy] || { label: r.strategy, color: "bg-stone-700 text-stone-300" };
                  const branch = branchesByPid[r.property_id];
                  const applied = branch?.applied || 0;
                  const uplift = branch?.avg_uplift_pct || 0;
                  return (
                    <div key={r.property_id} className="bg-stone-950/40 rounded-lg p-3 border border-stone-800/60" data-testid={`ai-rec-${r.property_id}`}>
                      <div className="flex items-start justify-between gap-3 mb-1">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-black text-stone-100">{branch?.property_name || r.property_id}</span>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${badge.color}`}>
                              {badge.label}
                            </span>
                          </div>
                          <p className="text-[10px] text-stone-400 mt-1 leading-relaxed">
                            <Sparkles className="w-2.5 h-2.5 inline mr-1 text-fuchsia-400" />
                            {r.reason}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-black text-emerald-300">+{uplift}%</p>
                          <p className="text-[9px] text-stone-500">{applied}g</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="bg-stone-950/40 rounded-xl p-6 text-center border border-stone-800">
              <AlertCircle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
              <p className="text-xs text-stone-300">AI uygulayacak bir gap bulamadı</p>
              <p className="text-[10px] text-stone-500 mt-1">Min gap eşiğini düşürmeyi dene</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 p-4 border-t border-stone-800 bg-stone-950/40">
          <p className="text-[10px] text-stone-500">
            AI önerileri ve uplift'ler `fleet_gap_history`'e kaydedilir · geri alınabilir
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300" data-testid="ai-cancel">
              İptal
            </button>
            <button onClick={apply} disabled={!fs || fs.total_days_applied === 0 || applying}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500/30 to-fuchsia-500/30 hover:from-purple-500/50 hover:to-fuchsia-500/50 border border-fuchsia-500/40 text-fuchsia-100 text-xs font-black transition disabled:opacity-40"
              data-testid="ai-apply">
              {applying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              {fs && fs.total_days_applied > 0 ? `AI önerisini uygula (${fs.branches_with_apply}×${fs.total_days_applied}g)` : "Uygulanacak yok"}
              {fs && fs.total_days_applied > 0 && <TrendingUp className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AiKpi({ label, value, testid, tone }) {
  const toneClass = tone === "emerald" ? "text-emerald-300" : "text-stone-100";
  return (
    <div className="bg-stone-900/60 rounded-lg p-2.5 border border-stone-800/50" data-testid={testid}>
      <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className={`text-base font-black mt-0.5 ${toneClass}`}>{value}</p>
    </div>
  );
}
