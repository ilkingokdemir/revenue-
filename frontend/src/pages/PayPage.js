import { useEffect, useState } from "react";
import axios from "axios";
import { InlinePayment } from "../templates/InlinePayment";
import { TEMPLATES } from "../templates/templateConfig";
import { LanguageProvider } from "../i18n/LanguageContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmt = (v, cur = "GBP") => new Intl.NumberFormat("en-GB", { style: "currency", currency: cur }).format(Number(v || 0));

export default function PayPage({ mode }) {
  return <LanguageProvider><PayPageInner mode={mode} /></LanguageProvider>;
}

function PayPageInner({ mode }) {
  const seg = window.location.pathname.split("/").filter(Boolean);
  const ref = mode === "share" ? "" : decodeURIComponent(seg[1] || ""); const token = mode === "share" ? decodeURIComponent(seg[1] || "") : "";
  const email = new URLSearchParams(window.location.search).get("email") || "";
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);
  const t = TEMPLATES["booking-classic"];

  useEffect(() => {
    const url = mode === "share" ? `${API}/booking/split/${token}` : `${API}/booking/payment-schedule/${ref}?email=${encodeURIComponent(email)}`;
    axios.get(url).then((r) => setInfo(r.data)).catch((e) => setErr(e.response?.data?.detail || "Bağlantı geçersiz"));
  }, [mode, ref, token, email]);

  if (err) return <div className="min-h-screen flex items-center justify-center text-slate-600" data-testid="pay-page-error">{err}</div>;
  if (!info) return <div className="min-h-screen flex items-center justify-center text-slate-400">Yükleniyor…</div>;
  const amount = mode === "share" ? info.amount : info.balance_due;
  const cur = info.currency || "GBP";
  const paid = done || (mode === "share" ? info.status === "paid" : !(info.balance_due > 0));
  const createIntent = () => (mode === "share" ? axios.post(`${API}/booking/split/${token}/intent`) : axios.post(`${API}/booking/payment-schedule/${ref}/pay-now`, { email }));
  const confirmIntent = () => (mode === "share" ? axios.post(`${API}/booking/split/${token}/confirm`, {}) : axios.post(`${API}/booking/payment-schedule/${ref}/confirm`, { email }));
  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4" data-testid="pay-page">
      <div className="max-w-xl mx-auto bg-white rounded-2xl border border-slate-200 p-6">
        <h1 className="text-xl font-bold text-slate-900">{mode === "share" ? "Rezervasyon payınızı ödeyin" : "Kalan bakiyeyi ödeyin"}</h1>
        <div className="text-sm text-slate-600 mt-1" data-testid="pay-page-summary">
          {mode === "share" ? <>{info.host_name} · {info.property_name} · {info.room_name} · {info.check_in} → {info.check_out}</> : <>Rezervasyon <b>{info.booking_ref}</b> · Ödenen {fmt(info.deposit_paid, cur)} · Toplam {fmt(info.total, cur)}</>}
        </div>
        <div className="text-3xl font-black mt-3" style={{ color: t.colors.accent }} data-testid="pay-page-amount">{fmt(amount, cur)}</div>
        {mode === "share" && info.parts?.length > 1 && <div className="text-xs text-slate-500 mt-1" data-testid="pay-page-parts">{info.parts.filter((p) => p.status === "paid").length}/{info.parts.length} pay ödendi</div>}
        {paid ? <div className="mt-4 rounded-lg bg-emerald-50 border border-emerald-200 p-4 text-emerald-800 font-semibold" data-testid="pay-page-paid">✓ Ödeme alındı. Teşekkürler!</div> : (
          <div className="mt-4">
            <InlinePayment t={t} booking={{ id: mode === "share" ? token : info.id, booking_ref: info.booking_ref, property_id: info.property_id }} amountMode="full" fmt={(v) => fmt(v, cur)} compact
              createIntent={createIntent} confirmIntent={confirmIntent} onPaid={() => setDone(true)} payLabel={() => `${fmt(amount, cur)} öde`} />
          </div>
        )}
      </div>
    </div>
  );
}
