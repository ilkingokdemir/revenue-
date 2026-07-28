import { useEffect, useState, useCallback, useMemo, Suspense } from "react";
import "@/App.css";
import axios from "axios";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { LanguageProvider, useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PWAInstall } from "@/components/PWAInstall";
import { OfflineBanner } from "@/components/OfflineBanner";
import { installOfflineQueue } from "@/lib/offlineQueue";
installOfflineQueue();
import ReviewWidget from "./ReviewWidget";
import BookingEngine from "./BookingEngine";
import ReviewCollectionPage from "./ReviewCollectionPage";
import SelfCheckInPage from "./SelfCheckInPage";
import KioskPWA from "./pages/KioskPWA";
import HousekeepingMobilePWA from "./pages/HousekeepingMobilePWA";
import SelfCheckoutPage from "./SelfCheckoutPage";
import DashboardSharePage from "./DashboardSharePage";
import RoomKeyPage from "./RoomKeyPage";
import SelfCheckInV2Page from "./SelfCheckInV2Page";
import TipPage from "./TipPage";
import OwnerSelfServiceApp from "./components/owner/OwnerSelfServiceApp";
import AgencyPortalApp from "./components/agency/AgencyPortalApp";
import PublicEventPage from "./PublicEventPage";
import GuestPortalV2Page from "./GuestPortalV2Page";
import GuestPortalPage from "./GuestPortalPage";
import GuestPaymentPage from "./GuestPaymentPage";
import TurkishPayPage from "./TurkishPayPage";
// ---------- EAGER imports (rendered on every dashboard render or first paint) ----------
import CommandPalette from "./components/CommandPalette";
import SectionHub from "./components/SectionHub";
import PwaInstallButton from "./components/PwaInstallButton";
import MobileHome from "./components/MobileHome";
import TodayHub from "./components/dashboard/TodayHub";
import GlobalReportIssueFAB from "./components/dashboard/GlobalReportIssueFAB";
import ActionFeedPanel from "./components/dashboard/ActionFeedPanel";
import { OnboardingBanner } from "./components/dashboard/OnboardingBanner";
import { NotificationBell } from "./components/dashboard/NotificationBell";
import { LoginPage } from "./components/dashboard/LoginPage";
import LandingPage from "./LandingPage";
import ReveniqLanding from "./ReveniqLanding";
import { PendingLegalDocsGate } from "./components/PendingLegalDocsGate";
import { StaffOnboardingGate } from "./components/StaffOnboardingGate";
import { ContractSigningPage } from "./components/public/ContractSigningPage";

// ---------- LAZY-LOADED dashboard panels (code-split per panel chunk) ----------
import {
  IntegrationsPanel, ArrivalsCockpit, StaffContractsPanel, StaffOnboardingAdminPanel,
  PayrollRateMatrix, CityLedgerPanel, TaxConfigPanel, DepositPolicyPanel, CurrencyFxPanel, RateStructurePanel,
  GroupBookingsPanel, GdprPanel,
  NightAuditClosePanel, DepositLedgerPanel, CommissionReconPanel, GiftCardsPanel,
  ReviewSentimentPanel, GuestRfmPanel, PreventiveMaintenancePanel,
  AssetRegisterPanel, CashDrawerPanel, TwoFactorAuthPanel,
  RevenueHealthPanel, IpAllowlistPanel, CardVaultPanel, DepositAutomationPanel,
  ChannelRestrictionsPanel, ChannelInboundPanel, ChannelParityPanel, OtaHealthPanel,
  ChannelMappingsPanel, SyncQueuePanel,
  ChannelManagerHub, GroupBlocksPanel, LaundrySettingsPanel,
  OnboardingWizard, UnifiedInboxPanel,
  TRCompliancePanel, EUCompliancePanel, AIPredictionsPanel, ChannelRevenuePanel,
  KDSPanel, LoyaltyV2Panel, ExternalLoyaltyPanel, OTACommissionPanel, DirectConversionPanel, SiteMinderPanel, AvailabilityCalendarPanel, SentimentHeatmapPanel, SelfCheckInPipelinePanel, BrandPortalPanel,
  OpsV2Panel, HousekeepingHubPanel, GlitchLogPanel, SopsPanel, TeamChatPanel, GuestCRM360Panel, ChannelManagerV2Panel, ForecastV2Panel, AnomalyPanel, TippingPanel, GuestPortalV2Panel,
  ConferenceSCPanel, CopilotLibraryPanel, ImageAIPanel, FnbTabsPanel, BiFeedPanel, HkTurnoverPanel,
  PricingExplainPanel, LoyaltyTierPanel, BanquetOrdersPanel, HelpGuidePanel, SiteFeasibilityPanel, SelfCheckinAutoPanel, LockSDKPanel, RecipeCogsPanel, VoiceConciergePanel, WhatsAppVoicePanel,
  BugTrackerPanel, AuditTrailPanel, CollisionsPanel, ProfitOSPanel, RolesPermissionsPanel,
  ImportModulePanel, LegalDocumentsPanel, AnalyticsPanel, ReportsSettings,
  BrandingPanel, SyncLogPanel, PropertyMappingPanel, BookingEnginePanel,
  TemplateGallery, TemplateCustomizer, PromoCodesPanel, AddOnsPanel, PoliciesPanel,
  MessagingHub, ConciergeAnalyticsPanel, AutomationPanel, ChatbotAutomationPanel, LiveChatInboxPanel, ChannelSettingsPanel,
  DashboardHome, StaffPerformancePanel, GuestProfilesPanel, AdminPanel, HousekeepingPanel,
  NightAuditPanel, LoyaltyPanel, LogbookPanel, ForecastPanel,
  PaceReports, AIPricingV2Panel, ParityHeatmapPanel, MorningBriefPanel, RMLabPanel,
  ConciergeInboxPanel, GroupRequestsPanel, SustainabilityPanel, HousekeepingRoutePanel,
  NightlyRecapPanel, AccountingExportPanel, LateCheckoutPanel, ServiceRecoveryPanel,
  RoomQRPanel, TaxPresetsPanel, WalkInPanel, NoShowPanel, GuestPrefsPanel,
  CleaningChecklistsPanel, AttributionPanel, MewsUniversityPanel, ScheduledReportsPanel, CustomDashboardBuilder, GroupRoomingImportPanel, OpsQuickActionsPanel,
  TimeSlotsPanel, StaffOpsPanel, RevenueProtectionPanel, SpacesPanel, VccPanel, OwnerSummaryPanel, MarketplacePanel, MultiPropertyRollupPanel,
  CurrencyPanel, AgentsB2BPanel, SecurityOwnerPanel, PreAuthPanel, ChargebackPanel,
  WebPushPanel, PmsCrsSyncPanel, PmsProPanel, PublicApiPortalPanel, MidStaySurveyPanel, FolioLivePanel,
  ABTestPanel, PreArrivalDripPanel, MenuEngineeringPanel, SRVoucherPanel, FolioSplitPanel,
  LoyaltyAutoPanel, LateCheckoutOfferPanel, OTAStopSellForecastPanel,
  MsgTemplatesPanel, BirthdayPanel, LowStockPanel, RebookPanel, StayExtPanel, LongStayPanel,
  CancelInsurancePanel, GroupRoomingWizPanel, TaxReportsV2Panel, CISlotsPanel, Tier1DashboardPanel,
  BookingEngineV2Panel, OwnerPortalPanel, SpaActivitiesPanel, LoyaltyTiersPanel,
  BudgetActualPanel, CompsetPanel, PartnerWebhooksPanel,
  MeetingsSalesPanel, FnbPosHubPanel, CarbonReportingV2Panel,
  AgencyPortalAdminPanel, WebConciergeAdminPanel, ReviewAgentPanel,
  OpenPricingPanel, BeachPosPanel, PublicEventsPanel, HurdleLrvPanel, LeakagePanel, GuestRiskPanel, GuestSegmentsPanel, ChannelHealthPanel, KeyFiguresPanel, AutomationHubPanel, ArReconPanel, WaitlistPanel, HkDispatchPanel, ResQualityPanel, ChainBenchmarkPanel, DigitalAuthPanel, AllotmentsPanel, ForecastPlansPanel, IntradayRepricePanel, RestrictionAdvisorPanel, GapFillerPanel, LostDemandPanel, DemoLeadsPanel, RevenueStrategistPanel, MinRateFloorsPanel, DiscountStackPanel, OwnerRatesAdminPanel, OwnerPulseAdminPanel, PortfolioBoardPanel,
  AgentsPanel, VacationRentalPanel,
  DevPortalAdminPanel, WholesalerHubPanel, LeadFunnelPanel,
  MarketingVideosPanel,
  BrandVoicePanel,
  CampaignsPanel, GuestAppPanel, SmartLocksPanel, SmartRoomsPanel, BasePriceCurvePanel, SetupWizardPanel, StockManagementPanel,
  AccountingPanel, POSPanel, PaymentsPanel, SurveyPanel, GuestJourneyPanel, MaintenancePanel,
  RateManagerPanel, MyRatesPanel, ReportsCentrePanel, ScheduledReports, MobileCompanion, EnhancedDashboard,
  ReportsHub, FinancePL, ShiftScheduler, ReceptionReport, PassOverDuties, ComplianceRegister,
  LaundryManagement, PayrollManagement, ExpenseManagement, CashFlowForecast,
  OperationsHubPanel, FinancePanel, StaffManagementPanel, MyTasksPanel, LostFoundPanel,
  EventsPanel, SettingsHubPanel, BookingEngineAdmin, BookingTimeline, RevenuePanel,
} from "./lazyPanels";
import { StarRating, PlatformBadge, StatsCard, ReviewCard } from "@/components/dashboard/ReviewComponents";
import { AIResponsePanel, NotificationSettings, TemplatesManager, ApprovalQueuePanel } from "@/panels/ReviewToolsPanels";
import { UserManagementPanel, ApiConnectionPanel, WebhooksPanel, IntegrationGuidePanel } from "@/panels/SystemToolsPanels";
import { buildMenuSections } from "./navigation/menuSections";
import { SIDEBAR_PERM_MAP } from "./navigation/permMap";
import GuestMaintenancePage from "./GuestMaintenancePage";
import BookingWidgetPage from "./BookingWidgetPage";
import AuthorizeFormPage from "./AuthorizeFormPage";
import SpacesPublicPage from "./SpacesPublicPage";
import GuestSurveyPage from "./GuestSurveyPage";
import UpsellOfferPage from "./UpsellOfferPage";
import GuestRegistrationPage from "./GuestRegistrationPage";
import GuestFeedbackPage from "./GuestFeedbackPage";
import CheckInKioskPage from "./CheckInKioskPage";
import FeatureComparePage from "./FeatureComparePage";
import QROrderPage from "./QROrderPage";
import KioskPage from "./KioskPage";
import MidStaySurveyPublicPage from "./MidStaySurveyPublicPage";
import HandoffSidebarBadge from "./components/dashboard/HandoffSidebarBadge";
import {
  Star,
  CheckCircle,
  WarningCircle,
  Sparkle,
  ChatText,
  FunnelSimple,
  ArrowsClockwise,
  Buildings,
  Quotes,
  PaperPlaneTilt,
  PencilSimple,
  Bell,
  X,
  EnvelopeSimple,
  TestTube,
  FileText,
  Plus,
  Trash,
  Copy,
  Tag,
  TrendUp,
  TrendDown,
  Lightning,
  Users,
  Brain,
  Smiley,
  SmileyMeh,
  SmileySad,
  PaperPlaneTilt as Send,
  Database,
  Info,
  CaretRight,
  Palette,
  Image,
  SignOut,
  UserCircle,
  ShieldCheck,
  ClockCounterClockwise,
  UserPlus,
  Key,
  ArrowSquareOut,
  Code,
  MagicWand,
  Bug,
  Lock,
  Funnel,
} from "@phosphor-icons/react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Configure axios to send cookies
axios.defaults.withCredentials = true;

// Loader shown while a lazy-loaded panel chunk is fetched
const PanelLoader = () => (
  <div className="flex items-center justify-center py-20" data-testid="panel-loader">
    <div className="flex items-center gap-3 text-stone-400">
      <div className="w-5 h-5 border-2 border-stone-200 border-t-cyan-500 rounded-full animate-spin" />
      <span className="text-xs uppercase tracking-wider">Yükleniyor…</span>
    </div>
  </div>
);

function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

// Mobile breakpoint helper — phones / native get the role-based home grid,
// tablets / desktops get the full TodayHub. Re-evaluated on every render so
// orientation/resize works without a hook.
function isMobileViewport() {
  if (typeof window === "undefined") return false;
  return window.innerWidth <= 768;
}

// Re-export from modular components for external use
export { StarRating, PlatformBadge, StatsCard, ReviewCard } from "@/components/dashboard";

// Platform configuration with colors
const PLATFORMS = {
  "booking.com": { name: "Booking.com", color: "#003580", bg: "bg-[#003580]" },
  "airbnb": { name: "Airbnb", color: "#FF5A5F", bg: "bg-[#FF5A5F]" },
  "expedia": { name: "Expedia", color: "#FFCC00", bg: "bg-[#FFCC00]", textDark: true },
  "tripadvisor": { name: "TripAdvisor", color: "#00AF87", bg: "bg-[#00AF87]" },
  "google": { name: "Google", color: "#4285F4", bg: "bg-[#4285F4]" },
  "trip.com": { name: "Trip.com", color: "#287DFA", bg: "bg-[#287DFA]" },
  "agoda": { name: "Agoda", color: "#5542B6", bg: "bg-[#5542B6]" },
  "hotels.com": { name: "Hotels.com", color: "#D32F2F", bg: "bg-[#D32F2F]" },
  "yelp": { name: "Yelp", color: "#D32323", bg: "bg-[#D32323]" },
  "facebook": { name: "Facebook", color: "#1877F2", bg: "bg-[#1877F2]" },
  "makemytrip": { name: "MakeMyTrip", color: "#EE2E24", bg: "bg-[#EE2E24]" },
  "hrs": { name: "HRS", color: "#C4161C", bg: "bg-[#C4161C]" },
  "despegar": { name: "Despegar", color: "#6B2D8B", bg: "bg-[#6B2D8B]" },
  "hostelworld": { name: "Hostelworld", color: "#F47920", bg: "bg-[#F47920]" }
};

// Template categories
const TEMPLATE_CATEGORIES = {
  positive: { name: "Positive", color: "bg-[#5A6B50]", icon: "👍" },
  negative: { name: "Negative", color: "bg-[#C05A44]", icon: "👎" },
  neutral: { name: "Neutral", color: "bg-[#57534E]", icon: "➖" },
  complaint: { name: "Complaint", color: "bg-[#D4A373]", icon: "⚠️" },
  praise: { name: "Praise", color: "bg-[#3E5245]", icon: "⭐" }
};

// Sentiment colors
const SENTIMENT_COLORS = {
  positive: { bg: "bg-[#5A6B50]", text: "text-[#5A6B50]", light: "bg-[#E8EDE7]" },
  negative: { bg: "bg-[#C05A44]", text: "text-[#C05A44]", light: "bg-red-50" },
  neutral: { bg: "bg-[#57534E]", text: "text-[#57534E]", light: "bg-stone-100" },
  mixed: { bg: "bg-[#D4A373]", text: "text-[#D4A373]", light: "bg-amber-50" }
};

// Urgency colors
const URGENCY_COLORS = {
  low: "bg-[#5A6B50]",
  medium: "bg-[#D4A373]",
  high: "bg-orange-500",
  critical: "bg-[#C05A44]"
};

// Main Dashboard Component
const Dashboard = ({ user, onLogout, permissions }) => {
  const { t } = useTranslation();
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedReview, setSelectedReview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showNotificationSettings, setShowNotificationSettings] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [showReports, setShowReports] = useState(false);
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [showBranding, setShowBranding] = useState(false);
  const [showUserManagement, setShowUserManagement] = useState(false);
  const [showApprovalQueue, setShowApprovalQueue] = useState(false);
  const [branding, setBranding] = useState(null);
  const [templateTextToApply, setTemplateTextToApply] = useState(null);
  const [properties, setProperties] = useState([]);
  const [activePropertyId, setActivePropertyId] = useState("all");
  const [filters, setFilters] = useState({
    platform: "all",
    status: "all"
  });

  const handleApplyTemplate = (templateContent) => {
    setTemplateTextToApply(templateContent);
  };

  const handleSyncComplete = () => {
    fetchReviews();
    fetchStats();
  };

  const fetchProperties = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/properties`);
      setProperties(data);
    } catch (e) {
      console.error("Error fetching properties:", e);
    }
  }, []);

  const fetchReviews = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activePropertyId && activePropertyId !== "all") params.append("property_id", activePropertyId);
      if (filters.platform !== "all") params.append("platform", filters.platform);
      if (filters.status !== "all") params.append("status", filters.status);
      
      const response = await axios.get(`${API}/reviews?${params.toString()}`);
      setReviews(response.data);
    } catch (error) {
      console.error("Error fetching reviews:", error);
      toast.error("Failed to load reviews");
    }
  }, [filters, activePropertyId]);

  const fetchStats = useCallback(async () => {
    try {
      const params = activePropertyId && activePropertyId !== "all" ? `?property_id=${activePropertyId}` : "";
      const response = await axios.get(`${API}/reviews/stats/summary${params}`);
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching stats:", error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const seedReviews = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/reviews/seed`);
      if (response.data.seeded) {
        toast.success("Demo reviews loaded!");
        await fetchReviews();
        await fetchStats();
      }
    } catch (error) {
      console.error("Error seeding reviews:", error);
    }
  }, [fetchReviews, fetchStats]);

  const fetchBranding = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/branding`);
      setBranding(response.data);
    } catch (error) {
      console.error("Error fetching branding:", error);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await seedReviews();
      await fetchProperties();
      await fetchReviews();
      await fetchStats();
      await fetchBranding();
      setIsLoading(false);
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchReviews();
    fetchStats();
  }, [filters, activePropertyId, fetchReviews, fetchStats]);

  const handleResponseSubmit = async (reviewId, responseText) => {
    setIsLoading(true);
    try {
      // First save the response text
      await axios.put(`${API}/reviews/${reviewId}/respond`, {
        response_text: responseText
      });
      
      // If receptionist, auto-submit for approval
      if (user?.role === "receptionist") {
        try {
          await axios.post(`${API}/reviews/${reviewId}/submit-for-approval`);
          toast.success("Response submitted for manager approval!");
        } catch (e) {
          // If auth fails (no token), just save the draft
          console.log("Auto-submit skipped:", e.message);
        }
      }
      
      await fetchReviews();
      await fetchStats();
      
      const updatedReview = reviews.find(r => r.id === reviewId);
      if (updatedReview) {
        setSelectedReview({
          ...updatedReview,
          response_text: responseText,
          response_status: user?.role === "receptionist" ? "pending_approval" : "responded"
        });
      }
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const [activeView, setActiveView] = useState("dashboard");
  const [collapsedSections, setCollapsedSections] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isBatchResponding, setIsBatchResponding] = useState(false);
  const [batchResult, setBatchResult] = useState(null);

  // Recents tracker for Command Palette
  const [recentsRaw, setRecentsRaw] = useState(() => {
    try { return JSON.parse(localStorage.getItem("mhb_recents") || "[]"); }
    catch (_) { return []; }
  });
  const pushRecent = useCallback((id) => {
    if (!id || id === "dashboard") return;
    setRecentsRaw((prev) => {
      const next = [id, ...prev.filter((x) => x !== id)].slice(0, 8);
      try { localStorage.setItem("mhb_recents", JSON.stringify(next)); } catch (_) {}
      return next;
    });
  }, []);

  // Centralised navigation: tracks recents + closes mobile sidebar
  const navigate = useCallback((id) => {
    setActiveView(id);
    setSidebarOpen(false);
    pushRecent(id);
  }, [pushRecent]);

  // Ask-AI handler from command palette: routes "?question" to concierge inbox
  // (Concierge Inbox is the closest existing AI surface). Drops the query into a toast for now.
  const handleAskAi = useCallback((q) => {
    if (!q) return;
    toast.info(`AI sorgusu: "${q}" → Concierge Inbox'e yönlendiriliyor`, { duration: 3500 });
    navigate("concierge-inbox");
  }, [navigate]);


  const batchAutoRespond = async (tone = "professional") => {
    setIsBatchResponding(true);
    setBatchResult(null);
    try {
      const { data } = await axios.post(`${API}/reviews/batch-auto-respond`, {
        tone,
        limit: 10,
        property_id: activePropertyId !== "all" ? activePropertyId : undefined,
      });
      setBatchResult(data);
      if (data.processed > 0) {
        toast.success(`AI responded to ${data.processed} review${data.processed !== 1 ? "s" : ""}`);
        fetchReviews();
        fetchStats();
      } else {
        toast.info("No unresponded reviews to process");
      }
    } catch (e) {
      toast.error("Batch auto-respond failed");
    }
    setIsBatchResponding(false);
  };

  // Mobile breakpoint helper — phones / native get the role-based home grid,
  // tablets / desktops get the full TodayHub. Re-renders on resize.
  const [viewportIsMobile, setViewportIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 768 : false
  );
  useEffect(() => {
    const onResize = () => setViewportIsMobile(window.innerWidth <= 768);
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, []);

  // Sidebar menu items — Mews/Eviivo-style clean grouping.
  // - No emoji in names, only Phosphor icons.
  // - Each section ≤ 12 items so users can scan.
  // - All section labels use a single muted color (text-stone-500).
  // - Test IDs preserved for backward compatibility with the test suite.
  // - i18n: name/label always translated via tNav()/tSection() at render time.
  //   The hardcoded `name` here is just the English fallback when a translation key is missing.
  const tNav = useCallback((item) => {
    if (!item) return "";
    const key = `nav.${(item.id || "").replace(/-/g, "_")}`;
    const out = t(key);
    return out && out !== key ? out : (item.name || item.id);
  }, [t]);
  const tSectionKey = (label) => (label || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const tSectionLabel = useCallback((sectionOrLabel) => {
    const label = typeof sectionOrLabel === "string" ? sectionOrLabel : (sectionOrLabel?.label || "");
    if (!label) return "";
    const key = `section_label.${tSectionKey(label)}`;
    const out = t(key);
    return out && out !== key ? out : label;
  }, [t]);

  const menuSections = buildMenuSections(t, user);


  // Sidebar permission gating map extracted to navigation/permMap.js (iter 386)

  const menuPerms = permissions?.menu_permissions;
  const isLegacyAdmin = !!permissions?.is_legacy_admin;
  const canSeeSidebar = (testId) => {
    if (isLegacyAdmin) return true;                       // admin bypass
    const perm = SIDEBAR_PERM_MAP[testId];
    if (!perm) return true;                               // no gate → visible
    if (!menuPerms) return true;                          // perms not loaded yet → show (avoid flicker)
    return menuPerms.has(perm);
  };
  const gatedNavigation = menuSections.map(section => ({
    ...section,
    items: section.items.filter(it => it.divider || canSeeSidebar(it.testId)),
  })).filter(section => section.items.length > 0);

  // Flatten gated navigation into a Command Palette catalogue
  const commandItems = useMemo(() => {
    const out = [];
    for (const section of gatedNavigation) {
      for (const it of section.items) {
        if (it.divider || !it.id) continue; // skip label-only dividers
        if (it.launchUrl) continue; // external launches skipped
        const translatedName = tNav(it);
        const translatedSection = tSectionLabel(section);
        out.push({
          id: it.id,
          name: translatedName,
          group: translatedSection,
          icon: it.icon,
          testId: it.testId,
          keywords: `${translatedName} ${it.name} ${translatedSection} ${section.label} ${it.id}`,
        });
      }
    }
    return out;
  }, [gatedNavigation, tNav, tSectionLabel]);

  // Resolve recent IDs back into rich items
  const recents = useMemo(
    () => recentsRaw.map((id) => commandItems.find((i) => i.id === id)).filter(Boolean),
    [recentsRaw, commandItems]
  );


  return (
    <div className="min-h-screen bg-[#F4F6F8] flex" data-testid="review-dashboard">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} data-testid="sidebar-overlay" />
      )}

      {/* Mobile Top Bar */}
      <div className="fixed top-0 left-0 right-0 h-14 bg-[#1C1917] flex items-center justify-between px-4 z-30 lg:hidden" data-testid="mobile-topbar">
        <button onClick={() => setSidebarOpen(true)} className="p-2 text-stone-400 hover:text-white" data-testid="mobile-menu-btn">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16"/></svg>
        </button>
        <h1 className="text-sm font-semibold text-white truncate">{branding?.app_name || "Review Hub"}</h1>
        <NotificationBell onNavigate={(v) => { setActiveView(v); setSidebarOpen(false); }} />
      </div>

      {/* Left Sidebar */}
      <aside className={`w-56 bg-[#0A0F1C] border-r border-slate-800/60 flex flex-col fixed inset-y-0 left-0 z-50 transition-transform duration-200 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`} data-testid="sidebar">
        {/* Logo */}
        <div className="p-4 border-b border-stone-800">
          <div className="flex items-center gap-2.5">
            {branding?.logo_url ? (
              <img src={branding.logo_url} alt="Logo" className="w-8 h-8 rounded-lg object-cover" data-testid="header-logo" />
            ) : (
              <img src="/logos/myhotelbox_icon.png" alt="MyHotelBox" className="w-8 h-8 rounded-lg object-cover" data-testid="header-logo-default" />
            )}
            <div className="min-w-0 flex-1">
              <h1 className="text-sm font-semibold text-white truncate" data-testid="header-app-name">{branding?.app_name || "MyHotelBox & ReveniQ"}</h1>
              <p className="text-[10px] text-stone-500 truncate" data-testid="header-subtitle">{branding?.subtitle || "PMS & Revenue Suite"}</p>
            </div>
            {/* Close button for mobile */}
            <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 text-stone-500 hover:text-white" data-testid="sidebar-close-btn">
              <X size={18} />
            </button>
          </div>
          {/* Notification Bell — desktop only */}
          <div className="mt-3 hidden lg:flex items-center gap-2">
            <NotificationBell onNavigate={setActiveView} />
            <span className="text-[10px] text-stone-500">Notifications</span>
          </div>
          {/* ⌘K Command Palette trigger */}
          <div className="mt-3">
            <CommandPalette
              items={commandItems}
              recents={recents}
              onSelect={navigate}
              onAskAi={handleAskAi}
            />
          </div>
          {/* Branch Selector — always visible */}
          <div className="mt-3" data-testid="branch-selector-container">
            <label className="text-[9px] uppercase tracking-[0.15em] font-semibold text-stone-600 mb-1 block px-0.5">Branch</label>
            <Select value={activePropertyId} onValueChange={(v) => setActivePropertyId(v)} data-testid="property-selector">
              <SelectTrigger className="w-full bg-stone-800 border-stone-700 text-stone-200 h-8 text-xs font-medium hover:bg-stone-750 transition-colors">
                <div className="flex items-center gap-2 truncate">
                  <Buildings size={13} className="text-emerald-500 flex-shrink-0" />
                  <SelectValue placeholder="Select branch" />
                </div>
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                <SelectItem value="all" data-testid="branch-all">
                  <span className="font-medium">All Branches</span>
                </SelectItem>
                {properties.map((p) => (
                  <SelectItem key={p.id} value={p.id} data-testid={`branch-${p.id}`}>
                    <div className="flex items-center gap-2">
                      <span>{p.name}</span>
                      {p.external_id && <span className="text-[9px] text-emerald-600 ml-1">linked</span>}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 custom-scrollbar">
          {gatedNavigation.map((section, sIdx) => {
            const sectionKey = section.label || `section-${sIdx}`;
            const sectionHubId = `hub-${sectionKey.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
            // Default: ALL sections collapsed except Overview + the section containing the active view.
            // User explicit toggle is persisted in localStorage as `nav-open-<key>`.
            const containsActive = section.items.some((it) => it.id === activeView) || activeView === sectionHubId;
            const storedOpen = (typeof localStorage !== "undefined"
              ? localStorage.getItem(`nav-open-${sectionKey}`)
              : null);
            const isOverview = sectionKey === "Overview";
            const reallyOpen = containsActive
              || (storedOpen === "1")
              || (storedOpen !== "0" && isOverview);
            const toggleSection = () => {
              const wasOpen = reallyOpen;
              if (wasOpen) {
                // Collapse only — never auto-navigate when explicitly closing
                setCollapsedSections({ ...collapsedSections, [sectionKey]: true });
                try { localStorage.setItem(`nav-open-${sectionKey}`, "0"); } catch {}
              } else {
                // First click on a closed section → open hub page (Mews-style).
                // User can still expand sub-items via the chevron alone via second click after opening.
                setCollapsedSections({ ...collapsedSections, [sectionKey]: false });
                try { localStorage.setItem(`nav-open-${sectionKey}`, "1"); } catch {}
                if (!isOverview && !containsActive) {
                  navigate(sectionHubId);
                }
              }
            };
            return (
              <div key={sectionKey} className="mb-1">
                {sIdx > 0 && <div className="mx-4 my-1 border-t border-stone-800/60" />}
                {section.label && (
                  <button onClick={toggleSection} data-testid={`nav-section-${sectionKey}`}
                    className="w-full flex items-center justify-between px-4 py-2 text-left hover:bg-stone-800/30 transition-colors group">
                    <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-stone-400 group-hover:text-stone-200">
                      {tSectionLabel(section)}
                    </span>
                    <CaretRight
                      size={9}
                      weight="bold"
                      className={`text-stone-700 group-hover:text-stone-500 transition-transform duration-200 ${reallyOpen ? "rotate-90" : ""}`}
                    />
                  </button>
                )}
                {reallyOpen && section.items.map((item) => {
                  // Render sub-section dividers (label-only items)
                  if (item.divider) {
                    return (
                      <div
                        key={`div-${item.label}`}
                        className="px-4 pt-3 pb-1 text-[9px] uppercase tracking-[0.18em] text-stone-400 font-semibold select-none"
                        data-testid={`sidebar-divider-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                      >
                        {item.label}
                      </div>
                    );
                  }
                  return (
                  <button
                    key={item.id}
                    onClick={() => {
                      if (item.launchUrl && item.id === "kiosk-launch") {
                        window.open(`/checkin-kiosk/${activePropertyId || "default"}`, "_blank", "noopener,noreferrer");
                        return;
                      }
                      navigate(item.id);
                    }}
                    className={`w-full flex items-center gap-2.5 px-4 py-2 text-left text-[13px] transition-all ${
                      activeView === item.id
                        ? "bg-stone-800 text-white font-medium border-l-2 border-emerald-500"
                        : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50 border-l-2 border-transparent"
                    }`}
                    data-testid={item.testId}
                  >
                    <item.icon size={16} weight={activeView === item.id ? "fill" : "regular"} />
                    {tNav(item)}
                    {item.id === "live-chat-inbox" && (
                      <HandoffSidebarBadge propertyId={activePropertyId} />
                    )}
                  </button>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Language & User & Logout */}
        <div className="p-3 border-t border-stone-800 space-y-2">
          <LanguageSwitcher compact />
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-stone-800 flex items-center justify-center">
              <UserCircle size={18} className="text-stone-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-stone-300 truncate" data-testid="user-name">{user?.name}</div>
              <div className="text-[10px] text-stone-500 capitalize" data-testid="user-role">{user?.role} · {user?.department?.replace("_", " ")}</div>
            </div>
            <button onClick={onLogout} className="text-stone-500 hover:text-red-400 transition-colors p-1" data-testid="logout-btn">
              <SignOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 lg:ml-56 pt-14 lg:pt-0">
        {/* First-run progress banner — auto-hides when setup is complete */}
        {activeView !== "onboarding" && user?.role === "admin" && (
          <OnboardingBanner
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : "default"}
            onResume={() => setActiveView("onboarding")}
          />
        )}

        <Suspense fallback={<PanelLoader />}>
        {/* Section hub pages — Mews-style. Auto-rendered when activeView starts with hub-. */}
        {activeView?.startsWith("hub-") && (() => {
          const target = activeView.replace(/^hub-/, "");
          const matchedSection = menuSections.find((s) => {
            const k = (s.label || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
            return k === target;
          });
          if (matchedSection) {
            return (
              <SectionHub
                section={matchedSection}
                tNav={tNav}
                tSectionLabel={tSectionLabel}
                onSelect={(itemId) => {
                  const it = matchedSection.items.find((x) => x.id === itemId);
                  if (it?.launchUrl && it.id === "kiosk-launch") {
                    window.open(`/checkin-kiosk/${activePropertyId || "default"}`, "_blank", "noopener,noreferrer");
                    return;
                  }
                  navigate(itemId);
                }}
              />
            );
          }
          return null;
        })()}

        {/* Dashboard Home — AI-first "Today" hub
            On mobile / native we replace this with a role-based MobileHome
            so receptionists / housekeepers get one-tap shortcuts. */}
        {activeView === "dashboard" && (
          isMobileViewport() || viewportIsMobile ? (
            <MobileHome
              user={user}
              branding={branding}
              onNavigate={(id) => {
                if (id === "__open_command_palette__") {
                  // Trigger ⌘K palette by dispatching the standard shortcut
                  document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
                  return;
                }
                navigate(id);
              }}
            />
          ) : (
            <TodayHub
              propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
              hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
              onNavigate={navigate}
            />
          )
        )}

        {/* TR Compliance — KBS + e-Fatura */}
        {activeView === "tr-compliance" && (
          <TRCompliancePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* EU Compliance — 7 country hub */}
        {activeView === "eu-compliance" && (
          <EUCompliancePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* AI Predictions — Cancel Risk + Upsell Propensity */}
        {activeView === "ai-predictions" && (
          <AIPredictionsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Channel Revenue — Open Pricing + Yield Rules */}
        {activeView === "channel-revenue" && (
          <ChannelRevenuePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Yield Guard — Hurdle Rate & Last Room Value */}
        {activeView === "hurdle-lrv" && (
          <HurdleLrvPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}

        {/* KDS — Kitchen Display + 86 List + Recipes */}
        {activeView === "kds" && (
          <KDSPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Loyalty v2 — Tier Benefits + Referrals + Dynamic Packaging */}
        {activeView === "loyalty-v2" && (
          <LoyaltyV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* External Loyalty — Marriott Bonvoy, Hilton, IHG, Accor, Hyatt, Wyndham, BW */}
        {activeView === "external-loyalty" && (
          <ExternalLoyaltyPanel
            activePropertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* OTA Commission Dashboard — net revenue per channel */}
        {activeView === "ota-commission" && (
          <OTACommissionPanel activePropertyId={activePropertyId} />
        )}

        {/* Direct Booking Conversion Engine — OTA→Direct kupon motoru */}
        {activeView === "direct-conversion" && <DirectConversionPanel />}

        {/* SiteMinder Middleware Translator Adapter */}
        {activeView === "siteminder" && (
          <SiteMinderPanel activePropertyId={activePropertyId} />
        )}

        {/* Müsaitlik Takvimi — aylık doluluk ısı haritası (iter 378'de canlandırıldı) */}
        {activeView === "availability-calendar" && (
          <AvailabilityCalendarPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Sentiment Heatmap — Cross-channel guest voice */}
        {activeView === "sentiment-heatmap" && (
          <SentimentHeatmapPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Self Check-in v2 — Pre-arrival pipeline */}
        {activeView === "self-checkin-v2" && (
          <SelfCheckInPipelinePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
          />
        )}

        {/* Brand Portal — Chain HQ rollup + white-label */}
        {activeView === "brand-portal" && (
          <BrandPortalPanel
            hotelName={branding?.app_name}
          />
        )}

        {/* Ops — Misafir Talepleri + Bakım İş Emirleri + Çamaşır PAR + HK Denetim */}
        {(activeView === "ops-v2" || activeView === "maintenance") && (
          <OpsV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
            properties={properties}
          />
        )}

        {/* Glitch Log & Shift Handover (Flexkeeping-style) */}
        {activeView === "glitch-log" && (
          <GlitchLogPanel propertyId={activePropertyId || "all"} />
        )}

        {/* SOP Library (Standard Operating Procedures) */}
        {activeView === "sops" && (
          <SopsPanel propertyId={activePropertyId || "all"} user={user} />
        )}

        {/* Automation Rules (event-driven workflows) */}
        {["automation-hub", "automation-rules"].includes(activeView) && (
          <AutomationHubPanel key={activeView} initialView={activeView}
            propertyId={activePropertyId || "all"} user={user} onNavigate={navigate} />
        )}

        {/* Team Chat (multi-channel internal communication) */}
        {activeView === "team-chat" && (
          <div className="p-5 max-w-[1400px] mx-auto">
            <div className="mb-4">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
                <ChatText size={12} weight="fill" className="text-blue-500" />
                <span>Collaboration Suite</span>
              </div>
              <h1 className="text-2xl font-semibold text-stone-900">Team Chat</h1>
              <p className="text-sm text-stone-500 mt-1 max-w-2xl">
                Departman bazlı kanal sohbeti — vardiyalar arası iletişim, hızlı bildirim ve takip. Real-time polling (4sn).
              </p>
            </div>
            <TeamChatPanel user={user} />
          </div>
        )}

        {/* Guest CRM 360 (Revinate-killer) */}
        {activeView === "crm-360" && <GuestCRM360Panel user={user} />}

        {/* Channel Manager v2 (production OTA framework) */}
        {activeView === "channels-v2" && <ChannelManagerV2Panel />}

        {/* ===== Competitor Parity v3 (Iter 277) ===== */}
        {activeView === "booking-engine-v2" && (
          <BookingEngineV2Panel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "owner-portal" && <OwnerPortalPanel />}
        {activeView === "agency-portal" && <AgencyPortalAdminPanel />}
        {activeView === "web-concierge" && <WebConciergeAdminPanel />}
        {activeView === "review-agent" && <ReviewAgentPanel />}
        {activeView === "open-pricing" && (
          <OpenPricingPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "beach-pos" && (
          <BeachPosPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "public-events" && (
          <PublicEventsPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "spa-activities" && (
          <SpaActivitiesPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "loyalty-tiers-v2" && <LoyaltyTiersPanel />}
        {activeView === "budget-actual" && (
          <BudgetActualPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}
        {activeView === "compset" && (
          <CompsetPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}
        {activeView === "partner-webhooks" && <PartnerWebhooksPanel />}
        {["automation-analytics", "automation-roi", "automation-settings"].includes(activeView) && (
          <AutomationHubPanel key={activeView} initialView={activeView}
            propertyId={activePropertyId || "all"} user={user} onNavigate={navigate} />
        )}
        {activeView === "leakage-audit" && (
          <LeakagePanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "guest-risk" && (
          <GuestRiskPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "waitlist" && (
          <WaitlistPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "hk-dispatch" && (
          <HkDispatchPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "res-quality" && (
          <ResQualityPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "guest-segments" && <GuestSegmentsPanel />}
        {activeView === "channel-health" && (
          <ChannelHealthPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "key-figures" && (
          <KeyFiguresPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "comp-radar" && (
          <CompsetPanel propertyId={activePropertyId || "default"} initialTab="radar" />
        )}
        {activeView === "meetings-sales" && (
          <MeetingsSalesPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "fnb-pos-hub" && (
          <FnbPosHubPanel propertyId={activePropertyId || "all"} />
        )}
        {activeView === "carbon-v2" && (
          <CarbonReportingV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Forecast v2 — 24-month horizon + Demand Calendar + Pickup Curve */}
        {activeView === "forecast-v2" && (
          <ForecastV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Anomaly Radar — statistical z-score detection + GPT root-cause explain */}
        {activeView === "anomaly" && (
          <AnomalyPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Digital Tipping — Stripe-powered guest-to-staff tipping */}
        {activeView === "tipping" && (
          <TippingPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Guest Portal v2 — Self-Modify + Cancel */}
        {activeView === "guest-portal-v2" && (
          <GuestPortalV2Panel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Conference S&C — MICE Proposal Builder */}
        {activeView === "conference-sc" && (
          <ConferenceSCPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Banquet Event Orders */}
        {activeView === "banquet-orders" && (
          <BanquetOrdersPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Help & user guide */}
        {activeView === "help-guide" && <HelpGuidePanel />}

        {/* Site Feasibility & Investor Analysis */}
        {activeView === "site-feasibility" && (
          <SiteFeasibilityPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Auto pre-arrival self check-in trigger */}
        {activeView === "self-checkin-auto" && (
          <SelfCheckinAutoPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Hardware Lock SDK adapter (Batch 39) */}
        {activeView === "lock-sdk" && (
          <LockSDKPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Recipe COGS & modifier trees (Batch 40) */}
        {activeView === "recipe-cogs" && (
          <RecipeCogsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Voice Concierge — Whisper STT + LLM (Batch 42) */}
        {activeView === "voice-concierge" && (
          <VoiceConciergePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
            currentUser={user}
          />
        )}

        {/* WhatsApp Voice Concierge — Twilio inbound webhook admin */}
        {activeView === "whatsapp-voice" && (
          <WhatsAppVoicePanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* AI Copilot Library */}
        {activeView === "copilot" && (
          <CopilotLibraryPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Image AI Cleanliness Scoring — merged into Housekeeping hub */}

        {/* HK Turnover — merged into Housekeeping hub */}

        {/* AI Pricing Explainability */}
        {activeView === "pricing-explain" && (
          <PricingExplainPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* F&B Tab Transfer */}
        {activeView === "fnb-tabs" && (
          <FnbTabsPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* BI Feed (Power BI / Tableau / Excel) */}
        {activeView === "bi-feed" && (
          <BiFeedPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* My Tasks */}
        {activeView === "my-tasks" && (
          <MyTasksPanel user={user} />
        )}

        {/* Booking Calendar Timeline */}
        {activeView === "calendar" && (
          <BookingTimeline properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Revenue Management */}
        {activeView === "revenue" && (
          <RevenuePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Reviews View */}
        {activeView === "reviews" && (
          <div className="p-5">
            {/* Stats Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
              <StatsCard icon={ChatText} label="Total Reviews" value={stats?.total_reviews || 0} subtext={`Across ${Object.keys(stats?.by_platform || {}).length} platforms`} />
              <StatsCard icon={Star} label="Average Rating" value={stats?.average_rating ? `${stats.average_rating}/5` : "N/A"} subtext={<StarRating rating={Math.round(stats?.average_rating || 0)} size={12} />} />
              <StatsCard icon={CheckCircle} label="Response Rate" value={`${stats?.response_rate || 0}%`} subtext={`${stats?.responded || 0} of ${stats?.total_reviews || 0} responded`} />
              <StatsCard icon={WarningCircle} label="Pending" value={(stats?.pending || 0) + (stats?.pending_approval || 0)} subtext="Reviews awaiting response" />
            </div>

            {/* Auto-Respond Bar */}
            {((stats?.pending || 0) + (stats?.pending_approval || 0)) > 0 && (
              <div className="bg-gradient-to-r from-violet-50 to-blue-50 border border-violet-200 rounded-xl p-4 mb-5 flex items-center justify-between" data-testid="auto-respond-bar">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 bg-violet-100 rounded-lg flex items-center justify-center">
                    <MagicWand size={18} className="text-violet-600" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-stone-800">AI Auto-Respond</p>
                    <p className="text-xs text-stone-500">{(stats?.pending || 0)} reviews awaiting response — let AI handle them</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => batchAutoRespond("professional")} disabled={isBatchResponding} data-testid="batch-respond-professional"
                    className={`px-3 py-2 text-xs font-bold rounded-lg transition-all ${isBatchResponding ? "bg-stone-200 text-stone-400" : "bg-violet-500 hover:bg-violet-600 text-white"}`}>
                    {isBatchResponding ? "Generating..." : "Professional Tone"}
                  </button>
                  <button onClick={() => batchAutoRespond("friendly")} disabled={isBatchResponding} data-testid="batch-respond-friendly"
                    className={`px-3 py-2 text-xs font-bold rounded-lg transition-all ${isBatchResponding ? "bg-stone-200 text-stone-400" : "bg-blue-500 hover:bg-blue-600 text-white"}`}>
                    Friendly Tone
                  </button>
                  <button onClick={() => batchAutoRespond("apologetic")} disabled={isBatchResponding} data-testid="batch-respond-apologetic"
                    className={`px-3 py-2 text-xs font-bold rounded-lg transition-all ${isBatchResponding ? "bg-stone-200 text-stone-400" : "bg-amber-500 hover:bg-amber-600 text-white"}`}>
                    Apologetic Tone
                  </button>
                </div>
              </div>
            )}

            {/* Batch Result */}
            {batchResult && batchResult.processed > 0 && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-5" data-testid="batch-result">
                <p className="text-sm font-bold text-emerald-800">AI responded to {batchResult.processed} review{batchResult.processed !== 1 ? "s" : ""}</p>
                <div className="mt-2 space-y-1">
                  {batchResult.results?.slice(0, 5).map(r => (
                    <div key={r.review_id} className="flex items-center gap-2 text-xs text-stone-600">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span className="font-medium">{r.guest_name}</span>
                      <span className="text-stone-400">({r.platform}, {r.rating}/5)</span>
                      <span className="text-stone-400 truncate max-w-[300px]">{r.response_preview}</span>
                    </div>
                  ))}
                </div>
                {batchResult.errors > 0 && <p className="text-xs text-red-500 mt-1">{batchResult.errors} failed</p>}
              </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
              {/* Filters & Review List */}
              <div className="md:col-span-4 bg-white border border-stone-200/80 rounded-xl shadow-card overflow-hidden" data-testid="review-list-panel">
                <div className="p-3 border-b border-stone-100 bg-stone-50/50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <FunnelSimple size={14} className="text-stone-400" />
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-stone-400">Filters</span>
                    </div>
                    <button onClick={() => { fetchReviews(); fetchStats(); toast.success("Refreshed!"); }} className="text-stone-400 hover:text-stone-600 transition-colors" data-testid="refresh-btn">
                      <ArrowsClockwise size={14} />
                    </button>
                  </div>
                  <div className="flex gap-2">
                    <Select value={filters.platform} onValueChange={(value) => setFilters(prev => ({ ...prev, platform: value }))} data-testid="platform-filter">
                      <SelectTrigger className="flex-1 bg-white border-stone-200 h-7 text-[11px]"><SelectValue placeholder="Platform" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Platforms</SelectItem>
                        {Object.entries(PLATFORMS).map(([key, config]) => (
                          <SelectItem key={key} value={key}>{config.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select value={filters.status} onValueChange={(value) => setFilters(prev => ({ ...prev, status: value }))} data-testid="status-filter">
                      <SelectTrigger className="flex-1 bg-white border-stone-200 h-7 text-[11px]"><SelectValue placeholder="Status" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="pending_approval">Awaiting Approval</SelectItem>
                        <SelectItem value="rejected">Rejected</SelectItem>
                        <SelectItem value="responded">Responded</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <ScrollArea className="h-[calc(100vh-250px)] custom-scrollbar" data-testid="review-list">
                  {isLoading ? (
                    <div className="p-8 text-center"><ArrowsClockwise size={24} className="mx-auto mb-2 animate-spin text-stone-300" /><p className="text-sm text-stone-400">Loading reviews...</p></div>
                  ) : reviews.length === 0 ? (
                    <div className="p-8 text-center"><ChatText size={24} className="mx-auto mb-2 text-stone-300" /><p className="text-sm text-stone-400">No reviews found</p></div>
                  ) : (
                    <AnimatePresence>
                      {reviews.map((review) => (
                        <ReviewCard key={review.id} review={review} isSelected={selectedReview?.id === review.id} onClick={() => setSelectedReview(review)} />
                      ))}
                    </AnimatePresence>
                  )}
                </ScrollArea>
              </div>
              {/* Review Detail */}
              <div className="md:col-span-8 bg-white border border-stone-200/80 rounded-xl shadow-card p-5 flex flex-col" data-testid="review-detail-panel">
                <AIResponsePanel review={selectedReview} onResponseSubmit={handleResponseSubmit} isLoading={isLoading} templateText={templateTextToApply} onTemplateApplied={() => setTemplateTextToApply(null)} />
              </div>
            </div>
          </div>
        )}

        {/* Analytics View */}
        {activeView === "analytics" && (
          <AnalyticsPanel isOpen={true} onClose={() => setActiveView("reviews")} />
        )}

        {/* Templates View */}
        {activeView === "templates" && (
          <TemplatesManager isOpen={true} onClose={() => setActiveView("reviews")} onSelectTemplate={handleApplyTemplate} />
        )}

        {/* Approvals View */}
        {activeView === "approvals" && (
          <ApprovalQueuePanel onReviewUpdate={() => { fetchReviews(); fetchStats(); }} />
        )}

        {/* Integrations View */}
        {activeView === "integrations" && (
          <IntegrationsPanel isOpen={true} onClose={() => setActiveView("reviews")} onSyncComplete={handleSyncComplete} />
        )}

        {/* API Connection View */}
        {activeView === "api" && (
          <ApiConnectionPanel user={user} />
        )}

        {/* Webhooks View */}
        {activeView === "webhooks" && (
          <WebhooksPanel user={user} />
        )}

        {/* Integration Guide View */}
        {activeView === "guide" && (
          <IntegrationGuidePanel />
        )}

        {/* Alerts View */}
        {activeView === "alerts" && (
          <NotificationSettings isOpen={true} onClose={() => setActiveView("reviews")} />
        )}

        {/* Reports View */}
        {activeView === "reports" && (
          <ReportsSettings isOpen={true} onClose={() => setActiveView("reviews")} />
        )}

        {/* Branding View */}
        {activeView === "branding" && (
          <BrandingPanel isOpen={true} onClose={() => setActiveView("reviews")} branding={branding} onBrandingUpdate={(updated) => setBranding(updated)} />
        )}

        {/* Team View - Enhanced Staff Management */}
        {activeView === "team" && (
          <StaffManagementPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Admin Panel */}
        {activeView === "admin-panel" && (
          <AdminPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Settings Hub */}
        {activeView === "settings-hub" && (
          <SettingsHubPanel />
        )}

        {/* Sync Log View */}
        {activeView === "synclog" && (
          <SyncLogPanel />
        )}

        {/* Property Mapping View */}
        {activeView === "mapping" && (
          <PropertyMappingPanel user={user} />
        )}

        {/* Booking Engine View */}
        {activeView === "booking" && (
          <BookingEnginePanel properties={properties} />
        )}

        {/* Templates Gallery View */}
        {activeView === "website-templates" && (
          <TemplateGallery properties={properties} />
        )}

        {/* Template Customizer View */}
        {activeView === "customize-template" && (
          <TemplateCustomizer properties={properties} />
        )}

        {/* Promo Codes View */}
        {activeView === "promo-codes" && (
          <PromoCodesPanel properties={properties} />
        )}

        {/* Add-ons View */}
        {activeView === "add-ons" && (
          <AddOnsPanel properties={properties} />
        )}

        {/* Policies & Facilities View */}
        {activeView === "policies" && (
          <PoliciesPanel properties={properties} />
        )}

        {/* Guest Messaging Hub */}
        {activeView === "messaging" && (
          <MessagingHub properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* AI Concierge Analytics */}
        {activeView === "concierge-analytics" && (
          <ConciergeAnalyticsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Automation */}
        {activeView === "automation" && (
          <AutomationPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Chatbot Automation (Cloudbeds Guest Experience parity) */}
        {activeView === "chatbot-automation" && (
          <ChatbotAutomationPanel propertyId={activePropertyId} />
        )}

        {/* Live Chat Inbox (handoff sessions) */}
        {activeView === "live-chat-inbox" && (
          <LiveChatInboxPanel propertyId={activePropertyId} />
        )}

        {/* Channel Settings */}
        {activeView === "channel-settings" && (
          <ChannelSettingsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Staff Performance */}
        {activeView === "staff-performance" && (
          <StaffPerformancePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Profiles */}
        {activeView === "guest-profiles" && (
          <GuestProfilesPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Journey */}
        {activeView === "guest-journey" && (
          <GuestJourneyPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Campaigns */}
        {activeView === "campaigns" && (
          <CampaignsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest App */}
        {activeView === "guest-app" && (
          <GuestAppPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Smart Locks / Digital Keys */}
        {activeView === "smart-locks" && (
          <SmartLocksPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Smart Rooms / IoT Control */}
        {activeView === "smart-rooms" && (
          <SmartRoomsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Base Price Curve (18-month pricing) */}
        {activeView === "base-curve" && (
          <BasePriceCurvePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Setup Wizard */}
        {activeView === "setup-wizard" && (
          <SetupWizardPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Stock Management */}
        {activeView === "stock-management" && (
          <StockManagementPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Housekeeping Hub — merged: Rooms · Turnover · Route · Checklists · AI Score · QR · Laundry */}
        {["housekeeping", "hk-turnover", "hk-route", "cleaning-checklists",
          "image-ai", "room-qr", "laundry", "laundry-settings"].includes(activeView) && (
          <HousekeepingHubPanel
            properties={properties}
            activePropertyId={activePropertyId}
            user={user}
            permissions={permissions}
            initialTab={{
              "housekeeping": "rooms",
              "hk-turnover": "turnover",
              "hk-route": "route",
              "cleaning-checklists": "checklists",
              "image-ai": "ai-score",
              "room-qr": "qr",
              "laundry": "laundry",
              "laundry-settings": "laundry-cfg",
            }[activeView] || "rooms"}
          />
        )}

        {activeView === "hk-route" && false && (
          <HousekeepingRoutePanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "room-qr" && false && (
          <RoomQRPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "service-recovery" && (
          <ServiceRecoveryPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {activeView === "late-checkout" && (
          <LateCheckoutPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Iter 214 — Batch 1 Keyless Features */}
        {activeView === "tax-presets" && (
          <div className="p-6">
            <TaxPresetsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "walkin" && (
          <div className="p-6">
            <WalkInPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "no-show" && (
          <div className="p-6">
            <NoShowPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "guest-prefs" && (
          <div className="p-6">
            <GuestPrefsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "cleaning-checklists" && false && (
          <div className="p-6">
            <CleaningChecklistsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ops-quick" && (
          <div className="p-6">
            <OpsQuickActionsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "group-rooming" && (
          <div className="p-6">
            <GroupRoomingImportPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "attribution" && (
          <div className="p-6">
            <AttributionPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "mews-university" && (
          <div className="p-6">
            <MewsUniversityPanel userRole={user?.role || ""} />
          </div>
        )}

        {activeView === "scheduled-reports" && (
          <div className="p-6">
            <ScheduledReportsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : null}
              userEmail={user?.email || ""}
            />
          </div>
        )}

        {activeView === "custom-dashboard" && (
          <div className="p-6">
            <CustomDashboardBuilder
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : null}
            />
          </div>
        )}

        {activeView === "timeslots" && (
          <div className="p-6">
            <TimeSlotsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "staff-ops" && (
          <div className="p-6">
            <StaffOpsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "rev-protection" && (
          <div className="p-6">
            <RevenueProtectionPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "spaces" && (
          <div className="p-6">
            <SpacesPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "marketplace" && (
          <div className="p-6">
            <MarketplacePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "multi-rollup" && (
          <div className="p-6">
            <MultiPropertyRollupPanel hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""} />
          </div>
        )}
        {activeView === "chain-benchmark" && <ChainBenchmarkPanel onNavigate={navigate} />}

        {activeView === "currency" && (
          <div className="p-6">
            <CurrencyPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "b2b-agents" && (
          <div className="p-6">
            <AgentsB2BPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "security-owner" && (
          <div className="p-6">
            <SecurityOwnerPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "preauth" && (
          <div className="p-6">
            <PreAuthPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "chargeback" && (
          <div className="p-6">
            <ChargebackPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "web-push" && (
          <div className="p-6">
            <WebPushPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
              currentUser={user}
            />
          </div>
        )}

        {activeView === "pms-crs" && (
          <div className="p-6">
            <PmsCrsSyncPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "pms-pro" && (
          <div className="p-6">
            <PmsProPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "public-api" && (
          <div className="p-6">
            <PublicApiPortalPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "mid-stay" && (
          <div className="p-6">
            <MidStaySurveyPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "folio-live" && (
          <div className="p-6">
            <FolioLivePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ab-test" && (
          <div className="p-6">
            <ABTestPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "pre-arrival" && (
          <div className="p-6">
            <PreArrivalDripPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "menu-engineering" && (
          <div className="p-6">
            <MenuEngineeringPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "sr-voucher" && (
          <div className="p-6">
            <SRVoucherPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "folio-split" && (
          <div className="p-6">
            <FolioSplitPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "loyalty-auto" && (
          <div className="p-6">
            <LoyaltyAutoPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "late-checkout-offer" && (
          <div className="p-6">
            <LateCheckoutOfferPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ota-forecast" && (
          <div className="p-6">
            <OTAStopSellForecastPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "msg-templates" && (
          <div className="p-6">
            <MsgTemplatesPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "birthday" && (
          <div className="p-6">
            <BirthdayPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "low-stock" && (
          <div className="p-6">
            <LowStockPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "rebook" && (
          <div className="p-6">
            <RebookPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "stay-ext" && (
          <div className="p-6">
            <StayExtPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "long-stay" && (
          <div className="p-6">
            <LongStayPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "cancel-insurance" && (
          <div className="p-6">
            <CancelInsurancePanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "group-rooming-wiz" && (
          <div className="p-6">
            <GroupRoomingWizPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "tax-reports-v2" && (
          <div className="p-6">
            <TaxReportsV2Panel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "ci-slots" && (
          <div className="p-6">
            <CISlotsPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {activeView === "tier1-dashboard" && (
          <div className="p-6">
            <Tier1DashboardPanel
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
              hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
            />
          </div>
        )}

        {/* Maintenance — merged into Operasyon (ops-v2) tab "Misafir Talepleri" */}

        {/* Night Audit */}
        {activeView === "night-audit" && (
          <NightAuditPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Loyalty Program */}
        {activeView === "loyalty" && (
          <LoyaltyPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {activeView === "loyalty-tier" && (
          <LoyaltyTierPanel
            propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
          />
        )}

        {/* Duty Logbook */}
        {activeView === "logbook" && (
          <LogbookPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Occupancy Forecast */}
        {activeView === "forecast" && (
          <ForecastPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Pace Reports — STLY + Pickup + Source */}
        {activeView === "pace-reports" && (
          <PaceReports
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* AI Dynamic Pricing v2 (GPT-5.2) */}
        {activeView === "ai-pricing-v2" && (
          <AIPricingV2Panel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Rate Parity Heatmap */}
        {activeView === "parity-heatmap" && (
          <ParityHeatmapPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Morning Brief & Pricing Autopilot */}
        {activeView === "morning-brief" && (
          <MorningBriefPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Nightly Recap */}
        {activeView === "nightly-recap" && (
          <NightlyRecapPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Accounting Export */}
        {activeView === "accounting-export" && (
          <AccountingExportPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* RM Lab — Forecast Accuracy + Marketing Automation */}
        {activeView === "rm-lab" && (
          <RMLabPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Concierge Inbox — Admin view of AI guest chats */}
        {activeView === "concierge-inbox" && (
          <ConciergeInboxPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Group Requests & Allotments — B2B / corporate / wedding */}
        {activeView === "group-requests" && (
          <GroupRequestsPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Sustainability & ESG */}
        {activeView === "sustainability" && (
          <SustainabilityPanel
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "")}
            hotelName={properties?.find(p => p.id === activePropertyId)?.name || ""}
          />
        )}

        {/* Accounting */}
        {activeView === "accounting" && (
          <AccountingPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Point of Sale */}
        {activeView === "pos" && (
          <POSPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Payment Gateway */}
        {activeView === "payments" && (
          <PaymentsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Rate Manager */}
        {activeView === "rate-manager" && (
          <RateManagerPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* My Rates — Market-Pulse style 365-day grid with PMS Override + AI rate */}
        {activeView === "my-rates" && (
          <MyRatesPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Reports Centre */}
        {activeView === "reports-centre" && (
          <div className="p-6"><ReportsHub propertyId={activePropertyId} /></div>
        )}

        {/* Scheduled Reports */}
        {activeView === "scheduled-reports" && (
          <div className="p-6"><ScheduledReports propertyId={activePropertyId} /></div>
        )}

        {/* Mobile Companion */}
        {activeView === "mobile-companion" && (
          <div className="p-6"><MobileCompanion propertyId={activePropertyId} /></div>
        )}

        {/* Operations Hub */}
        {activeView === "operations-hub" && (
          <OperationsHubPanel properties={properties} activePropertyId={activePropertyId} user={user} />
        )}

        {/* Finance */}
        {activeView === "finance" && (
          <FinancePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Finance P&L */}
        {activeView === "finance-pl" && (
          <div className="p-6"><FinancePL propertyId={activePropertyId} /></div>
        )}

        {/* Lost & Found */}
        {activeView === "lost-found" && (
          <LostFoundPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Events & Meeting Rooms */}
        {activeView === "events" && (
          <EventsPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Booking Engine Admin */}
        {activeView === "booking-engine-admin" && (
          <BookingEngineAdmin properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Guest Satisfaction Surveys */}
        {activeView === "surveys" && (
          <SurveyPanel properties={properties} user={user} activePropertyId={activePropertyId} />
        )}

        {/* Shift Scheduler */}
        {activeView === "shift-scheduler" && (
          <div className="p-6"><ShiftScheduler propertyId={activePropertyId} /></div>
        )}

        {/* Reception Report */}
        {activeView === "reception-report" && (
          <div className="p-6"><ReceptionReport propertyId={activePropertyId} /></div>
        )}

        {/* Pass Over Duties */}
        {activeView === "pass-over" && (
          <div className="p-6"><PassOverDuties propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Compliance Register */}
        {activeView === "compliance" && (
          <div className="p-6"><ComplianceRegister propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Laundry Management — merged into Housekeeping hub */}
        {activeView === "laundry" && false && (
          <div className="p-6"><LaundryManagement propertyId={activePropertyId} user={user} permissions={permissions} /></div>
        )}

        {/* Payroll Management */}
        {activeView === "payroll" && (
          <div className="p-6"><PayrollManagement propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Expense Management */}
        {activeView === "expenses" && (
          <div className="p-6"><ExpenseManagement propertyId={activePropertyId} user={user} permissions={permissions} /></div>
        )}

        {/* Cash Flow Forecast */}
        {activeView === "cash-flow" && (
          <div className="p-6"><CashFlowForecast propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Arrivals Cockpit */}
        {activeView === "arrivals" && (
          <div className="p-6"><ArrivalsCockpit propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Staff Contracts */}
        {activeView === "contracts" && (
          <div className="p-6"><StaffContractsPanel propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Legal Documents & Consents */}
        {activeView === "legal-docs" && (
          <div className="p-6"><LegalDocumentsPanel user={user} /></div>
        )}

        {/* Onboarding Review (admin/manager) */}
        {activeView === "onboarding-admin" && (
          <div className="p-6"><StaffOnboardingAdminPanel user={user} /></div>
        )}

        {/* Payroll Rate Matrix */}
        {activeView === "rate-matrix" && (
          <div className="p-6"><PayrollRateMatrix user={user} /></div>
        )}

        {/* City Ledger (Corporate AR) */}
        {activeView === "city-ledger" && (
          <CityLedgerPanel user={user} />
        )}

        {activeView === "ar-recon" && <ArReconPanel />}

        {activeView === "digital-auth" && <DigitalAuthPanel propertyId={activePropertyId || "all"} />}
        {activeView === "allotments" && <AllotmentsPanel propertyId={activePropertyId || "all"} />}
        {activeView === "forecast-plans" && <ForecastPlansPanel propertyId={activePropertyId || "all"} />}
        {activeView === "intraday-reprice" && <IntradayRepricePanel propertyId={activePropertyId || "all"} />}
        {activeView === "restriction-advisor" && <RestrictionAdvisorPanel propertyId={activePropertyId || "all"} />}
        {activeView === "gap-filler" && <GapFillerPanel propertyId={activePropertyId || "all"} />}
        {activeView === "lost-demand" && <LostDemandPanel propertyId={activePropertyId || "all"} />}
        {activeView === "demo-leads" && <DemoLeadsPanel />}
        {activeView === "revenue-strategist" && <RevenueStrategistPanel propertyId={activePropertyId || "default"} />}
        {activeView === "min-rates" && <MinRateFloorsPanel propertyId={activePropertyId || "default"} />}
        {activeView === "discount-stack" && <DiscountStackPanel propertyId={activePropertyId || "default"} />}
        {activeView === "owner-rates" && <OwnerRatesAdminPanel propertyId={activePropertyId || "default"} />}
        {activeView === "owner-pulse-admin" && <OwnerPulseAdminPanel propertyId={activePropertyId || "default"} />}
        {activeView === "portfolio-board" && <PortfolioBoardPanel />}

        {activeView === "vcc-automation" && (
          <VccPanel propertyId={activePropertyId || "all"} />
        )}

        {activeView === "owner-summary" && (
          <OwnerSummaryPanel propertyId={activePropertyId || "all"} />
        )}

        {/* Tax Configuration */}
        {activeView === "tax-config" && (
          <TaxConfigPanel propertyId={activePropertyId} user={user} />
        )}

        {/* Deposit Policies */}
        {activeView === "deposit-policies" && (
          <DepositPolicyPanel propertyId={activePropertyId} user={user} />
        )}

        {/* Multi-Currency / FX */}
        {activeView === "currency-fx" && (
          <CurrencyFxPanel user={user} />
        )}

        {/* Rate Structure / OTA Mapping */}
        {activeView === "rate-structure" && (
          <RateStructurePanel propertyId={activePropertyId} user={user} />
        )}

        {/* Group Bookings */}
        {activeView === "group-bookings" && (
          <GroupBookingsPanel propertyId={activePropertyId} user={user} />
        )}

        {/* GDPR Data Rights */}
        {activeView === "gdpr" && (
          <GdprPanel user={user} />
        )}

        {/* Iter 156 — Top-10 Competitor Gap Features */}
        {activeView === "night-audit-close" && <div className="p-6"><NightAuditClosePanel activePropertyId={activePropertyId} /></div>}
        {activeView === "deposit-ledger" && <div className="p-6"><DepositLedgerPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "commission-recon" && <div className="p-6"><CommissionReconPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "gift-cards" && <div className="p-6"><GiftCardsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "review-sentiment" && <div className="p-6"><ReviewSentimentPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "guest-rfm" && <div className="p-6"><GuestRfmPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "preventive-maintenance" && <div className="p-6"><PreventiveMaintenancePanel activePropertyId={activePropertyId} /></div>}
        {activeView === "asset-register" && <div className="p-6"><AssetRegisterPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "cash-drawer" && <div className="p-6"><CashDrawerPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "two-factor-auth" && <div className="p-6"><TwoFactorAuthPanel /></div>}

        {/* Iter 157 — Remaining gaps: Revenue Health, IP Allowlist, PCI Card Vault */}
        {activeView === "revenue-health" && <div className="p-6"><RevenueHealthPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "ip-allowlist" && <div className="p-6"><IpAllowlistPanel /></div>}
        {activeView === "card-vault" && <div className="p-6"><CardVaultPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "deposit-automation" && <div className="p-6"><DepositAutomationPanel activePropertyId={activePropertyId} /></div>}

        {/* Iter 160 — Channel Manager MVP */}
        {activeView === "channel-restrictions" && <div className="p-6"><ChannelRestrictionsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-inbound" && <div className="p-6"><ChannelInboundPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-parity" && <div className="p-6"><ChannelParityPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "ota-health" && <div className="p-6"><OtaHealthPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-map-matrix" && <div className="p-6"><ChannelMappingsPanel activePropertyId={activePropertyId} /></div>}
        {activeView === "channel-sync-queue" && <div className="p-6"><SyncQueuePanel activePropertyId={activePropertyId} /></div>}

        {/* Iter 163 — Channel Manager Hub (Dashboard, Channels, Mappings, Rate Structure, Publish Jobs, Audit Logs, Benchmark, Profiles, Overrides) */}
        {activeView === "chmgr-hub" && <ChannelManagerHub activePropertyId={activePropertyId} />}
        {activeView?.startsWith?.("chmgr-hub:") && <ChannelManagerHub activePropertyId={activePropertyId} initialPanel={activeView.split(":")[1]} />}

        {/* Iter 165 — Group Blocks (Smart Rate Control lives inside Revenue → Pricing tab to avoid duplication) */}
        {activeView === "group-blocks" && <GroupBlocksPanel activePropertyId={activePropertyId} />}

        {/* Iter 165.4 — Laundry Settings (Providers + Contracts with Per Piece / Flat Rate / Hybrid pricing) */}
        {activeView === "laundry-settings" && false && <LaundrySettingsPanel activePropertyId={activePropertyId} />}

        {/* Onboarding Wizard */}
        {activeView === "onboarding" && (
          <div className="p-6">
            <OnboardingWizard
              propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : "default"}
              onClose={() => setActiveView("calendar")}
            />
          </div>
        )}

        {/* Unified Inbox */}
        {activeView === "unified-inbox" && (
          <UnifiedInboxPanel user={user} />
        )}

        {/* Bug Tracker */}
        {activeView === "bug-tracker" && (
          <div className="p-6"><BugTrackerPanel user={user} /></div>
        )}

        {/* Roles & Permissions */}
        {activeView === "roles-permissions" && (
          <div className="p-6"><RolesPermissionsPanel user={user} propertyId={activePropertyId && activePropertyId !== "all" ? activePropertyId : null} /></div>
        )}

        {/* Import Module */}
        {activeView === "import-module" && (
          <div className="p-6"><ImportModulePanel user={user} /></div>
        )}

        {/* Audit Trail */}
        {activeView === "audit-trail" && (
          <div className="p-6"><AuditTrailPanel user={user} /></div>
        )}

        {/* Collisions */}
        {activeView === "collisions" && (
          <div className="p-6"><CollisionsPanel user={user} onJumpToCalendar={(pid) => { if (pid) setActivePropertyId(pid); setActiveView("calendar"); }} /></div>
        )}

        {/* Profit OS */}
        {activeView === "profit-os" && (
          <div className="p-6"><ProfitOSPanel user={user} propertyId={activePropertyId} /></div>
        )}

        {/* Agentic AI Loops — Mews 2026 parity (Iter 286) */}
        {activeView === "ai-agents" && <AgentsPanel />}

        {/* Vacation Rental dedicated view — Eviivo/Lighthouse parity (Iter 286) */}
        {activeView === "vacation-rental" && <VacationRentalPanel />}

        {/* Dev Portal / Wholesaler / Lead Funnel — Iter 287 */}
        {activeView === "dev-portal" && <DevPortalAdminPanel />}
        {activeView === "wholesaler-hub" && (
          <WholesalerHubPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "lead-funnel" && (
          <LeadFunnelPanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        {activeView === "marketing-videos" && <MarketingVideosPanel />}
        {activeView === "brand-voice" && (
          <BrandVoicePanel propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")} />
        )}
        </Suspense>
      </main>

      {/* Powered By Footer */}
      {branding?.powered_by_visible && branding?.powered_by_text && (
        <div className="fixed bottom-0 left-0 lg:left-56 right-0 text-center py-1.5 border-t border-stone-100 bg-white/90 z-30" data-testid="powered-by-footer">
          <span className="text-[10px] text-stone-400">Powered by {branding.powered_by_text}</span>
        </div>
      )}

      <Toaster position="top-right" richColors />

      {/* Global "Report Maintenance Issue" FAB — available to ALL departments */}
      <GlobalReportIssueFAB propertyId={activePropertyId} currentUser={user} properties={properties} />

      {/* Global Revenue Action Feed — live pricing events drawer (single-branch only) */}
      <ActionFeedPanel propertyId={activePropertyId} />

      {/* PWA install banner (Batch 41) */}
      <PwaInstallButton />
    </div>
  );
};

function MainApp() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [permissions, setPermissions] = useState(null); // { permissions:Set, menu_permissions:Set, is_legacy_admin:bool }

  // Global axios 401 interceptor + unhandledrejection guard. When a token
  // expires, every authenticated component fires a 401 and CRA's error
  // overlay surfaces each one as a red runtime-error banner. Instead we:
  //   1. Clear auth state on the first 401 so the user is sent to login.
  //   2. Swallow CRA's unhandledrejection overlay for these specific errors
  //      (regular .catch handlers still receive the rejection).
  useEffect(() => {
    const id = axios.interceptors.response.use(
      (r) => r,
      (error) => {
        if (error?.response?.status === 401) {
          delete axios.defaults.headers.common["Authorization"];
          setUser(null);
          setPermissions(null);
          // Tag the error so the unhandledrejection guard below can recognise
          // and suppress only auth-related rejections.
          if (error && typeof error === "object") error.__auth_expired = true;
        }
        return Promise.reject(error);
      },
    );
    const onUnhandled = (ev) => {
      const reason = ev.reason;
      if (reason?.__auth_expired || reason?.response?.status === 401) {
        ev.preventDefault();
      }
    };
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      axios.interceptors.response.eject(id);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, []);

  const fetchPermissions = async () => {
    try {
      const { data } = await axios.get(`${API}/rbac/me/permissions`);
      setPermissions({
        permissions: new Set(data.permissions || []),
        menu_permissions: new Set(data.menu_permissions || []),
        is_legacy_admin: !!data.is_legacy_admin,
      });
    } catch {
      setPermissions({ permissions: new Set(), menu_permissions: new Set(), is_legacy_admin: false });
    }
  };

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const { data } = await axios.get(`${API}/auth/me`);
        setUser(data);
        await fetchPermissions();
      } catch (e) {
        setUser(null);
        setPermissions(null);
      } finally {
        setAuthChecking(false);
      }
    };
    checkAuth();
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
    if (userData.token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${userData.token}`;
    }
    fetchPermissions();
  };

  const handleLogout = async () => {
    try {
      await axios.post(`${API}/auth/logout`);
    } catch (e) {
      // ignore
    }
    delete axios.defaults.headers.common["Authorization"];
    setUser(null);
    setPermissions(null);
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center">
          <ArrowsClockwise size={28} className="mx-auto mb-3 animate-spin text-[#3E5245]" />
          <p className="text-sm text-stone-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    if (window.location.pathname !== "/login") {
      return <LandingPage />;
    }
    return (
      <>
        <LoginPage onLogin={handleLogin} />
        <Toaster position="top-right" richColors />
      </>
    );
  }

  return (
    <div className="App">
      <Dashboard user={user} onLogout={handleLogout} permissions={permissions} />
      <StaffOnboardingGate
        user={user}
        onActivated={async () => {
          try {
            const { data } = await axios.get(`${API}/auth/me`);
            setUser(data);
          } catch { /* silent */ }
        }}
      />
      <PendingLegalDocsGate user={user} />
    </div>
  );
}

function App() {
  if (window.location.pathname === "/reveniq" || window.location.pathname.startsWith("/reveniq/")) {
    return <ReveniqLanding />;
  }
  if (window.location.pathname === "/owner" || window.location.pathname.startsWith("/owner/")) {
    return <OwnerSelfServiceApp />;
  }
  if (window.location.pathname === "/agency" || window.location.pathname.startsWith("/agency/")) {
    return <AgencyPortalApp />;
  }
  if (window.location.pathname.startsWith("/events/")) {
    return <PublicEventPage />;
  }
  if (window.location.pathname === "/widget") {
    return <ReviewWidget />;
  }
  if (window.location.pathname === "/compare") {
    return <FeatureComparePage />;
  }
  if (window.location.pathname === "/book") {
    return <BookingEngine />;
  }
  if (window.location.pathname === "/book-space" || window.location.pathname.startsWith("/book-space/")) {
    return <SpacesPublicPage />;
  }
  if (window.location.pathname === "/review") {
    return <ReviewCollectionPage />;
  }
  if (window.location.pathname.startsWith("/kiosk/")) {
    return <KioskPWA />;
  }
  if (window.location.pathname.startsWith("/hk-mobile/")) {
    return <HousekeepingMobilePWA />;
  }
  if (window.location.pathname === "/checkout" || window.location.pathname.startsWith("/checkout/")) {
    return <SelfCheckoutPage />;
  }
  if (window.location.pathname.startsWith("/dashboard-share/")) {
    return <DashboardSharePage />;
  }
  if (window.location.pathname === "/room-key" || window.location.pathname.startsWith("/room-key/")) {
    return <RoomKeyPage />;
  }
  if (window.location.pathname === "/checkin" || window.location.pathname.startsWith("/checkin/")) {
    return <SelfCheckInPage />;
  }
  if (window.location.pathname.startsWith("/selfcheckin-v2/")) {
    return <SelfCheckInV2Page />;
  }
  if (window.location.pathname.startsWith("/tip/") || window.location.pathname === "/tip") {
    return <TipPage />;
  }
  if (window.location.pathname.startsWith("/portal/")) {
    return <GuestPortalV2Page />;
  }
  if (window.location.pathname === "/guest-portal") {
    return <GuestPortalPage />;
  }
  if (window.location.pathname.startsWith("/pay/")) {
    const payToken = window.location.pathname.split("/pay/")[1];
    return <GuestPaymentPage token={payToken} />;
  }
  if (window.location.pathname === "/turkish-pay") {
    return <TurkishPayPage />;
  }
  if (window.location.pathname.startsWith("/survey/")) {
    const token = window.location.pathname.split("/survey/")[1];
    return <GuestSurveyPage token={token} />;
  }
  if (window.location.pathname.startsWith("/register/")) {
    const token = window.location.pathname.split("/register/")[1];
    return <GuestRegistrationPage token={token} />;
  }
  if (window.location.pathname.startsWith("/contract/sign/")) {
    const token = window.location.pathname.split("/contract/sign/")[1];
    return <ContractSigningPage token={token} />;
  }
  if (window.location.pathname.startsWith("/feedback/")) {
    const token = window.location.pathname.split("/feedback/")[1];
    return <GuestFeedbackPage token={token} />;
  }
  if (window.location.pathname.startsWith("/checkin-kiosk/")) {
    const propertyId = window.location.pathname.split("/checkin-kiosk/")[1];
    return <CheckInKioskPage propertyId={propertyId} />;
  }
  if (window.location.pathname.startsWith("/room-help/")) {
    const parts = window.location.pathname.split("/room-help/")[1].split("/");
    return <GuestMaintenancePage propertyId={parts[0]} roomId={parts[1] || "unknown"} />;
  }
  if (window.location.pathname.startsWith("/authorize/")) {
    const token = window.location.pathname.split("/authorize/")[1];
    return <AuthorizeFormPage token={token} />;
  }
  if (window.location.pathname.startsWith("/offer/")) {
    const token = window.location.pathname.split("/offer/")[1];
    return <UpsellOfferPage token={token} />;
  }
  if (window.location.pathname.startsWith("/book/")) {
    const propertyId = window.location.pathname.split("/book/")[1];
    return <BookingWidgetPage propertyId={propertyId} />;
  }
  if (window.location.pathname.startsWith("/qr-order/")) {
    const parts = window.location.pathname.split("/qr-order/")[1].split("/");
    return <QROrderPage propertyId={parts[0]} outletId={parts[1]} />;
  }
  if (window.location.pathname.startsWith("/kiosk/")) {
    const parts = window.location.pathname.split("/kiosk/")[1].split("/");
    return <KioskPage propertyId={parts[0]} outletId={parts[1]} />;
  }
  if (window.location.pathname.startsWith("/mid-stay/")) {
    const inviteId = window.location.pathname.split("/mid-stay/")[1];
    return <MidStaySurveyPublicPage inviteId={inviteId} />;
  }
  return <MainApp />;
}

function AppWithLanguage() {
  return (
    <LanguageProvider>
      <App />
      <PWAInstall />
      <OfflineBanner />
    </LanguageProvider>
  );
}

export default AppWithLanguage;

