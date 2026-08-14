import { useState, useEffect, lazy, Suspense } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "@/i18n";
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
import RmsProSuitePanel from "./RmsProSuitePanel";
import { DynamicPricingEngine } from "./DynamicPricingEngine";
import SmartRateControlPanel from "./SmartRateControlPanel";
import { EventIntelligence } from "./EventIntelligence";
import { ChannelManager } from "./ChannelManager";
import { HistoricalPricing } from "./HistoricalPricing";
import { BookingPace } from "./BookingPace";
import { RevenueForecast } from "./RevenueForecast";
import { RateRecommendations } from "./RateRecommendations";
import { WhatIfSimulator } from "./WhatIfSimulator";
import { CompsetIntelligence } from "./CompsetIntelligence";
import { PriceAlerts } from "./PriceAlerts";
import { DisplacementAnalysis } from "./DisplacementAnalysis";
import { LOSOptimizer } from "./LOSOptimizer";
import { WeeklyDigest } from "./WeeklyDigest";
import { RateScraper } from "./RateScraper";
import ReputationDashboard from "./ReputationDashboard";
import PaceReports from "./PaceReports";
import {
  BarChart3, CalendarDays, Settings2, Zap, CheckSquare, Users, Search, Wand2,
  LineChart, PieChart, BookOpen, FlaskConical, Hotel, Bell, DollarSign,
  Network, Eye, Bot, Download, ChevronRight, Radar, BrainCircuit, PartyPopper, History, Activity, Trophy, AlertTriangle, Scale, Timer, Sparkles, ScanLine, Star, TrendingUp
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RevenueBrainPanel = lazy(() => import("./RevenueBrainPanel"));
const RevenueRobotTour = lazy(() => import("./RevenueRobotTour"));

const PANEL_TOURS = {
  calendar: {
    key: "rate_cal_tour_done",
    steps: [
      { title: "Rate Calendar'a hoş geldiniz", body: "Aylık fiyat takvimi: her günün fiyatını doğrudan hücreye tıklayarak düzenlersiniz. Kısa bir turla özellikleri tanıyalım." },
      { target: "rev-cal-next", title: "Ay gezinme", body: "Ok butonlarıyla aylar arasında gezinin; gelecek 18 aya kadar fiyat planlayabilirsiniz." },
      { target: "rev-cal-bulk", title: "Toplu Düzenleme", body: "Bulk Edit ile tarih aralığı seçip tek seferde onlarca günün fiyatını güncelleyin — sezon açılışlarında dakikalar kazandırır." },
      { target: "rev-rate-calendar-tab", title: "Takvim ızgarası", body: "Hücrelerdeki renkler doluluk seviyesini gösterir; robotun önerdiği fiyat değişiklikleri de bu takvime işlenir. İyi gelirler! 🚀" },
    ],
  },
  "dynamic-pricing": {
    key: "dyn_pricing_tour_done",
    steps: [
      { title: "AI Dynamic Pricing'e hoş geldiniz", body: "Motor; talep, pace, rakip fiyatları ve robotun öğrenilmiş derslerini birleştirerek her gün için fiyat önerir." },
      { target: "dp-nights-30", title: "Fiyatlama ufku", body: "7 günden 1 yıla kadar ufuk seçin — motor seçtiğiniz aralıktaki her gece için öneri üretir." },
      { target: "dp-calculate", title: "Hesapla", body: "Tek tıkla tüm aralığı analiz eder: doluluk, pickup hızı, rakip konumu ve öğrenilmiş çarpanlar hesaba katılır." },
      { target: "dp-apply", title: "Tek tıkla uygula", body: "Önerileri beğendiyseniz Apply ile hepsini fiyat takvimine yazın — guardrail (±15%) otomatik korur. İyi gelirler! 🚀" },
    ],
  },
};

const NAV_SECTIONS = [
  {
    labelKey: "nav.dashboard",
    items: [
      { id: "dashboard", labelKey: "rev.tab.dashboard", icon: BarChart3 },
      { id: "ai-copilot", labelKey: "rev.tab.ai_copilot", icon: Bot },
      { id: "learning-robot", labelKey: "rev.tab.learning_robot", fallback: "Revenue Robotu (Öğrenen Uzman)", icon: BrainCircuit },
      { id: "wizard", labelKey: "nav.setup_wizard", icon: Wand2 },
    ],
  },
  {
    labelKey: "section.pricing",
    items: [
      { id: "dynamic-pricing", labelKey: "rev.tab.dynamic_pricing", icon: BrainCircuit },
      { id: "calendar", labelKey: "rev.tab.calendar", icon: CalendarDays },
      { id: "smart-rate-control", labelKey: "rev.tab.smart_rate_control", icon: Zap },
      { id: "strategy", labelKey: "rev.tab.strategy", icon: Settings2 },
      { id: "smart-pricing", labelKey: "rev.tab.smart_pricing", icon: Zap },
      { id: "approvals", labelKey: "rev.tab.approvals", icon: CheckSquare },
    ],
  },
  {
    labelKey: "section.intelligence",
    items: [
      { id: "rms-pro", labelKey: "rev.tab.rms_pro", icon: Sparkles },
      { id: "market-robot", labelKey: "rev.tab.market_robot", icon: Radar },
      { id: "compset-intel", labelKey: "rev.tab.compset_intel", icon: Trophy },
      { id: "price-alerts", labelKey: "rev.tab.price_alerts", icon: AlertTriangle },
      { id: "weekly-digest", labelKey: "rev.tab.weekly_digest", icon: Sparkles },
      { id: "rate-scraper", labelKey: "rev.tab.rate_scraper", icon: ScanLine },
      { id: "booking-pace", labelKey: "rev.tab.booking_pace", icon: Activity },
      { id: "revenue-forecast", labelKey: "rev.tab.revenue_forecast", icon: DollarSign },
      { id: "rate-actions", labelKey: "rev.tab.rate_actions", icon: Zap },
      { id: "what-if", labelKey: "rev.tab.what_if", icon: FlaskConical },
      { id: "displacement", labelKey: "rev.tab.displacement", icon: Scale },
      { id: "los-optimizer", labelKey: "rev.tab.los_optimizer", icon: Timer },
      { id: "historical", labelKey: "rev.tab.historical_analysis", fallback: "Historical Analysis", icon: History },
      { id: "forecasting", labelKey: "rev.tab.forecasting", icon: LineChart },
      { id: "analytics", labelKey: "nav.analytics", icon: PieChart },
      { id: "competitors", labelKey: "rev.tab.competitors", fallback: "Competitors", icon: Eye },
      { id: "reputation", labelKey: "rev.tab.reputation", fallback: "Reputation", icon: Star },
      { id: "pace", labelKey: "rev.tab.pace", fallback: "Pace Reports", icon: TrendingUp },
    ],
  },
  {
    labelKey: "rev.section.automation",
    fallback: "Automation",
    items: [
      { id: "playbooks", labelKey: "rev.tab.playbooks", fallback: "Playbooks", icon: BookOpen },
      { id: "experiments", labelKey: "rev.tab.experiments", fallback: "Experiments", icon: FlaskConical },
      { id: "action-center", labelKey: "rev.tab.action_center", fallback: "Action Center", icon: Bell },
    ],
  },
  {
    labelKey: "rev.section.distribution",
    fallback: "Distribution",
    items: [
      { id: "channel-manager", labelKey: "rev.tab.channel_manager", fallback: "Channel Manager", icon: Network },
      { id: "segments", labelKey: "rev.tab.segments", fallback: "Segments", icon: Users },
      { id: "overbooking", labelKey: "rev.tab.overbooking", fallback: "Overbooking", icon: Hotel },
      { id: "distribution", labelKey: "rev.tab.distribution_item", fallback: "Distribution", icon: Network },
    ],
  },
  {
    labelKey: "section.finance",
    items: [
      { id: "profit-os", labelKey: "rev.tab.profit_os", icon: DollarSign },
      { id: "reports", labelKey: "rev.tab.reports", icon: Download },
      { id: "rate-resolver", labelKey: "rev.tab.rate_resolver", icon: Search },
    ],
  },
];

export const RevenuePanel = ({ properties, activePropertyId, initialTab }) => {
  const { t } = useTranslation();
  const [tab, setTab] = useState(initialTab || "dashboard");
  const [roomTypes, setRoomTypes] = useState([]);
  // Auto-collapse on mobile so the inner nav doesn't force horizontal overflow
  const [collapsed, setCollapsed] = useState(() =>
    typeof window !== "undefined" && window.innerWidth < 1024
  );
  const pid = activePropertyId || "all";
  const [panelTour, setPanelTour] = useState(null);

  useEffect(() => {
    const cfg = PANEL_TOURS[tab];
    if (cfg && !localStorage.getItem(cfg.key)) setPanelTour(tab);
  }, [tab]);

  useEffect(() => {
    axios.get(`${API}/revenue/pricing-strategy-full/${pid}`).then(r => setRoomTypes(r.data.room_types || [])).catch(() => {});
  }, [pid]);

  // Keep inner nav collapsed when the viewport goes below lg; expand back up if user resizes wider
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth < 1024) setCollapsed(true);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const handleNavigate = (tabId) => setTab(tabId);

  // Resolves a label via i18n — falls back to `fallback` prop when key is missing
  const label = (o) => {
    if (!o?.labelKey) return o?.label || "";
    const tr = t(o.labelKey);
    if (tr && tr !== o.labelKey) return tr;
    return o.fallback || o.label || o.labelKey;
  };

  const currentItem = NAV_SECTIONS.flatMap(s => s.items).find(i => i.id === tab);

  return (
    <div className="flex h-full min-h-[calc(100vh-64px)]" data-testid="revenue-panel">
      {/* Left Sidebar Navigation */}
      <div className={`bg-stone-900 flex-shrink-0 overflow-y-auto transition-all duration-300 ${collapsed ? "w-14" : "w-56"}`} data-testid="rev-sidebar">
        {/* Header */}
        <div className={`sticky top-0 bg-stone-900 z-10 border-b border-stone-700/50 ${collapsed ? "px-2 py-3" : "px-4 py-4"}`}>
          {!collapsed && (
            <div className="mb-1">
              <h2 className="text-sm font-bold text-white tracking-wide">{t("rev.breadcrumb.home")}</h2>
              <p className="text-[10px] text-stone-400">{t("rev.system")}</p>
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
            <div key={section.labelKey || section.label} className="mb-1">
              {!collapsed && (
                <div className="px-4 py-2">
                  <span className="text-[9px] font-bold text-stone-500 uppercase tracking-[0.15em]">{label(section)}</span>
                </div>
              )}
              {collapsed && <div className="h-px bg-stone-700/40 mx-2 my-2" />}
              {section.items.map(item => {
                const isActive = tab === item.id;
                const itemLabel = label(item);
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
                    title={collapsed ? itemLabel : undefined}
                  >
                    {isActive && <div className="absolute left-0 top-1 bottom-1 w-[3px] rounded-r-full bg-violet-500" />}
                    <item.icon className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-violet-400" : "text-stone-500 group-hover:text-stone-300"}`} />
                    {!collapsed && (
                      <span className={`text-[13px] truncate ${isActive ? "font-semibold" : "font-medium"}`}>
                        {itemLabel}
                      </span>
                    )}
                    {collapsed && (
                      <div className="absolute left-full ml-2 px-2.5 py-1 bg-stone-800 text-white text-xs font-medium rounded-md opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-50 shadow-lg border border-stone-700">
                        {itemLabel}
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
      <div className="flex-1 min-w-0 overflow-y-auto bg-stone-50">
        <div className="p-4 md:p-6">
          {/* Breadcrumb */}
          {currentItem && tab !== "dashboard" && (
            <div className="flex items-center gap-1.5 text-xs text-stone-400 mb-4">
              <button onClick={() => setTab("dashboard")} className="hover:text-stone-600 transition-colors">{t("rev.breadcrumb.home")}</button>
              <ChevronRight className="w-3 h-3" />
              <span className="text-stone-600 font-medium">{label(currentItem)}</span>
              {PANEL_TOURS[tab] && (
                <button onClick={() => setPanelTour(tab)} data-testid={`rev-tour-btn-${tab}`}
                  className="ml-auto px-2.5 py-1 rounded-md border border-stone-200 text-stone-500 hover:border-stone-400 hover:text-stone-700 text-[11px] font-semibold">
                  ▶ Tanıtım Turu
                </button>
              )}
            </div>
          )}

          {PANEL_TOURS[tab] && panelTour === tab && (
            <Suspense fallback={null}>
              <RevenueRobotTour open steps={PANEL_TOURS[tab].steps}
                onClose={() => { localStorage.setItem(PANEL_TOURS[tab].key, "1"); setPanelTour(null); }} />
            </Suspense>
          )}

          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              {tab === "dashboard" && <RevenueDashboardEnhanced propertyId={pid} onNavigate={handleNavigate} />}
              {tab === "ai-copilot" && <RevenueAICopilot propertyId={pid} />}
              {tab === "learning-robot" && (
                <Suspense fallback={<div className="p-8 text-sm text-stone-400">Yükleniyor…</div>}>
                  <RevenueBrainPanel properties={properties || []} activePropertyId={pid} />
                </Suspense>
              )}
              {tab === "calendar" && <RateCalendarEditable propertyId={pid} />}
              {tab === "smart-rate-control" && <SmartRateControlPanel activePropertyId={pid} />}
              {tab === "dynamic-pricing" && <DynamicPricingEngine propertyId={pid} />}
              {tab === "strategy" && <RevenuePricingStrategy propertyId={pid} />}
              {tab === "smart-pricing" && <RevenueSmartPricing propertyId={pid} />}
              {tab === "forecasting" && <RevenueForecasting propertyId={pid} />}
              {tab === "market-robot" && <MarketRobot propertyId={pid} properties={properties} />}
              {tab === "rms-pro" && <RmsProSuitePanel propertyId={pid} />}
              {tab === "reputation" && <ReputationDashboard propertyId={pid} hotelName={(properties || []).find(p => p.id === pid)?.name || ""} />}
              {tab === "pace" && <PaceReports propertyId={pid} hotelName={(properties || []).find(p => p.id === pid)?.name || ""} />}
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
              {tab === "channel-manager" && <ChannelManager propertyId={pid} hotelName={(properties || []).find(p => p.id === pid)?.name || ""} />}
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

