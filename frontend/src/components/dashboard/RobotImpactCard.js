import React, { useEffect, useState } from "react";
import axios from "axios";
import { Robot, TrendUp, Lightning, Tag, ArrowRight, ChartLineUp } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (v) => `£${Number(v || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 })}`;

export default function RobotImpactCard({ propertyId, onNavigate }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (!propertyId || propertyId === "all") return;
    let on = true;
    axios.get(`${API}/api/revenue-brain/${propertyId}/impact-summary`, { withCredentials: true })
      .then((r) => { if (on) setD(r.data); })
      .catch(() => {});
    return () => { on = false; };
  }, [propertyId]);

  if (!d) return null;
  const total = d.est_total_contribution || 0;
  const pos = total >= 0;

  return (
    <div className="bg-stone-900 rounded-xl p-4 text-stone-100" data-testid="robot-impact-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-violet-500/20 flex items-center justify-center shrink-0">
            <Robot size={20} weight="fill" className="text-violet-300" />
          </div>
          <div>
            <div className="text-sm font-semibold">Robot Başarı Panosu <span className="text-stone-400 font-normal">— {d.month}</span></div>
            <div className="text-[10px] text-stone-400">Robotun bu ayki tahmini kâr katkısı</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-black leading-none ${pos ? "text-emerald-400" : "text-rose-400"}`} data-testid="robot-impact-total">
            {pos ? "+" : ""}{fmt(total)}
          </div>
          {d.contribution_pct_of_mtd != null && (
            <div className="text-[10px] text-stone-400 mt-0.5">ay içi gelirin %{d.contribution_pct_of_mtd}'i</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
        <Metric icon={ChartLineUp} label="Ölçülen karar" value={d.outcomes_measured} testId="robot-impact-outcomes" />
        <Metric icon={TrendUp} label="Başarı oranı" value={d.success_rate != null ? `%${d.success_rate}` : "—"} testId="robot-impact-success" />
        <Metric icon={Lightning} label="Uygulanan karar" value={d.decisions_applied} testId="robot-impact-decisions" />
        <Metric icon={Tag} label="Kampanya pickup" value={d.campaign_rooms_gained > 0 ? `+${d.campaign_rooms_gained} oda` : "—"} testId="robot-impact-campaign" />
      </div>

      <div className="mt-3 text-[11px] text-stone-300 bg-stone-800/70 border border-stone-700 rounded-lg px-3 py-2" data-testid="robot-impact-headline">
        🤖 {d.headline}
      </div>

      {onNavigate && (
        <button onClick={() => onNavigate("revenue-brain")} data-testid="robot-impact-goto"
          className="mt-3 text-[11px] font-bold text-violet-300 hover:text-violet-200 inline-flex items-center gap-1">
          Revenue Robotu'na git <ArrowRight size={12} weight="bold" />
        </button>
      )}
    </div>
  );
}

function Metric({ icon: Icon, label, value, testId }) {
  return (
    <div className="bg-stone-800/60 rounded-lg px-2.5 py-2 flex items-center gap-2" data-testid={testId}>
      <Icon size={14} className="text-stone-400 shrink-0" />
      <div>
        <div className="text-sm font-bold leading-tight">{value}</div>
        <div className="text-[9px] text-stone-400">{label}</div>
      </div>
    </div>
  );
}
