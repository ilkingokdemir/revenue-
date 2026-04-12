import { useState, useEffect } from "react";
import axios from "axios";
import { CheckCircle, CreditCard, Shield, Building2, ChevronDown } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PROVIDER_INFO = {
  iyzico: {
    name: "iyzico",
    tagline: "Turkey's Trusted Payment Platform",
    color: "#4F46E5",
    gradient: "from-indigo-600 to-violet-700",
    logo: "iyzico",
    banks: ["Garanti BBVA", "Yapı Kredi", "İş Bankası", "Akbank", "Ziraat", "QNB Finansbank", "Halkbank", "VakıfBank", "DenizBank"],
    features: ["3D Secure", "Taksit (Installments)", "All Turkish Banks", "BKM Express"],
  },
  paytr: {
    name: "PayTR",
    tagline: "Sanal POS - Virtual POS Turkey",
    color: "#DC2626",
    gradient: "from-red-600 to-rose-700",
    logo: "PayTR",
    banks: ["Garanti BBVA", "Yapı Kredi", "İş Bankası", "Akbank", "Ziraat", "Denizbank", "Halkbank", "VakıfBank"],
    features: ["3D Secure", "Taksitli Odeme", "SMS Payment", "Virtual POS"],
  },
};

const CURRENCY_SYMBOLS = { TRY: "₺", USD: "$", EUR: "€", GBP: "£" };

export default function TurkishPayPage() {
  const params = new URLSearchParams(window.location.search);
  const provider = params.get("provider") || "iyzico";
  const token = params.get("token") || "";
  const amount = parseFloat(params.get("amount") || "0");
  const currency = params.get("currency") || "TRY";
  const bookingRef = params.get("ref") || "";
  const guestName = decodeURIComponent(params.get("name") || "Guest");
  const maxInstallments = parseInt(params.get("installments") || "1");

  const [step, setStep] = useState("form"); // form, processing, success
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");
  const [cardName, setCardName] = useState(guestName);
  const [installment, setInstallment] = useState(1);
  const [showInstallments, setShowInstallments] = useState(false);
  const [processing, setProcessing] = useState(false);

  const info = PROVIDER_INFO[provider] || PROVIDER_INFO.iyzico;
  const sym = CURRENCY_SYMBOLS[currency] || currency + " ";

  const installmentOptions = [];
  for (let i = 1; i <= Math.min(maxInstallments, 12); i++) {
    if (i === 1 || [2, 3, 6, 9, 12].includes(i)) {
      const monthlyAmount = (amount / i).toFixed(2);
      installmentOptions.push({ value: i, label: i === 1 ? "Tek Cekim (Single Payment)" : `${i} Taksit — ${sym}${monthlyAmount}/ay`, monthly: monthlyAmount });
    }
  }

  const formatCard = (v) => {
    const digits = v.replace(/\D/g, "").slice(0, 16);
    return digits.replace(/(.{4})/g, "$1 ").trim();
  };
  const formatExpiry = (v) => {
    const digits = v.replace(/\D/g, "").slice(0, 4);
    if (digits.length > 2) return digits.slice(0, 2) + "/" + digits.slice(2);
    return digits;
  };

  const handlePay = async () => {
    if (!cardNumber || !expiry || !cvv || !cardName) return;
    setProcessing(true);
    setStep("processing");

    // Simulate 3D Secure verification delay
    await new Promise(r => setTimeout(r, 2500));

    try {
      await axios.post(`${API}/payments/turkish-demo-confirm`, { token, provider });
      setStep("success");
    } catch (e) {
      setStep("success"); // Show success anyway in demo mode
    }
  };

  if (step === "processing") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-10 text-center max-w-sm w-full">
          <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${info.gradient} flex items-center justify-center mx-auto mb-5`}>
            <Shield size={28} className="text-white" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">3D Secure Verification</h2>
          <p className="text-sm text-slate-500 mb-6">Connecting to your bank for verification...</p>
          <div className="w-10 h-10 border-3 border-slate-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-xs text-slate-400">Please do not close this page</p>
          <div className="mt-6 bg-slate-50 rounded-lg p-3 text-xs text-slate-500">
            <span className="font-medium">Demo Mode</span> — In production, your bank's 3D Secure page appears here
          </div>
        </div>
      </div>
    );
  }

  if (step === "success") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-10 text-center max-w-sm w-full" data-testid="turkish-pay-success">
          <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-5">
            <CheckCircle size={32} className="text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Odeme Basarili!</h2>
          <p className="text-base text-slate-600 mb-1">Payment Successful</p>
          <p className="text-sm text-slate-400 mb-6">Your payment has been processed via {info.name}</p>
          <div className="bg-slate-50 rounded-xl p-4 text-sm text-left space-y-2 border border-slate-100">
            <div className="flex justify-between"><span className="text-slate-500">Booking Ref</span><span className="font-bold text-slate-800">{bookingRef}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Amount</span><span className="font-bold text-emerald-600">{sym}{amount.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Provider</span><span className="font-medium text-slate-700">{info.name}</span></div>
            {installment > 1 && <div className="flex justify-between"><span className="text-slate-500">Installments</span><span className="font-medium text-slate-700">{installment} x {sym}{(amount/installment).toFixed(2)}</span></div>}
            <div className="flex justify-between"><span className="text-slate-500">Status</span><span className="font-semibold text-emerald-600">Paid</span></div>
          </div>
          <div className="mt-5 bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700">
            Demo Mode — With real {info.name} credentials, this processes actual bank payments
          </div>
          <p className="text-[11px] text-slate-400 mt-4">A confirmation email will be sent. You may close this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100" data-testid="turkish-pay-page">
      {/* Header */}
      <div className={`bg-gradient-to-r ${info.gradient} text-white`}>
        <div className="max-w-lg mx-auto px-4 py-5 flex items-center justify-between">
          <div>
            <div className="text-lg font-bold tracking-tight">{info.logo}</div>
            <div className="text-xs opacity-80">{info.tagline}</div>
          </div>
          <div className="flex items-center gap-1.5 text-xs bg-white/20 px-3 py-1.5 rounded-lg">
            <Shield size={12} /> 3D Secure
          </div>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 -mt-3 pb-8">
        {/* Amount Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider">Odeme Tutari / Payment Amount</div>
              <div className="text-3xl font-bold text-slate-900 mt-1">{sym}{amount.toFixed(2)}</div>
              <div className="text-xs text-slate-500 mt-0.5">Booking: {bookingRef} · {guestName}</div>
            </div>
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${info.gradient} flex items-center justify-center`}>
              <CreditCard size={22} className="text-white" />
            </div>
          </div>
        </div>

        {/* Card Form */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-4">
          <div className="bg-slate-50 border-b border-slate-200 px-5 py-3">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Kart Bilgileri / Card Details</span>
          </div>
          <div className="p-5 space-y-4">
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Kart Numarasi / Card Number</label>
              <input
                value={cardNumber}
                onChange={e => setCardNumber(formatCard(e.target.value))}
                placeholder="4242 4242 4242 4242"
                className="w-full border border-slate-300 rounded-lg px-4 py-3 text-base font-mono focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
                data-testid="card-number-input"
              />
              <div className="flex gap-2 mt-1.5">
                {["Visa", "MC", "Troy", "Amex"].map(c => (
                  <span key={c} className="text-[9px] px-2 py-0.5 bg-slate-100 text-slate-500 rounded font-medium">{c}</span>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1 block">Son Kullanma / Expiry</label>
                <input
                  value={expiry}
                  onChange={e => setExpiry(formatExpiry(e.target.value))}
                  placeholder="MM/YY"
                  className="w-full border border-slate-300 rounded-lg px-4 py-3 text-base font-mono focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
                  data-testid="expiry-input"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 mb-1 block">CVV / CVC</label>
                <input
                  value={cvv}
                  onChange={e => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  placeholder="123"
                  type="password"
                  className="w-full border border-slate-300 rounded-lg px-4 py-3 text-base font-mono focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none"
                  data-testid="cvv-input"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">Kart Sahibi / Cardholder Name</label>
              <input
                value={cardName}
                onChange={e => setCardName(e.target.value)}
                placeholder="MEHMET YILMAZ"
                className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 outline-none uppercase"
                data-testid="card-name-input"
              />
            </div>
          </div>
        </div>

        {/* Installments */}
        {installmentOptions.length > 1 && (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-4">
            <button
              onClick={() => setShowInstallments(!showInstallments)}
              className="w-full px-5 py-3 flex items-center justify-between text-left"
              data-testid="installments-toggle"
            >
              <div>
                <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider">Taksit Secenekleri / Installments</div>
                <div className="text-sm text-slate-800 mt-0.5 font-medium">
                  {installment === 1 ? "Tek Cekim (Single)" : `${installment} Taksit — ${sym}${(amount/installment).toFixed(2)}/month`}
                </div>
              </div>
              <ChevronDown size={16} className={`text-slate-400 transition-transform ${showInstallments ? "rotate-180" : ""}`} />
            </button>
            {showInstallments && (
              <div className="border-t border-slate-100 px-5 py-3 space-y-1">
                {installmentOptions.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => { setInstallment(opt.value); setShowInstallments(false); }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm flex justify-between items-center ${installment === opt.value ? "bg-indigo-50 text-indigo-700 font-semibold" : "text-slate-600 hover:bg-slate-50"}`}
                  >
                    <span>{opt.label}</span>
                    {opt.value > 1 && <span className="text-xs font-bold">{sym}{opt.monthly}/ay</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Supported Banks */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-4 mb-4">
          <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Desteklenen Bankalar / Supported Banks</div>
          <div className="flex flex-wrap gap-1.5">
            {info.banks.map(bank => (
              <span key={bank} className="text-[10px] px-2 py-1 bg-slate-50 text-slate-600 rounded-md border border-slate-100">{bank}</span>
            ))}
          </div>
        </div>

        {/* Pay Button */}
        <button
          onClick={handlePay}
          disabled={processing || !cardNumber || !expiry || !cvv || !cardName}
          className={`w-full bg-gradient-to-r ${info.gradient} text-white py-4 rounded-xl text-base font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-50 shadow-lg`}
          data-testid="turkish-pay-btn"
        >
          <CreditCard size={18} />
          {sym}{amount.toFixed(2)} Ode / Pay Now
        </button>

        {/* Trust Badges */}
        <div className="flex items-center justify-center gap-3 mt-4 text-[10px] text-slate-400">
          <span className="flex items-center gap-1"><Shield size={10} /> 3D Secure</span>
          <span>·</span>
          <span>256-bit SSL</span>
          <span>·</span>
          <span>PCI DSS</span>
          <span>·</span>
          <span>{info.name} Guvenli Odeme</span>
        </div>

        {/* Demo Notice */}
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-xl p-3 text-center text-xs text-amber-700">
          <span className="font-semibold">Demo Mode</span> — Use any card number (e.g. 4242 4242 4242 4242). With real {info.name} API credentials, this connects to actual Turkish bank networks.
        </div>
      </div>
    </div>
  );
}
