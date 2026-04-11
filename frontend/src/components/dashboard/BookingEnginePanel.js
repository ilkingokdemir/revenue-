import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Bed,
  ArrowsClockwise,
  Plus,
  Trash,
  PencilSimple,
  Users,
  CheckCircle,
  X,
  Copy,
  Eye,
  Lightning,
  Coffee,
  WifiHigh,
  Snowflake,
  Television,
  Buildings,
  CreditCard,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { API } from "./config";

const BookingEnginePanel = ({ properties }) => {
  const [rooms, setRooms] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("rooms"); // rooms, bookings, settings
  const [editingRoom, setEditingRoom] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [roomForm, setRoomForm] = useState({
    property_id: "",
    name: "",
    description: "",
    max_guests: 2,
    bed_type: "double",
    size_sqm: 0,
    amenities: [],
    photos: [],
    base_price: 0,
    currency: "GBP",
    total_rooms: 1,
    free_cancellation: true,
    breakfast_included: false,
  });
  const [amenityInput, setAmenityInput] = useState("");
  const [photoInput, setPhotoInput] = useState("");

  const fetchRooms = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/room-types`);
      setRooms(data);
    } catch (e) {
      toast.error("Failed to load room types");
    }
  }, []);

  const fetchBookings = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/bookings`);
      setBookings(data);
    } catch (e) {
      toast.error("Failed to load bookings");
    }
  }, []);

  useEffect(() => {
    const loadAll = async () => {
      setIsLoading(true);
      await Promise.all([fetchRooms(), fetchBookings()]);
      setIsLoading(false);
    };
    loadAll();
  }, [fetchRooms, fetchBookings]);

  const handleSaveRoom = async () => {
    if (!roomForm.name || !roomForm.property_id) {
      toast.error("Room name and property are required");
      return;
    }
    try {
      if (editingRoom) {
        await axios.put(`${API}/room-types/${editingRoom}`, roomForm);
        toast.success("Room type updated!");
      } else {
        await axios.post(`${API}/room-types`, roomForm);
        toast.success("Room type created!");
      }
      setShowCreateForm(false);
      setEditingRoom(null);
      resetForm();
      await fetchRooms();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to save room type");
    }
  };

  const handleDeleteRoom = async (roomId) => {
    if (!window.confirm("Are you sure you want to delete this room type?")) return;
    try {
      await axios.delete(`${API}/room-types/${roomId}`);
      toast.success("Room type deleted");
      await fetchRooms();
    } catch (e) {
      toast.error("Failed to delete room type");
    }
  };

  const handleUpdateBookingStatus = async (bookingId, status) => {
    try {
      await axios.put(`${API}/bookings/${bookingId}/status?status=${status}`);
      toast.success(`Booking ${status}`);
      await fetchBookings();
    } catch (e) {
      toast.error("Failed to update booking");
    }
  };

  const resetForm = () => {
    setRoomForm({
      property_id: properties?.[0]?.id || "",
      name: "",
      description: "",
      max_guests: 2,
      bed_type: "double",
      size_sqm: 0,
      amenities: [],
      photos: [],
      base_price: 0,
      currency: "GBP",
      total_rooms: 1,
      free_cancellation: true,
      breakfast_included: false,
    });
  };

  const startEdit = (room) => {
    setEditingRoom(room.id);
    setRoomForm({
      property_id: room.property_id,
      name: room.name,
      description: room.description || "",
      max_guests: room.max_guests || 2,
      bed_type: room.bed_type || "double",
      size_sqm: room.size_sqm || 0,
      amenities: room.amenities || [],
      photos: room.photos || [],
      base_price: room.base_price || 0,
      currency: room.currency || "GBP",
      total_rooms: room.total_rooms || 1,
      free_cancellation: room.free_cancellation ?? true,
      breakfast_included: room.breakfast_included ?? false,
    });
    setShowCreateForm(true);
  };

  const addAmenity = () => {
    if (amenityInput.trim() && !roomForm.amenities.includes(amenityInput.trim())) {
      setRoomForm(p => ({ ...p, amenities: [...p.amenities, amenityInput.trim()] }));
      setAmenityInput("");
    }
  };

  const addPhoto = () => {
    if (photoInput.trim()) {
      setRoomForm(p => ({ ...p, photos: [...p.photos, photoInput.trim()] }));
      setPhotoInput("");
    }
  };

  const bookingUrl = `${window.location.origin}/book?property=${properties?.[0]?.id || "aldgate-flats"}`;

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
          <h2 className="text-lg font-semibold text-stone-800" data-testid="booking-engine-title">Booking Engine</h2>
          <p className="text-sm text-stone-500 mt-0.5">Manage room types, view bookings, and configure your booking engine</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              navigator.clipboard.writeText(bookingUrl);
              toast.success("Booking URL copied!");
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-stone-200 rounded-lg text-xs text-stone-600 hover:bg-stone-50"
            data-testid="copy-booking-url"
          >
            <Copy size={13} />
            Copy Booking URL
          </button>
          <a
            href={bookingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#006CE4] text-white rounded-lg text-xs font-medium hover:bg-[#0056B3]"
            data-testid="preview-booking-engine"
          >
            <Eye size={13} />
            Preview
          </a>
        </div>
      </div>

      {/* Booking URL Display */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-5">
        <div className="flex items-center gap-2">
          <Lightning size={16} className="text-blue-600" />
          <span className="text-xs font-medium text-blue-800">Your booking engine is live at:</span>
        </div>
        <code className="text-xs text-blue-700 mt-1 block font-mono break-all" data-testid="booking-url-display">{bookingUrl}</code>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-stone-200 mb-5">
        {[
          { id: "rooms", label: "Room Types", count: rooms.length },
          { id: "bookings", label: "Bookings", count: bookings.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-emerald-600 text-emerald-700"
                : "border-transparent text-stone-500 hover:text-stone-700"
            }`}
            data-testid={`tab-${tab.id}`}
          >
            {tab.label}
            <span className="ml-1.5 text-[10px] bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded-full">{tab.count}</span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : activeTab === "rooms" ? (
        <>
          <div className="flex justify-end mb-4">
            <button
              onClick={() => { resetForm(); setShowCreateForm(true); setEditingRoom(null); }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 text-white rounded-lg text-xs font-medium hover:bg-emerald-800"
              data-testid="create-room-btn"
            >
              <Plus size={14} /> Add Room Type
            </button>
          </div>

          {/* Create/Edit Form */}
          {showCreateForm && (
            <div className="bg-white border border-stone-200 rounded-lg p-5 mb-5" data-testid="room-form">
              <h3 className="text-sm font-semibold text-stone-800 mb-4">{editingRoom ? "Edit Room Type" : "Create Room Type"}</h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Property *</label>
                  <select
                    value={roomForm.property_id}
                    onChange={(e) => setRoomForm(p => ({ ...p, property_id: e.target.value }))}
                    className="w-full text-xs border border-stone-200 rounded-lg px-3 py-2 bg-white"
                    data-testid="room-property-select"
                  >
                    <option value="">Select property</option>
                    {properties?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Room Name *</label>
                  <Input value={roomForm.name} onChange={e => setRoomForm(p => ({ ...p, name: e.target.value }))} placeholder="Deluxe King Room" className="text-xs h-9" data-testid="room-name-input" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-stone-500 block mb-1">Description</label>
                  <textarea value={roomForm.description} onChange={e => setRoomForm(p => ({ ...p, description: e.target.value }))} placeholder="Room description..." rows={2} className="w-full text-xs border border-stone-200 rounded-lg px-3 py-2 resize-none" data-testid="room-desc-input" />
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Bed Type</label>
                  <select value={roomForm.bed_type} onChange={e => setRoomForm(p => ({ ...p, bed_type: e.target.value }))} className="w-full text-xs border border-stone-200 rounded-lg px-3 py-2 bg-white">
                    {["single", "double", "twin", "queen", "king", "suite"].map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Max Guests</label>
                  <Input type="number" value={roomForm.max_guests} onChange={e => setRoomForm(p => ({ ...p, max_guests: parseInt(e.target.value) || 1 }))} className="text-xs h-9" min={1} max={10} />
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Size (m&sup2;)</label>
                  <Input type="number" value={roomForm.size_sqm} onChange={e => setRoomForm(p => ({ ...p, size_sqm: parseInt(e.target.value) || 0 }))} className="text-xs h-9" min={0} />
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Total Rooms</label>
                  <Input type="number" value={roomForm.total_rooms} onChange={e => setRoomForm(p => ({ ...p, total_rooms: parseInt(e.target.value) || 1 }))} className="text-xs h-9" min={1} />
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Price per Night (&pound;)</label>
                  <Input type="number" value={roomForm.base_price} onChange={e => setRoomForm(p => ({ ...p, base_price: parseFloat(e.target.value) || 0 }))} className="text-xs h-9" min={0} step={0.01} data-testid="room-price-input" />
                </div>
                <div>
                  <label className="text-xs text-stone-500 block mb-1">Currency</label>
                  <select value={roomForm.currency} onChange={e => setRoomForm(p => ({ ...p, currency: e.target.value }))} className="w-full text-xs border border-stone-200 rounded-lg px-3 py-2 bg-white">
                    {["GBP", "USD", "EUR", "INR", "AED", "THB"].map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              {/* Toggles */}
              <div className="flex gap-4 mb-4">
                <label className="flex items-center gap-2 text-xs text-stone-700 cursor-pointer">
                  <input type="checkbox" checked={roomForm.free_cancellation} onChange={e => setRoomForm(p => ({ ...p, free_cancellation: e.target.checked }))} className="rounded" />
                  Free Cancellation
                </label>
                <label className="flex items-center gap-2 text-xs text-stone-700 cursor-pointer">
                  <input type="checkbox" checked={roomForm.breakfast_included} onChange={e => setRoomForm(p => ({ ...p, breakfast_included: e.target.checked }))} className="rounded" />
                  Breakfast Included
                </label>
              </div>

              {/* Amenities */}
              <div className="mb-4">
                <label className="text-xs text-stone-500 block mb-1">Amenities</label>
                <div className="flex gap-2 mb-2">
                  <Input value={amenityInput} onChange={e => setAmenityInput(e.target.value)} placeholder="Free WiFi" className="text-xs h-8 flex-1" onKeyDown={e => e.key === "Enter" && addAmenity()} />
                  <button onClick={addAmenity} className="px-3 py-1 bg-stone-100 border border-stone-200 text-xs rounded-lg hover:bg-stone-200">Add</button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {roomForm.amenities.map((a, i) => (
                    <span key={i} className="text-[10px] bg-stone-100 text-stone-700 px-2 py-1 rounded flex items-center gap-1">
                      {a}
                      <button onClick={() => setRoomForm(p => ({ ...p, amenities: p.amenities.filter((_, idx) => idx !== i) }))} className="text-stone-400 hover:text-red-500"><X size={10} /></button>
                    </span>
                  ))}
                </div>
              </div>

              {/* Photos */}
              <div className="mb-4">
                <label className="text-xs text-stone-500 block mb-1">Photo URLs</label>
                <div className="flex gap-2 mb-2">
                  <Input value={photoInput} onChange={e => setPhotoInput(e.target.value)} placeholder="https://..." className="text-xs h-8 flex-1" onKeyDown={e => e.key === "Enter" && addPhoto()} />
                  <button onClick={addPhoto} className="px-3 py-1 bg-stone-100 border border-stone-200 text-xs rounded-lg hover:bg-stone-200">Add</button>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {roomForm.photos.map((p, i) => (
                    <div key={i} className="relative w-16 h-12 rounded overflow-hidden border border-stone-200">
                      <img src={p} alt="" className="w-full h-full object-cover" />
                      <button onClick={() => setRoomForm(prev => ({ ...prev, photos: prev.photos.filter((_, idx) => idx !== i) }))} className="absolute top-0 right-0 bg-red-500 text-white p-0.5 rounded-bl"><X size={8} /></button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex gap-2">
                <button onClick={handleSaveRoom} className="px-4 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800" data-testid="save-room-btn">
                  {editingRoom ? "Update Room" : "Create Room"}
                </button>
                <button onClick={() => { setShowCreateForm(false); setEditingRoom(null); }} className="px-4 py-2 border border-stone-300 text-stone-600 text-xs rounded-lg hover:bg-stone-50">Cancel</button>
              </div>
            </div>
          )}

          {/* Room Types List */}
          <div className="space-y-3" data-testid="room-types-list">
            {rooms.map((room) => (
              <div key={room.id} className="bg-white border border-stone-200 rounded-lg overflow-hidden" data-testid={`admin-room-${room.id}`}>
                <div className="flex">
                  <div className="w-32 h-24 bg-stone-200 flex-shrink-0 overflow-hidden">
                    {room.photos?.[0] ? (
                      <img src={room.photos[0]} alt={room.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center"><Bed size={24} className="text-stone-300" /></div>
                    )}
                  </div>
                  <div className="flex-1 p-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="text-sm font-semibold text-stone-800">{room.name}</h4>
                        <div className="flex items-center gap-2 text-[10px] text-stone-500 mt-0.5">
                          <span>{room.bed_type} bed</span>
                          <span>&middot;</span>
                          <span>{room.max_guests} guests</span>
                          {room.size_sqm > 0 && <><span>&middot;</span><span>{room.size_sqm} m&sup2;</span></>}
                          <span>&middot;</span>
                          <span>{room.total_rooms} room{room.total_rooms !== 1 ? "s" : ""}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-lg font-bold text-stone-900">&pound;{room.base_price}</span>
                        <span className="text-[10px] text-stone-500">/night</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex flex-wrap gap-1 flex-1">
                        {room.free_cancellation && (
                          <span className="text-[9px] bg-green-50 text-green-700 px-1.5 py-0.5 rounded">Free cancellation</span>
                        )}
                        {room.breakfast_included && (
                          <span className="text-[9px] bg-green-50 text-green-700 px-1.5 py-0.5 rounded">Breakfast</span>
                        )}
                        {room.amenities?.slice(0, 3).map(a => (
                          <span key={a} className="text-[9px] bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded">{a}</span>
                        ))}
                      </div>
                      <button onClick={() => startEdit(room)} className="p-1.5 text-stone-400 hover:text-stone-600" data-testid={`edit-room-${room.id}`}>
                        <PencilSimple size={14} />
                      </button>
                      <button onClick={() => handleDeleteRoom(room.id)} className="p-1.5 text-stone-400 hover:text-red-500" data-testid={`delete-room-${room.id}`}>
                        <Trash size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {rooms.length === 0 && (
              <div className="text-center py-12 bg-white border border-stone-200 rounded-lg">
                <Bed size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500">No room types yet</p>
                <p className="text-xs text-stone-400 mt-1">Create your first room type to get started</p>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Bookings Tab */
        <div className="space-y-2" data-testid="bookings-list">
          {bookings.length === 0 ? (
            <div className="text-center py-12 bg-white border border-stone-200 rounded-lg">
              <CreditCard size={32} className="mx-auto text-stone-300 mb-3" />
              <p className="text-sm text-stone-500">No bookings yet</p>
              <p className="text-xs text-stone-400 mt-1">Bookings will appear here when guests reserve rooms</p>
            </div>
          ) : bookings.map((booking) => (
            <div key={booking.id} className="bg-white border border-stone-200 rounded-lg p-4" data-testid={`booking-${booking.id}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <code className="text-sm font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">{booking.booking_ref}</code>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${statusColors[booking.status] || "bg-stone-50 text-stone-700"}`}>
                    {booking.status}
                  </span>
                </div>
                <span className="text-xs text-stone-400">{new Date(booking.created_at).toLocaleDateString()}</span>
              </div>
              <div className="grid grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-stone-400 block">Guest</span>
                  <span className="text-stone-800 font-medium">{booking.guest_name}</span>
                  <span className="text-stone-500 block">{booking.guest_email}</span>
                </div>
                <div>
                  <span className="text-stone-400 block">Dates</span>
                  <span className="text-stone-800 font-medium">{new Date(booking.check_in).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} — {new Date(booking.check_out).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
                </div>
                <div>
                  <span className="text-stone-400 block">Guests</span>
                  <span className="text-stone-800 font-medium">{booking.adults} adult{booking.adults !== 1 ? "s" : ""}{booking.children > 0 ? `, ${booking.children} child` : ""}</span>
                </div>
                <div>
                  <span className="text-stone-400 block">Total</span>
                  <span className="text-stone-900 font-bold">&pound;{booking.total_price?.toFixed(0)}</span>
                </div>
              </div>
              {booking.status === "confirmed" && (
                <div className="flex gap-2 mt-3 pt-3 border-t border-stone-100">
                  <button onClick={() => handleUpdateBookingStatus(booking.id, "checked_in")} className="text-[10px] px-2.5 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 font-medium" data-testid={`checkin-${booking.id}`}>Check In</button>
                  <button onClick={() => handleUpdateBookingStatus(booking.id, "cancelled")} className="text-[10px] px-2.5 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100 font-medium" data-testid={`cancel-${booking.id}`}>Cancel</button>
                  <button onClick={() => handleUpdateBookingStatus(booking.id, "no_show")} className="text-[10px] px-2.5 py-1 bg-amber-50 text-amber-700 rounded hover:bg-amber-100 font-medium" data-testid={`noshow-${booking.id}`}>No Show</button>
                </div>
              )}
              {booking.status === "checked_in" && (
                <div className="flex gap-2 mt-3 pt-3 border-t border-stone-100">
                  <button onClick={() => handleUpdateBookingStatus(booking.id, "checked_out")} className="text-[10px] px-2.5 py-1 bg-stone-100 text-stone-700 rounded hover:bg-stone-200 font-medium" data-testid={`checkout-${booking.id}`}>Check Out</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { BookingEnginePanel };
