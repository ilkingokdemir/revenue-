import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CalendarDays,
  Search, Plus, X, User, Phone, Mail, CreditCard, Bed, Clock, MapPin,
  GripVertical, CheckSquare, Square, LogIn, LogOut, Users, AlertTriangle,
  FileText, Send, Receipt
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const STATUS_COLORS = {
  pending: { bar: "bg-amber-400", text: "text-amber-900", border: "border-amber-500", label: "Pending" },
  confirmed: { bar: "bg-blue-400", text: "text-blue-900", border: "border-blue-500", label: "Confirmed" },
  checked_in: { bar: "bg-emerald-500", text: "text-white", border: "border-emerald-600", label: "Checked In" },
  checked_out: { bar: "bg-stone-400", text: "text-stone-900", border: "border-stone-500", label: "Checked Out" },
  no_show: { bar: "bg-red-400", text: "text-red-900", border: "border-red-500", label: "No Show" },
};

const HK_COLORS = { clean: "bg-emerald-400", dirty: "bg-red-400", inspected: "bg-blue-400" };

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
// Special icons for non-OTA sources (no domain)
const NON_OTA = {
  "direct":         { bg: "#1F2937", emoji: "⌂", label: "Direct" },
  "website":        { bg: "#0EA5E9", emoji: "🌐", label: "Website" },
  "website_widget": { bg: "#0EA5E9", emoji: "🌐", label: "Website Widget" },
  "walk_in":        { bg: "#78716C", emoji: "👤", label: "Walk-in" },
  "walk-in":        { bg: "#78716C", emoji: "👤", label: "Walk-in" },
  "phone":          { bg: "#10B981", emoji: "☎", label: "Phone" },
  "affiliate":      { bg: "#8B5CF6", emoji: "⚯", label: "Affiliate" },
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
    return (
      <span
        className="inline-flex items-center justify-center rounded-full flex-shrink-0 leading-none"
        style={{ width: size, height: size, backgroundColor: non.bg, fontSize: size * 0.6, color: "white" }}
        title={non.label}
      >{non.emoji}</span>
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
  const [detailData, setDetailData] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [dragBooking, setDragBooking] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkMode, setBulkMode] = useState(false);
  const [todaysActions, setTodaysActions] = useState(null);
  const [showBulkPanel, setShowBulkPanel] = useState(false);
  const [folio, setFolio] = useState(null);
  const [showAddCharge, setShowAddCharge] = useState(false);
  const [detailTab, setDetailTab] = useState("info");
  const [upsells, setUpsells] = useState(null);
  const scrollRef = useRef(null);

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

  useEffect(() => { loadTodaysActions(); }, [pid]);

  const openDetail = async (bookingId) => {
    setSelectedBooking(bookingId);
    setDetailTab("info");
    setFolio(null);
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
  };

  const addCharge = async (desc, amount, category) => {
    if (!selectedBooking) return;
    try {
      await axios.post(`${API}/folio/${selectedBooking}/add-charge`, { description: desc, unit_price: parseFloat(amount), quantity: 1, category });
      toast.success("Charge added");
      loadFolio(selectedBooking);
      setShowAddCharge(false);
    } catch { toast.error("Failed"); }
  };

  const addPayment = async (amount, method) => {
    if (!selectedBooking) return;
    try {
      await axios.post(`${API}/folio/${selectedBooking}/add-payment`, { amount: parseFloat(amount), method });
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
        toast.success(`${dragBooking.guest_name} moved to ${res.new_room_name}`);
        load();
      }
    } catch { toast.error("Failed to reassign room"); }
    setDragBooking(null);
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
    if (!searchTerm) return true;
    const s = searchTerm.toLowerCase();
    return b.guest_name?.toLowerCase().includes(s) || b.source?.toLowerCase().includes(s) || b.id?.toLowerCase().includes(s);
  };

  return (
    <div className="h-full flex flex-col" data-testid="booking-timeline">
      {/* Header */}
      <div className="bg-white border-b border-stone-200 px-5 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-stone-700" />
          <h2 className="text-base font-bold text-stone-800" data-testid="timeline-title">Booking Calendar</h2>
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
          <button onClick={() => { setBulkMode(!bulkMode); setSelectedIds(new Set()); setShowBulkPanel(!showBulkPanel); }} data-testid="bulk-mode-btn"
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition-all ${bulkMode ? "bg-violet-500 text-white border-violet-600" : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"}`}>
            <CheckSquare className="w-3.5 h-3.5" />{bulkMode ? "Exit Bulk" : "Bulk Actions"}
          </button>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-2" />
            <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Search guest, ID..."
              className="pl-8 pr-3 py-1.5 text-xs border border-stone-200 rounded-lg w-48 focus:outline-none focus:ring-1 focus:ring-blue-300" data-testid="timeline-search" />
          </div>
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

      {/* Navigation Bar */}
      <div className="bg-stone-50 border-b border-stone-200 px-5 py-2 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1.5 hover:bg-stone-200 rounded-lg" data-testid="timeline-prev"><ChevronLeft className="w-4 h-4" /></button>
          <button onClick={goToday} className="px-3 py-1 text-xs font-semibold bg-white border border-stone-200 rounded-lg hover:bg-stone-100" data-testid="timeline-today">Today</button>
          <button onClick={() => navigate(1)} className="p-1.5 hover:bg-stone-200 rounded-lg" data-testid="timeline-next"><ChevronRight className="w-4 h-4" /></button>
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="text-xs border border-stone-200 rounded-lg px-2 py-1" data-testid="timeline-date-pick" />
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
        <div className="inline-block min-w-full">
          {/* Date Header */}
          <div className="flex sticky top-0 z-20 bg-white border-b border-stone-200">
            <div className="flex-shrink-0 bg-white border-r border-stone-200 z-30 sticky left-0" style={{ width: ROOM_LABEL_W }}>
              <div className="h-12 flex items-center px-3 text-[10px] text-stone-500 uppercase font-bold">Rooms</div>
            </div>
            {date_columns.map((col, i) => {
              const occ = daily_occupancy[i];
              return (
                <div key={col.date} className={`flex-shrink-0 border-r border-stone-100 text-center ${col.is_today ? "bg-blue-50" : col.is_weekend ? "bg-stone-50" : "bg-white"}`} style={{ width: COL_W }}>
                  <div className="h-12 flex flex-col items-center justify-center">
                    <span className="text-[9px] text-stone-400 uppercase">{col.dow}</span>
                    <span className={`text-sm ${col.is_today ? "text-red-600 font-black" : "font-bold text-stone-700"}`}>{col.day}/{col.month}</span>
                    <span className={`text-[9px] ${getOccColor(occ?.occupancy_pct || 0)}`}>{occ?.occupancy_pct || 0}%</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Room Type Groups */}
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
                      <div key={col.date} className={`flex-shrink-0 border-r border-stone-200/50 flex flex-col items-center justify-center ${col.is_today ? "bg-blue-50/50" : ""}`} style={{ width: COL_W, height: ROW_H }}>
                        <span className="text-[10px] font-bold text-stone-600">{avail}/{group.total_rooms}</span>
                        <span className="text-[9px] text-stone-400">{cur(group.rate)}</span>
                      </div>
                    );
                  })}
                </div>

                {/* Room Rows */}
                {!isCollapsed && group.rooms.map(room => (
                  <div key={room.id} className={`flex border-b border-stone-100 relative transition-all ${dropTarget === room.id ? "bg-violet-100 ring-2 ring-violet-400 ring-inset" : ""}`}
                    style={{ height: ROW_H }} data-testid={`timeline-room-${room.id}`}
                    onDragOver={(e) => handleDragOver(e, room.id)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, room.id)}>
                    {/* Room Label */}
                    <div className="flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 bg-white z-10 border-r border-stone-200" style={{ width: ROOM_LABEL_W }}>
                      <span className={`w-2 h-2 rounded-full ${HK_COLORS[room.housekeeping] || "bg-stone-300"}`} title={room.housekeeping} />
                      <span className="text-[11px] text-stone-600 truncate">{room.name}</span>
                      {dropTarget === room.id && dragBooking && <span className="text-[9px] text-violet-500 font-bold ml-auto">Drop here</span>}
                    </div>

                    {/* Date cells */}
                    <div className="relative flex" style={{ height: ROW_H }}>
                      {date_columns.map(col => (
                        <div key={col.date} className={`flex-shrink-0 border-r border-stone-50 ${col.is_today ? "bg-blue-50/30" : col.is_weekend ? "bg-stone-50/30" : ""}`} style={{ width: COL_W, height: ROW_H }} />
                      ))}

                      {/* Booking Bars */}
                      {room.bookings.filter(matchSearch).map(bk => {
                        const startIdx = date_columns.findIndex(c => c.date >= bk.check_in);
                        const endIdx = date_columns.findIndex(c => c.date >= bk.check_out);
                        const si = startIdx >= 0 ? startIdx : 0;
                        const ei = endIdx >= 0 ? endIdx : date_columns.length;
                        const left = si * COL_W;
                        const width = Math.max((ei - si) * COL_W - 4, COL_W * 0.5);
                        const sc = STATUS_COLORS[bk.status] || STATUS_COLORS.confirmed;
                        const isSelected = selectedIds.has(bk.id);

                        return (
                          <div key={bk.id} className="absolute top-1" style={{ left: left + 2, width, height: ROW_H - 8 }}>
                            {bulkMode && (
                              <button onClick={(e) => { e.stopPropagation(); toggleSelect(bk.id); }} data-testid={`select-${bk.id}`}
                                className="absolute -left-0.5 top-0.5 z-10 w-4 h-4 flex items-center justify-center">
                                {isSelected ? <CheckSquare className="w-3.5 h-3.5 text-violet-600" /> : <Square className="w-3.5 h-3.5 text-stone-400" />}
                              </button>
                            )}
                            {(() => {
                              const src = bk.source || bk.source_code || "";
                              return (
                                <button
                                  draggable={!bulkMode}
                                  onDragStart={(e) => handleDragStart(e, { ...bk, room_id: room.id })}
                                  onClick={() => bulkMode ? toggleSelect(bk.id) : openDetail(bk.id)}
                                  data-testid={`booking-bar-${bk.id}`}
                                  className={`w-full h-full rounded-md ${sc.bar} ${sc.text} ${sc.border} border cursor-pointer hover:brightness-110 transition-all overflow-hidden flex flex-col justify-center px-1.5 shadow-sm ${isSelected ? "ring-2 ring-violet-500 ring-offset-1" : ""} ${dragBooking?.id === bk.id ? "opacity-50" : ""}`}
                                  title={`${bk.guest_name} | ${src} | ${cur(bk.total_price)} | ${bk.check_in} → ${bk.check_out} | ${bk.status}`}>
                                  {/* Line 1: platform logo + guest name */}
                                  <div className="flex items-center gap-1 min-w-0">
                                    <span data-testid={`platform-badge-${bk.id}`}><PlatformLogo source={src} size={16} /></span>
                                    <span className="text-[11px] font-bold truncate flex-1" data-testid={`guest-name-${bk.id}`}>{bk.guest_name}</span>
                                  </div>
                                  {/* Line 2: price + nights */}
                                  <div className="flex items-center justify-between gap-1 mt-0.5 min-w-0 opacity-90">
                                    <span className="text-[10px] font-bold font-mono truncate" data-testid={`price-${bk.id}`}>{cur(bk.total_price)}</span>
                                    {width > 110 && <span className="text-[9px] opacity-80 flex-shrink-0">{bk.nights}n</span>}
                                  </div>
                                </button>
                              );
                            })()}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

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
                    <button onClick={() => setShowAddCharge(true)} data-testid="add-charge-btn" className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-semibold text-stone-600 bg-stone-100 rounded-lg hover:bg-stone-200">
                      <Plus className="w-3 h-3" />Add Charge
                    </button>
                  </div>

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

                  {/* Items List */}
                  <div className="space-y-1">
                    {folio.items.map(item => (
                      <div key={item.id} className={`flex items-center justify-between py-2 px-3 rounded-lg text-xs ${item.type === "payment" ? "bg-emerald-50" : item.type === "adjustment" ? "bg-amber-50" : "bg-white border border-stone-100"}`}>
                        <div>
                          <p className="font-medium text-stone-700">{item.description}</p>
                          <p className="text-[10px] text-stone-400">{item.category} {item.quantity > 1 ? `x${item.quantity}` : ""}</p>
                        </div>
                        <span className={`font-bold ${item.type === "payment" ? "text-emerald-600" : item.type === "adjustment" ? "text-amber-600" : "text-stone-800"}`}>
                          {item.type === "payment" ? "-" : ""}{cur(item.amount)}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Totals */}
                  <div className="bg-stone-800 rounded-xl p-4 space-y-2 text-white" data-testid="folio-totals">
                    <div className="flex justify-between text-xs"><span className="text-stone-400">Charges</span><span>{cur(folio.totals.charges)}</span></div>
                    {folio.totals.payments > 0 && <div className="flex justify-between text-xs"><span className="text-stone-400">Payments</span><span className="text-emerald-400">-{cur(folio.totals.payments)}</span></div>}
                    {folio.totals.adjustments !== 0 && <div className="flex justify-between text-xs"><span className="text-stone-400">Adjustments</span><span className="text-amber-400">{cur(folio.totals.adjustments)}</span></div>}
                    <div className="h-px bg-stone-700" />
                    <div className="flex justify-between text-sm font-bold"><span>Balance Due</span><span className={folio.totals.balance_due <= 0 ? "text-emerald-400" : "text-red-400"}>{cur(folio.totals.balance_due)}</span></div>
                  </div>

                  {/* Quick Payment */}
                  {folio.totals.balance_due > 0 && (
                    <button onClick={() => addPayment(folio.totals.balance_due, "card")} data-testid="record-payment-btn"
                      className="w-full py-2.5 text-xs font-bold text-white bg-emerald-500 hover:bg-emerald-600 rounded-lg flex items-center justify-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5" />Record Full Payment ({cur(folio.totals.balance_due)})
                    </button>
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
                  </div>
                </div>
              </div>
              </>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
