import {
  User, EnvelopeSimple, Phone, CreditCard, ShieldCheck,
  Lock, Buildings, CheckCircle, Bed,
} from "@phosphor-icons/react";

export function GuestDetailsStep({ t, selectedRoom, property, guestForm, setGuestForm, paymentMethod, setPaymentMethod, onBook, bookingLoading, totalPrice, nights, adults, children, roomCount, checkIn, checkOut }) {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="guest-details-step">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Guest Info Form */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }}>
            <h2 className="text-xl font-semibold text-slate-900 mb-6 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <User size={22} style={{ color: t.colors.accent }} /> Your Details
            </h2>
            <div className="space-y-4">
              {[
                { label: "Full Name *", field: "guest_name", type: "text", icon: User, placeholder: "John Smith", testId: "guest-name-input" },
                { label: "Email Address *", field: "guest_email", type: "email", icon: EnvelopeSimple, placeholder: "john@example.com", testId: "guest-email-input" },
                { label: "Phone Number", field: "guest_phone", type: "tel", icon: Phone, placeholder: "+44 7XXX XXXXXX", testId: "guest-phone-input" },
              ].map(({ label, field, type, icon: Icon, placeholder, testId }) => (
                <div key={field}>
                  <label className="text-sm font-medium text-slate-700 mb-1 block">{label}</label>
                  <div className="relative">
                    <Icon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input type={type} value={guestForm[field]} onChange={e => setGuestForm(p => ({ ...p, [field]: e.target.value }))}
                      placeholder={placeholder} className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:border-transparent"
                      style={{ "--tw-ring-color": t.colors.accent }} data-testid={testId} />
                  </div>
                </div>
              ))}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">Special Requests</label>
                <textarea value={guestForm.special_requests} onChange={e => setGuestForm(p => ({ ...p, special_requests: e.target.value }))}
                  placeholder="Any special requirements?" rows={3} className="w-full border border-gray-300 rounded-lg px-3 py-3 resize-none" data-testid="special-requests-input" />
              </div>
            </div>
          </div>

          {/* Payment Method */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="payment-method-section">
            <h2 className="text-xl font-semibold text-slate-900 mb-4 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <CreditCard size={22} style={{ color: t.colors.accent }} /> Payment Method
            </h2>
            <div className="space-y-3">
              {[
                { value: "card", icon: CreditCard, label: "Pay Now with Card", sub: "Secure payment via Stripe. Instantly confirmed.", showSecure: true },
                { value: "hotel", icon: Buildings, label: "Pay at Hotel", sub: "Pay when you arrive. No payment required now." },
              ].map(({ value, icon: Icon, label, sub, showSecure }) => (
                <label key={value} className="flex items-center gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors"
                  style={{ borderColor: paymentMethod === value ? t.colors.accent : "#e5e7eb", background: paymentMethod === value ? `${t.colors.accent}08` : "transparent", borderRadius: t.borderRadius }}
                  data-testid={`payment-${value}-option`}>
                  <input type="radio" name="payment" value={value} checked={paymentMethod === value} onChange={() => setPaymentMethod(value)} className="sr-only" />
                  <div className="w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0" style={{ borderColor: paymentMethod === value ? t.colors.accent : "#d1d5db" }}>
                    {paymentMethod === value && <div className="w-2.5 h-2.5 rounded-full" style={{ background: t.colors.accent }} />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Icon size={18} style={{ color: paymentMethod === value ? t.colors.accent : "#64748b" }} />
                      <span className="font-semibold text-slate-800 text-sm">{label}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
                  </div>
                  {showSecure && <div className="flex items-center gap-1 text-xs text-slate-400"><ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /><span>Secure</span></div>}
                </label>
              ))}
            </div>
          </div>

          {/* Book Button */}
          <button onClick={onBook} disabled={bookingLoading || !guestForm.guest_name || !guestForm.guest_email}
            className="w-full text-white py-4 rounded-lg font-bold text-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-xl"
            style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="complete-booking-btn">
            {bookingLoading ? <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
              : paymentMethod === "card" ? <><CreditCard size={20} weight="fill" /> Pay &pound;{totalPrice.toFixed(0)} &amp; Complete Booking</>
              : <><Lock size={20} weight="fill" /> Complete Booking — Pay at Hotel</>}
          </button>
          <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1 mt-2">
            <ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /> Your personal data is protected by SSL encryption
          </p>
        </div>

        {/* Booking Summary Sidebar */}
        <div className="lg:col-span-1">
          <BookingSummary t={t} room={selectedRoom} property={property} totalPrice={totalPrice} nights={nights} adults={adults} children={children} roomCount={roomCount} checkIn={checkIn} checkOut={checkOut} />
        </div>
      </div>
    </div>
  );
}

function BookingSummary({ t, room, property, totalPrice, nights, adults, children, roomCount, checkIn, checkOut }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 sticky top-20" style={{ borderRadius: t.borderRadius }} data-testid="booking-summary">
      <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: t.fonts.heading }}>Booking Summary</h3>
      <div className="flex gap-3 mb-4 pb-4 border-b border-gray-100">
        <div className="w-20 h-16 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
          {room.photos?.[0] ? <img src={room.photos[0]} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Bed size={20} className="text-slate-300" /></div>}
        </div>
        <div>
          <div className="font-semibold text-sm text-slate-900">{room.name}</div>
          <div className="text-xs text-slate-500 mt-0.5">{property?.name}</div>
        </div>
      </div>
      <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
        {[
          ["Check-in", new Date(checkIn).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
          ["Check-out", new Date(checkOut).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
          ["Duration", `${nights} night${nights !== 1 ? "s" : ""}`],
          ["Guests", `${adults} adult${adults !== 1 ? "s" : ""}${children > 0 ? `, ${children} child${children !== 1 ? "ren" : ""}` : ""}`],
          ["Rooms", roomCount],
        ].map(([l, v]) => <div key={l} className="flex justify-between"><span className="text-slate-500">{l}</span><span className="font-medium text-slate-800">{v}</span></div>)}
      </div>
      <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
        <div className="flex justify-between"><span className="text-slate-500">&pound;{room.base_price} x {nights} night{nights !== 1 ? "s" : ""}</span><span>&pound;{totalPrice.toFixed(0)}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">Taxes & fees</span><span>Included</span></div>
      </div>
      <div className="flex justify-between items-baseline">
        <span className="font-semibold text-slate-900">Total</span>
        <span className="text-2xl font-bold text-slate-900">&pound;{totalPrice.toFixed(0)}</span>
      </div>
      {room.free_cancellation && (
        <div className="mt-3 rounded-lg p-3 text-xs font-medium flex items-center gap-1.5" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
          <CheckCircle size={14} weight="fill" /> Free cancellation available
        </div>
      )}
    </div>
  );
}
