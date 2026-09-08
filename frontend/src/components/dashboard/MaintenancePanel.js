import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Wrench, CheckCircle, Clock, X, Eye, Plus, ArrowsClockwise, WarningCircle, Camera,
  ChatText, Timer, CurrencyDollar, CalendarBlank, Repeat, Lightning, Funnel,
} from "@phosphor-icons/react";
import { AlertTriangle, LayoutGrid, List, Send, ChevronRight, Upload, Trash2, MessageSquare, Package, QrCode, User, History } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE_URL = process.env.REACT_APP_BACKEND_URL;

const PRIORITY_CONFIG = {
  critical: { label: "Critical", color: "bg-red-600 text-white", ring: "ring-red-400", sla: "2h" },
  high: { label: "High", color: "bg-orange-500 text-white", ring: "ring-orange-300", sla: "8h" },
  medium: { label: "Medium", color: "bg-amber-100 text-amber-800", ring: "ring-amber-200", sla: "24h" },
  low: { label: "Low", color: "bg-stone-100 text-stone-600", ring: "ring-stone-200", sla: "72h" },
};

const STATUS_CONFIG = {
  open: { label: "Open", color: "bg-red-50 text-red-700 border-red-200", badge: "bg-red-100 text-red-700" },
  acknowledged: { label: "Acknowledged", color: "bg-blue-50 text-blue-700 border-blue-200", badge: "bg-blue-100 text-blue-700" },
  in_progress: { label: "In Progress", color: "bg-amber-50 text-amber-700 border-amber-200", badge: "bg-amber-100 text-amber-700" },
  resolved: { label: "Resolved", color: "bg-emerald-50 text-emerald-700 border-emerald-200", badge: "bg-emerald-100 text-emerald-700" },
  verified: { label: "Verified", color: "bg-teal-50 text-teal-700 border-teal-200", badge: "bg-teal-100 text-teal-700" },
  closed: { label: "Closed", color: "bg-stone-100 text-stone-500 border-stone-200", badge: "bg-stone-100 text-stone-600" },
};

const CATEGORY_CONFIG = {
  plumbing: { label: "Plumbing", icon: "🔧" },
  electrical: { label: "Electrical", icon: "⚡" },
  hvac: { label: "HVAC / AC", icon: "❄️" },
  furniture: { label: "Furniture", icon: "🪑" },
  appliance: { label: "Appliance", icon: "🔌" },
  structural: { label: "Structural", icon: "🏗️" },
  pest_control: { label: "Pest Control", icon: "🐛" },
  safety: { label: "Safety", icon: "🛡️" },
  it_network: { label: "IT / Network", icon: "📡" },
  general: { label: "General", icon: "🔨" },
};

const KANBAN_COLUMNS = [
  { id: "open", label: "Open", statuses: ["open"] },
  { id: "working", label: "In Progress", statuses: ["acknowledged", "in_progress"] },
  { id: "resolved", label: "Resolved", statuses: ["resolved"] },
  { id: "verified", label: "Verified / Closed", statuses: ["verified", "closed"] },
];

/* ─────────────── i18n ─────────────── */
const M_I18N = {
  en: {
    flag: "🇬🇧",
    title: "Maintenance", subtitle: "Issues, SLA tracking, costs & preventive maintenance",
    checkSla: "Check SLA", reportIssue: "Report Issue",
    kpiOpen: "Open", kpiInProgress: "In Progress", kpiResolved: "Resolved", kpiOverdue: "Overdue (SLA)", kpiCost: "Total Cost",
    tabIssues: "Issues", tabAssets: "Assets", tabTeam: "Team", tabVendors: "Vendors", tabPreventive: "Preventive", tabAnalytics: "Analytics",
    search: "Search issues...", allStatus: "All Status", allPriority: "All Priority", allCategory: "All Category", allDepts: "All Departments",
    priCritical: "Critical", priHigh: "High", priMedium: "Medium", priLow: "Low",
    stOpen: "Open", stAck: "Acknowledged", stInProgress: "In Progress", stResolved: "Resolved", stVerified: "Verified", stClosed: "Closed",
    colOpen: "OPEN", colInProgress: "IN PROGRESS", colResolved: "RESOLVED", colVerifiedClosed: "VERIFIED / CLOSED",
    actAck: "Ack", actStart: "Start", actResolve: "Resolve", actVerify: "Verify", actClose: "Close",
    dialogTitle: "Report Maintenance Issue", issueTitle: "Issue title *",
    overrideLbl: "Priority Override (0-10, optional)", overridePh: "0 = use default by priority level",
    overrideHint: "Leave at 0 to use default. Higher = more urgent (e.g. 10 for VIP/emergency).",
    locPh: "Location (e.g. Lobby)", roomPh: "Room number", descPh: "Describe the issue in detail...",
    beforePhotos: "Before Photos (current condition)", submit: "Submit Issue",
    linkAsset: "Link to asset (optional)", noAsset: "No asset",
    autoDept: "Auto (by category)", deptMaint: "Maintenance", deptHk: "Housekeeping",
    deptRec: "Reception", deptMgmt: "Management", deptKitch: "Kitchen",
    unassigned: "Unassigned", assignTo: "Assign to...",
    issueCreated: "Issue reported!", issueFailed: "Failed to create",
    reportedBy: "Reported by", resolvedBy: "Resolved by", onDate: "on",
    tlReported: "Reported", tlAcked: "Acknowledged", tlStarted: "Started",
    tlResolved: "Resolved", tlVerified: "Verified", tlClosed: "Closed",
    tlDuration: "Duration", tlTotalTime: "Total time", tlPending: "Pending",
    tlNoActor: "—",
  },
  tr: {
    flag: "🇹🇷",
    title: "Bakım", subtitle: "Arıza, SLA takibi, maliyet ve önleyici bakım",
    checkSla: "SLA Kontrol", reportIssue: "Arıza Bildir",
    kpiOpen: "Açık", kpiInProgress: "Devam Ediyor", kpiResolved: "Çözüldü", kpiOverdue: "SLA Aşımı", kpiCost: "Toplam Maliyet",
    tabIssues: "Arızalar", tabAssets: "Varlıklar", tabTeam: "Ekip", tabVendors: "Tedarikçiler", tabPreventive: "Önleyici", tabAnalytics: "Analiz",
    search: "Arıza ara...", allStatus: "Tüm Durumlar", allPriority: "Tüm Öncelikler", allCategory: "Tüm Kategoriler", allDepts: "Tüm Departmanlar",
    priCritical: "Kritik", priHigh: "Yüksek", priMedium: "Orta", priLow: "Düşük",
    stOpen: "Açık", stAck: "Onaylandı", stInProgress: "Devam Ediyor", stResolved: "Çözüldü", stVerified: "Doğrulandı", stClosed: "Kapandı",
    colOpen: "AÇIK", colInProgress: "DEVAM EDİYOR", colResolved: "ÇÖZÜLDÜ", colVerifiedClosed: "DOĞRULANDI / KAPANDI",
    actAck: "Onayla", actStart: "Başla", actResolve: "Çöz", actVerify: "Doğrula", actClose: "Kapat",
    dialogTitle: "Bakım Arızası Bildir", issueTitle: "Arıza başlığı *",
    overrideLbl: "Öncelik Geçersiz Kılma (0-10, opsiyonel)", overridePh: "0 = öncelik seviyesine göre varsayılan",
    overrideHint: "0 bırakırsanız varsayılan kullanılır. Yüksek = daha acil (örn. VIP/acil durumda 10).",
    locPh: "Konum (örn. Lobi)", roomPh: "Oda numarası", descPh: "Arızayı detaylı açıklayın...",
    beforePhotos: "Önce Fotoğraflar (mevcut durum)", submit: "Arızayı Kaydet",
    linkAsset: "Varlığa bağla (opsiyonel)", noAsset: "Varlık yok",
    autoDept: "Otomatik (kategoriye göre)", deptMaint: "Bakım", deptHk: "Housekeeping",
    deptRec: "Resepsiyon", deptMgmt: "Yönetim", deptKitch: "Mutfak",
    unassigned: "Atanmadı", assignTo: "Atama yap...",
    issueCreated: "Arıza kaydedildi!", issueFailed: "Kayıt başarısız",
    reportedBy: "Rapor eden", resolvedBy: "Çözen", onDate: "·",
    tlReported: "Rapor Edildi", tlAcked: "Onaylandı", tlStarted: "Başlatıldı",
    tlResolved: "Çözüldü", tlVerified: "Doğrulandı", tlClosed: "Kapandı",
    tlDuration: "Süre", tlTotalTime: "Toplam süre", tlPending: "Beklemede",
    tlNoActor: "—",
  },
};
const useMLang = () => {
  const [lang, setLang] = useState(() => localStorage.getItem("maint_lang") || "en");
  const setLangPersist = (v) => { localStorage.setItem("maint_lang", v); setLang(v); };
  return [lang, setLangPersist, M_I18N[lang] || M_I18N.en];
};

export function MaintenancePanel({ properties, activePropertyId: propActivePropertyId }) {
  const activePropertyId = propActivePropertyId || "all";
  const [issues, setIssues] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("kanban"); // kanban, table
  const [tab, setTab] = useState("issues"); // issues, recurring, analytics
  const [selectedIssue, setSelectedIssue] = useState(null);
  const [showRecurring, setShowRecurring] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [filterCategory, setFilterCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [recurring, setRecurring] = useState([]);
  const [assignees, setAssignees] = useState([]);
  const [assets, setAssets] = useState([]);
  const [filterDepartment, setFilterDepartment] = useState("all");
  const [lang, setLang, L] = useMLang();

  const fetchData = useCallback(async () => {
    if (!activePropertyId) return;
    try {
      const [issuesRes, statsRes, assigneesRes, assetsRes] = await Promise.all([
        axios.get(`${API}/maintenance/issues/${activePropertyId}`),
        axios.get(`${API}/maintenance/stats/${activePropertyId}`),
        axios.get(`${API}/maintenance/assignees/${activePropertyId}`),
        axios.get(`${API}/assets/${activePropertyId}`).catch(() => ({ data: [] })),
      ]);
      setIssues(issuesRes.data);
      setStats(statsRes.data);
      setAssignees(assigneesRes.data);
      setAssets(assetsRes.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [activePropertyId]);

  const fetchRecurring = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/maintenance/recurring/${activePropertyId}`);
      setRecurring(data);
    } catch { }
  }, [activePropertyId]);

  useEffect(() => { fetchData(); fetchRecurring(); }, [fetchData, fetchRecurring]);

  // Refresh when a new issue is created via the Global FAB
  useEffect(() => {
    const onCreated = () => fetchData();
    window.addEventListener("issue-created", onCreated);
    return () => window.removeEventListener("issue-created", onCreated);
  }, [fetchData]);

  const filtered = issues.filter(i => {
    if (filterStatus !== "all" && i.status !== filterStatus) return false;
    if (filterPriority !== "all" && i.priority !== filterPriority) return false;
    if (filterCategory !== "all" && i.category !== filterCategory) return false;
    if (filterDepartment !== "all" && (i.assigned_department || "") !== filterDepartment) return false;
    if (search && !i.title?.toLowerCase().includes(search.toLowerCase()) && !i.location?.toLowerCase().includes(search.toLowerCase()) && !i.room_number?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const updateStatus = async (issue, newStatus) => {
    try {
      await axios.put(`${API}/maintenance/issues/${issue.id}`, { status: newStatus });
      toast.success(`Status updated to ${newStatus}`);
      fetchData();
    } catch { toast.error("Failed to update"); }
  };

  return (
    <div className="p-3 md:p-6 space-y-3 md:space-y-4 max-w-[1600px] mx-auto" data-testid="maintenance-panel">
      {/* Sticky compact header */}
      <div className="sticky top-0 z-20 -mx-3 md:mx-0 px-3 md:px-0 py-2 md:py-0 bg-white/95 backdrop-blur md:bg-transparent md:backdrop-blur-none border-b border-stone-100 md:border-0">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex-1 min-w-0">
            <h1 className="text-lg md:text-2xl font-bold text-stone-800 leading-tight truncate" data-testid="maintenance-title">{L.title}</h1>
            <p className="hidden md:block text-sm text-stone-500 mt-0.5">{L.subtitle}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <div className="flex gap-0.5 bg-stone-100 rounded-lg p-0.5" data-testid="maint-lang-toggle">
              {Object.keys(M_I18N).map(code => (
                <button key={code} onClick={() => setLang(code)}
                  className={`px-2 py-0.5 text-[10px] md:text-xs font-semibold rounded transition ${lang === code ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}
                  data-testid={`maint-lang-${code}`}>
                  {M_I18N[code].flag} {code.toUpperCase()}
                </button>
              ))}
            </div>
            <button onClick={() => { axios.post(`${API}/maintenance/check-sla/${activePropertyId}`).then(() => { toast.success("SLA check complete"); fetchData(); }); }}
              className="hidden md:flex px-2.5 py-1.5 text-xs font-medium text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50 items-center gap-1" data-testid="btn-check-sla">
              <Timer size={12} /> {L.checkSla}
            </button>
            <button onClick={() => window.dispatchEvent(new CustomEvent("open-report-issue"))}
              className="px-3 py-1.5 bg-orange-500 text-white text-xs md:text-sm font-semibold rounded-lg hover:bg-orange-600 transition flex items-center gap-1 shadow-md"
              data-testid="btn-new-issue">
              <Plus size={13} weight="bold" /> {L.reportIssue}
            </button>
          </div>
        </div>
      </div>

      {/* KPI cards — horizontal scroll on mobile, grid on desktop */}
      <div className="flex md:grid md:grid-cols-5 gap-2 overflow-x-auto -mx-3 md:mx-0 px-3 md:px-0 pb-1 md:pb-0 snap-x" data-testid="maintenance-stats">
        {[
          { label: L.kpiOpen, value: stats.open || 0, bg: "bg-red-50", tx: "text-red-700", accent: "text-red-500", icon: <WarningCircle size={14} weight="fill" /> },
          { label: L.kpiInProgress, value: stats.in_progress || 0, bg: "bg-amber-50", tx: "text-amber-700", accent: "text-amber-500", icon: <Wrench size={14} weight="fill" /> },
          { label: L.kpiResolved, value: stats.resolved || 0, bg: "bg-emerald-50", tx: "text-emerald-700", accent: "text-emerald-500", icon: <CheckCircle size={14} weight="fill" /> },
          { label: L.kpiOverdue, value: stats.overdue || 0, bg: stats.overdue > 0 ? "bg-red-100" : "bg-stone-50", tx: stats.overdue > 0 ? "text-red-800" : "text-stone-600", accent: stats.overdue > 0 ? "text-red-600" : "text-stone-400", icon: <Timer size={14} weight="fill" /> },
          { label: L.kpiCost, value: `£${(stats.costs?.total_actual || 0).toLocaleString()}`, bg: "bg-blue-50", tx: "text-blue-700", accent: "text-blue-500", icon: <CurrencyDollar size={14} weight="fill" /> },
        ].map((s, i) => (
          <div key={i} className={`${s.bg} rounded-lg md:rounded-xl p-2.5 md:p-3 flex items-center gap-2 shrink-0 snap-start min-w-[130px] md:min-w-0 ${s.tx}`} data-testid={`stat-${i}`}>
            <div className={`${s.accent} shrink-0`}>{s.icon}</div>
            <div className="min-w-0">
              <p className="text-base md:text-lg font-black leading-none">{s.value}</p>
              <p className="text-[9px] md:text-[10px] font-medium opacity-70 mt-1 truncate">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs + View Toggle — horizontal scroll on mobile */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-0.5 bg-stone-100 p-0.5 rounded-lg overflow-x-auto scrollbar-hide -mx-3 md:mx-0 px-3 md:px-0.5" data-testid="maint-tabs">
          {[
            { id: "issues", label: L.tabIssues, icon: <Wrench size={12} /> },
            { id: "assets", label: L.tabAssets, icon: <Package size={12} /> },
            { id: "team", label: L.tabTeam, icon: <Lightning size={12} /> },
            { id: "vendors", label: L.tabVendors, icon: <Lightning size={12} /> },
            { id: "recurring", label: L.tabPreventive, icon: <Repeat size={12} /> },
            { id: "analytics", label: L.tabAnalytics, icon: <Lightning size={12} /> },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-2.5 py-1.5 text-[11px] md:text-xs font-medium rounded-md flex items-center gap-1 transition whitespace-nowrap shrink-0 ${tab === t.id ? "bg-white shadow-sm text-stone-800" : "text-stone-500"}`}
              data-testid={`maint-tab-${t.id}`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
        {tab === "issues" && (
          <div className="hidden md:flex gap-0.5 bg-stone-100 p-0.5 rounded-lg shrink-0">
            <button onClick={() => setView("kanban")} className={`p-1.5 rounded-md transition ${view === "kanban" ? "bg-white shadow-sm" : ""}`} data-testid="view-kanban"><LayoutGrid size={13} className="text-stone-600" /></button>
            <button onClick={() => setView("table")} className={`p-1.5 rounded-md transition ${view === "table" ? "bg-white shadow-sm" : ""}`} data-testid="view-table"><List size={13} className="text-stone-600" /></button>
          </div>
        )}
      </div>

      {tab === "issues" && (
        <>
          {/* Filters — scrollable on mobile, toggle to hide */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-hide -mx-3 md:mx-0 px-3 md:px-0 pb-1" data-testid="maint-filters">
            <Input data-testid="maint-search" placeholder={L.search} value={search} onChange={(e) => setSearch(e.target.value)} className="min-w-[160px] md:max-w-[200px] h-8 text-xs shrink-0" />
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[110px] h-8 text-xs shrink-0"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{L.allStatus}</SelectItem>
                <SelectItem value="open">{L.stOpen}</SelectItem>
                <SelectItem value="acknowledged">{L.stAck}</SelectItem>
                <SelectItem value="in_progress">{L.stInProgress}</SelectItem>
                <SelectItem value="resolved">{L.stResolved}</SelectItem>
                <SelectItem value="verified">{L.stVerified}</SelectItem>
                <SelectItem value="closed">{L.stClosed}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="w-[100px] h-8 text-xs shrink-0"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{L.allPriority}</SelectItem>
                <SelectItem value="critical">{L.priCritical}</SelectItem>
                <SelectItem value="high">{L.priHigh}</SelectItem>
                <SelectItem value="medium">{L.priMedium}</SelectItem>
                <SelectItem value="low">{L.priLow}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-[120px] h-8 text-xs shrink-0"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{L.allCategory}</SelectItem>
                {Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={filterDepartment} onValueChange={setFilterDepartment}>
              <SelectTrigger className="w-[130px] h-8 text-xs shrink-0" data-testid="filter-department"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{L.allDepts}</SelectItem>
                <SelectItem value="maintenance">{L.deptMaint}</SelectItem>
                <SelectItem value="housekeeping">{L.deptHk}</SelectItem>
                <SelectItem value="reception">{L.deptRec}</SelectItem>
                <SelectItem value="management">{L.deptMgmt}</SelectItem>
                <SelectItem value="kitchen">{L.deptKitch}</SelectItem>
              </SelectContent>
            </Select>
            <button onClick={fetchData} className="p-1.5 text-stone-400 hover:text-stone-600 shrink-0"><ArrowsClockwise size={13} /></button>
          </div>

          {/* Kanban View */}
          {view === "kanban" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 md:gap-3" data-testid="kanban-board">
              {KANBAN_COLUMNS.map(col => {
                const colIssues = filtered.filter(i => col.statuses.includes(i.status));
                return (
                  <div key={col.id} className="bg-stone-50/70 rounded-xl p-2.5 border border-stone-100" data-testid={`kanban-col-${col.id}`}>
                    <div className="flex items-center justify-between mb-2 px-1">
                      <h3 className="text-[10px] font-bold text-stone-600 uppercase tracking-wider">
                        {col.id === "open" ? L.colOpen : col.id === "working" ? L.colInProgress : col.id === "resolved" ? L.colResolved : L.colVerifiedClosed}
                      </h3>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${col.id === "open" ? "bg-red-100 text-red-700" : col.id === "working" ? "bg-amber-100 text-amber-700" : col.id === "resolved" ? "bg-emerald-100 text-emerald-700" : "bg-teal-100 text-teal-700"}`}>{colIssues.length}</span>
                    </div>
                    <div className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-0.5">
                      {colIssues.map(issue => (
                        <IssueCard key={issue.id} issue={issue} L={L} onClick={() => setSelectedIssue(issue)} onStatusChange={updateStatus} />
                      ))}
                      {colIssues.length === 0 && <p className="text-[10px] text-stone-300 text-center py-4 italic">—</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Table View */}
          {view === "table" && (
            <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden" data-testid="issues-table">
              <div className="hidden md:grid grid-cols-[1fr_90px_90px_120px_100px_80px_80px_80px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
                <span>Issue</span><span>Priority</span><span>Category</span><span>Location</span><span>Status</span><span>SLA</span><span>Cost</span><span>Actions</span>
              </div>
              <ScrollArea className="max-h-[60vh] md:max-h-[45vh]">
                {filtered.length === 0 ? (
                  <div className="p-8 text-center text-stone-400 text-sm">No issues found</div>
                ) : (
                  <>
                    {/* Mobile: IssueCard stack */}
                    <div className="md:hidden divide-y divide-stone-100">
                      {filtered.map(issue => (
                        <div key={issue.id} className="p-2" onClick={() => setSelectedIssue(issue)}>
                          <IssueCard issue={issue} L={L} onClick={() => setSelectedIssue(issue)} onStatusChange={updateStatus} />
                        </div>
                      ))}
                    </div>
                    {/* Desktop: grid table */}
                    <div className="hidden md:block">
                      {filtered.map(issue => (
                        <div key={issue.id} className="grid grid-cols-[1fr_90px_90px_120px_100px_80px_80px_80px] gap-2 px-4 py-2.5 border-b border-stone-100 items-center hover:bg-stone-50/50 cursor-pointer" onClick={() => setSelectedIssue(issue)} data-testid={`issue-row-${issue.id}`}>
                          <div>
                      <p className="text-sm font-medium text-stone-800 truncate">{issue.title || "Untitled"}</p>
                      <p className="text-[10px] text-stone-400 truncate">{issue.description?.slice(0, 50)}</p>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-fit ${PRIORITY_CONFIG[issue.priority]?.color || "bg-stone-100"}`}>{PRIORITY_CONFIG[issue.priority]?.label || issue.priority}</span>
                    <span className="text-[10px] text-stone-600">{CATEGORY_CONFIG[issue.category]?.icon} {CATEGORY_CONFIG[issue.category]?.label || issue.category}</span>
                    <span className="text-xs text-stone-600 truncate">{issue.location || issue.room_number || "—"}</span>
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border w-fit ${STATUS_CONFIG[issue.status]?.color || ""}`}>{STATUS_CONFIG[issue.status]?.label || issue.status}</span>
                    <span className={`text-[10px] font-medium ${issue.sla_breached ? "text-red-600 font-bold" : "text-stone-500"}`}>{issue.sla_breached ? "OVERDUE" : `${issue.sla_hours || 24}h`}</span>
                    <span className="text-xs text-stone-600">£{issue.actual_cost || 0}</span>
                    <button onClick={(e) => { e.stopPropagation(); setSelectedIssue(issue); }} className="p-1 text-stone-400 hover:text-stone-600"><Eye size={14} /></button>
                  </div>
                      ))}
                    </div>
                  </>
                )}
              </ScrollArea>
            </div>
          )}
        </>
      )}

      {/* Assets Tab */}
      {tab === "assets" && (
        <AssetsTab assets={assets} issues={issues} propertyId={activePropertyId} onRefresh={fetchData} onSelectIssue={setSelectedIssue} />
      )}

      {/* Team Tab */}
      {tab === "team" && (
        <TeamTab propertyId={activePropertyId} onRefresh={fetchData} />
      )}

      {/* Vendors Tab */}
      {tab === "vendors" && (
        <VendorsTab propertyId={activePropertyId} onRefresh={fetchData} />
      )}

      {/* Recurring / Preventive Tab */}
      {tab === "recurring" && (
        <RecurringTab recurring={recurring} propertyId={activePropertyId} onRefresh={() => { fetchRecurring(); fetchData(); }} />
      )}

      {/* Analytics Tab */}
      {tab === "analytics" && (
        <AnalyticsTab stats={stats} issues={issues} propertyId={activePropertyId} />
      )}

      {/* Issue Detail Drawer */}
      <IssueDetailDrawer issue={selectedIssue} onClose={() => setSelectedIssue(null)} assignees={assignees} L={L} onUpdate={() => { fetchData(); }} />
    </div>
  );
}

/* ==================== ISSUE CARD (Kanban) — Compact Modern ==================== */
function IssueCard({ issue, L, onClick, onStatusChange }) {
  const pri = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
  const nextStatus =
    issue.status === "open" ? "acknowledged" :
    issue.status === "acknowledged" ? "in_progress" :
    issue.status === "in_progress" ? "resolved" :
    issue.status === "resolved" ? "verified" :
    issue.status === "verified" ? "closed" : null;
  const nextLabel =
    nextStatus === "acknowledged" ? (L?.actAck || "Ack") :
    nextStatus === "in_progress" ? (L?.actStart || "Start") :
    nextStatus === "resolved" ? (L?.actResolve || "Resolve") :
    nextStatus === "verified" ? (L?.actVerify || "Verify") :
    nextStatus === "closed" ? (L?.actClose || "Close") : null;

  const fmtShort = (iso) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" }) + " · " +
             d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    } catch { return iso.slice(5, 16).replace("T", " "); }
  };
  const cat = CATEGORY_CONFIG[issue.category] || CATEGORY_CONFIG.general;
  const resolved = !!issue.resolved_at;
  const hasOverride = issue.priority_override > 0;

  return (
    <div className={`group relative bg-white rounded-lg border-l-[3px] ${pri.color.includes("red-600") ? "border-l-red-500" : pri.color.includes("orange") ? "border-l-orange-500" : pri.color.includes("amber-100") ? "border-l-amber-400" : "border-l-stone-300"} border-y border-r border-stone-200/70 p-2.5 hover:shadow-md hover:border-stone-300 transition-all cursor-pointer`}
         onClick={onClick} data-testid={`kanban-card-${issue.id}`}>
      {/* Top line: category icon + title + priority chip + advance button */}
      <div className="flex items-start gap-1.5 mb-1">
        <span className="text-sm leading-none shrink-0 mt-0.5" title={cat.label}>{cat.icon}</span>
        <p className="text-[13px] font-semibold text-stone-800 leading-tight line-clamp-2 flex-1">{issue.title || "Untitled"}</p>
        {nextStatus && (
          <button onClick={(e) => { e.stopPropagation(); onStatusChange(issue, nextStatus); }}
            className="opacity-0 group-hover:opacity-100 transition shrink-0 text-[9px] px-1.5 py-0.5 bg-orange-500 hover:bg-orange-600 text-white rounded font-bold"
            data-testid={`btn-advance-${issue.id}`}>{nextLabel}</button>
        )}
      </div>

      {/* Badges line */}
      <div className="flex items-center gap-1 mb-1.5 flex-wrap">
        <span className={`text-[8.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${pri.color}`}>{pri.label}</span>
        {hasOverride && (
          <span className="text-[8.5px] font-bold px-1.5 py-0.5 rounded bg-fuchsia-100 text-fuchsia-700" title="Priority Override">
            ★{issue.priority_override}
          </span>
        )}
        {issue.sla_breached && !resolved && (
          <span className="text-[8.5px] font-bold px-1.5 py-0.5 rounded bg-red-50 text-red-600 animate-pulse">SLA</span>
        )}
        {issue.room_number && (
          <span className="text-[8.5px] font-mono px-1.5 py-0.5 rounded bg-stone-100 text-stone-600">#{issue.room_number}</span>
        )}
      </div>

      {/* Asset chip */}
      {issue.asset_name && (
        <div className="text-[10px] text-violet-700 bg-violet-50 rounded px-1.5 py-0.5 mb-1.5 flex items-center gap-1 w-fit max-w-full">
          <Package size={9} className="shrink-0" />
          <span className="truncate">{issue.asset_name}</span>
        </div>
      )}

      {/* Footer: reporter + resolver in compact pills */}
      <div className="space-y-1 pt-1.5 border-t border-stone-100/80">
        {issue.reported_by && (
          <div className="flex items-center gap-1 text-[10px] text-stone-500">
            <User size={9} className="text-stone-400 shrink-0" />
            <span className="font-semibold text-stone-700 truncate max-w-[100px]">{issue.reported_by}</span>
            {issue.created_at && <span className="text-stone-400 ml-auto font-mono tabular-nums shrink-0">{fmtShort(issue.created_at)}</span>}
          </div>
        )}
        {resolved && (
          <div className="flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50/60 -mx-2.5 -mb-2.5 px-2.5 py-1.5 mt-1.5 rounded-b-lg">
            <CheckCircle size={10} className="text-emerald-500 shrink-0" weight="fill" />
            <span className="font-semibold truncate max-w-[90px]">{issue.resolved_by || "—"}</span>
            {issue.resolved_at && <span className="text-emerald-600 font-mono tabular-nums">{fmtShort(issue.resolved_at)}</span>}
            {issue.duration_hours != null && (
              <span className="ml-auto font-mono font-bold bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded text-[9px] shrink-0">
                {issue.duration_hours}h
              </span>
            )}
          </div>
        )}
        {!resolved && issue.assigned_to && (
          <div className="flex items-center gap-1 text-[10px] text-stone-600">
            <Wrench size={9} className="text-stone-400 shrink-0" />
            <span className="truncate">{issue.assigned_to}</span>
            {issue.assigned_department && (
              <span className="ml-auto text-[9px] bg-stone-100 text-stone-500 px-1 py-0.5 rounded uppercase tracking-wide shrink-0">
                {issue.assigned_department.slice(0, 4)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Tiny icon row: photos, comments */}
      {((issue.photos?.length || 0) + (issue.photos_before?.length || 0) + (issue.photos_after?.length || 0) + (issue.comments?.length || 0)) > 0 && (
        <div className="flex items-center gap-2 text-[9px] text-stone-400 mt-1.5 pt-1.5 border-t border-stone-100/80">
          {((issue.photos_before?.length || 0) + (issue.photos_after?.length || 0) + (issue.photos?.length || 0)) > 0 && (
            <span className="flex items-center gap-0.5"><Camera size={9} /> {(issue.photos_before?.length || 0) + (issue.photos_after?.length || 0) + (issue.photos?.length || 0)}</span>
          )}
          {issue.comments?.length > 0 && <span className="flex items-center gap-0.5"><ChatText size={9} /> {issue.comments.length}</span>}
        </div>
      )}
    </div>
  );
}

/* ==================== CREATE ISSUE DIALOG ==================== */
function CreateIssueDialog({ open, onClose, propertyId, assignees = [], assets = [], L, onCreated }) {
  const [form, setForm] = useState({ title: "", description: "", category: "general", priority: "medium", priority_override: 0, location: "", room_number: "", assigned_to: "", assigned_department: "", asset_id: "", asset_name: "" });
  const [creating, setCreating] = useState(false);
  const [photos, setPhotos] = useState([]);
  const fileRef = useRef(null);

  const handlePhoto = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setPhotos(prev => [...prev, { file, preview: ev.target.result, name: file.name }]);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const create = async () => {
    if (!form.title) { toast.error("Title is required"); return; }
    setCreating(true);
    try {
      const { data } = await axios.post(`${API}/maintenance/issues`, { ...form, property_id: propertyId });
      // Upload before photos
      for (const p of photos) {
        const fd = new FormData();
        fd.append("file", p.file);
        fd.append("photo_type", "before");
        await axios.post(`${API}/maintenance/upload-photo/${data.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      toast.success(L?.issueCreated || "Issue reported!"); setForm({ title: "", description: "", category: "general", priority: "medium", priority_override: 0, location: "", room_number: "", assigned_to: "", assigned_department: "", asset_id: "", asset_name: "" }); setPhotos([]); onCreated();
    } catch { toast.error(L?.issueFailed || "Failed to create"); }
    setCreating(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="create-issue-dialog">
        <DialogHeader><DialogTitle>{L?.dialogTitle || "Report Maintenance Issue"}</DialogTitle></DialogHeader>
        <div className="space-y-3 max-h-[65vh] overflow-y-auto">
          <Input data-testid="issue-title" value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} placeholder={L?.issueTitle || "Issue title *"} />
          <div className="grid grid-cols-2 gap-3">
            <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-category"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.icon} {v.label}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={form.priority} onValueChange={v => setForm(p => ({ ...p, priority: v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-priority"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="critical">{L?.priCritical || "Critical"} (SLA: 2h)</SelectItem>
                <SelectItem value="high">{L?.priHigh || "High"} (SLA: 8h)</SelectItem>
                <SelectItem value="medium">{L?.priMedium || "Medium"} (SLA: 24h)</SelectItem>
                <SelectItem value="low">{L?.priLow || "Low"} (SLA: 72h)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input data-testid="issue-location" value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} placeholder={L?.locPh || "Location (e.g. Lobby)"} />
            <Input data-testid="issue-room" value={form.room_number} onChange={e => setForm(p => ({ ...p, room_number: e.target.value }))} placeholder={L?.roomPh || "Room number"} />
          </div>
          <div>
            <label className="text-[10px] font-medium text-stone-500 block mb-0.5">{L?.overrideLbl || "Priority Override (0-10, optional)"}</label>
            <Input type="number" min="0" max="10" value={form.priority_override}
              onChange={e => setForm(p => ({ ...p, priority_override: Math.max(0, Math.min(10, parseInt(e.target.value) || 0)) }))}
              data-testid="issue-priority-override" placeholder={L?.overridePh || "0 = use default"} />
            <p className="text-[9px] text-stone-400 mt-0.5">{L?.overrideHint || "Leave at 0 to use default."}</p>
          </div>
          {/* Asset linker */}
          <Select value={form.asset_id || "_none"} onValueChange={v => {
            const a = assets.find(x => x.id === v);
            setForm(p => ({ ...p, asset_id: v === "_none" ? "" : v, asset_name: a?.name || "" }));
          }}>
            <SelectTrigger className="h-9 text-sm" data-testid="issue-asset"><SelectValue placeholder={L?.linkAsset || "Link to asset (optional)"} /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_none">{L?.noAsset || "No asset"}</SelectItem>
              {assets.map(a => (
                <SelectItem key={a.id} value={a.id}>{a.name} {a.location ? `· ${a.location}` : ""}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="grid grid-cols-2 gap-3">
            <Select value={form.assigned_department || "_auto"} onValueChange={v => setForm(p => ({ ...p, assigned_department: v === "_auto" ? "" : v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-department"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="_auto">{L?.autoDept || "Auto (by category)"}</SelectItem>
                <SelectItem value="maintenance">{L?.deptMaint || "Maintenance"}</SelectItem>
                <SelectItem value="housekeeping">{L?.deptHk || "Housekeeping"}</SelectItem>
                <SelectItem value="reception">{L?.deptRec || "Reception"}</SelectItem>
                <SelectItem value="management">{L?.deptMgmt || "Management"}</SelectItem>
                <SelectItem value="kitchen">{L?.deptKitch || "Kitchen"}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={form.assigned_to || "_unassigned"} onValueChange={v => setForm(p => ({ ...p, assigned_to: v === "_unassigned" ? "" : v }))}>
              <SelectTrigger className="h-9 text-sm" data-testid="issue-assignee"><SelectValue placeholder={L?.assignTo || "Assign to..."} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="_unassigned">{L?.unassigned || "Unassigned"}</SelectItem>
                {assignees.filter(a => a.type === "internal").length > 0 && <div className="px-2 py-1 text-[9px] font-bold text-stone-400 uppercase">Internal Team</div>}
                {assignees.filter(a => a.type === "internal").map(a => (
                  <SelectItem key={a.name} value={a.name}>{a.name} ({a.open_issues} open)</SelectItem>
                ))}
                {assignees.filter(a => a.type === "external").length > 0 && <div className="px-2 py-1 text-[9px] font-bold text-stone-400 uppercase">External Vendors</div>}
                {assignees.filter(a => a.type === "external").map(a => (
                  <SelectItem key={a.name} value={a.name}>{a.name} — £{a.hourly_rate}/h ({a.open_issues} open)</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Textarea data-testid="issue-description" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder={L?.descPh || "Describe the issue in detail..."} rows={3} />

          {/* Before Photos */}
          <div>
            <label className="text-xs font-medium text-stone-600 mb-1.5 block">{L?.beforePhotos || "Before Photos (current condition)"}</label>
            <div className="flex gap-2 flex-wrap">
              {photos.map((p, i) => (
                <div key={i} className="w-16 h-16 rounded-lg border border-stone-200 overflow-hidden relative group">
                  <img src={p.preview} alt="" className="w-full h-full object-cover" />
                  <button onClick={() => setPhotos(prev => prev.filter((_, idx) => idx !== i))} className="absolute top-0 right-0 bg-red-500 text-white p-0.5 rounded-bl opacity-0 group-hover:opacity-100 transition"><X size={10} /></button>
                </div>
              ))}
              <button onClick={() => fileRef.current?.click()} className="w-16 h-16 rounded-lg border-2 border-dashed border-stone-300 flex items-center justify-center text-stone-400 hover:border-orange-400 hover:text-orange-500 transition" data-testid="btn-add-photo">
                <Camera size={20} />
              </button>
              <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={handlePhoto} className="hidden" />
            </div>
          </div>

          <button onClick={create} disabled={creating} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl hover:bg-orange-600 disabled:opacity-50 transition" data-testid="btn-submit-issue">
            {creating ? "Submitting..." : (L?.submit || "Submit Issue")}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ==================== ISSUE DETAIL DRAWER ==================== */
function IssueDetailDrawer({ issue, onClose, assignees = [], L, onUpdate }) {
  const [comment, setComment] = useState("");
  const [sending, setSending] = useState(false);
  const [costForm, setCostForm] = useState({ estimated_cost: 0, actual_cost: 0, cost_notes: "" });
  const [showCost, setShowCost] = useState(false);
  const beforeRef = useRef(null);
  const afterRef = useRef(null);
  const [detailTab, setDetailTab] = useState("info");
  const [lightbox, setLightbox] = useState(null); // info, timeline, photos

  useEffect(() => {
    if (issue) setCostForm({ estimated_cost: issue.estimated_cost || 0, actual_cost: issue.actual_cost || 0, cost_notes: issue.cost_notes || "" });
  }, [issue]);

  if (!issue) return null;

  const addComment = async () => {
    if (!comment.trim()) return;
    setSending(true);
    try {
      await axios.post(`${API}/maintenance/issues/${issue.id}/comment`, { text: comment });
      setComment(""); toast.success("Comment added"); onUpdate();
    } catch { toast.error("Failed"); }
    setSending(false);
  };

  const uploadPhoto = async (e, type) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("photo_type", type);
    try {
      await axios.post(`${API}/maintenance/upload-photo/${issue.id}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`${type === "before" ? "Before" : "After"} photo uploaded`); onUpdate();
    } catch { toast.error("Upload failed"); }
    e.target.value = "";
  };

  const saveCost = async () => {
    try {
      await axios.put(`${API}/maintenance/issues/${issue.id}/cost`, costForm);
      toast.success("Cost saved"); setShowCost(false); onUpdate();
    } catch { toast.error("Failed"); }
  };

  const updateStatus = async (s, notes) => {
    try {
      const body = { status: s };
      if (notes) body.resolution_notes = notes;
      await axios.put(`${API}/maintenance/issues/${issue.id}`, body);
      toast.success(`Status: ${s}`); onUpdate();
    } catch { toast.error("Failed"); }
  };

  const pri = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
  const sta = STATUS_CONFIG[issue.status] || {};

  // Calculate timing
  const created = issue.created_at ? new Date(issue.created_at) : null;
  const resolved = issue.resolved_at ? new Date(issue.resolved_at) : null;
  const totalTime = created && resolved ? Math.round((resolved - created) / 3600000) : null;

  const TIMELINE_ICONS = {
    created: { icon: <Plus size={10} weight="bold" />, color: "bg-blue-500" },
    acknowledged: { icon: <Eye size={10} />, color: "bg-indigo-500" },
    started: { icon: <Wrench size={10} />, color: "bg-amber-500" },
    assigned: { icon: <ArrowsClockwise size={10} />, color: "bg-violet-500" },
    resolved: { icon: <CheckCircle size={10} weight="fill" />, color: "bg-emerald-500" },
    closed: { icon: <X size={10} />, color: "bg-stone-500" },
    comment: { icon: <ChatText size={10} />, color: "bg-stone-400" },
    photo_uploaded: { icon: <Camera size={10} />, color: "bg-orange-500" },
  };

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/40 flex items-center justify-end z-50" onClick={onClose}>
        <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }} className="bg-white h-full w-full md:max-w-md shadow-xl" onClick={(e) => e.stopPropagation()} data-testid="issue-detail-drawer">
          <div className="p-4 border-b border-stone-100 flex items-center justify-between">
            <h3 className="font-semibold text-stone-800 text-sm truncate pr-4">{issue.title || "Issue Detail"}</h3>
            <button onClick={onClose} className="p-1.5 hover:bg-stone-100 rounded-lg"><X size={16} className="text-stone-400" /></button>
          </div>
          <ScrollArea className="h-[calc(100vh-56px)]">
            <div className="p-4 space-y-4">
              {/* Status + Priority */}
              <div className="flex gap-2 flex-wrap">
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${pri.color}`}>{pri.label}</span>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${sta.color}`}>{sta.label}</span>
                {issue.sla_breached && <span className="text-xs font-bold text-red-600 bg-red-50 px-2.5 py-1 rounded-full">SLA BREACHED</span>}
                {totalTime !== null && <span className="text-xs text-stone-500 bg-stone-50 px-2.5 py-1 rounded-full">Total: {totalTime}h</span>}
              </div>

              {/* Quick Status Actions */}
              <div className="flex gap-1.5 flex-wrap">
                {["open", "acknowledged", "in_progress", "resolved", "closed"].filter(s => s !== issue.status).map(s => (
                  <button key={s} onClick={() => updateStatus(s)} className="text-[10px] px-2.5 py-1 border border-stone-200 rounded-lg hover:bg-stone-50 text-stone-600 font-medium transition" data-testid={`btn-status-${s}`}>
                    {STATUS_CONFIG[s]?.label}
                  </button>
                ))}
              </div>

              {/* Detail Tabs */}
              <div className="flex gap-1 bg-stone-100 p-0.5 rounded-lg">
                {[
                  { id: "info", label: "Info" },
                  { id: "timeline", label: `Timeline (${(issue.timeline || []).length})` },
                  { id: "photos", label: `Photos (${(issue.photos_before || []).length + (issue.photos_after || []).length})` },
                ].map(t => (
                  <button key={t.id} onClick={() => setDetailTab(t.id)} className={`flex-1 px-2 py-1.5 text-[10px] font-medium rounded-md transition ${detailTab === t.id ? "bg-white shadow-sm text-stone-800" : "text-stone-500"}`} data-testid={`detail-tab-${t.id}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              {/* INFO TAB */}
              {detailTab === "info" && (
                <div className="space-y-4">
                  {/* Visual Lifecycle Timeline */}
                  <LifecycleTimeline issue={issue} L={L} />

                  {/* Details */}
                  <div className="bg-stone-50 rounded-xl p-3 space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-stone-500">Category</span><span className="font-medium">{CATEGORY_CONFIG[issue.category]?.icon} {CATEGORY_CONFIG[issue.category]?.label}</span></div>
                    <div className="flex justify-between"><span className="text-stone-500">Location</span><span className="font-medium">{issue.location || issue.room_number || "—"}</span></div>
                    <div className="flex justify-between items-center"><span className="text-stone-500">Assigned</span>
                      <Select value={issue.assigned_to || "_unassigned"} onValueChange={async (v) => {
                        try { await axios.put(`${API}/maintenance/issues/${issue.id}`, { assigned_to: v === "_unassigned" ? "" : v }); toast.success("Reassigned"); onUpdate(); } catch {}
                      }}>
                        <SelectTrigger className="h-7 w-40 text-xs border-stone-200" data-testid="reassign-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="_unassigned">Unassigned</SelectItem>
                          {assignees.filter(a => a.type === "internal").map(a => <SelectItem key={a.name} value={a.name}>{a.name}</SelectItem>)}
                          {assignees.filter(a => a.type === "external").map(a => <SelectItem key={a.name} value={a.name}>{a.name} (vendor)</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex justify-between"><span className="text-stone-500">Department</span><span className="font-medium capitalize">{issue.assigned_department || "—"}</span></div>
                    <div className="flex justify-between"><span className="text-stone-500">SLA Target</span><span className="font-medium">{issue.sla_hours}h</span></div>
                  </div>

                  {issue.description && (
                    <div><h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">Description</h4><p className="text-sm text-stone-700 bg-stone-50 rounded-xl p-3">{issue.description}</p></div>
                  )}

                  {/* Cost */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Cost Tracking</h4>
                      <button onClick={() => setShowCost(!showCost)} className="text-[10px] text-orange-600 font-medium hover:underline">{showCost ? "Cancel" : "Edit Costs"}</button>
                    </div>
                    {showCost ? (
                      <div className="bg-stone-50 rounded-xl p-3 space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          <div><label className="text-[10px] text-stone-500">Estimated</label><Input type="number" value={costForm.estimated_cost} onChange={e => setCostForm(p => ({ ...p, estimated_cost: Number(e.target.value) }))} className="h-8 text-sm" /></div>
                          <div><label className="text-[10px] text-stone-500">Actual</label><Input type="number" value={costForm.actual_cost} onChange={e => setCostForm(p => ({ ...p, actual_cost: Number(e.target.value) }))} className="h-8 text-sm" /></div>
                        </div>
                        <Input value={costForm.cost_notes} onChange={e => setCostForm(p => ({ ...p, cost_notes: e.target.value }))} placeholder="Cost notes..." className="h-8 text-sm" />
                        <button onClick={saveCost} className="text-xs px-3 py-1.5 bg-orange-500 text-white rounded-lg font-medium">Save</button>
                      </div>
                    ) : (
                      <div className="bg-stone-50 rounded-xl p-3 flex gap-4 text-sm">
                        <div><span className="text-stone-500">Est:</span> <span className="font-medium">£{issue.estimated_cost || 0}</span></div>
                        <div><span className="text-stone-500">Actual:</span> <span className="font-medium">£{issue.actual_cost || 0}</span></div>
                      </div>
                    )}
                  </div>

                  {/* Comments */}
                  <div>
                    <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">Comments ({(issue.comments || []).length})</h4>
                    <div className="space-y-2 mb-3 max-h-32 overflow-y-auto">
                      {(issue.comments || []).map(c => (
                        <div key={c.id} className="bg-stone-50 rounded-lg p-2.5">
                          <div className="flex justify-between items-center mb-0.5">
                            <span className="text-xs font-semibold text-stone-700">{c.author}</span>
                            <span className="text-[10px] text-stone-400">{c.created_at ? new Date(c.created_at).toLocaleString() : ""}</span>
                          </div>
                          <p className="text-xs text-stone-600">{c.text}</p>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Input data-testid="comment-input" value={comment} onChange={(e) => setComment(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addComment()} placeholder="Add a comment..." className="h-8 text-xs flex-1" />
                      <button onClick={addComment} disabled={sending} className="px-3 py-1.5 bg-[#1e3a5f] text-white text-xs font-medium rounded-lg hover:bg-[#15304f] disabled:opacity-50" data-testid="btn-add-comment">
                        <Send size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* TIMELINE TAB */}
              {detailTab === "timeline" && (
                <div className="space-y-1" data-testid="issue-timeline">
                  <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Full Activity Timeline</h4>
                  {(issue.timeline || []).length === 0 ? (
                    <p className="text-xs text-stone-400 text-center py-6">No activity yet</p>
                  ) : (
                    <div className="relative pl-5">
                      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-stone-200" />
                      {(issue.timeline || []).map((entry, i) => {
                        const icon = TIMELINE_ICONS[entry.action] || { icon: <Clock size={10} />, color: "bg-stone-400" };
                        return (
                          <div key={i} className="relative pb-4" data-testid={`timeline-entry-${i}`}>
                            <div className={`absolute left-[-13px] top-0.5 w-4 h-4 rounded-full ${icon.color} flex items-center justify-center text-white`}>
                              {icon.icon}
                            </div>
                            <div className="ml-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-stone-800">{entry.by}</span>
                                <span className="text-[10px] text-stone-400">{entry.at ? new Date(entry.at).toLocaleString() : ""}</span>
                              </div>
                              <p className="text-xs text-stone-600 mt-0.5">{entry.detail}</p>
                              <span className="text-[9px] text-stone-400 capitalize">{entry.action.replace("_", " ")}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* PHOTOS TAB - Before & After */}
              {detailTab === "photos" && (
                <div className="space-y-5" data-testid="issue-photos">
                  {((issue.photos_before || []).length + (issue.photos_after || []).length) > 0 && (
                    <button onClick={() => setLightbox(0)} className="w-full py-2 rounded-lg bg-stone-900 text-white text-xs font-bold" data-testid="issue-gallery-open">🖼 Galeriyi aç (kaydırarak gez · {(issue.photos_before || []).length} önce / {(issue.photos_after || []).length} sonra)</button>
                  )}
                  {lightbox !== null && <PhotoLightbox photos={[...(issue.photos_before || []).map((p) => ({ ...p, kind: "before" })), ...(issue.photos_after || []).map((p) => ({ ...p, kind: "after" }))]} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />}
                  {/* Before Photos */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-xs font-semibold text-red-600 uppercase tracking-wide flex items-center gap-1">
                        <Camera size={12} /> Before ({(issue.photos_before || []).length})
                      </h4>
                      <button onClick={() => beforeRef.current?.click()} className="text-[10px] text-orange-600 font-medium hover:underline" data-testid="btn-add-before-photo">+ Add Before Photo</button>
                      <input ref={beforeRef} type="file" accept="image/*" capture="environment" onChange={(e) => uploadPhoto(e, "before")} className="hidden" />
                    </div>
                    {(issue.photos_before || []).length > 0 ? (
                      <div className="grid grid-cols-3 gap-2">
                        {(issue.photos_before || []).map((p, i) => (
                          <div key={i} className="rounded-lg overflow-hidden border-2 border-red-200 relative group cursor-zoom-in" onClick={() => setLightbox(i)} data-testid={`issue-photo-before-${i}`}>
                            <img src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt="" className="w-full h-24 object-cover" />
                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-1.5 py-0.5">
                              <p className="text-[8px] text-white truncate">{p.uploaded_by}</p>
                              <p className="text-[7px] text-white/60">{p.uploaded_at ? new Date(p.uploaded_at).toLocaleDateString() : ""}</p>
                            </div>
                            <div className="absolute top-1 left-1 bg-red-600 text-white text-[7px] font-bold px-1 rounded">BEFORE</div>
                          </div>
                        ))}
                      </div>
                    ) : <p className="text-xs text-stone-400 bg-stone-50 rounded-lg p-4 text-center">No before photos</p>}
                  </div>

                  {/* Divider */}
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-stone-200" />
                    <span className="text-[10px] font-bold text-stone-400">VS</span>
                    <div className="flex-1 h-px bg-stone-200" />
                  </div>

                  {/* After Photos */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-xs font-semibold text-emerald-600 uppercase tracking-wide flex items-center gap-1">
                        <CheckCircle size={12} weight="fill" /> After ({(issue.photos_after || []).length})
                      </h4>
                      <button onClick={() => afterRef.current?.click()} className="text-[10px] text-emerald-600 font-medium hover:underline" data-testid="btn-add-after-photo">+ Add After Photo</button>
                      <input ref={afterRef} type="file" accept="image/*" capture="environment" onChange={(e) => uploadPhoto(e, "after")} className="hidden" />
                    </div>
                    {(issue.photos_after || []).length > 0 ? (
                      <div className="grid grid-cols-3 gap-2">
                        {(issue.photos_after || []).map((p, i) => (
                          <div key={i} className="rounded-lg overflow-hidden border-2 border-emerald-200 relative group cursor-zoom-in" onClick={() => setLightbox((issue.photos_before || []).length + i)} data-testid={`issue-photo-after-${i}`}>
                            <img src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt="" className="w-full h-24 object-cover" />
                            <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-1.5 py-0.5">
                              <p className="text-[8px] text-white truncate">{p.uploaded_by}</p>
                              <p className="text-[7px] text-white/60">{p.uploaded_at ? new Date(p.uploaded_at).toLocaleDateString() : ""}</p>
                            </div>
                            <div className="absolute top-1 left-1 bg-emerald-600 text-white text-[7px] font-bold px-1 rounded">AFTER</div>
                          </div>
                        ))}
                      </div>
                    ) : <p className="text-xs text-stone-400 bg-stone-50 rounded-lg p-4 text-center">No after photos yet — upload when job is complete</p>}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

/* ==================== RECURRING TAB ==================== */
function RecurringTab({ recurring, propertyId, onRefresh }) {
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", category: "general", priority: "medium", frequency: "monthly", location: "", assigned_to: "" });

  const create = async () => {
    if (!form.title) return;
    try {
      await axios.post(`${API}/maintenance/recurring`, { ...form, property_id: propertyId });
      toast.success("Recurring schedule created"); setShowNew(false);
      setForm({ title: "", description: "", category: "general", priority: "medium", frequency: "monthly", location: "", assigned_to: "" });
      onRefresh();
    } catch { toast.error("Failed"); }
  };

  const generate = async () => {
    try {
      const { data } = await axios.post(`${API}/maintenance/recurring/generate/${propertyId}`);
      toast.success(`Generated ${data.generated} tasks from ${data.schedules_checked} schedules`);
      onRefresh();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-4" data-testid="recurring-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">Schedule preventive maintenance tasks that auto-generate on a recurring basis</p>
        <div className="flex gap-2">
          <button onClick={generate} className="px-3 py-2 text-xs font-medium border border-stone-200 rounded-lg hover:bg-stone-50 flex items-center gap-1.5" data-testid="btn-generate-recurring"><Lightning size={13} /> Generate Due Tasks</button>
          <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-new-recurring"><Plus size={13} weight="bold" /> New Schedule</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
        <div className="grid grid-cols-[1fr_100px_90px_90px_100px_100px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
          <span>Task</span><span>Category</span><span>Priority</span><span>Frequency</span><span>Next Due</span><span>Status</span>
        </div>
        {recurring.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">No recurring schedules. Create one to automate preventive maintenance.</div>
        ) : recurring.map(r => (
          <div key={r.id} className="grid grid-cols-[1fr_100px_90px_90px_100px_100px] gap-2 px-4 py-3 border-b border-stone-100 items-center" data-testid={`recurring-${r.id}`}>
            <div>
              <p className="text-sm font-medium text-stone-800">{r.title}</p>
              <p className="text-[10px] text-stone-400">{r.location || "All areas"} · {r.assigned_to || "Unassigned"}</p>
            </div>
            <span className="text-xs text-stone-600">{CATEGORY_CONFIG[r.category]?.icon} {CATEGORY_CONFIG[r.category]?.label}</span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-fit ${PRIORITY_CONFIG[r.priority]?.color}`}>{PRIORITY_CONFIG[r.priority]?.label}</span>
            <span className="text-xs text-stone-600 capitalize">{r.frequency}</span>
            <span className="text-xs text-stone-600">{r.next_due ? new Date(r.next_due).toLocaleDateString() : "—"}</span>
            <span className={`text-[10px] font-medium ${r.is_active ? "text-emerald-600" : "text-stone-400"}`}>{r.is_active ? "Active" : "Paused"}</span>
          </div>
        ))}
      </div>

      {/* New Recurring Dialog */}
      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-recurring-dialog">
          <DialogHeader><DialogTitle>New Recurring Schedule</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} placeholder="Task title *" data-testid="recurring-title" />
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.category} onValueChange={v => setForm(p => ({ ...p, category: v }))}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>{Object.entries(CATEGORY_CONFIG).map(([k, v]) => <SelectItem key={k} value={k}>{v.icon} {v.label}</SelectItem>)}</SelectContent>
              </Select>
              <Select value={form.frequency} onValueChange={v => setForm(p => ({ ...p, frequency: v }))}>
                <SelectTrigger className="h-9 text-sm" data-testid="recurring-frequency"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="quarterly">Quarterly</SelectItem>
                  <SelectItem value="yearly">Yearly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Input value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} placeholder="Location" />
            <Input value={form.assigned_to} onChange={e => setForm(p => ({ ...p, assigned_to: e.target.value }))} placeholder="Assign to" />
            <Textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Description..." rows={2} />
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-recurring">Create Schedule</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==================== ANALYTICS TAB ==================== */
function AnalyticsTab({ stats, issues, propertyId }) {
  const [qrRoom, setQrRoom] = useState("");
  const [qrRoomShow, setQrRoomShow] = useState("");
  const categories = Object.entries(stats.by_category || {}).sort((a, b) => b[1] - a[1]);
  const priorities = Object.entries(stats.by_priority || {}).sort((a, b) => b[1] - a[1]);
  const maxCat = Math.max(...categories.map(c => c[1]), 1);
  const maxPri = Math.max(...priorities.map(p => p[1]), 1);

  // Avg resolution time
  const resolvedIssues = issues.filter(i => i.resolved_at && i.created_at);
  let avgResTime = 0;
  if (resolvedIssues.length > 0) {
    const totalMs = resolvedIssues.reduce((acc, i) => acc + (new Date(i.resolved_at) - new Date(i.created_at)), 0);
    avgResTime = Math.round(totalMs / resolvedIssues.length / 3600000); // hours
  }

  return (
    <div className="space-y-4" data-testid="analytics-tab">
      <div className="grid grid-cols-3 gap-4">
        {/* Summary */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Summary</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-stone-500">Total Issues</span><span className="font-bold">{stats.total || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Open</span><span className="font-bold text-red-600">{stats.open || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">In Progress</span><span className="font-bold text-amber-600">{stats.in_progress || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Resolved</span><span className="font-bold text-emerald-600">{stats.resolved || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">SLA Breaches</span><span className="font-bold text-red-600">{stats.overdue || 0}</span></div>
            <div className="flex justify-between"><span className="text-stone-500">Avg Resolution</span><span className="font-bold">{avgResTime}h</span></div>
          </div>
        </div>

        {/* By Category */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">By Category</h4>
          <div className="space-y-2">
            {categories.map(([cat, count]) => (
              <div key={cat}>
                <div className="flex justify-between text-xs mb-0.5"><span className="text-stone-600">{CATEGORY_CONFIG[cat]?.icon} {CATEGORY_CONFIG[cat]?.label || cat}</span><span className="font-bold">{count}</span></div>
                <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden"><div className="h-full bg-orange-400 rounded-full" style={{ width: `${(count / maxCat) * 100}%` }} /></div>
              </div>
            ))}
            {categories.length === 0 && <p className="text-xs text-stone-400">No data</p>}
          </div>
        </div>

        {/* Cost Summary */}
        <div className="bg-white rounded-xl border border-stone-200/60 p-4">
          <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Cost Summary</h4>
          <div className="space-y-3">
            <div className="text-center">
              <p className="text-3xl font-bold text-stone-800">£{(stats.costs?.total_actual || 0).toLocaleString()}</p>
              <p className="text-xs text-stone-500 mt-0.5">Total Actual Cost</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-stone-600">£{(stats.costs?.total_estimated || 0).toLocaleString()}</p>
              <p className="text-xs text-stone-400">Estimated</p>
            </div>
            {/* By Priority */}
            <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mt-3">By Priority</h4>
            {priorities.map(([pri, count]) => (
              <div key={pri}>
                <div className="flex justify-between text-xs mb-0.5"><span className={`font-medium ${pri === "critical" ? "text-red-600" : pri === "high" ? "text-orange-600" : "text-stone-600"}`}>{PRIORITY_CONFIG[pri]?.label || pri}</span><span className="font-bold">{count}</span></div>
                <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden"><div className={`h-full rounded-full ${pri === "critical" ? "bg-red-500" : pri === "high" ? "bg-orange-500" : pri === "medium" ? "bg-amber-400" : "bg-stone-300"}`} style={{ width: `${(count / maxPri) * 100}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Room QR Codes for Guest Reporting */}
      <div className="bg-white rounded-xl border border-stone-200/60 p-4 mt-4">
        <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">Guest Room QR Codes</h4>
        <p className="text-xs text-stone-500 mb-3">Generate QR codes for rooms. Guests scan to report maintenance issues directly.</p>
        <div className="flex items-center gap-3">
          <Input value={qrRoom} onChange={(e) => setQrRoom(e.target.value)} placeholder="Room number (e.g. 301)" className="max-w-[180px] h-8 text-xs" data-testid="qr-room-input" />
          <button onClick={() => { if (qrRoom.trim()) setQrRoomShow(qrRoom.trim()); }} className="px-3 py-1.5 bg-orange-500 text-white text-xs font-medium rounded-lg" data-testid="btn-gen-room-qr">Generate QR</button>
        </div>
        {qrRoomShow && (
          <div className="mt-3 bg-stone-50 rounded-xl p-4 flex items-center gap-4">
            <div data-testid="room-qr-code">
              <QRCodeSVG value={`${BASE_URL}/room-help/${propertyId}/${qrRoomShow}`} size={100} level="M" includeMargin />
            </div>
            <div>
              <p className="text-sm font-semibold text-stone-800">Room {qrRoomShow}</p>
              <code className="text-[10px] text-stone-500 block mt-0.5">{BASE_URL}/room-help/{propertyId}/{qrRoomShow}</code>
              <div className="flex gap-2 mt-2">
                <button onClick={() => { navigator.clipboard.writeText(`${BASE_URL}/room-help/${propertyId}/${qrRoomShow}`); toast.success("Link copied!"); }} className="text-[10px] text-orange-600 font-medium hover:underline">Copy Link</button>
                <button onClick={() => {
                  const svg = document.querySelector('[data-testid="room-qr-code"] svg');
                  if (!svg) return;
                  const svgData = new XMLSerializer().serializeToString(svg);
                  const canvas = document.createElement("canvas");
                  canvas.width = 200; canvas.height = 200;
                  const ctx = canvas.getContext("2d");
                  const img = new Image();
                  img.onload = () => { ctx.fillStyle = "#fff"; ctx.fillRect(0,0,200,200); ctx.drawImage(img, 0, 0, 200, 200); const a = document.createElement("a"); a.download = `room-${qrRoomShow}-qr.png`; a.href = canvas.toDataURL("image/png"); a.click(); };
                  img.src = "data:image/svg+xml;base64," + btoa(svgData);
                }} className="text-[10px] text-orange-600 font-medium hover:underline">Download QR</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ==================== TEAM TAB ==================== */

/* ==================== LIFECYCLE TIMELINE — visual step-by-step flow ==================== */
function LifecycleTimeline({ issue, L }) {
  const fmtDT = (iso) => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      return {
        date: d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "2-digit" }),
        time: d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
      };
    } catch { return null; }
  };

  const diffHuman = (fromIso, toIso) => {
    if (!fromIso || !toIso) return null;
    try {
      const ms = new Date(toIso) - new Date(fromIso);
      if (ms < 0) return null;
      const mins = Math.floor(ms / 60000);
      if (mins < 60) return `${mins}m`;
      const hrs = mins / 60;
      if (hrs < 24) return `${hrs.toFixed(1)}h`;
      return `${(hrs / 24).toFixed(1)}d`;
    } catch { return null; }
  };

  const steps = [
    { key: "created", label: L?.tlReported || "Reported", at: issue.created_at, by: issue.reported_by,
      icon: <Plus size={12} weight="bold" />, color: "bg-blue-500", ring: "ring-blue-100" },
    { key: "acknowledged", label: L?.tlAcked || "Acknowledged", at: issue.acknowledged_at, by: issue.acknowledged_by,
      icon: <Eye size={12} />, color: "bg-indigo-500", ring: "ring-indigo-100" },
    { key: "started", label: L?.tlStarted || "Started", at: issue.started_at, by: issue.started_by || issue.assigned_to,
      icon: <Wrench size={12} />, color: "bg-amber-500", ring: "ring-amber-100" },
    { key: "resolved", label: L?.tlResolved || "Resolved", at: issue.resolved_at, by: issue.resolved_by,
      icon: <CheckCircle size={12} weight="fill" />, color: "bg-emerald-500", ring: "ring-emerald-100" },
    { key: "verified", label: L?.tlVerified || "Verified", at: issue.verified_at, by: issue.verified_by,
      icon: <CheckCircle size={12} weight="fill" />, color: "bg-teal-500", ring: "ring-teal-100" },
    { key: "closed", label: L?.tlClosed || "Closed", at: issue.closed_at, by: issue.closed_by,
      icon: <X size={12} weight="bold" />, color: "bg-stone-500", ring: "ring-stone-100" },
  ];

  const firstIso = issue.created_at;
  const lastIso = issue.closed_at || issue.verified_at || issue.resolved_at;
  const totalDur = diffHuman(firstIso, lastIso);

  return (
    <div className="bg-gradient-to-br from-stone-50 to-white border border-stone-200 rounded-xl p-4" data-testid="lifecycle-timeline">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-[11px] font-bold uppercase tracking-wider text-stone-600">Lifecycle</h4>
        {totalDur && (
          <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
            {L?.tlTotalTime || "Total"}: {totalDur}
          </span>
        )}
      </div>
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-[13px] top-1 bottom-1 w-0.5 bg-gradient-to-b from-stone-200 via-stone-200 to-transparent" />
        <div className="space-y-3">
          {steps.map((s, idx) => {
            const done = !!s.at;
            const dt = fmtDT(s.at);
            const prevIso = idx > 0 ? steps[idx - 1].at : null;
            const dur = done && prevIso ? diffHuman(prevIso, s.at) : null;
            if (!done && !(idx < steps.length && steps.slice(0, idx).every(x => x.at))) {
              // hide future steps that haven't been reached (keep structure tidy)
              const prevReached = idx === 0 || steps[idx - 1].at;
              if (!prevReached) return null;
            }
            return (
              <div key={s.key} className="flex items-start gap-3" data-testid={`timeline-step-${s.key}`}>
                <div className={`relative z-10 w-[26px] h-[26px] rounded-full flex items-center justify-center text-white shrink-0 ring-4 ${done ? s.color + " " + s.ring : "bg-stone-200 ring-stone-100"} transition-all`}>
                  {done ? s.icon : <span className="w-1.5 h-1.5 rounded-full bg-stone-400" />}
                </div>
                <div className="flex-1 min-w-0 pt-0.5">
                  <div className="flex items-baseline justify-between gap-2 flex-wrap">
                    <span className={`text-xs font-bold ${done ? "text-stone-800" : "text-stone-400"}`}>{s.label}</span>
                    {dur && <span className="text-[9px] font-mono text-stone-400">+{dur}</span>}
                  </div>
                  {done ? (
                    <div className="text-[10px] text-stone-500 flex items-center gap-2 flex-wrap mt-0.5">
                      <span className="font-semibold text-stone-700">{s.by || L?.tlNoActor || "—"}</span>
                      {dt && <span className="font-mono tabular-nums">{dt.date} · {dt.time}</span>}
                    </div>
                  ) : (
                    <div className="text-[10px] italic text-stone-400">{L?.tlPending || "Pending"}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}


function TeamTab({ propertyId, onRefresh }) {
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ name: "", role: "technician", phone: "", email: "", specialities: [] });
  const [specInput, setSpecInput] = useState("");

  useEffect(() => {
    const load = async () => {
      try { const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); } catch {}
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  const create = async () => {
    if (!form.name) return;
    try {
      await axios.post(`${API}/maintenance/team`, { ...form, property_id: propertyId });
      toast.success("Team member added");
      setShowNew(false); setForm({ name: "", role: "technician", phone: "", email: "", specialities: [] });
      const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); onRefresh();
    } catch { toast.error("Failed"); }
  };

  const toggle = async (m) => {
    await axios.put(`${API}/maintenance/team/${m.id}`, { is_active: !m.is_active });
    const { data } = await axios.get(`${API}/maintenance/team/${propertyId}`); setTeam(data); onRefresh();
  };

  return (
    <div className="space-y-4" data-testid="team-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">Your internal maintenance team members and their current workload</p>
        <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-add-team">
          <Plus size={13} weight="bold" /> Add Member
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {team.map(m => (
          <div key={m.id} className={`bg-white rounded-xl border ${m.is_active ? "border-stone-200" : "border-stone-100 opacity-60"} p-4`} data-testid={`team-${m.id}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-full bg-orange-100 flex items-center justify-center text-orange-700 font-bold text-sm">{m.name?.charAt(0)}</div>
                <div>
                  <p className="text-sm font-semibold text-stone-800">{m.name}</p>
                  <p className="text-[10px] text-stone-400 capitalize">{m.role}</p>
                </div>
              </div>
              <button onClick={() => toggle(m)} className={`text-[9px] px-2 py-0.5 rounded font-medium ${m.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                {m.is_active ? "Active" : "Inactive"}
              </button>
            </div>
            {m.specialities?.length > 0 && (
              <div className="flex gap-1 flex-wrap mb-2">
                {m.specialities.map((s, i) => <span key={i} className="text-[9px] px-1.5 py-0.5 bg-stone-100 text-stone-600 rounded">{s}</span>)}
              </div>
            )}
            <div className="flex gap-3 text-[10px] text-stone-500">
              <span className="text-orange-600 font-bold">{m.open_issues || 0} open</span>
              <span className="text-emerald-600">{m.total_resolved || 0} resolved</span>
              {m.phone && <span>{m.phone}</span>}
            </div>
          </div>
        ))}
        {!loading && team.length === 0 && <div className="col-span-3 p-8 text-center text-stone-400 text-sm">No team members added yet</div>}
      </div>

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-team-dialog">
          <DialogHeader><DialogTitle>Add Team Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Full name *" data-testid="team-name" />
            <Select value={form.role} onValueChange={v => setForm(p => ({ ...p, role: v }))}>
              <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="technician">Technician</SelectItem>
                <SelectItem value="supervisor">Supervisor</SelectItem>
                <SelectItem value="electrician">Electrician</SelectItem>
                <SelectItem value="plumber">Plumber</SelectItem>
                <SelectItem value="handyman">Handyman</SelectItem>
                <SelectItem value="hvac_tech">HVAC Technician</SelectItem>
              </SelectContent>
            </Select>
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="Phone" />
              <Input value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Specialities</label>
              <div className="flex gap-1 flex-wrap mb-1.5">
                {form.specialities.map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-orange-50 text-orange-700 rounded-full flex items-center gap-1">
                    {s} <button onClick={() => setForm(p => ({ ...p, specialities: p.specialities.filter((_, idx) => idx !== i) }))}><X size={8} /></button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1">
                <Input value={specInput} onChange={e => setSpecInput(e.target.value)} placeholder="e.g. Plumbing" className="h-8 text-xs" onKeyDown={(e) => { if (e.key === "Enter" && specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} />
                <button onClick={() => { if (specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} className="px-2 h-8 bg-stone-100 text-stone-600 rounded text-xs">Add</button>
              </div>
            </div>
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-team">Add Member</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ==================== VENDORS TAB ==================== */
function VendorsTab({ propertyId, onRefresh }) {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ company_name: "", contact_person: "", phone: "", email: "", specialities: [], hourly_rate: 0, notes: "" });
  const [specInput, setSpecInput] = useState("");

  useEffect(() => {
    const load = async () => {
      try { const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); } catch {}
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  const create = async () => {
    if (!form.company_name) return;
    try {
      await axios.post(`${API}/maintenance/vendors`, { ...form, property_id: propertyId });
      toast.success("Vendor added");
      setShowNew(false); setForm({ company_name: "", contact_person: "", phone: "", email: "", specialities: [], hourly_rate: 0, notes: "" });
      const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); onRefresh();
    } catch { toast.error("Failed"); }
  };

  const toggle = async (v) => {
    await axios.put(`${API}/maintenance/vendors/${v.id}`, { is_active: !v.is_active });
    const { data } = await axios.get(`${API}/maintenance/vendors/${propertyId}`); setVendors(data); onRefresh();
  };

  return (
    <div className="space-y-4" data-testid="vendors-tab">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">External service providers and contractors you work with</p>
        <button onClick={() => setShowNew(true)} className="px-3 py-2 bg-orange-500 text-white text-xs font-semibold rounded-lg hover:bg-orange-600 flex items-center gap-1.5" data-testid="btn-add-vendor">
          <Plus size={13} weight="bold" /> Add Vendor
        </button>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden">
        <div className="grid grid-cols-[1fr_120px_120px_80px_80px_80px_80px] gap-2 px-4 py-2.5 bg-stone-50 text-[10px] font-semibold text-stone-500 uppercase tracking-wide border-b">
          <span>Vendor</span><span>Contact</span><span>Specialities</span><span>Rate</span><span>Open</span><span>Resolved</span><span>Total Cost</span>
        </div>
        {vendors.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm">No vendors added yet. Add external service providers to assign maintenance tasks.</div>
        ) : vendors.map(v => (
          <div key={v.id} className={`grid grid-cols-[1fr_120px_120px_80px_80px_80px_80px] gap-2 px-4 py-3 border-b border-stone-100 items-center ${!v.is_active ? "opacity-50" : ""}`} data-testid={`vendor-${v.id}`}>
            <div>
              <p className="text-sm font-semibold text-stone-800">{v.company_name}</p>
              <p className="text-[10px] text-stone-400">{v.contact_person || "—"}</p>
            </div>
            <div className="text-[10px] text-stone-500">
              {v.phone && <p>{v.phone}</p>}
              {v.email && <p className="truncate">{v.email}</p>}
            </div>
            <div className="flex gap-1 flex-wrap">
              {(v.specialities || []).map((s, i) => <span key={i} className="text-[8px] px-1 py-0.5 bg-blue-50 text-blue-700 rounded">{s}</span>)}
            </div>
            <span className="text-xs font-medium text-stone-700">£{v.hourly_rate}/h</span>
            <span className="text-xs font-bold text-orange-600">{v.open_issues || 0}</span>
            <span className="text-xs text-emerald-600">{v.total_resolved || 0}</span>
            <span className="text-xs font-medium text-stone-700">£{(v.total_cost || 0).toLocaleString()}</span>
          </div>
        ))}
      </div>

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-vendor-dialog">
          <DialogHeader><DialogTitle>Add External Vendor</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input value={form.company_name} onChange={e => setForm(p => ({ ...p, company_name: e.target.value }))} placeholder="Company name *" data-testid="vendor-name" />
            <Input value={form.contact_person} onChange={e => setForm(p => ({ ...p, contact_person: e.target.value }))} placeholder="Contact person" />
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="Phone" />
              <Input value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Hourly Rate (£)</label>
                <Input type="number" value={form.hourly_rate} onChange={e => setForm(p => ({ ...p, hourly_rate: Number(e.target.value) }))} placeholder="0" data-testid="vendor-rate" />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Specialities</label>
              <div className="flex gap-1 flex-wrap mb-1.5">
                {form.specialities.map((s, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full flex items-center gap-1">
                    {s} <button onClick={() => setForm(p => ({ ...p, specialities: p.specialities.filter((_, idx) => idx !== i) }))}><X size={8} /></button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1">
                <Input value={specInput} onChange={e => setSpecInput(e.target.value)} placeholder="e.g. Plumbing, Electrical" className="h-8 text-xs" onKeyDown={(e) => { if (e.key === "Enter" && specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} />
                <button onClick={() => { if (specInput.trim()) { setForm(p => ({ ...p, specialities: [...p.specialities, specInput.trim()] })); setSpecInput(""); } }} className="px-2 h-8 bg-stone-100 text-stone-600 rounded text-xs">Add</button>
              </div>
            </div>
            <Textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} placeholder="Notes (contract details, availability...)" rows={2} />
            <button onClick={create} className="w-full py-2.5 bg-orange-500 text-white text-sm font-bold rounded-xl" data-testid="btn-create-vendor">Add Vendor</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}


/* ==================== ASSETS TAB — Asset ↔ Issue history + QR ==================== */
function AssetsTab({ assets = [], issues = [], propertyId, onRefresh, onSelectIssue }) {
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState(null);
  const [qrAsset, setQrAsset] = useState(null);
  const [search, setSearch] = useState("");

  const loadHistory = async (asset) => {
    setSelected(asset);
    setHistory({ loading: true });
    try {
      const { data } = await axios.get(`${API}/maintenance/issues/by-asset/${asset.id}`);
      setHistory(data);
    } catch { setHistory({ loading: false, issues: [], count: 0 }); }
  };

  const issuesByAsset = assets.map(a => ({
    ...a,
    open_issues: issues.filter(i => i.asset_id === a.id && !["resolved", "closed"].includes(i.status)).length,
    total_issues: issues.filter(i => i.asset_id === a.id).length,
  }));
  const filtered = issuesByAsset.filter(a =>
    !search || a.name?.toLowerCase().includes(search.toLowerCase()) || a.location?.toLowerCase().includes(search.toLowerCase())
  );

  if (!assets.length) {
    return (
      <div className="bg-white border border-stone-200 rounded-xl p-10 text-center" data-testid="assets-empty">
        <Package className="w-10 h-10 mx-auto text-stone-300 mb-2" />
        <h3 className="text-sm font-bold text-stone-600">No assets yet</h3>
        <p className="text-xs text-stone-400 mt-1">Add assets from the Asset Register module. They will appear here with issue history.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="assets-tab">
      <div className="flex items-center gap-2">
        <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search assets..." className="max-w-xs h-8 text-xs" data-testid="assets-search" />
        <div className="text-[10px] text-stone-500">{filtered.length} of {assets.length} assets</div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-stone-50 border-b border-stone-200">
            <tr>
              <th className="text-left py-2 px-3 font-semibold text-stone-600">Asset</th>
              <th className="text-left py-2 px-3 font-semibold text-stone-600">Location</th>
              <th className="text-center py-2 px-3 font-semibold text-stone-600">Open</th>
              <th className="text-center py-2 px-3 font-semibold text-stone-600">Total</th>
              <th className="text-right py-2 px-3 font-semibold text-stone-600">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(a => (
              <tr key={a.id} className="border-b border-stone-100 hover:bg-stone-50/60" data-testid={`asset-row-${a.id.slice(0, 6)}`}>
                <td className="py-2 px-3 font-medium text-stone-800">{a.name}</td>
                <td className="py-2 px-3 text-stone-500">{a.location || "—"}</td>
                <td className="py-2 px-3 text-center">
                  {a.open_issues > 0 ? <Badge className="bg-red-100 text-red-700">{a.open_issues}</Badge> : <span className="text-stone-300">—</span>}
                </td>
                <td className="py-2 px-3 text-center text-stone-600">{a.total_issues}</td>
                <td className="py-2 px-3 text-right">
                  <div className="inline-flex items-center gap-1">
                    <button onClick={() => loadHistory(a)} className="px-2 py-1 text-[10px] bg-blue-50 text-blue-700 hover:bg-blue-100 rounded font-semibold" data-testid={`asset-history-${a.id.slice(0, 6)}`}>
                      <History className="w-3 h-3 inline mr-0.5" />History
                    </button>
                    <button onClick={() => setQrAsset(a)} className="px-2 py-1 text-[10px] bg-violet-50 text-violet-700 hover:bg-violet-100 rounded font-semibold" data-testid={`asset-qr-${a.id.slice(0, 6)}`}>
                      <QrCode className="w-3 h-3 inline mr-0.5" />QR
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* History Drawer */}
      {selected && history && !history.loading && (
        <Dialog open onOpenChange={() => { setSelected(null); setHistory(null); }}>
          <DialogContent className="max-w-2xl" data-testid="asset-history-dialog">
            <DialogHeader>
              <DialogTitle>{selected.name} — Issue History</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <div className="bg-stone-50 rounded-lg p-3 text-center">
                <div className="text-2xl font-black text-stone-800">{history.count || 0}</div>
                <div className="text-[10px] text-stone-500">Total Issues</div>
              </div>
              <div className="bg-emerald-50 rounded-lg p-3 text-center">
                <div className="text-2xl font-black text-emerald-700">{history.mttr_hours ?? "—"}h</div>
                <div className="text-[10px] text-emerald-600">MTTR (avg repair)</div>
              </div>
              <div className="bg-blue-50 rounded-lg p-3 text-center">
                <div className="text-2xl font-black text-blue-700">{history.mtbf_days ?? "—"}d</div>
                <div className="text-[10px] text-blue-600">MTBF (avg gap)</div>
              </div>
            </div>
            <div className="max-h-[50vh] overflow-y-auto">
              {(history.issues || []).length === 0 ? (
                <p className="text-center py-6 text-stone-400 text-sm">No issues recorded for this asset.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 sticky top-0">
                    <tr>
                      <th className="text-left py-2 px-2">Title</th>
                      <th className="text-left py-2 px-2">Created</th>
                      <th className="text-left py-2 px-2">Resolved</th>
                      <th className="text-center py-2 px-2">Duration</th>
                      <th className="text-left py-2 px-2">By</th>
                      <th className="text-center py-2 px-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.issues.map(i => (
                      <tr key={i.id} className="border-b hover:bg-stone-50 cursor-pointer" onClick={() => { onSelectIssue(i); setSelected(null); }}>
                        <td className="py-2 px-2 font-medium">{i.title}</td>
                        <td className="py-2 px-2 text-stone-500">{(i.created_at || "").slice(0, 10)}</td>
                        <td className="py-2 px-2 text-stone-500">{(i.resolved_at || "—").slice(0, 10)}</td>
                        <td className="py-2 px-2 text-center font-mono">{i.duration_hours != null ? `${i.duration_hours}h` : "—"}</td>
                        <td className="py-2 px-2 text-stone-600">{i.resolved_by || i.assigned_to || "—"}</td>
                        <td className="py-2 px-2 text-center">
                          <Badge className={STATUS_CONFIG[i.status]?.badge || "bg-stone-100"}>{STATUS_CONFIG[i.status]?.label || i.status}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* QR Modal */}
      {qrAsset && (
        <Dialog open onOpenChange={() => setQrAsset(null)}>
          <DialogContent className="max-w-sm" data-testid="asset-qr-dialog">
            <DialogHeader><DialogTitle>{qrAsset.name} — QR Tag</DialogTitle></DialogHeader>
            <div className="flex flex-col items-center py-4 space-y-3">
              <div className="p-4 bg-white border-2 border-stone-200 rounded-xl">
                <QRCodeSVG value={`${window.location.origin}/maintenance/report?asset=${qrAsset.id}&property=${propertyId}`} size={200} />
              </div>
              <div className="text-center">
                <div className="text-sm font-bold">{qrAsset.name}</div>
                <div className="text-[10px] text-stone-500">{qrAsset.location || ""} · {qrAsset.id.slice(0, 8)}</div>
              </div>
              <p className="text-[10px] text-stone-400 text-center">Print and stick on the asset. Staff scan → opens report form pre-linked to this asset.</p>
              <button onClick={() => window.print()} className="px-4 py-2 bg-stone-800 text-white text-xs font-semibold rounded-lg hover:bg-stone-700">Print QR</button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}



export function PhotoLightbox({ photos, index, onIndex, onClose }) {
  const touch = useRef(null);
  const n = photos.length;
  const go = useCallback((d) => onIndex((index + d + n) % n), [index, n, onIndex]);
  useEffect(() => {
    const k = (e) => { if (e.key === "ArrowRight") go(1); else if (e.key === "ArrowLeft") go(-1); else if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [go, onClose]);
  if (!n) return null;
  const p = photos[index] || photos[0];
  return (
    <div className="fixed inset-0 z-[100] bg-black/95 flex flex-col select-none" data-testid="photo-lightbox"
      onTouchStart={(e) => { touch.current = e.touches[0].clientX; }}
      onTouchEnd={(e) => { if (touch.current === null) return; const dx = e.changedTouches[0].clientX - touch.current; if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1); touch.current = null; }}>
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <span className={`text-[10px] font-black px-2 py-0.5 rounded ${p.kind === "after" ? "bg-emerald-600" : "bg-red-600"}`} data-testid="lightbox-kind">{p.kind === "after" ? "SONRA / AFTER" : "ÖNCE / BEFORE"}</span>
        <span className="text-xs text-white/70" data-testid="lightbox-counter">{index + 1} / {n}</span>
        <button onClick={onClose} className="text-white text-xl leading-none px-2" data-testid="lightbox-close">×</button>
      </div>
      <div className="flex-1 flex items-center justify-center relative px-2">
        <button onClick={() => go(-1)} className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/10 text-white text-2xl" data-testid="lightbox-prev">‹</button>
        <img src={`${process.env.REACT_APP_BACKEND_URL}${p.url}`} alt="" className="max-h-[70vh] max-w-full object-contain rounded-lg" data-testid="lightbox-img" />
        <button onClick={() => go(1)} className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/10 text-white text-2xl" data-testid="lightbox-next">›</button>
      </div>
      <div className="px-4 pb-2 text-center text-[11px] text-white/70">{p.uploaded_by}{p.uploaded_at ? ` · ${new Date(p.uploaded_at).toLocaleString()}` : ""}{p.source === "hk_mobile" ? " · HK mobil" : ""}</div>
      <div className="flex gap-1.5 overflow-x-auto px-4 pb-4">
        {photos.map((x, i) => <img key={i} src={`${process.env.REACT_APP_BACKEND_URL}${x.url}`} alt="" onClick={() => onIndex(i)} className={`w-14 h-14 object-cover rounded-md border-2 shrink-0 cursor-pointer ${i === index ? "border-white" : x.kind === "after" ? "border-emerald-500/60" : "border-red-500/60"}`} data-testid={`lightbox-thumb-${i}`} />)}
      </div>
    </div>
  );
}
