import { useEffect, useState, useCallback, useMemo, Suspense } from "react";
import "@/App.css";
import axios from "axios";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { LanguageProvider, useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { PWAInstall } from "@/components/PWAInstall";
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
  OpsV2Panel, HousekeepingHubPanel, GlitchLogPanel, SopsPanel, AutomationRulesPanel, TeamChatPanel, GuestCRM360Panel, ChannelManagerV2Panel, ForecastV2Panel, AnomalyPanel, TippingPanel, GuestPortalV2Panel,
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
  TimeSlotsPanel, StaffOpsPanel, RevenueProtectionPanel, SpacesPanel, MarketplacePanel, MultiPropertyRollupPanel,
  CurrencyPanel, AgentsB2BPanel, SecurityOwnerPanel, PreAuthPanel, ChargebackPanel,
  WebPushPanel, PmsCrsSyncPanel, PmsProPanel, PublicApiPortalPanel, MidStaySurveyPanel, FolioLivePanel,
  ABTestPanel, PreArrivalDripPanel, MenuEngineeringPanel, SRVoucherPanel, FolioSplitPanel,
  LoyaltyAutoPanel, LateCheckoutOfferPanel, OTAStopSellForecastPanel,
  MsgTemplatesPanel, BirthdayPanel, LowStockPanel, RebookPanel, StayExtPanel, LongStayPanel,
  CancelInsurancePanel, GroupRoomingWizPanel, TaxReportsV2Panel, CISlotsPanel, Tier1DashboardPanel,
  BookingEngineV2Panel, OwnerPortalPanel, SpaActivitiesPanel, LoyaltyTiersPanel,
  BudgetActualPanel, CompsetPanel, PartnerWebhooksPanel, AutomationAnalyticsPanel,
  MeetingsSalesPanel, FnbPosHubPanel, CarbonReportingV2Panel,
  AgencyPortalAdminPanel, WebConciergeAdminPanel, ReviewAgentPanel,
  OpenPricingPanel, BeachPosPanel, PublicEventsPanel, HurdleLrvPanel,
  AgentsPanel, VacationRentalPanel,
  DevPortalAdminPanel, WholesalerHubPanel, LeadFunnelPanel,
  MarketingVideosPanel,
  BrandVoicePanel,
  CampaignsPanel, GuestAppPanel, SmartLocksPanel, SetupWizardPanel, StockManagementPanel,
  AccountingPanel, POSPanel, PaymentsPanel, SurveyPanel, GuestJourneyPanel, MaintenancePanel,
  RateManagerPanel, MyRatesPanel, ReportsCentrePanel, ScheduledReports, MobileCompanion, EnhancedDashboard,
  ReportsHub, FinancePL, ShiftScheduler, ReceptionReport, PassOverDuties, ComplianceRegister,
  LaundryManagement, PayrollManagement, ExpenseManagement, CashFlowForecast,
  OperationsHubPanel, FinancePanel, StaffManagementPanel, MyTasksPanel, LostFoundPanel,
  EventsPanel, SettingsHubPanel, BookingEngineAdmin, BookingTimeline, RevenuePanel,
} from "./lazyPanels";
import GuestMaintenancePage from "./GuestMaintenancePage";
import BookingWidgetPage from "./BookingWidgetPage";
import GuestSurveyPage from "./GuestSurveyPage";
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
  Camera,
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
  ChartBar,
  TrendUp,
  TrendDown,
  Lightning,
  ForkKnife,
  ChartLineUp,
  Users,
  Trophy,
  Target,
  Brain,
  Fire,
  Smiley,
  SmileyMeh,
  SmileySad,
  CalendarBlank,
  PaperPlaneTilt as Send,
  Eye,
  PlugsConnected,
  Link,
  LinkBreak,
  CloudArrowUp,
  Database,
  Info,
  CaretRight,
  PaintBrush,
  Palette,
  Upload,
  Image,
  SignIn,
  SignOut,
  UserCircle,
  ShieldCheck,
  ClockCounterClockwise,
  UserPlus,
  Key,
  WebhookLogo,
  Gear,
  House,
  ArrowSquareOut,
  Code,
  CopySimple,
  Bed,
  Layout,
  Package,
  Scroll,
  WhatsappLogo,
  Robot,
  Headset,
  Envelope,
  AddressBook,
  Megaphone,
  MapPin,
  Wallet,
  Receipt,
  DeviceTablet,
  Tray,
  Broom,
  Moon,
  Crown,
  Notebook,
  ChartLine,
  Wrench,
  Globe,
  MagicWand,
  DeviceMobile,
  TShirt,
  Bug,
  Lock,
  Microphone,
  Calculator,
  Briefcase,
  CreditCard,
  Scales,
  Heart,
  Clock,
  QrCode,
  SquaresFour,
  Storefront,
  CurrencyDollar,
  BookOpen,
  GraduationCap,
  FileArrowDown,
  GridFour,
  Warning,
  Stack,
  Umbrella,
  Confetti,
  Funnel,
  FilmReel,
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

// Star Rating Component
const StarRating = ({ rating, size = 16 }) => {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          size={size}
          weight={star <= rating ? "fill" : "regular"}
          className={star <= rating ? "text-amber-400 star-glow" : "text-stone-200"}
        />
      ))}
    </div>
  );
};

// Platform Badge Component
const PlatformBadge = ({ platform }) => {
  const config = PLATFORMS[platform] || { name: platform, bg: "bg-gray-500" };
  return (
    <span
      className={`platform-pill ${config.bg} ${config.textDark ? "text-stone-900" : "text-white"}`}
      data-testid={`platform-badge-${platform}`}
    >
      {config.name}
    </span>
  );
};

// Stats Card Component
const StatsCard = ({ icon: Icon, label, value, subtext }) => (
  <motion.div
    initial={{ opacity: 0, y: 16 }}
    animate={{ opacity: 1, y: 0 }}
    className="border border-stone-200/80 rounded-xl bg-white p-5 flex flex-col gap-1.5 shadow-card card-hover relative overflow-hidden"
    data-testid={`stats-card-${label.toLowerCase().replace(/\s/g, '-')}`}
  >
    <div className="flex items-center justify-between">
      <span className="text-[11px] tracking-[0.15em] uppercase font-semibold text-stone-400">{label}</span>
      <div className="w-8 h-8 rounded-lg bg-stone-50 flex items-center justify-center">
        <Icon size={16} weight="regular" className="text-stone-400" />
      </div>
    </div>
    <div className="text-3xl font-semibold tracking-tight text-stone-900">{value}</div>
    {subtext && <div className="text-xs text-stone-500">{subtext}</div>}
  </motion.div>
);

// Review Card Component
const ReviewCard = ({ review, isSelected, onClick }) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={onClick}
      className={`px-4 py-3.5 cursor-pointer review-item ${
        isSelected ? "review-item-active" : ""
      }`}
      data-testid={`review-card-${review.id}`}
    >
      <div className="flex items-start gap-3">
        <img
          src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=f5f5f4&color=3E5245&bold=true`}
          alt={review.guest_name}
          className="w-9 h-9 rounded-full object-cover ring-1 ring-stone-200"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className="font-medium text-sm text-stone-900 truncate">{review.guest_name}</span>
            <PlatformBadge platform={review.platform} />
          </div>
          <StarRating rating={review.rating} size={12} />
          <p className="text-sm text-stone-500 line-clamp-2 mt-1.5 leading-relaxed">{review.review_text}</p>
          <div className="flex items-center justify-between mt-2">
            <span className="text-[11px] text-stone-400">
              {new Date(review.review_date).toLocaleDateString()}
            </span>
            {review.response_status === "pending" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-amber-600">
                <WarningCircle size={12} weight="fill" />
                Pending
              </span>
            )}
            {review.response_status === "pending_approval" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-blue-600">
                <ClockCounterClockwise size={12} weight="fill" />
                Awaiting Approval
              </span>
            )}
            {review.response_status === "rejected" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-red-600">
                <X size={12} weight="bold" />
                Rejected
              </span>
            )}
            {review.response_status === "responded" && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                <CheckCircle size={12} weight="fill" />
                Responded
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// AI Response Panel Component
const AIResponsePanel = ({ review, onResponseSubmit, isLoading, templateText, onTemplateApplied }) => {
  const [responseText, setResponseText] = useState("");
  const [tone, setTone] = useState("professional");
  const [language, setLanguage] = useState("auto");
  const [detectedLang, setDetectedLang] = useState(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [sentimentData, setSentimentData] = useState(null);
  const [suggestedTemplates, setSuggestedTemplates] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const LANGUAGES = [
    { code: "auto", name: "Auto-detect" },
    { code: "en", name: "English" },
    { code: "fr", name: "French" },
    { code: "de", name: "German" },
    { code: "es", name: "Spanish" },
    { code: "it", name: "Italian" },
    { code: "pt", name: "Portuguese" },
    { code: "zh", name: "Chinese" },
    { code: "ja", name: "Japanese" },
    { code: "ko", name: "Korean" },
    { code: "ar", name: "Arabic" },
    { code: "ru", name: "Russian" },
    { code: "nl", name: "Dutch" },
    { code: "th", name: "Thai" },
    { code: "hi", name: "Hindi" },
    { code: "tr", name: "Turkish" }
  ];

  useEffect(() => {
    if (review?.response_text) {
      setResponseText(review.response_text);
    } else {
      setResponseText("");
    }
    setSentimentData(review?.sentiment_analysis || null);
    setSuggestedTemplates([]);
    setDetectedLang(null);
    setLanguage("auto");
  }, [review]);

  // Auto-detect language when review changes
  useEffect(() => {
    if (review && !review.response_text) {
      detectLanguage();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [review?.id]);

  const detectLanguage = async () => {
    if (!review) return;
    setIsDetecting(true);
    try {
      const response = await axios.post(`${API}/reviews/${review.id}/detect-language`);
      setDetectedLang(response.data);
    } catch (error) {
      console.error("Language detection error:", error);
    } finally {
      setIsDetecting(false);
    }
  };

  const translateToEnglish = async () => {
    if (!responseText.trim()) return;
    setIsTranslating(true);
    try {
      const response = await axios.post(`${API}/reviews/translate`, {
        text: responseText,
        target_language: "en"
      });
      setResponseText(response.data.translated_text);
      toast.success("Translated to English");
    } catch (error) {
      toast.error("Translation failed");
    } finally {
      setIsTranslating(false);
    }
  };

  // Handle template application
  useEffect(() => {
    if (templateText && review) {
      // Replace {guest_name} placeholder with actual guest name
      const processedText = templateText.replace(/\{guest_name\}/g, review.guest_name);
      setResponseText(processedText);
      if (onTemplateApplied) onTemplateApplied();
    }
  }, [templateText, review, onTemplateApplied]);

  const analyzeSentiment = async () => {
    if (!review) return;
    setIsAnalyzing(true);
    try {
      const response = await axios.post(`${API}/reviews/${review.id}/analyze`);
      setSentimentData(response.data.analysis);
      setSuggestedTemplates(response.data.suggested_templates || []);
      
      // Auto-set tone based on analysis
      if (response.data.analysis?.suggested_tone) {
        setTone(response.data.analysis.suggested_tone);
      }
      
      toast.success("Sentiment analyzed!");
    } catch (error) {
      console.error("Error analyzing sentiment:", error);
      toast.error("Failed to analyze sentiment");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applyTemplate = (templateContent) => {
    const processedText = templateContent.replace(/\{guest_name\}/g, review?.guest_name || "Guest");
    setResponseText(processedText);
    toast.success("Template applied!");
  };

  const generateAIResponse = async () => {
    if (!review) return;
    
    setIsGenerating(true);
    try {
      const response = await axios.post(`${API}/reviews/generate-ai-response`, {
        review_id: review.id,
        tone: tone,
        language: language
      });
      
      // Typewriter effect
      const text = response.data.generated_text;
      let currentIndex = 0;
      setResponseText("");
      
      const typeWriter = setInterval(() => {
        if (currentIndex < text.length) {
          setResponseText(text.substring(0, currentIndex + 1));
          currentIndex++;
        } else {
          clearInterval(typeWriter);
          setIsGenerating(false);
        }
      }, 15);
      
      toast.success("AI response generated!");
    } catch (error) {
      console.error("Error generating AI response:", error);
      toast.error("Failed to generate AI response");
      setIsGenerating(false);
    }
  };

  const handleSubmit = async () => {
    if (!responseText.trim() || !review) return;
    
    try {
      await onResponseSubmit(review.id, responseText);
      toast.success("Response published successfully!");
      setIsEditing(false);
    } catch (error) {
      console.error("Error submitting response:", error);
      toast.error("Failed to publish response");
    }
  };

  if (!review) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="no-review-selected">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-stone-100 flex items-center justify-center mx-auto mb-4">
            <ChatText size={28} className="text-stone-300" />
          </div>
          <p className="text-sm font-medium text-stone-400">Select a review to view details and respond</p>
          <p className="text-xs text-stone-300 mt-1">Choose from the list on the left</p>
        </div>
      </div>
    );
  }

  const isResponded = review.response_status === "responded";

  return (
    <div className="flex-1 flex flex-col" data-testid="ai-response-panel">
      {/* Review Details */}
      <div className="border-b border-stone-100 pb-6 mb-6">
        <div className="flex items-start gap-4">
          <img
            src={review.guest_avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(review.guest_name)}&background=f5f5f4&color=3E5245&bold=true`}
            alt={review.guest_name}
            className="w-12 h-12 rounded-full object-cover ring-2 ring-stone-100"
          />
          <div className="flex-1">
            <div className="flex items-center gap-2.5 mb-1.5">
              <h3 className="text-lg font-semibold tracking-tight text-stone-900" data-testid="review-guest-name">
                {review.guest_name}
              </h3>
              <PlatformBadge platform={review.platform} />
              {review.response_status === "responded" ? (
                <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <CheckCircle size={12} className="mr-1" weight="fill" />
                  Responded
                </Badge>
              ) : review.response_status === "pending_approval" ? (
                <Badge className="bg-blue-50 text-blue-700 border border-blue-200">
                  <ClockCounterClockwise size={12} className="mr-1" weight="fill" />
                  Awaiting Approval
                </Badge>
              ) : review.response_status === "rejected" ? (
                <Badge className="bg-red-50 text-red-700 border border-red-200">
                  <X size={12} className="mr-1" weight="bold" />
                  Rejected
                </Badge>
              ) : (
                <Badge className="bg-amber-50 text-amber-700 border border-amber-200">
                  <WarningCircle size={12} className="mr-1" weight="fill" />
                  Pending
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-stone-500">
              <StarRating rating={review.rating} />
              {review.room_type && <span className="text-stone-300">|</span>}
              {review.room_type && <span>{review.room_type}</span>}
              {review.stay_date && <span className="text-stone-300">|</span>}
              {review.stay_date && <span>Stayed: {review.stay_date}</span>}
            </div>
          </div>
        </div>
        
        <div className="mt-4 bg-stone-50 rounded-xl p-5 relative" data-testid="review-text-container">
          <Quotes size={20} className="absolute top-3 left-3 text-stone-200" weight="fill" />
          <p className="text-stone-700 leading-relaxed pl-6 text-sm" data-testid="review-text">
            {review.review_text}
          </p>
          {/* Language Detection Badge */}
          {detectedLang && (
            <div className="mt-3 pt-3 border-t border-stone-200/60 flex items-center gap-2" data-testid="detected-language">
              <span className="text-[11px] text-stone-400">Detected language:</span>
              <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                {detectedLang.name}
              </span>
              {detectedLang.confidence && (
                <span className="text-[10px] text-stone-300">{Math.round(detectedLang.confidence * 100)}% confidence</span>
              )}
            </div>
          )}
          {isDetecting && (
            <div className="mt-3 pt-3 border-t border-stone-200/60 flex items-center gap-2">
              <ArrowsClockwise size={12} className="animate-spin text-stone-300" />
              <span className="text-[11px] text-stone-400">Detecting language...</span>
            </div>
          )}
        </div>

        {/* Sentiment Analysis Section */}
        <div className="mt-4 border border-stone-200 rounded-md bg-white p-4" data-testid="sentiment-section">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain size={18} className="text-[#3E5245]" />
              <span className="text-sm font-medium text-[#1C1917]">Smart Analysis</span>
            </div>
            {!sentimentData && (
              <button
                onClick={analyzeSentiment}
                disabled={isAnalyzing}
                className="text-sm text-[#3E5245] hover:text-[#2A3B30] flex items-center gap-1"
                data-testid="analyze-sentiment-btn"
              >
                {isAnalyzing ? <ArrowsClockwise size={14} className="animate-spin" /> : <Sparkle size={14} />}
                {isAnalyzing ? "Analyzing..." : "Analyze Review"}
              </button>
            )}
          </div>

          {sentimentData ? (
            <div className="space-y-3">
              {/* Sentiment Badge */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className={`${SENTIMENT_COLORS[sentimentData.sentiment]?.light || 'bg-stone-100'} px-3 py-1 rounded-full flex items-center gap-2`}>
                  {sentimentData.sentiment === 'positive' && <Smiley size={16} weight="fill" className="text-[#5A6B50]" />}
                  {sentimentData.sentiment === 'negative' && <SmileySad size={16} weight="fill" className="text-[#C05A44]" />}
                  {(sentimentData.sentiment === 'neutral' || sentimentData.sentiment === 'mixed') && <SmileyMeh size={16} weight="fill" className="text-[#57534E]" />}
                  <span className="text-sm font-medium capitalize">{sentimentData.sentiment}</span>
                </div>
                <Badge className={`${URGENCY_COLORS[sentimentData.urgency]} text-white`}>
                  {sentimentData.urgency} urgency
                </Badge>
                <Badge className="bg-[#E8EDE7] text-[#1C1917]">
                  Suggested: {sentimentData.suggested_tone}
                </Badge>
              </div>

              {/* Topics */}
              {sentimentData.topics?.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-[#57534E]">Topics:</span>
                  {sentimentData.topics.slice(0, 5).map((topic) => (
                    <span key={topic} className="text-xs bg-stone-100 px-2 py-0.5 rounded capitalize">{topic}</span>
                  ))}
                </div>
              )}

              {/* Key Issues & Praises */}
              <div className="grid grid-cols-2 gap-3">
                {sentimentData.key_issues?.length > 0 && (
                  <div className="text-sm">
                    <span className="text-[#C05A44] font-medium flex items-center gap-1 mb-1">
                      <TrendDown size={14} /> Issues
                    </span>
                    {sentimentData.key_issues.slice(0, 2).map((issue, idx) => (
                      <div key={idx} className="text-xs text-[#57534E] truncate">• {issue}</div>
                    ))}
                  </div>
                )}
                {sentimentData.key_praises?.length > 0 && (
                  <div className="text-sm">
                    <span className="text-[#5A6B50] font-medium flex items-center gap-1 mb-1">
                      <TrendUp size={14} /> Praises
                    </span>
                    {sentimentData.key_praises.slice(0, 2).map((praise, idx) => (
                      <div key={idx} className="text-xs text-[#57534E] truncate">• {praise}</div>
                    ))}
                  </div>
                )}
              </div>

              {/* Suggested Templates */}
              {suggestedTemplates.length > 0 && (
                <div className="pt-3 border-t border-stone-200">
                  <span className="text-xs font-medium text-[#1C1917] mb-2 block">Suggested Templates:</span>
                  <div className="flex gap-2 flex-wrap">
                    {suggestedTemplates.map((template) => (
                      <button
                        key={template.id}
                        onClick={() => applyTemplate(template.content)}
                        className="text-xs bg-[#E8EDE7] hover:bg-[#D5DDD3] px-2 py-1 rounded flex items-center gap-1 transition-colors"
                        data-testid={`suggested-template-${template.id}`}
                      >
                        <Copy size={12} />
                        {template.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-[#57534E]">
              Click "Analyze Review" to get AI-powered sentiment analysis and template suggestions.
            </p>
          )}
        </div>
      </div>

      {/* AI Response Generator */}
      <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-6 relative overflow-hidden" data-testid="ai-generator-panel">
        {/* Texture overlay */}
        <div 
          className="absolute inset-0 ai-texture-overlay pointer-events-none"
          style={{
            backgroundImage: "url('https://static.prod-images.emergentagent.com/jobs/f284f94c-059d-4721-a5db-def78e330cac/images/06790bb25ee93b714799620c98d82862ea6db3df67429246c55c3ae00c5536b8.png')",
            backgroundSize: "cover"
          }}
        />
        
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-emerald-800 flex items-center justify-center">
                <Sparkle size={14} className="text-white" weight="fill" />
              </div>
              <span className="text-sm font-semibold text-emerald-900 tracking-tight">AI Response Assistant</span>
            </div>
            
            {!isResponded && (
              <div className="flex items-center gap-2">
                <Select value={language} onValueChange={setLanguage} data-testid="language-select">
                  <SelectTrigger className="w-[130px] bg-white/80 border-emerald-200 text-xs h-8">
                    <SelectValue placeholder="Language" />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGES.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.code === "auto" && detectedLang ? `Auto (${detectedLang.name})` : lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={tone} onValueChange={setTone} data-testid="tone-select">
                  <SelectTrigger className="w-[120px] bg-white/80 border-emerald-200 text-xs h-8">
                    <SelectValue placeholder="Tone" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="friendly">Friendly</SelectItem>
                    <SelectItem value="apologetic">Apologetic</SelectItem>
                  </SelectContent>
                </Select>
                
                <button
                  onClick={generateAIResponse}
                  disabled={isGenerating || isLoading}
                  className="bg-emerald-800 text-white px-3.5 py-1.5 rounded-lg hover:bg-emerald-900 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center gap-1.5 text-sm font-medium"
                  data-testid="generate-ai-btn"
                >
                  {isGenerating ? (
                    <>
                      <ArrowsClockwise size={14} className="animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Sparkle size={14} weight="fill" />
                      Generate Reply
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {isGenerating && (
            <div className="ai-shimmer h-1.5 rounded-full mb-3" />
          )}

          <div className="relative">
            <Textarea
              value={responseText}
              onChange={(e) => setResponseText(e.target.value)}
              placeholder={isResponded ? "Response already submitted" : "AI-generated response will appear here. You can edit before publishing..."}
              className={`min-h-[160px] bg-white border-emerald-200/60 rounded-lg resize-none text-sm focus:ring-2 focus:ring-emerald-800/15 focus:border-emerald-300 ${isGenerating ? "cursor-blink" : ""}`}
              disabled={isResponded && !isEditing}
              data-testid="response-textarea"
            />
            
            {isResponded && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="absolute top-2 right-2 p-2 bg-white rounded-md border border-stone-200 hover:bg-stone-50 transition-colors"
                data-testid="edit-response-btn"
              >
                <PencilSimple size={16} className="text-[#57534E]" />
              </button>
            )}
          </div>

          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-2">
              {responseText.trim() && !isResponded && (
                <button
                  onClick={translateToEnglish}
                  disabled={isTranslating}
                  className="bg-white border border-emerald-200 text-emerald-800 px-2.5 py-1 rounded-lg hover:bg-emerald-50 transition-all text-xs font-medium flex items-center gap-1 disabled:opacity-50"
                  data-testid="translate-to-english-btn"
                >
                  {isTranslating ? (
                    <ArrowsClockwise size={12} className="animate-spin" />
                  ) : (
                    <span>EN</span>
                  )}
                  {isTranslating ? "Translating..." : "Translate to English"}
                </button>
              )}
              <p className="text-[11px] text-stone-400">
                {isResponded ? "This review has been responded to." : ""}
              </p>
            </div>
            
            {(!isResponded || isEditing) && (
              <div className="flex items-center gap-2">
                {isEditing && (
                  <button
                    onClick={() => {
                      setIsEditing(false);
                      setResponseText(review.response_text || "");
                    }}
                    className="bg-white border border-stone-200 text-stone-700 px-3 py-1.5 rounded-lg hover:bg-stone-50 transition-all text-sm"
                    data-testid="cancel-edit-btn"
                  >
                    Cancel
                  </button>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={!responseText.trim() || isLoading || isGenerating}
                  className="bg-emerald-800 text-white px-4 py-1.5 rounded-lg hover:bg-emerald-900 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center gap-1.5 text-sm font-medium"
                  data-testid="publish-response-btn"
                >
                  <PaperPlaneTilt size={14} weight="fill" />
                  {isEditing ? "Update" : "Publish"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="mt-4 px-4 py-2.5 bg-stone-50 border border-stone-100 rounded-lg">
        <p className="text-[11px] text-stone-400 flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400"></span>
          <strong className="text-stone-500">DEMO:</strong> Responses will sync to {PLATFORMS[review.platform]?.name || review.platform} in production.
        </p>
      </div>
    </div>
  );
};

// Notification Settings Component
const NotificationSettings = ({ isOpen, onClose }) => {
  const [settings, setSettings] = useState({
    email: "",
    notify_negative_reviews: true,
    negative_threshold: 2,
    enabled: false
  });
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
    }
  }, [isOpen]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API}/notifications/settings`);
      setSettings(response.data);
    } catch (error) {
      console.error("Error fetching notification settings:", error);
    }
  };

  const saveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/notifications/settings`, settings);
      toast.success("Notification settings saved!");
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const sendTestNotification = async () => {
    setIsTesting(true);
    try {
      await axios.post(`${API}/notifications/test`);
      toast.success("Test notification sent! Check your email.");
    } catch (error) {
      console.error("Error sending test notification:", error);
      toast.error(error.response?.data?.detail || "Failed to send test notification");
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <DialogContent className="sm:max-w-[500px]" data-testid="notification-settings-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <Bell size={20} weight="fill" className="text-[#3E5245]" />
          Email Notifications
        </DialogTitle>
      </DialogHeader>
      
      <div className="space-y-6 py-4">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 bg-[#FAF9F6] rounded-md border border-[#E7E5E4]">
          <div>
            <p className="font-medium text-[#1C1917]">Enable Notifications</p>
            <p className="text-sm text-[#57534E]">Receive alerts for negative reviews</p>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(checked) => setSettings(prev => ({ ...prev, enabled: checked }))}
            data-testid="notification-enable-switch"
          />
        </div>

        {/* Email Address */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-[#1C1917] flex items-center gap-2">
            <EnvelopeSimple size={16} className="text-[#57534E]" />
            Notification Email
          </label>
          <Input
            type="email"
            placeholder="hotel@example.com"
            value={settings.email}
            onChange={(e) => setSettings(prev => ({ ...prev, email: e.target.value }))}
            className="border-stone-200"
            data-testid="notification-email-input"
          />
          <p className="text-xs text-[#57534E]">Email address to receive negative review alerts</p>
        </div>

        {/* Rating Threshold */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-[#1C1917]">Alert Threshold</label>
          <Select
            value={String(settings.negative_threshold)}
            onValueChange={(value) => setSettings(prev => ({ ...prev, negative_threshold: parseInt(value) }))}
            data-testid="threshold-select"
          >
            <SelectTrigger className="border-stone-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 star only</SelectItem>
              <SelectItem value="2">1-2 stars (recommended)</SelectItem>
              <SelectItem value="3">1-3 stars</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-[#57534E]">Send alerts when reviews are at or below this rating</p>
        </div>

        {/* Info Banner */}
        <div className="p-3 bg-[#E8EDE7] border border-[#D5DDD3] rounded-md">
          <p className="text-xs text-[#57534E]">
            <strong>Note:</strong> In demo mode, notifications are logged but not actually sent. 
            Configure a valid Resend API key in production to enable real email delivery.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-stone-200">
          <button
            onClick={sendTestNotification}
            disabled={!settings.enabled || !settings.email || isTesting}
            className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors disabled:opacity-50 flex items-center gap-2"
            data-testid="test-notification-btn"
          >
            <TestTube size={16} />
            {isTesting ? "Sending..." : "Send Test"}
          </button>
          
          <button
            onClick={saveSettings}
            disabled={isSaving}
            className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
            data-testid="save-notification-settings-btn"
          >
            {isSaving ? (
              <>
                <ArrowsClockwise size={16} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircle size={16} weight="fill" />
                Save Settings
              </>
            )}
          </button>
        </div>
      </div>
    </DialogContent>
  );
};

// Templates Manager Component
const TemplatesManager = ({ isOpen, onClose, onSelectTemplate }) => {
  const [templates, setTemplates] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    category: "positive",
    content: "",
    tone: "professional"
  });

  const fetchTemplates = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await axios.get(`${API}/templates`);
      setTemplates(response.data);
    } catch (error) {
      console.error("Error fetching templates:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const seedTemplates = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/templates/seed`);
      if (response.data.seeded) {
        toast.success("Default templates loaded!");
        await fetchTemplates();
      }
    } catch (error) {
      console.error("Error seeding templates:", error);
    }
  }, [fetchTemplates]);

  useEffect(() => {
    if (isOpen) {
      seedTemplates();
      fetchTemplates();
    }
  }, [isOpen, fetchTemplates, seedTemplates]);

  const handleCreateOrUpdate = async () => {
    try {
      if (editingTemplate) {
        await axios.put(`${API}/templates/${editingTemplate.id}`, formData);
        toast.success("Template updated!");
      } else {
        await axios.post(`${API}/templates`, formData);
        toast.success("Template created!");
      }
      setShowCreateForm(false);
      setEditingTemplate(null);
      setFormData({ name: "", category: "positive", content: "", tone: "professional" });
      await fetchTemplates();
    } catch (error) {
      console.error("Error saving template:", error);
      toast.error("Failed to save template");
    }
  };

  const handleDelete = async (templateId) => {
    if (!window.confirm("Are you sure you want to delete this template?")) return;
    try {
      await axios.delete(`${API}/templates/${templateId}`);
      toast.success("Template deleted!");
      await fetchTemplates();
    } catch (error) {
      console.error("Error deleting template:", error);
      toast.error("Failed to delete template");
    }
  };

  const handleUseTemplate = async (template) => {
    try {
      await axios.post(`${API}/templates/${template.id}/use`);
      onSelectTemplate(template.content);
      onClose();
      toast.success("Template applied!");
    } catch (error) {
      console.error("Error using template:", error);
    }
  };

  const handleEdit = (template) => {
    setEditingTemplate(template);
    setFormData({
      name: template.name,
      category: template.category,
      content: template.content,
      tone: template.tone
    });
    setShowCreateForm(true);
  };

  const filteredTemplates = selectedCategory === "all" 
    ? templates 
    : templates.filter(t => t.category === selectedCategory);

  return (
    <DialogContent className="sm:max-w-[700px] max-h-[85vh]" data-testid="templates-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <FileText size={20} weight="fill" className="text-[#3E5245]" />
          Response Templates
        </DialogTitle>
      </DialogHeader>

      <Tabs defaultValue="browse" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-4">
          <TabsTrigger value="browse" data-testid="templates-browse-tab">Browse Templates</TabsTrigger>
          <TabsTrigger 
            value="create" 
            onClick={() => {
              setShowCreateForm(true);
              setEditingTemplate(null);
              setFormData({ name: "", category: "positive", content: "", tone: "professional" });
            }}
            data-testid="templates-create-tab"
          >
            {editingTemplate ? "Edit Template" : "Create New"}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="browse" className="space-y-4">
          {/* Category Filter */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setSelectedCategory("all")}
              className={`px-3 py-1 rounded-full text-sm transition-colors ${
                selectedCategory === "all" 
                  ? "bg-[#3E5245] text-white" 
                  : "bg-[#E8EDE7] text-[#1C1917] hover:bg-[#D5DDD3]"
              }`}
              data-testid="category-filter-all"
            >
              All
            </button>
            {Object.entries(TEMPLATE_CATEGORIES).map(([key, cat]) => (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={`px-3 py-1 rounded-full text-sm transition-colors flex items-center gap-1 ${
                  selectedCategory === key 
                    ? `${cat.color} text-white` 
                    : "bg-[#E8EDE7] text-[#1C1917] hover:bg-[#D5DDD3]"
                }`}
                data-testid={`category-filter-${key}`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Templates List */}
          <ScrollArea className="h-[400px] pr-4">
            {isLoading ? (
              <div className="flex items-center justify-center h-32">
                <ArrowsClockwise size={24} className="animate-spin text-[#57534E]" />
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="text-center py-8 text-[#57534E]">
                <FileText size={32} className="mx-auto mb-2 opacity-50" />
                <p>No templates found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredTemplates.map((template) => (
                  <motion.div
                    key={template.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border border-stone-200 rounded-md p-4 bg-white hover:shadow-sm transition-shadow"
                    data-testid={`template-card-${template.id}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h4 className="font-medium text-[#1C1917]">{template.name}</h4>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`${TEMPLATE_CATEGORIES[template.category]?.color || "bg-gray-500"} text-white px-2 py-0.5 rounded text-xs`}>
                            {TEMPLATE_CATEGORIES[template.category]?.name || template.category}
                          </span>
                          <span className="text-xs text-[#57534E]">
                            <Tag size={12} className="inline mr-1" />
                            {template.tone}
                          </span>
                          <span className="text-xs text-[#57534E]">
                            Used {template.usage_count || 0} times
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleEdit(template)}
                          className="p-2 hover:bg-stone-100 rounded-md transition-colors"
                          title="Edit"
                          data-testid={`edit-template-${template.id}`}
                        >
                          <PencilSimple size={16} className="text-[#57534E]" />
                        </button>
                        <button
                          onClick={() => handleDelete(template.id)}
                          className="p-2 hover:bg-red-50 rounded-md transition-colors"
                          title="Delete"
                          data-testid={`delete-template-${template.id}`}
                        >
                          <Trash size={16} className="text-[#C05A44]" />
                        </button>
                      </div>
                    </div>
                    <p className="text-sm text-[#57534E] line-clamp-3 mb-3">
                      {template.content}
                    </p>
                    <button
                      onClick={() => handleUseTemplate(template)}
                      className="bg-[#3E5245] text-white px-3 py-1.5 rounded-md text-sm hover:bg-[#2A3B30] transition-colors flex items-center gap-1"
                      data-testid={`use-template-${template.id}`}
                    >
                      <Copy size={14} />
                      Use This Template
                    </button>
                  </motion.div>
                ))}
              </div>
            )}
          </ScrollArea>
        </TabsContent>

        <TabsContent value="create" className="space-y-4">
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-[#1C1917] block mb-1">Template Name</label>
              <Input
                placeholder="e.g., Thank You - Great Stay"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className="border-stone-200"
                data-testid="template-name-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-[#1C1917] block mb-1">Category</label>
                <Select
                  value={formData.category}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, category: value }))}
                  data-testid="template-category-select"
                >
                  <SelectTrigger className="border-stone-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TEMPLATE_CATEGORIES).map(([key, cat]) => (
                      <SelectItem key={key} value={key}>{cat.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-[#1C1917] block mb-1">Tone</label>
                <Select
                  value={formData.tone}
                  onValueChange={(value) => setFormData(prev => ({ ...prev, tone: value }))}
                  data-testid="template-tone-select"
                >
                  <SelectTrigger className="border-stone-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="friendly">Friendly</SelectItem>
                    <SelectItem value="apologetic">Apologetic</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-[#1C1917] block mb-1">
                Template Content
                <span className="text-xs text-[#57534E] ml-2">Use {"{guest_name}"} as placeholder</span>
              </label>
              <Textarea
                placeholder="Dear {guest_name},&#10;&#10;Thank you for your feedback..."
                value={formData.content}
                onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                className="min-h-[200px] border-stone-200"
                data-testid="template-content-textarea"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreateForm(false);
                  setEditingTemplate(null);
                  setFormData({ name: "", category: "positive", content: "", tone: "professional" });
                }}
                className="bg-white border border-stone-200 text-[#1C1917] px-4 py-2 rounded-md hover:bg-stone-50 transition-colors"
                data-testid="cancel-template-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateOrUpdate}
                disabled={!formData.name || !formData.content}
                className="bg-[#3E5245] text-white px-4 py-2 rounded-md hover:bg-[#2A3B30] transition-colors disabled:opacity-50 flex items-center gap-2"
                data-testid="save-template-btn"
              >
                <Plus size={16} />
                {editingTemplate ? "Update Template" : "Create Template"}
              </button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </DialogContent>
  );
};

// User Management Panel
const UserManagementPanel = ({ currentUser }) => {
  const [users, setUsers] = useState([]);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", password: "", name: "", role: "receptionist", department: "front_desk" });
  const [isLoading, setIsLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/users`);
      setUsers(data);
    } catch (e) {
      console.error("Failed to load users");
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleAddUser = async () => {
    if (!newUser.email || !newUser.password || !newUser.name) {
      toast.error("Fill in all fields");
      return;
    }
    setIsLoading(true);
    try {
      await axios.post(`${API}/auth/register`, newUser);
      toast.success("User created!");
      setShowAddUser(false);
      setNewUser({ email: "", password: "", name: "", role: "receptionist", department: "front_desk" });
      fetchUsers();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteUser = async (userId) => {
    try {
      await axios.delete(`${API}/users/${userId}`);
      toast.success("User removed");
      fetchUsers();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const roleColors = {
    admin: "bg-red-50 text-red-700 border-red-200",
    manager: "bg-blue-50 text-blue-700 border-blue-200",
    receptionist: "bg-emerald-50 text-emerald-700 border-emerald-200"
  };

  const deptNames = {
    front_desk: "Front Desk", management: "Management", housekeeping: "Housekeeping",
    food_beverage: "Food & Beverage", maintenance: "Maintenance", spa_wellness: "Spa & Wellness", concierge: "Concierge"
  };

  return (
    <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto" data-testid="user-management-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-stone-900">
          <Users size={20} className="text-[#3E5245]" />
          Team Management
        </DialogTitle>
      </DialogHeader>
      
      <div className="space-y-4 mt-2">
        {currentUser.role === "admin" && (
          <button
            onClick={() => setShowAddUser(!showAddUser)}
            className="w-full bg-[#3E5245] text-white py-2 rounded-lg hover:bg-[#2A3B30] transition-all flex items-center justify-center gap-2 text-sm font-medium"
            data-testid="add-user-btn"
          >
            <UserPlus size={16} />
            Add Team Member
          </button>
        )}
        
        {showAddUser && (
          <div className="bg-stone-50 rounded-xl p-4 border border-stone-200 space-y-3" data-testid="add-user-form">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-stone-500 mb-1 block">Name</label>
                <Input value={newUser.name} onChange={(e) => setNewUser(p => ({ ...p, name: e.target.value }))} placeholder="John Smith" className="border-stone-200 h-9 text-sm" data-testid="new-user-name" />
              </div>
              <div>
                <label className="text-xs font-medium text-stone-500 mb-1 block">Email</label>
                <Input type="email" value={newUser.email} onChange={(e) => setNewUser(p => ({ ...p, email: e.target.value }))} placeholder="john@hotel.com" className="border-stone-200 h-9 text-sm" data-testid="new-user-email" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-500 mb-1 block">Password</label>
              <Input type="password" value={newUser.password} onChange={(e) => setNewUser(p => ({ ...p, password: e.target.value }))} placeholder="Min 6 characters" className="border-stone-200 h-9 text-sm" data-testid="new-user-password" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-stone-500 mb-1 block">Role</label>
                <Select value={newUser.role} onValueChange={(v) => setNewUser(p => ({ ...p, role: v }))} data-testid="new-user-role">
                  <SelectTrigger className="border-stone-200 h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="receptionist">Receptionist</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium text-stone-500 mb-1 block">Department</label>
                <Select value={newUser.department} onValueChange={(v) => setNewUser(p => ({ ...p, department: v }))} data-testid="new-user-department">
                  <SelectTrigger className="border-stone-200 h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="front_desk">Front Desk</SelectItem>
                    <SelectItem value="management">Management</SelectItem>
                    <SelectItem value="housekeeping">Housekeeping</SelectItem>
                    <SelectItem value="food_beverage">Food & Beverage</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                    <SelectItem value="spa_wellness">Spa & Wellness</SelectItem>
                    <SelectItem value="concierge">Concierge</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <button onClick={handleAddUser} disabled={isLoading} className="w-full bg-emerald-700 text-white py-2 rounded-lg hover:bg-emerald-800 transition-all text-sm font-medium disabled:opacity-50" data-testid="confirm-add-user-btn">
              {isLoading ? "Creating..." : "Create Account"}
            </button>
          </div>
        )}
        
        <div className="space-y-2">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between p-3 bg-white border border-stone-200 rounded-lg" data-testid={`user-item-${u.id}`}>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-stone-100 flex items-center justify-center">
                  <UserCircle size={20} className="text-stone-400" />
                </div>
                <div>
                  <div className="text-sm font-medium text-stone-900">{u.name}</div>
                  <div className="text-[11px] text-stone-400">{u.email} · {deptNames[u.department] || u.department}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${roleColors[u.role] || "bg-stone-50 text-stone-600"}`}>
                  {u.role}
                </span>
                {currentUser.role === "admin" && u.email !== currentUser.email && (
                  <button onClick={() => handleDeleteUser(u.id)} className="text-stone-400 hover:text-red-500 transition-colors" data-testid={`delete-user-${u.id}`}>
                    <Trash size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </DialogContent>
  );
};

// Approval Queue Panel
const ApprovalQueuePanel = ({ onReviewUpdate }) => {
  const [pendingReviews, setPendingReviews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [rejectNotes, setRejectNotes] = useState({});

  const fetchPending = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await axios.get(`${API}/reviews/pending-approval`);
      setPendingReviews(data);
    } catch (e) {
      console.error("Failed to fetch pending approvals");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchPending(); }, [fetchPending]);

  const handleAction = async (reviewId, action, notes) => {
    try {
      await axios.post(`${API}/reviews/${reviewId}/approve`, { action, notes });
      toast.success(action === "approve" ? "Response approved & published!" : "Response rejected");
      fetchPending();
      if (onReviewUpdate) onReviewUpdate();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  return (
    <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto" data-testid="approval-queue-dialog">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-stone-900">
          <ShieldCheck size={20} className="text-[#3E5245]" />
          Approval Queue
          {pendingReviews.length > 0 && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              {pendingReviews.length} pending
            </span>
          )}
        </DialogTitle>
      </DialogHeader>

      {isLoading ? (
        <div className="py-8 text-center">
          <ArrowsClockwise size={24} className="mx-auto mb-2 animate-spin text-stone-300" />
          <p className="text-sm text-stone-400">Loading...</p>
        </div>
      ) : pendingReviews.length === 0 ? (
        <div className="py-8 text-center" data-testid="no-pending-approvals">
          <ShieldCheck size={32} className="mx-auto mb-2 text-emerald-300" />
          <p className="text-sm text-stone-400">No responses pending approval</p>
        </div>
      ) : (
        <div className="space-y-4 mt-2">
          {pendingReviews.map((review) => (
            <div key={review.id} className="border border-stone-200 rounded-xl overflow-hidden" data-testid={`approval-item-${review.id}`}>
              <div className="bg-stone-50 px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <PlatformBadge platform={review.platform} />
                  <span className="text-sm font-medium text-stone-900">{review.guest_name}</span>
                  <StarRating rating={review.rating} size={12} />
                </div>
                {review.drafted_by && (
                  <span className="text-[11px] text-stone-400">Drafted by: {review.drafted_by}</span>
                )}
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold">Guest Review</span>
                  <p className="text-sm text-stone-600 mt-1">{review.review_text}</p>
                </div>
                <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-100">
                  <span className="text-[10px] uppercase tracking-wider text-emerald-600 font-semibold">Proposed Response</span>
                  <p className="text-sm text-emerald-900 mt-1">{review.response_text}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAction(review.id, "approve")}
                    className="flex-1 bg-emerald-700 text-white py-2 rounded-lg hover:bg-emerald-800 transition-all text-sm font-medium flex items-center justify-center gap-1.5"
                    data-testid={`approve-btn-${review.id}`}
                  >
                    <CheckCircle size={14} weight="fill" />
                    Approve & Publish
                  </button>
                  <button
                    onClick={() => handleAction(review.id, "reject", rejectNotes[review.id] || "")}
                    className="flex-1 bg-white border border-red-200 text-red-600 py-2 rounded-lg hover:bg-red-50 transition-all text-sm font-medium flex items-center justify-center gap-1.5"
                    data-testid={`reject-btn-${review.id}`}
                  >
                    <X size={14} />
                    Reject
                  </button>
                </div>
                <Input
                  placeholder="Optional notes for rejection..."
                  value={rejectNotes[review.id] || ""}
                  onChange={(e) => setRejectNotes(p => ({ ...p, [review.id]: e.target.value }))}
                  className="border-stone-200 h-8 text-xs"
                  data-testid={`rejection-notes-${review.id}`}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </DialogContent>
  );
};


// ==================== API CONNECTION PANEL ====================
const ApiConnectionPanel = ({ user }) => {
  const [apiKeys, setApiKeys] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showNewKey, setShowNewKey] = useState(false);
  const [newKeyLabel, setNewKeyLabel] = useState("");
  const [createdKey, setCreatedKey] = useState(null);
  const [copiedKeyId, setCopiedKeyId] = useState(null);

  const fetchKeys = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await axios.get(`${API}/api-keys`);
      setApiKeys(data);
    } catch (e) {
      toast.error("Failed to load API keys");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchKeys(); }, [fetchKeys]);

  const handleCreateKey = async () => {
    if (!newKeyLabel.trim()) { toast.error("Enter a label for the key"); return; }
    try {
      const { data } = await axios.post(`${API}/api-keys`, { label: newKeyLabel.trim() });
      setCreatedKey(data);
      setNewKeyLabel("");
      setShowNewKey(false);
      fetchKeys();
      toast.success("API key created!");
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create key");
    }
  };

  const handleDeleteKey = async (keyId) => {
    try {
      await axios.delete(`${API}/api-keys/${keyId}`);
      toast.success("API key deleted");
      if (createdKey?.id === keyId) setCreatedKey(null);
      fetchKeys();
    } catch (e) {
      toast.error("Failed to delete key");
    }
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedKeyId(id);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedKeyId(null), 2000);
  };

  return (
    <div className="p-5" data-testid="api-connection-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="api-panel-title">API Connection</h2>
          <p className="text-sm text-stone-500 mt-0.5">Manage API keys for integrating with MyHotelBox.com</p>
        </div>
        {user?.role === "admin" && (
          <button
            onClick={() => setShowNewKey(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800 transition-colors"
            data-testid="create-api-key-btn"
          >
            <Plus size={14} /> New API Key
          </button>
        )}
      </div>

      {/* New Key Form */}
      {showNewKey && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="bg-white border border-stone-200 rounded-lg p-4 mb-4" data-testid="new-key-form">
          <h3 className="text-sm font-medium text-stone-700 mb-3">Create New API Key</h3>
          <div className="flex gap-2">
            <Input
              placeholder="Key label (e.g., MyHotelBox Production)"
              value={newKeyLabel}
              onChange={(e) => setNewKeyLabel(e.target.value)}
              className="flex-1 text-sm"
              data-testid="api-key-label-input"
            />
            <button onClick={handleCreateKey} className="px-4 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800 transition-colors" data-testid="confirm-create-key-btn">Create</button>
            <button onClick={() => { setShowNewKey(false); setNewKeyLabel(""); }} className="px-3 py-2 border border-stone-300 text-stone-600 text-xs rounded-lg hover:bg-stone-50 transition-colors">Cancel</button>
          </div>
        </motion.div>
      )}

      {/* Created Key Alert */}
      {createdKey && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4" data-testid="created-key-alert">
          <div className="flex items-start gap-2">
            <WarningCircle size={18} className="text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-amber-800 mb-1">Save this key now — it won't be shown again</p>
              <div className="flex items-center gap-2 bg-white border border-amber-300 rounded px-3 py-2">
                <code className="text-xs text-stone-800 flex-1 break-all font-mono" data-testid="new-key-value">{createdKey.key}</code>
                <button onClick={() => copyToClipboard(createdKey.key, "new")} className="text-stone-500 hover:text-emerald-700 flex-shrink-0" data-testid="copy-new-key-btn">
                  {copiedKeyId === "new" ? <CheckCircle size={16} className="text-emerald-600" /> : <Copy size={16} />}
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* API Documentation Card */}
      <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Info size={16} className="text-stone-500" />
          <h3 className="text-sm font-medium text-stone-700">Quick Start</h3>
        </div>
        <div className="space-y-2 text-xs text-stone-600">
          <p>Include your API key in requests as a Bearer token:</p>
          <div className="bg-stone-900 text-stone-100 rounded-lg p-3 font-mono text-[11px] leading-relaxed">
            <span className="text-emerald-400">GET</span> /api/reviews<br />
            <span className="text-stone-500">Authorization:</span> <span className="text-amber-300">Bearer rhk_your_api_key</span><br />
            <span className="text-stone-500">Content-Type:</span> application/json
          </div>
          <p className="mt-2">
            <a href={`${BACKEND_URL}/api/docs`} target="_blank" rel="noreferrer" className="text-emerald-700 hover:underline font-medium inline-flex items-center gap-1" data-testid="swagger-docs-link">
              View Full API Documentation <ArrowSquareOut size={12} />
            </a>
          </p>
        </div>
      </div>

      {/* Keys List */}
      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : apiKeys.length === 0 ? (
        <div className="text-center py-12 bg-white border border-stone-200 rounded-lg" data-testid="no-keys-message">
          <Key size={32} className="mx-auto text-stone-300 mb-3" />
          <p className="text-sm text-stone-500">No API keys yet</p>
          <p className="text-xs text-stone-400 mt-1">Create a key to start integrating</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="api-keys-list">
          {apiKeys.map((k) => (
            <div key={k.id} className="bg-white border border-stone-200 rounded-lg p-4 flex items-center gap-4 hover:border-stone-300 transition-colors" data-testid={`api-key-${k.id}`}>
              <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                <Key size={16} className="text-emerald-700" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-stone-800">{k.label}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${k.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                    {k.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <code className="text-xs text-stone-500 font-mono">{k.key_masked}</code>
                  <span className="text-[10px] text-stone-400">Created {new Date(k.created_at).toLocaleDateString()}</span>
                  {k.request_count > 0 && <span className="text-[10px] text-stone-400">{k.request_count} requests</span>}
                </div>
              </div>
              <button onClick={() => copyToClipboard(k.key_masked, k.id)} className="text-stone-400 hover:text-stone-600 p-1.5" data-testid={`copy-key-${k.id}`}>
                {copiedKeyId === k.id ? <CheckCircle size={14} className="text-emerald-600" /> : <Copy size={14} />}
              </button>
              {user?.role === "admin" && (
                <button onClick={() => handleDeleteKey(k.id)} className="text-stone-400 hover:text-red-500 p-1.5" data-testid={`delete-key-${k.id}`}>
                  <Trash size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== WEBHOOKS PANEL ====================
const WebhooksPanel = ({ user }) => {
  const [webhooks, setWebhooks] = useState([]);
  const [availableEvents, setAvailableEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showNewWebhook, setShowNewWebhook] = useState(false);
  const [newWebhook, setNewWebhook] = useState({ url: "", label: "", events: [] });
  const [expandedId, setExpandedId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResults, setTestResults] = useState({});
  const [deliveryLogs, setDeliveryLogs] = useState({});
  const [loadingLogs, setLoadingLogs] = useState({});

  const fetchWebhooks = useCallback(async () => {
    setIsLoading(true);
    try {
      const [whRes, evRes] = await Promise.all([
        axios.get(`${API}/webhooks`),
        axios.get(`${API}/webhooks/events`)
      ]);
      setWebhooks(whRes.data);
      setAvailableEvents(evRes.data);
    } catch (e) {
      toast.error("Failed to load webhooks");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchWebhooks(); }, [fetchWebhooks]);

  const handleCreate = async () => {
    if (!newWebhook.url.trim()) { toast.error("Enter a webhook URL"); return; }
    try {
      await axios.post(`${API}/webhooks`, newWebhook);
      toast.success("Webhook created!");
      setShowNewWebhook(false);
      setNewWebhook({ url: "", label: "", events: [] });
      fetchWebhooks();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create webhook");
    }
  };

  const handleToggle = async (wh) => {
    try {
      await axios.put(`${API}/webhooks/${wh.id}`, { is_active: !wh.is_active });
      fetchWebhooks();
      toast.success(`Webhook ${wh.is_active ? "paused" : "activated"}`);
    } catch (e) {
      toast.error("Failed to update webhook");
    }
  };

  const handleDelete = async (whId) => {
    try {
      await axios.delete(`${API}/webhooks/${whId}`);
      toast.success("Webhook deleted");
      fetchWebhooks();
    } catch (e) {
      toast.error("Failed to delete webhook");
    }
  };

  const toggleEvent = (eventId) => {
    setNewWebhook(prev => ({
      ...prev,
      events: prev.events.includes(eventId) ? prev.events.filter(e => e !== eventId) : [...prev.events, eventId]
    }));
  };

  const copySecret = (secret, id) => {
    navigator.clipboard.writeText(secret);
    setCopiedId(id);
    toast.success("Secret copied");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleTestWebhook = async (whId) => {
    setTestingId(whId);
    setTestResults(prev => ({ ...prev, [whId]: null }));
    try {
      const { data } = await axios.post(`${API}/webhooks/${whId}/test`);
      setTestResults(prev => ({ ...prev, [whId]: data }));
      if (data.success) {
        toast.success(`Webhook test passed (${data.response_time_ms}ms)`);
      } else {
        toast.error(data.message);
      }
      fetchWebhooks();
      fetchDeliveryLog(whId);
    } catch (e) {
      setTestResults(prev => ({ ...prev, [whId]: { success: false, message: "Request failed" } }));
      toast.error("Failed to test webhook");
    } finally {
      setTestingId(null);
    }
  };

  const fetchDeliveryLog = async (whId) => {
    setLoadingLogs(prev => ({ ...prev, [whId]: true }));
    try {
      const { data } = await axios.get(`${API}/webhooks/${whId}/deliveries`);
      setDeliveryLogs(prev => ({ ...prev, [whId]: data }));
    } catch (e) {
      toast.error("Failed to load delivery log");
    } finally {
      setLoadingLogs(prev => ({ ...prev, [whId]: false }));
    }
  };

  // Fetch logs when expanding
  const handleExpand = (whId) => {
    const isExpanding = expandedId !== whId;
    setExpandedId(isExpanding ? whId : null);
    if (isExpanding && !deliveryLogs[whId]) {
      fetchDeliveryLog(whId);
    }
  };

  return (
    <div className="p-5" data-testid="webhooks-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="webhooks-panel-title">Webhooks</h2>
          <p className="text-sm text-stone-500 mt-0.5">Receive real-time notifications when events happen</p>
        </div>
        {user?.role === "admin" && (
          <button
            onClick={() => setShowNewWebhook(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800 transition-colors"
            data-testid="create-webhook-btn"
          >
            <Plus size={14} /> New Webhook
          </button>
        )}
      </div>

      {/* New Webhook Form */}
      {showNewWebhook && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="bg-white border border-stone-200 rounded-lg p-4 mb-4" data-testid="new-webhook-form">
          <h3 className="text-sm font-medium text-stone-700 mb-3">Create New Webhook</h3>
          <div className="space-y-3">
            <Input
              placeholder="Label (e.g., MyHotelBox Sync)"
              value={newWebhook.label}
              onChange={(e) => setNewWebhook(p => ({ ...p, label: e.target.value }))}
              className="text-sm"
              data-testid="webhook-label-input"
            />
            <Input
              placeholder="https://myhotelbox.com/api/webhooks/reviews"
              value={newWebhook.url}
              onChange={(e) => setNewWebhook(p => ({ ...p, url: e.target.value }))}
              className="text-sm font-mono"
              data-testid="webhook-url-input"
            />
            <div>
              <p className="text-xs font-medium text-stone-600 mb-2">Events to subscribe (leave empty for all)</p>
              {/* Group events by category */}
              {Object.entries(
                availableEvents.reduce((groups, ev) => {
                  const cat = ev.category || "general";
                  if (!groups[cat]) groups[cat] = [];
                  groups[cat].push(ev);
                  return groups;
                }, {})
              ).map(([category, events]) => (
                <div key={category} className="mb-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-stone-400 mb-1.5">{category}</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {events.map((ev) => (
                      <label key={ev.id} className="flex items-center gap-2 text-xs text-stone-600 p-1.5 rounded hover:bg-stone-50 cursor-pointer" data-testid={`event-${ev.id}`}>
                        <input
                          type="checkbox"
                          checked={newWebhook.events.includes(ev.id)}
                          onChange={() => toggleEvent(ev.id)}
                          className="rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
                        />
                        <span>{ev.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 pt-1">
              <button onClick={handleCreate} className="px-4 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800 transition-colors" data-testid="confirm-create-webhook-btn">Create Webhook</button>
              <button onClick={() => { setShowNewWebhook(false); setNewWebhook({ url: "", label: "", events: [] }); }} className="px-3 py-2 border border-stone-300 text-stone-600 text-xs rounded-lg hover:bg-stone-50 transition-colors">Cancel</button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Webhook Info Card */}
      <div className="bg-stone-50 border border-stone-200 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Info size={16} className="text-stone-500" />
          <h3 className="text-sm font-medium text-stone-700">How Webhooks Work</h3>
        </div>
        <div className="text-xs text-stone-600 space-y-1">
          <p>When an event occurs (new review, response approved, etc.), we send a POST request to your URL with the event payload.</p>
          <p>Each webhook includes a <code className="bg-stone-200 px-1 rounded text-[11px]">X-Webhook-Secret</code> header for verification.</p>
        </div>
      </div>

      {/* Webhooks List */}
      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : webhooks.length === 0 ? (
        <div className="text-center py-12 bg-white border border-stone-200 rounded-lg" data-testid="no-webhooks-message">
          <Code size={32} className="mx-auto text-stone-300 mb-3" />
          <p className="text-sm text-stone-500">No webhooks configured</p>
          <p className="text-xs text-stone-400 mt-1">Set up webhooks to receive real-time updates</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="webhooks-list">
          {webhooks.map((wh) => (
            <div key={wh.id} className="bg-white border border-stone-200 rounded-lg hover:border-stone-300 transition-colors" data-testid={`webhook-${wh.id}`}>
              <div className="flex items-center gap-4 p-4">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${wh.is_active ? "bg-emerald-50" : "bg-stone-100"}`}>
                  <Code size={16} className={wh.is_active ? "text-emerald-700" : "text-stone-400"} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-stone-800">{wh.label || "Unnamed Webhook"}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${wh.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                      {wh.is_active ? "Active" : "Paused"}
                    </span>
                  </div>
                  <code className="text-xs text-stone-500 font-mono block mt-0.5 truncate">{wh.url}</code>
                </div>
                <div className="flex items-center gap-1">
                  <Switch
                    checked={wh.is_active}
                    onCheckedChange={() => handleToggle(wh)}
                    data-testid={`toggle-webhook-${wh.id}`}
                  />
                  <button onClick={() => handleExpand(wh.id)} className="text-stone-400 hover:text-stone-600 p-1.5" data-testid={`expand-webhook-${wh.id}`}>
                    <CaretRight size={14} className={`transition-transform ${expandedId === wh.id ? "rotate-90" : ""}`} />
                  </button>
                  {user?.role === "admin" && (
                    <button onClick={() => handleDelete(wh.id)} className="text-stone-400 hover:text-red-500 p-1.5" data-testid={`delete-webhook-${wh.id}`}>
                      <Trash size={14} />
                    </button>
                  )}
                </div>
              </div>
              {/* Expanded Details */}
              <AnimatePresence>
                {expandedId === wh.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="px-4 pb-4 pt-0 border-t border-stone-100">
                      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                        <div>
                          <span className="text-stone-400 block mb-1">Secret</span>
                          <div className="flex items-center gap-1.5">
                            <code className="text-stone-600 font-mono bg-stone-50 px-2 py-1 rounded text-[11px]">{wh.secret?.slice(0, 8)}...{wh.secret?.slice(-4)}</code>
                            <button onClick={() => copySecret(wh.secret, wh.id)} className="text-stone-400 hover:text-emerald-600" data-testid={`copy-secret-${wh.id}`}>
                              {copiedId === wh.id ? <CheckCircle size={12} className="text-emerald-600" /> : <Copy size={12} />}
                            </button>
                          </div>
                        </div>
                        <div>
                          <span className="text-stone-400 block mb-1">Created</span>
                          <span className="text-stone-600">{new Date(wh.created_at).toLocaleDateString()} by {wh.created_by}</span>
                        </div>
                        <div>
                          <span className="text-stone-400 block mb-1">Deliveries</span>
                          <span className="text-stone-600">{wh.delivery_count} sent, {wh.failure_count} failed</span>
                        </div>
                        <div>
                          <span className="text-stone-400 block mb-1">Last Triggered</span>
                          <span className="text-stone-600">{wh.last_triggered ? new Date(wh.last_triggered).toLocaleString() : "Never"}</span>
                        </div>
                      </div>
                      <div className="mt-3">
                        <span className="text-stone-400 text-xs block mb-1.5">Subscribed Events</span>
                        <div className="flex flex-wrap gap-1">
                          {wh.events?.map(ev => (
                            <span key={ev} className={`text-[10px] px-2 py-0.5 rounded-full ${ev.startsWith("booking.") ? "bg-blue-50 text-blue-700" : "bg-stone-100 text-stone-600"}`}>{ev}</span>
                          ))}
                        </div>
                      </div>
                      {/* Test Webhook Button & Result */}
                      <div className="mt-4 pt-3 border-t border-stone-100">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleTestWebhook(wh.id)}
                            disabled={testingId === wh.id}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-stone-800 text-white text-xs font-medium rounded-lg hover:bg-stone-900 transition-colors disabled:opacity-50"
                            data-testid={`test-webhook-${wh.id}`}
                          >
                            {testingId === wh.id ? (
                              <><ArrowsClockwise size={12} className="animate-spin" /> Sending...</>
                            ) : (
                              <><Lightning size={12} /> Send Test Ping</>
                            )}
                          </button>
                          <span className="text-[10px] text-stone-400">Sends a sample review.test event to your endpoint</span>
                        </div>
                        {testResults[wh.id] && (
                          <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className={`mt-2 p-3 rounded-lg text-xs flex items-center gap-2 ${testResults[wh.id].success ? "bg-emerald-50 border border-emerald-200" : "bg-red-50 border border-red-200"}`} data-testid={`test-result-${wh.id}`}>
                            {testResults[wh.id].success ? (
                              <CheckCircle size={14} className="text-emerald-600 flex-shrink-0" />
                            ) : (
                              <WarningCircle size={14} className="text-red-500 flex-shrink-0" />
                            )}
                            <div>
                              <span className={`font-medium ${testResults[wh.id].success ? "text-emerald-800" : "text-red-800"}`}>
                                {testResults[wh.id].success ? "Delivered" : "Failed"}
                              </span>
                              {testResults[wh.id].status_code && (
                                <span className="text-stone-500 ml-2">HTTP {testResults[wh.id].status_code}</span>
                              )}
                              {testResults[wh.id].response_time_ms && (
                                <span className="text-stone-500 ml-2">{testResults[wh.id].response_time_ms}ms</span>
                              )}
                              {!testResults[wh.id].success && testResults[wh.id].message && (
                                <span className="text-red-600 ml-2">{testResults[wh.id].message}</span>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </div>
                      {/* Delivery Log */}
                      <div className="mt-3 pt-3 border-t border-stone-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium text-stone-600">Delivery Log</span>
                          <button onClick={() => fetchDeliveryLog(wh.id)} className="text-[10px] text-stone-400 hover:text-stone-600 flex items-center gap-1" data-testid={`refresh-logs-${wh.id}`}>
                            <ArrowsClockwise size={10} className={loadingLogs[wh.id] ? "animate-spin" : ""} /> Refresh
                          </button>
                        </div>
                        {loadingLogs[wh.id] ? (
                          <div className="flex justify-center py-3"><ArrowsClockwise size={14} className="animate-spin text-stone-400" /></div>
                        ) : !deliveryLogs[wh.id] || deliveryLogs[wh.id].length === 0 ? (
                          <p className="text-[10px] text-stone-400 py-2">No deliveries yet. Send a test ping to see logs here.</p>
                        ) : (
                          <div className="space-y-1 max-h-48 overflow-y-auto custom-scrollbar" data-testid={`delivery-log-${wh.id}`}>
                            {deliveryLogs[wh.id].map((d) => (
                              <div key={d.id} className={`flex items-center gap-2 text-[10px] px-2 py-1.5 rounded ${d.success ? "bg-emerald-50/50" : "bg-red-50/50"}`}>
                                {d.success ? <CheckCircle size={10} className="text-emerald-600 flex-shrink-0" /> : <WarningCircle size={10} className="text-red-500 flex-shrink-0" />}
                                <span className="text-stone-600 font-medium">{d.event}</span>
                                {d.status_code && <span className="text-stone-400">HTTP {d.status_code}</span>}
                                {d.response_time_ms && <span className="text-stone-400">{d.response_time_ms}ms</span>}
                                {d.error && <span className="text-red-500">{d.error}</span>}
                                <span className="text-stone-400 ml-auto">{new Date(d.timestamp).toLocaleTimeString()}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ==================== INTEGRATION GUIDE PANEL ====================
const IntegrationGuidePanel = () => {
  const [guide, setGuide] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [copiedSnippet, setCopiedSnippet] = useState(null);

  useEffect(() => {
    const fetchGuide = async () => {
      try {
        const { data } = await axios.get(`${API}/integration-guide`);
        setGuide(data);
      } catch (e) {
        console.error("Failed to load guide");
      } finally {
        setIsLoading(false);
      }
    };
    fetchGuide();
  }, []);

  const copyCode = (code, id) => {
    navigator.clipboard.writeText(code);
    setCopiedSnippet(id);
    setTimeout(() => setCopiedSnippet(null), 2000);
  };

  if (isLoading) return <div className="flex justify-center py-20"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>;
  if (!guide) return <div className="p-5 text-stone-500">Failed to load guide</div>;

  const curlFetchReviews = `curl -X GET "${guide.base_url}/reviews?property_id=YOUR_PROPERTY_ID" \\
  -H "Authorization: Bearer rhk_your_api_key" \\
  -H "Content-Type: application/json"`;

  const curlGenerateResponse = `curl -X POST "${guide.base_url}/reviews/generate-ai-response" \\
  -H "Authorization: Bearer rhk_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "review_id": "REVIEW_ID",
    "language": "en",
    "tone": "professional"
  }'`;

  const webhookHandler = `// MyHotelBox.com — Webhook Handler Example (Node.js)
app.post('/api/integrations/review-hub/webhook', (req, res) => {
  const secret = req.headers['x-webhook-secret'];
  if (secret !== process.env.REVIEW_HUB_WEBHOOK_SECRET) {
    return res.status(401).json({ error: 'Invalid secret' });
  }
  
  const { event, data } = req.body;
  
  switch (event) {
    case 'review.created':
      // New review received — show in MyHotelBox dashboard
      console.log('New review from', data.platform, 'by', data.guest_name);
      // Match with booking: find guest by name + property
      break;
    case 'review.responded':
      // AI response was published to platform
      break;
    case 'rating.low':
      // Alert: bad review received — notify hotel manager
      break;
  }
  
  res.json({ received: true });
});`;

  const pythonHandler = `# MyHotelBox.com — Webhook Handler Example (Python/FastAPI)
@app.post("/api/integrations/review-hub/webhook")
async def handle_review_webhook(request: Request):
    secret = request.headers.get("X-Webhook-Secret")
    if secret != os.environ["REVIEW_HUB_WEBHOOK_SECRET"]:
        raise HTTPException(status_code=401, detail="Invalid secret")
    
    body = await request.json()
    event = body["event"]
    data = body["data"]
    
    if event == "review.created":
        # New review — match with booking by guest name + property
        guest = data["guest_name"]
        property_id = data["property_id"]
        # Find matching booking in your database
        pass
    elif event == "rating.low":
        # Bad review alert — notify hotel manager
        pass
    
    return {"received": True}`;

  return (
    <div className="p-5 max-w-4xl" data-testid="integration-guide-panel">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-stone-800" data-testid="guide-title">MyHotelBox Integration Guide</h2>
        <p className="text-sm text-stone-500 mt-0.5">Step-by-step instructions to connect Review Hub to your MyHotelBox.com software</p>
      </div>

      {/* Steps */}
      <div className="space-y-3 mb-6">
        {guide.steps.map((s) => (
          <div key={s.step} className="flex gap-3 bg-white border border-stone-200 rounded-lg p-4" data-testid={`guide-step-${s.step}`}>
            <div className="w-7 h-7 rounded-full bg-emerald-700 text-white flex items-center justify-center text-xs font-bold flex-shrink-0">{s.step}</div>
            <div>
              <h3 className="text-sm font-medium text-stone-800">{s.title}</h3>
              <p className="text-xs text-stone-500 mt-0.5">{s.description}</p>
            </div>
          </div>
        ))}
      </div>

      {/* API Endpoints Reference */}
      <div className="bg-white border border-stone-200 rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-stone-700 mb-3 flex items-center gap-2"><Database size={14} /> Available API Endpoints</h3>
        <div className="space-y-1.5">
          {guide.api_examples.endpoints.map((ep, i) => (
            <div key={i} className="flex items-center gap-2 text-xs py-1.5 border-b border-stone-50 last:border-0">
              <span className={`font-mono font-bold px-1.5 py-0.5 rounded text-[10px] ${ep.method === "GET" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{ep.method}</span>
              <code className="font-mono text-stone-700">{ep.path}</code>
              <span className="text-stone-400 ml-auto">{ep.description}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Code Snippets */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-stone-700 flex items-center gap-2"><Code size={14} /> Code Examples</h3>

        {[
          { id: "fetch", label: "Fetch Reviews from Review Hub", code: curlFetchReviews, lang: "bash" },
          { id: "generate", label: "Generate AI Response", code: curlGenerateResponse, lang: "bash" },
          { id: "webhook-node", label: "Webhook Handler (Node.js)", code: webhookHandler, lang: "javascript" },
          { id: "webhook-python", label: "Webhook Handler (Python)", code: pythonHandler, lang: "python" }
        ].map(({ id, label, code }) => (
          <div key={id} className="bg-stone-900 rounded-lg overflow-hidden" data-testid={`code-snippet-${id}`}>
            <div className="flex items-center justify-between px-3 py-2 bg-stone-800">
              <span className="text-[11px] text-stone-400 font-medium">{label}</span>
              <button onClick={() => copyCode(code, id)} className="text-stone-500 hover:text-white text-[10px] flex items-center gap-1" data-testid={`copy-snippet-${id}`}>
                {copiedSnippet === id ? <><CheckCircle size={10} className="text-emerald-400" /> Copied</> : <><Copy size={10} /> Copy</>}
              </button>
            </div>
            <pre className="p-3 text-[11px] text-stone-200 font-mono leading-relaxed overflow-x-auto"><code>{code}</code></pre>
          </div>
        ))}
      </div>

      {/* Webhook Payload Example */}
      <div className="mt-4 bg-stone-900 rounded-lg overflow-hidden" data-testid="webhook-payload-example">
        <div className="flex items-center justify-between px-3 py-2 bg-stone-800">
          <span className="text-[11px] text-stone-400 font-medium">Webhook Payload Example (review.created)</span>
          <button onClick={() => copyCode(JSON.stringify(guide.webhook_payload_example, null, 2), "payload")} className="text-stone-500 hover:text-white text-[10px] flex items-center gap-1" data-testid="copy-payload">
            {copiedSnippet === "payload" ? <><CheckCircle size={10} className="text-emerald-400" /> Copied</> : <><Copy size={10} /> Copy</>}
          </button>
        </div>
        <pre className="p-3 text-[11px] text-stone-200 font-mono leading-relaxed overflow-x-auto"><code>{JSON.stringify(guide.webhook_payload_example, null, 2)}</code></pre>
      </div>

      {/* Webhook Headers */}
      <div className="mt-4 bg-stone-50 border border-stone-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-stone-700 mb-2 flex items-center gap-2"><Info size={14} /> Webhook Request Headers</h3>
        <div className="space-y-1">
          {Object.entries(guide.webhook_headers).map(([key, val]) => (
            <div key={key} className="flex gap-2 text-xs">
              <code className="text-stone-600 font-mono font-medium">{key}:</code>
              <span className="text-stone-500">{val}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Embeddable Widget */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mt-4" data-testid="widget-embed-section">
        <div className="flex items-center gap-2 mb-2">
          <Code size={16} className="text-emerald-700" />
          <h3 className="text-sm font-semibold text-emerald-800">Embeddable Reviews Widget</h3>
        </div>
        <p className="text-xs text-emerald-700 mb-3">Embed the Review Hub directly into MyHotelBox.com dashboard using an iframe. Your staff can view and respond to reviews without leaving your software.</p>
        <div className="bg-stone-900 rounded-lg p-3 font-mono text-[11px] leading-relaxed text-stone-200 overflow-x-auto">
          <span className="text-stone-500">&lt;!-- Add to your MyHotelBox dashboard --&gt;</span><br/>
          <span className="text-emerald-400">&lt;iframe</span><br/>
          &nbsp;&nbsp;<span className="text-amber-300">src</span>=<span className="text-stone-300">"{guide.base_url.replace('/api', '')}/widget?api_key=YOUR_API_KEY&property_id=YOUR_PROPERTY_ID"</span><br/>
          &nbsp;&nbsp;<span className="text-amber-300">width</span>=<span className="text-stone-300">"100%"</span><br/>
          &nbsp;&nbsp;<span className="text-amber-300">height</span>=<span className="text-stone-300">"700"</span><br/>
          &nbsp;&nbsp;<span className="text-amber-300">frameBorder</span>=<span className="text-stone-300">"0"</span><br/>
          &nbsp;&nbsp;<span className="text-amber-300">style</span>=<span className="text-stone-300">"border-radius: 8px;"</span><br/>
          <span className="text-emerald-400">/&gt;</span>
        </div>
        <div className="mt-2 flex items-center gap-3">
          <span className="text-[10px] text-emerald-700">Supports: <code className="bg-emerald-100 px-1 rounded">?theme=dark</code> for dark mode</span>
          <span className="text-[10px] text-emerald-700"><code className="bg-emerald-100 px-1 rounded">?property_id=xxx</code> to filter by property</span>
        </div>
      </div>
    </div>
  );
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

  const menuSections = [
    {
      label: "Overview",
      color: "text-stone-500",
      items: [
        { id: "dashboard", icon: House, name: t("nav.dashboard"), testId: "dashboard-btn" },
        { id: "my-tasks", icon: Target, name: "My tasks", testId: "my-tasks-btn" },
        { id: "calendar", icon: CalendarBlank, name: "Calendar", testId: "sidebar-calendar" },
        { id: "availability-calendar", icon: CalendarBlank, name: "Müsaitlik Takvimi", testId: "availability-calendar-btn" },
        { id: "tier1-dashboard", icon: ChartBar, name: "Master dashboard", testId: "tier1-dashboard-btn" },
        { id: "morning-brief", icon: ChartLine, name: "Morning brief", testId: "morning-brief-btn" },
        { id: "nightly-recap", icon: Moon, name: "Nightly recap", testId: "nightly-recap-btn" },
        { id: "help-guide", icon: BookOpen, name: "Help & user guide", testId: "help-guide-btn" },
        { id: "mews-university", icon: GraduationCap, name: "HotelBox Academy", testId: "mews-university-btn" },
        { id: "scheduled-reports", icon: FileArrowDown, name: "Planlı Raporlar", testId: "scheduled-reports-btn" },
        { id: "custom-dashboard", icon: GridFour, name: "Custom Dashboard", testId: "custom-dashboard-btn" },
      ],
    },
    {
      label: "Mobile & Apps",
      color: "text-emerald-600",
      items: [
        { id: "mobile-companion", icon: DeviceMobile, name: "Mobil görünüm (PWA)", testId: "mobile-companion-btn" },
        { id: "guest-app", icon: MapPin, name: t("nav.guest_app"), testId: "guest-app-btn" },
        { id: "kiosk-launch", icon: DeviceTablet, name: "Self-service kiosk", testId: "kiosk-launch-btn", launchUrl: true },
        { id: "self-checkin-v2", icon: SignIn, name: "Pre-arrival check-in", testId: "self-checkin-v2-btn" },
        { id: "self-checkin-auto", icon: Lightning, name: "Auto pre-arrival trigger", testId: "self-checkin-auto-btn" },
        { id: "voice-concierge", icon: Microphone, name: "Voice concierge (Whisper)", testId: "voice-concierge-btn" },
        { id: "whatsapp-voice", icon: WhatsappLogo, name: "WhatsApp sesli concierge", testId: "whatsapp-voice-btn" },
        { id: "concierge-inbox", icon: Robot, name: "Concierge inbox (AI)", testId: "concierge-inbox-btn" },
        { id: "lock-sdk", icon: Lock, name: "Hardware lock SDK", testId: "lock-sdk-btn" },
        { id: "marketplace", icon: Sparkle, name: "Marketplace (3rd-party apps)", testId: "marketplace-btn" },
      ],
    },
    {
      label: "Reservations",
      color: "text-stone-500",
      items: [
        { id: "arrivals", icon: Bed, name: "Arrivals cockpit", testId: "arrivals-btn" },
        { id: "unified-inbox", icon: Tray, name: "Unified inbox", testId: "unified-inbox-btn" },
        { id: "walkin", icon: UserPlus, name: "Walk-in", testId: "walkin-btn" },
        { id: "no-show", icon: Bell, name: "No-show charges", testId: "no-show-btn" },
        { id: "late-checkout", icon: Clock, name: "Late check-out", testId: "late-checkout-btn" },
        { id: "ci-slots", icon: Clock, name: "Check-in time slots", testId: "ci-slots-btn" },
        { id: "reception-report", icon: Notebook, name: "Reception report", testId: "reception-report-btn" },
        { id: "pass-over", icon: Notebook, name: "Pass-over duties", testId: "pass-over-btn" },
        { id: "logbook", icon: Notebook, name: t("nav.logbook"), testId: "logbook-btn" },
        { id: "lost-found", icon: Eye, name: "Lost & found", testId: "lost-found-btn" },
        { id: "collisions", icon: ShieldCheck, name: "Collisions", testId: "collisions-btn" },
        { id: "booking", icon: Bed, name: t("nav.booking"), testId: "booking-engine-btn" },
        { id: "booking-engine-admin", icon: Globe, name: "Booking engine setup", testId: "booking-engine-admin-btn" },
        { id: "booking-engine-v2", icon: Package, name: "Booking engine v2 (paket & upsell)", testId: "booking-engine-v2-btn" },
        { id: "rate-structure", icon: Tag, name: "Rate plans", testId: "rate-structure-btn" },
        { id: "promo-codes", icon: Tag, name: t("nav.promo_codes"), testId: "promo-codes-btn" },
        { id: "add-ons", icon: Package, name: t("nav.add_ons"), testId: "add-ons-btn" },
        { id: "policies", icon: Scroll, name: t("nav.policies"), testId: "policies-btn" },
        { id: "group-bookings", icon: Users, name: "Group bookings", testId: "group-bookings-btn" },
        { id: "group-blocks", icon: Users, name: "Group blocks", testId: "group-blocks-btn" },
        { id: "group-rooming", icon: FileText, name: "Group rooming import", testId: "group-rooming-btn" },
        { id: "group-rooming-wiz", icon: Users, name: "Group rooming wizard", testId: "group-rooming-wiz-btn" },
        { id: "group-requests", icon: Users, name: "Group requests", testId: "group-requests-btn" },
        { id: "stay-ext", icon: Plus, name: "Stay extension", testId: "stay-ext-btn" },
        { id: "rebook", icon: ArrowsClockwise, name: "Quick re-booking", testId: "rebook-btn" },
        { id: "long-stay", icon: CalendarBlank, name: "Long-stay discount", testId: "long-stay-btn" },
        { id: "cancel-insurance", icon: ShieldCheck, name: "Cancellation insurance", testId: "cancel-insurance-btn" },
        { id: "website-templates", icon: Layout, name: "Website templates", testId: "website-templates-btn" },
        { id: "customize-template", icon: PaintBrush, name: "Template customizer", testId: "customize-template-btn" },
      ],
    },
    {
      label: "Guests",
      color: "text-stone-500",
      items: [
        { id: "guest-profiles", icon: AddressBook, name: t("nav.guest_profiles"), testId: "guest-profiles-btn" },
        { id: "crm-360", icon: Users, name: "Guest CRM 360", testId: "crm-360-btn" },
        { id: "guest-journey", icon: SignIn, name: t("nav.guest_journey"), testId: "guest-journey-btn" },
        { id: "guest-rfm", icon: Target, name: "RFM segmentation", testId: "guest-rfm-btn" },
        { id: "guest-prefs", icon: Heart, name: "Guest preferences", testId: "guest-prefs-btn" },
        { id: "guest-portal-v2", icon: Users, name: "Guest self-modify", testId: "guest-portal-v2-btn" },
        { id: "loyalty", icon: Crown, name: t("nav.loyalty"), testId: "loyalty-btn" },
        { id: "loyalty-tier", icon: Trophy, name: "Tier engine", testId: "loyalty-tier-btn" },
        { id: "loyalty-tiers-v2", icon: Crown, name: "Sadakat seviyeleri (Silver/Gold/Plat)", testId: "loyalty-tiers-v2-btn" },
        { id: "loyalty-v2", icon: Crown, name: "Loyalty referrals & packages", testId: "loyalty-v2-btn" },
        { id: "external-loyalty", icon: Crown, name: "Zincir Loyalty (Bonvoy/Honors)", testId: "external-loyalty-btn" },
        { id: "loyalty-auto", icon: Crown, name: "Loyalty auto-tier", testId: "loyalty-auto-btn" },
        { id: "birthday", icon: Sparkle, name: "Birthday discounts", testId: "birthday-btn" },
        { id: "service-recovery", icon: Notebook, name: "Service recovery", testId: "service-recovery-btn" },
        { id: "sr-voucher", icon: Tag, name: "Recovery vouchers", testId: "sr-voucher-btn" },
        { id: "campaigns", icon: Megaphone, name: t("nav.campaigns"), testId: "campaigns-btn" },
        { id: "messaging", icon: Envelope, name: t("nav.messaging"), testId: "messaging-btn" },
        { id: "msg-templates", icon: Globe, name: "Message templates", testId: "msg-templates-btn" },
        { id: "pre-arrival", icon: Envelope, name: "Pre-arrival drip", testId: "pre-arrival-btn" },
        { id: "mid-stay", icon: Smiley, name: "Mid-stay survey", testId: "mid-stay-btn" },
        { id: "surveys", icon: Star, name: t("nav.surveys"), testId: "surveys-btn" },
        { id: "concierge-analytics", icon: Robot, name: t("nav.concierge"), testId: "concierge-analytics-btn" },
        { id: "automation", icon: Lightning, name: t("nav.automation"), testId: "automation-btn" },
        { id: "chatbot-automation", icon: Robot, name: "Chatbot motoru", testId: "chatbot-automation-btn" },
        { id: "live-chat-inbox", icon: Headset, name: "Live Chat Inbox", testId: "live-chat-inbox-btn" },
        { id: "web-push", icon: Bell, name: "Web push", testId: "web-push-btn" },
        { id: "ab-test", icon: TestTube, name: "A/B testing", testId: "ab-test-btn" },
        { id: "attribution", icon: ChartBar, name: "Source attribution", testId: "attribution-btn" },
      ],
    },
    {
      label: "Operations",
      color: "text-stone-500",
      items: [
        { divider: true, label: "Housekeeping" },
        { id: "housekeeping", icon: Broom, name: t("nav.housekeeping"), testId: "housekeeping-btn" },

        { divider: true, label: "Maintenance & Ops" },
        { id: "ops-quick", icon: Lightning, name: "Quick ops", testId: "ops-quick-btn" },
        { id: "ops-v2", icon: Wrench, name: t("nav.ops_v2"), testId: "ops-v2-btn" },
        { id: "operations-hub", icon: Gear, name: "Operations hub", testId: "operations-hub-btn" },
        { id: "pms-pro", icon: Sparkle, name: "PMS Pro (AI ops)", testId: "pms-pro-btn" },

        { divider: true, label: "Inventory & Assets" },
        { id: "asset-register", icon: Package, name: "Asset register", testId: "asset-register-btn" },
        { id: "stock-management", icon: Package, name: t("nav.stock"), testId: "stock-management-btn" },
        { id: "low-stock", icon: Package, name: "Low-stock alerts", testId: "low-stock-btn" },
        { id: "spaces", icon: SquaresFour, name: "Spaces (parking, meet)", testId: "spaces-btn" },
        { id: "marketplace", icon: Storefront, name: "Marketplace (integrations)", testId: "marketplace-btn" },
        { id: "smart-locks", icon: Key, name: t("nav.smart_locks"), testId: "smart-locks-btn" },

        { divider: true, label: "Staff" },
        { id: "team-chat", icon: ChatText, name: "Team chat", testId: "team-chat-btn" },
        { id: "shift-scheduler", icon: CalendarBlank, name: "Shift scheduler", testId: "shift-scheduler-btn" },
        { id: "staff-performance", icon: Trophy, name: t("nav.staff_performance"), testId: "staff-performance-btn" },
        { id: "staff-ops", icon: Clock, name: "Staff clock-in & tips", testId: "staff-ops-btn" },

        { divider: true, label: "Quality Assurance" },
        { id: "glitch-log", icon: Warning, name: "Glitch log & devir", testId: "glitch-log-btn" },
        { id: "sops", icon: BookOpen, name: "SOP kütüphanesi", testId: "sops-btn" },
        { id: "automation-rules", icon: Lightning, name: "Otomasyon kuralları", testId: "automation-rules-btn" },
      ],
    },
    {
      label: "Revenue & rates",
      color: "text-stone-500",
      items: [
        { divider: true, label: "Pricing" },
        { id: "my-rates", icon: ChartLine, name: "My Rates (Daily Grid)", testId: "my-rates-btn" },
        { id: "revenue", icon: ChartLine, name: "Revenue management", testId: "revenue-btn" },
        { id: "profit-os", icon: Target, name: "Profit OS", testId: "profit-os-btn" },
        { id: "rate-manager", icon: ChartLine, name: "Rate manager", testId: "rate-manager-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "rate-matrix", icon: Users, name: "Rate matrix", testId: "rate-matrix-btn" }] : []),

        { divider: true, label: "Forecast & Pace" },
        { id: "forecast", icon: ChartLine, name: t("nav.forecast"), testId: "forecast-btn" },
        { id: "forecast-v2", icon: TrendUp, name: "24-month forecast", testId: "forecast-v2-btn" },
        { id: "pace-reports", icon: ChartLine, name: "Pace reports", testId: "pace-reports-btn" },

        { divider: true, label: "AI & Insights" },
        { id: "ai-pricing-v2", icon: Lightning, name: "AI pricing", testId: "ai-pricing-v2-btn" },
        { id: "pricing-explain", icon: Brain, name: "AI pricing explainer", testId: "pricing-explain-btn" },
        { id: "anomaly", icon: Lightning, name: "Anomaly radar", testId: "anomaly-btn" },
        { id: "ai-predictions", icon: Sparkle, name: "AI predictions", testId: "ai-predictions-btn" },

        { divider: true, label: "Channels & Parity" },
        { id: "channels-v2", icon: CloudArrowUp, name: "Channel Manager v2", testId: "channels-v2-btn" },
        { id: "channel-revenue", icon: Lightning, name: "Open pricing & yield", testId: "channel-revenue-btn" },
        { id: "parity-heatmap", icon: CalendarBlank, name: "Parity heatmap", testId: "parity-heatmap-btn" },
        { id: "ota-forecast", icon: TrendUp, name: "OTA stop-sell forecast", testId: "ota-forecast-btn" },
        { id: "compset", icon: Target, name: "Compset yönetimi", testId: "compset-btn" },

        { divider: true, label: "Tools" },
        { id: "rev-protection", icon: ShieldCheck, name: "Revenue protection", testId: "rev-protection-btn" },
        { id: "hurdle-lrv", icon: ShieldCheck, name: "Hurdle rate & LRV", testId: "hurdle-lrv-btn" },
        { id: "rm-lab", icon: ChartLine, name: "RM Lab", testId: "rm-lab-btn" },
        { id: "late-checkout-offer", icon: Clock, name: "Late checkout offers", testId: "late-checkout-offer-btn" },
        { id: "site-feasibility", icon: ChartLineUp, name: "Site feasibility & investor", testId: "site-feasibility-btn" },
        { id: "automation-analytics", icon: ChartBar, name: "Otomasyon analitiği", testId: "automation-analytics-btn" },
      ],
    },
    {
      label: "Food & events",
      color: "text-stone-500",
      items: [
        { id: "pos", icon: Receipt, name: t("nav.pos"), testId: "pos-btn" },
        { id: "kds", icon: ForkKnife, name: "Kitchen display", testId: "kds-btn" },
        { id: "menu-engineering", icon: ChartBar, name: "Menu engineering", testId: "menu-engineering-btn" },
        { id: "recipe-cogs", icon: Calculator, name: "Recipe COGS & modifiers", testId: "recipe-cogs-btn" },
        { id: "fnb-tabs", icon: ForkKnife, name: "F&B tab transfer", testId: "fnb-tabs-btn" },
        { id: "tipping", icon: Trophy, name: "Digital tipping", testId: "tipping-btn" },
        { id: "events", icon: CalendarBlank, name: "Events & rooms", testId: "events-btn" },
        { id: "conference-sc", icon: Briefcase, name: "Conference S&C", testId: "conference-sc-btn" },
        { id: "banquet-orders", icon: CalendarBlank, name: "Banquet event orders", testId: "banquet-orders-btn" },
        { id: "meetings-sales", icon: Briefcase, name: "Meeting & Events sales", testId: "meetings-sales-btn" },
        { id: "fnb-pos-hub", icon: PlugsConnected, name: "F&B POS entegrasyon hub", testId: "fnb-pos-hub-btn" },
        { id: "timeslots", icon: Sparkle, name: "Spa & activity slots", testId: "timeslots-btn" },
        { id: "spa-activities", icon: Sparkle, name: "Spa & aktivite rezervasyon", testId: "spa-activities-btn" },
      ],
    },
    {
      label: "Finance",
      color: "text-stone-500",
      items: [
        { divider: true, label: "Accounting" },
        { id: "accounting", icon: Wallet, name: t("nav.accounting"), testId: "accounting-btn" },
        { id: "finance", icon: Wallet, name: "Finance overview", testId: "finance-btn" },
        { id: "finance-pl", icon: ChartLine, name: "Profit & loss", testId: "finance-pl-btn" },
        { id: "cash-flow", icon: ChartLine, name: "Cash flow", testId: "cash-flow-btn" },
        { id: "budget-actual", icon: ChartBar, name: "Bütçe vs Gerçekleşen", testId: "budget-actual-btn" },
        { id: "expenses", icon: Receipt, name: "Expenses", testId: "expenses-btn" },
        { id: "payroll", icon: Wallet, name: "Payroll", testId: "payroll-btn" },

        { divider: true, label: "Payments" },
        { id: "payments", icon: Lightning, name: t("nav.payments"), testId: "payments-btn" },
        { id: "preauth", icon: CreditCard, name: "Pre-auth holds", testId: "preauth-btn" },
        { id: "chargeback", icon: Scales, name: "Chargebacks", testId: "chargeback-btn" },
        { id: "card-vault", icon: CreditCard, name: "Card vault", testId: "card-vault-btn" },

        { divider: true, label: "Deposits" },
        { id: "deposit-policies", icon: ShieldCheck, name: "Deposit policies", testId: "deposit-policies-btn" },
        { id: "deposit-automation", icon: Lightning, name: "Deposit automation", testId: "deposit-automation-btn" },
        { id: "deposit-ledger", icon: Wallet, name: "Deposit ledger", testId: "deposit-ledger-btn" },

        { divider: true, label: "Ledger & Folios" },
        { id: "city-ledger", icon: Wallet, name: "City ledger (AR)", testId: "city-ledger-btn" },
        { id: "commission-recon", icon: Receipt, name: "Commission reconciliation", testId: "commission-recon-btn" },
        { id: "folio-live", icon: Receipt, name: "In-stay folio", testId: "folio-live-btn" },
        { id: "folio-split", icon: Receipt, name: "Folio split-billing", testId: "folio-split-btn" },
        { id: "cash-drawer", icon: Wallet, name: "Cash drawer", testId: "cash-drawer-btn" },
        { id: "gift-cards", icon: Tag, name: "Gift cards", testId: "gift-cards-btn" },
        { id: "currency", icon: CurrencyDollar, name: "Currency / FX", testId: "currency-btn" },
        { id: "currency-fx", icon: Globe, name: "Multi-currency settings", testId: "currency-fx-btn" },

        { divider: true, label: "Night Audit" },
        { id: "night-audit", icon: Moon, name: t("nav.night_audit"), testId: "night-audit-btn" },
        { id: "night-audit-close", icon: Lock, name: "Close day", testId: "night-audit-close-btn" },

        { divider: true, label: "Tax & Compliance" },
        { id: "compliance", icon: ShieldCheck, name: "Compliance", testId: "compliance-btn" },
        { id: "tr-compliance", icon: FileText, name: "TR KBS & e-Invoice", testId: "tr-compliance-btn" },
        { id: "eu-compliance", icon: Globe, name: "EU police reports", testId: "eu-compliance-btn" },
        { id: "tax-config", icon: Receipt, name: "Tax configuration", testId: "tax-config-btn" },
        { id: "tax-presets", icon: Globe, name: "Tax presets library", testId: "tax-presets-btn" },
        { id: "tax-reports-v2", icon: Receipt, name: "Tax reports", testId: "tax-reports-v2-btn" },
        { id: "gdpr", icon: ShieldCheck, name: "GDPR data rights", testId: "gdpr-btn" },
        { id: "legal-docs", icon: ShieldCheck, name: "Legal documents", testId: "legal-docs-btn", roles: ["admin", "manager"] },
      ],
    },
    {
      label: "Reports",
      color: "text-stone-500",
      items: [
        { divider: true, label: "Reviews & Sentiment" },
        { id: "reviews", icon: ChatText, name: t("nav.reviews"), testId: "nav-reviews" },
        { id: "review-sentiment", icon: Sparkle, name: "AI sentiment themes", testId: "review-sentiment-btn" },
        { id: "sentiment-heatmap", icon: ChartLineUp, name: "Sentiment heatmap", testId: "sentiment-heatmap-btn" },

        { divider: true, label: "Analytics" },
        { id: "analytics", icon: ChartBar, name: t("nav.analytics"), testId: "analytics-btn" },
        { id: "reports", icon: CalendarBlank, name: t("nav.reports"), testId: "reports-btn" },
        { id: "reports-centre", icon: CalendarBlank, name: "Reports centre", testId: "reports-centre-btn" },
        { id: "scheduled-reports", icon: Envelope, name: "Scheduled reports", testId: "scheduled-reports-btn" },

        { divider: true, label: "Exports & BI" },
        { id: "accounting-export", icon: ChartLine, name: "Accounting export", testId: "accounting-export-btn" },
        { id: "bi-feed", icon: ChartBar, name: "BI feed (Power BI / Tableau)", testId: "bi-feed-btn" },
        { id: "sustainability", icon: ChartLine, name: "Sustainability & ESG", testId: "sustainability-btn" },
        { id: "carbon-v2", icon: ChartLine, name: "Karbon Raporu (GHG Scope 1/2/3)", testId: "carbon-v2-btn" },

        { divider: true, label: "Workflow & Alerts" },
        { id: "templates", icon: FileText, name: t("nav.templates"), testId: "templates-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "approvals", icon: ShieldCheck, name: t("nav.approvals"), testId: "approval-queue-btn" }] : []),
        { id: "alerts", icon: Bell, name: t("nav.alerts"), testId: "notification-settings-btn" },
        { id: "copilot", icon: Sparkle, name: "AI copilot library", testId: "copilot-btn" },
      ],
    },
    {
      label: "System",
      color: "text-stone-500",
      items: [
        { id: "chmgr-hub", icon: Lightning, name: "Channel manager hub", testId: "chmgr-hub-btn" },
        { id: "ota-commission", icon: Lightning, name: "OTA Komisyon & Net Gelir", testId: "ota-commission-btn" },
        { id: "direct-conversion", icon: Sparkle, name: "Direct Booking Conversion", testId: "direct-conversion-btn" },
        { id: "siteminder", icon: PlugsConnected, name: "SiteMinder adapter", testId: "siteminder-btn" },
        { id: "channel-map-matrix", icon: Buildings, name: "Channel mappings", testId: "channel-map-matrix-btn" },
        { id: "channel-restrictions", icon: Lock, name: "Restrictions", testId: "channel-restrictions-btn" },
        { id: "channel-inbound", icon: Link, name: "Inbound reservations", testId: "channel-inbound-btn" },
        { id: "channel-parity", icon: Scales, name: "Parity monitor", testId: "channel-parity-btn" },
        { id: "ota-health", icon: Heart, name: "OTA health", testId: "ota-health-btn" },
        { id: "channel-sync-queue", icon: ArrowsClockwise, name: "Sync queue", testId: "channel-sync-queue-btn" },
        { id: "channel-settings", icon: Gear, name: t("nav.channel_settings"), testId: "channel-settings-btn" },
        { id: "pms-crs", icon: ArrowsClockwise, name: "PMS-CRS sync", testId: "pms-crs-btn" },
        { id: "synclog", icon: ArrowsClockwise, name: t("nav.synclog"), testId: "sync-log-btn" },
        { id: "b2b-agents", icon: Briefcase, name: "B2B portal (agents)", testId: "b2b-agents-btn" },
        { id: "multi-rollup", icon: Buildings, name: "Multi-property roll-up", testId: "multi-rollup-btn" },
        { id: "brand-portal", icon: Buildings, name: "Brand portal (HQ)", testId: "brand-portal-btn" },
        { id: "security-owner", icon: Lock, name: "Owner portal", testId: "security-owner-btn" },
        { id: "setup-wizard", icon: Gear, name: t("nav.setup_wizard"), testId: "setup-wizard-btn" },
        { id: "onboarding", icon: MagicWand, name: "First-run wizard", testId: "onboarding-btn" },
        { id: "integrations", icon: PlugsConnected, name: t("nav.integrations"), testId: "integrations-btn" },
        { id: "api", icon: Key, name: t("nav.api"), testId: "api-connection-btn" },
        { id: "webhooks", icon: Code, name: t("nav.webhooks"), testId: "webhooks-btn" },
        { id: "public-api", icon: Code, name: "Developer portal", testId: "public-api-btn" },
        { id: "partner-webhooks", icon: PlugsConnected, name: "Partner webhooks & API keys", testId: "partner-webhooks-btn" },
        { id: "owner-portal", icon: Buildings, name: "Sahip / yatırımcı portalı", testId: "owner-portal-btn" },
        { id: "agency-portal", icon: Briefcase, name: "Acenta portalı (TÜRSAB)", testId: "agency-portal-btn" },
        { id: "web-concierge", icon: ChatText, name: "AI Web Concierge", testId: "web-concierge-btn" },
        { id: "review-agent", icon: Star, name: "AI Yorum Yanıt Ajanı", testId: "review-agent-btn" },
        { id: "open-pricing", icon: Stack, name: "Open Pricing matrisi", testId: "open-pricing-btn" },
        { id: "beach-pos", icon: Umbrella, name: "Beach POS (şezlong)", testId: "beach-pos-btn" },
        { id: "public-events", icon: Confetti, name: "Halka açık etkinlikler", testId: "public-events-btn" },
        { id: "ai-agents", icon: Robot, name: "Otonom AI Agent'lar", testId: "ai-agents-btn" },
        { id: "vacation-rental", icon: House, name: "Vacation Rental (apart)", testId: "vacation-rental-btn" },
        { id: "dev-portal", icon: Code, name: "Geliştirici portalı", testId: "dev-portal-btn" },
        { id: "wholesaler-hub", icon: Globe, name: "Wholesaler ağı", testId: "wholesaler-hub-btn" },
        { id: "lead-funnel", icon: Funnel, name: "Lead Funnel + Compset", testId: "lead-funnel-btn" },
        { id: "marketing-videos", icon: FilmReel, name: "AI Pazarlama Videoları (Sora 2)", testId: "marketing-videos-btn" },
        { id: "brand-voice", icon: Megaphone, name: "Marka Sesi Stüdyosu", testId: "brand-voice-btn" },
        { id: "guide", icon: ArrowSquareOut, name: t("nav.guide"), testId: "integration-guide-btn" },
        { id: "mapping", icon: Buildings, name: t("nav.mapping"), testId: "property-mapping-btn" },
        { id: "branding", icon: Palette, name: t("nav.branding"), testId: "branding-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "team", icon: Users, name: t("nav.team"), testId: "team-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "contracts", icon: FileText, name: "Staff contracts", testId: "contracts-btn" }] : []),
        ...(user?.role !== "receptionist" ? [{ id: "onboarding-admin", icon: Users, name: "Onboarding review", testId: "onboarding-admin-btn" }] : []),
        { id: "two-factor-auth", icon: ShieldCheck, name: "Two-factor auth", testId: "two-factor-auth-btn" },
        ...(user?.role === "admin" ? [{ id: "ip-allowlist", icon: Globe, name: "IP allowlist", testId: "ip-allowlist-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "admin-panel", icon: ShieldCheck, name: t("nav.admin_panel"), testId: "admin-panel-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "roles-permissions", icon: ShieldCheck, name: "Roles & permissions", testId: "roles-permissions-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "import-module", icon: Upload, name: "Import data", testId: "import-module-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "audit-trail", icon: ShieldCheck, name: "Audit trail", testId: "audit-trail-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "settings-hub", icon: Gear, name: "Settings hub", testId: "settings-hub-btn" }] : []),
        { id: "bug-tracker", icon: Bug, name: "Bug tracker", testId: "bug-tracker-btn" },
      ],
    },
  ];


  // Sidebar permission gating — mapping testId → required MENU permission key.
  // Items not listed stay visible by default (admin, housekeeper role, etc.)
  // Legacy admin role always sees everything (is_legacy_admin bypass).
  const SIDEBAR_PERM_MAP = {
    // Dashboard / Tasks / Calendar — broad visibility
    "dashboard-btn":          "dashboard_view",
    "my-tasks-btn":           "tasks_my_view",
    "sidebar-calendar":       "bookings_calendar_view",

    // Bookings
    "booking-engine-btn":         "bookings_view",
    "booking-engine-admin-btn":   "bookings_view",
    "arrivals-btn":               "bookings_view",
    "guest-profiles-btn":         "bookings_view",
    "guest-journey-btn":          "bookings_view",

    // Operations
    "operations-hub-btn":     "operations_reception_view",
    "housekeeping-btn":       "housekeeping_view",
    "hk-route-btn":           "housekeeping_view",
    "room-qr-btn":            "housekeeping_view",
    "service-recovery-btn":   "operations_reception_view",
    "late-checkout-btn":      "operations_reception_view",
    "no-show-btn":            "operations_reception_view",
    "walkin-btn":             "operations_reception_view",
    "guest-prefs-btn":        "operations_reception_view",
    "cleaning-checklists-btn":"housekeeping_view",
    "ops-quick-btn":          "operations_reception_view",
    "group-rooming-btn":      "view_bookings",
    "timeslots-btn":          "operations_reception_view",
    "staff-ops-btn":          "operations_reception_view",
    "rev-protection-btn":     "revenue_forecasting_view",
    "hurdle-lrv-btn":         "revenue_forecasting_view",
    "spaces-btn":             "operations_reception_view",
    "multi-rollup-btn":       "revenue_forecasting_view",
    "currency-btn":           "view_bookings",
    "b2b-agents-btn":         "view_bookings",
    "security-owner-btn":     "operations_reception_view",
    "preauth-btn":            "operations_reception_view",
    "chargeback-btn":         "operations_reception_view",
    "web-push-btn":           "operations_reception_view",
    "pms-crs-btn":            "operations_reception_view",
    "pms-pro-btn":            "operations_reception_view",
    "public-api-btn":         "operations_reception_view",
    "mid-stay-btn":           "operations_reception_view",
    "folio-live-btn":         "operations_reception_view",
    "ab-test-btn":            "operations_reception_view",
    "pre-arrival-btn":        "operations_reception_view",
    "menu-engineering-btn":   "operations_reception_view",
    "sr-voucher-btn":         "operations_reception_view",
    "folio-split-btn":        "operations_reception_view",
    "loyalty-auto-btn":       "operations_reception_view",
    "late-checkout-offer-btn":"operations_reception_view",
    "ota-forecast-btn":       "operations_reception_view",
    "ota-commission-btn":     "operations_reception_view",
    "availability-calendar-btn": "operations_reception_view",
    "direct-conversion-btn":  "operations_reception_view",
    "siteminder-btn":         "operations_reception_view",
    "external-loyalty-btn":   "operations_reception_view",
    "msg-templates-btn":      "operations_reception_view",
    "birthday-btn":           "operations_reception_view",
    "low-stock-btn":          "operations_reception_view",
    "rebook-btn":             "operations_reception_view",
    "stay-ext-btn":           "operations_reception_view",
    "long-stay-btn":          "operations_reception_view",
    "cancel-insurance-btn":   "operations_reception_view",
    "group-rooming-wiz-btn":  "operations_reception_view",
    "tax-reports-v2-btn":     "operations_reception_view",
    "ci-slots-btn":           "operations_reception_view",
    "tier1-dashboard-btn":    "operations_reception_view",
    "brand-portal-btn":       "operations_reception_view",
    "ops-v2-btn":             "maintenance_view",
    "forecast-v2-btn":        "revenue_forecasting_view",
    "anomaly-btn":            "revenue_forecasting_view",
    "pricing-explain-btn":    "revenue_forecasting_view",
    "tipping-btn":            "operations_reception_view",
    "guest-portal-v2-btn":    "operations_reception_view",
    "conference-sc-btn":      "operations_reception_view",
    "banquet-orders-btn":     "operations_reception_view",
    "copilot-btn":            "operations_reception_view",
    "image-ai-btn":           "housekeeping_view",
    "hk-turnover-btn":        "housekeeping_view",
    "fnb-tabs-btn":           "pos_view",
    "bi-feed-btn":            "revenue_forecasting_view",
    "ai-predictions-btn":     "revenue_forecasting_view",
    "channel-revenue-btn":    "revenue_forecasting_view",
    "sentiment-heatmap-btn":  "revenue_forecasting_view",
    "attribution-btn":        "revenue_forecasting_view",
    "tax-presets-btn":        "view_bookings",
    "maintenance-btn":        "maintenance_view",
    "shift-scheduler-btn":    "operations_shifts_view",
    "reception-report-btn":   "operations_reception_view",
    "pass-over-btn":          "operations_notes_view",
    "compliance-btn":         "operations_compliance_view",
    "tr-compliance-btn":      "operations_compliance_view",
    "eu-compliance-btn":      "operations_compliance_view",
    "laundry-btn":            "laundry_reports_view",
    "stock-management-btn":   "view_laundry_stock",
    "logbook-btn":            "operations_notes_view",
    "lost-found-btn":         "operations_reception_view",
    "night-audit-btn":        "operations_reception_view",
    "events-btn":             "operations_reception_view",

    // Reports / Analytics / Forecast
    "reports-btn":            "reports_overview_view",
    "reports-centre-btn":     "reports_overview_view",
    "analytics-btn":          "revenue_analytics_performance_view",
    "forecast-btn":           "revenue_forecasting_view",
    "pace-reports-btn":       "revenue_forecasting_view",
    "ai-pricing-v2-btn":      "revenue_forecasting_view",
    "parity-heatmap-btn":     "revenue_forecasting_view",
    "morning-brief-btn":      "revenue_forecasting_view",
    "nightly-recap-btn":      "revenue_forecasting_view",
    "help-guide-btn":         null,
    "accounting-export-btn":  "revenue_forecasting_view",
    "rm-lab-btn":             "revenue_forecasting_view",
    "concierge-inbox-btn":    "revenue_forecasting_view",
    "group-requests-btn":     "view_bookings",
    "sustainability-btn":     "revenue_forecasting_view",
    "revenue-btn":            "revenue_dashboard_view",
    "profit-os-btn":          "revenue_profit_os_view",
    "approval-queue-btn":     "revenue_approvals_view",
    "setup-wizard-btn":       "revenue_wizard_view",
    "rate-manager-btn":       "rates_calendar_view",
    "my-rates-btn":           "rates_calendar_view",
    "scheduled-reports-btn":  "reports_overview_view",
    "staff-performance-btn":  "reports_overview_view",
    "concierge-analytics-btn":"reports_overview_view",

    // Finance
    "payroll-btn":            "finance_payroll_runs_view",
    "rate-matrix-btn":        "finance_payroll_runs_view",
    "expenses-btn":           "finance_expenses_view",
    "cash-flow-btn":          "finance_dashboard_view",
    "finance-btn":            "finance_dashboard_view",
    "finance-pl-btn":         "finance_dashboard_view",
    "payments-btn":           "finance_dashboard_view",
    "accounting-btn":         "finance_dashboard_view",

    // Channel Manager / Marketplace / Integrations
    "marketplace-btn":        "channel_manager_connections_view",
    "integrations-btn":       "channel_manager_connections_view",
    "channel-settings-btn":   "channel_manager_profiles_view",
    "property-mapping-btn":   "channel_manager_mapping_view",
    "sync-log-btn":           "channel_manager_sync_view",
    "api-connection-btn":     "channel_manager_connections_view",
    "integration-guide-btn":  "channel_manager_connections_view",
    "webhooks-btn":           "webhooks_view",
    "add-ons-btn":            "channel_manager_connections_view",

    // Guest-facing / Messaging / Marketing
    "messaging-btn":          "bookings_view",
    "guest-app-btn":          "bookings_view",
    "mobile-companion-btn":   "bookings_view",
    "whatsapp-voice-btn":     "bookings_view",
    "surveys-btn":            "bookings_view",
    "nav-reviews":            "bookings_view",
    "campaigns-btn":          "bookings_view",
    "loyalty-btn":            "bookings_view",
    "loyalty-tier-btn":       "bookings_view",
    "loyalty-v2-btn":         "bookings_view",
    "promo-codes-btn":        "bookings_view",
    "pos-btn":                "finance_dashboard_view",
    "kds-btn":                "finance_dashboard_view",
    "self-checkin-v2-btn":    "operations_reception_view",
    "smart-locks-btn":        "bookings_view",
    "automation-btn":         "channel_manager_connections_view",
    "templates-btn":          "settings_roles_view",
    "website-templates-btn":  "settings_roles_view",
    "customize-template-btn": "settings_roles_view",
    "branding-btn":           "settings_roles_view",
    "policies-btn":           "settings_cancellation_policies_view",
    "notification-settings-btn": "settings_users_view",

    // Settings / People
    "team-btn":               "settings_users_view",
    "contracts-btn":          "settings_user_contracts_view",
    "onboarding-admin-btn":   "settings_users_view",
    "legal-docs-btn":         "settings_roles_view",
    "roles-permissions-btn":  "settings_roles_view",
    "admin-panel-btn":        "settings_users_view",
    "settings-hub-btn":       "settings_users_view",
    "bug-tracker-btn":        "system_feedback_view",
    "import-module-btn":      "settings_import_module_view",
    "audit-trail-btn":        "settings_roles_view",
  };

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
    <div className="min-h-screen bg-stone-50 flex" data-testid="review-dashboard">
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
      <aside className={`w-56 bg-[#1C1917] flex flex-col fixed inset-y-0 left-0 z-50 transition-transform duration-200 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0`} data-testid="sidebar">
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
                    <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-stone-500 group-hover:text-stone-300">
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
                        className="px-4 pt-3 pb-1 text-[9px] uppercase tracking-[0.18em] text-stone-600 font-semibold select-none"
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
        {activeView === "automation-rules" && (
          <AutomationRulesPanel propertyId={activePropertyId || "all"} user={user} />
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
        {activeView === "automation-analytics" && <AutomationAnalyticsPanel />}
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
        {/* Modal tabanlı araç görünümleri için arka plan bilgisi (iter 379) */}
        {["analytics", "templates", "integrations", "alerts", "reports", "branding"].includes(activeView) && (
          <div className="flex items-center justify-center min-h-[50vh] text-stone-400 text-sm" data-testid="modal-view-backdrop">
            Araç penceresi açık — kapatınca Reviews görünümüne dönersiniz.
          </div>
        )}

        {activeView === "analytics" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <AnalyticsPanel isOpen={true} onClose={() => setActiveView("reviews")} />
          </Dialog>
        )}

        {/* Templates View */}
        {activeView === "templates" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <TemplatesManager isOpen={true} onClose={() => setActiveView("reviews")} onSelectTemplate={handleApplyTemplate} />
          </Dialog>
        )}

        {/* Approvals View */}
        {activeView === "approvals" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <ApprovalQueuePanel onReviewUpdate={() => { fetchReviews(); fetchStats(); }} />
          </Dialog>
        )}

        {/* Integrations View */}
        {activeView === "integrations" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <IntegrationsPanel isOpen={true} onClose={() => setActiveView("reviews")} onSyncComplete={handleSyncComplete} />
          </Dialog>
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
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <NotificationSettings isOpen={true} onClose={() => setActiveView("reviews")} />
          </Dialog>
        )}

        {/* Reports View */}
        {activeView === "reports" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <ReportsSettings isOpen={true} onClose={() => setActiveView("reviews")} />
          </Dialog>
        )}

        {/* Branding View */}
        {activeView === "branding" && (
          <Dialog open={true} onOpenChange={() => setActiveView("reviews")}>
            <BrandingPanel isOpen={true} onClose={() => setActiveView("reviews")} branding={branding} onBrandingUpdate={(updated) => setBranding(updated)} />
          </Dialog>
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
    </LanguageProvider>
  );
}

export default AppWithLanguage;

