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
import { InlineContent, InlineHeader, InlineTitle } from "./InlineShell";


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

export { UserManagementPanel, ApiConnectionPanel, WebhooksPanel, IntegrationGuidePanel };
