import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RevenueDashboardEnhanced } from "./RevenueDashboardEnhanced";
import { RevenuePricingStrategy } from "./RevenuePricingStrategy";
import { RevenueSmartPricing } from "./RevenueSmartPricing";
import { RevenueApprovals } from "./RevenueApprovals";
import { RevenueSegments } from "./RevenueSegments";
import { RevenueRateResolver } from "./RevenueRateResolver";
import { RevenueSetupWizard } from "./RevenueSetupWizard";
import { RevenueForecasting } from "./RevenueForecasting";
import { RevenueAnalytics } from "./RevenueAnalytics";
import { RevenuePlaybooks, RevenueExperiments } from "./RevenuePlaybooksExperiments";
import { RevenueParity, RevenueOverbooking, RevenueActionCenter, RevenueProfitOS, RevenueDistribution, RevenueCompetitors } from "./RevenueModules";
import { BarChart3, CalendarDays, Settings2, Zap, CheckSquare, Users, Search, Wand2, LineChart, PieChart, BookOpen, FlaskConical, Shield, Hotel, Bell, DollarSign, Network, Eye } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "calendar", label: "Rate Calendar", icon: CalendarDays },
  { id: "strategy", label: "Pricing Strategy", icon: Settings2 },
  { id: "smart-pricing", label: "Smart Pricing", icon: Zap },
  { id: "forecasting", label: "Forecasting", icon: LineChart },
  { id: "analytics", label: "Analytics", icon: PieChart },
  { id: "approvals", label: "Approvals", icon: CheckSquare },
  { id: "segments", label: "Segments", icon: Users },
  { id: "playbooks", label: "Playbooks", icon: BookOpen },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "parity", label: "Parity", icon: Shield },
  { id: "overbooking", label: "Overbooking", icon: Hotel },
  { id: "action-center", label: "Action Center", icon: Bell },
  { id: "profit-os", label: "Profit OS", icon: DollarSign },
  { id: "distribution", label: "Distribution", icon: Network },
  { id: "competitors", label: "Competitors", icon: Eye },
  { id: "rate-resolver", label: "Rate Resolver", icon: Search },
  { id: "wizard", label: "Setup Wizard", icon: Wand2 },
];

/* ── RATE CALENDAR TAB ── */
const RateCalendarTab = ({ propertyId }) => {
  const [cal, setCal] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [roomType, setRoomType] = useState("");
  const [viewMode, setViewMode] = useState("prices");

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/revenue/rate-calendar/${propertyId}?year=${year}&month=${month}${roomType ? `&room_type=${roomType}` : ""}`); setCal(data); } catch { toast.error("Failed"); }
  }, [propertyId, year, month, roomType]);
  useEffect(() => { load(); }, [load]);

  const navMonth = (dir) => { let nm = month + dir, ny = year; if (nm > 12) { nm = 1; ny++; } if (nm < 1) { nm = 12; ny--; } setMonth(nm); setYear(ny); };
  if (!cal) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  const firstDow = new Date(year, month - 1, 1).getDay();
  const offset = firstDow === 0 ? 6 : firstDow - 1;
  const weeks = [];
  for (const d of cal.days) { const wi = Math.floor((offset + d.day - 1) / 7); const di = (offset + d.day - 1) % 7; if (!weeks[wi]) weeks[wi] = Array(7).fill(null); weeks[wi][di] = d; }
  const perf = cal.performance || {};

  return (
    <div data-testid="rev-rate-calendar-tab">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navMonth(-1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-prev"><svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg></button>
          <h2 className="text-lg font-bold text-stone-800">{cal.month_name} {year}</h2>
          <button onClick={() => navMonth(1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="rev-cal-next"><svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg></button>
        </div>
        <div className="flex items-center gap-2">
          {["prices","occupancy","pickup"].map(v => <button key={v} onClick={() => setViewMode(v)} className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize ${viewMode === v ? "bg-violet-600 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`rev-cal-view-${v}`}>{v}</button>)}
        </div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl p-5 mb-4">
        <div className="flex items-center gap-6 text-sm mb-4"><span><strong>{perf.occupancy}%</strong> Occupancy</span><span><strong>{perf.expected_by_today}%</strong> Expected by Today</span><span><strong>{perf.target}%</strong> Target</span></div>
        <div className="flex items-center gap-3"><label className="text-xs text-stone-500 mr-2">Room Type</label>
          <Select value={roomType || cal.room_type?.id || "default"} onValueChange={v => setRoomType(v)}><SelectTrigger className="w-44 h-9 text-sm"><SelectValue /></SelectTrigger><SelectContent>{cal.room_types.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}</SelectContent></Select>
        </div>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <div className="grid grid-cols-7 border-b">{["Mo","Tu","We","Th","Fr","Sa","Su"].map(d => <div key={d} className="px-2 py-2 text-center text-xs font-bold text-stone-500 border-r last:border-0">{d}</div>)}</div>
        {weeks.map((w, wi) => (
          <div key={wi} className="grid grid-cols-7 border-b last:border-0">{w.map((d, di) => (
            <div key={di} className={`border-r last:border-0 min-h-[90px] p-2 ${d?.is_today ? "bg-violet-50 ring-2 ring-violet-300 ring-inset" : d ? "bg-white" : "bg-stone-50"}`} data-testid={d ? `rev-cal-day-${d.day}` : undefined}>
              {d && <><div className="flex items-center justify-between mb-1"><span className={`text-xs font-bold ${d.is_today ? "text-violet-700" : "text-stone-800"}`}>{d.day}</span>{d.is_today && <span className="text-[8px] bg-violet-600 text-white px-1.5 py-0.5 rounded-full font-bold">Today</span>}</div>
                {viewMode === "prices" && <><div className="text-sm font-bold text-violet-700">{cur(d.recommended_rate)}</div><div className="text-[10px] text-stone-400">{cur(d.pms_rate)} PMS</div></>}
                {viewMode === "occupancy" && <><div className={`text-sm font-bold ${d.occupancy >= 70 ? "text-emerald-600" : d.occupancy >= 40 ? "text-amber-600" : "text-red-500"}`}>{d.occupancy}%</div><div className="text-[10px] text-stone-400">{d.booked}/{d.booked + d.available}</div></>}
                {viewMode === "pickup" && <><div className="text-sm font-bold text-blue-600">{d.booked}</div><div className="text-[10px] text-stone-400">{d.available} avail</div></>}
                {d.is_full && <Badge className="text-[8px] bg-emerald-500 text-white mt-1">Full</Badge>}</>}
            </div>
          ))}</div>
        ))}
      </div>
    </div>
  );
};

/* ── MAIN PANEL ── */
export const RevenuePanel = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("dashboard");
  const [roomTypes, setRoomTypes] = useState([]);
  const pid = activePropertyId || "all";

  useEffect(() => { axios.get(`${API}/revenue/pricing-strategy-full/${pid}`).then(r => setRoomTypes(r.data.room_types || [])).catch(() => {}); }, [pid]);
  const handleNavigate = (tabId) => setTab(tabId);

  return (
    <div className="p-5" data-testid="revenue-panel">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Revenue Management</h2><p className="text-sm text-stone-500">Monitor performance, optimize pricing, maximize revenue</p></div>
      </div>
      <div className="flex items-center gap-0.5 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-1 px-3 py-2.5 text-xs font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${tab === t.id ? "text-violet-700 border-violet-500 bg-violet-50/50" : "text-stone-400 border-transparent hover:text-stone-600"}`} data-testid={`rev-tab-${t.id}`}>
            <t.icon className="w-3 h-3" />{t.label}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tab === "dashboard" && <RevenueDashboardEnhanced propertyId={pid} onNavigate={handleNavigate} />}
          {tab === "calendar" && <RateCalendarTab propertyId={pid} />}
          {tab === "strategy" && <RevenuePricingStrategy propertyId={pid} />}
          {tab === "smart-pricing" && <RevenueSmartPricing propertyId={pid} />}
          {tab === "forecasting" && <RevenueForecasting propertyId={pid} />}
          {tab === "analytics" && <RevenueAnalytics propertyId={pid} />}
          {tab === "approvals" && <RevenueApprovals propertyId={pid} />}
          {tab === "segments" && <RevenueSegments propertyId={pid} />}
          {tab === "playbooks" && <RevenuePlaybooks propertyId={pid} />}
          {tab === "experiments" && <RevenueExperiments propertyId={pid} />}
          {tab === "parity" && <RevenueParity propertyId={pid} />}
          {tab === "overbooking" && <RevenueOverbooking propertyId={pid} />}
          {tab === "action-center" && <RevenueActionCenter propertyId={pid} />}
          {tab === "profit-os" && <RevenueProfitOS propertyId={pid} />}
          {tab === "distribution" && <RevenueDistribution propertyId={pid} />}
          {tab === "competitors" && <RevenueCompetitors propertyId={pid} />}
          {tab === "rate-resolver" && <RevenueRateResolver propertyId={pid} roomTypes={roomTypes} />}
          {tab === "wizard" && <RevenueSetupWizard propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
