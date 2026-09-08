import {
  User, EnvelopeSimple, Phone, CreditCard, ShieldCheck,
  Lock, Buildings, CheckCircle, Bed, Tag, Plus, X, Sparkle, Gift,
} from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";
import { SmartUpsellEngine } from "./SmartUpsellEngine";
import { PriceComparisonWidget } from "./PriceComparisonWidget";
import { planNightPrice, planName, roomNightBase } from "./RatePlanRows";

export function GuestDetailsStep({ t, selectedRoom, property, guestForm, setGuestForm, paymentMethod, setPaymentMethod, onBook, bookingLoading, totalPrice, subtotal, addOnsTotal, discountAmount, promoCode, setPromoCode, promoDiscount, applyPromo, setPromoDiscount, addOns, selectedAddOns, toggleAddOn, upsells, selectedUpsells, toggleUpsell, nights, adults, children, roomCount, checkIn, checkOut, socialProofSettings, dwConfig, damageWaiver, setDamageWaiver, waiverTotal, cart, onBackToRooms, giftCode, setGiftCode, giftCard, applyGift, clearGift, giftApplied, depositDue, fmt = (v) => `£${Math.round(v)}`, memberPct = 0, cityTax = 0, vatRate = 0, childExtra = 0, beCfg = null, agentCode = "", setAgentCode = () => {}, agentInfo = null, applyAgentCode = () => {}, clearAgentCode = () => {}, flexCancel = false, setFlexCancel = () => {}, flexFee = 0, extraAdultTotal = 0, losDiscount = 0, losPct = 0, agentDiscount = 0 }) {
  const { t: tr } = useLanguage();
  const showDeposit = depositDue > 0 && depositDue < totalPrice - 0.5;
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="guest-details-step">
      {onBackToRooms && (
        <button type="button" onClick={onBackToRooms} className="text-sm font-semibold mb-4 hover:underline" style={{ color: t.colors.accent }} data-testid="back-to-rooms-btn">← {tr("cart.addMoreRooms")}</button>
      )}
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

          {/* Smart Upsell Engine */}
          {upsells?.length > 0 && (
            <SmartUpsellEngine t={t} upsells={upsells} selectedUpsells={selectedUpsells || []} onToggle={toggleUpsell} nights={nights} adults={adults} />
          )}

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

          {/* Gift card */}
          {setGiftCode && (
            <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="gift-redeem-section">
              <h2 className="text-lg font-semibold text-slate-900 mb-3 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
                <Gift size={20} style={{ color: t.colors.accent }} /> {tr("gift.redeemTitle")}
              </h2>
              {giftCard ? (
                <div className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: `${t.colors.success}10` }} data-testid="gift-applied">
                  <span className="text-sm font-medium" style={{ color: t.colors.success }}>{giftCard.code} — {tr("gift.balance")} £{Number(giftCard.balance).toFixed(0)} · {tr("gift.applied")} £{giftApplied.toFixed(0)}</span>
                  <button onClick={clearGift} className="text-slate-400 hover:text-slate-600" aria-label="remove" data-testid="gift-remove-btn"><X size={16} /></button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <input value={giftCode} onChange={e => setGiftCode(e.target.value.toUpperCase())} placeholder="MHB-XXXX-XXXX-XXXX" className="flex-1 border border-gray-300 rounded-lg px-3 py-2.5 text-sm font-mono uppercase" onKeyDown={e => e.key === "Enter" && applyGift()} data-testid="gift-code-input" aria-label={tr("gift.redeemTitle")} />
                  <button onClick={applyGift} className="px-4 py-2.5 text-white rounded-lg text-sm font-semibold" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="gift-apply-btn">{tr("promo.apply")}</button>
                </div>
              )}
            </div>
          )}

          {beCfg?.agent_code_enabled && (
            <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="agent-code-section">
              <h3 className="font-semibold text-slate-800 mb-1 text-sm">{tr("agent.title")}</h3>
              {agentInfo ? (
                <div className="flex items-center justify-between text-sm" data-testid="agent-code-applied"><span className="text-emerald-700 font-semibold">✓ {agentInfo.agent_name} — −{agentInfo.discount_pct}%</span><button type="button" onClick={clearAgentCode} className="text-xs text-slate-500 underline" data-testid="agent-code-remove">×</button></div>
              ) : (
                <div className="flex gap-2"><input value={agentCode} onChange={(e) => setAgentCode(e.target.value.toUpperCase())} placeholder={tr("agent.placeholder")} className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm uppercase" data-testid="agent-code-input" />
                  <button type="button" onClick={applyAgentCode} disabled={!agentCode} className="px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-40" style={{ background: t.colors.primary, borderRadius: t.borderRadius }} data-testid="agent-code-apply">{tr("promo.apply")}</button></div>
              )}
            </div>
          )}
          {beCfg?.flex_cancel_enabled && flexFee >= 0 && (
            <label className="bg-white rounded-lg border border-gray-200 p-6 flex items-start gap-3 cursor-pointer" style={{ borderRadius: t.borderRadius }} data-testid="flex-cancel-section">
              <input type="checkbox" checked={flexCancel} onChange={(e) => setFlexCancel(e.target.checked)} className="mt-1" data-testid="flex-cancel-checkbox" />
              <div className="text-sm"><div className="font-semibold text-slate-800">{tr("flex.title", { pct: beCfg.flex_cancel_pct })}</div><div className="text-slate-500 text-xs">{tr("flex.sub")}</div></div>
            </label>
          )}
          {/* Damage Waiver opt-in */}
          {dwConfig && (
            <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="damage-waiver-section">
              <label className="flex items-start gap-3 cursor-pointer" data-testid="damage-waiver-option">
                <input type="checkbox" checked={damageWaiver} onChange={e => setDamageWaiver(e.target.checked)}
                  data-testid="damage-waiver-checkbox"
                  className="mt-1 w-5 h-5 rounded border-gray-300 flex-shrink-0" style={{ accentColor: t.colors.accent }} />
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <ShieldCheck size={18} weight="fill" style={{ color: t.colors.success }} />
                    <span className="font-semibold text-slate-800 text-sm">Depozitosuz Konaklama — Hasar Koruması</span>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ background: t.colors.badgeBg, color: t.colors.success }}>
                      +{dwConfig.currency === "TRY" ? "₺" : dwConfig.currency === "EUR" ? "€" : "£"}{dwConfig.fee_per_night}/gece
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Güvence depozitosu ödemeyin. {dwConfig.currency === "TRY" ? "₺" : dwConfig.currency === "EUR" ? "€" : "£"}{dwConfig.coverage_limit.toLocaleString()} tutarına kadar kazara oluşan hasarlar teminat altındadır.
                  </p>
                </div>
              </label>
            </div>
          )}

          {/* Payment Method */}
          <div className="bg-white rounded-lg border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }} data-testid="payment-method-section">
            <h2 className="text-xl font-semibold text-slate-900 mb-4 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}>
              <CreditCard size={22} style={{ color: t.colors.accent }} /> {tr("payment.title")}
            </h2>
            <div className="space-y-3">
              {[
                { value: "card", icon: CreditCard, label: tr("payment.payNow"), sub: tr("payment.payNowSub"), showSecure: true, wallets: true },
                ...(showDeposit ? [{ value: "deposit", icon: ShieldCheck, label: tr("payment.payDeposit", { amount: depositDue.toFixed(0) }), sub: tr("payment.payDepositSub", { rest: (totalPrice - depositDue).toFixed(0) }), showSecure: true, wallets: true }] : []),
                { value: "iyzico", icon: CreditCard, label: "iyzico ile Ode", sub: "Turkey — All Turkish banks, taksit (installments)", showSecure: true, flag: "🇹🇷" },
                { value: "paytr", icon: CreditCard, label: "PayTR ile Ode", sub: "Turkey — Sanal POS, SMS payment, taksitli odeme", showSecure: true, flag: "🇹🇷" },
                { value: "hotel", icon: Buildings, label: tr("payment.payHotel"), sub: tr("payment.payHotelSub") },
                ...(beCfg?.hold_enabled ? [{ value: "hold", icon: ShieldCheck, label: tr("payment.hold", { hours: beCfg.hold_hours || 24 }), sub: tr("payment.holdSub") }] : []),
              ].map(({ value, icon: Icon, label, sub, showSecure, wallets }) => (
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
                    {wallets && <div className="flex gap-1.5 mt-1.5">{["Visa", "Mastercard", "Apple Pay", "Google Pay"].map(w => <span key={w} className="text-[9px] font-bold px-1.5 py-0.5 rounded border border-gray-200 text-slate-500">{w}</span>)}</div>}
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
              : paymentMethod === "hold" ? <><ShieldCheck size={20} weight="fill" /> {tr("payment.holdBtn")}</> : paymentMethod === "card" ? <><CreditCard size={20} weight="fill" /> {tr("payment.payAndComplete", { amount: totalPrice.toFixed(0) })}</>
              : paymentMethod === "deposit" ? <><ShieldCheck size={20} weight="fill" /> {tr("payment.payAndComplete", { amount: depositDue.toFixed(0) })}</>
              : paymentMethod === "iyzico" ? <><CreditCard size={20} weight="fill" /> iyzico ile {totalPrice.toFixed(0)} {selectedRoom?.currency || "TRY"} Ode</>
              : paymentMethod === "paytr" ? <><CreditCard size={20} weight="fill" /> PayTR ile {totalPrice.toFixed(0)} {selectedRoom?.currency || "TRY"} Ode</>
              : <><Lock size={20} weight="fill" /> {tr("payment.completePayAtHotel")}</>}
          </button>
          <p className="text-center text-xs text-slate-400 flex items-center justify-center gap-1 mt-2">
            <ShieldCheck size={14} weight="fill" style={{ color: t.colors.success }} /> {tr("payment.dataProtected")}
          </p>
        </div>

        {/* Booking Summary Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Price Comparison Widget */}
          <PriceComparisonWidget t={t} roomPrice={selectedRoom.base_price * nights} settings={socialProofSettings} />
          <BookingSummary t={t} room={selectedRoom} property={property} totalPrice={totalPrice} subtotal={subtotal} addOnsTotal={addOnsTotal} discountAmount={discountAmount} promoDiscount={promoDiscount} selectedAddOns={selectedAddOns} selectedUpsells={selectedUpsells} nights={nights} adults={adults} children={children} roomCount={roomCount} checkIn={checkIn} checkOut={checkOut} waiverTotal={waiverTotal} cart={cart} giftApplied={giftApplied} fmt={fmt} memberPct={memberPct} cityTax={cityTax} vatRate={vatRate} childExtra={childExtra} flexCancel={flexCancel} flexFee={flexFee} extraAdultTotal={extraAdultTotal} losDiscount={losDiscount} losPct={losPct} agentDiscount={agentDiscount} />
        </div>
      </div>
    </div>
  );
}

function BookingSummary({ t, room, property, totalPrice, subtotal, addOnsTotal, discountAmount, promoDiscount, selectedAddOns, selectedUpsells, nights, adults, children, roomCount, checkIn, checkOut, waiverTotal, cart, giftApplied = 0, fmt = (v) => `£${Math.round(v)}`, memberPct = 0, cityTax = 0, vatRate = 0, childExtra = 0, beCfg = null, agentCode = "", setAgentCode = () => {}, agentInfo = null, applyAgentCode = () => {}, clearAgentCode = () => {}, flexCancel = false, setFlexCancel = () => {}, flexFee = 0, extraAdultTotal = 0, losDiscount = 0, losPct = 0, agentDiscount = 0 }) {
  const { t: tr, lang } = useLanguage();
  const multi = cart?.length > 0;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 sticky top-20" style={{ borderRadius: t.borderRadius }} data-testid="booking-summary">
      <h3 className="font-semibold text-slate-900 mb-4" style={{ fontFamily: t.fonts.heading }}>{tr("summary.title")}</h3>
      {multi ? (
        <div className="space-y-2 mb-4 pb-4 border-b border-gray-100" data-testid="summary-cart-items">
          {cart.map((c, i) => (
            <div key={i} className="flex gap-3">
              <div className="w-14 h-12 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
                {c.room.photos?.[0] ? <img src={c.room.photos[0]} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Bed size={16} className="text-slate-300" /></div>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-sm text-slate-900 truncate">{c.qty}× {c.room.name}</div>
                {c.plan && <div className="text-xs text-slate-500">{planName(c.plan, lang)}{c.extraBeds ? ` · +${c.extraBeds} ${tr("extra.bed")}` : ""}</div>}
              </div>
              <div className="text-sm font-semibold text-slate-800">{fmt(planNightPrice(roomNightBase(c.room), c.plan) * (1 - memberPct / 100) * nights * c.qty + (Number(c.room.extra_bed_price) || 0) * nights * (c.extraBeds || 0))}</div>
            </div>
          ))}
          <div className="text-xs text-slate-500 pt-1">{property?.name}</div>
        </div>
      ) : (
        <div className="flex gap-3 mb-4 pb-4 border-b border-gray-100">
          <div className="w-20 h-16 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
            {room.photos?.[0] ? <img src={room.photos[0]} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Bed size={20} className="text-slate-300" /></div>}
          </div>
          <div>
            <div className="font-semibold text-sm text-slate-900">{room.name}</div>
            <div className="text-xs text-slate-500 mt-0.5">{property?.name}</div>
          </div>
        </div>
      )}
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
        <div className="flex justify-between"><span className="text-slate-500">{multi ? tr("summary.roomsSubtotal") : <>{fmt(roomNightBase(room))} x {nights} {nights !== 1 ? tr("room.nights") : tr("room.night")}</>}</span><span data-testid="summary-subtotal">{fmt(subtotal ?? roomNightBase(room) * nights * roomCount)}</span></div>
        {memberPct > 0 && <div className="flex justify-between" style={{ color: t.colors.success }} data-testid="summary-member"><span>★ {tr("member.line", { pct: memberPct })}</span><span>{tr("summary.included")}</span></div>}
        {childExtra > 0 && <div className="flex justify-between" data-testid="summary-child"><span className="text-slate-500">{tr("summary.children")}</span><span>{fmt(childExtra)}</span></div>}
        {extraAdultTotal > 0 && <div className="flex justify-between" data-testid="summary-extra-adult"><span className="text-slate-500">{tr("summary.extraAdult")}</span><span>{fmt(extraAdultTotal)}</span></div>}
        {losDiscount > 0 && <div className="flex justify-between" data-testid="summary-los"><span className="text-emerald-700">{tr("summary.los", { pct: losPct })}</span><span className="text-emerald-700">−{fmt(losDiscount)}</span></div>}
        {agentDiscount > 0 && <div className="flex justify-between" data-testid="summary-agent"><span className="text-emerald-700">{tr("summary.agent")}</span><span className="text-emerald-700">−{fmt(agentDiscount)}</span></div>}
        {flexFee > 0 && flexCancel && <div className="flex justify-between" data-testid="summary-flex"><span className="text-slate-500">{tr("flex.short")}</span><span>{fmt(flexFee)}</span></div>}
        {cityTax > 0 && <div className="flex justify-between" data-testid="summary-city-tax"><span className="text-slate-500">{tr("tax.city")}</span><span>{fmt(cityTax)}</span></div>}
        {selectedAddOns?.length > 0 && selectedAddOns.map(ao => (
          <div key={ao.id} className="flex justify-between text-xs"><span className="text-slate-500">{ao.name}</span><span>{fmt(ao.price)}</span></div>
        ))}
        {selectedUpsells?.length > 0 && selectedUpsells.map(u => (
          <div key={u.id} className="flex justify-between text-xs"><span className="text-amber-600">{u.name}</span><span>{fmt(u.price)}</span></div>
        ))}
        {waiverTotal > 0 && (
          <div className="flex justify-between text-xs" data-testid="summary-damage-waiver">
            <span className="text-slate-500">Hasar koruması</span><span>{fmt(waiverTotal)}</span>
          </div>
        )}
        {discountAmount > 0 && (
          <div className="flex justify-between" style={{ color: t.colors.success }}>
            <span>{tr("summary.promo")} ({promoDiscount?.code})</span>
            <span>-{fmt(discountAmount)}</span>
          </div>
        )}
        {giftApplied > 0 && (
          <div className="flex justify-between" style={{ color: t.colors.success }} data-testid="summary-gift">
            <span>{tr("gift.card")}</span><span>-{fmt(giftApplied)}</span>
          </div>
        )}
        <div className="flex justify-between"><span className="text-slate-500">{vatRate ? tr("tax.vatIncl", { pct: vatRate }) : tr("summary.taxesFees")}</span><span data-testid="summary-vat">{vatRate ? fmt(totalPrice - totalPrice / (1 + vatRate / 100)) : tr("summary.included")}</span></div>
      </div>
      <div className="flex justify-between items-baseline">
        <span className="font-semibold text-slate-900">{tr("summary.total")}</span>
        <span className="text-2xl font-bold text-slate-900" data-testid="summary-total">{fmt(totalPrice)}</span>
      </div>
      {(multi ? cart.every((c) => !c.plan || c.plan.cancellation_type === "free") : room.free_cancellation) && (
        <div className="mt-3 rounded-lg p-3 text-xs font-medium flex items-center gap-1.5" style={{ background: t.colors.badgeBg, color: t.colors.success }} data-testid="summary-free-cancel">
          <CheckCircle size={14} weight="fill" /> {tr("summary.freeCancellation")}
        </div>
      )}
    </div>
  );
}
