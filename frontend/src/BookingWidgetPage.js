import { useState, useEffect } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "@/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BookingWidgetPage({ propertyId }) {
  const { t } = useTranslation();
  const [hotelName, setHotelName] = useState("Hotel");
  const [rooms, setRooms] = useState([]);
  const [currency, setCurrency] = useState("GBP");
  const [step, setStep] = useState("search"); // search, results, details, confirmed
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [guests, setGuests] = useState(2);
  const [available, setAvailable] = useState([]);
  const [selected, setSelected] = useState(null);
  const [searching, setSearching] = useState(false);
  const [booking, setBooking] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [form, setForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", special_requests: "" });

  useEffect(() => {
    axios.get(`${API}/booking-widget/info/${propertyId}`).then(r => {
      setHotelName(r.data.hotel_name || "Hotel");
      setRooms(r.data.rooms || []);
      setCurrency(r.data.currency || "GBP");
    }).catch(() => {});
  }, [propertyId]);

  // Default dates
  useEffect(() => {
    const today = new Date();
    const tmrw = new Date(today); tmrw.setDate(tmrw.getDate() + 1);
    const day3 = new Date(today); day3.setDate(day3.getDate() + 3);
    setCheckIn(tmrw.toISOString().split("T")[0]);
    setCheckOut(day3.toISOString().split("T")[0]);
  }, []);

  const search = async () => {
    if (!checkIn || !checkOut) return;
    setSearching(true);
    try {
      const { data } = await axios.post(`${API}/booking-widget/check-availability`, { property_id: propertyId, check_in: checkIn, check_out: checkOut });
      setAvailable(data.available_rooms || []);
      setStep("results");
    } catch { }
    setSearching(false);
  };

  const book = async () => {
    if (!form.guest_name || !form.guest_email || !selected) return;
    setBooking(true);
    try {
      const { data } = await axios.post(`${API}/booking-widget/book`, {
        property_id: propertyId, room_type: selected.name, check_in: checkIn, check_out: checkOut,
        rate: selected.base_rate, guests, currency, ...form,
      });
      setConfirmation(data);
      setStep("confirmed");
    } catch { alert("Booking failed. Please try again."); }
    setBooking(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e293b] to-[#0f172a]" data-testid="booking-widget-page">
      {/* Header */}
      <header className="border-b border-white/10">
        <div className="max-w-3xl mx-auto px-4 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-white" data-testid="widget-hotel-name">{hotelName}</h1>
            <p className="text-white/40 text-xs mt-0.5">Official Direct Booking</p>
          </div>
          <LanguageSwitcher compact />
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <AnimatePresence mode="wait">
          {/* SEARCH */}
          {step === "search" && (
            <motion.div key="search" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-white mb-2">Book Your Stay</h2>
                <p className="text-white/50">Best price guaranteed when you book direct</p>
              </div>
              <div className="bg-white/5 backdrop-blur-xl rounded-2xl border border-white/10 p-6" data-testid="search-form">
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs font-medium text-white/60 mb-1.5 block">Check-in</label>
                    <input data-testid="widget-checkin" type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-white/60 mb-1.5 block">Check-out</label>
                    <input data-testid="widget-checkout" type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-white/60 mb-1.5 block">Guests</label>
                    <select data-testid="widget-guests" value={guests} onChange={e => setGuests(Number(e.target.value))} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none">
                      {[1,2,3,4,5,6].map(n => <option key={n} value={n} className="bg-stone-800">{n} Guest{n > 1 ? "s" : ""}</option>)}
                    </select>
                  </div>
                </div>
                <button data-testid="widget-search-btn" onClick={search} disabled={searching || !checkIn || !checkOut} className="w-full py-3.5 bg-white text-[#0f172a] text-sm font-bold rounded-xl hover:bg-white/90 disabled:opacity-40 transition">
                  {searching ? t("common.loading") : "Search Availability"}
                </button>
              </div>
            </motion.div>
          )}

          {/* RESULTS */}
          {step === "results" && (
            <motion.div key="results" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">Available Rooms</h2>
                  <p className="text-white/40 text-xs">{checkIn} to {checkOut}</p>
                </div>
                <button onClick={() => setStep("search")} className="text-white/50 text-xs hover:text-white">{t("common.back")}</button>
              </div>

              {available.length === 0 ? (
                <div className="bg-white/5 rounded-2xl border border-white/10 p-10 text-center" data-testid="no-availability">
                  <p className="text-white/60">No rooms available for these dates. Try different dates.</p>
                </div>
              ) : (
                <div className="space-y-3" data-testid="room-results">
                  {available.map(room => (
                    <div key={room.room_type_id} className={`bg-white/5 rounded-2xl border ${selected?.room_type_id === room.room_type_id ? "border-white/40 bg-white/10" : "border-white/10"} p-5 cursor-pointer hover:border-white/30 transition`} onClick={() => setSelected(room)} data-testid={`room-${room.room_type_id}`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-semibold text-white">{room.name}</h3>
                          <p className="text-white/40 text-xs mt-0.5">{room.description || `Up to ${room.max_occupancy} guests`}</p>
                          <p className="text-white/30 text-[10px] mt-1">{room.available} room{room.available > 1 ? "s" : ""} left &middot; {room.nights} night{room.nights > 1 ? "s" : ""}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-2xl font-bold text-white">{currency} {room.total_rate}</p>
                          <p className="text-white/40 text-[10px]">{currency} {room.base_rate} / night</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {selected && (
                <button data-testid="btn-continue-booking" onClick={() => setStep("details")} className="w-full mt-4 py-3.5 bg-white text-[#0f172a] text-sm font-bold rounded-xl hover:bg-white/90 transition">
                  Continue — {currency} {selected.total_rate} total
                </button>
              )}
            </motion.div>
          )}

          {/* DETAILS */}
          {step === "details" && (
            <motion.div key="details" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white">Guest Details</h2>
                <button onClick={() => setStep("results")} className="text-white/50 text-xs hover:text-white">{t("common.back")}</button>
              </div>

              {/* Booking Summary */}
              <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-4 flex justify-between items-center" data-testid="booking-summary">
                <div>
                  <p className="text-sm font-semibold text-white">{selected?.name}</p>
                  <p className="text-white/40 text-xs">{checkIn} &rarr; {checkOut} &middot; {selected?.nights} night{selected?.nights > 1 ? "s" : ""}</p>
                </div>
                <p className="text-xl font-bold text-white">{currency} {selected?.total_rate}</p>
              </div>

              <div className="bg-white/5 rounded-2xl border border-white/10 p-5 space-y-4" data-testid="guest-details-form">
                <div>
                  <label className="text-xs font-medium text-white/60 mb-1.5 block">{t("common.name")} *</label>
                  <input data-testid="guest-name" type="text" value={form.guest_name} onChange={e => setForm(p => ({ ...p, guest_name: e.target.value }))} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none" placeholder="Full name" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-white/60 mb-1.5 block">{t("common.email")} *</label>
                    <input data-testid="guest-email" type="email" value={form.guest_email} onChange={e => setForm(p => ({ ...p, guest_email: e.target.value }))} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-white/60 mb-1.5 block">{t("common.phone")}</label>
                    <input data-testid="guest-phone" type="tel" value={form.guest_phone} onChange={e => setForm(p => ({ ...p, guest_phone: e.target.value }))} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-white/60 mb-1.5 block">Special Requests</label>
                  <textarea data-testid="special-requests" value={form.special_requests} onChange={e => setForm(p => ({ ...p, special_requests: e.target.value }))} rows={2} className="w-full px-3 py-3 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:border-white/40 outline-none resize-none" placeholder="Any preferences or requirements..." />
                </div>
                <button data-testid="btn-confirm-booking" onClick={book} disabled={booking || !form.guest_name || !form.guest_email} className="w-full py-3.5 bg-emerald-500 text-white text-sm font-bold rounded-xl hover:bg-emerald-600 disabled:opacity-40 transition">
                  {booking ? t("common.loading") : `Confirm Booking — ${currency} ${selected?.total_rate}`}
                </button>
              </div>
            </motion.div>
          )}

          {/* CONFIRMED */}
          {step === "confirmed" && confirmation && (
            <motion.div key="confirmed" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center" data-testid="booking-confirmed">
              <div className="w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-5">
                <svg className="w-10 h-10 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Booking Confirmed!</h2>
              <p className="text-white/50 text-sm mb-6">A confirmation email has been sent to {form.guest_email}</p>

              <div className="bg-white/5 rounded-2xl border border-white/10 p-5 max-w-sm mx-auto text-left space-y-2">
                <div className="flex justify-between text-sm"><span className="text-white/50">Reference</span><span className="font-mono font-bold text-emerald-400" data-testid="conf-ref">{confirmation.booking_ref}</span></div>
                <div className="flex justify-between text-sm"><span className="text-white/50">Hotel</span><span className="text-white font-medium">{hotelName}</span></div>
                <div className="flex justify-between text-sm"><span className="text-white/50">Room</span><span className="text-white font-medium">{selected?.name}</span></div>
                <div className="flex justify-between text-sm"><span className="text-white/50">Check-in</span><span className="text-white font-medium">{checkIn}</span></div>
                <div className="flex justify-between text-sm"><span className="text-white/50">Check-out</span><span className="text-white font-medium">{checkOut}</span></div>
                <div className="flex justify-between text-sm border-t border-white/10 pt-2"><span className="text-white/50">Total</span><span className="text-lg font-bold text-white">{currency} {selected?.total_rate}</span></div>
              </div>

              <p className="text-white/30 text-xs mt-6">You can close this page. We look forward to welcoming you!</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="text-center pb-4 text-[10px] text-white/20">Powered by My Hotel Box</div>
    </div>
  );
}
