import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Sparkle, Lightbulb, ArrowsClockwise, ChatCircleDots } from "@phosphor-icons/react";
import CopilotButton from "../CopilotButton";

const API = process.env.REACT_APP_BACKEND_URL;

const CONTEXT_LABELS = {
  kpis: "KPI",
  anomaly: "Anomali",
  timeseries: "Zaman Serisi",
  leaderboard: "Lider Tablo",
  inquiry: "MICE",
  forecast: "Tahmin",
  custom: "Özel",
};

export default function CopilotLibraryPanel({ propertyId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [customQuery, setCustomQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/copilot/recent?limit=30`, { withCredentials: true });
      setRows(r.data.rows || []);
    } catch (e) {
      toast.error("Geçmiş yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-5 max-w-[1200px] mx-auto" data-testid="copilot-library">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Sparkle size={12} weight="fill" className="text-violet-500" />
          <span>AI · Copilot Arşivi</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          AI Copilot Kütüphanesi
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Dashboard'larda "AI Özet" butonlarını kullanın — analizler burada arşivlenir.
          Sorularınızı buradan direkt GPT-5.2'ye sorabilirsiniz.
        </p>
      </div>

      {/* Custom ask */}
      <div className="bg-gradient-to-br from-violet-50 to-fuchsia-50 border border-violet-200 rounded-lg p-5 mb-6">
        <div className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-2">
          <ChatCircleDots size={16} className="text-violet-500" />
          Otele Özel Soru Sor
        </div>
        <div className="flex gap-2">
          <input
            value={customQuery}
            onChange={(e) => setCustomQuery(e.target.value)}
            placeholder="Örn: Bu hafta hangi segmentte gelir düştü?"
            data-testid="copilot-custom-query"
            className="flex-1 px-3 py-2 text-sm bg-white border border-stone-200 rounded-md focus:outline-none focus:border-violet-400"
            onKeyDown={(e) => e.key === "Enter" && customQuery && document.querySelector('[data-testid="copilot-ask-custom"]').click()}
          />
          <CopilotButton
            contextType="custom"
            data={{ general_query: true }}
            query={customQuery}
            label="Sor"
            testId="copilot-ask-custom"
            className="px-4 py-2 text-sm"
          />
        </div>
        <div className="text-[10px] text-stone-500 mt-2">
          Yanıtlar 24 saat önbelleklenir — aynı soru tekrar harcama çıkarmaz.
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-stone-800">Son Analizler ({rows.length})</div>
        <button onClick={load} className="px-3 py-1 text-xs rounded-md border border-stone-200 text-stone-600 hover:bg-stone-50 inline-flex items-center gap-1.5">
          <ArrowsClockwise size={12} /> Yenile
        </button>
      </div>

      {loading && <div className="text-sm text-stone-400">Yükleniyor…</div>}

      {rows.length === 0 && !loading && (
        <div className="text-center py-12 text-stone-400 text-sm border border-dashed border-stone-200 rounded-lg">
          Henüz AI analiz yok. Diğer dashboard'larda "AI Özet" butonuna tıklayın.
        </div>
      )}

      <div className="space-y-3" data-testid="copilot-history">
        {rows.map((r) => (
          <div key={r.key} className="bg-white border border-stone-200 rounded-lg p-4" data-testid={`copilot-row-${r.key}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-violet-100 text-violet-700 font-medium">
                {CONTEXT_LABELS[r.context_type] || r.context_type}
              </span>
              <span className="text-[10px] text-stone-400">{r.source === "llm" ? "GPT-5.2" : "Sezgisel"}</span>
              <span className="text-[10px] text-stone-400 ml-auto">{r.created_at?.slice(0, 16).replace("T", " ")}</span>
            </div>
            <div className="text-sm text-stone-800 mb-2 leading-relaxed">{r.insight}</div>
            {r.suggested_actions?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {r.suggested_actions.map((a, i) => (
                  <span key={i} className="px-1.5 py-0.5 text-[10px] bg-violet-50 border border-violet-100 rounded text-violet-700 inline-flex items-center gap-1">
                    <Lightbulb size={10} weight="fill" />
                    {a}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
