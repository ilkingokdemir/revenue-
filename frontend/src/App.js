import { useEffect, useState, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { LanguageProvider, useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import ReviewWidget from "./ReviewWidget";
import BookingEngine from "./BookingEngine";
import ReviewCollectionPage from "./ReviewCollectionPage";
import SelfCheckInPage from "./SelfCheckInPage";
import GuestPortalPage from "./GuestPortalPage";
import GuestPaymentPage from "./GuestPaymentPage";
import TurkishPayPage from "./TurkishPayPage";
import { IntegrationsPanel } from "./components/dashboard/IntegrationsPanel";
import { IntegrationsMarketplace } from "./components/dashboard/IntegrationsMarketplace";
import { ArrivalsCockpit } from "./components/dashboard/ArrivalsCockpit";
import { StaffContractsPanel } from "./components/dashboard/StaffContractsPanel";
import { StaffOnboardingAdminPanel } from "./components/dashboard/StaffOnboardingAdminPanel";
import { PayrollRateMatrix } from "./components/dashboard/finance/PayrollRateMatrix";
import { CityLedgerPanel } from "./components/dashboard/finance/CityLedgerPanel";
import { TaxConfigPanel } from "./components/dashboard/finance/TaxConfigPanel";
import { DepositPolicyPanel } from "./components/dashboard/finance/DepositPolicyPanel";
import { CurrencyFxPanel } from "./components/dashboard/finance/CurrencyFxPanel";
import { RateStructurePanel } from "./components/dashboard/finance/RateStructurePanel";
import { GroupBookingsPanel } from "./components/dashboard/GroupBookingsPanel";
import { GdprPanel } from "./components/dashboard/GdprPanel";
import {
  NightAuditClosePanel, DepositLedgerPanel, CommissionReconPanel, GiftCardsPanel,
  ReviewSentimentPanel, GuestRfmPanel, PreventiveMaintenancePanel,
  AssetRegisterPanel, CashDrawerPanel, TwoFactorAuthPanel,
  RevenueHealthPanel, IpAllowlistPanel, CardVaultPanel,
  DepositAutomationPanel,
} from "./components/dashboard/CompetitorGapPanels";
import { OnboardingWizard } from "./components/dashboard/OnboardingWizard";
import { OnboardingBanner } from "./components/dashboard/OnboardingBanner";
import { UnifiedInboxPanel } from "./components/dashboard/UnifiedInboxPanel";
import { BugTrackerPanel } from "./components/dashboard/ops/BugTrackerPanel";
import { AuditTrailPanel } from "./components/dashboard/rbac/AuditTrailPanel";
import { CollisionsPanel } from "./components/dashboard/ops/CollisionsPanel";
import { ProfitOSPanel } from "./components/dashboard/revenue/ProfitOSPanel";
import { RolesPermissionsPanel } from "./components/dashboard/rbac/RolesPermissionsPanel";
import { ImportModulePanel } from "./components/dashboard/imports/ImportModulePanel";
import { LegalDocumentsPanel } from "./components/dashboard/LegalDocumentsPanel";
import { PendingLegalDocsGate } from "./components/PendingLegalDocsGate";
import { StaffOnboardingGate } from "./components/StaffOnboardingGate";
import { ContractSigningPage } from "./components/public/ContractSigningPage";
import { AnalyticsPanel } from "./components/dashboard/AnalyticsPanel";
import { ReportsSettings } from "./components/dashboard/ReportsSettings";
import { LoginPage } from "./components/dashboard/LoginPage";
import { BrandingPanel } from "./components/dashboard/BrandingPanel";
import { SyncLogPanel } from "./components/dashboard/SyncLogPanel";
import { PropertyMappingPanel } from "./components/dashboard/PropertyMappingPanel";
import { BookingEnginePanel } from "./components/dashboard/BookingEnginePanel";
import { TemplateGallery } from "./components/dashboard/TemplateGallery";
import { TemplateCustomizer } from "./components/dashboard/TemplateCustomizer";
import { PromoCodesPanel } from "./components/dashboard/PromoCodesPanel";
import { AddOnsPanel } from "./components/dashboard/AddOnsPanel";
import { PoliciesPanel } from "./components/dashboard/PoliciesPanel";
import { MessagingHub } from "./components/dashboard/MessagingHub";
import { ConciergeAnalyticsPanel } from "./components/dashboard/ConciergeAnalyticsPanel";
import { AutomationPanel } from "./components/dashboard/AutomationPanel";
import { ChannelSettingsPanel } from "./components/dashboard/ChannelSettingsPanel";
import { DashboardHome } from "./components/dashboard/DashboardHome";
import { StaffPerformancePanel } from "./components/dashboard/StaffPerformancePanel";
import { GuestProfilesPanel } from "./components/dashboard/GuestProfilesPanel";
import { AdminPanel } from "./components/dashboard/AdminPanel";
import { HousekeepingPanel } from "./components/dashboard/HousekeepingPanel";
import { NightAuditPanel } from "./components/dashboard/NightAuditPanel";
import { LoyaltyPanel } from "./components/dashboard/LoyaltyPanel";
import { LogbookPanel } from "./components/dashboard/LogbookPanel";
import { ForecastPanel } from "./components/dashboard/ForecastPanel";
import { CampaignsPanel } from "./components/dashboard/CampaignsPanel";
import { GuestAppPanel } from "./components/dashboard/GuestAppPanel";
import { SmartLocksPanel } from "./components/dashboard/SmartLocksPanel";
import { SetupWizardPanel } from "./components/dashboard/SetupWizardPanel";
import { StockManagementPanel } from "./components/dashboard/StockManagementPanel";
import { AccountingPanel } from "./components/dashboard/AccountingPanel";
import { POSPanel } from "./components/dashboard/POSPanel";
import { PaymentsPanel } from "./components/dashboard/PaymentsPanel";
import { SurveyPanel } from "./components/dashboard/SurveyPanel";
import { GuestJourneyPanel } from "./components/dashboard/GuestJourneyPanel";
import { MaintenancePanel } from "./components/dashboard/MaintenancePanel";
import { RateManagerPanel } from "./components/dashboard/RateManagerPanel";
import { ReportsCentrePanel } from "./components/dashboard/ReportsCentrePanel";
import { ScheduledReports } from "./components/dashboard/ScheduledReports";
import { MobileCompanion } from "./components/dashboard/MobileCompanion";
import { EnhancedDashboard } from "./components/dashboard/EnhancedDashboard";
import { ReportsHub } from "./components/dashboard/ReportsHub";
import { FinancePL } from "./components/dashboard/FinancePL";
import { ShiftScheduler } from "./components/dashboard/ShiftScheduler";
import { ReceptionReport } from "./components/dashboard/ReceptionReport";
import { PassOverDuties } from "./components/dashboard/PassOverDuties";
import { ComplianceRegister } from "./components/dashboard/ComplianceRegister";
import { LaundryManagement } from "./components/dashboard/LaundryManagement";
import { PayrollManagement } from "./components/dashboard/PayrollManagement";
import { ExpenseManagement } from "./components/dashboard/ExpenseManagement";
import { CashFlowForecast } from "./components/dashboard/CashFlowForecast";
import { OperationsHubPanel } from "./components/dashboard/OperationsHubPanel";
import { NotificationBell } from "./components/dashboard/NotificationBell";
import { FinancePanel } from "./components/dashboard/FinancePanel";
import { StaffManagementPanel } from "./components/dashboard/StaffManagementPanel";
import { MyTasksPanel } from "./components/dashboard/MyTasksPanel";
import { LostFoundPanel } from "./components/dashboard/LostFoundPanel";
import { EventsPanel } from "./components/dashboard/EventsPanel";
import { SettingsHubPanel } from "./components/dashboard/SettingsHubPanel";
import { BookingEngineAdmin } from "./components/dashboard/BookingEngineAdmin";
import { BookingTimeline } from "./components/dashboard/BookingTimeline";
import { RevenuePanel } from "./components/dashboard/RevenuePanel";
import GuestMaintenancePage from "./GuestMaintenancePage";
import BookingWidgetPage from "./BookingWidgetPage";
import GuestSurveyPage from "./GuestSurveyPage";
import GuestRegistrationPage from "./GuestRegistrationPage";
import GuestFeedbackPage from "./GuestFeedbackPage";
import CheckInKioskPage from "./CheckInKioskPage";
import FeatureComparePage from "./FeatureComparePage";
import QROrderPage from "./QROrderPage";
import KioskPage from "./KioskPage";
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
  ChartBar,
  TrendUp,
  TrendDown,
  Lightning,
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
  CreditCard,
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

function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
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

  // Sidebar menu items — organised by topic, collapsible
  const menuSections = [
    {
      label: "Overview",
      color: "text-stone-400",
      items: [
        { id: "dashboard", icon: House, name: t("nav.dashboard"), testId: "dashboard-btn" },
        { id: "my-tasks", icon: Target, name: "My Tasks", testId: "my-tasks-btn" },
        { id: "calendar", icon: CalendarBlank, name: "Calendar", testId: "sidebar-calendar" },
      ],
    },
    {
      label: "Reception",
      color: "text-emerald-400",
      items: [
        { id: "arrivals", icon: Bed, name: "Arrivals Cockpit", testId: "arrivals-btn" },
        { id: "unified-inbox", icon: Tray, name: "Unified Inbox", testId: "unified-inbox-btn" },
        { id: "collisions", icon: ShieldCheck, name: "Collisions", testId: "collisions-btn" },
        { id: "reception-report", icon: Notebook, name: "Reception Report", testId: "reception-report-btn" },
        { id: "pass-over", icon: Notebook, name: "Pass Over Duties", testId: "pass-over-btn" },
        { id: "kiosk-launch", icon: DeviceTablet, name: "Self-Service Kiosk", testId: "kiosk-launch-btn", launchUrl: true },
        { id: "compliance", icon: ShieldCheck, name: "Compliance", testId: "compliance-btn" },
        { id: "lost-found", icon: Eye, name: "Lost & Found", testId: "lost-found-btn" },
        { id: "cash-drawer", icon: Wallet, name: "Cash Drawer", testId: "cash-drawer-btn" },
      ],
    },
    {
      label: "Reservations & Booking",
      color: "text-blue-400",
      items: [
        { id: "booking", icon: Bed, name: t("nav.booking"), testId: "booking-engine-btn" },
        { id: "booking-engine-admin", icon: Globe, name: "Booking Engine", testId: "booking-engine-admin-btn" },
        { id: "website-templates", icon: Layout, name: t("nav.website_templates"), testId: "website-templates-btn" },
        { id: "customize-template", icon: PaintBrush, name: t("nav.customize_template"), testId: "customize-template-btn" },
        { id: "group-bookings", icon: Users, name: "Group Bookings", testId: "group-bookings-btn" },
        { id: "rate-structure", icon: Tag, name: "Rate Plans & OTA Mapping", testId: "rate-structure-btn" },
        { id: "promo-codes", icon: Tag, name: t("nav.promo_codes"), testId: "promo-codes-btn" },
        { id: "add-ons", icon: Package, name: t("nav.add_ons"), testId: "add-ons-btn" },
        { id: "policies", icon: Scroll, name: t("nav.policies"), testId: "policies-btn" },
      ],
    },
    {
      label: "Guests",
      color: "text-rose-400",
      items: [
        { id: "guest-profiles", icon: AddressBook, name: t("nav.guest_profiles"), testId: "guest-profiles-btn" },
        { id: "guest-journey", icon: SignIn, name: t("nav.guest_journey"), testId: "guest-journey-btn" },
        { id: "guest-app", icon: MapPin, name: t("nav.guest_app"), testId: "guest-app-btn" },
        { id: "loyalty", icon: Crown, name: t("nav.loyalty"), testId: "loyalty-btn" },
        { id: "smart-locks", icon: Key, name: t("nav.smart_locks"), testId: "smart-locks-btn" },
        { id: "campaigns", icon: Megaphone, name: t("nav.campaigns"), testId: "campaigns-btn" },
        { id: "surveys", icon: Star, name: t("nav.surveys"), testId: "surveys-btn" },
        { id: "messaging", icon: Envelope, name: t("nav.messaging"), testId: "messaging-btn" },
        { id: "concierge-analytics", icon: Robot, name: t("nav.concierge"), testId: "concierge-analytics-btn" },
        { id: "guest-rfm", icon: Target, name: "Guest RFM Segmentation", testId: "guest-rfm-btn" },
        { id: "automation", icon: Lightning, name: t("nav.automation"), testId: "automation-btn" },
      ],
    },
    {
      label: "Operations",
      color: "text-amber-400",
      items: [
        { id: "housekeeping", icon: Broom, name: t("nav.housekeeping"), testId: "housekeeping-btn" },
        { id: "maintenance", icon: Wrench, name: t("nav.maintenance"), testId: "maintenance-btn" },
        { id: "preventive-maintenance", icon: Wrench, name: "Preventive Maintenance", testId: "preventive-maintenance-btn" },
        { id: "asset-register", icon: Package, name: "Asset Register", testId: "asset-register-btn" },
        { id: "laundry", icon: TShirt, name: "Laundry", testId: "laundry-btn" },
        { id: "night-audit", icon: Moon, name: t("nav.night_audit"), testId: "night-audit-btn" },
        { id: "night-audit-close", icon: Lock, name: "Close Day (Lock)", testId: "night-audit-close-btn" },
        { id: "logbook", icon: Notebook, name: t("nav.logbook"), testId: "logbook-btn" },
        { id: "stock-management", icon: Package, name: t("nav.stock"), testId: "stock-management-btn" },
        { id: "events", icon: CalendarBlank, name: "Events & Rooms", testId: "events-btn" },
        { id: "shift-scheduler", icon: CalendarBlank, name: "Shift Scheduler", testId: "shift-scheduler-btn" },
        { id: "staff-performance", icon: Trophy, name: t("nav.staff_performance"), testId: "staff-performance-btn" },
        { id: "mobile-companion", icon: DeviceMobile, name: "Mobile View", testId: "mobile-companion-btn" },
        { id: "operations-hub", icon: Gear, name: "Operations Hub", testId: "operations-hub-btn" },
      ],
    },
    {
      label: "Revenue & Rates",
      color: "text-violet-400",
      items: [
        { id: "revenue", icon: ChartLine, name: "Revenue Mgmt", testId: "revenue-btn" },
        { id: "profit-os", icon: Target, name: "Profit OS", testId: "profit-os-btn" },
        { id: "rate-manager", icon: ChartLine, name: "Rate Manager", testId: "rate-manager-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "rate-matrix", icon: Users, name: "Rate Matrix", testId: "rate-matrix-btn" }] : []),
        { id: "forecast", icon: ChartLine, name: t("nav.forecast"), testId: "forecast-btn" },
        { id: "reports-centre", icon: CalendarBlank, name: "Reports Centre", testId: "reports-centre-btn" },
        { id: "scheduled-reports", icon: Envelope, name: "Scheduled Reports", testId: "scheduled-reports-btn" },
      ],
    },
    {
      label: "Finance",
      color: "text-sky-400",
      items: [
        { id: "accounting", icon: Wallet, name: t("nav.accounting"), testId: "accounting-btn" },
        { id: "finance", icon: Wallet, name: "Finance", testId: "finance-btn" },
        { id: "revenue-health", icon: ChartLine, name: "Revenue Health", testId: "revenue-health-btn" },
        { id: "finance-pl", icon: ChartLine, name: "Profit & Loss", testId: "finance-pl-btn" },
        { id: "cash-flow", icon: ChartLine, name: "Cash Flow", testId: "cash-flow-btn" },
        { id: "expenses", icon: Receipt, name: "Expenses", testId: "expenses-btn" },
        { id: "payroll", icon: Wallet, name: "Payroll", testId: "payroll-btn" },
        { id: "payments", icon: Lightning, name: t("nav.payments"), testId: "payments-btn" },
        { id: "pos", icon: Receipt, name: t("nav.pos"), testId: "pos-btn" },
        { id: "city-ledger", icon: Wallet, name: "City Ledger (AR)", testId: "city-ledger-btn" },
        { id: "tax-config", icon: Receipt, name: "Tax Configuration", testId: "tax-config-btn" },
        { id: "deposit-policies", icon: ShieldCheck, name: "Deposit Policies", testId: "deposit-policies-btn" },
        { id: "currency-fx", icon: Globe, name: "Multi-Currency / FX", testId: "currency-fx-btn" },
        { id: "deposit-ledger", icon: Wallet, name: "Deposit Ledger", testId: "deposit-ledger-btn" },
        { id: "commission-recon", icon: Receipt, name: "Commission Reconciliation", testId: "commission-recon-btn" },
        { id: "gift-cards", icon: Tag, name: "Gift Cards", testId: "gift-cards-btn" },
        { id: "card-vault", icon: CreditCard, name: "Card Vault (Stripe)", testId: "card-vault-btn" },
        { id: "deposit-automation", icon: Lightning, name: "Deposit Automation", testId: "deposit-automation-btn" },
        { id: "onboarding", icon: MagicWand, name: "First-Run Wizard", testId: "onboarding-btn" },
      ],
    },
    {
      label: t("section.review_hub"),
      color: "text-emerald-500",
      items: [
        { id: "reviews", icon: ChatText, name: t("nav.reviews"), testId: "nav-reviews" },
        { id: "review-sentiment", icon: Sparkle, name: "AI Sentiment Themes", testId: "review-sentiment-btn" },
        { id: "analytics", icon: ChartBar, name: t("nav.analytics"), testId: "analytics-btn" },
        { id: "templates", icon: FileText, name: t("nav.templates"), testId: "templates-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "approvals", icon: ShieldCheck, name: t("nav.approvals"), testId: "approval-queue-btn" }] : []),
        { id: "alerts", icon: Bell, name: t("nav.alerts"), testId: "notification-settings-btn" },
        { id: "reports", icon: CalendarBlank, name: t("nav.reports"), testId: "reports-btn" },
      ],
    },
    {
      label: "Settings & Developers",
      color: "text-stone-500",
      items: [
        { id: "setup-wizard", icon: Gear, name: t("nav.setup_wizard"), testId: "setup-wizard-btn" },
        { id: "marketplace", icon: Sparkle, name: "Marketplace", testId: "marketplace-btn" },
        { id: "integrations", icon: PlugsConnected, name: t("nav.integrations"), testId: "integrations-btn" },
        { id: "api", icon: Key, name: t("nav.api"), testId: "api-connection-btn" },
        { id: "webhooks", icon: Code, name: t("nav.webhooks"), testId: "webhooks-btn" },
        { id: "synclog", icon: ArrowsClockwise, name: t("nav.synclog"), testId: "sync-log-btn" },
        { id: "guide", icon: ArrowSquareOut, name: t("nav.guide"), testId: "integration-guide-btn" },
        { id: "channel-settings", icon: Gear, name: t("nav.channel_settings"), testId: "channel-settings-btn" },
        { id: "mapping", icon: Buildings, name: t("nav.mapping"), testId: "property-mapping-btn" },
        { id: "branding", icon: Palette, name: t("nav.branding"), testId: "branding-btn" },
        ...(user?.role !== "receptionist" ? [{ id: "team", icon: Users, name: t("nav.team"), testId: "team-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "contracts", icon: FileText, name: "Staff Contracts", testId: "contracts-btn" }] : []),
        ...(user?.role !== "receptionist" ? [{ id: "onboarding-admin", icon: Users, name: "Onboarding Review", testId: "onboarding-admin-btn" }] : []),
        ...(user?.role !== "receptionist" ? [{ id: "legal-docs", icon: ShieldCheck, name: "Legal Documents", testId: "legal-docs-btn" }] : []),
        { id: "gdpr", icon: ShieldCheck, name: "GDPR Data Rights", testId: "gdpr-btn" },
        { id: "two-factor-auth", icon: ShieldCheck, name: "Two-Factor Auth (2FA)", testId: "two-factor-auth-btn" },
        ...(user?.role === "admin" ? [{ id: "ip-allowlist", icon: Globe, name: "IP Allowlist", testId: "ip-allowlist-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "admin-panel", icon: ShieldCheck, name: t("nav.admin_panel"), testId: "admin-panel-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "roles-permissions", icon: ShieldCheck, name: "Roles & Permissions", testId: "roles-permissions-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "import-module", icon: Upload, name: "Import Module", testId: "import-module-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "audit-trail", icon: ShieldCheck, name: "Audit Trail", testId: "audit-trail-btn" }] : []),
        ...(user?.role === "admin" ? [{ id: "settings-hub", icon: Gear, name: "Settings Hub", testId: "settings-hub-btn" }] : []),
        { id: "bug-tracker", icon: Bug, name: "Bug Tracker", testId: "bug-tracker-btn" },
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
    "maintenance-btn":        "maintenance_view",
    "shift-scheduler-btn":    "operations_shifts_view",
    "reception-report-btn":   "operations_reception_view",
    "pass-over-btn":          "operations_notes_view",
    "compliance-btn":         "operations_compliance_view",
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
    "revenue-btn":            "revenue_dashboard_view",
    "profit-os-btn":          "revenue_profit_os_view",
    "approval-queue-btn":     "revenue_approvals_view",
    "setup-wizard-btn":       "revenue_wizard_view",
    "rate-manager-btn":       "rates_calendar_view",
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
    "surveys-btn":            "bookings_view",
    "nav-reviews":            "bookings_view",
    "campaigns-btn":          "bookings_view",
    "loyalty-btn":            "bookings_view",
    "promo-codes-btn":        "bookings_view",
    "pos-btn":                "finance_dashboard_view",
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
    items: section.items.filter(it => canSeeSidebar(it.testId)),
  })).filter(section => section.items.length > 0);

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
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: branding?.primary_color || "#3E5245" }}>
                <Buildings size={16} className="text-white" weight="fill" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <h1 className="text-sm font-semibold text-white truncate" data-testid="header-app-name">{branding?.app_name || "Review Hub"}</h1>
              <p className="text-[10px] text-stone-500 truncate" data-testid="header-subtitle">{branding?.subtitle || "Review Management"}</p>
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
            // Auto-expand the section that contains the active view
            const containsActive = section.items.some((it) => it.id === activeView);
            const storedClosed = (typeof localStorage !== "undefined"
              ? (localStorage.getItem(`nav-closed-${sectionKey}`) === "1")
              : false);
            const reallyOpen = containsActive || (collapsedSections[sectionKey] === undefined
              ? !storedClosed : !collapsedSections[sectionKey]);
            const toggleSection = () => {
              const now = reallyOpen; // currently open → will close
              const next = { ...collapsedSections, [sectionKey]: now };
              setCollapsedSections(next);
              try { localStorage.setItem(`nav-closed-${sectionKey}`, now ? "1" : "0"); } catch {}
            };
            return (
              <div key={sectionKey} className="mb-1">
                {sIdx > 0 && <div className="mx-4 mb-2 border-t border-stone-800" />}
                {section.label && (
                  <button onClick={toggleSection} data-testid={`nav-section-${sectionKey}`}
                    className="w-full flex items-center justify-between px-4 py-1.5 text-left hover:bg-stone-800/30 transition-colors group">
                    <span className={`text-[10px] uppercase tracking-[0.15em] font-bold ${section.color || "text-stone-500"}`}>
                      {section.label}
                    </span>
                    <CaretRight
                      size={10}
                      weight="bold"
                      className={`text-stone-600 group-hover:text-stone-400 transition-transform duration-200 ${reallyOpen ? "rotate-90" : ""}`}
                    />
                  </button>
                )}
                {reallyOpen && section.items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      if (item.launchUrl && item.id === "kiosk-launch") {
                        window.open(`/checkin-kiosk/${activePropertyId || "default"}`, "_blank", "noopener,noreferrer");
                        return;
                      }
                      setActiveView(item.id); setSidebarOpen(false);
                    }}
                    className={`w-full flex items-center gap-2.5 px-4 py-2 text-left text-[13px] transition-all ${
                      activeView === item.id
                        ? "bg-stone-800 text-white font-medium border-l-2 border-emerald-500"
                        : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50 border-l-2 border-transparent"
                    }`}
                    data-testid={item.testId}
                  >
                    <item.icon size={16} weight={activeView === item.id ? "fill" : "regular"} />
                    {item.name}
                  </button>
                ))}
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
      <main className="flex-1 lg:ml-56 pt-14 lg:pt-0">
        {/* First-run progress banner — auto-hides when setup is complete */}
        {activeView !== "onboarding" && user?.role === "admin" && (
          <OnboardingBanner
            propertyId={(activePropertyId && activePropertyId !== "all") ? activePropertyId : "default"}
            onResume={() => setActiveView("onboarding")}
          />
        )}

        {/* Dashboard Home */}
        {activeView === "dashboard" && (
          <EnhancedDashboard propertyId={activePropertyId} />
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

        {/* Housekeeping */}
        {activeView === "housekeeping" && (
          <HousekeepingPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Maintenance */}
        {activeView === "maintenance" && (
          <MaintenancePanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Night Audit */}
        {activeView === "night-audit" && (
          <NightAuditPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Loyalty Program */}
        {activeView === "loyalty" && (
          <LoyaltyPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Duty Logbook */}
        {activeView === "logbook" && (
          <LogbookPanel properties={properties} activePropertyId={activePropertyId} />
        )}

        {/* Occupancy Forecast */}
        {activeView === "forecast" && (
          <ForecastPanel properties={properties} activePropertyId={activePropertyId} />
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
          <OperationsHubPanel properties={properties} activePropertyId={activePropertyId} />
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

        {/* Laundry Management */}
        {activeView === "laundry" && (
          <div className="p-6"><LaundryManagement propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Payroll Management */}
        {activeView === "payroll" && (
          <div className="p-6"><PayrollManagement propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Expense Management */}
        {activeView === "expenses" && (
          <div className="p-6"><ExpenseManagement propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Cash Flow Forecast */}
        {activeView === "cash-flow" && (
          <div className="p-6"><CashFlowForecast propertyId={activePropertyId} user={user} /></div>
        )}

        {/* Integrations Marketplace */}
        {activeView === "marketplace" && (
          <div className="p-6"><IntegrationsMarketplace propertyId={activePropertyId} user={user} /></div>
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
      </main>

      {/* Powered By Footer */}
      {branding?.powered_by_visible && branding?.powered_by_text && (
        <div className="fixed bottom-0 left-0 lg:left-56 right-0 text-center py-1.5 border-t border-stone-100 bg-white/90 z-30" data-testid="powered-by-footer">
          <span className="text-[10px] text-stone-400">Powered by {branding.powered_by_text}</span>
        </div>
      )}

      <Toaster position="top-right" richColors />
    </div>
  );
};

function MainApp() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [permissions, setPermissions] = useState(null); // { permissions:Set, menu_permissions:Set, is_legacy_admin:bool }

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
  if (window.location.pathname === "/checkin") {
    return <SelfCheckInPage />;
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
  return <MainApp />;
}

function AppWithLanguage() {
  return (
    <LanguageProvider>
      <App />
    </LanguageProvider>
  );
}

export default AppWithLanguage;
