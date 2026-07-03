/**
 * SmartTipsCard — Mews-parity AI feature (iter 356).
 *
 * Renders a compact card in the Guest Profile detail view that generates
 * personalized service tips for the currently selected guest via the LLM.
 *
 * Props:
 *   guestId?: string       — pass to fetch full server-side context
 *   inlineProfile?: object — fallback when guest doesn't have a DB id yet
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Sparkles, Loader2, RefreshCcw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ICON_EMOJI = {
  star: "⭐", gift: "🎁", leaf: "🌿", alert: "⚠️", moon: "🌙",
  briefcase: "💼", heart: "❤️", coffee: "☕", wine: "🍷", utensils: "🍽️",
};

export function SmartTipsCard({ guestId, inlineProfile }) {
  const [tips, setTips] = useState(null);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const body = guestId ? { guest_id: guestId } : { profile: inlineProfile || {} };
      const r = await axios.post(`${API}/mews-ai/smart-tips`, body);
      setTips(r.data.tips || []);
      setMeta({ model: r.data.model, generated_at: r.data.generated_at });
      toast.success(`${r.data.tips.length} kişisel öneri üretildi`);
    } catch (e) {
      toast.error("Öneriler üretilemedi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-violet-50 to-fuchsia-50 rounded-2xl border-2 border-violet-200 p-4 shadow-sm" data-testid="smart-tips-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-md">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h4 className="text-sm font-black text-stone-900">AI Smart Tips</h4>
            <p className="text-[10px] text-violet-700/80">Bu misafire özel servis önerileri</p>
          </div>
        </div>
        <button
          onClick={generate}
          disabled={loading}
          data-testid="smart-tips-generate"
          className="text-[11px] px-3 py-1.5 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-bold shadow-sm disabled:opacity-50 inline-flex items-center gap-1"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : (tips ? <RefreshCcw className="w-3 h-3" /> : <Sparkles className="w-3 h-3" />)}
          {loading ? "Üretiliyor..." : tips ? "Yenile" : "Öneri Üret"}
        </button>
      </div>

      {!tips && !loading && (
        <p className="text-xs text-stone-500 italic">
          &quot;Öneri Üret&quot; tıklayın — misafirin etiketleri, tercihleri ve geçmiş konaklamalarına göre AI ekibinize aksiyon önerileri hazırlar.
        </p>
      )}

      {tips && (
        <div className="space-y-2" data-testid="smart-tips-list">
          {tips.map((tip, i) => (
            <div key={i} className="bg-white rounded-lg p-2.5 border border-violet-100 flex items-start gap-2.5 hover:border-violet-300 transition-colors">
              <div className="text-lg leading-none flex-shrink-0 mt-0.5">
                {ICON_EMOJI[tip.icon] || "💡"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-bold text-stone-800">{tip.title}</div>
                <div className="text-[11px] text-stone-600 mt-0.5">{tip.action}</div>
              </div>
            </div>
          ))}
          {meta && (
            <p className="text-[9px] text-stone-400 text-right pt-1">
              {meta.model === "fallback" ? "kural tabanlı" : "AI · " + meta.model}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
