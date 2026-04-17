import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CalendarDays,
  Search, Plus, X, User, Phone, Mail, CreditCard, Bed, Clock, MapPin
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

  const openDetail = async (bookingId) => {
    setSelectedBooking(bookingId);
    try {
      const { data: d } = await axios.get(`${API}/bookings/timeline/${pid}/detail/${bookingId}`);
      setDetailData(d);
    } catch { /* silent */ }
  };

  const changeStatus = async (bookingId, newStatus) => {
    try {
      await axios.put(`${API}/bookings/timeline/${pid}/status/${bookingId}`, { status: newStatus });
      load();
      if (detailData && detailData.id === bookingId) {
        setDetailData({ ...detailData, status: newStatus });
      }
    } catch { /* silent */ }
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
  const ROW_H = 40;
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
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-2" />
            <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Search guest, ID..."
              className="pl-8 pr-3 py-1.5 text-xs border border-stone-200 rounded-lg w-48 focus:outline-none focus:ring-1 focus:ring-blue-300" data-testid="timeline-search" />
          </div>
        </div>
      </div>

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
        <div className="flex items-center gap-3 text-[10px]">
          {Object.entries(STATUS_COLORS).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1"><span className={`w-3 h-2 rounded-sm ${v.bar}`} />{v.label}</span>
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
                  <div key={room.id} className="flex border-b border-stone-100 relative" style={{ height: ROW_H }} data-testid={`timeline-room-${room.id}`}>
                    {/* Room Label */}
                    <div className="flex-shrink-0 flex items-center px-3 gap-2 sticky left-0 bg-white z-10 border-r border-stone-200" style={{ width: ROOM_LABEL_W }}>
                      <span className={`w-2 h-2 rounded-full ${HK_COLORS[room.housekeeping] || "bg-stone-300"}`} title={room.housekeeping} />
                      <span className="text-[11px] text-stone-600 truncate">{room.name}</span>
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

                        return (
                          <button key={bk.id} onClick={() => openDetail(bk.id)} data-testid={`booking-bar-${bk.id}`}
                            className={`absolute top-1 rounded-md ${sc.bar} ${sc.text} ${sc.border} border cursor-pointer hover:brightness-110 transition-all overflow-hidden flex items-center px-1.5 gap-1 shadow-sm`}
                            style={{ left: left + 2, width, height: ROW_H - 8 }}
                            title={`${bk.guest_name} | ${bk.check_in} → ${bk.check_out} | ${bk.status} | ${cur(bk.total_price)}`}>
                            <span className="text-[10px] font-bold truncate">{bk.guest_name}</span>
                            {width > 140 && <span className="text-[9px] opacity-70">{bk.source_code}</span>}
                            {width > 180 && <span className="text-[9px] opacity-70">{cur(bk.total_price)}</span>}
                            {width > 220 && <span className="text-[9px] opacity-70">{bk.nights}n</span>}
                          </button>
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

              {/* Financial */}
              <div className="bg-stone-50 rounded-xl p-4 space-y-2">
                <p className="text-[9px] text-stone-400 uppercase font-bold">Folio</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Rate/night</span>
                  <span className="text-sm font-bold">{cur(detailData.rate_per_night)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Total ({detailData.nights || 1} night{(detailData.nights || 1) > 1 ? "s" : ""})</span>
                  <span className="text-sm font-bold">{cur(detailData.total_price)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Payment</span>
                  <Badge className={`text-[10px] ${detailData.payment_status === "paid" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{detailData.payment_status || "pending"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-stone-500">Source</span>
                  <span className="text-xs font-medium">{detailData.source} ({detailData.source_code})</span>
                </div>
              </div>

              {/* Quick Actions */}
              <div>
                <p className="text-[9px] text-stone-400 uppercase font-bold mb-2">Quick Actions</p>
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

              {/* Timestamps */}
              <div className="text-[10px] text-stone-400 space-y-1 border-t border-stone-100 pt-3">
                {detailData.created_at && <p>Booked: {new Date(detailData.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</p>}
                <p>ID: {detailData.id}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
