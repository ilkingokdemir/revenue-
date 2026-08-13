import { useState, useEffect } from "react";
import axios from "axios";
import { Pulse } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const color = (s) => s == null ? "bg-stone-200 text-stone-500"
  : s >= 80 ? "bg-emerald-100 text-emerald-700 border-emerald-200"
  : s >= 60 ? "bg-amber-100 text-amber-700 border-amber-200"
  : "bg-rose-100 text-rose-700 border-rose-200";

export const DataHealthStrip = ({ onNavigate }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    axios.get(`${API}/data-quality/summary/all`).then(({ data: d }) => setData(d)).catch(() => {});
  }, []);
  if (!data || !(data.properties || []).some((p) => p.score !== null)) return null;
  return (
    <div className="flex items-center gap-2 flex-wrap mb-4 px-1" data-testid="data-health-strip">
      <button onClick={() => onNavigate?.("data-quality")} data-testid="dhs-title"
        className="flex items-center gap-1.5 text-[11px] font-black text-stone-500 uppercase hover:text-indigo-600">
        <Pulse size={13} weight="fill" /> Veri Nöbetçisi
        {data.avg_score !== null && <span className="text-stone-400 normal-case font-bold">Ø {data.avg_score}</span>}
      </button>
      {data.properties.filter((p) => p.score !== null).map((p) => (
        <button key={p.property_id} onClick={() => onNavigate?.("data-quality")}
          data-testid={`dhs-chip-${p.property_id}`}
          title={`${p.name}: skor ${p.score} · ${p.issue_count} sorun`}
          className={`px-2.5 py-1 rounded-full border text-[10px] font-bold transition-transform hover:scale-105 ${color(p.score)}`}>
          {p.name} · {p.score}
        </button>
      ))}
    </div>
  );
};
