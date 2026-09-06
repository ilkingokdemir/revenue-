import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Lock, CreditCard } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function loadStripeJs() {
  return new Promise((res, rej) => {
    if (window.Stripe) return res(window.Stripe);
    const s = document.createElement("script"); s.src = "https://js.stripe.com/v3/"; s.async = true;
    s.onload = () => res(window.Stripe); s.onerror = rej; document.head.appendChild(s);
  });
}

export function InlinePayment({ t, booking, amountMode, fmt, onPaid, onFallback }) {
  const { t: tr, lang } = useLanguage();
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [amount, setAmount] = useState(0);
  const stripeRef = useRef(null); const elementsRef = useRef(null); const mounted = useRef(false);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const { data } = await axios.post(`${API}/payments/intent`, { booking_id: booking.id, amount_mode: amountMode });
        const Stripe = await loadStripeJs();
        if (!live) return;
        setAmount(data.amount);
        const stripe = Stripe(data.publishable_key);
        const elements = stripe.elements({ clientSecret: data.client_secret, locale: lang === "tr" ? "tr" : lang === "de" ? "de" : "en",
          appearance: { theme: "stripe", variables: { colorPrimary: t.colors.accent, borderRadius: t.borderRadius, fontFamily: "system-ui, sans-serif" } } });
        const el = elements.create("payment", { layout: "tabs", wallets: { applePay: "auto", googlePay: "auto" } });
        el.mount("#mhb-payment-element");
        el.on("ready", () => setState("ready"));
        stripeRef.current = stripe; elementsRef.current = elements; mounted.current = true;
      } catch (e) {
        setErr(e.response?.data?.detail || "Stripe yüklenemedi"); setState("error");
      }
    })();
    return () => { live = false; };
  }, [booking.id, amountMode, lang, t.colors.accent, t.borderRadius]);

  const pay = async () => {
    if (!stripeRef.current || !elementsRef.current) return;
    setState("paying"); setErr("");
    const { error } = await stripeRef.current.confirmPayment({ elements: elementsRef.current, redirect: "if_required",
      confirmParams: { return_url: `${window.location.origin}/book?property=${booking.property_id}&booking_ref=${booking.booking_ref}&payment=success` } });
    if (error) { setErr(error.message); setState("ready"); return; }
    try {
      const { data } = await axios.post(`${API}/payments/intent/confirm`, { booking_id: booking.id });
      if (data.paid) onPaid(data); else { setErr(tr("inline.pending")); setState("ready"); }
    } catch { setErr(tr("inline.pending")); setState("ready"); }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-10" data-testid="inline-payment-step">
      <div className="bg-white border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2" style={{ fontFamily: t.fonts.heading }}><CreditCard size={20} style={{ color: t.colors.accent }} /> {tr("inline.title")}</h2>
          <span className="text-xs text-slate-500 font-mono">{booking.booking_ref}</span>
        </div>
        <div className="flex items-baseline justify-between mb-4 pb-4 border-b border-gray-100">
          <span className="text-sm text-slate-500">{tr("inline.amount")}</span>
          <span className="text-2xl font-bold text-slate-900" data-testid="inline-amount">{amount ? fmt(amount) : "…"}</span>
        </div>
        {state === "loading" && <div className="h-24 flex items-center justify-center text-sm text-slate-400" data-testid="inline-loading">{tr("loading")}</div>}
        <div id="mhb-payment-element" data-testid="inline-payment-element" />
        {err && <p className="text-sm text-red-600 mt-3" role="alert" data-testid="inline-error">{err}</p>}
        {state === "error" ? (
          <button onClick={onFallback} className="mt-4 w-full py-3 rounded-lg font-semibold text-white text-sm" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="inline-fallback-btn">{tr("inline.fallback")}</button>
        ) : (
          <button onClick={pay} disabled={state !== "ready"} className="mt-4 w-full py-3.5 rounded-lg font-bold text-white text-sm flex items-center justify-center gap-2 disabled:opacity-50" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="inline-pay-btn">
            <Lock size={16} weight="fill" /> {state === "paying" ? tr("processing.title") : tr("payment.payAndComplete", { amount: amount ? fmt(amount).replace(/^[^\d]*/, "") : "" })}
          </button>
        )}
        <p className="text-[11px] text-slate-400 text-center mt-3">{tr("inline.secure")}</p>
      </div>
    </div>
  );
}
