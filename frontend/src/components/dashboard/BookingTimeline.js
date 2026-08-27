import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CalendarDays,
  Search, Plus, X, User, Phone, Mail, CreditCard, Bed, Clock, MapPin,
  GripVertical, CheckSquare, Square, LogIn, LogOut, Users, AlertTriangle,
  FileText, Send, Receipt, Home, Globe, PhoneCall, Share2, UserCheck, UserX, Lock, StickyNote, LayoutList, Copy, Filter,
  Bell, Building2, Wrench, Printer, Edit3, Banknote, Landmark,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS_COLORS = {
  // Eviivo-style polar-opposite palette — warm = active/problem, cool = future, grey = past
  pending:     { bar: "bg-gradient-to-br from-yellow-300 via-yellow-400 to-amber-500",       text: "text-amber-950",   border: "border-amber-600",   label: "Pending",     shadow: "shadow-yellow-500/40" },
  confirmed:   { bar: "bg-gradient-to-br from-sky-400 via-blue-500 to-indigo-600",            text: "text-white",       border: "border-indigo-700",  label: "Confirmed",   shadow: "shadow-blue-500/40" },
  checked_in:  { bar: "bg-gradient-to-br from-rose-500 via-red-600 to-rose-700",              text: "text-white",       border: "border-red-800",     label: "Checked In",  shadow: "shadow-red-500/50" },
  checked_out: { bar: "bg-gradient-to-br from-stone-300 via-stone-400 to-stone-500",          text: "text-stone-800",   border: "border-stone-600",   label: "Checked Out", shadow: "shadow-stone-400/30" },
  no_show:     { bar: "bg-gradient-to-br from-purple-700 via-violet-800 to-slate-900",        text: "text-white",       border: "border-purple-900",  label: "No show",     shadow: "shadow-purple-700/50" },
  cancelled:   { bar: "bg-[repeating-linear-gradient(135deg,#64748b,#64748b_4px,#94a3b8_4px,#94a3b8_8px)]", text: "text-white", border: "border-slate-700", label: "Cancelled", shadow: "shadow-slate-500/30" },
  // Operational / housekeeping overlays
  unassigned:        { bar: "bg-gradient-to-br from-white to-stone-100 border-2 border-dashed", text: "text-stone-700", border: "border-stone-400", label: "Unassigned",       shadow: "shadow-stone-200/30" },
  awaiting_cleaning: { bar: "bg-gradient-to-br from-amber-50 to-amber-100 border-2",             text: "text-amber-900", border: "border-amber-400", label: "Awaiting Cleaning",shadow: "shadow-amber-300/30" },
  being_cleaned:     { bar: "bg-gradient-to-br from-sky-50 to-sky-100 border-2",                 text: "text-sky-900",   border: "border-sky-400",   label: "Being Cleaned",    shadow: "shadow-sky-300/30" },
  blocked:           { bar: "bg-[repeating-linear-gradient(45deg,#78716c,#78716c_6px,#57534e_6px,#57534e_12px)]", text: "text-white", border: "border-stone-700", label: "Blocked",     shadow: "shadow-stone-500/40" },
  // Contextual (computed) — decorate the base colour
  arriving_today:  { accent: "ring-2 ring-offset-1 ring-amber-400",  dotCls: "bg-amber-400",  label: "Arrives today" },
  departing_today: { accent: "ring-2 ring-offset-1 ring-fuchsia-400",dotCls: "bg-fuchsia-400",label: "Departs today" },
};

// Per-source channel colour strip (left edge accent) — adds multi-colour variety based on booking source
const SOURCE_STRIP = {
  "Booking.com": "bg-[#003580]",
  "Airbnb":      "bg-[#FF5A5F]",
  "Expedia":     "bg-[#FFC72C]",
  "Google":      "bg-[#4285F4]",
  "Direct":      "bg-emerald-600",
  "Web":         "bg-violet-600",
  "Agoda":       "bg-[#FF3B00]",
  "Hotelbeds":   "bg-[#00A3E4]",
  "Stripe":      "bg-[#635BFF]",
  "Turkish_Payment": "bg-rose-600",
  "PayAtHotel":  "bg-slate-600",
};
const getSourceStrip = (src) => SOURCE_STRIP[src] || "bg-stone-500";

// Compute effective status based on today's date + booking flags
const computeContext = (bk, todayISO) => {
  if (bk.status === "cancelled" || bk.status === "no_show") return null;
  if (bk.check_in === todayISO && bk.status !== "checked_in") return "arriving_today";
  if (bk.check_out === todayISO && bk.status === "checked_in") return "departing_today";
  return null;
};

// Resolve final display status — only promote to unassigned/blocked/cleaning when EXPLICITLY flagged.
// A booking rendered inside a room row is assigned by definition.
const resolveDisplayStatus = (bk) => {
  if (bk.blocked === true) return "blocked";
  if (bk.housekeeping_status === "being_cleaned") return "being_cleaned";
  if (bk.housekeeping_status === "awaiting_cleaning") return "awaiting_cleaning";
  if (bk.unassigned === true || bk.status === "unassigned") return "unassigned";
  return bk.status || "confirmed";
};

const HK_COLORS = { clean: "bg-emerald-400", dirty: "bg-red-400", inspected: "bg-blue-400" };

// ---------- Smart Collision Detector ----------
// Greedy interval lane assignment (Google-Calendar style).
// For a set of bookings in a single room, assigns each to the lowest available
// lane (0-indexed) such that no two bookings in the same lane overlap in time.
// Returns: { laneOf: { [bookingId]: laneIdx }, totalLanes: number }
const assignLanes = (bookings) => {
  const sorted = [...bookings].sort((a, b) => {
    if (a.check_in !== b.check_in) return a.check_in < b.check_in ? -1 : 1;
    return a.check_out > b.check_out ? -1 : 1; // longer stays first on ties
  });
  const laneEnds = []; // laneEnds[i] = check_out ISO of last booking in lane i
  const laneOf = {};
  sorted.forEach((bk) => {
    let placed = -1;
    for (let i = 0; i < laneEnds.length; i++) {
      if (laneEnds[i] <= bk.check_in) { placed = i; break; }
    }
    if (placed === -1) {
      laneEnds.push(bk.check_out);
      placed = laneEnds.length - 1;
    } else {
      laneEnds[placed] = bk.check_out;
    }
    laneOf[bk.id] = placed;
  });
  return { laneOf, totalLanes: laneEnds.length };
};

const MAX_VISIBLE_LANES = 2; // Rows render up to 2 lanes; overflow → "+N more" pill

// Build overflow clusters: group bookings in lane >= MAX_VISIBLE_LANES into
// time-continuous clusters so we can render one "+N more" pill per cluster.
const buildOverflowClusters = (bookings, laneOf) => {
  const hidden = bookings
    .filter((b) => laneOf[b.id] >= MAX_VISIBLE_LANES)
    .sort((a, b) => (a.check_in < b.check_in ? -1 : 1));
  if (hidden.length === 0) return [];
  const clusters = [];
  let cur = null;
  hidden.forEach((bk) => {
    if (!cur || bk.check_in >= cur.check_out) {
      cur = { check_in: bk.check_in, check_out: bk.check_out, items: [bk] };
      clusters.push(cur);
    } else {
      cur.items.push(bk);
      if (bk.check_out > cur.check_out) cur.check_out = bk.check_out;
    }
  });
  return clusters;
};
// ------------------------------------------------

// Real platform favicons — uses Google's favicon CDN to fetch the actual brand logo
// e.g. Booking.com's blue "B." or Airbnb's real Bélo symbol — not letter initials.
const PLATFORM_DOMAINS = {
  "booking":          "booking.com",
  "booking.com":      "booking.com",
  "airbnb":           "airbnb.com",
  "expedia":          "expedia.com",
  "hotels.com":       "hotels.com",
  "hotels":           "hotels.com",
  "agoda":            "agoda.com",
  "google":           "google.com",
  "tripadvisor":      "tripadvisor.com",
  "vrbo":             "vrbo.com",
  // Non-domain sources below also normalise to web icons
};
// Special icons for non-OTA sources — use Lucide SVG for same clean look as real favicons
const NON_OTA = {
  "direct":         { bg: "#1F2937", Icon: Home,      label: "Direct" },
  "website":        { bg: "#0EA5E9", Icon: Globe,     label: "Website" },
  "website_widget": { bg: "#0EA5E9", Icon: Globe,     label: "Website Widget" },
  "walk_in":        { bg: "#78716C", Icon: UserCheck, label: "Walk-in" },
  "walk-in":        { bg: "#78716C", Icon: UserCheck, label: "Walk-in" },
  "phone":          { bg: "#10B981", Icon: PhoneCall, label: "Phone" },
  "affiliate":      { bg: "#8B5CF6", Icon: Share2,    label: "Affiliate" },
  "other":          { bg: "#6366F1", Icon: Globe,     label: "Other" },
};
// 2-letter codes used by the PMS
const CODE_TO_KEY = {
  "BO": "booking", "AB": "airbnb", "EX": "expedia", "HO": "hotels.com",
  "AG": "agoda",   "GO": "google", "TA": "tripadvisor", "VR": "vrbo",
  "DR": "direct",  "WB": "website", "OT": "website_widget",
  "WI": "walk_in", "PH": "phone",   "AF": "affiliate",
};

const PlatformLogo = ({ source, size = 16 }) => {
  let key = (source || "").toString().toLowerCase().trim();
  // Normalise 2-letter PMS codes to full names
  const upper = (source || "").toString().toUpperCase().trim();
  if (upper.length === 2 && CODE_TO_KEY[upper]) {
    key = CODE_TO_KEY[upper];
  }
  const domain = PLATFORM_DOMAINS[key] || PLATFORM_DOMAINS[key.split(".")[0]] || PLATFORM_DOMAINS[key.replace(/[_-]/g, "")];
  if (domain) {
    // Fetch the real site favicon — this returns Booking.com's actual logo, Airbnb's actual Bélo, etc.
    return (
      <img
        src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
        alt={domain}
        title={domain}
        width={size}
        height={size}
        style={{ borderRadius: 3, flexShrink: 0, objectFit: "contain", background: "white" }}
        onError={(e) => { e.currentTarget.style.display = "none"; }}
      />
    );
  }
  const non = NON_OTA[key];
  if (non) {
    const Icon = non.Icon;
    return (
      <span
        className="inline-flex items-center justify-center rounded-full flex-shrink-0"
        style={{ width: size, height: size, backgroundColor: non.bg }}
        title={non.label}
      >
        <Icon size={size * 0.6} color="white" strokeWidth={2.5} />
      </span>
    );
  }
  // Fallback — unknown source
  return (
    <span
      className="inline-flex items-center justify-center rounded-full flex-shrink-0 leading-none"
      style={{ width: size, height: size, backgroundColor: "#6366F1", fontSize: size * 0.55, color: "white", fontWeight: 900 }}
      title={source || "Unknown"}
    >?</span>
  );
};

function getOccColor(pct) {
  if (pct >= 85) return "text-red-600 font-black";
  if (pct >= 60) return "text-amber-600 font-bold";
  if (pct >= 30) return "text-emerald-600 font-bold";
  return "text-stone-400";
}

export const BookingTimeline = ({ properties, activePropertyId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [viewDays, setViewDays] = useState(14);
  const [collapsed, setCollapsed] = useState({});
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [quickActions, setQuickActions] = useState(null); // { booking, anchorRect } — click popover
  const [createBooking, setCreateBookingState] = useState(null); // { room_id, room_name, room_type_id, check_in } | null
  const [createForm, setCreateForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", nights: 1, adults: 2, children: 0 });
  const [creating, setCreating] = useState(false);
  const [showPassOver, setShowPassOver] = useState(false);
  const [showGuestList, setShowGuestList] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  const [statusFilter, setStatusFilter] = useState("all"); // all|pending|confirmed|checked_in|checked_out|no_show
  const [sourceFilter, setSourceFilter] = useState("all");
  const [oosBlocks, setOosBlocks] = useState([]); // [{room_id, start, end, reason}]
  const [oosForm, setOosForm] = useState(null); // {room_id, room_name, start} when modal open
  const [detailData, setDetailData] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [dragBooking, setDragBooking] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkMode, setBulkMode] = useState(false);
  const [todaysActions, setTodaysActions] = useState(null);
  const [showBulkPanel, setShowBulkPanel] = useState(false);
  const [folio, setFolio] = useState(null);
  // Sub-folios (split folio) — list + currently-active tab
  const [subFolios, setSubFolios] = useState([]);
  const [activeSubFolio, setActiveSubFolio] = useState("primary");
  const [newSubFolioOpen, setNewSubFolioOpen] = useState(false);
  const [newSubFolioName, setNewSubFolioName] = useState("");
  const [showAddCharge, setShowAddCharge] = useState(false);
  const [detailTab, setDetailTab] = useState("info");
  const [upsells, setUpsells] = useState(null);
  const [collisionCluster, setCollisionCluster] = useState(null); // { room, cluster } for "+N more" pill modal
  const [showResolver, setShowResolver] = useState(false); // overbooking auto-suggest resolver modal
  const [quickPay, setQuickPay] = useState(null); // { booking } when the flashing balance chip is clicked
  const [payLink, setPayLink] = useState(null);
  const [payLinkBusy, setPayLinkBusy] = useState(false);
  const scrollRef = useRef(null);
  const obNotifiedRef = useRef(false);

  useEffect(() => {
    if (!data || obNotifiedRef.current) return;
    let cnt = 0;
    data.groups.forEach(g => g.rooms.forEach(r => {
      const act = r.bookings.filter(b => !["cancelled", "checked_out", "no_show"].includes(b.status));
      cnt += act.filter((b1, i) => act.slice(i + 1).some(b2 => b1.check_in < b2.check_out && b2.check_in < b1.check_out)).length;
    }));
    if (cnt > 0) {
      obNotifiedRef.current = true;
      toast.error(`Overbooking uyarısı: ${cnt} oda çakışması var — takvimde kırmızı işaretli günlere bakın ve rezervasyonu sürükleyip başka odaya taşıyın.`, { duration: 8000 });
    }
  }, [data]);

  const pid = activePropertyId || "all";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/bookings/timeline/${pid}?start=${startDate}&days=${viewDays}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [pid, startDate, viewDays]);

  useEffect(() => { load(); }, [load]);

  const loadTodaysActions = async () => {
    try {
      const { data: d } = await axios.get(`${API}/bookings/timeline/${pid}/todays-actions`);
      setTodaysActions(d);
    } catch { /* silent */ }
  };

  const loadOosBlocks = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/rooms/oos-blocks${pid && pid !== "all" ? `?property_id=${pid}` : ""}`);
      setOosBlocks(d || []);
    } catch { /* silent */ }
  }, [pid]);

  useEffect(() => { loadTodaysActions(); loadOosBlocks(); }, [pid, loadOosBlocks]);

  const openDetail = async (bookingId) => {
    setSelectedBooking(bookingId);
    setDetailTab("info");
    setFolio(null);
    setPayLink(null);
    setShowAddCharge(false);
    setUpsells(null);
    try {
      const { data: d } = await axios.get(`${API}/bookings/timeline/${pid}/detail/${bookingId}`);
      setDetailData(d);
    } catch { /* silent */ }
  };

  const loadUpsells = async (bookingId) => {
    try {
      const { data: d } = await axios.get(`${API}/revenue/upsell/${bookingId}`);
      setUpsells(d);
    } catch { /* silent */ }
  };

  const acceptUpsell = async (suggestion) => {
    if (!selectedBooking) return;
    try {
      await axios.post(`${API}/revenue/upsell/${selectedBooking}/accept`, {
        type: suggestion.type, price: suggestion.price, description: suggestion.title,
        target_room_type: suggestion.target_room_type || "",
      });
      toast.success(`Upsell accepted: ${suggestion.title}`);
      loadFolio(selectedBooking);
      loadUpsells(selectedBooking);
    } catch { toast.error("Failed"); }
  };

  const loadFolio = async (bookingId) => {
    try {
      const { data: d } = await axios.get(`${API}/folio/${bookingId}`);
      setFolio(d);
    } catch { /* silent */ }
    // Also load sub-folios (split folio tabs)
    try {
      const { data: sf } = await axios.get(`${API}/folio/${bookingId}/sub-folios`);
      setSubFolios(sf.sub_folios || []);
    } catch { /* silent */ }
  };

  const createSubFolio = async () => {
    if (!selectedBooking || !newSubFolioName.trim()) return;
    try {
      await axios.post(`${API}/folio/${selectedBooking}/sub-folios`, { name: newSubFolioName.trim() });
      toast.success(`Sub-folio "${newSubFolioName}" created`);
      setNewSubFolioName(""); setNewSubFolioOpen(false);
      loadFolio(selectedBooking);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const deleteSubFolio = async (sfId) => {
    if (!selectedBooking) return;
    if (!window.confirm("Delete this sub-folio? All items will be moved to Primary.")) return;
    try {
      await axios.delete(`${API}/folio/${selectedBooking}/sub-folios/${sfId}`);
      toast.success("Sub-folio deleted");
      setActiveSubFolio("primary");
      loadFolio(selectedBooking);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const moveFolioItem = async (itemId, targetSfId) => {
    try {
      await axios.put(`${API}/folio/items/${itemId}/move`, { sub_folio_id: targetSfId });
      toast.success("Moved");
      loadFolio(selectedBooking);
    } catch { toast.error("Failed"); }
  };

  // Per-sub-folio PDF print + email — uses the same blob-open trick as whole-folio print
  const printSubFolio = async (sfId) => {
    if (!selectedBooking) return;
    try {
      const { data } = await axios.get(`${API}/folio/${selectedBooking}/sub-folios/${sfId}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch { toast.error("Could not open sub-folio PDF"); }
  };

  const [emailSubFolioFor, setEmailSubFolioFor] = useState(null);  // {sfId, sfName, payerEmail}
  const [editPayerFor, setEditPayerFor] = useState(null);          // {sfId, sfName, payerName, payerEmail}
  const savePayer = async (name, email) => {
    if (!editPayerFor || !selectedBooking) return;
    try {
      await axios.put(
        `${API}/folio/${selectedBooking}/sub-folios/${editPayerFor.sfId}`,
        { payer_name: name, payer_email: email },
      );
      toast.success("Payer updated");
      setEditPayerFor(null);
      loadFolio(selectedBooking);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };
  const sendSubFolioEmail = async (to, subject, message) => {
    if (!emailSubFolioFor) return;
    try {
      const { data } = await axios.post(
        `${API}/folio/${selectedBooking}/sub-folios/${emailSubFolioFor.sfId}/email`,
        { to, subject, message },
      );
      toast.success(`Sub-folio emailed to ${(data.sent_to || []).join(", ")}`);
      setEmailSubFolioFor(null);
    } catch (e) { toast.error(e?.response?.data?.detail || "Send failed"); }
  };

  const addCharge = async (desc, amount, category) => {
    if (!selectedBooking) return;
    try {
      const body = { description: desc, unit_price: parseFloat(amount), quantity: 1, category };
      if (activeSubFolio && activeSubFolio !== "primary") body.sub_folio_id = activeSubFolio;
      await axios.post(`${API}/folio/${selectedBooking}/add-charge`, body);
      toast.success("Charge added");
      loadFolio(selectedBooking);
      setShowAddCharge(false);
    } catch { toast.error("Failed"); }
  };

  const addPayment = async (amount, method) => {
    if (!selectedBooking) return;
    try {
      const body = { amount: parseFloat(amount), method };
      if (activeSubFolio && activeSubFolio !== "primary") body.sub_folio_id = activeSubFolio;
      await axios.post(`${API}/folio/${selectedBooking}/add-payment`, body);
      toast.success("Payment recorded");
      loadFolio(selectedBooking);
      load();
    } catch { toast.error("Failed"); }
  };

  const sendCheckinLink = async () => {
    if (!selectedBooking) return;
    try {
      await axios.post(`${API}/guest-checkin/send-link/${selectedBooking}`);
      toast.success("Check-in link sent to guest");
    } catch { toast.error("Failed"); }
  };

  // Stripe pay-by-link — resepsiyon tek tıkla ödeme linki üretir
  const generatePayLink = async () => {
    if (!selectedBooking || !folio) return;
    setPayLinkBusy(true);
    try {
      const { data } = await axios.post(`${API}/payments/checkout`, {
        amount: folio.totals.balance_due,
        currency: "gbp",
        property_id: detailData?.property_id || (pid !== "all" ? pid : "default"),
        booking_id: selectedBooking,
        description: `Konaklama ödemesi — ${detailData?.guest_name || selectedBooking}`,
        origin_url: window.location.origin,
      });
      setPayLink(data.checkout_url);
      try { await navigator.clipboard.writeText(data.checkout_url); toast.success("Ödeme linki üretildi ve panoya kopyalandı"); }
      catch { toast.success("Ödeme linki üretildi"); }
    } catch (e) { toast.error(e.response?.data?.detail || "Ödeme linki üretilemedi"); }
    setPayLinkBusy(false);
  };

  const emailPayLink = async () => {
    if (!payLink) return;
    const to = detailData?.guest_email;
    if (!to) { toast.error("Misafirin e-posta adresi yok"); return; }
    try {
      await axios.post(`${API}/payments/email-link`, {
        to, link: payLink, booking_id: selectedBooking, amount: folio?.totals?.balance_due,
      });
      toast.success(`Ödeme linki ${to} adresine gönderildi`);
    } catch { toast.error("E-posta gönderilemedi"); }
  };

  // Download a PDF (respects auth header from axios defaults) and open it in a new tab.
  const downloadPdf = async (path, filename) => {
    try {
      const { data } = await axios.get(`${API}${path}`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
      const w = window.open(url, "_blank", "noopener,noreferrer");
      if (!w) {
        // Popup blocked — force download instead
        const a = document.createElement("a");
        a.href = url; a.download = filename; a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      toast.success("PDF opened in new tab");
    } catch (e) {
      toast.error("Could not generate PDF");
    }
  };

  // Email the Reg Card / Folio PDF directly to the guest (or custom recipient) via Resend.
  const emailDocument = async (docType) => {
    if (!detailData) return;
    const defaultTo = detailData.guest_email || "";
    const label = docType === "reg_card" ? "Registration Card" : "Folio Receipt";
    const to = window.prompt(`Email ${label} to (comma-separated for multiple):`, defaultTo);
    if (!to || !to.trim()) return;
    try {
      const { data } = await axios.post(`${API}/bookings/${detailData.id}/email-document`,
        { document_type: docType, to: to.trim() });
      toast.success(`${label} emailed to ${(data.sent_to || []).join(", ")}`);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Failed to send email";
      toast.error(msg);
    }
  };

  // Corporate Invoice modal state + companies cache
  const [corpInvoiceOpen, setCorpInvoiceOpen] = useState(false);
  const [corpCompanies, setCorpCompanies] = useState([]);
  const [corpForm, setCorpForm] = useState({ company_id: "", amount: 0, notes: "" });

  const openCorpInvoiceModal = async () => {
    if (!detailData) return;
    try {
      const { data } = await axios.get(`${API}/city-ledger/companies?active_only=true`);
      setCorpCompanies(data || []);
      // Pre-fill amount from folio total_charges if we have it, else booking.total_price
      const prefillAmount = (folio && folio.total_charges) ? folio.total_charges :
        parseFloat(detailData.total_price || detailData.amount || 0);
      setCorpForm({
        company_id: "",
        amount: prefillAmount,
        notes: `Booking ${detailData.booking_ref || detailData.id?.slice(0, 8).toUpperCase()} — ${detailData.guest_name || ""} · ${detailData.check_in} → ${detailData.check_out}`,
      });
      setCorpInvoiceOpen(true);
    } catch { toast.error("Failed to load companies"); }
  };

  const createCorpInvoice = async () => {
    if (!corpForm.company_id) return toast.error("Select a company");
    if (!corpForm.amount || corpForm.amount <= 0) return toast.error("Amount must be positive");
    try {
      const { data } = await axios.post(`${API}/city-ledger/invoices`, {
        company_id: corpForm.company_id,
        amount: parseFloat(corpForm.amount),
        notes: corpForm.notes,
        booking_ids: [detailData.id],
        currency: detailData.currency || "GBP",
      });
      toast.success(`Invoice ${data.invoice_number} created — you can now email it from the City Ledger panel`);
      setCorpInvoiceOpen(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create invoice"); }
  };

  const changeStatus = async (bookingId, newStatus) => {
    try {
      await axios.put(`${API}/bookings/timeline/${pid}/status/${bookingId}`, { status: newStatus });
      load();
      loadTodaysActions();
      if (detailData && detailData.id === bookingId) {
        setDetailData({ ...detailData, status: newStatus });
      }
      toast.success(`Status updated to ${newStatus.replace("_", " ")}`);
    } catch { /* silent */ }
  };

  // Drag and drop
  const handleDragStart = (e, booking) => {
    setDragBooking(booking);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", booking.id);
  };

  const handleDragOver = (e, roomId) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTarget(roomId);
  };

  const handleDragLeave = () => setDropTarget(null);

  const handleDrop = async (e, targetRoomId) => {
    e.preventDefault();
    setDropTarget(null);
    if (!dragBooking || dragBooking.room_id === targetRoomId) {
      setDragBooking(null);
      return;
    }
    try {
      const { data: res } = await axios.put(`${API}/bookings/timeline/${pid}/reassign/${dragBooking.id}`, { room_id: targetRoomId });
      if (res.error) {
        toast.error(res.error === "Room conflict" ? `Conflict with ${res.conflict_guest} (${res.conflict_dates})` : res.error);
      } else {
        toast.success(`${dragBooking.guest_name} moved to ${res.new_room_name}${res.conflicts_resolved > 0 ? ` — ${res.conflicts_resolved} overbooking çakışması çözüldü ✓` : ""}`);
        load();
      }
    } catch { toast.error("Failed to reassign room"); }
    setDragBooking(null);
  };

  // One-click suggested move (overbooking resolver)
  const applySuggestedMove = async (booking, roomId, roomName) => {
    try {
      const { data: res } = await axios.put(`${API}/bookings/timeline/${pid}/reassign/${booking.id}`, { room_id: roomId });
      if (res.error) {
        toast.error(res.error === "Room conflict" ? `Çakışma: ${res.conflict_guest} (${res.conflict_dates})` : res.error);
      } else {
        toast.success(`${booking.guest_name} → ${roomName} taşındı${res.conflicts_resolved > 0 ? " — overbooking çözüldü ✓" : " ✓"}`);
        load();
      }
    } catch { toast.error("Taşıma başarısız"); }
  };

  // Bulk actions
  const toggleSelect = (bookingId) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(bookingId) ? next.delete(bookingId) : next.add(bookingId);
      return next;
    });
  };

  const selectAllArrivals = () => {
    if (todaysActions) {
      setSelectedIds(new Set(todaysActions.arrivals.map(a => a.id)));
    }
  };

  const selectAllDepartures = () => {
    if (todaysActions) {
      setSelectedIds(new Set(todaysActions.departures.map(d => d.id)));
    }
  };

  const runBulkAction = async (action) => {
    if (selectedIds.size === 0) return;
    try {
      const { data: res } = await axios.post(`${API}/bookings/timeline/${pid}/bulk-action`, {
        booking_ids: Array.from(selectedIds), action,
      });
      toast.success(`${res.updated} booking(s) updated to ${action.replace("_", " ")}`);
      if (res.errors?.length) {
        toast.error(`${res.errors.length} failed: ${res.errors[0]?.error}`);
      }
      setSelectedIds(new Set());
      setBulkMode(false);
      setShowBulkPanel(false);
      load();
      loadTodaysActions();
    } catch { toast.error("Bulk action failed"); }
  };

  const navigate = (dir) => {
    const d = new Date(startDate);
    d.setDate(d.getDate() + (dir * viewDays));
    setStartDate(d.toISOString().slice(0, 10));
  };

  const navigateJump = (numDays) => {
    const d = new Date(startDate);
    d.setDate(d.getDate() + numDays);
    setStartDate(d.toISOString().slice(0, 10));
  };

  const goToday = () => {
    const d = new Date(); d.setDate(d.getDate() - 1);
    setStartDate(d.toISOString().slice(0, 10));
  };

  const toggleGroup = (rtid) => setCollapsed(prev => ({ ...prev, [rtid]: !prev[rtid] }));

  if (loading && !data) return <div className="flex items-center justify-center py-20 text-stone-400"><RefreshCw className="w-5 h-5 animate-spin mr-2" />Loading Booking Calendar...</div>;
  if (!data) return null;

  const { date_columns, daily_occupancy, groups, total_rooms, total_bookings } = data;
  const COL_W = viewDays <= 7 ? 120 : viewDays <= 14 ? 90 : 65;
  const ROW_H = 56;
  const ROOM_LABEL_W = 180;

  // Filter bookings by search
  const matchSearch = (b) => {
    if (statusFilter !== "all" && (resolveDisplayStatus(b) !== statusFilter)) return false;
    if (sourceFilter !== "all" && (b.source || b.source_code || "") !== sourceFilter) return false;
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return b.guest_name?.toLowerCase().includes(s) || b.source?.toLowerCase().includes(s) || b.id?.toLowerCase().includes(s);
  };

  // Compute all distinct sources for the filter dropdown
  const allSources = Array.from(new Set(groups.flatMap(g => g.rooms.flatMap(r => r.bookings.map(b => b.source || b.source_code))).filter(Boolean))).sort();

  // Check for overbooking: any room-day with more than 1 active booking (not cancelled/checked_out)
  const overbookingCount = groups.reduce((acc, g) => {
    return acc + g.rooms.reduce((a, r) => {
      const active = r.bookings.filter(b => !["cancelled", "checked_out", "no_show"].includes(b.status));
      const overlap = active.filter((b1, i) => active.slice(i + 1).some(b2 => b1.check_in < b2.check_out && b2.check_in < b1.check_out)).length;
      return a + overlap;
    }, 0);
  }, 0);

  // Per-day overbooking map: date -> number of rooms with >1 active booking that night
  const overbookedDates = {};
  date_columns.forEach(col => {
    let cnt = 0;
    groups.forEach(g => g.rooms.forEach(r => {
      const active = r.bookings.filter(b => !["cancelled", "checked_out", "no_show"].includes(b.status) && b.check_in <= col.date && b.check_out > col.date);
      if (active.length > 1) cnt += 1;
    }));
    if (cnt > 0) overbookedDates[col.date] = cnt;
  });

  // Conflict pairs + auto-suggested free room (same type preferred)
  const conflictPairs = [];
  {
    const allRoomsFlat = groups.flatMap(g => g.rooms.map(r => ({ ...r, room_type_id: g.room_type_id, room_type_name: g.room_type_name })));
    const isActive = (b) => !["cancelled", "checked_out", "no_show"].includes(b.status);
    groups.forEach(g => g.rooms.forEach(r => {
      const active = r.bookings.filter(isActive);
      active.forEach((b1, i) => active.slice(i + 1).forEach(b2 => {
        if (b1.check_in < b2.check_out && b2.check_in < b1.check_out) {
          const mover = b2;
          const isFree = (rm) => rm.id !== r.id && !rm.bookings.some(b => isActive(b) && b.check_in < mover.check_out && mover.check_in < b.check_out);
          const suggestion = allRoomsFlat.find(rm => rm.room_type_id === g.room_type_id && isFree(rm)) || allRoomsFlat.find(isFree) || null;
          conflictPairs.push({ roomName: r.name, stay: b1, mover, suggestion });
        }
      }));
    }));
  }

  return (
    <div className="h-full flex flex-col" data-testid="booking-timeline">
      {/* Header */}
      <div className="bg-white border-b border-stone-200 px-5 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="timeline-title">Booking Calendar</h2>
          <button
            onClick={() => setShowPassOver(true)}
            data-testid="pass-over-duties-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold text-stone-700 bg-stone-50 border border-stone-200 rounded-lg hover:bg-stone-100 transition-all"
          >
            <Bell className="w-3.5 h-3.5" /> Pass Over Duties
          </button>
          <Badge className="bg-stone-100 text-stone-600 text-[10px]">{total_rooms} rooms</Badge>
          <Badge className="bg-blue-50 text-blue-700 text-[10px]">{total_bookings} bookings</Badge>
          {todaysActions && (
            <div className="flex items-center gap-2 ml-2">
              {todaysActions.counts.arrivals > 0 && <Badge className="bg-emerald-50 text-emerald-700 text-[10px]" data-testid="arrivals-badge"><LogIn className="w-3 h-3 mr-1" />{todaysActions.counts.arrivals} arrivals</Badge>}
              {todaysActions.counts.departures > 0 && <Badge className="bg-amber-50 text-amber-700 text-[10px]" data-testid="departures-badge"><LogOut className="w-3 h-3 mr-1" />{todaysActions.counts.departures} departures</Badge>}
              {todaysActions.counts.in_house > 0 && <Badge className="bg-blue-50 text-blue-700 text-[10px]" data-testid="inhouse-badge"><Users className="w-3 h-3 mr-1" />{todaysActions.counts.in_house} in-house</Badge>}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Date nav: Today · < > · Apr 17 - May 17 */}
          <div className="flex items-center gap-1 bg-stone-50 border border-stone-200 rounded-lg p-0.5" data-testid="date-nav">
            <button onClick={() => setStartDate(new Date().toISOString().slice(0,10))} className="px-2 py-0.5 text-[11px] font-semibold text-stone-700 hover:bg-white rounded" data-testid="date-nav-today">Today</button>
            <button onClick={() => { const d = new Date(startDate); d.setDate(d.getDate() - viewDays); setStartDate(d.toISOString().slice(0,10)); }} className="p-1 hover:bg-white rounded text-stone-500" data-testid="date-nav-prev"><ChevronLeft className="w-3.5 h-3.5" /></button>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="bg-transparent text-[11px] font-semibold text-stone-700 focus:outline-none w-24" data-testid="date-nav-picker" />
            <button onClick={() => { const d = new Date(startDate); d.setDate(d.getDate() + viewDays); setStartDate(d.toISOString().slice(0,10)); }} className="p-1 hover:bg-white rounded text-stone-500" data-testid="date-nav-next"><ChevronRight className="w-3.5 h-3.5" /></button>
            <span className="ml-1 mr-1.5 text-[10px] text-stone-400 border-l border-stone-200 pl-2">
              {new Date(startDate).toLocaleDateString("en-GB", { month: "short", day: "numeric" })} – {(() => { const d = new Date(startDate); d.setDate(d.getDate() + viewDays - 1); return d.toLocaleDateString("en-GB", { month: "short", day: "numeric", year: "numeric" }); })()}
            </span>
          </div>
          <button onClick={() => { setBulkMode(!bulkMode); setSelectedIds(new Set()); setShowBulkPanel(!showBulkPanel); }} data-testid="bulk-mode-btn"
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all ${bulkMode ? "bg-violet-500 text-white border-violet-600" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}>
            <CheckSquare className="w-3.5 h-3.5" />{bulkMode ? "Exit Bulk" : "Bulk Actions"}
          </button>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-2" />
            <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Search guest, ID..."
              className="pl-8 pr-3 py-1.5 text-xs border border-stone-200 rounded-lg w-48 focus:outline-none focus:ring-1 focus:ring-blue-300" data-testid="timeline-search" />
          </div>
          <button
            onClick={() => setShowGuestList(true)}
            data-testid="guest-list-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-stone-700 bg-white border border-stone-200 rounded-lg hover:bg-stone-50 transition-all"
          >
            <Users className="w-3.5 h-3.5" /> Guest List
          </button>
          <button
            onClick={() => {
              const firstRoom = groups[0]?.rooms[0];
              if (!firstRoom) { toast.error("No rooms available"); return; }
              const today = new Date().toISOString().slice(0, 10);
              setCreateBookingState({ room_id: firstRoom.id, room_name: firstRoom.name, room_type_id: groups[0].room_type_id, check_in: today });
              setCreateForm({ guest_name: "", guest_email: "", guest_phone: "", nights: 1, adults: 2, children: 0 });
            }}
            data-testid="timeline-new-booking-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" /> New Booking
          </button>
        </div>
      </div>

      {/* Bulk Actions Panel */}
      {bulkMode && showBulkPanel && (
        <div className="bg-violet-50 border-b border-violet-200 px-5 py-3 flex items-center justify-between flex-shrink-0" data-testid="bulk-panel">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-violet-700">{selectedIds.size} selected</span>
            {todaysActions && todaysActions.counts.arrivals > 0 && (
              <button onClick={selectAllArrivals} data-testid="select-arrivals-btn"
                className="px-2.5 py-1 text-[11px] font-medium text-emerald-700 bg-emerald-100 rounded-md hover:bg-emerald-200">
                Select all arrivals ({todaysActions.counts.arrivals})
              </button>
            )}
            {todaysActions && todaysActions.counts.departures > 0 && (
              <button onClick={selectAllDepartures} data-testid="select-departures-btn"
                className="px-2.5 py-1 text-[11px] font-medium text-amber-700 bg-amber-100 rounded-md hover:bg-amber-200">
                Select all departures ({todaysActions.counts.departures})
              </button>
            )}
            <button onClick={() => setSelectedIds(new Set())} className="px-2 py-1 text-[11px] text-stone-500 hover:text-stone-700">Clear</button>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => runBulkAction("checked_in")} disabled={selectedIds.size === 0} data-testid="bulk-checkin-btn"
              className="px-3 py-1.5 text-[11px] font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg disabled:opacity-40">
              <LogIn className="w-3 h-3 inline mr-1" />Bulk Check In
            </button>
            <button onClick={() => runBulkAction("checked_out")} disabled={selectedIds.size === 0} data-testid="bulk-checkout-btn"
              className="px-3 py-1.5 text-[11px] font-bold text-white bg-stone-600 hover:bg-stone-700 rounded-lg disabled:opacity-40">
              <LogOut className="w-3 h-3 inline mr-1" />Bulk Check Out
            </button>
            <button onClick={() => runBulkAction("confirmed")} disabled={selectedIds.size === 0} data-testid="bulk-confirm-btn"
              className="px-3 py-1.5 text-[11px] font-bold text-white bg-blue-500 hover:bg-blue-600 rounded-lg disabled:opacity-40">
              Bulk Confirm
            </button>
            <button onClick={() => runBulkAction("no_show")} disabled={selectedIds.size === 0} data-testid="bulk-noshow-btn"
              className="px-3 py-1.5 text-[11px] font-bold text-white bg-red-500 hover:bg-red-600 rounded-lg disabled:opacity-40">
              Bulk No Show
            </button>
          </div>
        </div>
      )}

      {/* Overbooking Warning Banner */}
      {overbookingCount > 0 && (
        <div className="bg-gradient-to-r from-rose-100 via-red-50 to-rose-100 border-b-2 border-rose-300 px-5 py-2 flex items-center gap-2" data-testid="overbooking-banner">
          <AlertTriangle className="w-4 h-4 text-rose-600 animate-pulse" />
          <span className="text-xs font-bold text-rose-800">OVERBOOKING ALERT</span>
          <span className="text-[11px] text-rose-700">{overbookingCount} same-room conflict{overbookingCount === 1 ? "" : "s"} detected — resolve by dragging bookings to other rooms.</span>
          {Object.keys(overbookedDates).length > 0 && (
            <span className="text-[10px] font-semibold text-rose-800 bg-rose-200/70 rounded-full px-2 py-0.5 ml-1" data-testid="overbooked-dates-chips">
              {Object.keys(overbookedDates).sort().slice(0, 6).map(d => d.slice(5)).join(" · ")}{Object.keys(overbookedDates).length > 6 ? " …" : ""}
            </span>
          )}
          <button onClick={() => setShowResolver(true)} data-testid="overbooking-resolver-btn"
            className="ml-auto flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow transition-all">
            <Wrench className="w-3 h-3" /> Çözüm önerileri
          </button>
        </div>
      )}

      {/* Filter Chip Bar */}
      <div className="bg-white border-b border-stone-200 px-5 py-2 flex items-center gap-2 flex-wrap flex-shrink-0" data-testid="filter-bar">
        <Filter className="w-3.5 h-3.5 text-stone-500" />
        <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mr-1">Filters:</span>
        {[
          { id: "all", label: "All", bg: "bg-stone-100 text-stone-700" },
          { id: "pending", label: "Pending", bg: "bg-amber-100 text-amber-800" },
          { id: "confirmed", label: "Confirmed", bg: "bg-indigo-100 text-indigo-800" },
          { id: "checked_in", label: "Checked In", bg: "bg-rose-100 text-rose-800" },
          { id: "checked_out", label: "Checked Out", bg: "bg-stone-200 text-stone-700" },
          { id: "no_show", label: "No-Show", bg: "bg-rose-600 text-white" },
          { id: "cancelled", label: "Cancelled", bg: "bg-stone-300 text-stone-800" },
        ].map(s => (
          <button key={s.id} onClick={() => setStatusFilter(s.id)} data-testid={`filter-status-${s.id}`}
            className={`px-2.5 py-0.5 text-[10px] font-bold rounded-full transition-all ${statusFilter === s.id ? `${s.bg} ring-2 ring-offset-1 ring-stone-400 shadow-sm` : "bg-white text-stone-500 border border-stone-200 hover:bg-stone-50"}`}>
            {s.label}
          </button>
        ))}
        <span className="text-stone-300 mx-1">|</span>
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} data-testid="filter-source"
          className="text-[10px] font-semibold px-2 py-0.5 border border-stone-200 rounded-full bg-white text-stone-600 focus:outline-none focus:ring-1 focus:ring-blue-300">
          <option value="all">All sources</option>
          {allSources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {(statusFilter !== "all" || sourceFilter !== "all") && (
          <button onClick={() => { setStatusFilter("all"); setSourceFilter("all"); }} className="text-[10px] text-rose-600 hover:underline ml-2" data-testid="filter-clear">Clear filters</button>
        )}
      </div>

      {/* Color legend — decode the calendar at a glance. Matches myhotelbox semantics. */}
      <div className="bg-gradient-to-r from-stone-50 to-white border-b border-stone-200 px-5 py-2.5 flex-shrink-0 overflow-x-auto" data-testid="color-legend">
        <div className="flex items-center gap-x-5 gap-y-1.5 text-[11px] whitespace-nowrap flex-wrap">
          <span className="font-semibold text-stone-500 uppercase tracking-wider text-[9px]">Legend:</span>

          {/* Vertical-strip style matching the reference */}
          <span className="flex items-center gap-1.5" data-testid="legend-pending">
            <span className="inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-yellow-300 to-amber-500"></span>
            <span className="text-stone-700">Pending</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-confirmed">
            <span className="inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-sky-400 to-blue-600"></span>
            <span className="text-stone-700">Confirmed</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-checked-in">
            <span className="inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-rose-500 to-red-700"></span>
            <span className="text-stone-700">Checked In</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-checked-out">
            <span className="inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-stone-300 to-stone-500"></span>
            <span className="text-stone-700">Checked Out</span>
          </span>

          {/* Operational states — icon-style */}
          <span className="flex items-center gap-1.5" data-testid="legend-unassigned">
            <span className="inline-flex w-4 h-4 rounded-full border-2 border-dashed border-stone-400 items-center justify-center text-stone-400 text-[8px]">?</span>
            <span className="text-stone-700">Unassigned</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-awaiting">
            <span className="inline-block w-4 h-4 rounded-full border-2 border-amber-400 bg-amber-50"></span>
            <span className="text-stone-700">Awaiting Cleaning</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-cleaning">
            <span className="inline-flex w-4 h-4 rounded-full border-2 border-sky-400 bg-sky-50 items-center justify-center">
              <span className="w-1 h-1 rounded-full bg-sky-500"></span>
            </span>
            <span className="text-stone-700">Being Cleaned</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-blocked">
            <span className="inline-block w-4 h-4 rounded bg-[repeating-linear-gradient(45deg,#78716c,#78716c_2px,#d6d3d1_2px,#d6d3d1_4px)]"></span>
            <span className="text-stone-700">Blocked</span>
          </span>

          {/* Contextual — today decorations */}
          <span className="w-px h-4 bg-stone-300" />
          <span className="flex items-center gap-1.5" data-testid="legend-arrives">
            <span className="relative inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-sky-400 to-blue-600 ring-2 ring-amber-400">
              <span className="absolute -top-1 -right-1 w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            </span>
            <span className="text-stone-700">Arrives today</span>
          </span>
          <span className="flex items-center gap-1.5" data-testid="legend-departs">
            <span className="relative inline-block w-1.5 h-5 rounded-sm bg-gradient-to-b from-rose-500 to-red-700 ring-2 ring-fuchsia-400">
              <span className="absolute -top-1 -right-1 w-1.5 h-1.5 rounded-full bg-fuchsia-400"></span>
            </span>
            <span className="text-stone-700">Departs today</span>
          </span>
        </div>
      </div>

      {/* Navigation Bar */}
      <div className="bg-stone-50 border-b border-stone-200 px-5 py-2 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-1.5">
          <button onClick={() => navigateJump(-30)} className="p-1.5 hover:bg-stone-200 rounded-lg" title="Back 30 days" data-testid="timeline-prev-month"><ChevronLeft className="w-3.5 h-3.5" /><ChevronLeft className="w-3.5 h-3.5 -ml-2" /></button>
          <button onClick={() => navigate(-1)} className="p-1.5 hover:bg-stone-200 rounded-lg" title={`Back ${viewDays} days`} data-testid="timeline-prev"><ChevronLeft className="w-4 h-4" /></button>
          <button onClick={goToday} className="px-3 py-1 text-xs font-semibold bg-white border border-stone-200 rounded-lg hover:bg-stone-100" data-testid="timeline-today">Today</button>
          <button onClick={() => navigate(1)} className="p-1.5 hover:bg-stone-200 rounded-lg" title={`Forward ${viewDays} days`} data-testid="timeline-next"><ChevronRight className="w-4 h-4" /></button>
          <button onClick={() => navigateJump(30)} className="p-1.5 hover:bg-stone-200 rounded-lg flex" title="Forward 30 days" data-testid="timeline-next-month"><ChevronRight className="w-3.5 h-3.5" /><ChevronRight className="w-3.5 h-3.5 -ml-2" /></button>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="text-xs border border-stone-200 rounded-lg px-2 py-1 ml-1" data-testid="timeline-date-pick" />
        </div>
        <div className="flex items-center gap-1 bg-white border border-stone-200 rounded-lg p-0.5">
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => setViewDays(d)} data-testid={`timeline-days-${d}`}
              className={`px-3 py-1 text-xs font-semibold rounded-md ${viewDays === d ? "bg-stone-800 text-white" : "text-stone-500 hover:bg-stone-100"}`}>{d}d</button>
          ))}
        </div>
        <div className="flex items-center gap-3 text-[10px] flex-wrap">
          {Object.entries(STATUS_COLORS).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1"><span className={`w-3 h-2 rounded-sm ${v.bar}`} />{v.label}</span>
          ))}
          <span className="text-stone-300">|</span>
          <span className="text-stone-500 font-semibold">Sources:</span>
          {[["booking","Booking"],["airbnb","Airbnb"],["expedia","Expedia"],["google","Google"],["direct","Direct"],["website","Web"]].map(([k,label]) => (
            <span key={k} className="flex items-center gap-1" data-testid={`legend-${k}`}>
              <PlatformLogo source={k} size={14} />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Timeline Grid */}
      <div className="flex-1 overflow-auto" ref={scrollRef} data-testid="timeline-grid">
        <div className="inline-block min-w-full relative">
          {/* TODAY vertical red line across the whole grid */}
          {(() => {
            const todayIdx = date_columns.findIndex(c => c.is_today);
            if (todayIdx < 0) return null;
            const left = ROOM_LABEL_W + todayIdx * COL_W + COL_W / 2;
            return (
              <div className="absolute top-0 bottom-0 w-px bg-rose-500/70 z-30 pointer-events-none" style={{ left }} data-testid="today-line">
                <div className="absolute -top-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-rose-500"></div>
              </div>
            );
          })()}
          {/* Date Header */}
          <div className="flex sticky top-0 z-20 bg-white border-b border-stone-200">
            <div className="flex-shrink-0 bg-white border-r border-stone-200 z-30 sticky left-0" style={{ width: ROOM_LABEL_W }}>
              <div className="h-12 flex items-center px-3 text-[10px] text-stone-500 uppercase font-bold">Rooms</div>
            </div>
            {date_columns.map((col, i) => {
              const occ = daily_occupancy[i];
              const obCnt = overbookedDates[col.date];
              return (
                <div key={col.date}
                  title={obCnt ? `⚠ Overbooking! ${obCnt} odada çakışan rezervasyon var (${col.date})` : undefined}
                  data-testid={obCnt ? `overbooked-day-${col.date}` : undefined}
                  className={`flex-shrink-0 border-r text-center relative ${obCnt ? "bg-rose-100 border-rose-300 border-b-2 border-b-rose-500" : `border-stone-300 ${col.is_today ? "bg-blue-50" : col.is_weekend ? "bg-stone-50" : "bg-white"}`}`}
                  style={{ width: COL_W }}>
                  <div className="h-12 flex flex-col items-center justify-center">
                    <span className={`text-[9px] uppercase ${obCnt ? "text-rose-500 font-bold" : "text-stone-400"}`}>{col.dow}</span>
                    <span className={`text-sm ${obCnt ? "text-rose-700 font-black" : col.is_today ? "text-red-600 font-black" : "font-bold text-stone-700"}`}>{col.day}/{col.month}</span>
                    {obCnt ? (
                      <span className="flex items-center gap-0.5 text-[9px] font-bold text-rose-600">
                        <AlertTriangle className="w-2.5 h-2.5 animate-pulse" />{obCnt} çakışma
                      </span>
                    ) : (
                      <span className={`text-[9px] ${getOccColor(occ?.occupancy_pct || 0)}`}>{occ?.occupancy_pct || 0}%</span>
                    )}
                  </div>
                  {obCnt > 0 && <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />}
                </div>
              );
            })}
          </div>

          {/* Unassigned Row — shows bookings without a room assignment, per day */}
          {(() => {
            const allBookings = groups.flatMap(g => g.rooms.flatMap(r => r.bookings));
            const unassignedByDate = date_columns.map(col => {
              const count = allBookings.filter(b => (b.status === "pending" || b.status === "unassigned" || !b.room_id) && b.check_in <= col.date && b.check_out > col.date).length;
              return count;
            });
            const totalUnassigned = unassignedByDate.reduce((a, b) => a + b, 0);
            return (
              <div className="flex border-b border-amber-200 bg-amber-50/40" style={{ height: 32 }} data-testid="unassigned-row">
                <div className="flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 z-10 bg-amber-50/60 border-r border-stone-200" style={{ width: ROOM_LABEL_W }}>
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  <span className="text-[11px] text-amber-800 font-semibold">Unassigned</span>
                  {totalUnassigned > 0 && <Badge className="bg-amber-600 text-white text-[9px] ml-auto">{totalUnassigned}</Badge>}
                </div>
                {date_columns.map((col, i) => {
                  const c = unassignedByDate[i];
                  return (
                    <div key={col.date} className={`flex-shrink-0 border-r border-amber-100 flex items-center justify-center ${col.is_today ? "bg-blue-50/50" : ""}`} style={{ width: COL_W, height: 32 }}>
                      <div className={`flex items-center gap-0.5 text-[10px] font-semibold ${c > 0 ? "text-amber-700" : "text-amber-400/50"}`}>
                        <AlertTriangle className="w-2.5 h-2.5" />{c}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {/* Room Type Groups */}
          {(() => {
            const activeProp = (properties || []).find(p => p.id === pid);
            const propLabel = activeProp ? activeProp.name : "All Properties";
            return (
              <div className="flex bg-gradient-to-r from-indigo-50 via-white to-indigo-50 border-b-2 border-indigo-200" data-testid="property-group-header">
                <div className="flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 z-20 border-r border-stone-200 bg-gradient-to-r from-indigo-50 to-white" style={{ width: ROOM_LABEL_W, height: 28 }}>
                  <Building2 className="w-3.5 h-3.5 text-indigo-600" />
                  <span className="text-[11px] font-black tracking-wider uppercase text-stone-700">{propLabel}</span>
                </div>
                {date_columns.map(col => (
                  <div key={col.date} className={`flex-shrink-0 border-r border-indigo-100 ${col.is_today ? "bg-blue-50/50" : ""}`} style={{ width: COL_W, height: 28 }} />
                ))}
              </div>
            );
          })()}
          {groups.map(group => {
            const isCollapsed = collapsed[group.room_type_id];
            const groupBookingCount = group.rooms.reduce((s, r) => s + r.bookings.length, 0);

            return (
              <div key={group.room_type_id} data-testid={`timeline-group-${group.room_type_id}`}>
                {/* Group Header */}
                <div className="flex sticky left-0 z-10 bg-stone-100 border-b border-stone-200 cursor-pointer hover:bg-stone-200/80" onClick={() => toggleGroup(group.room_type_id)}>
                  <div className="flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 bg-stone-100 z-20 border-r border-stone-200" style={{ width: ROOM_LABEL_W, height: ROW_H }}>
                    {isCollapsed ? <ChevronRight className="w-3.5 h-3.5 text-stone-400" /> : <ChevronDown className="w-3.5 h-3.5 text-stone-400" />}
                    <Bed className="w-3.5 h-3.5 text-stone-500" />
                    <span className="text-xs font-bold text-stone-700 truncate">{group.room_type_name}</span>
                    <Badge className="bg-white text-stone-500 text-[9px] border border-stone-200">{group.total_rooms}</Badge>
                  </div>
                  {date_columns.map(col => {
                    const dayBookings = group.rooms.reduce((s, r) => s + r.bookings.filter(b => b.check_in <= col.date && b.check_out > col.date).length, 0);
                    const avail = group.total_rooms - dayBookings;
                    return (
                      <div key={col.date} className={`flex-shrink-0 border-r border-stone-300 flex flex-col items-center justify-center ${col.is_today ? "bg-blue-50/50" : ""}`} style={{ width: COL_W, height: ROW_H }}>
                        <span className="text-[10px] font-bold text-stone-600">{avail}/{group.total_rooms}</span>
                        <span className="text-[9px] text-stone-400">{cur(group.rate)}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Room Rows */}
                {!isCollapsed && group.rooms.map((room, rowIdx) => (
                  <div key={room.id} className={`flex border-b border-stone-300 relative transition-all group ${rowIdx % 2 === 1 ? "bg-stone-50/50" : "bg-white"} ${dropTarget === room.id ? "bg-violet-100 ring-2 ring-violet-400 ring-inset" : ""}`}
                    style={{ height: ROW_H }} data-testid={`timeline-room-${room.id}`}
                    onDragOver={(e) => handleDragOver(e, room.id)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, room.id)}>
                    {/* Room Label */}
                    <div className={`flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 z-10 border-r border-stone-300 ${rowIdx % 2 === 1 ? "bg-stone-50/70" : "bg-white"}`} style={{ width: ROOM_LABEL_W }}>
                      <span className={`w-2 h-2 rounded-full ${HK_COLORS[room.housekeeping] || "bg-stone-300"}`} title={room.housekeeping} />
                      <span className="text-[11px] text-stone-600 truncate flex-1">{room.name}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); setOosForm({ room_id: room.id, room_name: room.name, property_id: group.property_id, start: new Date().toISOString().slice(0,10), end: "", reason: "" }); }}
                        data-testid={`room-oos-btn-${room.id}`}
                        title="Block room (out of service)"
                        className="p-0.5 text-stone-300 hover:text-amber-600 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <Wrench className="w-3 h-3" />
                      </button>
                      {dropTarget === room.id && dragBooking && <span className="text-[9px] text-violet-500 font-bold ml-auto">Drop here</span>}
                    </div>

                    {/* Date cells */}
                    <div className="relative flex" style={{ height: ROW_H }}>
                      {date_columns.map(col => {
                        // Is this cell already occupied?
                        const occupied = room.bookings.some(b => b.check_in <= col.date && b.check_out > col.date);
                        return (
                          <div
                            key={col.date}
                            className={`flex-shrink-0 border-r border-stone-300 transition-colors ${col.is_today ? "bg-blue-50/40" : col.is_weekend ? "bg-stone-100/50" : ""} ${occupied ? "" : "hover:bg-emerald-50/80 cursor-cell"}`}
                            style={{ width: COL_W, height: ROW_H }}
                            onClick={() => {
                              if (occupied || bulkMode) return;
                              setCreateBookingState({
                                room_id: room.id,
                                room_name: room.name,
                                room_type_id: group.room_type_id,
                                check_in: col.date,
                              });
                              setCreateForm({ guest_name: "", guest_email: "", guest_phone: "", nights: 1, adults: 2, children: 0 });
                            }}
                            data-testid={`cell-${room.id}-${col.date}`}
                            title={occupied ? "" : "Click to create booking"}
                          />
                        );
                      })}

                      {/* Out-of-Service / Maintenance blocks — grey striped bars */}
                      {oosBlocks.filter(b => b.room_id === room.id).map(block => {
                        const startIdx = date_columns.findIndex(c => c.date >= block.start);
                        const endIdx = date_columns.findIndex(c => c.date >= block.end);
                        if (startIdx < 0 && endIdx < 0) return null;
                        const si = startIdx >= 0 ? startIdx : 0;
                        const ei = endIdx >= 0 ? endIdx : date_columns.length;
                        if (ei <= 0 || si >= date_columns.length) return null;
                        const left = si * COL_W + 2;
                        const width = Math.max((ei - si) * COL_W - 4, COL_W * 0.5);
                        const isIcal = !!block.ical_source_id || block.created_by === "ical_sync";
                        if (isIcal) {
                          const channel = (block.reason || "").replace(/^iCal:\s*/, "").split(" — ")[0] || "iCal";
                          const isAirbnb = channel.toLowerCase().includes("airbnb");
                          return (
                            <div
                              key={block.id}
                              className="absolute top-1 bottom-1 rounded-md shadow cursor-default overflow-hidden"
                              style={{
                                left, width,
                                backgroundImage: "repeating-linear-gradient(45deg, #FF385C 0, #FF385C 6px, #e5254c 6px, #e5254c 12px)",
                              }}
                              title={`iCal SENKRON · ${block.reason} · ${block.start} → ${block.end} (senkronla yönetilir, elle silinemez)`}
                              data-testid={`ical-block-${block.id}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                toast.info(`Bu blok "${channel}" iCal senkronundan geliyor — iCal Senkronu panelinden yönetilir`);
                              }}
                            >
                              <div className="absolute inset-0 bg-black/15 flex items-center gap-1 px-1.5">
                                {isAirbnb ? (
                                  <svg viewBox="0 0 448 512" className="w-3 h-3 flex-shrink-0" fill="white" aria-label="Airbnb">
                                    <path d="M224 373.12c-25.24-31.67-40.08-59.43-45-83.18-22.55-88 112.61-88 90.06 0-5.45 24.25-20.29 52-45.06 83.18zm138.15 73.23c-42.06 18.31-83.67-10.88-119.3-50.47 103.9-130.07 46.11-200-18.85-200-54.92 0-85.16 46.51-73.28 100.5 6.93 29.19 25.23 62.39 54.43 99.5-32.53 36.05-60.55 52.69-85.15 54.92-50 7.43-89.11-41.06-71.3-91.09 15.1-39.16 111.72-231.18 115.87-241.56 15.75-30.07 25.56-57.4 59.38-57.4 32.34 0 43.4 25.94 60.37 59.87 36 70.62 89.35 177.48 114.84 239.09 13.17 33.07-1.37 71.29-37.01 86.64z" />
                                  </svg>
                                ) : (
                                  <CalendarDays className="w-3 h-3 text-white flex-shrink-0" />
                                )}
                                <span className="text-[10px] text-white font-bold uppercase tracking-wider truncate">{channel}</span>
                              </div>
                            </div>
                          );
                        }
                        return (
                          <div
                            key={block.id}
                            className="absolute top-1 bottom-1 rounded-md shadow cursor-pointer group overflow-hidden"
                            style={{
                              left, width,
                              backgroundImage: "repeating-linear-gradient(45deg, #9ca3af 0, #9ca3af 6px, #d1d5db 6px, #d1d5db 12px)",
                            }}
                            title={`OUT OF SERVICE · ${block.reason} · ${block.start} → ${block.end}`}
                            data-testid={`oos-block-${block.id}`}
                            onClick={async (e) => {
                              e.stopPropagation();
                              if (window.confirm(`Remove OOS block "${block.reason}"?`)) {
                                try { await axios.delete(`${API}/rooms/oos-blocks/${block.id}`); toast.success("Block removed"); loadOosBlocks(); }
                                catch { toast.error("Failed"); }
                              }
                            }}
                          >
                            <div className="absolute inset-0 bg-black/20 flex items-center gap-1 px-2">
                              <Wrench className="w-3 h-3 text-white flex-shrink-0" />
                              <span className="text-[10px] text-white font-bold uppercase tracking-wider truncate">{block.reason}</span>
                            </div>
                          </div>
                        );
                      })}
                      {/* Booking Bars (smart collision detector: lanes + overflow pills) */}
                      {(() => {
                        const visibleBookings = room.bookings.filter(matchSearch);
                        if (visibleBookings.length === 0) return null;
                        const { laneOf, totalLanes } = assignLanes(visibleBookings);
                        const visibleLanes = Math.min(Math.max(totalLanes, 1), MAX_VISIBLE_LANES);
                        const innerH = ROW_H - 8;
                        const laneH = innerH / visibleLanes;
                        const overflowClusters = buildOverflowClusters(visibleBookings, laneOf);
                        const todayISO = new Date().toISOString().slice(0, 10);

                        const bars = visibleBookings.map(bk => {
                          const laneIdx = laneOf[bk.id];
                          if (laneIdx >= MAX_VISIBLE_LANES) return null;
                          const startIdx = date_columns.findIndex(c => c.date >= bk.check_in);
                          const endIdx = date_columns.findIndex(c => c.date >= bk.check_out);
                          const si = startIdx >= 0 ? startIdx : 0;
                          const ei = endIdx >= 0 ? endIdx : date_columns.length;
                          const left = si * COL_W;
                          const width = Math.max((ei - si) * COL_W - 4, COL_W * 0.5);
                          const sc = STATUS_COLORS[resolveDisplayStatus(bk)] || STATUS_COLORS.confirmed;
                          const ctx = computeContext(bk, todayISO);
                          const ctxMeta = ctx ? STATUS_COLORS[ctx] : null;
                          const isSelected = selectedIds.has(bk.id);
                          const top = 4 + laneIdx * laneH;
                          const height = laneH - 2;
                          const isCompact = height < 30;
                          const src = bk.source || bk.source_code || "";

                          return (
                            <div key={bk.id} className="absolute" style={{ left: left + 2, width, top, height }}>
                              {bulkMode && (
                                <button onClick={(e) => { e.stopPropagation(); toggleSelect(bk.id); }} data-testid={`select-${bk.id}`}
                                  className="absolute -left-0.5 top-0.5 z-10 w-4 h-4 flex items-center justify-center">
                                  {isSelected ? <CheckSquare className="w-3.5 h-3.5 text-violet-600" /> : <Square className="w-3.5 h-3.5 text-stone-400" />}
                                </button>
                              )}
                              <button
                                draggable={!bulkMode}
                                onDragStart={(e) => handleDragStart(e, { ...bk, room_id: room.id })}
                                onClick={(e) => {
                                  if (bulkMode) { toggleSelect(bk.id); return; }
                                  e.stopPropagation();
                                  const rect = e.currentTarget.getBoundingClientRect();
                                  setQuickActions({ booking: bk, rect, roomName: room.name });
                                }}
                                data-testid={`booking-bar-${bk.id}`}
                                data-status={bk.status}
                                data-context={ctx || ""}
                                data-lane={laneIdx}
                                className={`relative w-full h-full rounded-md ${sc.bar} ${sc.text} ${sc.border} border shadow-md ${sc.shadow || ""} cursor-pointer hover:brightness-110 hover:shadow-lg transition-all overflow-hidden flex ${isCompact ? "flex-row items-center gap-1.5 px-1.5" : "flex-col justify-center pl-2 pr-1.5"} ${ctxMeta ? ctxMeta.accent : ""} ${isSelected ? "ring-2 ring-violet-500 ring-offset-1" : ""} ${dragBooking?.id === bk.id ? "opacity-50" : ""}`}
                                title={`${bk.guest_name} | ${src} | ${cur(bk.total_price)} | ${bk.check_in} → ${bk.check_out} | ${sc.label}${ctxMeta ? " · " + ctxMeta.label : ""}`}>
                                {/* Left-edge channel colour strip */}
                                <span className={`absolute left-0 top-0 bottom-0 w-1 ${getSourceStrip(src)}`} aria-hidden></span>
                                {/* Inner highlight */}
                                {!["blocked","unassigned","awaiting_cleaning","being_cleaned"].includes(resolveDisplayStatus(bk)) && (
                                  <span className="absolute inset-x-0 top-0 h-[2px] bg-white/40 rounded-t-md" aria-hidden></span>
                                )}
                                {/* Contextual pulsing dot */}
                                {ctxMeta && (
                                  <span className="absolute top-0.5 right-0.5 flex h-2 w-2" data-testid={`ctx-dot-${bk.id}`}>
                                    <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${ctxMeta.dotCls}`}></span>
                                    <span className={`relative inline-flex rounded-full h-2 w-2 ${ctxMeta.dotCls}`}></span>
                                  </span>
                                )}
                                {/* Payment status badge — bottom-left corner */}
                                {width > 60 && (
                                  <span className={`absolute bottom-0.5 left-1.5 w-1.5 h-1.5 rounded-full ring-1 ring-white ${bk.payment_status === "paid" ? "bg-emerald-500" : bk.payment_status === "partial" ? "bg-amber-500" : "bg-rose-500"}`}
                                    data-testid={`pay-dot-${bk.id}`} title={`Payment: ${bk.payment_status || "unpaid"}`}></span>
                                )}
                                {/* Notes indicator — if booking has notes, show sticky-note icon top-right */}
                                {bk.notes && width > 80 && (
                                  <StickyNote className="absolute top-0.5 right-3.5 w-2.5 h-2.5 text-white/90 drop-shadow" data-testid={`note-icon-${bk.id}`} />
                                )}
                                {isCompact ? (
                                  // Compact (2-lane) layout: single row with logo + name + source + price chip
                                  <>
                                    <span className="ml-1 flex-shrink-0" data-testid={`platform-badge-${bk.id}`}><PlatformLogo source={src} size={12} /></span>
                                    <span className="text-[10px] font-bold truncate flex-1 relative z-10" data-testid={`guest-name-${bk.id}`}>{bk.guest_name}</span>
                                    {width > 90 && (() => {
                                      const bal = (bk.balance_due !== undefined && bk.balance_due !== null) ? Number(bk.balance_due) : Number(bk.total_price || 0);
                                      const paid = bal <= 0;
                                      const today = new Date().toISOString().slice(0, 10);
                                      const isUrgent = !paid && (bk.status === "checked_in" || bk.status === "checked_out" || bk.check_in === today);
                                      return (
                                        <span
                                          role="button"
                                          onClick={(e) => { e.stopPropagation(); if (!paid) setQuickPay({ booking: bk }); }}
                                          className={`text-[9px] font-mono flex-shrink-0 opacity-90 rounded-sm px-1 ${
                                            paid ? "bg-emerald-500/30 text-emerald-50"
                                                 : isUrgent ? "balance-flash"
                                                            : "bg-rose-100 text-rose-700 cursor-pointer"
                                          }`}
                                          data-testid={`price-${bk.id}`}
                                          title={paid ? `Paid in full (${cur(bk.total_price)})`
                                                      : isUrgent ? `Balance due ${cur(bal)} — click to take payment`
                                                                 : `Balance due ${cur(bal)} · future booking`}
                                        >
                                          {paid ? "PAID" : cur(bal)}
                                        </span>
                                      );
                                    })()}
                                  </>
                                ) : (
                                  <>
                                    {/* Line 1: guest name — big */}
                                    <div className="flex items-center gap-1 min-w-0 relative z-10">
                                      <span className="text-[11px] font-bold truncate flex-1" data-testid={`guest-name-${bk.id}`}>{bk.guest_name}</span>
                                    </div>
                                    {/* Line 2: #ID · source logo · balance · nights */}
                                    <div className="flex items-center gap-1 mt-0.5 min-w-0 relative z-10">
                                      {width > 80 && bk.booking_ref && (
                                        <span className="text-[9px] font-mono opacity-70 truncate" data-testid={`ref-${bk.id}`}>#{String(bk.booking_ref).slice(-5)}</span>
                                      )}
                                      <span className="inline-flex items-center" data-testid={`platform-badge-${bk.id}`} title={src}>
                                        <PlatformLogo source={src} size={12} />
                                      </span>
                                      {(() => {
                                        const bal = (bk.balance_due !== undefined && bk.balance_due !== null) ? Number(bk.balance_due) : Number(bk.total_price || 0);
                                        const paid = bal <= 0;
                                        const today = new Date().toISOString().slice(0, 10);
                                        const isUrgent = !paid && (bk.status === "checked_in" || bk.status === "checked_out" || bk.check_in === today);
                                        return (
                                          <span
                                            role="button"
                                            onClick={(e) => { e.stopPropagation(); if (!paid) setQuickPay({ booking: bk }); }}
                                            className={`text-[9px] font-bold font-mono rounded-sm px-1 leading-tight flex-shrink-0 ${
                                              paid ? "bg-emerald-100 text-emerald-700"
                                                   : isUrgent ? "balance-flash"
                                                              : "bg-rose-100 text-rose-700 cursor-pointer"
                                            }`}
                                            data-testid={`price-${bk.id}`}
                                            title={paid ? `Paid in full (${cur(bk.total_price)})`
                                                        : isUrgent ? `Balance due ${cur(bal)} — click to take payment`
                                                                   : `Balance due ${cur(bal)} · future booking`}
                                          >
                                            {paid ? "PAID" : cur(bal)}
                                          </span>
                                        );
                                      })()}
                                      {width > 140 && <span className="text-[9px] opacity-80 flex-shrink-0 ml-auto">{bk.nights}n</span>}
                                    </div>
                                  </>
                                )}
                              </button>
                            </div>
                          );
                        });

                        // Overflow pills for hidden lanes ("+N more")
                        const pills = overflowClusters.map((cluster, ci) => {
                          const startIdx = date_columns.findIndex(c => c.date >= cluster.check_in);
                          const endIdx = date_columns.findIndex(c => c.date >= cluster.check_out);
                          const si = startIdx >= 0 ? startIdx : 0;
                          const ei = endIdx >= 0 ? endIdx : date_columns.length;
                          const left = si * COL_W + 4;
                          const width = Math.max((ei - si) * COL_W - 8, COL_W * 0.5);
                          return (
                            <button
                              key={`cluster-${ci}`}
                              onClick={(e) => { e.stopPropagation(); setCollisionCluster({ room, cluster }); }}
                              data-testid={`collision-pill-${room.id}-${ci}`}
                              title={`${cluster.items.length} more overlapping booking${cluster.items.length === 1 ? "" : "s"} in ${room.name}: ${cluster.items.map(b => b.guest_name).join(", ")}`}
                              className="absolute bottom-0.5 z-20 bg-gradient-to-br from-rose-600 via-red-600 to-rose-700 text-white text-[10px] font-bold rounded-full px-2 py-0.5 shadow-lg shadow-rose-400/40 ring-2 ring-white hover:from-rose-700 hover:to-rose-800 transition-all flex items-center gap-1 hover:scale-105"
                              style={{ left, maxWidth: width }}
                            >
                              <AlertTriangle className="w-2.5 h-2.5" />
                              <span className="truncate">+{cluster.items.length} more</span>
                            </button>
                          );
                        });

                        return <>{bars}{pills}</>;
                      })()}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      {/* Pass Over Duties Modal — shift handover report */}
      {showPassOver && (() => {
        const todayISO = new Date().toISOString().slice(0, 10);
        const allBookings = groups.flatMap(g => g.rooms.flatMap(r => r.bookings.map(b => ({...b, room_name: r.name}))));
        const arrivalsToday = allBookings.filter(b => b.check_in === todayISO);
        const departuresToday = allBookings.filter(b => b.check_out === todayISO);
        const inHouse = allBookings.filter(b => b.check_in < todayISO && b.check_out > todayISO && b.status === "checked_in");
        const pending = allBookings.filter(b => b.status === "pending");
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowPassOver(false)} data-testid="pass-over-modal">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="bg-gradient-to-br from-indigo-600 to-violet-800 px-5 py-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center">
                  <Bell className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-white text-base">Pass Over Duties</h3>
                  <p className="text-[11px] text-indigo-100">Shift handover report · {new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</p>
                </div>
                <button onClick={() => setShowPassOver(false)} className="p-1 hover:bg-white/20 rounded-lg"><X className="w-4 h-4 text-white" /></button>
              </div>
              <div className="p-5 space-y-4 max-h-[70vh] overflow-auto">
                {/* KPI row */}
                <div className="grid grid-cols-4 gap-2">
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-center">
                    <div className="text-2xl font-black text-emerald-700">{arrivalsToday.length}</div>
                    <div className="text-[10px] text-emerald-800 uppercase tracking-wider font-semibold">Arrivals</div>
                  </div>
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center">
                    <div className="text-2xl font-black text-amber-700">{departuresToday.length}</div>
                    <div className="text-[10px] text-amber-800 uppercase tracking-wider font-semibold">Departures</div>
                  </div>
                  <div className="bg-sky-50 border border-sky-200 rounded-lg p-3 text-center">
                    <div className="text-2xl font-black text-sky-700">{inHouse.length}</div>
                    <div className="text-[10px] text-sky-800 uppercase tracking-wider font-semibold">In-House</div>
                  </div>
                  <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-center">
                    <div className="text-2xl font-black text-rose-700">{pending.length}</div>
                    <div className="text-[10px] text-rose-800 uppercase tracking-wider font-semibold">Pending</div>
                  </div>
                </div>
                {/* Checklists */}
                {arrivalsToday.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-700 mb-2 flex items-center gap-1.5"><LogIn className="w-3.5 h-3.5" /> Expected arrivals ({arrivalsToday.length})</h4>
                    <ul className="space-y-1 text-[11px]">
                      {arrivalsToday.map(b => <li key={b.id} className="flex items-center gap-2 bg-emerald-50/50 p-1.5 rounded">
                        <input type="checkbox" className="accent-emerald-600" />
                        <span className="font-semibold">{b.guest_name}</span>
                        <span className="text-stone-500">· {b.room_name}</span>
                        <span className="text-stone-400 ml-auto">{cur(b.total_price)}</span>
                      </li>)}
                    </ul>
                  </div>
                )}
                {departuresToday.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-amber-700 mb-2 flex items-center gap-1.5"><LogOut className="w-3.5 h-3.5" /> Expected departures ({departuresToday.length})</h4>
                    <ul className="space-y-1 text-[11px]">
                      {departuresToday.map(b => <li key={b.id} className="flex items-center gap-2 bg-amber-50/50 p-1.5 rounded">
                        <input type="checkbox" className="accent-amber-600" />
                        <span className="font-semibold">{b.guest_name}</span>
                        <span className="text-stone-500">· {b.room_name}</span>
                      </li>)}
                    </ul>
                  </div>
                )}
                <div className="bg-stone-50 border border-stone-200 rounded-lg p-3">
                  <h4 className="text-xs font-bold text-stone-700 mb-1">Notes for next shift</h4>
                  <textarea placeholder="Hand over notes, issues, guest requests..." className="w-full text-xs p-2 border border-stone-200 rounded min-h-[80px] focus:outline-none focus:ring-1 focus:ring-indigo-300" data-testid="pass-over-notes" />
                </div>
              </div>
              <div className="px-5 py-3 bg-stone-50 border-t border-stone-100 flex items-center justify-end gap-2">
                <button onClick={() => setShowPassOver(false)} className="px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900">Close</button>
                <button onClick={() => { toast.success("Handover report saved"); setShowPassOver(false); }} className="px-4 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow" data-testid="pass-over-save">Save &amp; Send</button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Guest List Modal */}
      {showGuestList && (() => {
        const allBookings = groups.flatMap(g => g.rooms.flatMap(r => r.bookings.map(b => ({...b, room_name: r.name}))));
        const filtered = searchTerm
          ? allBookings.filter(b => (b.guest_name || "").toLowerCase().includes(searchTerm.toLowerCase()) || (b.guest_email || "").toLowerCase().includes(searchTerm.toLowerCase()))
          : allBookings;
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowGuestList(false)} data-testid="guest-list-modal">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="bg-gradient-to-br from-stone-700 to-stone-900 px-5 py-4 flex items-center gap-3 flex-shrink-0">
                <Users className="w-5 h-5 text-white" />
                <h3 className="font-bold text-white text-base flex-1">Guest List</h3>
                <Badge className="bg-white/20 text-white text-[10px]">{filtered.length} guests</Badge>
                <button onClick={() => setShowGuestList(false)} className="p-1 hover:bg-white/20 rounded-lg"><X className="w-4 h-4 text-white" /></button>
              </div>
              <div className="flex-1 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-stone-50 sticky top-0 border-b border-stone-200">
                    <tr>
                      <th className="text-left px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Guest</th>
                      <th className="text-left px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Email</th>
                      <th className="text-left px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Room</th>
                      <th className="text-left px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Dates</th>
                      <th className="text-left px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Status</th>
                      <th className="text-right px-3 py-2 font-semibold text-stone-600 uppercase tracking-wider text-[9px]">Price</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {filtered.map(b => {
                      const sc = STATUS_COLORS[resolveDisplayStatus(b)] || STATUS_COLORS.confirmed;
                      return (
                        <tr key={b.id} className="hover:bg-stone-50 cursor-pointer" onClick={() => { setShowGuestList(false); openDetail(b.id); }} data-testid={`guest-row-${b.id}`}>
                          <td className="px-3 py-2 font-semibold">{b.guest_name}</td>
                          <td className="px-3 py-2 text-stone-500">{b.guest_email || "—"}</td>
                          <td className="px-3 py-2 text-stone-600">{b.room_name}</td>
                          <td className="px-3 py-2 text-stone-500 font-mono">{b.check_in} → {b.check_out}</td>
                          <td className="px-3 py-2"><Badge className={`text-[9px] ${sc.bar} ${sc.text} border-0`}>{sc.label}</Badge></td>
                          <td className="px-3 py-2 text-right font-mono font-bold text-stone-700">{cur(b.total_price)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Out-of-Service Block Modal */}
      {oosForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setOosForm(null)} data-testid="oos-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="bg-gradient-to-br from-stone-600 to-stone-900 px-5 py-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center">
                <Wrench className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-white text-base">Block Room (Out of Service)</h3>
                <p className="text-[11px] text-stone-200">{oosForm.room_name} will be unavailable for the selected range</p>
              </div>
              <button onClick={() => setOosForm(null)} className="p-1 hover:bg-white/20 rounded-lg"><X className="w-4 h-4 text-white" /></button>
            </div>
            <div className="p-5 space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Start *</label>
                  <input type="date" value={oosForm.start} onChange={e => setOosForm({...oosForm, start: e.target.value})} className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400" data-testid="oos-start" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">End (exclusive) *</label>
                  <input type="date" value={oosForm.end} onChange={e => setOosForm({...oosForm, end: e.target.value})} className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400" data-testid="oos-end" />
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Reason *</label>
                <select value={oosForm.reason} onChange={e => setOosForm({...oosForm, reason: e.target.value})} className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-stone-400" data-testid="oos-reason">
                  <option value="">Select reason...</option>
                  <option value="Painting">Painting</option>
                  <option value="Deep Clean">Deep Clean</option>
                  <option value="Maintenance">Maintenance</option>
                  <option value="Plumbing">Plumbing</option>
                  <option value="Refurbishment">Refurbishment</option>
                  <option value="Inspection">Inspection</option>
                  <option value="Pest Control">Pest Control</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>
            <div className="px-5 py-3 bg-stone-50 border-t border-stone-100 flex items-center justify-end gap-2">
              <button onClick={() => setOosForm(null)} className="px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900">Cancel</button>
              <button
                onClick={async () => {
                  if (!oosForm.start || !oosForm.end || !oosForm.reason) { toast.error("All fields required"); return; }
                  try {
                    await axios.post(`${API}/rooms/oos-blocks`, { room_id: oosForm.room_id, property_id: oosForm.property_id, start: oosForm.start, end: oosForm.end, reason: oosForm.reason });
                    toast.success(`${oosForm.room_name} blocked: ${oosForm.reason}`);
                    setOosForm(null);
                    loadOosBlocks();
                  } catch (err) {
                    toast.error(err?.response?.data?.detail || "Failed to block room");
                  }
                }}
                data-testid="oos-submit"
                className="px-4 py-1.5 text-xs font-bold text-white bg-stone-800 hover:bg-stone-900 rounded-lg shadow"
              >Block Room</button>
            </div>
          </div>
        </div>
      )}

      {/* Create Booking Modal */}
      {createBooking && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => !creating && setCreateBookingState(null)} data-testid="create-booking-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="bg-gradient-to-br from-emerald-600 to-teal-700 px-5 py-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center">
                <Plus className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-white text-base">New Booking</h3>
                <p className="text-[11px] text-emerald-100">{createBooking.room_name} · from {createBooking.check_in}</p>
              </div>
              <button onClick={() => setCreateBookingState(null)} className="p-1 hover:bg-white/20 rounded-lg" data-testid="create-booking-close"><X className="w-4 h-4 text-white" /></button>
            </div>
            <div className="p-5 space-y-3">
              <div>
                <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Guest Name *</label>
                <input value={createForm.guest_name} onChange={e => setCreateForm({...createForm, guest_name: e.target.value})} placeholder="John Doe"
                  className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-guest-name" autoFocus />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Email *</label>
                  <input type="email" value={createForm.guest_email} onChange={e => setCreateForm({...createForm, guest_email: e.target.value})} placeholder="guest@example.com"
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-guest-email" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Phone</label>
                  <input value={createForm.guest_phone} onChange={e => setCreateForm({...createForm, guest_phone: e.target.value})} placeholder="+44 7..."
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-guest-phone" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Nights *</label>
                  <input type="number" min="1" max="365" value={createForm.nights} onChange={e => setCreateForm({...createForm, nights: parseInt(e.target.value) || 1})}
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-nights" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Adults</label>
                  <input type="number" min="1" max="20" value={createForm.adults} onChange={e => setCreateForm({...createForm, adults: parseInt(e.target.value) || 1})}
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-adults" />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider font-bold text-stone-500 mb-1 block">Children</label>
                  <input type="number" min="0" max="20" value={createForm.children} onChange={e => setCreateForm({...createForm, children: parseInt(e.target.value) || 0})}
                    className="w-full px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="cb-children" />
                </div>
              </div>
              <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-[11px] text-stone-600 flex items-center justify-between">
                <span>Check-in: <b>{createBooking.check_in}</b></span>
                <span>Check-out: <b>{(() => {
                  const d = new Date(createBooking.check_in); d.setDate(d.getDate() + createForm.nights);
                  return d.toISOString().slice(0, 10);
                })()}</b></span>
              </div>
            </div>
            <div className="px-5 py-3 bg-stone-50 border-t border-stone-100 flex items-center justify-end gap-2">
              <button onClick={() => setCreateBookingState(null)} disabled={creating} className="px-3 py-1.5 text-xs font-semibold text-stone-600 hover:text-stone-900" data-testid="cb-cancel">Cancel</button>
              <button
                onClick={async () => {
                  if (!createForm.guest_name.trim() || !createForm.guest_email.trim()) {
                    toast.error("Guest name and email are required");
                    return;
                  }
                  setCreating(true);
                  try {
                    const co = new Date(createBooking.check_in);
                    co.setDate(co.getDate() + createForm.nights);
                    await axios.post(`${API}/booking/reserve`, {
                      property_id: pid,
                      room_type_id: createBooking.room_type_id,
                      guest_name: createForm.guest_name.trim(),
                      guest_email: createForm.guest_email.trim(),
                      guest_phone: createForm.guest_phone.trim(),
                      check_in: createBooking.check_in,
                      check_out: co.toISOString().slice(0, 10),
                      adults: createForm.adults,
                      children: createForm.children,
                      rooms: 1,
                    });
                    toast.success(`Booking created for ${createForm.guest_name}`);
                    setCreateBookingState(null);
                    load();
                  } catch (err) {
                    toast.error(err?.response?.data?.detail || "Failed to create booking");
                  }
                  setCreating(false);
                }}
                disabled={creating}
                data-testid="cb-submit"
                className="px-4 py-1.5 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Booking"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quick-Action Popover — myhotelbox-style click-popover on booking bars */}
      {quickActions && (() => {
        const { booking: bk, rect, roomName } = quickActions;
        const sc = STATUS_COLORS[resolveDisplayStatus(bk)] || STATUS_COLORS.confirmed;
        // Position below bar, center-aligned, clamped to viewport
        const popoverW = 320, popoverH = 370;
        let left = rect.left + rect.width / 2 - popoverW / 2;
        let top = rect.bottom + 8;
        if (left < 8) left = 8;
        if (left + popoverW > window.innerWidth - 8) left = window.innerWidth - popoverW - 8;
        if (top + popoverH > window.innerHeight - 8) top = rect.top - popoverH - 8;
        const actions = [
          { id: "checkin",   label: "Check In",  icon: LogIn,      color: "text-emerald-600 bg-emerald-50 hover:bg-emerald-100",
            disabled: bk.status === "checked_in" || bk.status === "checked_out" || bk.status === "no_show",
            onClick: () => { changeStatus(bk.id, "checked_in"); setQuickActions(null); } },
          { id: "checkout",  label: "Check Out", icon: LogOut,     color: "text-amber-600 bg-amber-50 hover:bg-amber-100",
            disabled: bk.status !== "checked_in",
            onClick: () => { changeStatus(bk.id, "checked_out"); setQuickActions(null); } },
          { id: "noshow",    label: "No-Show",   icon: UserX,      color: "text-rose-600 bg-rose-50 hover:bg-rose-100",
            disabled: bk.status === "checked_out" || bk.status === "no_show",
            onClick: () => { if (window.confirm(`Mark ${bk.guest_name} as NO-SHOW? This charges the booking and blocks the room.`)) { changeStatus(bk.id, "no_show"); } setQuickActions(null); } },
          { id: "addnote",   label: "Add Note",  icon: StickyNote, color: "text-amber-600 bg-amber-50 hover:bg-amber-100",
            onClick: () => { openDetail(bk.id); setQuickActions(null); toast.info("Notes tab opened"); } },
          { id: "copy",      label: "Duplicate", icon: Copy,       color: "text-sky-600 bg-sky-50 hover:bg-sky-100",
            onClick: () => {
              const co = new Date(bk.check_out);
              const nextCi = new Date(co);
              setCreateBookingState({ room_id: bk.room_id, room_name: roomName, room_type_id: bk.room_type_id, check_in: nextCi.toISOString().slice(0, 10) });
              setCreateForm({ guest_name: bk.guest_name || "", guest_email: bk.guest_email || "", guest_phone: bk.guest_phone || "", nights: bk.nights || 1, adults: bk.adults || 2, children: bk.children || 0 });
              setQuickActions(null);
              toast.info("Duplicate booking — edit dates and save");
            } },
          { id: "lock",      label: "Lock",      icon: Lock,       color: "text-stone-600 bg-stone-50 hover:bg-stone-100",
            onClick: () => { toast.info("Booking locked — cannot be modified"); setQuickActions(null); } },
          { id: "details",   label: "Details",   icon: LayoutList, color: "text-violet-600 bg-violet-50 hover:bg-violet-100",
            onClick: () => { openDetail(bk.id); setQuickActions(null); } },
          { id: "cancel",    label: "Cancel",    icon: X,          color: "text-rose-700 bg-rose-50 hover:bg-rose-100",
            disabled: bk.status === "cancelled" || bk.status === "checked_out",
            onClick: () => { if (window.confirm(`Cancel booking for ${bk.guest_name}?`)) { changeStatus(bk.id, "cancelled"); } setQuickActions(null); } },
          { id: "sendlink",  label: "Send Link", icon: Send, color: "text-indigo-600 bg-indigo-50 hover:bg-indigo-100",
            disabled: !bk.guest_email,
            onClick: async () => {
              try { await axios.post(`${API}/guest-checkin/send-link/${bk.id}`); toast.success("Check-in link sent to guest"); }
              catch { toast.error("Failed to send"); }
              setQuickActions(null);
            } },
          { id: "invitekit", label: "Davet Kiti", icon: Send, color: "text-emerald-700 bg-emerald-50 hover:bg-emerald-100",
            onClick: async () => {
              try {
                const { data } = await axios.get(`${API}/guest-journey/invite-kit/${bk.id}`);
                await navigator.clipboard.writeText(data.message_tr);
                window.open(data.whatsapp_link_tr, "_blank");
                toast.success("Davet mesajı kopyalandı, WhatsApp açıldı — kimlik yükleme linki içeriyor");
              } catch { toast.error("Davet kiti oluşturulamadı"); }
              setQuickActions(null);
            } },
        ];
        return (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setQuickActions(null)} data-testid="qa-overlay" />
            <div className="fixed z-50 bg-white rounded-2xl shadow-2xl border border-stone-200 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150"
                 style={{ left, top, width: popoverW }} data-testid="quick-actions-popover">
              {/* Header */}
              <div className="px-4 py-3 border-b border-stone-100 bg-gradient-to-br from-white to-stone-50">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-bold text-stone-900 text-sm truncate" data-testid="qa-guest">{bk.guest_name}</span>
                  <Badge className={`text-[9px] font-bold uppercase ${sc.bar} ${sc.text} border-0 flex-shrink-0`} data-testid="qa-status">{sc.label}</Badge>
                </div>
                <div className="flex items-center gap-1 text-[11px] text-stone-500">
                  <Bed className="w-3 h-3" /> <span className="truncate">{roomName}</span>
                </div>
              </div>
              {/* IN / OUT / TOTAL row */}
              <div className="grid grid-cols-3 border-b border-stone-100 bg-stone-50/50">
                <div className="px-3 py-2 text-center border-r border-stone-100">
                  <div className="text-[9px] text-stone-400 uppercase font-bold">IN</div>
                  <div className="text-[11px] font-semibold text-stone-800 leading-tight">{new Date(bk.check_in).toLocaleDateString("en-GB", { weekday: "short", month: "short", day: "numeric" })}</div>
                </div>
                <div className="px-3 py-2 text-center border-r border-stone-100">
                  <div className="text-[9px] text-stone-400 uppercase font-bold">OUT</div>
                  <div className="text-[11px] font-semibold text-stone-800 leading-tight">{new Date(bk.check_out).toLocaleDateString("en-GB", { weekday: "short", month: "short", day: "numeric" })}</div>
                </div>
                <div className="px-3 py-2 text-center">
                  <div className="text-[9px] text-stone-400 uppercase font-bold">TOTAL</div>
                  <div className="text-[11px] font-bold text-emerald-700 leading-tight">{cur(bk.total_price)}</div>
                </div>
              </div>
              {/* 6 action buttons in 2x3 grid */}
              <div className="grid grid-cols-3 gap-0">
                {actions.map(a => (
                  <button
                    key={a.id}
                    onClick={a.onClick}
                    disabled={a.disabled}
                    data-testid={`qa-${a.id}`}
                    className={`flex flex-col items-center justify-center gap-1 py-3 transition-colors border-r last:border-r-0 border-b last-3:border-b-0 border-stone-100 disabled:opacity-40 disabled:cursor-not-allowed ${a.color}`}
                  >
                    <a.icon className="w-4 h-4" />
                    <span className="text-[10px] font-semibold">{a.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        );
      })()}

      {/* Collision Cluster Modal — "+N more" hidden bookings */}
      {showResolver && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowResolver(false)} data-testid="overbooking-resolver-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-rose-600 to-red-500 rounded-t-2xl">
              <div>
                <h3 className="text-sm font-black text-white flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Overbooking Çözüm Önerileri</h3>
                <p className="text-[11px] text-rose-100 mt-0.5">Sistem her çakışma için uygun boş oda buldu — tek tıkla taşıyın.</p>
              </div>
              <button onClick={() => setShowResolver(false)} className="p-1 hover:bg-white/20 rounded-lg" data-testid="resolver-close"><X className="w-4 h-4 text-white" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {conflictPairs.length === 0 ? (
                <div className="text-center py-10" data-testid="resolver-empty">
                  <div className="text-3xl mb-2">🎉</div>
                  <p className="text-sm font-bold text-emerald-700">Tüm çakışmalar çözüldü!</p>
                  <p className="text-[11px] text-stone-500 mt-1">Takvimde açık overbooking kalmadı.</p>
                </div>
              ) : conflictPairs.map((cp, i) => (
                <div key={`${cp.mover.id}-${i}`} className="border border-rose-200 bg-rose-50/50 rounded-xl p-3" data-testid={`resolver-row-${cp.mover.id}`}>
                  <div className="flex items-center gap-2 text-[11px] font-bold text-rose-700 mb-2">
                    <Bed className="w-3.5 h-3.5" /> {cp.roomName} — çakışan tarihler
                  </div>
                  <div className="grid grid-cols-2 gap-2 mb-2.5">
                    <div className="bg-white border border-stone-200 rounded-lg px-2.5 py-1.5">
                      <div className="text-xs font-semibold text-stone-800 truncate">{cp.stay.guest_name}</div>
                      <div className="text-[10px] text-stone-500">{cp.stay.check_in} → {cp.stay.check_out} · kalıyor</div>
                    </div>
                    <div className="bg-white border border-rose-300 rounded-lg px-2.5 py-1.5">
                      <div className="text-xs font-semibold text-stone-800 truncate">{cp.mover.guest_name}</div>
                      <div className="text-[10px] text-rose-600">{cp.mover.check_in} → {cp.mover.check_out} · taşınacak</div>
                    </div>
                  </div>
                  {cp.suggestion ? (
                    <button onClick={() => applySuggestedMove(cp.mover, cp.suggestion.id, cp.suggestion.name)}
                      data-testid={`suggest-move-${cp.mover.id}`}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow transition-all">
                      <ChevronRight className="w-3.5 h-3.5" /> {cp.mover.guest_name} → {cp.suggestion.name}'e taşı
                      <span className="text-[9px] font-semibold text-emerald-100 bg-emerald-700/50 rounded-full px-1.5 py-0.5 ml-1">{cp.suggestion.room_type_name}</span>
                    </button>
                  ) : (
                    <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2" data-testid={`no-suggestion-${cp.mover.id}`}>
                      Bu tarihler için uygun boş oda yok — tarih değişikliği veya iptal gerekir.
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {collisionCluster && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setCollisionCluster(null)} data-testid="collision-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="bg-gradient-to-br from-rose-500 via-red-600 to-rose-700 px-5 py-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-white text-base">Overlapping Bookings</h3>
                <p className="text-[11px] text-rose-100">{collisionCluster.room.name} · {collisionCluster.cluster.items.length} booking{collisionCluster.cluster.items.length === 1 ? "" : "s"} collide in {collisionCluster.cluster.check_in} → {collisionCluster.cluster.check_out}</p>
              </div>
              <button onClick={() => setCollisionCluster(null)} className="p-1 hover:bg-white/20 rounded-lg" data-testid="collision-close"><X className="w-4 h-4 text-white" /></button>
            </div>
            <div className="max-h-96 overflow-auto divide-y divide-stone-100">
              {collisionCluster.cluster.items.map(bk => {
                const sc = STATUS_COLORS[resolveDisplayStatus(bk)] || STATUS_COLORS.confirmed;
                const src = bk.source || bk.source_code || "";
                return (
                  <button
                    key={bk.id}
                    onClick={() => { setCollisionCluster(null); openDetail(bk.id); }}
                    data-testid={`collision-item-${bk.id}`}
                    className="w-full px-5 py-3 flex items-center gap-3 hover:bg-rose-50/60 text-left transition-colors"
                  >
                    <div className={`w-1 h-10 rounded-full ${getSourceStrip(src)} flex-shrink-0`}></div>
                    <PlatformLogo source={src} size={20} />
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-stone-800 text-sm truncate">{bk.guest_name}</div>
                      <div className="text-[11px] text-stone-500 truncate">{bk.check_in} → {bk.check_out} · {bk.nights}n · {src || "Direct"}</div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <Badge className={`${sc.bar} ${sc.text} text-[9px] border-0`}>{sc.label}</Badge>
                      <div className="text-xs font-bold font-mono text-stone-700 mt-1">{cur(bk.total_price)}</div>
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="p-3 bg-stone-50 border-t border-stone-100 flex items-center justify-between">
              <span className="text-[11px] text-stone-500 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-amber-500" />
                Tip: drag a booking to another room to resolve the collision.
              </span>
              <button onClick={() => setCollisionCluster(null)} className="text-xs font-semibold text-stone-600 hover:text-stone-900" data-testid="collision-close-btn">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Booking Detail Slide-Over */}
      {selectedBooking && detailData && (
        <div className="fixed inset-0 z-50 flex justify-end" data-testid="booking-detail-panel">
          <div className="absolute inset-0 bg-black/30" onClick={() => { setSelectedBooking(null); setDetailData(null); }} />
          <div className="relative w-[420px] bg-white shadow-2xl overflow-y-auto animate-in slide-in-from-right">
            {/* Detail Header */}
            <div className="sticky top-0 bg-white border-b border-stone-200 px-5 py-4 z-10">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-stone-800" data-testid="detail-guest-name">{detailData.guest_name}</h3>
                <button onClick={() => { setSelectedBooking(null); setDetailData(null); }} className="p-1 hover:bg-stone-100 rounded-lg" data-testid="detail-close"><X className="w-4 h-4" /></button>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={`${STATUS_COLORS[detailData.status]?.bar || "bg-stone-300"} ${STATUS_COLORS[detailData.status]?.text || "text-white"} text-[10px]`}>
                  {STATUS_COLORS[detailData.status]?.label || detailData.status}
                </Badge>
                <span className="text-[10px] text-stone-400">#{detailData.id?.slice(0, 8)}</span>
              </div>
            </div>

            {/* Detail Body */}
            <div className="p-5 space-y-5">
              {/* Tabs */}
              <div className="flex gap-1 bg-stone-100 rounded-lg p-0.5" data-testid="detail-tabs">
                {[
                  { id: "info", label: "Info" },
                  { id: "folio", label: "Folio" },
                  { id: "upsell", label: "Upsell" },
                  { id: "actions", label: "Actions" },
                ].map(t => (
                  <button key={t.id} onClick={() => { setDetailTab(t.id); if (t.id === "folio" && !folio) loadFolio(detailData.id); if (t.id === "upsell" && !upsells) loadUpsells(detailData.id); }}
                    data-testid={`detail-tab-${t.id}`}
                    className={`flex-1 px-3 py-1.5 text-xs font-semibold rounded-md ${detailTab === t.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500"}`}>
                    {t.label}
                  </button>
                ))}
              </div>

              {/* INFO TAB */}
              {detailTab === "info" && (<>
              {/* Dates */}
              <div className="grid grid-cols-3 gap-3">
                <div><p className="text-[9px] text-stone-400 uppercase">Check-In</p><p className="text-sm font-bold">{detailData.check_in}</p></div>
                <div><p className="text-[9px] text-stone-400 uppercase">Check-Out</p><p className="text-sm font-bold">{detailData.check_out}</p></div>
                <div><p className="text-[9px] text-stone-400 uppercase">Nights</p><p className="text-sm font-bold">{detailData.nights || 1}</p></div>
              </div>

              {/* Guest Info */}
              <div className="bg-stone-50 rounded-xl p-4 space-y-2">
                <p className="text-[9px] text-stone-400 uppercase font-bold">Guest Details</p>
                <div className="flex items-center gap-2 text-sm"><User className="w-3.5 h-3.5 text-stone-400" />{detailData.guest_name}</div>
                {detailData.guest_email && <div className="flex items-center gap-2 text-xs text-stone-500"><Mail className="w-3.5 h-3.5 text-stone-400" />{detailData.guest_email}</div>}
                {detailData.guest_phone && <div className="flex items-center gap-2 text-xs text-stone-500"><Phone className="w-3.5 h-3.5 text-stone-400" />{detailData.guest_phone}</div>}
                <div className="flex items-center gap-4 text-xs text-stone-500">
                  <span>{detailData.adults || 1} adult{(detailData.adults || 1) > 1 ? "s" : ""}</span>
                  {detailData.children > 0 && <span>{detailData.children} child{detailData.children > 1 ? "ren" : ""}</span>}
                </div>
              </div>

              {/* Room Info */}
              <div className="bg-stone-50 rounded-xl p-4 space-y-2">
                <p className="text-[9px] text-stone-400 uppercase font-bold">Accommodation</p>
                <div className="flex items-center gap-2 text-sm"><Bed className="w-3.5 h-3.5 text-stone-400" />{detailData.room_type_name}</div>
                {detailData.room_name && <div className="flex items-center gap-2 text-xs text-stone-500"><MapPin className="w-3.5 h-3.5 text-stone-400" />Room: {detailData.room_name}{detailData.room_floor ? ` (Floor ${detailData.room_floor})` : ""}</div>}
              </div>

              {/* Quick Financial Summary */}
              <div className="bg-stone-50 rounded-xl p-4 space-y-2">
                <p className="text-[9px] text-stone-400 uppercase font-bold">Summary</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Total</span>
                  <span className="text-sm font-bold">{cur(detailData.total_price)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Payment</span>
                  <Badge className={`text-[10px] ${detailData.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{detailData.payment_status || "pending"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Source</span>
                  <span className="text-xs font-medium flex items-center gap-1.5">
                    <PlatformLogo source={detailData.source || detailData.source_code} size={18} />
                    {detailData.source} {detailData.source_code && detailData.source !== detailData.source_code ? `(${detailData.source_code})` : ""}
                  </span>
                </div>
              </div>

              {/* Timestamps */}
              <div className="text-[10px] text-stone-400 space-y-1 border-t border-stone-100 pt-3">
                {detailData.created_at && <p>Booked: {new Date(detailData.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</p>}
                <p>ID: {detailData.id}</p>
                {detailData.registration_completed && <p className="text-emerald-500 font-bold">Digital check-in completed</p>}
              </div>
              </>)}

              {/* FOLIO TAB */}
              {detailTab === "folio" && (<>
              <div className="space-y-3" data-testid="folio-tab">
                {folio ? (<>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-bold text-stone-800 flex items-center gap-1.5"><Receipt className="w-4 h-4 text-stone-500" />{folio.invoice_number}</p>
                      <p className="text-[10px] text-stone-400">{folio.room?.type} — {folio.room?.name}</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => downloadPdf(`/folio/${detailData.id}/pdf`, `folio-${detailData.id.slice(0,8)}.pdf`)}
                        data-testid="print-folio-btn"
                        className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold text-stone-700 bg-white border border-stone-200 rounded-lg hover:bg-stone-50"
                        title="Open folio PDF">
                        <Printer className="w-3 h-3" />Print
                      </button>
                      <button onClick={() => setShowAddCharge(true)} data-testid="add-charge-btn" className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold text-stone-600 bg-stone-100 rounded-lg hover:bg-stone-200">
                        <Plus className="w-3 h-3" />Add Charge
                      </button>
                    </div>
                  </div>

                  {/* Sub-folio tabs (split folio) */}
                  {subFolios.length > 0 && (
                    <div className="flex items-center gap-1 overflow-x-auto border-b border-stone-200 pb-0.5" data-testid="sub-folio-tabs">
                      {subFolios.map(sf => (
                        <button key={sf.id} onClick={() => setActiveSubFolio(sf.id)}
                          data-testid={`sub-folio-tab-${sf.id}`}
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold rounded-t-lg whitespace-nowrap ${
                            activeSubFolio === sf.id
                              ? "bg-stone-800 text-white"
                              : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                          }`}>
                          <span>{sf.name}</span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${activeSubFolio === sf.id ? "bg-white/20" : "bg-stone-300 text-stone-600"}`}>
                            {cur(sf.totals.balance)}
                          </span>
                          {activeSubFolio === sf.id && (
                            <>
                              <span role="button" tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); printSubFolio(sf.id); }}
                                data-testid={`sub-folio-print-${sf.id}`}
                                className="ml-1 text-white/70 hover:text-white cursor-pointer"
                                title={`Print ${sf.name} folio`}><Printer className="w-3 h-3" /></span>
                              <span role="button" tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); setEmailSubFolioFor({ sfId: sf.id, sfName: sf.name, balance: sf.totals.balance, currency: sf.currency_symbol, payerEmail: sf.payer_email || "" }); }}
                                data-testid={`sub-folio-email-${sf.id}`}
                                className="text-white/70 hover:text-white cursor-pointer"
                                title={`Email ${sf.name} folio`}><Mail className="w-3 h-3" /></span>
                              {!sf.is_default && (
                                <>
                                  <span role="button" tabIndex={0}
                                    onClick={(e) => { e.stopPropagation(); setEditPayerFor({ sfId: sf.id, sfName: sf.name, payerName: sf.payer_name || "", payerEmail: sf.payer_email || "" }); }}
                                    data-testid={`sub-folio-edit-payer-${sf.id}`}
                                    className="text-white/70 hover:text-white cursor-pointer"
                                    title={`Set payer for ${sf.name}`}><Edit3 className="w-3 h-3" /></span>
                                  <span role="button" tabIndex={0}
                                    onClick={(e) => { e.stopPropagation(); deleteSubFolio(sf.id); }}
                                    className="ml-1 text-white/50 hover:text-rose-300 cursor-pointer"
                                    title="Delete sub-folio"><X className="w-3 h-3" /></span>
                                </>
                              )}
                            </>
                          )}
                        </button>
                      ))}
                      <button onClick={() => setNewSubFolioOpen(true)} data-testid="new-sub-folio-btn"
                        className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold text-stone-500 hover:text-stone-800">
                        <Plus className="w-3 h-3" />Split
                      </button>
                    </div>
                  )}

                  {/* Inline "New sub-folio" input */}
                  {newSubFolioOpen && (
                    <div className="flex gap-2 bg-stone-50 p-2 rounded-lg">
                      <input value={newSubFolioName} onChange={e => setNewSubFolioName(e.target.value)}
                        autoFocus placeholder='e.g. "Company Card", "Personal", "Guest 2"'
                        data-testid="new-sub-folio-name"
                        onKeyDown={e => e.key === "Enter" && createSubFolio()}
                        className="flex-1 border border-stone-200 rounded px-2 py-1 text-xs" />
                      <button onClick={createSubFolio} data-testid="submit-sub-folio"
                        className="px-3 py-1 text-xs bg-stone-800 text-white rounded">Create</button>
                      <button onClick={() => { setNewSubFolioOpen(false); setNewSubFolioName(""); }}
                        className="px-2 py-1 text-xs text-stone-400">Cancel</button>
                    </div>
                  )}

                  {/* Add Charge Form */}
                  {showAddCharge && (
                    <div className="bg-stone-50 rounded-xl p-3 space-y-2" data-testid="add-charge-form">
                      <input id="charge-desc" placeholder="Description (e.g. Minibar, Room Service)" className="w-full border border-stone-200 rounded-lg px-3 py-1.5 text-xs" />
                      <div className="flex gap-2">
                        <input id="charge-amt" type="number" step="0.01" placeholder="Amount" className="flex-1 border border-stone-200 rounded-lg px-3 py-1.5 text-xs" />
                        <select id="charge-cat" className="border border-stone-200 rounded-lg px-2 py-1.5 text-xs">
                          <option value="minibar">Minibar</option>
                          <option value="room_service">Room Service</option>
                          <option value="laundry">Laundry</option>
                          <option value="spa">Spa</option>
                          <option value="parking">Parking</option>
                          <option value="damage">Damage</option>
                          <option value="extra">Other</option>
                        </select>
                      </div>
                      <div className="flex justify-end gap-2">
                        <button onClick={() => setShowAddCharge(false)} className="text-xs text-stone-400">Cancel</button>
                        <button onClick={() => { const d = document.getElementById("charge-desc").value; const a = document.getElementById("charge-amt").value; const c = document.getElementById("charge-cat").value; if (d && a) addCharge(d, a, c); }} data-testid="submit-charge-btn"
                          className="px-3 py-1.5 text-xs font-bold text-white bg-stone-800 rounded-lg">Add</button>
                      </div>
                    </div>
                  )}

                  {/* Items List — filtered by active sub-folio */}
                  <div className="space-y-1">
                    {(() => {
                      const activeSF = subFolios.find(s => s.id === activeSubFolio);
                      const items = activeSF ? activeSF.items : folio.items;
                      const totals = activeSF ? activeSF.totals : folio.totals;
                      return <>
                        {items.map(item => {
                          const isPayment = item.type === "payment";
                          const method = (item.payment_method || item.category || "").toLowerCase();
                          const methodBadges = {
                            cash: { label: "Cash", cls: "bg-emerald-100 text-emerald-700" },
                            card: { label: "Card", cls: "bg-sky-100 text-sky-700" },
                            bank_transfer: { label: "Bank", cls: "bg-violet-100 text-violet-700" },
                            channel_collection: { label: item.channel || "OTA", cls: "bg-fuchsia-100 text-fuchsia-700" },
                          };
                          const badge = isPayment ? methodBadges[method] : null;
                          return (
                          <div key={item.id} className={`flex items-center justify-between py-2 px-3 rounded-lg text-xs ${isPayment ? "bg-emerald-50" : item.type === "adjustment" ? "bg-amber-50" : "bg-white border border-stone-100"}`}>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-stone-700 flex items-center gap-1.5 flex-wrap">
                                <span className="truncate">{item.description}</span>
                                {badge && <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${badge.cls}`} data-testid={`folio-payment-badge-${item.id}`}>{badge.label}</span>}
                                {isPayment && item.reference && <span className="text-[9px] font-mono text-stone-400">· {item.reference}</span>}
                              </p>
                              <p className="text-[10px] text-stone-400">{item.category} {item.quantity > 1 ? `x${item.quantity}` : ""}</p>
                            </div>
                            {subFolios.length > 1 && (
                              <select value={item.sub_folio_id || "primary"} onChange={e => moveFolioItem(item.id, e.target.value)}
                                data-testid={`move-item-${item.id}`}
                                className="mr-2 text-[10px] border border-stone-200 rounded px-1 py-0.5 bg-white" title="Move to sub-folio">
                                {subFolios.map(sf => <option key={sf.id} value={sf.id}>{sf.name}</option>)}
                              </select>
                            )}
                            <span className={`font-bold ${isPayment ? "text-emerald-600" : item.type === "adjustment" ? "text-amber-600" : "text-stone-800"}`}>
                              {isPayment ? "-" : ""}{cur(item.amount)}
                            </span>
                          </div>
                          );
                        })}
                        {items.length === 0 && <p className="text-center text-xs text-stone-400 py-6">No items in this sub-folio yet.</p>}

                        {/* Totals — for active sub-folio */}
                        <div className="bg-stone-800 rounded-xl p-4 space-y-2 text-white mt-3" data-testid="folio-totals">
                          <div className="flex justify-between text-xs"><span className="text-stone-400">Charges</span><span>{cur(totals.charges)}</span></div>
                          {totals.payments > 0 && <div className="flex justify-between text-xs"><span className="text-stone-400">Payments</span><span className="text-emerald-400">-{cur(totals.payments)}</span></div>}
                          {totals.adjustments !== 0 && <div className="flex justify-between text-xs"><span className="text-stone-400">Adjustments</span><span className="text-amber-400">{cur(totals.adjustments)}</span></div>}
                          <div className="h-px bg-stone-700" />
                          <div className="flex justify-between text-sm font-bold"><span>{activeSF && !activeSF.is_default ? `${activeSF.name} — Balance` : "Balance Due"}</span>
                            <span className={(activeSF ? activeSF.totals.balance : folio.totals.balance_due) <= 0 ? "text-emerald-400" : "text-red-400"}>
                              {cur(activeSF ? activeSF.totals.balance : folio.totals.balance_due)}
                            </span>
                          </div>
                        </div>
                      </>;
                    })()}
                  </div>

                  {/* Quick Payment — explicit type picker (cash / card / bank / channel) */}
                  {folio.totals.balance_due > 0 && (
                    <div className="space-y-2" data-testid="folio-record-payment-picker">
                      <div className="text-[10px] font-bold uppercase text-stone-500">Record payment · {cur(folio.totals.balance_due)} due</div>
                      <div className="grid grid-cols-4 gap-1.5">
                        <button onClick={() => addPayment(folio.totals.balance_due, "cash")} data-testid="record-payment-cash"
                          className="flex flex-col items-center gap-0.5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-[10px] font-bold">
                          <Banknote className="w-3.5 h-3.5" />Cash
                        </button>
                        <button onClick={() => addPayment(folio.totals.balance_due, "card")} data-testid="record-payment-card"
                          className="flex flex-col items-center gap-0.5 py-2 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-[10px] font-bold">
                          <CreditCard className="w-3.5 h-3.5" />Card
                        </button>
                        <button onClick={() => addPayment(folio.totals.balance_due, "bank_transfer")} data-testid="record-payment-bank"
                          className="flex flex-col items-center gap-0.5 py-2 rounded-lg bg-violet-500 hover:bg-violet-600 text-white text-[10px] font-bold">
                          <Landmark className="w-3.5 h-3.5" />Bank
                        </button>
                        <button onClick={() => addPayment(folio.totals.balance_due, "channel_collection")} data-testid="record-payment-channel"
                          className="flex flex-col items-center gap-0.5 py-2 rounded-lg bg-fuchsia-500 hover:bg-fuchsia-600 text-white text-[10px] font-bold">
                          <Globe className="w-3.5 h-3.5" />Channel
                        </button>
                      </div>
                      <p className="text-[10px] text-stone-400 text-center">Tip: click the flashing balance chip on the calendar for a partial-payment flow with amount picker.</p>

                      {/* Stripe Pay-by-Link — tek tıkla ödeme linki */}
                      <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-2.5 space-y-2" data-testid="stripe-paylink-box">
                        <div className="text-[10px] font-bold uppercase text-indigo-300">Stripe Ödeme Linki (pay-by-link)</div>
                        {!payLink ? (
                          <button onClick={generatePayLink} disabled={payLinkBusy} data-testid="generate-paylink-btn"
                            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#635BFF] hover:bg-[#5349f0] text-white text-[11px] font-bold disabled:opacity-50">
                            <CreditCard className="w-3.5 h-3.5" />
                            {payLinkBusy ? "Üretiliyor..." : `Ödeme Linki Üret · ${cur(folio.totals.balance_due)}`}
                          </button>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-1.5">
                              <input readOnly value={payLink} data-testid="paylink-url-input"
                                className="flex-1 min-w-0 rounded bg-stone-900 border border-stone-700 px-2 py-1.5 text-[10px] text-stone-300 font-mono truncate" />
                              <button onClick={async () => {
                                try { await navigator.clipboard.writeText(payLink); toast.success("Kopyalandı"); }
                                catch { toast.error("Pano erişimi engellendi — linki elle seçip kopyalayın"); }
                              }}
                                data-testid="paylink-copy-btn"
                                className="p-1.5 rounded bg-stone-700 hover:bg-stone-600 text-white"><Copy className="w-3.5 h-3.5" /></button>
                            </div>
                            <div className="grid grid-cols-2 gap-1.5">
                              <button onClick={emailPayLink} data-testid="paylink-email-btn"
                                className="flex items-center justify-center gap-1 py-1.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold">
                                <Mail className="w-3 h-3" /> E-posta Gönder
                              </button>
                              <button onClick={() => setPayLink(null)} data-testid="paylink-new-btn"
                                className="py-1.5 rounded bg-stone-700 hover:bg-stone-600 text-stone-300 text-[10px] font-bold">
                                Yeni Link
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>) : (
                  <div className="text-center py-8 text-stone-400"><RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />Loading folio...</div>
                )}
              </div>
              </>)}

              {/* UPSELL TAB */}
              {detailTab === "upsell" && (<>
              <div className="space-y-3" data-testid="upsell-tab">
                {upsells ? (<>
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-stone-500">Upsell potential: <strong className="text-stone-800">{`£${upsells.total_potential}`}</strong></p>
                    <Badge className="bg-violet-100 text-violet-700 text-[10px]">{upsells.suggestions?.length} options</Badge>
                  </div>
                  {upsells.suggestions?.map(s => (
                    <div key={s.id} className={`border rounded-xl p-3 flex items-center justify-between ${s.type === "room_upgrade" ? "border-amber-200 bg-amber-50" : s.type === "addon" ? "border-stone-200 bg-white" : "border-blue-200 bg-blue-50"}`}>
                      <div>
                        <p className="text-xs font-bold text-stone-800">{s.title}</p>
                        <p className="text-[10px] text-stone-500">{s.description}</p>
                        <p className="text-xs font-bold text-emerald-600 mt-0.5">{s.price_label}</p>
                      </div>
                      <button onClick={() => acceptUpsell(s)} data-testid={`accept-upsell-${s.id}`}
                        className="px-2.5 py-1.5 text-[10px] font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg flex-shrink-0">
                        Accept
                      </button>
                    </div>
                  ))}
                </>) : (
                  <div className="text-center py-8 text-stone-400"><RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />Loading upsells...</div>
                )}
              </div>
              </>)}

              {/* ACTIONS TAB */}
              {detailTab === "actions" && (<>
              <div className="space-y-4" data-testid="actions-tab">
                {/* Status Actions */}
                <div>
                  <p className="text-[9px] text-stone-400 uppercase font-bold mb-2">Change Status</p>
                  <div className="grid grid-cols-2 gap-2">
                    {detailData.status === "confirmed" && (
                      <button onClick={() => changeStatus(detailData.id, "checked_in")} data-testid="action-checkin"
                        className="px-3 py-2 text-xs font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg">Check In</button>
                    )}
                    {detailData.status === "checked_in" && (
                      <button onClick={() => changeStatus(detailData.id, "checked_out")} data-testid="action-checkout"
                        className="px-3 py-2 text-xs font-bold text-white bg-stone-600 hover:bg-stone-700 rounded-lg">Check Out</button>
                    )}
                    {detailData.status === "confirmed" && (
                      <button onClick={() => changeStatus(detailData.id, "no_show")} data-testid="action-noshow"
                        className="px-3 py-2 text-xs font-bold text-white bg-red-500 hover:bg-red-600 rounded-lg">No Show</button>
                    )}
                    {detailData.status === "pending" && (
                      <button onClick={() => changeStatus(detailData.id, "confirmed")} data-testid="action-confirm"
                        className="px-3 py-2 text-xs font-bold text-white bg-blue-500 hover:bg-blue-600 rounded-lg">Confirm</button>
                    )}
                    {!["cancelled", "checked_out"].includes(detailData.status) && (
                      <button onClick={() => changeStatus(detailData.id, "cancelled")} data-testid="action-cancel"
                        className="px-3 py-2 text-xs font-bold text-stone-600 bg-stone-100 hover:bg-stone-200 rounded-lg">Cancel</button>
                    )}
                  </div>
                </div>

                {/* Guest Services */}
                <div>
                  <p className="text-[9px] text-stone-400 uppercase font-bold mb-2">Guest Services</p>
                  <div className="space-y-2">
                    <button onClick={sendCheckinLink} data-testid="send-checkin-link"
                      className="w-full flex items-center gap-2 px-3 py-2.5 text-xs font-semibold text-violet-700 bg-violet-50 hover:bg-violet-100 rounded-lg border border-violet-200">
                      <Send className="w-3.5 h-3.5" />Send Digital Check-in Link
                    </button>
                    <div className="flex gap-2">
                      <button onClick={() => downloadPdf(`/bookings/${detailData.id}/registration-card.pdf`, `reg-card-${detailData.id.slice(0,8)}.pdf`)}
                        data-testid="print-reg-card-btn"
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-semibold text-stone-800 bg-stone-100 hover:bg-stone-200 rounded-lg border border-stone-200">
                        <Printer className="w-3.5 h-3.5" />Print Registration Card
                      </button>
                      <button onClick={() => emailDocument("reg_card")}
                        data-testid="email-reg-card-btn"
                        title="Email to guest"
                        className="px-3 py-2.5 text-xs font-semibold text-stone-700 bg-white hover:bg-stone-50 rounded-lg border border-stone-200">
                        <Mail className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => downloadPdf(`/folio/${detailData.id}/pdf`, `folio-${detailData.id.slice(0,8)}.pdf`)}
                        data-testid="print-folio-actions-btn"
                        className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 rounded-lg border border-emerald-200">
                        <Receipt className="w-3.5 h-3.5" />Print Folio Receipt
                      </button>
                      <button onClick={() => emailDocument("folio")}
                        data-testid="email-folio-btn"
                        title="Email to guest"
                        className="px-3 py-2.5 text-xs font-semibold text-emerald-700 bg-white hover:bg-emerald-50 rounded-lg border border-emerald-200">
                        <Mail className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <button onClick={openCorpInvoiceModal} data-testid="create-corp-invoice-btn"
                      className="w-full flex items-center gap-2 px-3 py-2.5 text-xs font-semibold text-amber-900 bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-200">
                      <Building2 className="w-3.5 h-3.5" />Create Corporate Invoice (City Ledger)
                    </button>
                  </div>
                </div>
              </div>
              </>)}
            </div>
          </div>
        </div>
      )}

      {/* Sub-Folio Email modal — user composes To/Subject/Message */}
      {emailSubFolioFor && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={() => setEmailSubFolioFor(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg" onClick={e => e.stopPropagation()} data-testid="sub-folio-email-modal">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-stone-900 flex items-center gap-2"><Mail className="w-5 h-5 text-sky-600" />Email {emailSubFolioFor.sfName} Folio</h2>
              <button onClick={() => setEmailSubFolioFor(null)} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
            </div>
            <SubFolioEmailForm
              defaultTo={emailSubFolioFor.payerEmail || detailData?.guest_email || ""}
              sfName={emailSubFolioFor.sfName}
              balance={emailSubFolioFor.balance}
              onSend={sendSubFolioEmail}
              onCancel={() => setEmailSubFolioFor(null)}
            />
          </div>
        </div>
      )}

      {/* Edit Payer modal — saves payer_name + payer_email on a sub-folio */}
      {editPayerFor && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={() => setEditPayerFor(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()} data-testid="edit-payer-modal">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-stone-900 flex items-center gap-2"><Edit3 className="w-5 h-5 text-stone-600" />Set Payer · {editPayerFor.sfName}</h2>
              <button onClick={() => setEditPayerFor(null)} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
            </div>
            <p className="text-xs text-stone-500 mb-3">Saving a payer email means the next time you click Email on this sub-folio, the To field is pre-filled with this address.</p>
            <div className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Payer Name</label>
                <input defaultValue={editPayerFor.payerName} id="payer-name-input" autoFocus
                  placeholder="e.g. Acme Ltd · Accounts"
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
                  data-testid="payer-name-input" />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Payer Email</label>
                <input defaultValue={editPayerFor.payerEmail} id="payer-email-input"
                  placeholder="accounts@acme.co"
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
                  data-testid="payer-email-input" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setEditPayerFor(null)} className="px-4 py-2 text-sm">Cancel</button>
              <button onClick={() => {
                const n = document.getElementById("payer-name-input").value;
                const e = document.getElementById("payer-email-input").value;
                savePayer(n, e);
              }} data-testid="payer-save-btn" className="px-4 py-2 bg-stone-800 hover:bg-stone-900 text-white rounded-lg text-sm font-semibold">Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Corporate Invoice (City Ledger) modal */}
      {corpInvoiceOpen && (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={() => setCorpInvoiceOpen(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg" onClick={e => e.stopPropagation()} data-testid="corp-invoice-modal">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-stone-900 flex items-center gap-2"><Building2 className="w-5 h-5 text-amber-600" />Create Corporate Invoice</h2>
              <button onClick={() => setCorpInvoiceOpen(false)} className="p-1 hover:bg-stone-100 rounded-lg"><X className="w-4 h-4 text-stone-500" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Bill to Company *</label>
                <select value={corpForm.company_id} onChange={e => setCorpForm({ ...corpForm, company_id: e.target.value })}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="corp-inv-company">
                  <option value="">— Select company —</option>
                  {corpCompanies.map(c => <option key={c.id} value={c.id}>{`${c.name}${c.payment_terms_days ? ` (${c.payment_terms_days}d terms)` : ""}`}</option>)}
                </select>
                {corpCompanies.length === 0 && <p className="text-[11px] text-rose-600 mt-1">No active companies. Create one in City Ledger → Companies first.</p>}
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Amount *</label>
                <input type="number" step="0.01" value={corpForm.amount} onChange={e => setCorpForm({ ...corpForm, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="corp-inv-amount" />
                <p className="text-[10px] text-stone-400 mt-1">Pre-filled from folio total — edit if needed.</p>
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Notes</label>
                <textarea value={corpForm.notes} onChange={e => setCorpForm({ ...corpForm, notes: e.target.value })} rows={3}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              </div>
              <p className="text-[11px] text-stone-500 bg-amber-50 border border-amber-200 rounded-lg p-2">
                Invoice will be auto-numbered (<code>CL-YYYY-NNNNN</code>). Due date is auto-calculated from company payment terms.
                After creating, open <strong>City Ledger → Invoices</strong> to email it to the client.
              </p>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setCorpInvoiceOpen(false)} className="px-4 py-2 text-sm">Cancel</button>
              <button onClick={createCorpInvoice} data-testid="corp-inv-create" className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-semibold">Create Invoice</button>
            </div>
          </div>
        </div>
      )}

      {/* Quick Pay modal — click flashing balance chip on a booking bar */}
      {quickPay && (
        <QuickPayModal
          booking={quickPay.booking}
          onClose={() => setQuickPay(null)}
          onDone={async () => { setQuickPay(null); await load(); }}
        />
      )}
    </div>
  );
};

// Quick-pay flow triggered from a flashing balance chip in the calendar.
// Pre-fills the full remaining balance. Supports 4 explicit payment types:
// Cash · Card · Bank Transfer · Channel Collection (OTA). For channel collection
// the channel is auto-inferred from the booking source but editable.
const QuickPayModal = ({ booking, onClose, onDone }) => {
  const balance = (booking.balance_due !== undefined && booking.balance_due !== null)
    ? Number(booking.balance_due) : Number(booking.total_price || 0);
  const [amount, setAmount] = useState(balance.toFixed(2));
  const [method, setMethod] = useState("card");
  const [channel, setChannel] = useState(booking.source || "Booking.com");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const paymentTypes = [
    { id: "cash", label: "Cash", icon: Banknote, activeCls: "border-emerald-500 bg-emerald-50 text-emerald-700" },
    { id: "card", label: "Card", icon: CreditCard, activeCls: "border-sky-500 bg-sky-50 text-sky-700" },
    { id: "bank_transfer", label: "Bank Transfer", icon: Landmark, activeCls: "border-violet-500 bg-violet-50 text-violet-700" },
    { id: "channel_collection", label: "Channel Collection", icon: Globe, activeCls: "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700" },
  ];

  const record = async () => {
    const n = parseFloat(amount);
    if (!n || n <= 0) return toast.error("Enter a valid amount");
    if (n > balance + 0.01) {
      if (!window.confirm(`Amount ${cur(n)} exceeds balance ${cur(balance)}. Record as overpayment?`)) return;
    }
    setBusy(true);
    try {
      const body = {
        amount: n,
        method,
        reference: reference.trim(),
        description: note.trim() || undefined,
      };
      if (method === "channel_collection") body.channel = channel.trim() || booking.source || "OTA";
      await axios.post(`${API}/folio/${booking.id}/add-payment`, body);
      const label = paymentTypes.find(p => p.id === method)?.label || method;
      toast.success(`${cur(n)} recorded · ${label}`);
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Payment failed");
    } finally { setBusy(false); }
  };

  const remainingAfter = Math.max(0, balance - (parseFloat(amount) || 0));

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose} data-testid="quickpay-modal">
      <div className="bg-white rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="bg-gradient-to-br from-rose-500 to-pink-600 text-white p-5">
          <div className="text-[11px] font-bold uppercase tracking-wider opacity-80">Take Payment</div>
          <div className="text-xl font-black mt-0.5">{booking.guest_name}</div>
          <div className="text-sm opacity-90 mt-0.5">
            Balance due <span className="font-mono font-bold">{cur(balance)}</span>
            <span className="opacity-70"> · charged {cur(booking.total_price)}</span>
          </div>
        </div>
        <div className="p-5 space-y-4">
          {/* Payment type — segmented 4-up picker */}
          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1.5">Payment Type</label>
            <div className="grid grid-cols-4 gap-2" data-testid="quickpay-type-picker">
              {paymentTypes.map(t => {
                const Icon = t.icon;
                const active = method === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setMethod(t.id)}
                    data-testid={`quickpay-type-${t.id}`}
                    className={`flex flex-col items-center gap-1 px-1 py-2.5 rounded-lg border-2 text-[10px] font-bold transition-all ${
                      active
                        ? `${t.activeCls} shadow-sm`
                        : "border-stone-200 text-stone-500 hover:border-stone-300 hover:bg-stone-50"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="leading-tight text-center">{t.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Channel selector — only for channel_collection */}
          {method === "channel_collection" && (
            <div>
              <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Collected by</label>
              <select value={channel} onChange={e => setChannel(e.target.value)}
                data-testid="quickpay-channel"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm bg-fuchsia-50 border-fuchsia-200">
                <option value="Booking.com">Booking.com</option>
                <option value="Expedia">Expedia</option>
                <option value="Airbnb">Airbnb</option>
                <option value="Agoda">Agoda</option>
                <option value="Hotels.com">Hotels.com</option>
                <option value="Trip.com">Trip.com</option>
                <option value="Vrbo">Vrbo</option>
                <option value="Direct OTA">Direct OTA</option>
              </select>
              <p className="text-[10px] text-stone-400 mt-1">Booking source: <strong>{booking.source || "n/a"}</strong> · for reconciliation reporting</p>
            </div>
          )}

          {/* Quick amount shortcuts */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setAmount(balance.toFixed(2))}
              data-testid="quickpay-full"
              className="flex-1 px-2 py-1.5 rounded-lg border border-stone-200 hover:border-rose-400 text-[11px] font-semibold">
              Full {cur(balance)}
            </button>
            <button
              type="button"
              onClick={() => setAmount((balance / 2).toFixed(2))}
              data-testid="quickpay-half"
              className="flex-1 px-2 py-1.5 rounded-lg border border-stone-200 hover:border-rose-400 text-[11px]">
              50%
            </button>
            <button
              type="button"
              onClick={() => setAmount((balance * 0.3).toFixed(2))}
              className="flex-1 px-2 py-1.5 rounded-lg border border-stone-200 hover:border-rose-400 text-[11px]">
              30% deposit
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Amount</label>
              <input type="number" step="0.01" value={amount} onChange={e => setAmount(e.target.value)}
                data-testid="quickpay-amount"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-mono font-bold" />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">
                {method === "card" ? "Auth / Last-4" : method === "bank_transfer" ? "Transfer ref" : method === "channel_collection" ? "OTA ref" : "Receipt #"}
              </label>
              <input value={reference} onChange={e => setReference(e.target.value)}
                data-testid="quickpay-reference"
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
                placeholder={method === "card" ? "•••• 4242" : method === "bank_transfer" ? "TRF-123" : "optional"} />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Note (optional)</label>
            <input value={note} onChange={e => setNote(e.target.value)}
              data-testid="quickpay-note"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
              placeholder="Internal note" />
          </div>

          {/* Preview after this payment */}
          <div className="rounded-lg bg-stone-900 text-white p-3 flex items-center justify-between text-xs">
            <span className="opacity-70">After this payment</span>
            <span className={`font-mono font-bold ${remainingAfter <= 0 ? "text-emerald-400" : "text-amber-300"}`} data-testid="quickpay-remaining">
              {remainingAfter <= 0 ? "PAID IN FULL" : `${cur(remainingAfter)} remaining`}
            </span>
          </div>
        </div>
        <div className="flex gap-2 p-5 pt-0">
          <button onClick={onClose} disabled={busy}
            data-testid="quickpay-cancel"
            className="flex-1 px-4 py-2.5 rounded-lg border border-stone-200 hover:bg-stone-50 text-sm font-semibold">
            Cancel
          </button>
          <button onClick={record} disabled={busy}
            data-testid="quickpay-record"
            className="flex-1 px-4 py-2.5 rounded-lg bg-gradient-to-br from-rose-600 to-pink-700 hover:from-rose-500 hover:to-pink-600 text-white text-sm font-bold shadow-lg disabled:opacity-60">
            {busy ? "Recording…" : `Record ${cur(parseFloat(amount) || 0)}`}
          </button>
        </div>
      </div>
    </div>
  );
};

// Sub-folio email composition form — user writes To, Subject, Message; PDF auto-attached
const SubFolioEmailForm = ({ defaultTo, sfName, balance, onSend, onCancel }) => {
  const [to, setTo] = useState(defaultTo);
  const [subject, setSubject] = useState(`Your ${sfName} folio`);
  const [message, setMessage] = useState(
    `Dear guest,\n\nPlease find attached your ${sfName} folio.\n\nBalance: £${Number(balance || 0).toFixed(2)}\n\nKindly review and let us know if you have any questions.\n\nThank you for your stay.`,
  );
  const [sending, setSending] = useState(false);

  const submit = async () => {
    if (!to.trim()) return toast.error("Please enter at least one recipient");
    if (!subject.trim() || !message.trim()) return toast.error("Subject and message required");
    setSending(true);
    try { await onSend(to, subject, message.replace(/\n/g, "<br>")); }
    finally { setSending(false); }
  };

  return (
    <div>
      <div className="space-y-3">
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">To *</label>
          <input value={to} onChange={e => setTo(e.target.value)}
            placeholder="guest@example.com"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
            data-testid="sub-folio-email-to" autoFocus />
          <p className="text-[10px] text-stone-400 mt-1">You write the recipient yourself. Comma-separate for multiple.</p>
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Subject *</label>
          <input value={subject} onChange={e => setSubject(e.target.value)}
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm"
            data-testid="sub-folio-email-subject" />
        </div>
        <div>
          <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">Message *</label>
          <textarea value={message} onChange={e => setMessage(e.target.value)} rows={8}
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm font-sans"
            data-testid="sub-folio-email-message" />
        </div>
        <p className="text-[11px] text-stone-500 bg-stone-50 border border-stone-200 rounded-lg p-2 flex items-center gap-1.5">
          <Receipt className="w-3.5 h-3.5" />{sfName} folio PDF will be attached automatically
        </p>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onCancel} className="px-4 py-2 text-sm">Cancel</button>
        <button onClick={submit} disabled={sending} data-testid="sub-folio-email-send"
          className="px-4 py-2 bg-sky-600 hover:bg-sky-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5">
          <Mail className="w-3.5 h-3.5" />{sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
};
