import { useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { Search, TrendingUp, CalendarDays, BarChart3, ArrowRight } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" },
};

export default function PriceCheckerSection({ onDemo }) {
  const [city, setCity] = useState("");
  const [rooms, setRooms] = useState("");
  const [email, setEmail] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const check = async () => {
    if (!city.trim()) { setError("Şehir girin"); return; }
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/api/public/price-check`, {
        city: city.trim(),
        room_count: rooms ? parseInt(rooms, 10) : null,
        email: email.trim() || null,
      });
      setResult(r.data);
    } catch (e) {
      setError(e?.response?.status === 429 ? "Çok fazla sorgu — bir saat sonra tekrar deneyin" : "Kontrol başarısız, tekrar deneyin");
    } finally { setBusy(false); }
  };

  return (
    <section id="price-checker" className="relative border-t border-white/10 bg-[#070B14] py-24 overflow-hidden">
      <div className="absolute top-[-80px] right-[15%] w-[360px] h-[360px] rounded-full bg-[#2563EB]/14 blur-3xl" aria-hidden="true" />
      <div className="relative max-w-7xl mx-auto px-5 sm:px-8 grid lg:grid-cols-12 gap-12 items-center">
        <motion.div {...fadeUp} className="lg:col-span-5">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-400 mb-3">Ücretsiz Price Checker</div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight text-white">
            Pazarınızın <span className="bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">fiyat aralığını</span> 10 saniyede görün
          </h2>
          <p className="mt-4 text-stone-400 leading-relaxed">
            Şehrinizi girin — çevrenizdeki otel ve kısa dönem kiralama pazarının medyan fiyatını, hafta sonu artışını ve gelir potansiyelinizi anında gösterelim.
          </p>
          <div className="mt-8 space-y-3">
            <div className="flex gap-2">
              <input value={city} onChange={(e) => setCity(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && check()}
                placeholder="Şehir (örn. İstanbul, Londra, Berlin)"
                data-testid="price-checker-city"
                className="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/15 text-sm text-white placeholder-stone-500 focus:outline-none focus:border-blue-400" />
              <input value={rooms} onChange={(e) => setRooms(e.target.value.replace(/\D/g, ""))}
                placeholder="Oda"
                data-testid="price-checker-rooms"
                className="w-20 px-3 py-3 rounded-xl bg-white/5 border border-white/15 text-sm text-white placeholder-stone-500 focus:outline-none focus:border-blue-400" />
            </div>
            <input value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="E-posta (opsiyonel — raporu gönderelim, demo daveti alın)"
              data-testid="price-checker-email"
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/15 text-sm text-white placeholder-stone-500 focus:outline-none focus:border-blue-400" />
            <button onClick={check} disabled={busy} data-testid="price-checker-submit"
              className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-500 to-cyan-400 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50 inline-flex items-center justify-center gap-2 transition-opacity">
              <Search size={16} /> {busy ? "Kontrol ediliyor…" : "Pazarımı Kontrol Et"}
            </button>
            {error && <div className="text-xs text-rose-400" data-testid="price-checker-error">{error}</div>}
          </div>
        </motion.div>

        <motion.div {...fadeUp} className="lg:col-span-7">
          {!result ? (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-10 text-center text-stone-500 text-sm" data-testid="price-checker-placeholder">
              <BarChart3 size={40} className="mx-auto mb-4 text-stone-600" />
              Sonuçlar burada görünecek — şehrinizi girin ve pazarınızı keşfedin.
            </div>
          ) : (
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 backdrop-blur" data-testid="price-checker-result">
              <div className="text-sm font-semibold text-white mb-4">
                {result.city} pazarı · {result.hotel_sample_size} otel + {result.str_sample_size} STR ilanı
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
                <Stat label="Pazar Medyanı" value={`€${result.market_median}`} testId="pc-median" />
                <Stat label="Fiyat Bandı" value={`€${result.market_min}–€${result.market_max}`} testId="pc-band" />
                <Stat label="Hafta Sonu Artışı" value={`+%${result.weekend_uplift_pct}`} icon={CalendarDays} testId="pc-weekend" />
                <Stat label="90 Günde Etkinlik" value={`${result.event_days_next_90} gün`} testId="pc-events" />
              </div>
              <div className="rounded-xl bg-gradient-to-r from-emerald-500/15 to-blue-500/10 border border-emerald-400/25 p-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs text-emerald-300 font-semibold uppercase tracking-wider mb-1 inline-flex items-center gap-1.5">
                    <TrendingUp size={13} /> Dinamik fiyatlama potansiyeli
                  </div>
                  <div className="text-2xl font-bold text-white" data-testid="pc-potential">+%{result.revenue_potential_pct} gelir</div>
                  {result.annual_uplift_estimate && (
                    <div className="text-xs text-stone-400 mt-0.5">≈ €{Number(result.annual_uplift_estimate).toLocaleString("tr-TR")} / yıl ({rooms} oda için)</div>
                  )}
                </div>
                <button onClick={onDemo} data-testid="price-checker-demo-cta"
                  className="px-5 py-2.5 rounded-xl bg-emerald-500 text-sm font-semibold text-white hover:bg-emerald-400 inline-flex items-center gap-2 transition-colors">
                  Demo Talep Et <ArrowRight size={15} />
                </button>
              </div>
              <div className="mt-3 text-[10px] text-stone-500">* Pazar verileri tahminidir; birebir analiz için demo talep edin.</div>
              {result.lead_created && (
                <div className="mt-2 text-xs text-emerald-300" data-testid="price-checker-lead-note">
                  {["sent", "mock"].includes(result.report_email)
                    ? "✓ Detaylı pazar raporunuz e-postanıza gönderildi — ekibimiz de sizinle iletişime geçecek."
                    : "✓ Bilgileriniz alındı — ekibimiz detaylı pazar raporunuzla birlikte sizinle iletişime geçecek."}
                </div>
              )}
            </div>
          )}
        </motion.div>
      </div>
    </section>
  );
}

function Stat({ label, value, testId }) {
  return (
    <div className="rounded-xl bg-white/[0.04] border border-white/10 p-3" data-testid={testId}>
      <div className="text-base font-bold text-white leading-tight">{value}</div>
      <div className="text-[10px] text-stone-400 mt-0.5">{label}</div>
    </div>
  );
}
