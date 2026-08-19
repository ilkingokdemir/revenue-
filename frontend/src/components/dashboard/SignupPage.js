import { useState } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Buildings, ChartLineUp, Plugs, Stack, ArrowRight } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PLAN_CARDS = [
  { k: "rms", icon: ChartLineUp, t: "RMS", d: "Sadece Gelir Yönetimi — AI fiyatlama, forecast, rakip takibi. 30 dk'da canlı.", badge: "En popüler" },
  { k: "cm", icon: Plugs, t: "Channel Manager", d: "Sadece dağıtım — OTA bağlantıları, oda eşleme, booking engine." },
  { k: "pro", icon: Stack, t: "PRO Paket", d: "PMS + gelir + kanallar + raporlar. Tam operasyon (~150 modül)." },
];

function formatApiErrorDetail(detail) {
  if (detail == null) return "Bir şeyler ters gitti. Tekrar deneyin.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  return String(detail);
}

export default function SignupPage({ onLogin }) {
  const [plan, setPlan] = useState("rms");
  const [form, setForm] = useState({ hotel_name: "", name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      const { data } = await axios.post(`${API}/auth/signup`, { ...form, plan }, { withCredentials: true });
      try {
        localStorage.setItem("active-property-id", data.property_id);
        localStorage.setItem("mhb_post_signup_view", plan === "cm" ? "cm-setup" : "rms-setup");
      } catch { /* ignore */ }
      toast.success("Hesabınız hazır! Kurulum sihirbazına yönlendiriliyorsunuz...");
      window.history.replaceState({}, "", "/");
      onLogin(data);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    }
    setBusy(false);
  };

  const inputCls = "w-full rounded-lg border border-stone-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]";

  return (
    <div className="min-h-screen bg-stone-950 flex items-center justify-center p-4" data-testid="signup-page">
      <Toaster position="top-right" richColors />
      <div className="w-full max-w-3xl">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#1D4ED8] to-[#06B6D4] flex items-center justify-center">
              <Buildings size={18} weight="fill" className="text-white" />
            </div>
            <span className="text-lg font-black text-white">MyHotelBox</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">Hesabınızı açın, 30 dakikada canlıya alın</h1>
          <p className="text-sm text-stone-400 mt-2">Kredi kartı gerekmez · Kurulum sihirbazı sizi adım adım yönlendirir</p>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-6">
          {PLAN_CARDS.map((p) => (
            <button key={p.k} onClick={() => setPlan(p.k)} data-testid={`signup-plan-${p.k}`}
              className={`relative text-left rounded-2xl border-2 p-4 transition-colors ${
                plan === p.k ? "border-cyan-400 bg-cyan-400/10" : "border-stone-700 hover:border-stone-500 bg-stone-900"}`}>
              {p.badge && <span className="absolute -top-2 right-3 text-[9px] font-black uppercase bg-cyan-400 text-stone-950 px-2 py-0.5 rounded-full">{p.badge}</span>}
              <p.icon size={20} weight="bold" className={plan === p.k ? "text-cyan-300" : "text-stone-400"} />
              <div className="text-sm font-bold text-white mt-2">{p.t}</div>
              <div className="text-[10px] text-stone-400 mt-1 leading-relaxed">{p.d}</div>
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="bg-white rounded-2xl p-6 shadow-2xl space-y-3" data-testid="signup-form">
          <div className="grid sm:grid-cols-2 gap-3">
            <input required value={form.hotel_name} placeholder="Otel adı" data-testid="signup-hotel-input"
              onChange={(e) => setForm({ ...form, hotel_name: e.target.value })} className={inputCls} />
            <input required value={form.name} placeholder="Ad Soyad" data-testid="signup-name-input"
              onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
            <input required type="email" value={form.email} placeholder="E-posta" data-testid="signup-email-input"
              onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputCls} />
            <input required type="password" value={form.password} placeholder="Şifre (en az 8 karakter)" data-testid="signup-password-input"
              onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputCls} />
          </div>
          {error && <p className="text-xs text-red-600 font-semibold" data-testid="signup-error">{error}</p>}
          <button type="submit" disabled={busy} data-testid="signup-submit-btn"
            className="w-full py-3 rounded-xl bg-gradient-to-r from-[#1D4ED8] to-[#06B6D4] text-white text-sm font-black hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
            {busy ? "Hesap açılıyor..." : `${plan.toUpperCase()} ile Başla`} <ArrowRight size={15} weight="bold" />
          </button>
          <p className="text-center text-[11px] text-stone-400">
            Zaten hesabınız var mı? <a href="/login" className="text-[#1D4ED8] font-bold hover:underline" data-testid="signup-login-link">Giriş yapın</a>
          </p>
        </form>
      </div>
    </div>
  );
}
