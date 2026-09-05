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
import ReviewWidget from "../ReviewWidget";
import BookingEngine from "../BookingEngine";
import ReviewCollectionPage from "../ReviewCollectionPage";
import SelfCheckInPage from "../SelfCheckInPage";
import KioskPWA from "../pages/KioskPWA";
import HousekeepingMobilePWA from "../pages/HousekeepingMobilePWA";
import SelfCheckoutPage from "../SelfCheckoutPage";
import DashboardSharePage from "../DashboardSharePage";
import RoomKeyPage from "../RoomKeyPage";
import SelfCheckInV2Page from "../SelfCheckInV2Page";
import TipPage from "../TipPage";
import OwnerSelfServiceApp from "../components/owner/OwnerSelfServiceApp";
import AgencyPortalApp from "../components/agency/AgencyPortalApp";
import PublicEventPage from "../PublicEventPage";
import GuestPortalV2Page from "../GuestPortalV2Page";
import GuestPortalPage from "../GuestPortalPage";
import GuestPaymentPage from "../GuestPaymentPage";
import TurkishPayPage from "../TurkishPayPage";
import CommandPalette from "../components/CommandPalette";
import SectionHub from "../components/SectionHub";
import PwaInstallButton from "../components/PwaInstallButton";
import MobileHome from "../components/MobileHome";
import TodayHub from "../components/dashboard/TodayHub";
import GlobalReportIssueFAB from "../components/dashboard/GlobalReportIssueFAB";
import ActionFeedPanel from "../components/dashboard/ActionFeedPanel";
import { OnboardingBanner } from "../components/dashboard/OnboardingBanner";
import { NotificationBell } from "../components/dashboard/NotificationBell";
import { LoginPage } from "../components/dashboard/LoginPage";
import { PendingLegalDocsGate } from "../components/PendingLegalDocsGate";
import { StaffOnboardingGate } from "../components/StaffOnboardingGate";
import { ContractSigningPage } from "../components/public/ContractSigningPage";
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
} from "../lazyPanels";
import { buildMenuSections } from "../navigation/menuSections";
import { SIDEBAR_PERM_MAP } from "../navigation/permMap";
import GuestMaintenancePage from "../GuestMaintenancePage";
import BookingWidgetPage from "../BookingWidgetPage";
import GuestSurveyPage from "../GuestSurveyPage";
import GuestRegistrationPage from "../GuestRegistrationPage";
import GuestFeedbackPage from "../GuestFeedbackPage";
import CheckInKioskPage from "../CheckInKioskPage";
import FeatureComparePage from "../FeatureComparePage";
import QROrderPage from "../QROrderPage";
import KioskPage from "../KioskPage";
import MidStaySurveyPublicPage from "../MidStaySurveyPublicPage";
import HandoffSidebarBadge from "../components/dashboard/HandoffSidebarBadge";
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

import { API, BACKEND_URL, PLATFORMS, TEMPLATE_CATEGORIES, SENTIMENT_COLORS, URGENCY_COLORS, formatApiErrorDetail } from "@/components/dashboard/config";
import { StarRating, PlatformBadge, StatsCard, ReviewCard } from "@/components/dashboard/ReviewComponents";
import { RiskBadge, FlagChips, SpamNotice, PrivacyAlert, QualityPanel, RISK_META } from "@/components/dashboard/ReviewOpsBits";
import { InlineContent, InlineHeader, InlineTitle } from "./InlineShell";


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
  const [genMeta, setGenMeta] = useState(null); // quality / similarity / decision / privacy / candidates
  const [useCandidates, setUseCandidates] = useState(false);

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
    setGenMeta(review?.response_quality ? { quality: review.response_quality, similarity: review.response_similarity, decision: review.ai_decision, privacy: review.response_privacy, candidates: review.ai_candidates } : null);
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
        language: language,
        candidates: useCandidates
      });
      const { quality, similarity, decision, privacy, candidates, analysis } = response.data;
      setGenMeta({ quality, similarity, decision, privacy, candidates });
      if (analysis) setSentimentData(analysis);
      
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
      toast.error(formatApiErrorDetail(error.response?.data?.detail) || "Failed to publish response");
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
                <RiskBadge analysis={sentimentData} />
              </div>
              <FlagChips analysis={sentimentData} />
              <SpamNotice analysis={sentimentData} review={review} />
              {sentimentData.emotion?.length > 0 && (
                <div className="text-[11px] text-stone-500">Emotion: {sentimentData.emotion.slice(0, 4).join(", ")}</div>
              )}

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
                
                <label className="inline-flex items-center gap-1 text-[11px] text-emerald-900 bg-white/80 border border-emerald-200 rounded-lg px-2 h-8 cursor-pointer" title="Warm / Professional / Concise — en iyisi seçilir">
                  <input type="checkbox" checked={useCandidates} onChange={e => setUseCandidates(e.target.checked)} data-testid="candidates-toggle" />
                  3 variants
                </label>
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

          {genMeta && !isGenerating && (
            <div className="mt-3 space-y-2">
              <PrivacyAlert privacy={genMeta.privacy} />
              <QualityPanel quality={genMeta.quality} similarity={genMeta.similarity} decision={genMeta.decision} />
              {genMeta.candidates?.length > 1 && (
                <div className="flex flex-wrap gap-1.5" data-testid="candidate-chips">
                  {genMeta.candidates.map((c) => (
                    <button key={c.style} onClick={() => setResponseText(c.text)} data-testid={`candidate-${c.style}`}
                      className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${responseText === c.text ? "bg-emerald-800 text-white border-emerald-800" : "bg-white border-emerald-200 text-emerald-900 hover:bg-emerald-50"}`}>
                      {c.style} · Q{c.quality} · S{c.similarity}%
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

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
  const [mobilePrefs, setMobilePrefs] = useState({ payment_received: true, pickup_strong: true, channel_drop: true, new_complaint: true });

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
    try {
      const { data } = await axios.get(`${API}/mobile/push-prefs`);
      setMobilePrefs(data);
    } catch (error) {
      console.error("Error fetching mobile push prefs:", error);
    }
  };

  const saveSettings = async () => {
    setIsSaving(true);
    try {
      await axios.put(`${API}/notifications/settings`, settings);
      await axios.post(`${API}/mobile/push-prefs`, mobilePrefs);
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
    <InlineContent className="sm:max-w-[500px]" data-testid="notification-settings-dialog">
      <InlineHeader>
        <InlineTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <Bell size={20} weight="fill" className="text-[#3E5245]" />
          Email Notifications
        </InlineTitle>
      </InlineHeader>
      
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

        {/* Mobile Push Preferences — synced with mobile app */}
        <div className="space-y-2" data-testid="mobile-push-prefs-section">
          <label className="text-sm font-medium text-[#1C1917] flex items-center gap-2">
            <Bell size={16} className="text-[#57534E]" />
            Mobil Push Bildirimleri
          </label>
          <p className="text-xs text-[#57534E]">Bu ayarlar mobil uygulamadaki push tercihleriyle senkronizedir.</p>
          {[
            { key: "payment_received", label: "Ödeme alındı", desc: "Yeni ödeme geldiğinde bildir" },
            { key: "pickup_strong", label: "Güçlü satış günü", desc: "Son 24 saatte yüksek pickup olduğunda bildir" },
            { key: "channel_drop", label: "Kanal düşüşü", desc: "Bir OTA kanalında pickup düşünce uyar" },
            { key: "new_complaint", label: "Yeni şikayet", desc: "Yeni misafir şikayeti kaydedildiğinde anında bildir" },
          ].map((p) => (
            <div key={p.key} className="flex items-center justify-between p-3 bg-[#FAF9F6] rounded-md border border-[#E7E5E4]">
              <div>
                <p className="text-sm font-medium text-[#1C1917]">{p.label}</p>
                <p className="text-xs text-[#57534E]">{p.desc}</p>
              </div>
              <Switch
                checked={!!mobilePrefs[p.key]}
                onCheckedChange={(checked) => setMobilePrefs(prev => ({ ...prev, [p.key]: checked }))}
                data-testid={`mobile-pref-${p.key}-switch`}
              />
            </div>
          ))}
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
    </InlineContent>
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
    <InlineContent className="sm:max-w-[700px] max-h-[85vh]" data-testid="templates-dialog">
      <InlineHeader>
        <InlineTitle className="flex items-center gap-2 text-[#1C1917] font-['Work_Sans']">
          <FileText size={20} weight="fill" className="text-[#3E5245]" />
          Response Templates
        </InlineTitle>
      </InlineHeader>

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
    </InlineContent>
  );
};

// Approval Queue Panel
const ApprovalQueuePanel = ({ onReviewUpdate }) => {
  const [pendingReviews, setPendingReviews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [notes, setNotes] = useState({});
  const [center, setCenter] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [riskFilter, setRiskFilter] = useState("");
  const { t } = useTranslation();

  const fetchPending = useCallback(async () => {
    setIsLoading(true);
    try {
      const [{ data }, st] = await Promise.all([
        axios.get(`${API}/reviews/pending-approval`),
        axios.get(`${API}/reviews/stats/summary`),
      ]);
      setPendingReviews(data);
      setCenter(st.data.approval_center || null);
    } catch (e) {
      console.error("Failed to fetch pending approvals");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchPending(); }, [fetchPending]);

  const handleAction = async (review, action) => {
    const a = review.sentiment_analysis || {};
    const needsReason = action === "approve" && (["high", "critical"].includes(a.risk_level) || review.escalated || a.spam_suspected);
    const n = notes[review.id] || "";
    if (needsReason && !n.trim()) {
      toast.error("Bu yorum için override gerekçesi zorunlu (not alanını doldurun)");
      return;
    }
    try {
      const { data } = await axios.post(`${API}/reviews/${review.id}/approve`, { action, notes: n });
      toast.success(action === "approve" ? (data.override ? "Override ile onaylandı & yayımlandı" : "Response approved & published!")
        : action === "escalate" ? `Escalated → ${data.escalation_level}` : "Response rejected");
      fetchPending();
      if (onReviewUpdate) onReviewUpdate();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const bulkSafe = async () => {
    setBulkBusy(true);
    try {
      const { data } = await axios.post(`${API}/reviews/approve-bulk`, { property_id: "all" });
      toast.success(`${data.approved} güvenli yanıt onaylandı, ${data.skipped.length} atlandı`);
      fetchPending();
      if (onReviewUpdate) onReviewUpdate();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBulkBusy(false); }
  };

  const visible = riskFilter ? pendingReviews.filter(r => ((r.sentiment_analysis || {}).risk_level || "low") === riskFilter) : pendingReviews;
  const rc = center?.risk_counts || {};
  const perf = center?.ai_performance;

  return (
    <InlineContent className="sm:max-w-[820px] max-h-[85vh] overflow-y-auto" data-testid="approval-queue-dialog">
      <InlineHeader>
        <InlineTitle className="flex items-center gap-2 text-stone-900">
          <ShieldCheck size={20} className="text-[#3E5245]" />
          {t("ro.approval_center")}
          {pendingReviews.length > 0 && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              {pendingReviews.length} {t("ro.pending")}
            </span>
          )}
        </InlineTitle>
      </InlineHeader>

      {/* Risk counters */}
      <div className="grid grid-cols-4 gap-2 mt-2" data-testid="risk-counters">
        {["critical", "high", "medium", "low"].map(lvl => (
          <button key={lvl} onClick={() => setRiskFilter(riskFilter === lvl ? "" : lvl)} data-testid={`risk-counter-${lvl}`}
            className={`rounded-lg border px-3 py-2 text-left transition-all ${riskFilter === lvl ? "ring-2 ring-stone-900" : ""} ${RISK_META[lvl].cls}`}>
            <div className="text-[10px] font-bold uppercase tracking-wider opacity-80">{RISK_META[lvl].label}</div>
            <div className="text-xl font-black">{rc[lvl] ?? 0}</div>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 mt-2 text-[11px] text-stone-500">
        <div className="flex gap-3">
          <span data-testid="escalated-count">{t("ro.escalated")}: <b className="text-stone-800">{center?.escalated ?? 0}</b></span>
          <span data-testid="spam-count">{t("ro.spam_suspected")}: <b className="text-stone-800">{center?.spam_suspected ?? 0}</b></span>
          {perf && <span>{t("ro.ai_score")}: <b className="text-stone-800">{perf.avg_response_score}</b> · Auto {perf.auto_approval_rate}% / Human {perf.human_approval_rate}% · Regen {perf.regeneration_rate}%</span>}
        </div>
        <button onClick={bulkSafe} disabled={bulkBusy || pendingReviews.length === 0} data-testid="bulk-approve-safe-btn"
          className="px-3 py-1.5 rounded-lg bg-emerald-700 text-white text-xs font-semibold hover:bg-emerald-800 disabled:opacity-50 inline-flex items-center gap-1">
          <Lightning size={12} weight="fill" /> {bulkBusy ? t("ro.approving") : t("ro.bulk_safe")}
        </button>
      </div>

      {isLoading ? (
        <div className="py-8 text-center">
          <ArrowsClockwise size={24} className="mx-auto mb-2 animate-spin text-stone-300" />
          <p className="text-sm text-stone-400">Loading...</p>
        </div>
      ) : visible.length === 0 ? (
        <div className="py-8 text-center" data-testid="no-pending-approvals">
          <ShieldCheck size={32} className="mx-auto mb-2 text-emerald-300" />
          <p className="text-sm text-stone-400">{t("ro.no_pending")}</p>
        </div>
      ) : (
        <div className="space-y-4 mt-3">
          {visible.map((review) => {
            const a = review.sentiment_analysis || {};
            const needsReason = ["high", "critical"].includes(a.risk_level) || review.escalated || a.spam_suspected;
            const privacyBad = review.response_privacy && !review.response_privacy.ok;
            return (
            <div key={review.id} className={`border rounded-xl overflow-hidden ${review.escalated ? "border-orange-300" : a.risk_level === "critical" ? "border-red-300" : "border-stone-200"}`} data-testid={`approval-item-${review.id}`}>
              <div className="bg-stone-50 px-4 py-3 flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <PlatformBadge platform={review.platform} />
                  <span className="text-sm font-medium text-stone-900">{review.guest_name}</span>
                  <StarRating rating={review.rating} size={12} />
                  <RiskBadge analysis={a} size="xs" />
                  {review.escalated && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-orange-100 text-orange-800 border border-orange-200" data-testid={`escalated-tag-${review.id}`}>ESCALATED → {review.escalation_level}</span>}
                  {review.response_quality && <span className="text-[10px] font-semibold text-stone-600" data-testid={`quality-tag-${review.id}`}>Q {review.response_quality.total}{review.response_similarity ? ` · S ${review.response_similarity.max_pct}%` : ""}</span>}
                </div>
                <span className="text-[11px] text-stone-400">{review.drafted_by ? `Drafted by: ${review.drafted_by}` : review.response_method || ""}</span>
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <span className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold">{t("ro.guest_review")}</span>
                  <p className="text-sm text-stone-600 mt-1">{review.review_text}</p>
                  <div className="mt-2"><FlagChips analysis={a} /></div>
                </div>
                <SpamNotice analysis={a} review={review} />
                {privacyBad && <PrivacyAlert privacy={review.response_privacy} />}
                <div className="bg-emerald-50 rounded-lg p-3 border border-emerald-100">
                  <span className="text-[10px] uppercase tracking-wider text-emerald-600 font-semibold">{t("ro.proposed")}</span>
                  <p className="text-sm text-emerald-900 mt-1 whitespace-pre-line">{review.response_text}</p>
                  {review.ai_decision?.reasons && <p className="text-[10px] text-emerald-700/70 mt-1">AI: {review.ai_decision.action} · {review.ai_decision.reasons.join(", ")}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAction(review, "approve")}
                    disabled={privacyBad || a.spam_suspected}
                    title={privacyBad ? "Gizlilik ihlali: önce metni düzenleyin" : a.spam_suspected ? "Spam şüpheli: yanıtlamayın" : ""}
                    className="flex-1 bg-emerald-700 text-white py-2 rounded-lg hover:bg-emerald-800 transition-all text-sm font-medium flex items-center justify-center gap-1.5 disabled:opacity-40"
                    data-testid={`approve-btn-${review.id}`}
                  >
                    <CheckCircle size={14} weight="fill" />
                    {needsReason ? t("ro.override_publish") : t("ro.approve_publish")}
                  </button>
                  {!review.escalated && (
                    <button
                      onClick={() => handleAction(review, "escalate")}
                      className="flex-1 bg-white border border-orange-300 text-orange-700 py-2 rounded-lg hover:bg-orange-50 transition-all text-sm font-medium flex items-center justify-center gap-1.5"
                      data-testid={`escalate-btn-${review.id}`}
                    >
                      <WarningCircle size={14} />
                      {t("ro.escalate")}
                    </button>
                  )}
                  <button
                    onClick={() => handleAction(review, "reject")}
                    className="flex-1 bg-white border border-red-200 text-red-600 py-2 rounded-lg hover:bg-red-50 transition-all text-sm font-medium flex items-center justify-center gap-1.5"
                    data-testid={`reject-btn-${review.id}`}
                  >
                    <X size={14} />
                    {t("ro.reject")}
                  </button>
                </div>
                <Input
                  placeholder={needsReason ? t("ro.notes_required") : t("ro.notes_optional")}
                  value={notes[review.id] || ""}
                  onChange={(e) => setNotes(p => ({ ...p, [review.id]: e.target.value }))}
                  className={`h-8 text-xs ${needsReason ? "border-orange-300" : "border-stone-200"}`}
                  data-testid={`rejection-notes-${review.id}`}
                />
              </div>
            </div>
          ); })}
        </div>
      )}
    </InlineContent>
  );
};

export { AIResponsePanel, NotificationSettings, TemplatesManager, ApprovalQueuePanel };
