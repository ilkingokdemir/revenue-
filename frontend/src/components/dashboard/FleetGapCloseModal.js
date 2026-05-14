/**
 * FleetGapCloseModal — Tek tıkta tüm filo için gap kapatma.
 * Dry-run preview tablosu + onay.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Zap, Building2, Loader2, CheckCircle2, AlertCircle, TrendingUp } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STRATEGIES = [
  { id: "half",  label: "Yarıyolda Buluş", desc: "Gap'in %50'sini kapat (önerilir)", tone: "emerald" },
  { id: "full",  label: "Tüm Pazara Yetiş", desc: "Doğrudan pazar ortalaması",        tone: "amber"   },
  { id: "value", label: "Value Pozisyonu", desc: "Pazar avg − %5",                    tone: "cyan"    },
  { id: "floor", label: "Güvenli Min",     desc: "Pazar minimumuna eşitle",            tone: "violet"  },
];

export default function FleetGapCloseModal({ onClose }) {
  const [strategy, setStrategy] = useState("half");
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
        const { data } = await axios.post(`${API}/revenue/market-robot/fleet-close-gap`, {
          strategy, days, dry_run: true, min_gap_pct: minGap,
        });
        if (!cancelled) setPreview(data);
      } catch {
        if (!cancelled) toast.error("Önizleme alınamadı");
      }
      if (!cancelled) setLoading(false);
    };
    run();
    return () => { cancelled = true; };
  }, [strategy, days, minGap]);

  const apply = async () => {
    if (!preview || preview.fleet_summary.total_days_applied === 0) return;
    setApplying(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/fleet-close-gap`, {
        strategy, days, dry_run: false, min_gap_pct: minGap,
      });
      const fs = data.fleet_summary;
      const batchId = data.batch_id;
      toast.success(
        `${fs.branches_with_apply} şube × ${fs.total_days_applied} gün uygulandı · +${fs.fleet_avg_uplift_pct}% uplift`,
        {
          duration: 12000,
          action: batchId ? {
            label: "↶ Geri Al",
            onClick: async () => {
              try {
                const r = await axios.post(`${API}/revenue/market-robot/gap-history/${batchId}/undo`);
                toast.success(`${r.data.deleted_overrides} fiyat geri alındı`);
              } catch {
                toast.error("Geri alma başarısız");
              }
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

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/85 backdrop-blur-sm flex items-center justify-center p-4" data-testid="fleet-gap-close-modal">
      <div className="bg-stone-900 border border-cyan-500/40 rounded-2xl max-w-3xl w-full max-h-[92vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-stone-800 bg-gradient-to-r from-cyan-950/30 to-emerald-950/30">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-cyan-500/30 to-emerald-500/30">
              <Building2 className="w-5 h-5 text-cyan-200" />
            </div>
            <div>
              <h2 className="text-sm font-black text-cyan-200">Tüm Filoda Gap Kapat</h2>
              <p className="text-[11px] text-stone-400 mt-0.5">Pazarın altında olan tüm şubelere tek tıkta strateji uygula</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400" data-testid="fleet-gap-x">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Strategy */}
          <div>
            <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Strateji</p>
            <div className="grid grid-cols-2 gap-2">
              {STRATEGIES.map(s => {
                const active = strategy === s.id;
                const toneClass = {
                  emerald: active ? "bg-emerald-500/20 border-emerald-500/60 text-emerald-200" : "border-stone-800 text-stone-300 hover:border-emerald-500/30",
                  amber:   active ? "bg-amber-500/20 border-amber-500/60 text-amber-200"     : "border-stone-800 text-stone-300 hover:border-amber-500/30",
                  cyan:    active ? "bg-cyan-500/20 border-cyan-500/60 text-cyan-200"        : "border-stone-800 text-stone-300 hover:border-cyan-500/30",
                  violet:  active ? "bg-violet-500/20 border-violet-500/60 text-violet-200"  : "border-stone-800 text-stone-300 hover:border-violet-500/30",
                }[s.tone];
                return (
                  <button key={s.id} onClick={() => setStrategy(s.id)}
                    className={`text-left p-3 rounded-xl border-2 transition ${toneClass}`}
                    data-testid={`fleet-strategy-${s.id}`}>
                    <div className="text-xs font-black">{s.label}</div>
                    <div className="text-[10px] mt-0.5 opacity-80">{s.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Süre</p>
              <div className="flex gap-2 flex-wrap">
                {[7, 14, 30, 60].map(n => (
                  <button key={n} onClick={() => setDays(n)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${days === n ? "bg-cyan-500/30 text-cyan-200 ring-1 ring-cyan-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
                    data-testid={`fleet-days-${n}`}>
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
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${minGap === n ? "bg-cyan-500/30 text-cyan-200 ring-1 ring-cyan-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
                    data-testid={`fleet-mingap-${n}`}>
                    ≥{n}%
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Preview */}
          {loading && !preview ? (
            <div className="bg-stone-950/40 rounded-xl p-6 text-center">
              <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
            </div>
          ) : fs ? (
            <div className="bg-stone-950/40 rounded-xl p-4 border border-stone-800 space-y-3">
              {fs.total_days_applied > 0 ? (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <FleetPreviewKpi label="Şube" value={`${fs.branches_with_apply}/${fs.total_branches}`} testid="fleet-preview-branches" />
                    <FleetPreviewKpi label="Gün Toplamı" value={fs.total_days_applied} testid="fleet-preview-days" />
                    <FleetPreviewKpi label="Ort. Uplift" value={`+${fs.fleet_avg_uplift_pct}%`} tone="emerald" testid="fleet-preview-uplift" />
                  </div>
                  <div className="max-h-64 overflow-y-auto rounded-lg border border-stone-800/50">
                    <table className="w-full text-[11px]">
                      <thead className="bg-stone-950/80 sticky top-0">
                        <tr className="text-[9px] text-stone-400 uppercase tracking-widest">
                          <th className="text-left py-2 pl-3 pr-1 font-bold">Şube</th>
                          <th className="text-right px-1 font-bold">Uygulanır</th>
                          <th className="text-right px-1 font-bold">Atlanan</th>
                          <th className="text-right pr-3 pl-1 font-bold">Uplift</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.branches.map(b => (
                          <tr key={b.property_id} className="border-b border-stone-800/30">
                            <td className="py-2 pl-3 pr-1 text-stone-200">{b.property_name}</td>
                            <td className="text-right px-1 font-bold text-emerald-300 tabular-nums">{b.applied}</td>
                            <td className="text-right px-1 text-stone-500 tabular-nums">{b.skipped}</td>
                            <td className="text-right pr-3 pl-1 text-emerald-400 tabular-nums">
                              {b.applied > 0 ? `+${b.avg_uplift_pct}%` : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="text-center py-6">
                  <AlertCircle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
                  <p className="text-xs text-stone-300">Filo'da kapatılacak gap yok</p>
                  <p className="text-[10px] text-stone-500 mt-1">Min gap %{minGap} altındaki tüm şubeler — eşiği düşürebilirsin</p>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-4 border-t border-stone-800 bg-stone-950/40">
          <p className="text-[10px] text-stone-500">
            Her şube için ayrı `rate_overrides` kaydı yazılır (source=fleet-gap-close).
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300" data-testid="fleet-gap-cancel">
              İptal
            </button>
            <button onClick={apply} disabled={!fs || fs.total_days_applied === 0 || applying}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500/30 to-cyan-500/30 hover:from-emerald-500/50 hover:to-cyan-500/50 border border-cyan-500/40 text-cyan-200 text-xs font-black transition disabled:opacity-40"
              data-testid="fleet-gap-apply">
              {applying
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <CheckCircle2 className="w-3.5 h-3.5" />}
              {fs && fs.total_days_applied > 0 ? `Tüm filoya uygula (${fs.branches_with_apply}×${fs.total_days_applied}g)` : "Uygulanacak yok"}
              {fs && fs.total_days_applied > 0 && <TrendingUp className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FleetPreviewKpi({ label, value, testid, tone }) {
  const toneClass = tone === "emerald" ? "text-emerald-300" : "text-stone-100";
  return (
    <div className="bg-stone-900/60 rounded-lg p-2.5 border border-stone-800/50" data-testid={testid}>
      <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className={`text-base font-black mt-0.5 ${toneClass}`}>{value}</p>
    </div>
  );
}
