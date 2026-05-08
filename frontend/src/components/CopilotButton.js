import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Sparkle, Lightbulb, X } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Reusable "AI Özet" button — drop anywhere next to data.
 * Usage: <CopilotButton contextType="kpis" data={kpisObject} label="Açıkla" />
 */
export default function CopilotButton({
  contextType = "custom",
  data,
  query,
  label = "AI Özet",
  propertyId,
  className = "",
  testId,
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const ask = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/copilot/summarize`, {
        context_type: contextType,
        data,
        query: query || null,
        property_id: propertyId || null,
      }, { withCredentials: true });
      setResult(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Özet alınamadı");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={ask}
        disabled={busy}
        data-testid={testId || "copilot-btn"}
        className={`px-2.5 py-1 text-[11px] rounded-md bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:from-violet-600 hover:to-fuchsia-600 disabled:opacity-60 inline-flex items-center gap-1.5 transition-all ${className}`}
      >
        <Sparkle size={11} weight="fill" />
        {busy ? "Düşünüyorum…" : label}
      </button>

      {result && (
        <div
          className="fixed inset-0 bg-stone-900/50 backdrop-blur-sm z-[9999] flex items-center justify-center p-4"
          onClick={() => setResult(null)}
          data-testid="copilot-modal"
        >
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5 bg-gradient-to-br from-violet-500 to-fuchsia-600 text-white relative">
              <button
                onClick={() => setResult(null)}
                data-testid="copilot-close"
                className="absolute top-3 right-3 w-7 h-7 rounded-full bg-white/20 hover:bg-white/30 inline-flex items-center justify-center"
              >
                <X size={14} weight="bold" />
              </button>
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] opacity-80 mb-1">
                <Sparkle size={12} weight="fill" />
                {result.source === "llm" || result.source === "llm_raw" ? "GPT-5.2 Analiz" : "Sezgisel Analiz"}
                {result.cached && <span className="opacity-60">· cache</span>}
              </div>
              <div className="text-lg font-semibold">AI Copilot</div>
            </div>

            <div className="p-5 space-y-4">
              <div className="text-sm text-stone-800 leading-relaxed" data-testid="copilot-insight">
                {result.insight}
              </div>

              {result.suggested_actions?.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1">
                    <Lightbulb size={11} weight="fill" />
                    Önerilen Aksiyonlar
                  </div>
                  <div className="space-y-1.5" data-testid="copilot-actions">
                    {result.suggested_actions.map((a, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-stone-700 bg-violet-50 border border-violet-100 rounded-md px-2.5 py-1.5">
                        <span className="text-violet-500 font-semibold">{i + 1}.</span>
                        <span>{a}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="px-5 pb-5">
              <button
                onClick={() => setResult(null)}
                className="w-full py-2 text-sm rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
