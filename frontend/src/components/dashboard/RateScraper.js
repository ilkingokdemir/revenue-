import { useState, useEffect } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { RefreshCw, Settings2, Zap, TrendingUp, TrendingDown, ArrowRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const STRATEGIES = [
  { id: "match_median", label: "Match Median", desc: "Set rate to competitor average" },
  { id: "undercut_5", label: "Undercut 5%", desc: "5% below competitor average" },
  { id: "premium_10", label: "Premium 10%", desc: "10% above competitor average" },
  { id: "match_lowest", label: "Match Lowest", desc: "Match cheapest competitor" },
];

export const RateScraper = ({ propertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConfig, setShowConfig] = useState(false);
  const [config, setConfig] = useState(null);
  const [selected, setSelected] = useState(new Set());

  const pid = propertyId || "all";

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/revenue/rate-scraper/${pid}`)
      .then(r => { setData(r.data); setConfig(r.data.config); setLoading(false); })
      .catch(() => setLoading(false));
  }, [pid]);

  const saveConfig = async () => {
    try {
      await axios.put(`${API}/revenue/rate-scraper/${pid}/config`, config);
      toast.success("Config saved");
      setShowConfig(false);
    } catch { toast.error("Failed"); }
  };

  const applyRates = async () => {
    const dates = data.daily.filter(d => selected.has(d.date)).map(d => ({ date: d.date, rate: d.suggested_rate }));
    if (!dates.length) { toast.error("Select dates first"); return; }
    try {
      const { data: res } = await axios.post(`${API}/revenue/rate-scraper/${pid}/apply`, { dates });
      toast.success(`Applied ${res.applied} rate${res.applied !== 1 ? "s" : ""}`);
      setSelected(new Set());
    } catch { toast.error("Failed"); }
  };

  const toggleDate = (ds) => setSelected(prev => { const n = new Set(prev); n.has(ds) ? n.delete(ds) : n.add(ds); return n; });
  const selectAll = () => setSelected(new Set(data.daily.map(d => d.date)));

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading...</div>;
  if (!data) return null;

  return (
    <div className="space-y-5" data-testid="rate-scraper">
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Zap className="w-5 h-5 text-amber-400" /></div>
            <div>
              <h2 className="text-lg font-bold" data-testid="scraper-title">Competitor Rate Automation</h2>
              <p className="text-xs text-white/40">{data.total_competitors} competitors tracked</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowConfig(!showConfig)} data-testid="scraper-config-btn"
              className="flex items-center gap-1 px-3 py-2 text-xs text-white/60 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10">
              <Settings2 className="w-3.5 h-3.5" />Config
            </button>
            <button onClick={applyRates} disabled={selected.size === 0} data-testid="apply-rates-btn"
              className="flex items-center gap-1 px-4 py-2 text-xs font-bold bg-emerald-500 hover:bg-emerald-400 text-white rounded-lg disabled:opacity-40">
              <ArrowRight className="w-3.5 h-3.5" />Apply {selected.size} Rate{selected.size !== 1 ? "s" : ""}
            </button>
          </div>
        </div>

        {/* Strategy display */}
        <div className="flex items-center gap-3 text-xs text-white/40">
          <span>Strategy: <strong className="text-white">{STRATEGIES.find(s => s.id === config?.strategy)?.label || "Match Median"}</strong></span>
          <span>Auto-adjust: <strong className={config?.auto_adjust ? "text-emerald-400" : "text-red-400"}>{config?.auto_adjust ? "ON" : "OFF"}</strong></span>
          <span>Guard: ±{config?.max_adjustment_pct || 15}%</span>
        </div>
      </div>

      {/* Config Panel */}
      {showConfig && config && (
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="scraper-config-panel">
          <h3 className="text-sm font-bold text-white mb-3">Scraper Configuration</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div>
              <label className="text-[9px] text-stone-500 uppercase block mb-1">Strategy</label>
              <select value={config.strategy} onChange={e => setConfig({...config, strategy: e.target.value})}
                className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-2 text-sm text-white">
                {STRATEGIES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[9px] text-stone-500 uppercase block mb-1">Max Adjustment %</label>
              <input type="number" value={config.max_adjustment_pct} onChange={e => setConfig({...config, max_adjustment_pct: parseInt(e.target.value)})}
                className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-2 text-sm text-white" />
            </div>
            <div>
              <label className="text-[9px] text-stone-500 uppercase block mb-1">Min Rate</label>
              <input type="number" value={config.min_rate} onChange={e => setConfig({...config, min_rate: parseFloat(e.target.value)})}
                className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-2 text-sm text-white" />
            </div>
            <div>
              <label className="text-[9px] text-stone-500 uppercase block mb-1">Max Rate</label>
              <input type="number" value={config.max_rate} onChange={e => setConfig({...config, max_rate: parseFloat(e.target.value)})}
                className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-2 text-sm text-white" />
            </div>
          </div>
          <div className="flex items-center gap-4 mt-3">
            <label className="flex items-center gap-2 text-xs text-stone-400"><input type="checkbox" checked={config.auto_adjust} onChange={e => setConfig({...config, auto_adjust: e.target.checked})} /> Auto-adjust rates</label>
            <label className="flex items-center gap-2 text-xs text-stone-400"><input type="checkbox" checked={config.enabled} onChange={e => setConfig({...config, enabled: e.target.checked})} /> Enabled</label>
            <button onClick={saveConfig} data-testid="save-scraper-config" className="ml-auto px-4 py-1.5 text-xs font-bold bg-violet-500 text-white rounded-lg">Save</button>
          </div>
        </div>
      )}

      {/* Rate Table */}
      <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="rate-table">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-white">Daily Rate Comparison</h3>
          <button onClick={selectAll} className="text-[10px] text-violet-400 hover:text-violet-300">Select All</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-stone-500 border-b border-stone-700">
                <th className="text-left py-2 px-1 w-8"></th>
                <th className="text-left py-2 px-2">Date</th>
                <th className="text-right py-2 px-2">Your Rate</th>
                <th className="text-right py-2 px-2">Comp Avg</th>
                <th className="text-right py-2 px-2">Comp Min</th>
                <th className="text-right py-2 px-2">Comp Max</th>
                <th className="text-right py-2 px-2">Diff</th>
                <th className="text-right py-2 px-2">Suggested</th>
              </tr>
            </thead>
            <tbody>
              {data.daily.map(d => {
                const hasDiff = d.diff_pct !== null;
                const isAbove = d.diff_pct > 5;
                const isBelow = d.diff_pct < -5;
                return (
                  <tr key={d.date} className={`border-b border-stone-800/50 hover:bg-stone-800/30 ${d.is_weekend ? "bg-stone-800/20" : ""} ${selected.has(d.date) ? "bg-violet-900/20" : ""}`}>
                    <td className="py-1.5 px-1">
                      <input type="checkbox" checked={selected.has(d.date)} onChange={() => toggleDate(d.date)} className="rounded" />
                    </td>
                    <td className="py-1.5 px-2 text-white font-medium">{d.dow} {new Date(d.date + "T00:00:00").toLocaleDateString("en", { day: "numeric", month: "short" })}</td>
                    <td className="py-1.5 px-2 text-right text-white font-bold">{cur(d.our_rate)}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.avg_competitor ? cur(d.avg_competitor) : "—"}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.min_competitor ? cur(d.min_competitor) : "—"}</td>
                    <td className="py-1.5 px-2 text-right text-stone-400">{d.max_competitor ? cur(d.max_competitor) : "—"}</td>
                    <td className={`py-1.5 px-2 text-right font-bold ${isAbove ? "text-red-400" : isBelow ? "text-emerald-400" : "text-stone-500"}`}>
                      {hasDiff ? `${d.diff_pct > 0 ? "+" : ""}${d.diff_pct}%` : "—"}
                    </td>
                    <td className={`py-1.5 px-2 text-right font-bold ${d.suggested_rate !== d.our_rate ? "text-amber-400" : "text-stone-500"}`}>
                      {cur(d.suggested_rate)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
