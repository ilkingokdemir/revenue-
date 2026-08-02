import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Bed, ArrowsClockwise, Plus, Trash, PencilSimple, Users,
  CheckCircle, X, Copy, Eye, Lightning, Coffee, WifiHigh,
  Buildings, CreditCard, PaperPlaneTilt,
} from "@phosphor-icons/react";
import { API } from "./config";
import { RoomEditor } from "./RoomEditor";
import { StripeLinkModal } from "./StripeLinkModal";

const BookingEnginePanel = ({ properties }) => {
  const [stripeLinkBooking, setStripeLinkBooking] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("rooms");
  const [editingRoom, setEditingRoom] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [filterProperty, setFilterProperty] = useState("");
  const [calendarDate, setCalendarDate] = useState(new Date());

  const fetchRooms = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/room-types`); setRooms(data); } catch (e) { toast.error("Failed to load room types"); }
  }, []);

  const fetchBookings = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/bookings`); setBookings(data); } catch (e) { toast.error("Failed to load bookings"); }
  }, []);

  useEffect(() => {
    const loadAll = async () => { setIsLoading(true); await Promise.all([fetchRooms(), fetchBookings()]); setIsLoading(false); };
    loadAll();
  }, [fetchRooms, fetchBookings]);

  const handleSaveRoom = async (form) => {
    if (editingRoom) {
      await axios.put(`${API}/room-types/${editingRoom}`, form);
    } else {
      await axios.post(`${API}/room-types`, form);
    }
    setShowEditor(false);
    setEditingRoom(null);
    await fetchRooms();
  };

  const handleDeleteRoom = async (roomId) => {
    if (!window.confirm("Delete this room type?")) return;
    try { await axios.delete(`${API}/room-types/${roomId}`); toast.success("Room deleted"); await fetchRooms(); }
    catch (e) { toast.error("Failed to delete"); }
  };

  const handleUpdateBookingStatus = async (bookingId, status) => {
    try { await axios.put(`${API}/bookings/${bookingId}/status?status=${status}`); toast.success(`Booking ${status}`); await fetchBookings(); }
    catch (e) { toast.error("Failed to update"); }
  };

  const handleSendPaymentLink = async (booking) => {
    try {
      const { data } = await axios.post(`${API}/guest-payment/send-link`, {
        booking_id: booking.id, extra_charges: [], notes: "",
      });
      toast.success(`Payment link sent to ${booking.guest_email}`);
      const link = data.url;
      if (link) navigator.clipboard?.writeText(link);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to send payment link");
    }
  };

  const startEdit = (room) => {
    setEditingRoom(room.id);
    setShowEditor(true);
  };

  const startCreate = () => {
    setEditingRoom(null);
    setShowEditor(true);
  };

  const filteredRooms = filterProperty ? rooms.filter(r => r.property_id === filterProperty) : rooms;
  const filteredBookings = filterProperty ? bookings.filter(b => b.property_id === filterProperty) : bookings;
  const bookingUrl = `${window.location.origin}/book?property=${filterProperty || properties?.[0]?.id || "aldgate-flats"}`;

  const statusColors = {
    confirmed: "bg-emerald-50 text-emerald-700 border-emerald-200",
    cancelled: "bg-red-50 text-red-700 border-red-200",
    checked_in: "bg-blue-50 text-blue-700 border-blue-200",
    checked_out: "bg-stone-50 text-stone-700 border-stone-200",
    no_show: "bg-amber-50 text-amber-700 border-amber-200",
  };

  return (
    <div className="p-5" data-testid="booking-engine-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="booking-engine-title">Rooms & Bookings</h2>
          <p className="text-sm text-stone-500 mt-0.5">Manage room inventory and view reservations</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={filterProperty} onChange={e => setFilterProperty(e.target.value)}
            className="text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white text-stone-700" data-testid="booking-property-filter">
            <option value="">All Properties</option>
            {properties?.filter(p => p.id !== "default").map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </div>

      {/* Booking Link */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 mb-5 flex items-center gap-3" data-testid="booking-url-bar">
        <div className="flex-1">
          <p className="text-xs font-medium text-emerald-800">Booking Page URL</p>
          <p className="text-xs text-emerald-600 font-mono mt-0.5 truncate">{bookingUrl}</p>
        </div>
        <button onClick={() => { navigator.clipboard.writeText(bookingUrl); toast.success("URL copied!"); }}
          className="flex items-center gap-1 px-2.5 py-1.5 bg-emerald-700 text-white text-xs rounded-lg hover:bg-emerald-800" data-testid="copy-booking-url-btn">
          <Copy size={12} /> Copy
        </button>
        <a href={bookingUrl} target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-1 px-2.5 py-1.5 bg-white border border-emerald-300 text-emerald-700 text-xs rounded-lg hover:bg-emerald-50" data-testid="preview-booking-btn">
          <Eye size={12} /> Preview
        </a>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-stone-100 rounded-lg p-1 mb-5">
        {[
          { id: "rooms", label: `Rooms (${filteredRooms.length})`, icon: Bed },
          { id: "calendar", label: "Calendar", icon: Eye },
          { id: "bookings", label: `Bookings (${filteredBookings.length})`, icon: CreditCard },
        ].map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-md transition-colors flex-1 justify-center ${
              activeTab === tab.id ? "bg-white text-stone-800 shadow-sm" : "text-stone-500 hover:text-stone-700"
            }`} data-testid={`tab-${tab.id}`}>
            <tab.icon size={14} /> {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : (
        <>
          {/* ROOMS TAB */}
          {activeTab === "rooms" && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <p className="text-xs text-stone-500">{filteredRooms.length} room type{filteredRooms.length !== 1 ? "s" : ""}</p>
                <button onClick={startCreate}
                  className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800"
                  data-testid="create-room-btn">
                  <Plus size={13} /> New Room Type
                </button>
              </div>

              {/* Room Editor */}
              {showEditor && (
                <div className="mb-5">
                  <RoomEditor
                    room={editingRoom ? rooms.find(r => r.id === editingRoom) : { property_id: filterProperty || properties?.filter(p => p.id !== "default")[0]?.id || "" }}
                    onSave={handleSaveRoom}
                    onCancel={() => { setShowEditor(false); setEditingRoom(null); }}
                  />
                </div>
              )}

              {/* Room List */}
              <div className="space-y-3">
                {filteredRooms.map(room => (
                  <div key={room.id} className="bg-white border border-stone-200 rounded-lg p-4" data-testid={`room-row-${room.id}`}>
                    <div className="flex items-start gap-4">
                      {/* Photo thumbnail */}
                      <div className="w-20 h-16 rounded-lg bg-stone-200 overflow-hidden flex-shrink-0">
                        {room.photos?.[0] ? (
                          <img src={room.photos[0]} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center"><Bed size={20} className="text-stone-300" /></div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-semibold text-stone-800 text-sm">{room.name}</span>
                          <span className="text-[10px] bg-stone-100 text-stone-500 px-1.5 py-0.5 rounded">{room.property_id}</span>
                          {room.photos?.length > 0 && <span className="text-[10px] text-stone-400">{room.photos.length} photos</span>}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-stone-500">
                          <span className="flex items-center gap-1"><Users size={12} /> {room.max_guests} guests</span>
                          <span className="flex items-center gap-1"><Bed size={12} /> {room.bed_type}</span>
                          {room.size_sqm > 0 && <span>{room.size_sqm} m²</span>}
                          <span>{room.total_rooms} room{room.total_rooms > 1 ? "s" : ""}</span>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {room.amenities?.slice(0, 5).map(a => (
                            <span key={a} className="text-[10px] bg-stone-50 text-stone-500 px-1.5 py-0.5 rounded">{a}</span>
                          ))}
                          {room.amenities?.length > 5 && <span className="text-[10px] text-stone-400">+{room.amenities.length - 5} more</span>}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-lg font-bold text-stone-800">£{room.base_price}</div>
                        <div className="text-[10px] text-stone-400">per night</div>
                        <div className="flex gap-1 mt-2">
                          {room.free_cancellation && <span className="text-[9px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">Free cancel</span>}
                          {room.breakfast_included && <span className="text-[9px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">Breakfast</span>}
                        </div>
                      </div>
                      <div className="flex gap-1 flex-shrink-0">
                        <button onClick={() => startEdit(room)} className="p-2 text-stone-400 hover:text-emerald-600 rounded-lg hover:bg-emerald-50" data-testid={`edit-room-${room.id}`}>
                          <PencilSimple size={16} />
                        </button>
                        <button onClick={() => handleDeleteRoom(room.id)} className="p-2 text-stone-400 hover:text-red-600 rounded-lg hover:bg-red-50" data-testid={`delete-room-${room.id}`}>
                          <Trash size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CALENDAR TAB */}
          {activeTab === "calendar" && (
            <div data-testid="calendar-view">
              {/* Calendar Navigation */}
              <div className="flex items-center justify-between mb-4">
                <button onClick={() => { const d = new Date(calendarDate); d.setMonth(d.getMonth() - 1); setCalendarDate(d); }}
                  className="text-xs px-3 py-1.5 bg-white border border-stone-200 rounded-lg hover:bg-stone-50">Previous</button>
                <h3 className="text-sm font-bold text-stone-800">
                  {calendarDate.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}
                </h3>
                <button onClick={() => { const d = new Date(calendarDate); d.setMonth(d.getMonth() + 1); setCalendarDate(d); }}
                  className="text-xs px-3 py-1.5 bg-white border border-stone-200 rounded-lg hover:bg-stone-50">Next</button>
              </div>
              {/* Calendar Grid */}
              <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
                {/* Day Headers */}
                <div className="grid grid-cols-7 border-b border-stone-100">
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => (
                    <div key={d} className="text-center py-2 text-[10px] font-bold text-stone-500 uppercase tracking-wider">{d}</div>
                  ))}
                </div>
                {/* Days */}
                <div className="grid grid-cols-7">
                  {(() => {
                    const year = calendarDate.getFullYear();
                    const month = calendarDate.getMonth();
                    const firstDay = new Date(year, month, 1);
                    const lastDay = new Date(year, month + 1, 0);
                    const startPad = (firstDay.getDay() + 6) % 7;
                    const days = [];
                    for (let i = 0; i < startPad; i++) days.push(null);
                    for (let d = 1; d <= lastDay.getDate(); d++) days.push(d);
                    const today = new Date();
                    return days.map((day, i) => {
                      if (!day) return <div key={i} className="h-20 border-b border-r border-stone-50" />;
                      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                      const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
                      const dayBookings = filteredBookings.filter(b => b.check_in <= dateStr && b.check_out > dateStr);
                      const checkIns = filteredBookings.filter(b => b.check_in === dateStr);
                      const checkOuts = filteredBookings.filter(b => b.check_out === dateStr);
                      return (
                        <div key={i} className={`h-20 border-b border-r border-stone-50 p-1 ${isToday ? "bg-blue-50" : ""}`}>
                          <div className={`text-[10px] font-bold ${isToday ? "text-blue-600" : "text-stone-600"}`}>{day}</div>
                          {checkIns.length > 0 && <div className="text-[8px] px-1 py-0.5 bg-emerald-100 text-emerald-700 rounded mt-0.5 truncate font-semibold">{checkIns.length} check-in{checkIns.length > 1 ? "s" : ""}</div>}
                          {checkOuts.length > 0 && <div className="text-[8px] px-1 py-0.5 bg-amber-100 text-amber-700 rounded mt-0.5 truncate font-semibold">{checkOuts.length} check-out{checkOuts.length > 1 ? "s" : ""}</div>}
                          {dayBookings.length > 0 && checkIns.length === 0 && checkOuts.length === 0 && (
                            <div className="text-[8px] px-1 py-0.5 bg-blue-50 text-blue-600 rounded mt-0.5 truncate">{dayBookings.length} staying</div>
                          )}
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>
              {/* Legend */}
              <div className="flex gap-4 mt-3 text-[10px] text-stone-500">
                <span className="flex items-center gap-1"><div className="w-3 h-2 bg-emerald-100 rounded" /> Check-ins</span>
                <span className="flex items-center gap-1"><div className="w-3 h-2 bg-amber-100 rounded" /> Check-outs</span>
                <span className="flex items-center gap-1"><div className="w-3 h-2 bg-blue-50 rounded" /> Staying</span>
              </div>
            </div>
          )}

          {/* BOOKINGS LIST TAB */}
          {activeTab === "bookings" && (
            <div className="space-y-2">
              {filteredBookings.length === 0 ? (
                <div className="text-center py-12 bg-white border border-stone-200 rounded-lg">
                  <CreditCard size={36} className="mx-auto text-stone-300 mb-2" />
                  <p className="text-sm text-stone-500">No bookings yet</p>
                </div>
              ) : (
                filteredBookings.map(booking => (
                  <div key={booking.id} className="bg-white border border-stone-200 rounded-lg p-4" data-testid={`booking-row-${booking.booking_ref}`}>
                    <div className="flex items-center gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono font-bold text-sm text-stone-800">{booking.booking_ref}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${statusColors[booking.status] || "bg-stone-50"}`}>{booking.status}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium ${booking.payment_status === "paid" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                            {booking.payment_status}
                          </span>
                        </div>
                        <div className="text-xs text-stone-600">
                          <span className="font-medium">{booking.guest_name}</span>
                          <span className="text-stone-400 mx-1">·</span>
                          <span>{new Date(booking.check_in).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(booking.check_out).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
                          <span className="text-stone-400 mx-1">·</span>
                          <span>{booking.adults} adult{booking.adults > 1 ? "s" : ""}{booking.children > 0 ? `, ${booking.children} child` : ""}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-stone-800">£{booking.total_price?.toFixed(0)}</div>
                        <div className="text-[10px] text-stone-400">{booking.property_id}</div>
                      </div>
                      {booking.status === "confirmed" && (
                        <div className="flex gap-1">
                          {booking.payment_status !== "paid" && (
                            <button onClick={() => handleSendPaymentLink(booking)}
                              className="px-2 py-1 bg-green-50 text-green-700 text-[10px] rounded font-medium hover:bg-green-100 flex items-center gap-0.5" data-testid={`send-payment-${booking.booking_ref}`}>
                              <PaperPlaneTilt size={10} weight="bold" /> Pay Link
                            </button>
                          )}
                          {booking.payment_status !== "paid" && (
                            <button onClick={() => setStripeLinkBooking(booking)}
                              className="px-2 py-1 bg-indigo-50 text-indigo-700 text-[10px] rounded font-medium hover:bg-indigo-100 flex items-center gap-0.5" data-testid={`stripe-link-${booking.booking_ref}`}>
                              <CreditCard size={10} weight="bold" /> Stripe Link
                            </button>
                          )}
                          <button onClick={() => handleUpdateBookingStatus(booking.id, "checked_in")}
                            className="px-2 py-1 bg-blue-50 text-blue-700 text-[10px] rounded font-medium hover:bg-blue-100" data-testid={`checkin-${booking.booking_ref}`}>
                            Check In
                          </button>
                          <button onClick={() => handleUpdateBookingStatus(booking.id, "cancelled")}
                            className="px-2 py-1 bg-red-50 text-red-700 text-[10px] rounded font-medium hover:bg-red-100" data-testid={`cancel-${booking.booking_ref}`}>
                            Cancel
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
      {stripeLinkBooking && (
        <StripeLinkModal booking={stripeLinkBooking} onClose={() => { setStripeLinkBooking(null); fetchBookings(); }} />
      )}
    </div>
  );
};

export { BookingEnginePanel };
