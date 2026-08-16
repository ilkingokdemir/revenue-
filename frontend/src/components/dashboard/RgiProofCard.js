import React, { useEffect, useState } from "react";
import axios from "axios";
import { ChartBarHorizontal } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function RgiProofCard({ propertyId }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (!propertyId) return;
    let on = true;
    axios.get(`${API}/api/rgi-proof/${propertyId}`, { withCredentials: true })
      .then((r) => on && setD(r.data)).catch(() => {});
    return () => { on = false; };
  }, [propertyId]);

  if (!d) return null;
  const withRgi = d.weeks.filter((w) => w.rgi);
  const maxRgi = Math.max(...withRgi.map((w) => w.rgi), 120);

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 mt-4" data-testid="rgi-proof-card">
      <div className="text-sm font-semibold text-stone-900 flex items-center gap-2 mb-1">
        <ChartBarHorizontal size={16} weight="fill" className="text-indigo-600" /> RGI — Pazar Endeksli Kanıt
        <span className="text-[10px] text-stone-400 font-normal">— RevPAR endeksi (biz / pazar × 100)</span>
        {d.avg_mpi != null && <span className="ml-auto px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 text-[10px] font-black" data-testid="rgi-mpi-badge">MPI {d.avg_mpi}</span>}
        {d.avg_ari != null && <span className="px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 text-[10px] font-black" data-testid="rgi-ari-badge">ARI {d.avg_ari}</span>}
      </div>
      <p className="text-[11px] text-indigo-800 bg-indigo-50 border border-indigo-100 rounded-lg px-3 py-2 mb-3" data-testid="rgi-verdict">
        📊 {d.verdict}
      </p>
      {withRgi.length === 0 ? (
        <div className="text-xs text-stone-400 py-2">Pazar taraması biriktikçe haftalık RGI çubukları burada görünecek.</div>
      ) : (
        <div className="space-y-1.5">
          {d.weeks.map((w) => (
            <div key={w.week} className="flex items-center gap-2 text-[11px]" data-testid={`rgi-week-${w.week}`}>
              <span className="w-16 text-stone-500 shrink-0">{w.week}</span>
              <span className={`w-10 shrink-0 text-[9px] font-bold ${w.phase === "robot" ? "text-violet-600" : "text-stone-400"}`}>
                {w.phase === "robot" ? "ROBOT" : "önce"}</span>
              <div className="flex-1 bg-stone-100 rounded-full h-3.5 relative overflow-hidden">
                {w.rgi ? (
                  <div className={`h-full rounded-full ${w.rgi >= 100 ? "bg-emerald-500" : "bg-amber-400"}`}
                    style={{ width: `${Math.min(w.rgi / maxRgi * 100, 100)}%` }} />
                ) : <div className="h-full w-1 bg-stone-200" />}
                <div className="absolute top-0 bottom-0 border-l border-dashed border-stone-400" style={{ left: `${100 / maxRgi * 100}%` }} />
              </div>
              <span className="w-14 text-right font-bold text-stone-800 shrink-0">{w.rgi ? w.rgi : "—"}</span>
              <span className="w-20 text-right text-[9px] text-stone-400 shrink-0" data-testid={`rgi-mpi-ari-${w.week}`}>{w.mpi ? `M${w.mpi}` : ""}{w.ari ? ` A${w.ari}` : ""}</span>
            </div>
          ))}
          <div className="flex justify-between text-[9px] text-stone-400 pt-1">
            <span>Kesikli çizgi = 100 (pazar paritesi)</span>
            {d.avg_rgi_before && <span>Önce ort: {d.avg_rgi_before}</span>}
            {d.avg_rgi_after && <span className="font-bold text-violet-600">Robot ort: {d.avg_rgi_after}</span>}
          </div>
        </div>
      )}
      <p className="text-[10px] text-stone-400 mt-2">{d.note}</p>
    </div>
  );
}
