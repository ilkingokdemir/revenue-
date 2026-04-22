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
import { RevenueOverbooking, RevenueActionCenter, RevenueProfitOS, RevenueDistribution, RevenueCompetitors } from "./RevenueModules";
import { RevenueAICopilot } from "./RevenueAICopilot";
import { RateCalendarEditable } from "./RateCalendarEditable";
import { ExportBar } from "./RevenueExports";
import { MarketRobot } from "./MarketRobot";
import { DynamicPricingEngine } from "./DynamicPricingEngine";
import SmartRateControlPanel from "./SmartRateControlPanel";
import { EventIntelligence } from "./EventIntelligence";
import { ChannelManager } from "./ChannelManager";
import { HistoricalPricing } from "./HistoricalPricing";
import { BookingPace } from "./BookingPace";
import { RevenueForecast } from "./RevenueForecast";
import { RateRecommendations } from "./RateRecommendations";
import { WhatIfSimulator } from "./WhatIfSimulator";
import { DemandRadar } from "./DemandRadar";
import { CompsetIntelligence } from "./CompsetIntelligence";
import { PriceAlerts } from "./PriceAlerts";
import { DisplacementAnalysis } from "./DisplacementAnalysis";
import { LOSOptimizer } from "./LOSOptimizer";
import { WeeklyDigest } from "./WeeklyDigest";
import { RateScraper } from "./RateScraper";
import {
  BarChart3, CalendarDays, Settings2, Zap, CheckSquare, Users, Search, Wand2,
  LineChart, PieChart, BookOpen, FlaskConical, Hotel, Bell, DollarSign,
  Network, Eye, Bot, Download, ChevronRight, Radar, BrainCircuit, PartyPopper, History, Activity, Trophy, AlertTriangle, Scale, Timer, Sparkles, ScanLine
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const NAV_SECTIONS = [
  {
    label: "Overview",
    items: [
      { id: "dashboard", label: "Dashboard", icon: BarChart3 },
      { id: "ai-copilot", label: "AI Copilot", icon: Bot },
      { id: "wizard", label: "Setup Wizard", icon: Wand2 },
    ],
  },
  {
    label: "Pricing",
    items: [
      { id: "dynamic-pricing", label: "AI Dynamic Pricing", icon: BrainCircuit },
      { id: "calendar", label: "Rate Calendar", icon: CalendarDays },
      { id: "smart-rate-control", label: "Smart Rate Control", icon: Zap },
      { id: "strategy", label: "Pricing Strategy", icon: Settings2 },
      { id: "smart-pricing", label: "Smart Pricing", icon: Zap },
      { id: "approvals", label: "Approvals", icon: CheckSquare },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { id: "market-robot", label: "Market Robot", icon: Radar },
      { id: "demand-radar", label: "Demand Radar", icon: Activity },
      { id: "compset-intel", label: "Compset Intelligence", icon: Trophy },
      { id: "price-alerts", label: "Price Alerts", icon: AlertTriangle },
      { id: "weekly-digest", label: "AI Weekly Digest", icon: Sparkles },
      { id: "rate-scraper", label: "Rate Automation", icon: ScanLine },
      { id: "booking-pace", label: "Booking Pace", icon: Activity },
      { id: "revenue-forecast", label: "Revenue Forecast", icon: DollarSign },
      { id: "rate-actions", label: "Rate Actions", icon: Zap },
      { id: "what-if", label: "What-If Simulator", icon: FlaskConical },
      { id: "displacement", label: "Displacement", icon: Scale },
      { id: "los-optimizer", label: "LOS Optimizer", icon: Timer },
      { id: "historical", label: "Historical Analysis", icon: History },
      { id: "forecasting", label: "Forecasting", icon: LineChart },
      { id: "analytics", label: "Analytics", icon: PieChart },
      { id: "competitors", label: "Competitors", icon: Eye },
    ],
  },
  {
    label: "Automation",
    items: [
      { id: "playbooks", label: "Playbooks", icon: BookOpen },
      { id: "experiments", label: "Experiments", icon: FlaskConical },
      { id: "action-center", label: "Action Center", icon: Bell },
    ],
  },
  {
    label: "Distribution",
    items: [
      { id: "channel-manager", label: "Channel Manager", icon: Network },
      { id: "segments", label: "Segments", icon: Users },
      { id: "overbooking", label: "Overbooking", icon: Hotel },
      { id: "distribution", label: "Distribution", icon: Network },
    ],
  },
  {
    label: "Finance",
    items: [
      { id: "profit-os", label: "Profit OS", icon: DollarSign },
      { id: "reports", label: "Reports & Export", icon: Download },
      { id: "rate-resolver", label: "Rate Resolver", icon: Search },
    ],
  },
];

export const RevenuePanel = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("dashboard");
  const [roomTypes, setRoomTypes] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const pid = activePropertyId || "all";

  useEffect(() => {
    axios.get(`${API}/revenue/pricing-strategy-full/${pid}`).then(r => setRoomTypes(r.data.room_types || [])).catch(() => {});
  }, [pid]);

  const handleNavigate = (tabId) => setTab(tabId);

  const currentItem = NAV_SECTIONS.flatMap(s => s.items).find(i => i.id === tab);

  return (
    <div className="flex h-full min-h-[calc(100vh-64px)]" data-testid="revenue-panel">
      {/* Left Sidebar Navigation */}
      <div className={`bg-stone-900 flex-shrink-0 overflow-y-auto transition-all duration-300 ${collapsed ? "w-14" : "w-56"}`} data-testid="rev-sidebar">
        {/* Header */}
        <div className={`sticky top-0 bg-stone-900 z-10 border-b border-stone-700/50 ${collapsed ? "px-2 py-3" : "px-4 py-4"}`}>
          {!collapsed && (
            <div className="mb-1">
              <h2 className="text-sm font-bold text-white tracking-wide">Revenue</h2>
              <p className="text-[10px] text-stone-400">Management System</p>
            </div>
          )}
          <button onClick={() => setCollapsed(!collapsed)}
            className="text-stone-500 hover:text-stone-300 transition-colors mt-1"
            data-testid="rev-sidebar-toggle">
            <ChevronRight className={`w-4 h-4 transition-transform ${collapsed ? "" : "rotate-180"}`} />
          </button>
        </div>

        {/* Nav Sections */}
        <div className="py-2">
          {NAV_SECTIONS.map(section => (
            <div key={section.label} className="mb-1">
              {!collapsed && (
                <div className="px-4 py-2">
                  <span className="text-[9px] font-bold text-stone-500 uppercase tracking-[0.15em]">{section.label}</span>
                </div>
              )}
              {collapsed && <div className="h-px bg-stone-700/40 mx-2 my-2" />}
              {section.items.map(item => {
                const isActive = tab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setTab(item.id)}
                    className={`w-full flex items-center gap-2.5 transition-all relative group ${
                      collapsed ? "justify-center px-2 py-2.5 mx-auto" : "px-4 py-2"
                    } ${
                      isActive
                        ? "text-white bg-violet-600/20"
                        : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/60"
                    }`}
                    data-testid={`rev-tab-${item.id}`}
                    title={collapsed ? item.label : undefined}
                  >
                    {isActive && <div className="absolute left-0 top-1 bottom-1 w-[3px] rounded-r-full bg-violet-500" />}
                    <item.icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-violet-400" : "text-stone-500 group-hover:text-stone-300"}`} />
                    {!collapsed && (
                      <span className={`text-[13px] truncate ${isActive ? "font-semibold" : "font-medium"}`}>
                        {item.label}
                      </span>
                    )}
                    {collapsed && (
                      <div className="absolute left-full ml-2 px-2.5 py-1 bg-stone-800 text-white text-xs font-medium rounded-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-lg border border-stone-700">
                        {item.label}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto bg-stone-50">
        <div className="p-6">
          {/* Breadcrumb */}
          {currentItem && tab !== "dashboard" && (
            <div className="flex items-center gap-1.5 text-xs text-stone-400 mb-4">
              <button onClick={() => setTab("dashboard")} className="hover:text-stone-600 transition-colors">Revenue</button>
              <ChevronRight className="w-3 h-3" />
              <span className="text-stone-600 font-medium">{currentItem.label}</span>
            </div>
          )}

          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              {tab === "dashboard" && <RevenueDashboardEnhanced propertyId={pid} onNavigate={handleNavigate} />}
              {tab === "ai-copilot" && <RevenueAICopilot propertyId={pid} />}
              {tab === "calendar" && <RateCalendarEditable propertyId={pid} />}
              {tab === "smart-rate-control" && <SmartRateControlPanel activePropertyId={pid} />}
              {tab === "dynamic-pricing" && <DynamicPricingEngine propertyId={pid} />}
              {tab === "strategy" && <RevenuePricingStrategy propertyId={pid} />}
              {tab === "smart-pricing" && <RevenueSmartPricing propertyId={pid} />}
              {tab === "forecasting" && <RevenueForecasting propertyId={pid} />}
              {tab === "market-robot" && <MarketRobot propertyId={pid} />}
              {tab === "demand-radar" && <DemandRadar propertyId={pid} />}
              {tab === "compset-intel" && <CompsetIntelligence propertyId={pid} />}
              {tab === "price-alerts" && <PriceAlerts propertyId={pid} onNavigate={handleNavigate} />}
              {tab === "weekly-digest" && <WeeklyDigest propertyId={pid} />}
              {tab === "rate-scraper" && <RateScraper propertyId={pid} />}
              {tab === "booking-pace" && <BookingPace propertyId={pid} />}
              {tab === "revenue-forecast" && <RevenueForecast propertyId={pid} />}
              {tab === "rate-actions" && <RateRecommendations propertyId={pid} />}
              {tab === "what-if" && <WhatIfSimulator propertyId={pid} />}
              {tab === "displacement" && <DisplacementAnalysis propertyId={pid} />}
              {tab === "los-optimizer" && <LOSOptimizer propertyId={pid} />}
              {tab === "historical" && <HistoricalPricing propertyId={pid} />}
              {tab === "analytics" && <RevenueAnalytics propertyId={pid} />}
              {tab === "reports" && <ExportBar propertyId={pid} />}
              {tab === "approvals" && <RevenueApprovals propertyId={pid} />}
              {tab === "segments" && <RevenueSegments propertyId={pid} />}
              {tab === "playbooks" && <RevenuePlaybooks propertyId={pid} />}
              {tab === "experiments" && <RevenueExperiments propertyId={pid} />}
              {tab === "overbooking" && <RevenueOverbooking propertyId={pid} />}
              {tab === "action-center" && <RevenueActionCenter propertyId={pid} />}
              {tab === "profit-os" && <RevenueProfitOS propertyId={pid} />}
              {tab === "distribution" && <RevenueDistribution propertyId={pid} />}
              {tab === "channel-manager" && <ChannelManager propertyId={pid} />}
              {tab === "competitors" && <RevenueCompetitors propertyId={pid} />}
              {tab === "rate-resolver" && <RevenueRateResolver propertyId={pid} roomTypes={roomTypes} />}
              {tab === "wizard" && <RevenueSetupWizard propertyId={pid} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
