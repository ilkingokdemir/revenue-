import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  RefreshCw, Bell, TrendingDown, TrendingUp, Zap, AlertTriangle, Shield, Activity,
  ChevronDown, ChevronUp, Check, X, Settings2, ScanLine, ArrowRight, Eye
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const ALERT_TYPES = {
  comp_price_drop: { icon: TrendingDown, color: "text-red-400", bg: "bg-red-900/20", border: "border-red-500/30", label: "Competitor Price Drop" },
  comp_price_rise: { icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-900/20", border: "border-emerald-500/30", label: "Competitor Price Rise" },
  demand_spike: { icon: Zap, color: "text-amber-400", bg: "bg-amber-900/20", border: "border-amber-500/30", label: "Demand Spike" },
  demand_drop: { icon: Activity, color: "text-blue-400", bg: "bg-blue-900/20", border: "border-blue-500/30", label: "Demand Drop" },
  supply_compression: { icon: AlertTriangle, color: "text-violet-400", bg: "bg-violet-900/20", border: "border-violet-500/30", label: "Supply Compression" },
  rate_parity: { icon: Shield, color: "text-cyan-400", bg: "bg-cyan-900/20", border: "border-cyan-500/30", label: "Rate Parity Breach" },
};

const SEVERITY_COLORS = {
  high: "bg-red-500 text-white",
  medium: "bg-amber-500/80 text-white",
  low: "bg-stone-600 text-white",
};

const timeAgo = (iso) => {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

export const PriceAlerts = ({ propertyId, onNavigate }) => {
  const [alerts, setAlerts] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [config, setConfig] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [filter, setFilter] = useState("all");
  const [scanResult, setScanResult] = useState(null);

  const load = useCallback(async () => {
    try {
      const [alertsRes, configRes] = await Promise.all([
        axios.get(`${API}/revenue/price-alerts/${propertyId}?limit=100`),
        axios.get(`${API}/revenue/price-alerts/config/${propertyId}`),
      ]);
      setAlerts(alertsRes.data.alerts || []);
      setUnread(alertsRes.data.unread_count || 0);
      setConfig(configRes.data);
    } catch { /* silent */ }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const runScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const { data } = await axios.post(`${API}/revenue/price-alerts/scan/${propertyId}`);
      setScanResult(data);
      load();
    } catch { /* silent */ }
    setScanning(false);
  };

  const dismissAlert = async (id) => {
    try {
      await axios.put(`${API}/revenue/price-alerts/${id}/dismiss`);
      load();
    } catch { /* silent */ }
  };

  const actionAlert = async (id, action) => {
    try {
      await axios.put(`${API}/revenue/price-alerts/${id}/action`, { action });
      load();
    } catch { /* silent */ }
  };

  const saveConfig = async () => {
    if (!config) return;
    try {
      await axios.put(`${API}/revenue/price-alerts/config/${propertyId}`, config);
      setShowConfig(false);
    } catch { /* silent */ }
  };

  const filtered = filter === "all" ? alerts
    : filter === "unread" ? alerts.filter(a => !a.read)
    : alerts.filter(a => a.sub_type === filter);

  const typeCounts = {};
  alerts.forEach(a => { typeCounts[a.sub_type] = (typeCounts[a.sub_type] || 0) + 1; });

  if (loading) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Price Alerts...</div>;

  return (
    <div className="space-y-5" data-testid="price-alerts">
      {/* Header */}
      <div className="bg-stone-900 rounded-2xl p-5 text-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><Bell className="w-5 h-5 text-red-400" /></div>
            <div>
              <h2 className="text-lg font-bold flex items-center gap-2" data-testid="price-alerts-title">
                Price Intelligence Alerts
                {unread > 0 && <Badge className="bg-red-500 text-white text-[10px]">{unread} new</Badge>}
              </h2>
              <p className="text-xs text-white/40">Competitor price changes, demand shifts & market signals</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowConfig(!showConfig)} data-testid="alert-config-btn"
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white/60 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-all">
              <Settings2 className="w-3.5 h-3.5" />Rules
            </button>
            <button onClick={runScan} disabled={scanning} data-testid="scan-now-btn"
              className={`flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-lg transition-all ${scanning ? "bg-amber-600/50 text-white/60" : "bg-amber-500 hover:bg-amber-400 text-white"}`}>
              <ScanLine className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
              {scanning ? "Scanning..." : "Scan Now"}
            </button>
          </div>
        </div>

        {/* Scan Result Banner */}
        {scanResult && (
          <div className="bg-white/5 border border-white/10 rounded-xl p-3 mb-4" data-testid="scan-result">
            <p className="text-sm">
              {scanResult.generated > 0 ? (
                <span className="text-amber-400 font-bold">{scanResult.generated} new alert{scanResult.generated !== 1 ? "s" : ""} detected</span>
              ) : (
                <span className="text-emerald-400 font-bold">No new alerts — market is stable</span>
              )}
              <span className="text-white/30 ml-2">Scanned {scanResult.scanned_properties} propert{scanResult.scanned_properties !== 1 ? "ies" : "y"}, {scanResult.scan_window_days}-day window</span>
            </p>
          </div>
        )}

        {/* Summary Stats */}
        <div className="grid grid-cols-6 gap-2">
          {Object.entries(ALERT_TYPES).map(([key, type]) => {
            const count = typeCounts[key] || 0;
            const Icon = type.icon;
            return (
              <button key={key} onClick={() => setFilter(filter === key ? "all" : key)} data-testid={`alert-filter-${key}`}
                className={`rounded-xl p-3 text-center border transition-all ${filter === key ? `${type.bg} ${type.border}` : "bg-white/5 border-white/5 hover:border-white/20"}`}>
                <Icon className={`w-4 h-4 mx-auto mb-1 ${type.color}`} />
                <p className="text-lg font-black text-white">{count}</p>
                <p className="text-[8px] text-white/30 uppercase">{type.label.split(" ").slice(-1)}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Config Panel */}
      {showConfig && config && (
        <div className="bg-stone-900 border border-stone-700 rounded-2xl p-5" data-testid="alert-config-panel">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white">Alert Rules Configuration</h3>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 text-xs text-stone-400">
                <input type="checkbox" checked={config.enabled} onChange={e => setConfig({...config, enabled: e.target.checked})} className="rounded" />
                Enabled
              </label>
            </div>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { key: "comp_price_drop_pct", label: "Comp Drop %", suffix: "%" },
              { key: "comp_price_drop_abs", label: "Comp Drop £", suffix: "£" },
              { key: "comp_price_rise_pct", label: "Comp Rise %", suffix: "%" },
              { key: "comp_price_rise_abs", label: "Comp Rise £", suffix: "£" },
              { key: "demand_spike_pp", label: "Demand Spike pp", suffix: "pp" },
              { key: "demand_drop_pp", label: "Demand Drop pp", suffix: "pp" },
              { key: "supply_compression_pct", label: "Supply Compress %", suffix: "%" },
              { key: "rate_parity_diff_pct", label: "Parity Diff %", suffix: "%" },
              { key: "occupancy_threshold_high", label: "High Occ Threshold", suffix: "%" },
              { key: "occupancy_threshold_low", label: "Low Occ Threshold", suffix: "%" },
              { key: "scan_window_days", label: "Scan Window", suffix: "days" },
            ].map(rule => (
              <div key={rule.key}>
                <label className="text-[10px] text-stone-500 uppercase block mb-1">{rule.label}</label>
                <div className="flex items-center gap-1">
                  <input type="number" value={config[rule.key] || 0}
                    onChange={e => setConfig({...config, [rule.key]: Number(e.target.value)})}
                    className="w-full bg-stone-800 border border-stone-700 rounded-lg px-3 py-1.5 text-sm text-white" />
                  <span className="text-[10px] text-stone-500">{rule.suffix}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-end mt-4">
            <button onClick={saveConfig} data-testid="save-config-btn"
              className="px-4 py-2 bg-violet-500 hover:bg-violet-400 text-white text-xs font-bold rounded-lg">Save Rules</button>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 bg-stone-100 rounded-xl p-1" data-testid="alert-filter-tabs">
        {[
          { id: "all", label: `All (${alerts.length})` },
          { id: "unread", label: `Unread (${unread})` },
          ...Object.entries(ALERT_TYPES).filter(([k]) => typeCounts[k]).map(([k, v]) => ({ id: k, label: `${v.label} (${typeCounts[k]})` })),
        ].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)} data-testid={`alert-tab-${f.id}`}
            className={`px-3 py-1.5 text-[11px] font-medium rounded-lg transition-colors ${filter === f.id ? "bg-stone-800 text-white" : "text-stone-500 hover:text-stone-700"}`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Alert List */}
      <div className="space-y-3" data-testid="alert-list">
        {filtered.length === 0 ? (
          <div className="bg-stone-900 border border-stone-700 rounded-2xl p-12 text-center">
            <Bell className="w-10 h-10 text-stone-600 mx-auto mb-3" />
            <p className="text-sm font-bold text-white mb-1">No alerts yet</p>
            <p className="text-xs text-stone-500">Click "Scan Now" to check for competitor price changes, demand shifts, and market signals.</p>
          </div>
        ) : (
          filtered.map(alert => {
            const typeInfo = ALERT_TYPES[alert.sub_type] || ALERT_TYPES.comp_price_drop;
            const Icon = typeInfo.icon;
            const meta = alert.meta || {};
            const isActioned = alert.actioned;
            const isDismissed = alert.dismissed;

            return (
              <div key={alert.id} data-testid={`alert-item-${alert.id}`}
                className={`bg-stone-900 border rounded-2xl p-4 transition-all ${!alert.read ? typeInfo.border : "border-stone-700/50"} ${isDismissed ? "opacity-50" : ""}`}>
                <div className="flex items-start gap-3">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${typeInfo.bg}`}>
                    <Icon className={`w-4.5 h-4.5 ${typeInfo.color}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[9px] font-bold uppercase ${typeInfo.color}`}>{typeInfo.label}</span>
                      {alert.severity && <Badge className={`text-[8px] ${SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.low}`}>{alert.severity}</Badge>}
                      {!alert.read && <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />}
                      {isActioned && <Badge className="bg-emerald-500/20 text-emerald-400 text-[8px]">Actioned</Badge>}
                    </div>
                    <p className={`text-sm leading-snug ${!alert.read ? "font-bold text-white" : "font-medium text-stone-300"}`}>{alert.title}</p>
                    <p className="text-xs text-stone-400 mt-1 leading-relaxed">{alert.message}</p>

                    {/* Meta details */}
                    {meta && Object.keys(meta).length > 0 && (
                      <div className="flex items-center gap-3 mt-2 text-[10px]">
                        {meta.old_comp_avg && meta.new_comp_avg && (
                          <span className="text-stone-500">Comp avg: {cur(meta.old_comp_avg)} → {cur(meta.new_comp_avg)}</span>
                        )}
                        {meta.our_rate && <span className="text-stone-500">Your rate: {cur(meta.our_rate)}</span>}
                        {meta.change_pct && <span className={meta.change_pct > 0 ? "text-emerald-400" : "text-red-400"}>{meta.change_pct > 0 ? "+" : ""}{meta.change_pct}%</span>}
                        {meta.old_demand !== undefined && meta.new_demand !== undefined && (
                          <span className="text-stone-500">Demand: {meta.old_demand}% → {meta.new_demand}%</span>
                        )}
                        {meta.diff_pct && <span className={meta.direction === "above" ? "text-red-400" : "text-emerald-400"}>{meta.diff_pct > 0 ? "+" : ""}{meta.diff_pct}% vs market</span>}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2 mt-3">
                      <span className="text-[10px] text-stone-500">{timeAgo(alert.created_at)}</span>
                      {!isActioned && !isDismissed && (
                        <>
                          {alert.link_to && onNavigate && (
                            <button onClick={() => { actionAlert(alert.id, "viewed"); onNavigate(alert.link_to); }} data-testid={`alert-view-${alert.id}`}
                              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-cyan-400 hover:text-cyan-300 bg-cyan-900/20 rounded-md">
                              <Eye className="w-3 h-3" />View
                            </button>
                          )}
                          <button onClick={() => actionAlert(alert.id, "adjust_rate")} data-testid={`alert-adjust-${alert.id}`}
                            className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-amber-400 hover:text-amber-300 bg-amber-900/20 rounded-md">
                            <ArrowRight className="w-3 h-3" />Adjust Rate
                          </button>
                          <button onClick={() => actionAlert(alert.id, "acknowledged")} data-testid={`alert-ack-${alert.id}`}
                            className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-900/20 rounded-md">
                            <Check className="w-3 h-3" />Acknowledge
                          </button>
                          <button onClick={() => dismissAlert(alert.id)} data-testid={`alert-dismiss-${alert.id}`}
                            className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-stone-500 hover:text-stone-400 bg-stone-800 rounded-md">
                            <X className="w-3 h-3" />Dismiss
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
