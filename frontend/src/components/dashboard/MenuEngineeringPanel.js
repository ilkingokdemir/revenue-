/**
 * Menu Engineering Panel
 * 4-quadrant analysis (Star / Plowhorse / Puzzle / Dog) with recommendations.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, RefreshCw, Download, Star, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const QUAD_COLOR = {
  star: "bg-emerald-500/20 border-emerald-500/40 text-emerald-200",
  plowhorse: "bg-amber-500/20 border-amber-500/40 text-amber-200",
  puzzle: "bg-cyan-500/20 border-cyan-500/40 text-cyan-200",
  dog: "bg-rose-500/20 border-rose-500/40 text-rose-200",
};

export default function MenuEngineeringPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/menu-engineering/${propertyId}?days=${days}`);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { refresh(); }, [refresh]);

  const fmt = (n) => Number(n || 0).toFixed(2);

  const exportCsv = async () => {
    try {
      const { data: ex } = await axios.get(`${API}/menu-engineering/${propertyId}/export?days=${days}`);
      const csv = [ex.columns.join(","), ...ex.rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `menu-engineering-${days}d.csv`; a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV downloaded");
    } catch { toast.error("Export failed"); }
  };

  const filteredRows = data?.rows?.filter((r) => !filter || r.quadrant === filter) || [];

  return (
    <div className="space-y-6" data-testid="menu-engineering-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Menu Engineering</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Star · Plowhorse · Puzzle · Dog — actionable F&B menu optimisation.</p>
      </div>

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <Stat label="Items" value={data.items_analysed} />
          <Stat label="Stars" value={data.counts.star} cls={QUAD_COLOR.star} />
          <Stat label="Plowhorses" value={data.counts.plowhorse} cls={QUAD_COLOR.plowhorse} />
          <Stat label="Puzzles" value={data.counts.puzzle} cls={QUAD_COLOR.puzzle} />
          <Stat label="Dogs" value={data.counts.dog} cls={QUAD_COLOR.dog} />
          <Stat label="Total CM" value={fmt(data.total_cm)} />
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <select value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{`${d} days`}</option>)}
        </select>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" data-testid="me-quad-filter">
          <option value="">All quadrants</option>
          {["star", "plowhorse", "puzzle", "dog"].map((q) => <option key={q} value={q}>{q}</option>)}
        </select>
        <button onClick={refresh} className="text-sm px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <button data-testid="me-export-btn" onClick={exportCsv} className="text-sm px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Download className="w-4 h-4" /> CSV</button>
      </div>

      {data && data.recommendations.length > 0 && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-1" data-testid="me-recommendations">
          <div className="flex items-center gap-2 text-amber-200 text-xs uppercase tracking-wider mb-1">
            <AlertTriangle className="w-3 h-3" /> Recommendations
          </div>
          {data.recommendations.map((r, i) => (
            <div key={i} className="text-sm text-amber-100">• {r}</div>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr>
              <th className="px-3 py-2">Item</th>
              <th className="px-3 py-2">Quadrant</th>
              <th className="px-3 py-2 text-right">Qty</th>
              <th className="px-3 py-2 text-right">Pop %</th>
              <th className="px-3 py-2 text-right">Unit Price</th>
              <th className="px-3 py-2 text-right">Unit Cost</th>
              <th className="px-3 py-2 text-right">Unit CM</th>
              <th className="px-3 py-2 text-right">Total CM</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r) => (
              <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="me-row">
                <td className="px-3 py-2"><div className="text-stone-100">{r.name}</div><div className="text-[10px] text-stone-500">{r.category}</div></td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${QUAD_COLOR[r.quadrant]} flex items-center gap-1 w-fit`}>{r.quadrant === "star" && <Star className="w-3 h-3" />}{r.quadrant}</span></td>
                <td className="px-3 py-2 text-right">{r.qty}</td>
                <td className="px-3 py-2 text-right">{r.pop_pct}%</td>
                <td className="px-3 py-2 text-right">{fmt(r.unit_price)}</td>
                <td className="px-3 py-2 text-right text-stone-400">{fmt(r.unit_cost)}</td>
                <td className="px-3 py-2 text-right text-emerald-300">{fmt(r.unit_cm)}</td>
                <td className="px-3 py-2 text-right">{fmt(r.total_cm)}</td>
              </tr>
            ))}
            {filteredRows.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-stone-500">No menu sales data in window. Post some POS orders to populate.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, cls = "" }) {
  return (
    <div className={`p-3 rounded-lg border ${cls || "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${cls ? "" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
