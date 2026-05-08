import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FlaskConical, TrendingUp, TrendingDown, RefreshCw, ArrowUpRight, ArrowDownRight, CheckCircle, XCircle, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export const WhatIfSimulator = ({ propertyId }) => {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [params, setParams] = useState({ rate_change_pct: 10, date_from: new Date().toISOString().split("T")[0], date_to: new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0] });

  const simulate = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/revenue/intelligence/${propertyId}/what-if`, params);
      setResult(data);
      toast.success("Simulation complete");
    } catch { toast.error("Simulation failed"); }
    setLoading(false);
  };

  const imp = result?.impact;

  return (
    <div className="space-y-5" data-testid="what-if-simulator">
      {/* Input Panel */}
      <div className="bg-gradient-to-r from-orange-900 via-amber-900 to-orange-900 rounded-2xl p-5 text-white">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><FlaskConical className="w-5 h-5 text-amber-300" /></div>
          <div><h2 className="text-lg font-bold">What-If Simulator</h2><p className="text-xs text-white/40">Test rate changes before you commit</p></div>
        </div>
        <div className="grid grid-cols-4 gap-4 items-end">
          <div>
            <label className="text-[10px] text-white/50 block mb-1">Rate Change %</label>
            <Input type="number" value={params.rate_change_pct} onChange={e => setParams(p => ({ ...p, rate_change_pct: Number(e.target.value) }))} className="bg-white/10 border-white/20 text-white h-10" data-testid="whatif-pct" />
          </div>
          <div>
            <label className="text-[10px] text-white/50 block mb-1">From Date</label>
            <Input type="date" value={params.date_from} onChange={e => setParams(p => ({ ...p, date_from: e.target.value }))} className="bg-white/10 border-white/20 text-white h-10" data-testid="whatif-from" />
          </div>
          <div>
            <label className="text-[10px] text-white/50 block mb-1">To Date</label>
            <Input type="date" value={params.date_to} onChange={e => setParams(p => ({ ...p, date_to: e.target.value }))} className="bg-white/10 border-white/20 text-white h-10" data-testid="whatif-to" />
          </div>
          <button onClick={simulate} disabled={loading}
            className="flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-600 text-white h-10 rounded-xl text-sm font-semibold disabled:opacity-50" data-testid="whatif-simulate">
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
            Simulate
          </button>
        </div>
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {[-20, -10, -5, 5, 10, 15, 20, 30].map(v => (
            <button key={v} onClick={() => { setParams(p => ({ ...p, rate_change_pct: v })); }}
              className={`px-3 py-1 text-xs font-semibold rounded-lg border ${params.rate_change_pct === v ? "bg-white/20 border-white/30 text-white" : "border-white/10 text-white/40 hover:text-white/70"}`}>
              {v > 0 ? "+" : ""}{v}%
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Verdict */}
          <div className={`rounded-2xl p-5 border ${imp.verdict === "positive" ? "bg-emerald-50 border-emerald-200" : imp.verdict === "negative" ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"}`} data-testid="whatif-verdict">
            <div className="flex items-center gap-3 mb-2">
              {imp.verdict === "positive" ? <CheckCircle className="w-6 h-6 text-emerald-600" /> : imp.verdict === "negative" ? <XCircle className="w-6 h-6 text-red-500" /> : <AlertTriangle className="w-6 h-6 text-amber-600" />}
              <h3 className={`text-lg font-bold ${imp.verdict === "positive" ? "text-emerald-800" : imp.verdict === "negative" ? "text-red-800" : "text-amber-800"}`}>{imp.recommendation}</h3>
            </div>
          </div>

          {/* Comparison Cards */}
          <div className="grid grid-cols-2 gap-4" data-testid="whatif-comparison">
            <div className="bg-white border border-stone-200 rounded-2xl p-5">
              <h4 className="text-sm font-bold text-stone-400 mb-3">CURRENT (No Change)</h4>
              <div className="grid grid-cols-2 gap-4">
                <div><p className="text-[10px] text-stone-400">Revenue</p><p className="text-xl font-bold text-stone-800">{cur(result.current.total_revenue)}</p></div>
                <div><p className="text-[10px] text-stone-400">Occupancy</p><p className="text-xl font-bold text-stone-800">{result.current.avg_occupancy}%</p></div>
                <div><p className="text-[10px] text-stone-400">ADR</p><p className="text-xl font-bold text-stone-800">{cur(result.current.avg_adr)}</p></div>
                <div><p className="text-[10px] text-stone-400">Rooms Sold</p><p className="text-xl font-bold text-stone-800">{result.current.total_rooms_sold}</p></div>
              </div>
            </div>
            <div className={`border rounded-2xl p-5 ${imp.verdict === "positive" ? "bg-emerald-50 border-emerald-200" : imp.verdict === "negative" ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"}`}>
              <h4 className="text-sm font-bold text-stone-400 mb-3">PROJECTED ({params.rate_change_pct > 0 ? "+" : ""}{params.rate_change_pct}% Change)</h4>
              <div className="grid grid-cols-2 gap-4">
                <div><p className="text-[10px] text-stone-400">Revenue</p><p className="text-xl font-bold">{cur(result.projected.total_revenue)}<span className={`text-sm ml-2 ${imp.revenue_diff >= 0 ? "text-emerald-600" : "text-red-500"}`}>{imp.revenue_diff >= 0 ? "+" : ""}{cur(imp.revenue_diff)}</span></p></div>
                <div><p className="text-[10px] text-stone-400">Occupancy</p><p className="text-xl font-bold">{result.projected.avg_occupancy}%<span className={`text-sm ml-2 ${imp.occupancy_diff >= 0 ? "text-emerald-600" : "text-red-500"}`}>{imp.occupancy_diff >= 0 ? "+" : ""}{imp.occupancy_diff}%</span></p></div>
                <div><p className="text-[10px] text-stone-400">ADR</p><p className="text-xl font-bold">{cur(result.projected.avg_adr)}<span className={`text-sm ml-2 ${imp.adr_diff >= 0 ? "text-emerald-600" : "text-red-500"}`}>{imp.adr_diff >= 0 ? "+" : ""}{cur(imp.adr_diff)}</span></p></div>
                <div><p className="text-[10px] text-stone-400">Rooms Sold</p><p className="text-xl font-bold">{result.projected.total_rooms_sold}</p></div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
