/**
 * GapCloseModal — Pazara karşı fiyat gap'ini kapatma asistanı.
 * 4 strateji (full/half/floor/value) + dry-run preview + onay.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Zap, ArrowUpRight, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STRATEGIES = [
  { id: "half",  label: "Yarıyolda Buluş", desc: "Gap'in %50'sini kapat (önerilir)", tone: "emerald" },
  { id: "full",  label: "Tüm Pazara Yetiş", desc: "Doğrudan pazar ortalaması",        tone: "amber"   },
  { id: "value", label: "Value Pozisyonu", desc: "Pazar avg − %5 (hafif iskonto)",    tone: "cyan"    },
  { id: "floor", label: "Güvenli Min",     desc: "Pazar minimumuna eşitle",            tone: "violet"  },
];

export default function GapCloseModal({ propertyId, propertyName, onClose }) {
  const [strategy, setStrategy] = useState("half");
  const [days, setDays] = useState(14);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  // Auto-dry-run when strategy/days change
  useEffect(() => {
    let cancelled = false;
    const fetchPreview = async () => {
      setLoading(true);
      try {
        const { data } = await axios.post(
          `${API}/revenue/market-robot/${propertyId}/close-gap`,
          { strategy, days, dry_run: true }
        );
        if (!cancelled) setPreview(data);
      } catch (e) {
        if (!cancelled) toast.error("Önizleme alınamadı");
      }
      if (!cancelled) setLoading(false);
    };
    fetchPreview();
    return () => { cancelled = true; };
  }, [propertyId, strategy, days]);

  const apply = async () => {
    if (!preview || preview.applied === 0) return;
    setApplying(true);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/close-gap`,
        { strategy, days, dry_run: false }
      );
      toast.success(`${data.applied} gün için yeni fiyat uygulandı · ort. +${data.avg_uplift_pct}% uplift`);
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Uygulama başarısız");
    }
    setApplying(false);
  };

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/85 backdrop-blur-sm flex items-center justify-center p-4" data-testid="gap-close-modal">
      <div className="bg-stone-900 border border-emerald-500/40 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-stone-800">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-emerald-500/20">
              <Zap className="w-5 h-5 text-emerald-300" />
            </div>
            <div>
              <h2 className="text-sm font-black text-emerald-300">Pazar Gap'ini Kapat</h2>
              <p className="text-[11px] text-stone-400 mt-0.5">{propertyName || propertyId}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400" data-testid="gap-close-x">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Strategy picker */}
        <div className="p-5 space-y-4">
          <div>
            <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Strateji</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
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
                    data-testid={`strategy-${s.id}`}>
                    <div className="text-xs font-black">{s.label}</div>
                    <div className="text-[10px] mt-0.5 opacity-80">{s.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Days */}
          <div>
            <p className="text-[10px] text-stone-500 mb-2 font-bold uppercase tracking-widest">Süre</p>
            <div className="flex gap-2">
              {[7, 14, 30, 60].map(n => (
                <button key={n} onClick={() => setDays(n)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${days === n ? "bg-emerald-500/30 text-emerald-200 ring-1 ring-emerald-500/50" : "bg-stone-800 text-stone-400 hover:text-stone-200"}`}
                  data-testid={`gap-days-${n}`}>
                  {n} gün
                </button>
              ))}
            </div>
          </div>

          {/* Preview KPIs */}
          {loading && !preview ? (
            <div className="bg-stone-950/40 rounded-xl p-6 text-center" data-testid="gap-preview-loading">
              <Loader2 className="w-5 h-5 text-stone-500 animate-spin mx-auto" />
            </div>
          ) : preview ? (
            <div className="bg-stone-950/40 rounded-xl p-4 border border-stone-800 space-y-3">
              {preview.applied > 0 ? (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <PreviewKpi label="Uygulanacak" value={preview.applied} suffix={` / ${preview.days_evaluated} gün`} testid="preview-applied" />
                    <PreviewKpi label="Ort. Uplift" value={`+${preview.avg_uplift_pct}%`} testid="preview-uplift" tone="emerald" />
                    <PreviewKpi label="Atlanan" value={preview.skipped} testid="preview-skipped" tone="stone" />
                  </div>
                  <div className="max-h-48 overflow-y-auto rounded-lg border border-stone-800/50">
                    <table className="w-full text-[11px]">
                      <thead className="bg-stone-950/80 sticky top-0">
                        <tr className="text-[9px] text-stone-400 uppercase tracking-widest">
                          <th className="text-left py-2 pl-3 pr-1">Tarih</th>
                          <th className="text-right px-1">Bizim</th>
                          <th className="text-right px-1">→</th>
                          <th className="text-right px-1">Yeni</th>
                          <th className="text-right px-1">+%</th>
                          <th className="text-right pr-3 pl-1">Pazar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.preview.map(p => (
                          <tr key={p.date} className="border-b border-stone-800/30 hover:bg-emerald-500/5">
                            <td className="py-1.5 pl-3 pr-1 text-stone-200">{p.date.slice(5)}</td>
                            <td className="text-right px-1 text-stone-500 tabular-nums">£{p.our_rate}</td>
                            <td className="text-right px-1 text-emerald-400/60">→</td>
                            <td className="text-right px-1 text-emerald-300 font-bold tabular-nums">£{p.new_rate}</td>
                            <td className="text-right px-1 text-emerald-400 tabular-nums">+{p.uplift_pct}%</td>
                            <td className="text-right pr-3 pl-1 text-stone-400 tabular-nums">£{p.market_avg}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="text-center py-6">
                  <AlertCircle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
                  <p className="text-xs text-stone-300">Pazara karşı kapatılacak gap yok</p>
                  <p className="text-[10px] text-stone-500 mt-1">Bu sürede zaten pazarın üstündesin veya rakip verisi yok</p>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-4 border-t border-stone-800 bg-stone-950/40">
          <p className="text-[10px] text-stone-500">
            Yeni fiyatlar `rate_overrides` koleksiyonuna yazılır (source=market-gap-close).
          </p>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-300" data-testid="gap-cancel">
              İptal
            </button>
            <button onClick={apply} disabled={!preview || preview.applied === 0 || applying}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 text-xs font-black transition disabled:opacity-40"
              data-testid="gap-apply">
              {applying
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <CheckCircle2 className="w-3.5 h-3.5" />}
              {preview && preview.applied > 0 ? `${preview.applied} güne uygula` : "Uygulanacak gün yok"}
              {preview && preview.applied > 0 && <ArrowUpRight className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewKpi({ label, value, suffix, testid, tone }) {
  const toneClass = tone === "emerald" ? "text-emerald-300" : tone === "stone" ? "text-stone-400" : "text-stone-100";
  return (
    <div className="bg-stone-900/60 rounded-lg p-2.5 border border-stone-800/50" data-testid={testid}>
      <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className={`text-base font-black mt-0.5 ${toneClass}`}>
        {value}
        {suffix && <span className="text-[10px] text-stone-500 font-normal">{suffix}</span>}
      </p>
    </div>
  );
}
