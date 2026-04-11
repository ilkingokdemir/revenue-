import { CheckCircle } from "@phosphor-icons/react";

export function ConfirmationStep({ t, confirmation, onBookAnother }) {
  if (!confirmation) return null;
  return (
    <div className="max-w-3xl mx-auto px-4 py-12" data-testid="confirmation-step">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden" style={{ borderRadius: t.borderRadius }}>
        <div className="text-white px-8 py-6 text-center" style={{ background: t.colors.success }}>
          <CheckCircle size={48} weight="fill" className="mx-auto mb-3" />
          <h2 className="text-2xl font-bold mb-1" style={{ fontFamily: t.fonts.heading }}>Booking Confirmed!</h2>
          <p style={{ opacity: 0.8 }}>{confirmation.payment_status === "paid" ? "Payment received" : "Your reservation is confirmed"}</p>
        </div>
        <div className="p-8">
          <div className="rounded-lg p-5 mb-6 text-center" style={{ background: t.colors.bodyBg }}>
            <div className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-1">Booking Reference</div>
            <div className="text-3xl font-bold tracking-wider" style={{ color: t.colors.primary }} data-testid="booking-ref">{confirmation.booking_ref}</div>
            <p className="text-xs text-slate-500 mt-2">Save this reference for your records</p>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {[
              ["Guest Name", confirmation.guest_name],
              ["Email", confirmation.guest_email],
              ["Check-in", new Date(confirmation.check_in).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
              ["Check-out", new Date(confirmation.check_out).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })],
              ["Guests", `${confirmation.adults} adult${confirmation.adults !== 1 ? "s" : ""}${confirmation.children > 0 ? `, ${confirmation.children} children` : ""}`],
              ["Total", `£${confirmation.total_price?.toFixed(0)}`],
            ].map(([l, v]) => <div key={l}><span className="text-slate-500 block mb-0.5">{l}</span><span className="font-semibold text-slate-800" data-testid={l === "Guest Name" ? "confirm-guest-name" : undefined}>{v}</span></div>)}
          </div>
          <div className="mt-6 pt-6 border-t border-gray-100 flex justify-center">
            <button onClick={onBookAnother}
              className="text-white px-6 py-3 rounded-lg font-semibold transition-colors" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="book-another-btn">
              Book Another Room
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
