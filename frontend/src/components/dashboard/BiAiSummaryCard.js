/**
 * BiAiSummaryCard — Mews-parity AI feature (iter 356).
 *
 * Compact AI-generated "what changed" narrative for a property. Consumes
 * POST /api/mews-ai/bi-summary and renders the emoji-tagged bullet lines.
 *
 * Props:
 *   propertyId: string
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Brain, Loader2, RefreshCcw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function BiAiSummaryCard({ propertyId }) {
  const [summary, setSummary] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    if (!propertyId || propertyId === "all") {
      toast.warning("Bir property seçin (All Branches değil)");
      return;
    }
    setLoading(true);
    try {
      const r = await axios.post(`${API}/mews-ai/bi-summary`, { property_id: propertyId });
      setSummary(r.data.summary_md);
      setSnapshot(r.data.snapshot);
      setMeta({ model: r.data.model, generated_at: r.data.generated_at });
    } catch (e) {
      toast.error("AI özet üretilemedi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-indigo-900 via-violet-900 to-fuchsia-900 rounded-2xl p-5 shadow-xl border border-white/10" data-testid="bi-ai-summary-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-white/10 backdrop-blur-sm flex items-center justify-center">
            <Brain className="w-5 h-5 text-fuchsia-300" />
          </div>
          <div>
            <h3 className="text-sm font-black text-white">AI İş Zekası Özeti</h3>
            <p className="text-[10px] text-fuchsia-200/70">&quot;Bu ay ne değişti?&quot; — LLM tarafından üretilir</p>
          </div>
        </div>
        <button
          onClick={generate}
          disabled={loading}
          data-testid="bi-ai-generate"
          className="text-[11px] px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white rounded-lg font-bold border border-white/20 disabled:opacity-50 inline-flex items-center gap-1.5"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : summary ? <RefreshCcw className="w-3 h-3" /> : <Brain className="w-3 h-3" />}
          {loading ? "Analiz ediliyor..." : summary ? "Yenile" : "Özet Üret"}
        </button>
      </div>

      {!summary && !loading && (
        <p className="text-xs text-white/60 italic">
          Son 30 gün rezervasyon trendleri, YoY karşılaştırma, gider kırılımı ve last-minute stratejinizi analiz eder → aksiyon önerileri sunar.
        </p>
      )}

      {summary && (
        <div className="space-y-2" data-testid="bi-ai-summary-content">
          <div className="bg-black/20 backdrop-blur-sm rounded-lg p-3 border border-white/10">
            <pre className="text-xs text-white/95 font-sans whitespace-pre-wrap leading-relaxed">
              {summary}
            </pre>
          </div>
          {snapshot && (
            <div className="grid grid-cols-4 gap-2 pt-1">
              <div className="text-center">
                <p className="text-[8px] text-fuchsia-200/60 uppercase">Son 30 gün</p>
                <p className="text-sm font-black text-white">{snapshot.bookings_last_30d}</p>
                <p className="text-[9px] text-fuchsia-300/80">{snapshot.bookings_delta_pct >= 0 ? "+" : ""}{snapshot.bookings_delta_pct}%</p>
              </div>
              <div className="text-center">
                <p className="text-[8px] text-fuchsia-200/60 uppercase">YoY Ay</p>
                <p className="text-sm font-black text-white">{snapshot.yoy_months_recorded}/12</p>
              </div>
              <div className="text-center">
                <p className="text-[8px] text-fuchsia-200/60 uppercase">Yıllık Gider</p>
                <p className="text-sm font-black text-white">{snapshot.currency}{Math.round(snapshot.expense_annual_total / 1000)}k</p>
              </div>
              <div className="text-center">
                <p className="text-[8px] text-fuchsia-200/60 uppercase">LM İskonto</p>
                <p className="text-sm font-black text-white">{snapshot.last_minute?.discount_pct || 0}%</p>
              </div>
            </div>
          )}
          {meta && (
            <p className="text-[9px] text-white/40 text-right">
              {meta.model === "fallback" ? "veri özeti (LLM devre dışı)" : "AI · " + meta.model}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
