/**
 * Multi-currency Tax Reports Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Download, RefreshCw, Globe } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TaxReportsV2Panel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [scope, setScope] = useState("property");

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const url = scope === "all" ? `${API}/tax-reports/all?days=${days}` : `${API}/tax-reports/${propertyId}?days=${days}`;
      const { data } = await axios.get(url);
      setData(data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, days, scope]);

  useEffect(() => { refresh(); }, [refresh]);

  const exportCsv = async () => {
    try {
      const res = await axios.get(`${API}/tax-reports/${propertyId}/export.csv?days=${days}`, { responseType: "text" });
      const blob = new Blob([res.data], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `tax-report-${days}d.csv`; a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported");
    } catch { toast.error("Export failed"); }
  };

  const fmt = (n) => Number(n || 0).toFixed(2);

  return (
    <div className="space-y-6" data-testid="tax-reports-v2-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Tax Reports · Multi-currency</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Net / VAT / gross by currency, category, and property.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <select value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
          {[7, 14, 30, 60, 90, 180, 365].map((d) => <option key={d} value={d}>{d} days</option>)}
        </select>
        <select value={scope} onChange={(e) => setScope(e.target.value)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" data-testid="trv2-scope">
          <option value="property">This property</option>
          <option value="all">All properties (admin)</option>
        </select>
        <button onClick={refresh} className="text-sm px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh
        </button>
        <button data-testid="trv2-export-btn" onClick={exportCsv} className="text-sm px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Download className="w-3 h-3" /> CSV</button>
      </div>

      {data && (
        <>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="rounded-xl border border-stone-800 bg-stone-900/60">
              <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2"><Globe className="w-3 h-3" /> By currency</div>
              <table className="min-w-full text-xs">
                <thead><tr className="text-left text-[10px] text-stone-500"><th className="px-3 py-2">Currency</th><th className="px-3 py-2 text-right">Net</th><th className="px-3 py-2 text-right">Tax</th><th className="px-3 py-2 text-right">Gross</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_currency).map(([c, v]) => (
                    <tr key={c} className="border-t border-stone-800/60 text-stone-200" data-testid="trv2-currency-row">
                      <td className="px-3 py-1">{c}</td>
                      <td className="px-3 py-1 text-right">{fmt(v.net)}</td>
                      <td className="px-3 py-1 text-right text-amber-300">{fmt(v.tax)}</td>
                      <td className="px-3 py-1 text-right">{fmt(v.gross)}</td>
                    </tr>
                  ))}
                  {Object.keys(data.by_currency).length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">No data.</td></tr>}
                </tbody>
              </table>
            </div>

            <div className="rounded-xl border border-stone-800 bg-stone-900/60">
              <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400">By category</div>
              <table className="min-w-full text-xs">
                <thead><tr className="text-left text-[10px] text-stone-500"><th className="px-3 py-2">Category</th><th className="px-3 py-2 text-right">Rate</th><th className="px-3 py-2 text-right">Net</th><th className="px-3 py-2 text-right">Tax</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_category).map(([c, v]) => (
                    <tr key={c} className="border-t border-stone-800/60 text-stone-200" data-testid="trv2-category-row">
                      <td className="px-3 py-1">{c}</td>
                      <td className="px-3 py-1 text-right text-stone-400">{v.rate}%</td>
                      <td className="px-3 py-1 text-right">{fmt(v.net)}</td>
                      <td className="px-3 py-1 text-right text-amber-300">{fmt(v.tax)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="rounded-xl border border-stone-800 bg-stone-900/60">
              <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400">By property</div>
              <table className="min-w-full text-xs">
                <thead><tr className="text-left text-[10px] text-stone-500"><th className="px-3 py-2">Hotel</th><th className="px-3 py-2 text-right">Currency</th><th className="px-3 py-2 text-right">Net</th><th className="px-3 py-2 text-right">Tax</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_property).map(([id, v]) => (
                    <tr key={id} className="border-t border-stone-800/60 text-stone-200" data-testid="trv2-property-row">
                      <td className="px-3 py-1">{v.name}</td>
                      <td className="px-3 py-1 text-right">{v.currency}</td>
                      <td className="px-3 py-1 text-right">{fmt(v.net)}</td>
                      <td className="px-3 py-1 text-right text-amber-300">{fmt(v.tax)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="text-xs text-stone-500">{data.lines_total} lines aggregated over {data.window_days} days.</div>
        </>
      )}
    </div>
  );
}
