/**
 * Inventory Low-Stock Alerts Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Package, RefreshCw, AlertTriangle, X } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LowStockPanel({ propertyId, hotelName = "" }) {
  const [items, setItems] = useState({ items: [], count: 0, low_count: 0, ok_count: 0 });
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("items");

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: i }, { data: a }] = await Promise.all([
        axios.get(`${API}/low-stock/${propertyId}/items`),
        axios.get(`${API}/low-stock/${propertyId}/alerts?status=open`),
      ]);
      setItems(i); setAlerts(a.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const scan = async () => {
    try {
      const { data } = await axios.post(`${API}/low-stock/scan`, { property_id: propertyId });
      toast.success(`Scanned ${data.items_scanned} items, ${data.alerts_created} new alerts`);
      refresh();
    } catch { toast.error("Scan failed"); }
  };

  const dismiss = async (id) => {
    try {
      await axios.post(`${API}/low-stock/alert/${id}/dismiss`, {});
      toast.success("Dismissed");
      refresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="low-stock-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Inventory Low-Stock Alerts</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Watch every consumable across stock + POS + minibar — automatic reorder alerts.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Items tracked" value={items.count} />
        <Stat label="Low / out" value={items.low_count} highlight={items.low_count > 0} />
        <Stat label="Open alerts" value={alerts.length} highlight={alerts.length > 0} />
        <Stat label="OK" value={items.ok_count} />
      </div>

      <div className="flex gap-2">
        <button data-testid="ls-scan-btn" onClick={scan} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Scan & alert</button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh</button>
        <div className="ml-auto flex gap-1">
          {["items", "alerts"].map((t) => <button key={t} data-testid={`ls-tab-${t}`} onClick={() => setTab(t)} className={`text-xs px-3 py-1 rounded border ${tab === t ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>{t}</button>)}
        </div>
      </div>

      {tab === "items" ? (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Item</th><th className="px-3 py-2">Category</th><th className="px-3 py-2 text-right">On hand</th><th className="px-3 py-2 text-right">Threshold</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Source</th></tr>
            </thead>
            <tbody>
              {items.items.map((i) => (
                <tr key={i.id} className={`border-t border-stone-800/60 ${i.status === "out" ? "bg-rose-500/5" : i.status === "low" ? "bg-amber-500/5" : ""}`} data-testid="ls-item-row">
                  <td className="px-3 py-2 text-stone-100">{i.name || i.id}</td>
                  <td className="px-3 py-2 text-xs text-stone-400">{i.category || "—"}</td>
                  <td className="px-3 py-2 text-right">{i.qty_on_hand}</td>
                  <td className="px-3 py-2 text-right text-stone-400">{i.reorder_threshold}</td>
                  <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${i.status === "out" ? "bg-rose-500/20 border-rose-500/40 text-rose-200" : i.status === "low" ? "bg-amber-500/20 border-amber-500/40 text-amber-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>{i.status}</span></td>
                  <td className="px-3 py-2 text-[10px] text-stone-500">{i.source}</td>
                </tr>
              ))}
              {items.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500"><Package className="w-5 h-5 mx-auto mb-1 opacity-60" />No stock items found.</td></tr>}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Opened</th><th className="px-3 py-2">Item</th><th className="px-3 py-2 text-right">On hand</th><th className="px-3 py-2 text-right">Threshold</th><th className="px-3 py-2 text-right">Shortfall</th><th className="px-3 py-2">Supplier</th><th className="px-3 py-2"></th></tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id} className="border-t border-stone-800/60 text-stone-200" data-testid="ls-alert-row">
                  <td className="px-3 py-2 text-xs text-stone-400">{(a.opened_at || "").slice(0, 16)}</td>
                  <td className="px-3 py-2">{a.item_name}</td>
                  <td className="px-3 py-2 text-right">{a.qty_on_hand}</td>
                  <td className="px-3 py-2 text-right text-stone-400">{a.reorder_threshold}</td>
                  <td className="px-3 py-2 text-right text-rose-300">{a.shortfall}</td>
                  <td className="px-3 py-2 text-xs">{a.preferred_supplier || "—"}</td>
                  <td className="px-3 py-2 text-right"><button data-testid="ls-dismiss-btn" onClick={() => dismiss(a.id)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300"><X className="w-3 h-3" /></button></td>
                </tr>
              ))}
              {alerts.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-500">No open alerts.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-amber-500/10 border-amber-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-amber-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
