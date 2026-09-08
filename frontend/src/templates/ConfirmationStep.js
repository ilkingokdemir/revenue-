import { CheckCircle } from "@phosphor-icons/react";
import { useState, useEffect } from "react";
import axios from "axios";
import { useLanguage } from "../i18n/LanguageContext";
import { InlinePayment } from "./InlinePayment";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function PostUpsells({ t, confirmation, fmt }) {
  const { t: tr } = useLanguage();
  const [items, setItems] = useState([]);
  const [added, setAdded] = useState({});
  const [unpaid, setUnpaid] = useState(0);
  const [payMode, setPayMode] = useState("");
  const [paidInfo, setPaidInfo] = useState(null);
  const [inlineOk, setInlineOk] = useState(false);
  useEffect(() => {
    axios.get(`${API}/upsells/${confirmation.property_id}`).then(({ data }) => setItems((Array.isArray(data) ? data : data.items || []).slice(0, 4))).catch(() => {});
    axios.get(`${API}/payments/config`).then(({ data }) => setInlineOk(!!data.inline_enabled)).catch(() => {});
  }, [confirmation.property_id]);
  if (!items.length) return null;
  const ident = { booking_ref: confirmation.booking_ref, guest_email: confirmation.guest_email };
  const add = async (u) => {
    try {
      const { data } = await axios.post(`${API}/booking/${confirmation.booking_ref}/add-upsell`, { upsell_id: u.id, guest_email: confirmation.guest_email });
      setAdded((a) => ({ ...a, [u.id]: data.added?.price ?? u.price }));
      setUnpaid(data.upsell_unpaid_total ?? 0); setPaidInfo(null); setPayMode("");
    } catch { /* ignore */ }
  };
  const onPaid = (d) => { setPaidInfo(d); setUnpaid(0); setPayMode(""); };
  return (
    <div className="mt-6 text-left w-full" data-testid="post-upsells">
      <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{tr("post.title")}</div>
      <div className="grid sm:grid-cols-2 gap-2">
        {items.map((u) => (
          <div key={u.id} className="flex items-center justify-between gap-3 border border-gray-200 rounded-lg px-3 py-2.5" style={{ borderRadius: t.borderRadius }} data-testid={`post-upsell-${u.id}`}>
            <div className="min-w-0"><div className="text-sm font-semibold text-slate-800 truncate">{u.name}</div><div className="text-[11px] text-slate-500">{fmt(u.price)}{u.price_type === "per_night" ? ` / ${tr("room.night")}` : ""}</div></div>
            {added[u.id] != null ? <span className="text-xs font-bold" style={{ color: t.colors.success }} data-testid={`post-upsell-added-${u.id}`}>✓ {tr("plan.added")}</span>
              : <button onClick={() => add(u)} className="px-3 py-1.5 rounded-lg text-xs font-bold text-white" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid={`post-upsell-add-${u.id}`}>+ {tr("post.add")}</button>}
          </div>
        ))}
      </div>
      {paidInfo && <p className="text-xs font-semibold mt-3" style={{ color: t.colors.success }} data-testid="post-upsell-paid">✓ {tr("post.paid", { amount: fmt(paidInfo.amount) })}</p>}
      {unpaid > 0 && !paidInfo && payMode !== "card" && (
        <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="post-upsell-pay-options">
          {inlineOk && <button onClick={() => setPayMode("card")} className="px-3 py-2 rounded-lg text-xs font-bold text-white" style={{ background: t.colors.primary, borderRadius: t.borderRadius }} data-testid="post-upsell-pay-card-btn">{tr("post.payNow", { amount: fmt(unpaid) })}</button>}
          <button onClick={() => setPayMode("hotel")} className={`px-3 py-2 rounded-lg text-xs font-semibold border ${payMode === "hotel" ? "border-slate-800 text-slate-800" : "border-gray-200 text-slate-500"}`} style={{ borderRadius: t.borderRadius }} data-testid="post-upsell-pay-hotel-btn">{tr("post.payAtProperty")}</button>
        </div>
      )}
      {payMode === "card" && unpaid > 0 && !paidInfo && (
        <div className="mt-3" data-testid="post-upsell-inline-pay">
          <InlinePayment t={t} booking={{ id: confirmation.booking_ref, booking_ref: confirmation.booking_ref, property_id: confirmation.property_id }} fmt={fmt} compact title={tr("post.payTitle")} payLabel={(a) => tr("post.payNow", { amount: a })}
            createIntent={() => axios.post(`${API}/payments/upsell-intent`, ident)} confirmIntent={(piId) => axios.post(`${API}/payments/upsell-intent/confirm`, { ...ident, payment_intent_id: piId })}
            onPaid={onPaid} onFallback={() => setPayMode("hotel")} />
        </div>
      )}
      {Object.keys(added).length > 0 && !paidInfo && payMode !== "card" && <p className="text-[11px] text-slate-500 mt-2" data-testid="post-upsell-note">{tr("post.note")}</p>}
    </div>
  );
}

export function ConfirmationStep({ t, confirmation, onBookAnother, fmt = (v) => `£${Math.round(v)}` }) {
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
              [tr("confirm.total"), fmt(confirmation.cart_total ?? confirmation.total_price ?? 0)],
            ].map(([l, v]) => <div key={l}><span className="text-slate-500 block mb-0.5">{l}</span><span className="font-semibold text-slate-800" data-testid={l === tr("confirm.guestName") ? "confirm-guest-name" : undefined}>{v}</span></div>)}
          </div>
          {confirmation.cart_items?.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-100 divide-y divide-gray-100" data-testid="confirm-cart-items">
              {confirmation.cart_items.map((it, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-2.5 text-sm">
                  <div><span className="font-semibold text-slate-800">{it.qty}× {it.room_name}</span>{it.rate_plan_name && <span className="text-slate-500"> · {it.rate_plan_name}</span>}<div className="text-[11px] text-slate-400 font-mono">{it.booking_ref}</div></div>
                  <span className="font-semibold text-slate-800">{fmt(Number(it.total))}</span>
                </div>
              ))}
            </div>
          )}
          {confirmation.status === "hold" && confirmation.hold_expires_at && <p className="text-xs font-semibold rounded-lg px-3 py-2 mb-3" style={{ background: "#fef3c7", color: "#92400e" }} data-testid="confirm-hold-note">⏳ {tr("confirm.holdNote", { until: new Date(confirmation.hold_expires_at).toLocaleString() })}</p>}
          <div className="pt-2 border-t border-gray-100">
            <PostUpsells t={t} confirmation={confirmation} fmt={fmt} />
          </div>
          <div className="mt-6 pt-6 border-t border-gray-100 flex flex-col items-center">
          {(confirmation.manage_url || confirmation.booking_ref) && (
            <a href={confirmation.manage_url || `/guest-portal-v2?ref=${confirmation.booking_ref}&email=${encodeURIComponent(confirmation.guest_email || "")}`} className="inline-flex items-center justify-center gap-2 w-full py-3 rounded-lg font-semibold text-sm border-2 mb-3" style={{ borderColor: t.colors.accent, color: t.colors.accent, borderRadius: t.borderRadius }} data-testid="manage-booking-link">{tr("confirm.manage")} →</a>
          )}
          {confirmation.booking_ref && (
            <a href={`/pass/${confirmation.booking_ref}?email=${encodeURIComponent(confirmation.guest_email || "")}`} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-2 w-full py-3 rounded-lg font-semibold text-sm text-white mb-3" style={{ background: "#111", borderRadius: t.borderRadius }} data-testid="wallet-pass-link">📲 {tr("confirm.wallet")}</a>
          )}
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
