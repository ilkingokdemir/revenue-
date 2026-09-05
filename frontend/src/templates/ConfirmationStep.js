import { CheckCircle } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

export function ConfirmationStep({ t, confirmation, onBookAnother }) {
  const { t: tr } = useLanguage();
  if (!confirmation) return null;
  return (
    <div className="max-w-3xl mx-auto px-4 py-12" data-testid="confirmation-step">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden" style={{ borderRadius: t.borderRadius }}>
        <div className="text-white px-8 py-6 text-center" style={{ background: t.colors.success }}>
          <CheckCircle size={48} weight="fill" className="mx-auto mb-3" />
          <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: t.fonts.heading }}>{tr("confirm.title")}</h2>
          <p style={{ opacity: 0.8 }}>{confirmation.payment_status === "paid" ? tr("confirm.paymentReceived") : tr("confirm.reservationConfirmed")}</p>
        </div>
        <div className="p-8">
          <div className="rounded-lg p-5 mb-6 text-center" style={{ background: t.colors.bodyBg }}>
            <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">{tr("confirm.bookingRef")}</div>
            <div className="text-3xl font-bold tracking-wider" style={{ color: t.colors.primary }} data-testid="booking-ref">{confirmation.booking_ref}</div>
            <p className="text-xs text-slate-500 mt-2">{tr("confirm.saveRef")}</p>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              [tr("confirm.guestName"), confirmation.guest_name],
              [tr("confirm.email"), confirmation.guest_email],
              [tr("confirm.checkIn"), new Date(confirmation.check_in).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
              [tr("confirm.checkOut"), new Date(confirmation.check_out).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
              [tr("confirm.guests"), `${confirmation.adults} ${confirmation.adults !== 1 ? "adults" : "adult"}${confirmation.children > 0 ? `, ${confirmation.children} children` : ""}`],
              [tr("confirm.total"), `£${(confirmation.cart_total ?? confirmation.total_price)?.toFixed(0)}`],
            ].map(([l, v]) => <div key={l}><span className="text-slate-500 block mb-0.5">{l}</span><span className="font-semibold text-slate-800" data-testid={l === tr("confirm.guestName") ? "confirm-guest-name" : undefined}>{v}</span></div>)}
          </div>
          {confirmation.cart_items?.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-100 divide-y divide-gray-100" data-testid="confirm-cart-items">
              {confirmation.cart_items.map((it, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <div><span className="font-semibold text-slate-800">{it.qty}× {it.room_name}</span>{it.rate_plan_name && <span className="text-slate-500"> · {it.rate_plan_name}</span>}<div className="text-[11px] text-slate-400 font-mono">{it.booking_ref}</div></div>
                  <span className="font-semibold text-slate-800">£{Number(it.total).toFixed(0)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-6 pt-6 border-t border-gray-100 flex justify-center">
            <button onClick={onBookAnother}
              className="text-white px-6 py-3 rounded-lg font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="book-another-btn">
              {tr("confirm.bookAnother")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
