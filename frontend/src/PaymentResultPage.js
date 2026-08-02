import { useEffect, useState } from "react";
import axios from "axios";
import { CheckCircle, XCircle, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const I18N = {
  en: {
    checking: ["Verifying your payment…", "Please wait a moment while we confirm with the bank."],
    paid: ["Payment successful!", "Thank you. Your payment has been received and your booking is updated."],
    pending: ["Payment processing", "Your payment is being processed. You will receive confirmation shortly."],
    failed: ["Payment failed", "The payment could not be completed. Please contact the hotel for a new link."],
    cancelled: ["Payment cancelled", "No charge was made. You can retry using the same payment link."],
    unknown: ["Missing payment session", "This page requires a valid payment session."],
  },
  tr: {
    checking: ["Ödemeniz doğrulanıyor…", "Banka onayı alınırken lütfen bekleyin."],
    paid: ["Ödeme başarılı!", "Teşekkürler. Ödemeniz alındı ve rezervasyonunuz güncellendi."],
    pending: ["Ödeme işleniyor", "Ödemeniz işleniyor. Kısa süre içinde onay alacaksınız."],
    failed: ["Ödeme başarısız", "Ödeme tamamlanamadı. Yeni bir bağlantı için lütfen otelle iletişime geçin."],
    cancelled: ["Ödeme iptal edildi", "Herhangi bir tahsilat yapılmadı. Aynı bağlantıyla tekrar deneyebilirsiniz."],
    unknown: ["Geçersiz ödeme oturumu", "Bu sayfa geçerli bir ödeme oturumu gerektirir."],
  },
  de: {
    checking: ["Ihre Zahlung wird überprüft…", "Bitte warten Sie einen Moment, während wir die Bank bestätigen."],
    paid: ["Zahlung erfolgreich!", "Vielen Dank. Ihre Zahlung ist eingegangen und Ihre Buchung wurde aktualisiert."],
    pending: ["Zahlung in Bearbeitung", "Ihre Zahlung wird bearbeitet. Sie erhalten in Kürze eine Bestätigung."],
    failed: ["Zahlung fehlgeschlagen", "Die Zahlung konnte nicht abgeschlossen werden. Bitte kontaktieren Sie das Hotel."],
    cancelled: ["Zahlung abgebrochen", "Es wurde nichts abgebucht. Sie können es mit demselben Link erneut versuchen."],
    unknown: ["Ungültige Zahlungssitzung", "Diese Seite erfordert eine gültige Zahlungssitzung."],
  },
};

const detectLang = () => {
  const p = new URLSearchParams(window.location.search).get("lang");
  if (p && I18N[p]) return p;
  const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
  return I18N[nav] ? nav : "en";
};

export default function PaymentResultPage() {
  const isSuccess = window.location.pathname === "/payment/success";
  const sessionId = new URLSearchParams(window.location.search).get("session_id");
  const [status, setStatus] = useState(isSuccess ? "checking" : "cancelled");
  const t = I18N[detectLang()];

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

  const icons = {
    checking: [Clock, "text-amber-500", "bg-amber-50"],
    paid: [CheckCircle, "text-emerald-500", "bg-emerald-50"],
    pending: [Clock, "text-amber-500", "bg-amber-50"],
    failed: [XCircle, "text-red-500", "bg-red-50"],
    cancelled: [XCircle, "text-stone-400", "bg-stone-100"],
    unknown: [XCircle, "text-stone-400", "bg-stone-100"],
  };
  const [Icon, color, bg] = icons[status];
  const [title, sub] = t[status];

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6" data-testid="payment-result-page">
      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm p-10 max-w-md w-full text-center">
        <div className={`w-16 h-16 ${bg} rounded-full flex items-center justify-center mx-auto mb-4`}>
          <Icon size={32} className={`${color} ${status === "checking" ? "animate-pulse" : ""}`} />
        </div>
        <h1 className="text-xl font-bold text-stone-900 mb-2" data-testid="payment-result-title">{title}</h1>
        <p className="text-sm text-stone-500">{sub}</p>
        {sessionId && <p className="text-[10px] text-stone-300 mt-6 font-mono truncate">Ref: {sessionId}</p>}
      </div>
    </div>
  );
}
