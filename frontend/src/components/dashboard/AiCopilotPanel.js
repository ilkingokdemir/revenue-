import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Brain, ArrowRight } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODULES = [
  { view: "bi-chat", name: "Veriye Sor (BI Chat)", desc: "Doğal dille rapor ve analiz sorgula", statKey: null },
  { view: "ai-pricing", name: "AI Fiyatlama Motoru", desc: "Rakip tetikleri, heatmap, öneriler", statKey: "comp_triggers_on", statLabel: "aktif tetik" },
  { view: "rms-setup", name: "RMS Co-Pilot Kuyruğu", desc: "Onay bekleyen fiyat önerileri", statKey: "copilot_pending", statLabel: "bekleyen öneri" },
  { view: "price-guards", name: "Fiyat Bekçileri", desc: "POBA + Surge otomatik koruma", statKey: "guard_actions_24h", statLabel: "aksiyon (24s)" },
  { view: "ical-sync", name: "Çakışma Nöbetçisi", desc: "iCal çifte rezervasyon alarmı", statKey: "open_conflicts", statLabel: "açık çakışma" },
  { view: "reviews", name: "Yorum Autopilot", desc: "AI yorum yanıtları ve itibar yönetimi", statKey: null },
  { view: "ai-predictions", name: "AI Tahminler", desc: "Talep, iptal ve no-show tahminleri", statKey: null },
  { view: "error-sentinel", name: "Health Sentinel", desc: "Gece API sağlık taraması", statKey: null },
];

export default function AiCopilotPanel({ activePropertyId, properties, onNavigate }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [stats, setStats] = useState({});
  const [today, setToday] = useState([]);

  const load = useCallback(async () => {
    try {
      const [{ data: s }, { data: t }] = await Promise.all([
        axios.get(`${API}/ai-copilot/summary/${pid}`),
        axios.get(`${API}/ai-copilot/today/${pid}`),
      ]);
      setStats(s);
      setToday(t.tasks || []);
    } catch { /* silent */ }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6 max-w-5xl" data-testid="ai-copilot-panel">
      <div className="rounded-2xl bg-gradient-to-r from-indigo-700 via-violet-700 to-fuchsia-700 p-6 mb-6 text-white">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-white/15 flex items-center justify-center">
            <Brain size={24} weight="fill" />
          </div>
          <div>
            <h2 className="text-xl font-black">ReveniQ AI Copilot</h2>
            <p className="text-[11px] text-white/80">Otelinizin tüm yapay zekâ gücü tek çatı altında — fiyattan yoruma, tahminden nöbete.</p>
          </div>
          <div className="ml-auto flex gap-3 text-center">
            {[["copilot_pending", "Bekleyen Öneri"], ["unread_ai_alerts", "AI Uyarısı"], ["autopilot_on", "Autopilot Açık"]].map(([k, l]) => (
              <div key={k} className="bg-white/10 rounded-xl px-4 py-2" data-testid={`copilot-stat-${k}`}>
                <div className="text-xl font-black">{stats[k] ?? "–"}</div>
                <div className="text-[9px] uppercase tracking-wide text-white/70">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bugün ne yapmalıyım */}
      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-6" data-testid="copilot-today-card">
        <h3 className="text-sm font-black text-stone-800 mb-3">📋 Bugün ne yapmalıyım?</h3>
        <div className="space-y-2">
          {today.map((t, i) => (
            <button key={i} onClick={() => onNavigate && onNavigate(t.view)} data-testid={`copilot-task-${i}`}
              className="w-full text-left flex items-start gap-3 rounded-xl border border-stone-100 px-3 py-2.5 hover:border-indigo-300 hover:bg-indigo-50/40 transition-colors">
              <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                t.severity === "high" ? "bg-red-500" : t.severity === "medium" ? "bg-amber-500"
                : t.severity === "ok" ? "bg-emerald-500" : "bg-stone-300"}`} />
              <span className="flex-1">
                <span className="block text-xs font-bold text-stone-800">{t.title}</span>
                <span className="block text-[10px] text-stone-500">{t.detail}</span>
              </span>
              <ArrowRight size={13} className="mt-1 text-stone-300" />
            </button>
          ))}
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {MODULES.map((m) => (
          <button key={m.view} onClick={() => onNavigate && onNavigate(m.view)} data-testid={`copilot-module-${m.view}`}
            className="text-left rounded-2xl border border-stone-200 bg-white p-4 hover:border-indigo-400 hover:shadow-md transition-all group">
            <div className="flex items-center justify-between">
              <div className="text-sm font-bold text-stone-800">{m.name}</div>
              <ArrowRight size={14} className="text-stone-300 group-hover:text-indigo-600" />
            </div>
            <div className="text-[11px] text-stone-500 mt-1">{m.desc}</div>
            {m.statKey && stats[m.statKey] !== undefined && (
              <div className="mt-2 inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                {stats[m.statKey]} {m.statLabel}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
