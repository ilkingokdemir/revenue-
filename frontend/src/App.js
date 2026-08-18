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
import PaymentResultPage from "./PaymentResultPage";
import TurkishPayPage from "./TurkishPayPage";
// ---------- EAGER imports (rendered on every dashboard render or first paint) ----------
import CommandPalette from "./components/CommandPalette";
import SectionHub from "./components/SectionHub";
import PwaInstallButton from "./components/PwaInstallButton";
import MobileHome from "./components/MobileHome";
import TodayHub from "./components/dashboard/TodayHub";
import { DataHealthStrip } from "./components/dashboard/DataHealthStrip";
import GlobalReportIssueFAB from "./components/dashboard/GlobalReportIssueFAB";
import ActionFeedPanel from "./components/dashboard/ActionFeedPanel";
import { OnboardingBanner } from "./components/dashboard/OnboardingBanner";
import { } from "./components/dashboard/DepartmentShortcutsPanel";
import { } from "./components/dashboard/GroupDisplacementPanel";
import { } from "./components/dashboard/DamageProtectionPanel";
import { NotificationBell } from "./components/dashboard/NotificationBell";
import { LoginPage } from "./components/dashboard/LoginPage";
import LandingPage from "./LandingPage";
import ReveniqLanding from "./ReveniqLanding";
import { PendingLegalDocsGate } from "./components/PendingLegalDocsGate";
import { StaffOnboardingGate } from "./components/StaffOnboardingGate";
import { ContractSigningPage } from "./components/public/ContractSigningPage";

// ---------- LAZY-LOADED dashboard panels (code-split per panel chunk) ----------
import {
  IntegrationsPanel,
  AnalyticsPanel,
} from "./lazyPanels";
import DashboardViews from "./DashboardViews";
import { StarRating, PlatformBadge, StatsCard, ReviewCard } from "@/components/dashboard/ReviewComponents";
import { AIResponsePanel, TemplatesManager, ApprovalQueuePanel } from "@/panels/ReviewToolsPanels";
import { UserManagementPanel, ApiConnectionPanel, WebhooksPanel, } from "@/panels/SystemToolsPanels";
import { buildMenuSections } from "./navigation/menuSections";
import { SIDEBAR_PERM_MAP } from "./navigation/permMap";
import GuestMaintenancePage from "./GuestMaintenancePage";
import BookingWidgetPage from "./BookingWidgetPage";
import AuthorizeFormPage from "./AuthorizeFormPage";
import SpacesPublicPage from "./SpacesPublicPage";
import GuestSurveyPage from "./GuestSurveyPage";
import PhotoContestPage from "./PhotoContestPage";
import ComplaintTrackPage from "./ComplaintTrackPage";
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
  PushPin,
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
  const [activePropertyId, setActivePropertyIdState] = useState(() => localStorage.getItem("active-property-id") || "all");
  const setActivePropertyId = (v) => {
    setActivePropertyIdState(v);
    try { localStorage.setItem("active-property-id", v); } catch { /* ignore */ }
  };
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
  // Simple/Pro navigation mode — Simple shows ~30 core screens, Pro shows everything.
  const [navMode, setNavMode] = useState(() => {
    try { return localStorage.getItem("mhb_nav_mode") || "simple"; } catch { return "simple"; }
  });
  const setNavModePersist = useCallback((m) => {
    setNavMode(m);
    try { localStorage.setItem("mhb_nav_mode", m); } catch {}
  }, []);
  // Pinned favorites — user-curated shortcuts shown at the top of the sidebar.
  const [favorites, setFavorites] = useState(() => {
    try { return JSON.parse(localStorage.getItem("mhb_favorites") || "[]"); } catch { return []; }
  });
  const toggleFavorite = useCallback((id) => {
    setFavorites((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(0, 12);
      try { localStorage.setItem("mhb_favorites", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);
  // Department shortcuts — admin-curated per-department task list shown in the sidebar
  const [deptShortcuts, setDeptShortcuts] = useState([]);
  const fetchDeptShortcuts = useCallback(async () => {
    if (!user?.department) return;
    try {
      const { data } = await axios.get(`${API}/department-shortcuts/${user.department}`);
      setDeptShortcuts(data.items || []);
    } catch { /* silent */ }
  }, [user?.department]);
  useEffect(() => { fetchDeptShortcuts(); }, [fetchDeptShortcuts]);
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

  // Simple mode: only core items, no dividers, drop empty sections.
  // Falls back to Pro list if the active view is not a core screen (so nothing disappears mid-use).
  const displayNavigation = useMemo(() => {
    if (navMode !== "simple") return gatedNavigation;
    return gatedNavigation.map(section => ({
      ...section,
      items: section.items.filter(it => !it.divider && (it.core || it.id === activeView)),
    })).filter(section => section.items.length > 0);
  }, [navMode, gatedNavigation, activeView]);

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

  // Resolve favorite IDs into rich items (respects permission gating via commandItems)
  const favItems = useMemo(
    () => favorites.map((id) => commandItems.find((i) => i.id === id)).filter(Boolean),
    [favorites, commandItems]
  );
  // Department shortcut items — skip ones already pinned personally
  const deptItems = useMemo(
    () => deptShortcuts
      .filter((id) => !favorites.includes(id))
      .map((id) => commandItems.find((i) => i.id === id))
      .filter(Boolean),
    [deptShortcuts, favorites, commandItems]
  );

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
          {/* Basit / Pro navigasyon modu */}
          <div className="mt-3 flex rounded-lg bg-stone-800 p-0.5" data-testid="nav-mode-toggle">
            <button onClick={() => setNavModePersist("simple")}
              data-testid="nav-mode-simple"
              className={`flex-1 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors ${
                navMode === "simple" ? "bg-emerald-600 text-white" : "text-stone-500 hover:text-stone-300"}`}>
              Basit
            </button>
            <button onClick={() => setNavModePersist("pro")}
              data-testid="nav-mode-pro"
              className={`flex-1 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors ${
                navMode === "pro" ? "bg-indigo-600 text-white" : "text-stone-500 hover:text-stone-300"}`}>
              Pro
            </button>
          </div>
          {/* Branch Selector — always visible */}
          <div className="mt-3" data-testid="branch-selector-container">
            <label className="text-[9px] uppercase tracking-[0.15em] font-semibold text-stone-600 mb-1 block px-0.5">Branch</label>
            <Select value={activePropertyId} onValueChange={(v) => setActivePropertyId(v)} data-testid="property-selector">
              <SelectTrigger data-testid="branch-selector-btn" className="w-full bg-stone-800 border-stone-700 text-stone-200 h-8 text-xs font-medium hover:bg-stone-750 transition-colors">
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
                      {p.external_id && <span className="text-[9px] text-emerald-600 ml-1.5 px-1 py-0.5 rounded bg-emerald-50 align-middle">linked</span>}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 custom-scrollbar">
          {/* Favoriler — pinned shortcuts, always on top in both modes */}
          {favItems.length > 0 && (
            <div className="mb-1" data-testid="favorites-section">
              <div className="w-full flex items-center gap-1.5 px-4 py-2">
                <PushPin size={10} weight="fill" className="text-amber-400" />
                <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-amber-400/90">Favoriler</span>
              </div>
              {favItems.map((item) => (
                <button key={`fav-${item.id}`} onClick={() => navigate(item.id)}
                  data-testid={`fav-item-${item.id}`}
                  className={`group w-full flex items-center gap-2.5 px-4 py-2 text-left text-[13px] transition-all ${
                    activeView === item.id
                      ? "bg-stone-800 text-white font-medium border-l-2 border-amber-400"
                      : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50 border-l-2 border-transparent"
                  }`}>
                  <item.icon size={16} weight={activeView === item.id ? "fill" : "regular"} />
                  <span className="flex-1 truncate">{item.name}</span>
                  <span role="button" tabIndex={-1}
                    onClick={(e) => { e.stopPropagation(); toggleFavorite(item.id); }}
                    data-testid={`fav-remove-${item.id}`}
                    title="Favorilerden kaldır"
                    className="opacity-0 group-hover:opacity-100 text-amber-400 hover:text-amber-300 transition-opacity">
                    <Star size={13} weight="fill" />
                  </span>
                </button>
              ))}
              <div className="mx-4 my-1 border-t border-stone-800/60" />
            </div>
          )}
          {/* Departman kısayolları — admin tarafından yönetilir */}
          {deptItems.length > 0 && (
            <div className="mb-1" data-testid="dept-shortcuts-sidebar">
              <div className="w-full flex items-center gap-1.5 px-4 py-2">
                <Users size={10} weight="fill" className="text-sky-400" />
                <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-sky-400/90">Departman</span>
              </div>
              {deptItems.map((item) => (
                <button key={`dept-${item.id}`} onClick={() => navigate(item.id)}
                  data-testid={`dept-sc-${item.id}`}
                  className={`w-full flex items-center gap-2.5 px-4 py-2 text-left text-[13px] transition-all ${
                    activeView === item.id
                      ? "bg-stone-800 text-white font-medium border-l-2 border-sky-400"
                      : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50 border-l-2 border-transparent"
                  }`}>
                  <item.icon size={16} weight={activeView === item.id ? "fill" : "regular"} />
                  <span className="flex-1 truncate">{item.name}</span>
                </button>
              ))}
              <div className="mx-4 my-1 border-t border-stone-800/60" />
            </div>
          )}
          {displayNavigation.map((section, sIdx) => {
            const sectionKey = section.label || `section-${sIdx}`;
            const sectionHubId = `hub-${sectionKey.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
            // Default: ALL sections collapsed except Overview + the section containing the active view.
            // User explicit toggle is persisted in localStorage as `nav-open-<key>`.
            // Simple mode: everything open (few items), no accordion needed.
            const containsActive = section.items.some((it) => it.id === activeView) || activeView === sectionHubId;
            const storedOpen = (typeof localStorage !== "undefined"
              ? localStorage.getItem(`nav-open-${sectionKey}`)
              : null);
            const isOverview = sectionKey === "Overview";
            const reallyOpen = navMode === "simple"
              || containsActive
              || (storedOpen === "1")
              || (storedOpen !== "0" && isOverview);
            const toggleSection = () => {
              if (navMode === "simple") return;
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
                    className={`group w-full flex items-center gap-2.5 px-4 py-2 text-left text-[13px] transition-all ${
                      activeView === item.id
                        ? "bg-stone-800 text-white font-medium border-l-2 border-emerald-500"
                        : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50 border-l-2 border-transparent"
                    }`}
                    data-testid={item.testId}
                  >
                    <item.icon size={16} weight={activeView === item.id ? "fill" : "regular"} />
                    <span className="flex-1 truncate">{tNav(item)}</span>
                    {item.id === "live-chat-inbox" && (
                      <HandoffSidebarBadge propertyId={activePropertyId} />
                    )}
                    <span role="button" tabIndex={-1}
                      onClick={(e) => { e.stopPropagation(); toggleFavorite(item.id); }}
                      data-testid={`fav-toggle-${item.id}`}
                      title={favorites.includes(item.id) ? "Favorilerden kaldır" : "Favorilere sabitle"}
                      className={`transition-opacity ${
                        favorites.includes(item.id)
                          ? "opacity-100 text-amber-400 hover:text-amber-300"
                          : "opacity-0 group-hover:opacity-60 hover:!opacity-100 text-stone-500 hover:text-amber-400"
                      }`}>
                      <Star size={13} weight={favorites.includes(item.id) ? "fill" : "regular"} />
                    </span>
                  </button>
                  );
                })}
              </div>
            );
          })}
          {navMode === "simple" && (
            <button onClick={() => setNavModePersist("pro")}
              data-testid="simple-mode-hint"
              className="w-full mt-3 mx-0 px-3 py-3 text-left rounded-xl bg-gradient-to-r from-indigo-950 to-stone-900 border border-indigo-800/50 hover:border-indigo-500 transition-colors group">
              <div className="flex items-center gap-2">
                <span className="text-base">🔓</span>
                <div>
                  <div className="text-[11px] font-black text-indigo-300 group-hover:text-indigo-200">250+ modül için PRO'ya geçin</div>
                  <div className="text-[10px] text-stone-500 mt-0.5">Gelir, kanal, finans, raporlar ve daha fazlası — hepsi tek tık uzağınızda. ⌘K ile de arayabilirsiniz.</div>
                </div>
              </div>
            </button>
          )}
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
              catalog={commandItems}
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
            <>
            <DataHealthStrip onNavigate={navigate} />
            <TodayHub
              propertyId={activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default")}
              pickupScope={activePropertyId}
              hotelName={properties?.find?.((p) => p.id === activePropertyId)?.name || branding?.app_name}
              onNavigate={navigate}
            />
            </>
          )
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

        <DashboardViews activeView={activeView} activePropertyId={activePropertyId} setActivePropertyId={setActivePropertyId} properties={properties} branding={branding} setBranding={setBranding} user={user} permissions={permissions} navigate={navigate} setActiveView={setActiveView} commandItems={commandItems} fetchDeptShortcuts={fetchDeptShortcuts} />
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
  if (window.location.pathname === "/payment/success" || window.location.pathname === "/payment/cancel") {
    return <PaymentResultPage />;
  }
  if (window.location.pathname === "/turkish-pay") {
    return <TurkishPayPage />;
  }
  if (window.location.pathname.startsWith("/survey/")) {
    const token = window.location.pathname.split("/survey/")[1];
    return <GuestSurveyPage token={token} />;
  }
  if (window.location.pathname.startsWith("/kareler/")) {
    return <PhotoContestPage />;
  }
  if (window.location.pathname.startsWith("/track/")) {
    const token = window.location.pathname.split("/track/")[1];
    return <ComplaintTrackPage token={token} />;
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
