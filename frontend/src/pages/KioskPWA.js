/**
 * KioskPWA — Self-Service Check-In (iter 359, Mews-parity Batch 3 F2)
 * -------------------------------------------------------------------
 * Full-screen tablet interface. Route: /kiosk/:propertyId
 *
 * Flow: Splash → Lookup (booking ref / email / phone) → Details confirm
 *       → Signature → Room number + door code reveal → Auto-reset (30s).
 */
import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { Loader2, CheckCircle2, RefreshCw, Search, Sparkles, KeyRound, Home } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEPS = ["splash", "lookup", "confirm", "sign", "success"];

export default function KioskPWA() {
  const propertyId = (() => {
    // Route pattern: /kiosk/:propertyId — parsed manually since we have no
    // react-router installed at the app root.
    const parts = window.location.pathname.split("/").filter(Boolean);
    return parts[0] === "kiosk" ? parts[1] || "" : "";
  })();
  const [step, setStep] = useState("splash");
  const [config, setConfig] = useState(null);
  const [form, setForm] = useState({ booking_ref: "", email: "", phone: "" });
  const [candidate, setCandidate] = useState(null);
  const [signature, setSignature] = useState("");
  const [checkinResult, setCheckinResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const idleTimer = useRef(null);

  // Load property config for the splash
  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/kiosk/${propertyId}/config`).then(r => setConfig(r.data))
      .catch(() => setErr("Kiosk yapılandırması yüklenemedi."));
    // Auto-redeem QR token if arriving via /kiosk/{pid}?token=...
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      setBusy(true);
      axios.post(`${API}/kiosk/${propertyId}/qr-redeem`, { token })
        .then(r => { setCandidate(r.data.booking); setStep("confirm"); })
        .catch(e => setErr(e.response?.data?.detail || "QR token geçersiz."))
        .finally(() => setBusy(false));
    }
  }, [propertyId]);

  // Auto-reset if inactive on non-splash screens
  useEffect(() => {
    if (step === "splash") return;
    clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => resetAll(), step === "success" ? 30000 : 90000);
    return () => clearTimeout(idleTimer.current);
  }, [step]);

  const resetAll = useCallback(() => {
    setStep("splash"); setForm({ booking_ref: "", email: "", phone: "" });
    setCandidate(null); setSignature(""); setCheckinResult(null); setErr(null);
  }, []);

  const lookup = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await axios.post(`${API}/kiosk/${propertyId}/lookup`, form);
      if (!r.data.bookings.length) throw new Error("bulunamadı");
      setCandidate(r.data.bookings[0]);
      setStep("confirm");
    } catch (e) {
      setErr(e.response?.data?.detail || "Rezervasyon bulunamadı.");
    } finally { setBusy(false); }
  };

  const finalizeCheckin = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await axios.post(
        `${API}/kiosk/${propertyId}/checkin/${candidate.id}`,
        { signature, id_scan_ref: "" },
      );
      setCheckinResult(r.data);
      setStep("success");
    } catch (e) {
      setErr(e.response?.data?.detail || "Check-in başarısız.");
    } finally { setBusy(false); }
  };

  if (err && step === "splash" && !config) {
    return <FullscreenMsg>{err}</FullscreenMsg>;
  }
  if (!config) {
    return <FullscreenMsg><Loader2 className="w-8 h-8 animate-spin" /></FullscreenMsg>;
  }

  const brand = config.brand_color || "#4f46e5";

  return (
    <div
      className="min-h-screen w-full flex flex-col overflow-hidden"
      style={{ background: `linear-gradient(135deg, ${brand} 0%, #000 100%)` }}
      data-testid="kiosk-pwa"
    >
      {/* Header */}
      <header className="flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-3">
          {config.logo_url
            ? <img src={config.logo_url} alt="" className="w-10 h-10 rounded-lg object-cover bg-white/10" />
            : <div className="w-10 h-10 rounded-lg bg-white/15 flex items-center justify-center"><Home className="w-5 h-5 text-white" /></div>}
          <div>
            <h1 className="text-lg font-black text-white">{config.name}</h1>
            <p className="text-[10px] text-white/70">Self-service kiosk · {new Date().toLocaleTimeString("tr-TR")}</p>
          </div>
        </div>
        {step !== "splash" && step !== "success" && (
          <button
            onClick={resetAll}
            data-testid="kiosk-reset"
            className="text-xs px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white border border-white/20 inline-flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Baştan
          </button>
        )}
      </header>

      <main className="flex-1 flex items-center justify-center px-6 pb-8">
        {step === "splash" && (
          <div className="text-center max-w-md" data-testid="kiosk-splash">
            <div className="w-24 h-24 rounded-3xl bg-white/10 backdrop-blur-sm mx-auto flex items-center justify-center mb-6 shadow-2xl">
              <Sparkles className="w-12 h-12 text-white" />
            </div>
            <h2 className="text-5xl font-black text-white mb-3">Hoş Geldiniz</h2>
            <p className="text-lg text-white/85 mb-8">Ekrana dokunarak <b>self-service check-in</b> yapabilirsiniz.</p>
            <button
              onClick={() => setStep("lookup")}
              data-testid="kiosk-start"
              className="px-8 py-4 rounded-2xl bg-white text-black text-xl font-black shadow-2xl hover:scale-[1.03] active:scale-95 transition-transform"
            >
              Check-in Başlat →
            </button>
            <p className="mt-6 text-xs text-white/60">
              Check-in saati: {config.checkin_time} · Ödeme yapılmamışsa lütfen resepsiyona başvurun.
            </p>
          </div>
        )}

        {step === "lookup" && (
          <div className="w-full max-w-lg bg-white/95 backdrop-blur-sm rounded-3xl shadow-2xl p-8" data-testid="kiosk-lookup">
            <h2 className="text-3xl font-black text-stone-900 mb-1">Rezervasyonunuzu Bulun</h2>
            <p className="text-sm text-stone-500 mb-6">En az bir bilgi girmeniz yeterli.</p>
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs font-bold text-stone-700">Rezervasyon Kodu</span>
                <input
                  value={form.booking_ref}
                  onChange={e => setForm(f => ({ ...f, booking_ref: e.target.value.toUpperCase() }))}
                  placeholder="MHB-XXXX"
                  data-testid="kiosk-input-ref"
                  className="w-full mt-1 px-4 py-3 text-lg rounded-xl border-2 border-stone-200 focus:border-indigo-500 outline-none font-mono"
                />
              </label>
              <label className="block">
                <span className="text-xs font-bold text-stone-700">E-mail</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="ad@ornek.com"
                  data-testid="kiosk-input-email"
                  className="w-full mt-1 px-4 py-3 text-lg rounded-xl border-2 border-stone-200 focus:border-indigo-500 outline-none"
                />
              </label>
              <label className="block">
                <span className="text-xs font-bold text-stone-700">Telefon (son 6 hane)</span>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  placeholder="1234567"
                  data-testid="kiosk-input-phone"
                  className="w-full mt-1 px-4 py-3 text-lg rounded-xl border-2 border-stone-200 focus:border-indigo-500 outline-none"
                />
              </label>
            </div>
            {err && <p className="text-sm text-rose-600 font-bold mt-3">{err}</p>}
            <button
              onClick={lookup}
              disabled={busy || !(form.booking_ref || form.email || form.phone)}
              data-testid="kiosk-lookup-btn"
              className="w-full mt-5 py-4 rounded-2xl bg-black hover:bg-stone-800 text-white text-lg font-black disabled:opacity-40 inline-flex items-center justify-center gap-2"
            >
              {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              Rezervasyonu Bul
            </button>
          </div>
        )}

        {step === "confirm" && candidate && (
          <div className="w-full max-w-lg bg-white/95 backdrop-blur-sm rounded-3xl shadow-2xl p-8" data-testid="kiosk-confirm">
            <h2 className="text-3xl font-black text-stone-900 mb-1">Merhaba, {candidate.guest_name}</h2>
            <p className="text-sm text-stone-500 mb-5">Rezervasyon detaylarınızı onaylayın:</p>
            <div className="bg-stone-50 rounded-2xl p-5 space-y-2 text-sm">
              <Row k="Rezervasyon Kodu" v={candidate.booking_ref} />
              <Row k="Giriş" v={candidate.check_in} />
              <Row k="Çıkış" v={candidate.check_out} />
              <Row k="Oda Tipi" v={candidate.room_type || "—"} />
              <Row k="Yetişkin/Çocuk" v={`${candidate.adults || 0} / ${candidate.children || 0}`} />
              <Row k="Toplam" v={`${candidate.currency || "£"}${candidate.total_price || 0}`} />
              <Row k="Ödeme" v={candidate.payment_status || "—"} highlight={candidate.payment_status !== "paid"} />
            </div>
            {!candidate.ready_for_checkin && (
              <div className="mt-4 bg-amber-50 border border-amber-300 rounded-xl p-3 text-xs text-amber-900">
                ⚠️ Ödeme veya statü tamamlanmamış — resepsiyondan yardım isteyin.
              </div>
            )}
            {err && <p className="text-sm text-rose-600 font-bold mt-3">{err}</p>}
            <button
              onClick={() => setStep("sign")}
              disabled={!candidate.ready_for_checkin}
              data-testid="kiosk-confirm-btn"
              className="w-full mt-5 py-4 rounded-2xl bg-emerald-500 hover:bg-emerald-600 text-white text-lg font-black disabled:opacity-40"
            >
              Onaylıyorum → İmza
            </button>
          </div>
        )}

        {step === "sign" && (
          <div className="w-full max-w-lg bg-white/95 backdrop-blur-sm rounded-3xl shadow-2xl p-8" data-testid="kiosk-sign">
            <h2 className="text-3xl font-black text-stone-900 mb-1">Dijital İmza</h2>
            <p className="text-sm text-stone-500 mb-5">Aşağıya adınızı yazın veya ekrana çizin (basitleştirilmiş versiyon).</p>
            <textarea
              value={signature}
              onChange={e => setSignature(e.target.value)}
              placeholder="Ad Soyad · İmza yerine ad giriniz"
              data-testid="kiosk-signature"
              rows={3}
              className="w-full p-4 rounded-2xl border-2 border-stone-200 focus:border-indigo-500 outline-none text-lg italic"
            />
            {err && <p className="text-sm text-rose-600 font-bold mt-3">{err}</p>}
            <button
              onClick={finalizeCheckin}
              disabled={busy || signature.trim().length < 3}
              data-testid="kiosk-finalize"
              className="w-full mt-5 py-4 rounded-2xl bg-emerald-500 hover:bg-emerald-600 text-white text-lg font-black disabled:opacity-40 inline-flex items-center justify-center gap-2"
            >
              {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <CheckCircle2 className="w-5 h-5" />}
              Check-in&apos;i Tamamla
            </button>
          </div>
        )}

        {step === "success" && checkinResult && (
          <div className="text-center max-w-md" data-testid="kiosk-success">
            <div className="w-32 h-32 rounded-full bg-emerald-500 mx-auto flex items-center justify-center mb-6 shadow-2xl animate-in zoom-in duration-500">
              <CheckCircle2 className="w-20 h-20 text-white stroke-[2.5]" />
            </div>
            <h2 className="text-5xl font-black text-white mb-3">Check-in Tamamlandı!</h2>
            <p className="text-lg text-white/90 mb-8">Keyifli konaklamalar, {checkinResult.guest_name}.</p>

            <div className="bg-white/95 rounded-3xl p-6 shadow-2xl space-y-4">
              <div>
                <p className="text-xs text-stone-500 uppercase font-bold">Oda Numaranız</p>
                <p className="text-6xl font-black text-stone-900 tracking-tight" data-testid="kiosk-room-number">
                  {checkinResult.room_number}
                </p>
              </div>
              <div className="border-t border-stone-200 pt-4">
                <p className="text-xs text-stone-500 uppercase font-bold flex items-center justify-center gap-1">
                  <KeyRound className="w-3 h-3" /> Kapı Kodu
                </p>
                <p className="text-4xl font-black text-indigo-600 tracking-widest font-mono" data-testid="kiosk-door-code">
                  {checkinResult.door_code}
                </p>
              </div>
              <div className="border-t border-stone-200 pt-4 text-xs text-stone-500">
                <p>Çıkış: <b className="text-stone-900">{checkinResult.checkout_reminder}</b></p>
              </div>
            </div>

            <button
              onClick={resetAll}
              data-testid="kiosk-done"
              className="mt-8 px-6 py-3 rounded-2xl bg-white/20 backdrop-blur-sm text-white text-sm font-bold border border-white/30"
            >
              Bitir · 30sn sonra otomatik ↻
            </button>
          </div>
        )}
      </main>

      <footer className="text-center text-[10px] text-white/50 pb-3">
        {config.address} · {config.phone}
      </footer>
    </div>
  );
}

function FullscreenMsg({ children }) {
  return (
    <div className="min-h-screen bg-black flex items-center justify-center text-white text-lg">
      {children}
    </div>
  );
}

function Row({ k, v, highlight }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-stone-500">{k}</span>
      <span className={`font-bold ${highlight ? "text-amber-600" : "text-stone-900"}`}>{v}</span>
    </div>
  );
}
