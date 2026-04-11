import {
  User, EnvelopeSimple, Phone, CreditCard, ShieldCheck,
  Lock, Buildings, CheckCircle, Bed, Tag, Plus, X, Sparkle,
} from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

export function GuestDetailsStep({ t, selectedRoom, property, guestForm, setGuestForm, paymentMethod, setPaymentMethod, onBook, bookingLoading, totalPrice, subtotal, addOnsTotal, discountAmount, promoCode, setPromoCode, promoDiscount, applyPromo, setPromoDiscount, addOns, selectedAddOns, toggleAddOn, nights, adults, children, roomCount, checkIn, checkOut }) {
  const { t: tr } = useLanguage();
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="guest-details-step">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Guest Info Form */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }}>
            <h2 className="text-xl font-semibold text-slate-900 mb-6 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <User size={22} style={{ color: t.colors.accent }} /> {tr("guest.yourDetails")}
            </h2>
            <div className="space-y-4">
              {[
                { label: tr("guest.fullName"), field: "guest_name", type: "text", icon: User, placeholder: tr("guest.namePlaceholder"), testId: "guest-name-input" },
                { label: tr("guest.emailAddress"), field: "guest_email", type: "email", icon: EnvelopeSimple, placeholder: tr("guest.emailPlaceholder"), testId: "guest-email-input" },
                { label: tr("guest.phoneNumber"), field: "guest_phone", type: "tel", icon: Phone, placeholder: tr("guest.phonePlaceholder"), testId: "guest-phone-input" },
              ].map(({ label, field, type, icon: Icon, placeholder, testId }) => (
                <div key={field}>
                  <label className="text-sm font-medium text-slate-700 mb-1 block">{label}</label>
                  <div className="relative">
                    <Icon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input type={type} value={guestForm[field]} onChange={e => setGuestForm(p => ({ ...p, [field]: e.target.value }))}
                      placeholder={placeholder} className="w-full border border-gray-300 rounded-lg pl-10 pr-3 py-3 focus:ring-2 focus:border-transparent"
                      data-testid={testId} />
                  </div>
                </div>
              ))}
              <div>
                <label className="text-sm font-medium text-slate-700 mb-1 block">{tr("guest.specialRequests")}</label>
                <textarea value={guestForm.special_requests} onChange={e => setGuestForm(p => ({ ...p, special_requests: e.target.value }))}
                  placeholder={tr("guest.requestsPlaceholder")} rows={3} className="w-full border border-gray-300 rounded-lg px-3 py-3 resize-none" data-testid="special-requests-input" />
              </div>
            </div>
          </div>

          {/* Add-on Services */}
          {addOns?.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="addons-section">
              <h2 className="text-xl font-semibold text-slate-900 mb-4 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
                <Sparkle size={22} style={{ color: t.colors.accent }} /> {tr("addons.title")}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {addOns.map(addon => {
                  const isSelected = selectedAddOns.find(a => a.id === addon.id);
                  return (
                    <button key={addon.id} onClick={() => toggleAddOn(addon)}
                      className="flex items-center gap-3 p-3 rounded-lg border-2 text-left transition-all"
                      style={{ borderColor: isSelected ? t.colors.accent : "#e5e7eb", background: isSelected ? `${t.colors.accent}08` : "transparent", borderRadius: t.borderRadius }}
                      data-testid={`addon-${addon.id}`}>
                      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: isSelected ? `${t.colors.accent}20` : "#f1f5f9" }}>
                        {isSelected ? <CheckCircle size={16} weight="fill" style={{ color: t.colors.accent }} /> : <Plus size={14} className="text-slate-400" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-semibold text-slate-800 block">{addon.name}</span>
                        {addon.description && <span className="text-xs text-slate-500 block truncate">{addon.description}</span>}
                      </div>
                      <span className="text-sm font-bold text-slate-800 flex-shrink-0">&pound;{addon.price}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Promo Code */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="promo-section">
            <h2 className="text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <Tag size={20} style={{ color: t.colors.accent }} /> {tr("promo.title")}
            </h2>
            <div className="flex gap-2">
              <input value={promoCode} onChange={e => setPromoCode(e.target.value.toUpperCase())}
                placeholder={tr("promo.placeholder")} className="flex-1 border border-gray-300 rounded-lg px-3 py-2.5 text-sm font-mono uppercase"
                onKeyDown={e => e.key === "Enter" && applyPromo()} data-testid="promo-code-input" />
              <button onClick={applyPromo} className="px-4 py-2.5 text-white rounded-lg text-sm font-semibold"
                style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="apply-promo-btn">
                {tr("promo.apply")}
              </button>
            </div>
            {promoDiscount && (
              <div className="flex items-center justify-between mt-3 px-3 py-2 rounded-lg" style={{ background: `${t.colors.success}10` }} data-testid="promo-applied">
                <div className="flex items-center gap-2">
                  <CheckCircle size={16} weight="fill" style={{ color: t.colors.success }} />
                  <span className="text-sm font-medium" style={{ color: t.colors.success }}>{promoDiscount.code} — {promoDiscount.description || `${promoDiscount.discount_value}${promoDiscount.discount_type === "percentage" ? "%" : "£"} ${tr("promo.off")}`}</span>
                </div>
                <button onClick={() => { setPromoDiscount(null); setPromoCode(""); }} className="text-slate-400 hover:text-slate-600" data-testid="remove-promo-btn">
                  <X size={16} />
                </button>
              </div>
            )}
          </div>

          {/* Payment Method */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="payment-method-section">
            <h2 className="text-xl font-semibold text-slate-900 mb-4 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <CreditCard size={22} style={{ color: t.colors.accent }} /> {tr("payment.title")}
            </h2>
            <div className="space-y-3">
              {[
                { value: "card", icon: CreditCard, label: tr("payment.payNow"), sub: tr("payment.payNowSub"), showSecure: true },
                { value: "hotel", icon: Buildings, label: tr("payment.payHotel"), sub: tr("payment.payHotelSub") },
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
                  {showSecure && <div className="flex items-center gap-1 text-xs text-slate-400"><ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /><span>{tr("payment.secure")}</span></div>}
                </label>
              ))}
            </div>
          </div>

          {/* Book Button */}
          <button onClick={onBook} disabled={bookingLoading || !guestForm.guest_name || !guestForm.guest_email}
            className="w-full text-white py-4 rounded-lg font-bold text-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 shadow-xl"
            style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="complete-booking-btn">
            {bookingLoading ? <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin" />
              : paymentMethod === "card" ? <><CreditCard size={20} weight="fill" /> {tr("payment.payAndComplete", { amount: totalPrice.toFixed(0) })}</>
              : <><Lock size={20} weight="fill" /> {tr("payment.completePayAtHotel")}</>}
          </button>
          <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1 mt-2">
            <ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /> {tr("payment.dataProtected")}
          </p>
        </div>

        {/* Booking Summary Sidebar */}
        <div className="lg:col-span-1">
          <BookingSummary t={t} room={selectedRoom} property={property} totalPrice={totalPrice} subtotal={subtotal} addOnsTotal={addOnsTotal} discountAmount={discountAmount} promoDiscount={promoDiscount} selectedAddOns={selectedAddOns} nights={nights} adults={adults} children={children} roomCount={roomCount} checkIn={checkIn} checkOut={checkOut} />
        </div>
      </div>
    </div>
  );
}

function BookingSummary({ t, room, property, totalPrice, subtotal, addOnsTotal, discountAmount, promoDiscount, selectedAddOns, nights, adults, children, roomCount, checkIn, checkOut }) {
  const { t: tr } = useLanguage();
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 sticky top-20" style={{ borderRadius: t.borderRadius }} data-testid="booking-summary">
      <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: t.fonts.heading }}>{tr("summary.title")}</h3>
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
          [tr("summary.checkIn"), new Date(checkIn).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
          [tr("summary.checkOut"), new Date(checkOut).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })],
          [tr("summary.duration"), `${nights} ${nights !== 1 ? tr("room.nights") : tr("room.night")}`],
          [tr("summary.guests"), `${adults} ${adults !== 1 ? tr("search.adults") : tr("search.adult")}${children > 0 ? `, ${children} ${children !== 1 ? tr("search.children") : tr("search.child")}` : ""}`],
          [tr("summary.rooms"), roomCount],
        ].map(([l, v]) => <div key={l} className="flex justify-between"><span className="text-slate-500">{l}</span><span className="font-medium text-slate-800">{v}</span></div>)}
      </div>
      <div className="space-y-2 text-sm mb-4 pb-4 border-b border-gray-100">
        <div className="flex justify-between"><span className="text-slate-500">&pound;{room.base_price} x {nights} {nights !== 1 ? tr("room.nights") : tr("room.night")}</span><span>&pound;{subtotal?.toFixed(0) || (room.base_price * nights * roomCount).toFixed(0)}</span></div>
        {selectedAddOns?.length > 0 && selectedAddOns.map(ao => (
          <div key={ao.id} className="flex justify-between text-xs"><span className="text-slate-500">{ao.name}</span><span>&pound;{ao.price}</span></div>
        ))}
        {discountAmount > 0 && (
          <div className="flex justify-between" style={{ color: t.colors.success }}>
            <span>{tr("summary.promo")} ({promoDiscount?.code})</span>
            <span>-&pound;{discountAmount.toFixed(0)}</span>
          </div>
        )}
        <div className="flex justify-between"><span className="text-slate-500">{tr("summary.taxesFees")}</span><span>{tr("summary.included")}</span></div>
      </div>
      <div className="flex justify-between items-baseline">
        <span className="font-semibold text-slate-900">{tr("summary.total")}</span>
        <span className="text-2xl font-bold text-slate-900">&pound;{totalPrice.toFixed(0)}</span>
      </div>
      {room.free_cancellation && (
        <div className="mt-3 rounded-lg p-3 text-xs font-medium flex items-center gap-1.5" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
          <CheckCircle size={14} weight="fill" /> {tr("summary.freeCancellation")}
        </div>
      )}
    </div>
  );
}
