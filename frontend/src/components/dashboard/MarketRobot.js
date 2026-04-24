import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useTranslation } from "@/i18n";
import { Bot, Play, RefreshCw, TrendingUp, TrendingDown, Zap, AlertTriangle, CheckCircle, Settings, Activity, Clock, ArrowUpRight, ArrowDownRight, Eye, Trash2, MapPin, Globe, Radar, PartyPopper, Users } from "lucide-react";
import { EventIntelligence } from "./EventIntelligence";
import { RateParity } from "./RateParity";
import { CompetitorAnalysis } from "./CompetitorAnalysis";
import { PerformanceReport } from "./PerformanceReport";
import { MarketDemandDashboard } from "./MarketDemandDashboard";
import { DemandRadar } from "./DemandRadar";
import NeighborhoodScanPanel from "./NeighborhoodScanPanel";
import MarketRobotHealthWidget from "./MarketRobotHealthWidget";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIERS_DISPLAY = [
  { label: "Today + Tomorrow", interval_mins: 30 },
  { label: "Next 3-7 days", interval_mins: 60 },
  { label: "1-2 weeks out", interval_mins: 180 },
  { label: "2-4 weeks out", interval_mins: 360 },
  { label: "1-3 months out", interval_mins: 720 },
  { label: "3-6 months out", interval_mins: 1440 },
  { label: "6-12 months out", interval_mins: 2880 },
];

export const MarketRobot = ({ propertyId }) => {
  const { t } = useTranslation();
  const [config, setConfig] = useState(null);
  const [supply, setSupply] = useState(null);
  const [logs, setLogs] = useState([]);
  const [adjustments, setAdjustments] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [subTab, setSubTab] = useState("dashboard");
  const [competitors, setCompetitors] = useState([]);
  const [compForm, setCompForm] = useState({ name: "", booking_url: "" });
  const [compScanning, setCompScanning] = useState(false);
  const [scannerStatus, setScannerStatus] = useState(null);

  useEffect(() => {
    loadAll();
    const interval = setInterval(() => {
      axios.get(`${API}/revenue/market-robot/${propertyId}/scanner/status`).then(r => setScannerStatus(r.data)).catch(() => {});
    }, 15000);
    return () => clearInterval(interval);
  }, [propertyId]);

  // Listen to cross-tab navigation events (e.g. "Add Competitor" CTA from Analysis tab)
  useEffect(() => {
    const onGoto = (e) => { if (e?.detail?.tab) setSubTab(e.detail.tab); };
    window.addEventListener("market-robot-goto", onGoto);
    return () => window.removeEventListener("market-robot-goto", onGoto);
  }, []);

  const loadAll = () => {
    axios.get(`${API}/revenue/market-robot/${propertyId}/config`).then(r => setConfig(r.data)).catch(() => {});
    axios.get(`${API}/revenue/market-robot/${propertyId}/supply`).then(r => setSupply(r.data)).catch(() => {});
    axios.get(`${API}/revenue/market-robot/${propertyId}/logs`).then(r => setLogs(r.data.logs || [])).catch(() => {});
    axios.get(`${API}/revenue/market-robot/${propertyId}/adjustments`).then(r => setAdjustments(r.data.adjustments || [])).catch(() => {});
    axios.get(`${API}/revenue/market-robot/${propertyId}/competitors`).then(r => setCompetitors(r.data.competitors || [])).catch(() => {});
    axios.get(`${API}/revenue/market-robot/${propertyId}/scanner/status`).then(r => setScannerStatus(r.data)).catch(() => {});
  };

  const toggleScanner = async () => {
    const action = scannerStatus?.running ? "stop" : "start";
    try {
      await axios.post(`${API}/revenue/market-robot/${propertyId}/scanner/${action}`);
      toast.success(action === "start" ? "Smart Scanner activated! Auto-scanning & re-pricing started." : "Scanner stopped");
      setTimeout(() => axios.get(`${API}/revenue/market-robot/${propertyId}/scanner/status`).then(r => setScannerStatus(r.data)).catch(() => {}), 2000);
    } catch { toast.error("Failed"); }
  };

  const saveConfig = async (updates) => {
    try {
      const merged = { ...config, ...updates };
      await axios.put(`${API}/revenue/market-robot/${propertyId}/config`, merged);
      setConfig(merged);
      toast.success("Configuration saved");
    } catch { toast.error("Failed"); }
  };

  const runScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/scan`, {
        city: config?.city || "London",
        days_ahead: config?.days_ahead || 14,
      });
      setScanResult(data);
      toast.success(`Scan complete: ${data.dates_scanned} dates scanned, ${data.auto_adjustments?.length || 0} prices adjusted`);
      loadAll();
    } catch (e) {
      toast.error("Scan failed");
    }
    setScanning(false);
  };

  const addCompetitor = async () => {
    if (!compForm.booking_url) { toast.error("Booking.com URL required"); return; }
    try {
      await axios.post(`${API}/revenue/market-robot/${propertyId}/competitors`, compForm);
      toast.success("Competitor added");
      setCompForm({ name: "", booking_url: "" });
      loadAll();
    } catch { toast.error("Failed"); }
  };

  const removeCompetitor = async (id) => {
    try {
      await axios.delete(`${API}/revenue/market-robot/competitors/${id}`);
      toast.success("Removed");
      loadAll();
    } catch { toast.error("Failed"); }
  };

  const scanCompetitors = async () => {
    setCompScanning(true);
    try {
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/competitors/scan`, { days_ahead: 7 });
      toast.success(`Scanned ${data.total_competitors} competitors`);
      loadAll();
    } catch { toast.error("Failed"); }
    setCompScanning(false);
  };

  const snapshots = supply?.snapshots || [];
  // Currency inferred from the active scan city
  const currency = useMemo(() => makeCurrencyFormatter(config?.currency || config?.city || ""), [config]);
  const cur = (v) => currency.format(v, 2);
  const curShort = currency.short;
  const summary = supply?.summary || {};
  const upcomingEvents = supply?.upcoming_events || [];

  const demandKey = summary.avg_unavailable_pct >= 70 ? "mr.kpi.demand_high" : summary.avg_unavailable_pct >= 40 ? "mr.kpi.demand_moderate" : "mr.kpi.demand_low";
  const demandLevel = t(demandKey);
  const demandColor = demandKey === "mr.kpi.demand_high" ? "text-emerald-600" : demandKey === "mr.kpi.demand_moderate" ? "text-amber-500" : "text-red-500";

  return (
    <div className="space-y-4 md:space-y-6" data-testid="market-robot">
      {/* Header — stacks on mobile, row on desktop */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 bg-gradient-to-br from-indigo-600 to-violet-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-stone-800">{t("mr.title")}</h2>
            <p className="text-xs text-stone-400 truncate">{t("mr.subtitle")}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 md:gap-3 flex-wrap">
          {/* Location Badge */}
          <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-xl px-3 py-2 flex-1 sm:flex-none min-w-[180px]">
            <MapPin className="w-4 h-4 text-violet-500 flex-shrink-0" />
            <input
              value={config?.city || ""}
              onChange={e => setConfig(p => ({ ...p, city: e.target.value }))}
              onBlur={() => config?.city && saveConfig({ city: config.city })}
              onKeyDown={e => e.key === "Enter" && config?.city && saveConfig({ city: config.city })}
              className="text-sm font-semibold text-stone-800 w-full sm:w-32 bg-transparent outline-none"
              placeholder={t("mr.city_placeholder")}
              data-testid="market-robot-city-quick"
            />
          </div>
          {config?.enabled && <Badge className="bg-emerald-100 text-emerald-700 text-xs"><span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 inline-block animate-pulse" />{t("mr.active")}</Badge>}
          <button onClick={runScan} disabled={scanning}
            className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 sm:px-5 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50 transition-all flex-1 sm:flex-none" data-testid="market-robot-scan">
            {scanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            <span className="whitespace-nowrap">{scanning ? t("mr.scanning") : t("mr.run_scan")}</span>
          </button>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 border-b border-stone-200 overflow-x-auto">
        {[
          {id:"dashboard",labelKey:"mr.sub.dashboard"},
          {id:"radar",labelKey:"mr.sub.radar"},
          {id:"neighborhood",labelKey:"mr.sub.neighborhood"},
          {id:"demand",labelKey:"mr.sub.demand"},
          {id:"performance",labelKey:"mr.sub.performance"},
          {id:"supply",labelKey:"mr.sub.supply"},
          {id:"parity",labelKey:"mr.sub.parity"},
          {id:"analysis",labelKey:"mr.sub.analysis"},
          {id:"events",labelKey:"mr.sub.events"},
          {id:"competitors-tab",labelKey:"mr.sub.competitors"},
          {id:"adjustments",labelKey:"mr.sub.adjustments"},
          {id:"config",labelKey:"mr.sub.config"},
          {id:"logs",labelKey:"mr.sub.logs"},
        ].map(tab => (
          <button key={tab.id} onClick={() => setSubTab(tab.id)} className={`whitespace-nowrap px-4 py-2.5 text-sm font-medium border-b-2 -mb-[1px] transition-all ${subTab === tab.id ? "text-indigo-700 border-indigo-500" : "text-stone-400 border-transparent hover:text-stone-600"}`} data-testid={`market-robot-${tab.id}`}>{t(tab.labelKey)}</button>
        ))}
      </div>

      {/* Dashboard */}
      {subTab === "dashboard" && (
        <div className="space-y-6">
          {/* Cross-Branch Scanner Health */}
          <MarketRobotHealthWidget />

          {/* Scan Result Banner */}
          {scanResult && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4" data-testid="market-robot-result">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-indigo-600" />
                <span className="font-bold text-indigo-800">{t("mr.scan_complete")}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 text-sm">
                <div><span className="text-indigo-500">{t("mr.dates_scanned")}:</span> <strong>{scanResult.dates_scanned}</strong></div>
                <div><span className="text-indigo-500">{t("mr.auto_adjustments")}:</span> <strong>{scanResult.auto_adjustments?.length || 0}</strong></div>
                <div><span className="text-indigo-500">{t("mr.city")}:</span> <strong>{scanResult.city}</strong></div>
              </div>
            </div>
          )}

          {/* Smart Scanner Control Panel */}
          <div className={`border rounded-2xl p-4 sm:p-5 ${scannerStatus?.running ? "bg-emerald-50 border-emerald-200" : "bg-white border-stone-200"}`} data-testid="smart-scanner-panel">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
              <div className="flex items-start gap-3 min-w-0">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${scannerStatus?.running ? "bg-emerald-500" : "bg-stone-200"}`}>
                  <Activity className={`w-5 h-5 ${scannerStatus?.running ? "text-white animate-pulse" : "text-stone-400"}`} />
                </div>
                <div className="min-w-0">
                  <h3 className="font-bold text-stone-800">{t("mr.smart_scanner")}</h3>
                  <p className="text-xs text-stone-400">
                    {scannerStatus?.running ? t("mr.smart_scanner_on") : t("mr.smart_scanner_off")}
                  </p>
                </div>
              </div>
              <button onClick={toggleScanner}
                className={`flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all flex-shrink-0 ${
                  scannerStatus?.running
                    ? "bg-red-500 hover:bg-red-600 text-white"
                    : "bg-emerald-500 hover:bg-emerald-600 text-white"
                }`} data-testid="smart-scanner-toggle">
                {scannerStatus?.running ? <><AlertTriangle className="w-4 h-4" />{t("mr.stop_scanner")}</> : <><Play className="w-4 h-4" />{t("mr.activate_scanner")}</>}
              </button>
            </div>
            {/* Tier Schedule — horizontal scroll on mobile, 7-col grid on desktop */}
            <div className="flex sm:grid sm:grid-cols-7 gap-2 overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0 pb-1 sm:pb-0 snap-x snap-mandatory sm:snap-none">
              {(scannerStatus?.tiers || TIERS_DISPLAY).map((tier, i) => {
                const ts = scannerStatus?.stats?.tier_status?.[tier.label] || {};
                const nextScan = ts.next_scan ? new Date(ts.next_scan) : null;
                const isOverdue = nextScan && nextScan < new Date();
                return (
                  <div key={i} className={`rounded-xl p-3 text-center text-xs border flex-shrink-0 w-[120px] sm:w-auto snap-start ${
                    scannerStatus?.running && ts.last_scan ? "bg-emerald-50 border-emerald-200" : "bg-stone-50 border-stone-200"
                  }`}>
                    <p className="font-bold text-stone-700 text-[10px]">{tier.label}</p>
                    <p className="text-stone-400 mt-0.5">Every {tier.interval_mins >= 60 ? `${tier.interval_mins / 60}h` : `${tier.interval_mins}m`}</p>
                    {scannerStatus?.running && ts.last_scan && (
                      <p className="text-[9px] text-emerald-600 mt-1 font-medium">
                        {isOverdue ? "Scanning..." : `Next: ${nextScan?.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            {scannerStatus?.running && scannerStatus?.stats && (
              <div className="flex items-center gap-6 mt-3 text-xs text-stone-500 border-t border-stone-200 pt-3 flex-wrap">
                <span>{t("mr.scans_today")}: <strong className="text-stone-700">{scannerStatus.stats.total_scans_today}</strong></span>
                <span>{t("mr.requests_today")}: <strong className="text-stone-700">{scannerStatus.stats.total_requests_today}</strong></span>
                <span>{t("mr.events_today")}: <strong className="text-red-500">{scannerStatus.stats.events_found_today || 0}</strong></span>
                {scannerStatus.stats.last_event_scan && <span>{t("mr.last_event_scan")}: <strong className="text-red-500">{new Date(scannerStatus.stats.last_event_scan).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</strong></span>}
                {scannerStatus.stats.last_reprice_time && <span>{t("mr.last_reprice")}: <strong className="text-emerald-600">{new Date(scannerStatus.stats.last_reprice_time).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</strong></span>}
              </div>
            )}
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="market-robot-kpis">
            <div className="bg-white border border-stone-200 rounded-2xl p-5">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">{t("mr.kpi.market_demand")}</p>
              <p className={`text-2xl font-bold mt-1 ${demandColor}`}>{demandLevel}</p>
              <p className="text-xs text-stone-400 mt-1">{summary.avg_unavailable_pct || 0}% {t("mr.kpi.unavailability_suffix")}</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl p-5">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">{t("mr.kpi.high_demand_days")}</p>
              <p className="text-2xl font-bold text-emerald-600 mt-1">{summary.high_demand_days || 0}</p>
              <p className="text-xs text-stone-400 mt-1">{t("mr.kpi.high_demand_hint")}</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl p-5">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">{t("mr.kpi.low_demand_days")}</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{summary.low_demand_days || 0}</p>
              <p className="text-xs text-stone-400 mt-1">{t("mr.kpi.oversupply_hint")}</p>
            </div>
            <div className="bg-white border border-red-100 rounded-2xl p-5">
              <p className="text-[10px] text-red-500 uppercase tracking-wider font-medium">{t("mr.kpi.event_days")}</p>
              <p className="text-2xl font-bold text-red-500 mt-1">{summary.event_days || 0}</p>
              <p className="text-xs text-stone-400 mt-1">{t("mr.kpi.events_hint")}</p>
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl p-5">
              <p className="text-[10px] text-stone-400 uppercase tracking-wider font-medium">{t("mr.kpi.active_adjustments")}</p>
              <p className="text-2xl font-bold text-indigo-600 mt-1">{adjustments.length}</p>
              <p className="text-xs text-stone-400 mt-1">{t("mr.kpi.adjustments_hint")}</p>
            </div>
          </div>

          {/* Upcoming Events Awareness */}
          {upcomingEvents.length > 0 && (
            <div className="bg-gradient-to-r from-red-50 to-orange-50 border border-red-200 rounded-2xl p-5" data-testid="market-robot-events-awareness">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <PartyPopper className="w-5 h-5 text-red-500" />
                  <h3 className="font-bold text-red-800">Robot Event Awareness</h3>
                  <Badge className="bg-red-100 text-red-700 text-[10px]">{upcomingEvents.length} upcoming</Badge>
                </div>
                <p className="text-[10px] text-red-400">Events auto-boost pricing via AI Dynamic Pricing & Smart Pricing</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {upcomingEvents.slice(0, 6).map((ev, i) => (
                  <div key={i} className={`flex items-center gap-2 rounded-xl px-3 py-2 border ${
                    ev.impact === "mega" ? "bg-red-100/50 border-red-200" : ev.impact === "large" ? "bg-orange-100/50 border-orange-200" : "bg-amber-100/50 border-amber-200"
                  }`}>
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      ev.impact === "mega" ? "bg-red-500" : ev.impact === "large" ? "bg-orange-500" : "bg-amber-400"
                    }`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-stone-800 truncate">{ev.name}</p>
                      <div className="flex items-center gap-2 text-[10px] text-stone-500">
                        <span>{new Date(ev.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })}</span>
                        {ev.estimated_attendance > 0 && <span className="flex items-center gap-0.5"><Users className="w-2.5 h-2.5" />{ev.estimated_attendance.toLocaleString()}</span>}
                      </div>
                    </div>
                    <Badge className={`text-[8px] flex-shrink-0 ${
                      ev.impact === "mega" ? "bg-red-500 text-white" : ev.impact === "large" ? "bg-orange-500 text-white" : "bg-amber-400 text-white"
                    }`}>{ev.impact?.toUpperCase()}</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Supply Trend Chart */}
          {snapshots.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="market-robot-chart">
              <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                <h3 className="font-bold text-stone-800">Market Supply Trend (Unavailability %)</h3>
                <div className="flex items-center gap-3 text-[10px] text-stone-500">
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-red-500 inline-block" /> High (70%+)</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-amber-400 inline-block" /> Moderate</span>
                  <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-emerald-400 inline-block" /> Low</span>
                  <span className="flex items-center gap-1 pl-2 border-l border-stone-300">
                    <span className="w-3 h-0.5 bg-cyan-500 inline-block" />
                    <span className="font-semibold text-cyan-700">BİZ · Doluluk</span>
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                {snapshots.slice(0, 20).map(s => {
                  const u = s.unavailable_pct;
                  const color = u >= 70 ? "bg-red-500" : u >= 40 ? "bg-amber-400" : "bg-emerald-400";
                  const adj = s.price_adjustment_pct || 0;
                  const hasEvent = s.event;
                  const ourOcc = s.our_occupancy_pct;
                  const ourRate = s.our_avg_rate;
                  return (
                    <div key={s.date} className="flex items-center gap-3 group">
                      <span className="w-20 text-xs text-stone-500 font-medium flex-shrink-0">{new Date(s.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric", weekday: "short" })}</span>
                      <div className="flex-1 bg-stone-100 rounded-full h-5 overflow-hidden relative">
                        <div className={`h-5 rounded-full transition-all ${color}`} style={{ width: `${u}%` }} />
                        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white mix-blend-difference">{u}%</span>
                        {ourOcc != null && (
                          <div
                            className="absolute top-0 bottom-0 w-0.5 bg-cyan-500 shadow-lg"
                            style={{ left: `${ourOcc}%` }}
                            title={`BİZ: ${ourOcc}% doluluk`}
                          />
                        )}
                      </div>
                      {ourOcc != null && (
                        <span className="w-12 text-right text-[10px] font-bold text-cyan-700 tabular-nums flex-shrink-0">
                          {ourOcc}%
                        </span>
                      )}
                      {ourRate > 0 && (
                        <span className="w-14 text-right text-[10px] font-bold text-violet-700 tabular-nums flex-shrink-0">
                          {curShort(ourRate)}
                        </span>
                      )}
                      {hasEvent ? (
                        <div className="w-24 text-right flex items-center justify-end gap-1" title={s.event}>
                          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                            s.event_impact === "mega" ? "bg-red-500 text-white" : s.event_impact === "large" ? "bg-orange-500 text-white" : "bg-amber-400 text-white"
                          }`}>{s.event_impact?.toUpperCase()}</span>
                          <span className="text-[10px] font-bold text-red-500">+{s.event_boost}%</span>
                        </div>
                      ) : (
                        <div className={`w-16 text-right text-xs font-bold ${adj > 0 ? "text-emerald-600" : adj < 0 ? "text-red-500" : "text-stone-400"}`}>
                          {adj > 0 ? <span className="flex items-center justify-end gap-0.5"><ArrowUpRight className="w-3 h-3" />+{adj}%</span> :
                           adj < 0 ? <span className="flex items-center justify-end gap-0.5"><ArrowDownRight className="w-3 h-3" />{adj}%</span> :
                           "0%"}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {snapshots.length === 0 && (
            <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
              <Bot className="w-16 h-16 text-stone-200 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-stone-600 mb-2">No Market Data Yet</h3>
              <p className="text-sm text-stone-400 mb-4">Click "Run Scan Now" to scrape Booking.com and analyze market supply for your city.</p>
              <button onClick={runScan} disabled={scanning} className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-xl text-sm font-semibold" data-testid="market-robot-scan-empty">
                {scanning ? "Scanning..." : "Start First Scan"}
              </button>
            </div>
          )}

          {/* How it works */}
          <div className="bg-stone-800 rounded-2xl p-6 text-white">
            <h3 className="font-bold text-lg mb-4 flex items-center gap-2"><Zap className="w-5 h-5 text-amber-400" /> How Market Robot Works</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[
                { step: 1, title: "Scrape Market Supply", desc: "Scans Booking.com for your city to see how many properties are available for each date in the next 90 days." },
                { step: 2, title: "Scan Events (GPT-5.2)", desc: "Every 6 hours, AI detects concerts, matches, exhibitions, festivals with 1,000+ attendees and auto-classifies impact." },
                { step: 3, title: "Detect Demand Changes", desc: "If availability drops (more sold out), demand is rising. Events create demand spikes. If supply increases, demand is falling." },
                { step: 4, title: "Auto-Adjust Prices", desc: "Automatically reprices using ALL 10 factors: supply, events, competitors, historical floors, seasonality & more." },
              ].map(s => (
                <div key={s.step} className="bg-stone-700/50 rounded-xl p-4">
                  <div className="w-8 h-8 rounded-full bg-indigo-500 text-white flex items-center justify-center text-sm font-bold mb-3">{s.step}</div>
                  <p className="font-semibold text-sm">{s.title}</p>
                  <p className="text-xs text-stone-300 mt-1">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Supply Data Tab */}
      {subTab === "supply" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="market-robot-supply-table">
          <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Supply Snapshots</div>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="border-b bg-stone-50/50">
              {["Date","Total Properties","Unavailable %","Available %","Available Est","Event","Price Adj","Reason"].map(h =>
                <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
              )}
            </tr></thead>
            <tbody>{snapshots.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-12 text-stone-400">No data. Run a scan first.</td></tr>
            ) : snapshots.map(s => (
              <tr key={s.date} className={`border-b border-stone-50 ${s.event ? "bg-red-50/20" : ""}`}>
                <td className="px-3 py-2 font-medium text-stone-700">{s.date}</td>
                <td className="px-3 py-2 text-center">{s.total_properties?.toLocaleString() || 0}</td>
                <td className="px-3 py-2 text-center"><span className={`font-semibold ${s.unavailable_pct >= 70 ? "text-red-500" : s.unavailable_pct >= 40 ? "text-amber-500" : "text-emerald-600"}`}>{s.unavailable_pct}%</span></td>
                <td className="px-3 py-2 text-center">{s.available_pct}%</td>
                <td className="px-3 py-2 text-center">{s.available_est?.toLocaleString() || 0}</td>
                <td className="px-3 py-2 text-center">
                  {s.event ? (
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      s.event_impact === "mega" ? "bg-red-500 text-white" : s.event_impact === "large" ? "bg-orange-500 text-white" : "bg-amber-400 text-white"
                    }`} title={s.event}>{s.event_impact?.toUpperCase()} +{s.event_boost}%</span>
                  ) : <span className="text-[10px] text-stone-300">—</span>}
                </td>
                <td className="px-3 py-2 text-center"><span className={`font-bold ${(s.price_adjustment_pct || 0) > 0 ? "text-emerald-600" : (s.price_adjustment_pct || 0) < 0 ? "text-red-500" : "text-stone-400"}`}>{(s.price_adjustment_pct || 0) > 0 ? "+" : ""}{s.price_adjustment_pct || 0}%</span></td>
                <td className="px-3 py-2 text-xs text-stone-500 max-w-[200px] truncate">{s.reason}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}

      {/* Auto-Adjustments Tab */}
      {subTab === "adjustments" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="market-robot-adjustments">
          <div className="px-5 py-3 bg-stone-50 border-b flex items-center justify-between">
            <span className="font-bold text-sm text-stone-800">Rate Adjustments by Market Robot</span>
            <Badge className="bg-indigo-100 text-indigo-700 text-xs">{adjustments.length} active</Badge>
          </div>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="border-b bg-stone-50/50">
              {["Date","Room Type","New Rate","Set By","Reason","Updated"].map(h =>
                <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
              )}
            </tr></thead>
            <tbody>{adjustments.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-stone-400">No auto-adjustments yet. Run a scan to generate.</td></tr>
            ) : adjustments.map((a, i) => (
              <tr key={i} className="border-b border-stone-50">
                <td className="px-3 py-2 font-medium text-stone-700">{a.date}</td>
                <td className="px-3 py-2 text-center text-stone-600">{a.room_type_id || "All"}</td>
                <td className="px-3 py-2 text-center font-bold text-indigo-700">{cur(a.custom_rate)}</td>
                <td className="px-3 py-2 text-center"><Badge className="bg-indigo-100 text-indigo-700 text-[10px]">market-robot</Badge></td>
                <td className="px-3 py-2 text-xs text-stone-500 max-w-[200px] truncate">{a.reason}</td>
                <td className="px-3 py-2 text-xs text-stone-400">{a.updated_at ? new Date(a.updated_at).toLocaleString("en-GB", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}


      {/* Market Demand Tab */}
      {subTab === "demand" && <MarketDemandDashboard propertyId={propertyId} />}
      {subTab === "radar" && <DemandRadar propertyId={propertyId} />}
      {subTab === "neighborhood" && <NeighborhoodScanPanel propertyId={propertyId} />}

      {/* Performance Report Tab */}
      {subTab === "performance" && <PerformanceReport propertyId={propertyId} />}

      {/* Rate Parity Tab */}
      {subTab === "parity" && <RateParity propertyId={propertyId} />}

      {/* Competitor Analysis Tab */}
      {subTab === "analysis" && <CompetitorAnalysis propertyId={propertyId} />}

      {/* Event Intelligence Tab */}
      {subTab === "events" && <EventIntelligence propertyId={propertyId} />}


      {/* Competitor Hotels Tab */}
      {subTab === "competitors-tab" && (
        <div className="space-y-6" data-testid="market-robot-competitors">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-stone-800">Competitor Hotels</h3>
              <p className="text-sm text-stone-400">Add Booking.com hotel URLs to track their prices and availability.</p>
            </div>
            <button onClick={scanCompetitors} disabled={compScanning || competitors.length === 0}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-medium disabled:opacity-50" data-testid="market-robot-scan-comps">
              {compScanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
              {compScanning ? "Scanning..." : "Scan All Prices"}
            </button>
          </div>

          {/* Add Competitor Form */}
          <div className="bg-white border border-stone-200 rounded-2xl p-5">
            <h4 className="font-semibold text-stone-700 mb-3">Add Competitor Hotel</h4>
            <div className="flex gap-3">
              <input value={compForm.name} onChange={e => setCompForm(p => ({ ...p, name: e.target.value }))}
                placeholder="Hotel name (optional)" className="border border-stone-200 rounded-lg px-3 py-2 text-sm w-48" data-testid="comp-name" />
              <input value={compForm.booking_url} onChange={e => setCompForm(p => ({ ...p, booking_url: e.target.value }))}
                placeholder="Booking.com hotel URL (paste full URL)" className="border border-stone-200 rounded-lg px-3 py-2 text-sm flex-1" data-testid="comp-url" />
              <button onClick={addCompetitor}
                className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2 rounded-lg text-sm font-semibold whitespace-nowrap" data-testid="comp-add">+ Add</button>
            </div>
            <p className="text-[10px] text-stone-400 mt-2">Example: https://www.booking.com/hotel/gb/the-barkston.html</p>
          </div>

          {/* Competitor List */}
          {competitors.length === 0 ? (
            <div className="bg-white border border-stone-200 rounded-2xl p-12 text-center">
              <Eye className="w-12 h-12 text-stone-200 mx-auto mb-3" />
              <p className="font-semibold text-stone-600">No competitors added yet</p>
              <p className="text-sm text-stone-400 mt-1">Paste a Booking.com hotel URL above to start tracking.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {competitors.map(comp => (
                <div key={comp.id} className="bg-white border border-stone-200 rounded-2xl p-5" data-testid={`comp-${comp.id}`}>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h4 className="font-bold text-stone-800">{comp.name}</h4>
                      <p className="text-xs text-stone-400 truncate max-w-md">{comp.booking_url}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {comp.last_scraped && <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Last scan: {new Date(comp.last_scraped).toLocaleString("en-GB", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</Badge>}
                      <button onClick={() => removeCompetitor(comp.id)} className="text-red-400 hover:text-red-600 p-1"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </div>
                  {comp.prices && comp.prices.length > 0 ? (
                    <div className="overflow-x-auto">
                      <div className="flex gap-2">
                        {comp.prices.map(p => (
                          <div key={p.date} className={`flex-shrink-0 text-center border rounded-xl p-3 min-w-[80px] ${p.scraped ? "border-stone-200" : "border-stone-100 bg-stone-50"}`}>
                            <div className="text-[10px] text-stone-400 font-medium">{new Date(p.date + "T00:00:00").toLocaleDateString("en", { weekday: "short", day: "numeric" })}</div>
                            {p.scraped && p.lowest_price ? (
                              <div className="text-sm font-bold text-stone-800 mt-1">{cur(p.lowest_price)}</div>
                            ) : (
                              <div className="text-sm font-bold text-stone-300 mt-1">—</div>
                            )}
                            {p.score && <div className="text-[9px] text-amber-500 mt-0.5">{p.score}</div>}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-stone-400">No prices scraped yet. Click "Scan All Prices" to fetch.</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Configuration Tab */}
      {subTab === "config" && config && (
        <div className="space-y-4" data-testid="market-robot-config">
          <div className="bg-white border border-stone-200 rounded-2xl p-6">
            <h3 className="font-bold text-stone-800 mb-4 flex items-center gap-2"><Settings className="w-4 h-4 text-stone-400" /> Robot Configuration</h3>
            <div className="space-y-5">
              <div className="flex items-center justify-between border border-stone-200 rounded-xl p-4">
                <div><label className="font-semibold text-stone-700 text-sm">Enable Market Robot</label><p className="text-xs text-stone-400">Activate automatic market scanning</p></div>
                <Switch checked={config.enabled} onCheckedChange={v => saveConfig({ enabled: v })} data-testid="market-robot-enable" />
              </div>
              <div className="flex items-center justify-between border border-stone-200 rounded-xl p-4">
                <div><label className="font-semibold text-stone-700 text-sm">Auto-Pricing</label><p className="text-xs text-stone-400">Automatically adjust rates based on market supply</p></div>
                <Switch checked={config.auto_pricing} onCheckedChange={v => saveConfig({ auto_pricing: v })} data-testid="market-robot-autopricing" />
              </div>

              {/* Location / City */}
              <div className="border border-violet-200 rounded-xl p-5 bg-violet-50/30">
                <div className="flex items-center gap-2 mb-3">
                  <Globe className="w-5 h-5 text-violet-600" />
                  <label className="font-bold text-stone-800 text-sm">Market Location</label>
                </div>
                <p className="text-xs text-stone-500 mb-3">Set the city or destination to monitor on Booking.com. This works for any location worldwide.</p>
                <Input value={config.city || ""} onChange={e => setConfig(p => ({ ...p, city: e.target.value }))} onBlur={() => saveConfig({ city: config.city })} className="w-80 mb-3" placeholder="Type any city name..." data-testid="market-robot-city" />
                <div className="flex flex-wrap gap-1.5">
                  {["London","Paris","New York","Dubai","Barcelona","Rome","Tokyo","Sydney","Amsterdam","Istanbul","Bangkok","Singapore","Berlin","Miami","Los Angeles","Hong Kong","Lisbon","Prague","Vienna","Bali","Zurich","Geneva","Munich","Milan","Edinburgh","Madrid","Athens","Marrakech","Cancun","Maldives"].map(city => (
                    <button key={city} onClick={() => { setConfig(p => ({ ...p, city })); saveConfig({ city }); }}
                      className={`px-2.5 py-1 text-[11px] font-medium rounded-lg transition-all ${config.city === city ? "bg-violet-600 text-white" : "bg-white border border-stone-200 text-stone-500 hover:border-violet-300 hover:text-violet-700"}`}
                      data-testid={`market-city-${city.toLowerCase().replace(/\s/g, "-")}`}>
                      {city}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-stone-400 mt-2">You can type any destination — these are popular presets. The robot will scrape Booking.com for the exact location you enter.</p>
              </div>

              <div>
                <label className="font-semibold text-stone-700 text-sm block mb-2">Days Ahead to Scan</label>
                <p className="text-xs text-stone-400 mb-2">Number of days into the future to scan. Max 90 for full quarter coverage.</p>
                <Input type="number" min={7} max={90} value={config.days_ahead || 90} onChange={e => setConfig(p => ({ ...p, days_ahead: Number(e.target.value) }))} onBlur={() => saveConfig({ days_ahead: config.days_ahead })} className="w-32" data-testid="market-robot-days" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="font-semibold text-stone-700 text-sm block mb-2">Max Price Increase %</label>
                  <Input type="number" value={config.max_increase_pct || 35} onChange={e => setConfig(p => ({ ...p, max_increase_pct: Number(e.target.value) }))} onBlur={() => saveConfig({ max_increase_pct: config.max_increase_pct })} className="w-24" />
                </div>
                <div>
                  <label className="font-semibold text-stone-700 text-sm block mb-2">Max Price Decrease %</label>
                  <Input type="number" value={config.max_decrease_pct || 25} onChange={e => setConfig(p => ({ ...p, max_decrease_pct: Number(e.target.value) }))} onBlur={() => saveConfig({ max_decrease_pct: config.max_decrease_pct })} className="w-24" />
                </div>
              </div>
            </div>
          </div>

          {/* Currency Configuration */}
          <div className="bg-white border border-stone-200 rounded-2xl p-6">
            <h3 className="font-bold text-stone-800 mb-3 flex items-center gap-2"><Globe className="w-4 h-4 text-stone-400" /> Regional Settings</h3>
            <p className="text-xs text-stone-400 mb-4">These settings adapt the robot for different markets worldwide.</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="font-semibold text-stone-700 text-sm block mb-2">Currency</label>
                <select value={config.currency || "GBP"} onChange={e => { setConfig(p => ({ ...p, currency: e.target.value })); saveConfig({ currency: e.target.value }); }}
                  className="border border-stone-200 rounded-lg px-3 py-2 text-sm w-full" data-testid="market-robot-currency">
                  {[["GBP","£ British Pound"],["USD","$ US Dollar"],["EUR","€ Euro"],["AED","د.إ UAE Dirham"],["THB","฿ Thai Baht"],["JPY","¥ Japanese Yen"],["AUD","A$ Australian Dollar"],["SGD","S$ Singapore Dollar"],["CHF","Fr Swiss Franc"],["CAD","C$ Canadian Dollar"],["INR","₹ Indian Rupee"],["BRL","R$ Brazilian Real"],["MXN","MX$ Mexican Peso"],["IDR","Rp Indonesian Rupiah"],["TRY","₺ Turkish Lira"],["ZAR","R South African Rand"]].map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-stone-700 text-sm block mb-2">Booking.com Language</label>
                <select value={config.language || "en-gb"} onChange={e => { setConfig(p => ({ ...p, language: e.target.value })); saveConfig({ language: e.target.value }); }}
                  className="border border-stone-200 rounded-lg px-3 py-2 text-sm w-full" data-testid="market-robot-language">
                  {[["en-gb","English (UK)"],["en-us","English (US)"],["fr","French"],["de","German"],["es","Spanish"],["it","Italian"],["pt-br","Portuguese (Brazil)"],["ja","Japanese"],["zh-cn","Chinese (Simplified)"],["ar","Arabic"],["ko","Korean"],["ru","Russian"],["tr","Turkish"],["nl","Dutch"],["th","Thai"]].map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Logs Tab */}
      {subTab === "logs" && (
        <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden" data-testid="market-robot-logs">
          <div className="px-5 py-3 bg-stone-50 border-b font-bold text-sm text-stone-800">Scan History</div>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="border-b bg-stone-50/50">
              {["Scan ID","City","Dates Scanned","Auto-Adjustments","Scanned At"].map(h =>
                <th key={h} className="px-3 py-2 text-xs font-semibold text-stone-500 text-center">{h}</th>
              )}
            </tr></thead>
            <tbody>{logs.length === 0 ? (
              <tr><td colSpan={5} className="text-center py-12 text-stone-400"><Clock className="w-8 h-8 mx-auto mb-2 text-stone-200" />No scans yet</td></tr>
            ) : logs.map(l => (
              <tr key={l.id} className="border-b border-stone-50">
                <td className="px-3 py-2 font-mono text-xs text-stone-500">{l.id}</td>
                <td className="px-3 py-2 text-center text-stone-700">{l.city}</td>
                <td className="px-3 py-2 text-center font-semibold">{l.dates_scanned}</td>
                <td className="px-3 py-2 text-center"><Badge className="bg-indigo-100 text-indigo-700 text-[10px]">{l.auto_adjustments}</Badge></td>
                <td className="px-3 py-2 text-center text-xs text-stone-400">{new Date(l.scanned_at).toLocaleString("en-GB")}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}
    </div>
  );
};
