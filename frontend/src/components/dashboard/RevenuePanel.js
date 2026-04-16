import { useState, useEffect } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
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
import { RevenueAICopilot } from "./RevenueAICopilot";
import { RateCalendarEditable } from "./RateCalendarEditable";
import { ExportBar } from "./RevenueExports";
import { BarChart3, CalendarDays, Settings2, Zap, CheckSquare, Users, Search, Wand2, LineChart, PieChart, BookOpen, FlaskConical, Shield, Hotel, Bell, DollarSign, Network, Eye, Bot, Download } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "ai-copilot", label: "AI Copilot", icon: Bot },
  { id: "calendar", label: "Rate Calendar", icon: CalendarDays },
  { id: "strategy", label: "Pricing Strategy", icon: Settings2 },
  { id: "smart-pricing", label: "Smart Pricing", icon: Zap },
  { id: "forecasting", label: "Forecasting", icon: LineChart },
  { id: "analytics", label: "Analytics", icon: PieChart },
  { id: "reports", label: "Reports", icon: Download },
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
          {tab === "ai-copilot" && <RevenueAICopilot propertyId={pid} />}
          {tab === "calendar" && <RateCalendarEditable propertyId={pid} />}
          {tab === "strategy" && <RevenuePricingStrategy propertyId={pid} />}
          {tab === "smart-pricing" && <RevenueSmartPricing propertyId={pid} />}
          {tab === "forecasting" && <RevenueForecasting propertyId={pid} />}
          {tab === "analytics" && <RevenueAnalytics propertyId={pid} />}
          {tab === "reports" && <ExportBar propertyId={pid} />}
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
