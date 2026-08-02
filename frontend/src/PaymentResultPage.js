import { useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle, XCircle, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PaymentResultPage() {
  const isSuccess = window.location.pathname === "/payment/success";
  const sessionId = new URLSearchParams(window.location.search).get("session_id");
  const [status, setStatus] = useState(isSuccess ? "checking" : "cancelled");

  useEffect(() => {
    if (!isSuccess || !sessionId) { if (isSuccess) setStatus("unknown"); return; }
    let attempts = 0;
    let timer;
    const poll = async () => {
      attempts += 1;
      try {
        const { data } = await axios.get(`${API}/pay-links/status/${sessionId}`);
        if (data.payment_status === "paid") { setStatus("paid"); return; }
        if (["failed", "expired"].includes(data.payment_status)) { setStatus("failed"); return; }
      } catch (e) { /* keep polling */ }
      if (attempts < 8) timer = setTimeout(poll, 2500);
      else setStatus("pending");
    };
    poll();
    return () => clearTimeout(timer);
  }, [isSuccess, sessionId]);

  const cfg = {
    checking: { icon: Clock, color: "text-amber-500", bg: "bg-amber-50", title: "Verifying your payment…", sub: "Please wait a moment while we confirm with the bank." },
    paid: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-50", title: "Payment successful!", sub: "Thank you. Your payment has been received and your booking is updated." },
    pending: { icon: Clock, color: "text-amber-500", bg: "bg-amber-50", title: "Payment processing", sub: "Your payment is being processed. You will receive confirmation shortly." },
    failed: { icon: XCircle, color: "text-red-500", bg: "bg-red-50", title: "Payment failed", sub: "The payment could not be completed. Please contact the hotel for a new link." },
    cancelled: { icon: XCircle, color: "text-stone-400", bg: "bg-stone-100", title: "Payment cancelled", sub: "No charge was made. You can retry using the same payment link." },
    unknown: { icon: XCircle, color: "text-stone-400", bg: "bg-stone-100", title: "Missing payment session", sub: "This page requires a valid payment session." },
  }[status];
  const Icon = cfg.icon;

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6" data-testid="payment-result-page">
      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm p-10 max-w-md w-full text-center">
        <div className={`w-16 h-16 ${cfg.bg} rounded-full flex items-center justify-center mx-auto mb-4`}>
          <Icon size={32} className={`${cfg.color} ${status === "checking" ? "animate-pulse" : ""}`} />
        </div>
        <h1 className="text-xl font-bold text-stone-900 mb-2" data-testid="payment-result-title">{cfg.title}</h1>
        <p className="text-sm text-stone-500">{cfg.sub}</p>
        {sessionId && <p className="text-[10px] text-stone-300 mt-6 font-mono truncate">Ref: {sessionId}</p>}
      </div>
    </div>
  );
}
