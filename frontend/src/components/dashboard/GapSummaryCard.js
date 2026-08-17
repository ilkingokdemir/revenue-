import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

export const GapSummaryCard = ({ propertyId, onNavigate }) => {
  const [s, setS] = useState(null);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/api/demand-signals/${propertyId}/comp-trigger/summary`, { headers: authHeaders() })
      .then((r) => setS(r.data)).catch(() => {});
  }, [propertyId]);

  if (!s || !s.this_week) return null;
  const dev = s.this_week.avg_dev;
  const dirCfg = {
    "açılıyor": { icon: "▲", cls: "text-rose-600 bg-rose-50 border-rose-200", label: "makas açılıyor" },
    "kapanıyor": { icon: "▼", cls: "text-emerald-600 bg-emerald-50 border-emerald-200", label: "makas kapanıyor" },
    "stabil": { icon: "→", cls: "text-stone-500 bg-stone-50 border-stone-200", label: "makas stabil" },
  }[s.direction];
  const wks = s.weeks || [];
  const vals = wks.map((w) => Math.abs(w.avg_dev));
  const hi = Math.max(...vals, 1);
  const pts = wks.map((w, i) => `${8 + (wks.length > 1 ? (i / (wks.length - 1)) * 104 : 52)},${30 - (Math.abs(w.avg_dev) / hi) * 24}`).join(" ");

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 flex flex-wrap items-center gap-4 cursor-pointer hover:border-stone-300 transition-colors"
      onClick={() => onNavigate && onNavigate("revenue")} data-testid="gap-summary-card">
      <div className="flex-1 min-w-[180px]">
        <div className="text-[11px] font-bold text-stone-400 uppercase tracking-wide">📡 Pazarla Makas — bu hafta</div>
        <div className="flex items-baseline gap-2 mt-1">
          <span className={`text-2xl font-black ${dev >= 0 ? "text-rose-600" : "text-sky-700"}`} data-testid="gap-summary-dev">
            {dev > 0 ? "+" : ""}{dev}%
          </span>
          <span className="text-xs text-stone-500">{dev >= 0 ? "pazardan pahalıyız" : "pazardan ucuzuz"}</span>
        </div>
      </div>
      <svg viewBox="0 0 120 34" className="w-28 h-9" data-testid="gap-summary-spark">
        <polyline points={pts} fill="none" stroke="#7c3aed" strokeWidth="2" strokeLinecap="round" />
        {wks.map((w, i) => (
          <circle key={w.week} cx={8 + (wks.length > 1 ? (i / (wks.length - 1)) * 104 : 52)}
            cy={30 - (Math.abs(w.avg_dev) / hi) * 24} r="2"
            fill={w.avg_dev >= 0 ? "#e11d48" : "#0284c7"} />
        ))}
      </svg>
      <div className="flex flex-col items-end gap-1">
        <span className={`text-[11px] font-black px-2.5 py-1 rounded-full border ${dirCfg.cls}`} data-testid="gap-summary-direction">
          {dirCfg.icon} {dirCfg.label}
        </span>
        {s.alert_active && (
          <span className="text-[10px] font-bold text-amber-600" data-testid="gap-summary-alert">📉 trend uyarısı aktif</span>
        )}
      </div>
    </div>
  );
};
